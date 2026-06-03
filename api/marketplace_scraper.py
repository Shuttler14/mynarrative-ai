"""
================================================================================
  MY NARRATIVE AI — INDIAN MARKETPLACE PRODUCT SCRAPER
  api/marketplace_scraper.py
================================================================================

  PURPOSE:
  Vercel Serverless Function that scrapes Indian e-commerce marketplaces
  (Myntra, Flipkart, AJIO, Amazon.in) for fashion products. Since there are
  NO affiliate API accounts, we use intelligent web scraping with urllib.

  ENDPOINTS:
    POST  /api/marketplace_scraper   →  search_products | ingest_products | get_product
    GET   /api/marketplace_scraper   →  health check

  REQUIRED ENVIRONMENT VARIABLES:
  ────────────────────────────────
  SUPABASE_URL            → Supabase project URL
  SUPABASE_KEY            → Supabase anon/service key
  OPENAI_API_KEY          → OpenAI API key (for embeddings during ingest)

================================================================================
"""

from http.server import BaseHTTPRequestHandler
import hashlib
import html
import json
import os
import random
import re
import time
import threading
import urllib.parse
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional, Tuple

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

SUPPORTED_PLATFORMS = ["myntra", "flipkart", "ajio", "amazon"]

CATEGORY_MAP = {
    "topwear":     {"myntra": "topwear", "flipkart": "topwear", "ajio": "topwear", "amazon": "tops"},
    "bottomwear":  {"myntra": "bottomwear", "flipkart": "bottomwear", "ajio": "bottomwear", "amazon": "bottoms"},
    "footwear":    {"myntra": "footwear", "flipkart": "footwear", "ajio": "footwear", "amazon": "shoes"},
    "accessories": {"myntra": "accessories", "flipkart": "accessories", "ajio": "accessories", "amazon": "accessories"},
    "ethnic":      {"myntra": "ethnic-wear", "flipkart": "ethnic-wear", "ajio": "ethnic-wear", "amazon": "ethnic"},
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
]

# Rate limiting state (per platform, per serverless invocation)
_rate_limit_lock = threading.Lock()
_last_request_time: Dict[str, float] = {}
RATE_LIMITS = {
    "myntra": 2.0,
    "flipkart": 2.0,
    "ajio": 2.0,
    "amazon": 3.0,
}


def _extract_json_block(text: str, marker: str) -> Optional[dict]:
    """Robustly extract JSON block following a specified marker string."""
    idx = text.find(marker)
    if idx == -1:
        return None
    start = idx + len(marker)
    brace_idx = text.find('{', start)
    if brace_idx == -1:
        return None
    
    brace_count = 0
    in_string = False
    escape = False
    
    for i in range(brace_idx, len(text)):
        char = text[i]
        if escape:
            escape = False
            continue
        if char == '\\':
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if not in_string:
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    try:
                        return json.loads(text[brace_idx:i+1])
                    except Exception:
                        return None
    return None


# ---------------------------------------------------------------------------
# SUPABASE HELPERS (urllib REST API — same pattern as stylist_pipeline.py)
# ---------------------------------------------------------------------------

def _sb_headers() -> Tuple[str, str, dict]:
    """Return (url, key, headers) for Supabase REST API."""
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_KEY", "").strip()
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    return url, key, headers


def _sb_request(method: str, path: str, payload: Any = None) -> Tuple[Any, Optional[str]]:
    """Execute a Supabase REST API request. Returns (data, error_string)."""
    url, key, headers = _sb_headers()
    if not url or not key:
        return None, "supabase_not_configured"
    full_url = f"{url.rstrip('/')}{path}"
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(full_url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8") or "null"
            return json.loads(raw), None
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8")
        except Exception:
            detail = str(e)
        return None, f"http_{e.code}:{detail[:300]}"
    except Exception as e:
        return None, str(e)


def _sb_upsert_global_inventory(rows: list) -> Tuple[dict, Optional[str]]:
    """Upsert rows into global_inventory via Supabase REST."""
    if not rows:
        return {"inserted": 0}, None
    url, key, headers = _sb_headers()
    if not url or not key:
        return None, "supabase_not_configured"
    headers["Prefer"] = "resolution=merge-duplicates,return=representation"
    req = urllib.request.Request(
        f"{url.rstrip('/')}/rest/v1/global_inventory",
        data=json.dumps(rows).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8") or "[]")
            return {"inserted": len(data) if isinstance(data, list) else len(rows)}, None
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8")
        except Exception:
            detail = str(e)
        return None, f"http_{e.code}:{detail[:300]}"
    except Exception as e:
        return None, str(e)


def _sb_log_scrape(platform: str, query: str, category: str,
                   products_found: int, products_ingested: int,
                   errors: list, duration_ms: int):
    """Insert a row into marketplace_scrape_log for audit."""
    row = {
        "platform": platform,
        "query": query,
        "category": category or "",
        "products_found": products_found,
        "products_ingested": products_ingested,
        "errors": json.dumps(errors) if errors else "[]",
        "duration_ms": duration_ms,
    }
    _sb_request("POST", "/rest/v1/marketplace_scrape_log", row)


# ---------------------------------------------------------------------------
# HTTP FETCH HELPER
# ---------------------------------------------------------------------------

def _rate_limit_wait(platform: str):
    """Enforce per-platform rate limiting."""
    delay = RATE_LIMITS.get(platform, 2.0)
    with _rate_limit_lock:
        last = _last_request_time.get(platform, 0)
        elapsed = time.time() - last
        if elapsed < delay:
            time.sleep(delay - elapsed)
        _last_request_time[platform] = time.time()


def _fetch_page(url: str, platform: str, timeout: int = 15) -> Tuple[str, Optional[str]]:
    """
    Fetch a web page with rotating user-agent and rate limiting.
    Returns (html_content, error_string).
    """
    _rate_limit_wait(platform)
    ua = random.choice(USER_AGENTS)
    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8",
        "Accept-Encoding": "identity",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
    }
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            body = resp.read().decode(charset, errors="replace")
            return body, None
    except urllib.error.HTTPError as e:
        return "", f"http_{e.code}"
    except Exception as e:
        return "", str(e)[:200]


def _fetch_json(url: str, platform: str, timeout: int = 15,
                extra_headers: dict = None) -> Tuple[Any, Optional[str]]:
    """Fetch JSON from a URL. Returns (parsed_json, error_string)."""
    _rate_limit_wait(platform)
    ua = random.choice(USER_AGENTS)
    headers = {
        "User-Agent": ua,
        "Accept": "application/json, text/javascript, */*;q=0.01",
        "Accept-Language": "en-IN,en;q=0.9",
        "Accept-Encoding": "identity",
    }
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            raw = resp.read().decode(charset, errors="replace")
            return json.loads(raw), None
    except urllib.error.HTTPError as e:
        return None, f"http_{e.code}"
    except json.JSONDecodeError as e:
        return None, f"json_parse_error:{str(e)[:100]}"
    except Exception as e:
        return None, str(e)[:200]


# ---------------------------------------------------------------------------
# PRODUCT NORMALIZER
# ---------------------------------------------------------------------------

def _normalize_scraped_product(raw: dict, platform: str) -> dict:
    """
    Normalize a raw scraped product dict into the canonical global_inventory schema.
    All prices in INR (₹).
    """
    def _get(keys: list, default=""):
        for k in keys:
            v = raw.get(k)
            if v is not None and str(v).strip():
                return v
        return default

    def _parse_price(val) -> float:
        if val is None:
            return 0.0
        s = str(val).replace(",", "").replace("₹", "").replace("Rs.", "").replace("Rs", "").strip()
        try:
            return round(float(re.sub(r"[^\d.]", "", s)), 2) if s else 0.0
        except (ValueError, TypeError):
            return 0.0

    title = str(_get(["title", "name", "productName", "product_name"], "")).strip()
    brand = str(_get(["brand", "brandName", "brand_name"], "")).strip()
    price = _parse_price(_get(["price", "discounted_price", "sale_price", "salePrice"], 0))
    original_price = _parse_price(_get(["original_price", "mrp", "originalPrice", "retail_price"], 0))
    if original_price <= 0:
        original_price = price

    discount_pct = 0
    if original_price > 0 and price > 0 and price < original_price:
        discount_pct = int(round(((original_price - price) / original_price) * 100))

    rating = 0.0
    raw_rating = _get(["rating", "averageRating", "average_rating"], 0)
    try:
        rating = round(float(raw_rating), 1)
    except (ValueError, TypeError):
        rating = 0.0

    reviews_count = 0
    raw_reviews = _get(["reviews_count", "ratingCount", "rating_count", "totalReviews"], 0)
    try:
        reviews_count = int(float(str(raw_reviews).replace(",", "")))
    except (ValueError, TypeError):
        reviews_count = 0

    image_url = str(_get(["image_url", "imageUrl", "image", "searchImage"], "")).strip()
    # Ensure HTTPS
    if image_url.startswith("//"):
        image_url = "https:" + image_url

    checkout_url = str(_get(["checkout_url", "product_url", "productUrl", "url", "link"], "")).strip()
    sizes_raw = _get(["sizes", "availableSizes", "available_sizes"], [])
    if isinstance(sizes_raw, str):
        try:
            sizes_raw = json.loads(sizes_raw)
        except (json.JSONDecodeError, ValueError):
            sizes_raw = [s.strip() for s in sizes_raw.split(",") if s.strip()]

    return {
        "network": platform.lower(),
        "external_product_id": str(_get(["id", "productId", "product_id", "pid", "asin", "sku"], f"{platform}_{hashlib.md5(title.encode()).hexdigest()[:12]}")),
        "title": title,
        "brand": brand,
        "category": str(_get(["category", "masterCategory", "productType", "type"], "")).strip().lower(),
        "price": price,
        "original_price": original_price,
        "discount_pct": discount_pct,
        "currency": "INR",
        "image_url": image_url,
        "flat_lay_url": "",
        "checkout_url": checkout_url,
        "affiliate_url": checkout_url,
        "rating": rating,
        "reviews_count": reviews_count,
        "source_platform": platform.lower(),
        "description": str(_get(["description", "shortDescription", "desc"], "")).strip()[:500],
        "sizes": sizes_raw if isinstance(sizes_raw, list) else [],
    }


# ---------------------------------------------------------------------------
# PLATFORM SCRAPERS
# ---------------------------------------------------------------------------

def _scrape_myntra(query: str, category: str, price_min: int, price_max: int, limit: int) -> Tuple[List[dict], Optional[str]]:
    """
    Scrape Myntra for products.
    Strategy: Fetch search page → extract window.__myx or embedded JSON from <script> tags.
    """
    print(f"🛍️ [myntra] Scraping: query='{query}' category='{category}' limit={limit}")
    products = []
    try:
        cat_slug = CATEGORY_MAP.get(category, {}).get("myntra", category or "")
        path = f"{cat_slug}" if cat_slug else "search"
        params = {"rawQuery": query, "sort": "popularity"}
        if price_min and price_min > 0:
            params["p_price"] = f"{price_min}-{price_max}" if price_max else f"{price_min}-100000"
        url = f"https://www.myntra.com/{path}?{urllib.parse.urlencode(params)}"

        page_html, err = _fetch_page(url, "myntra")
        if err:
            print(f"⚠️ [myntra] Fetch error: {err}")
            return [], err

        # Strategy 1: Look for window.__myx JSON blob
        myx_data = _extract_json_block(page_html, "window.__myx = ")
        if myx_data:
            try:
                search_data = myx_data.get("searchData", {}).get("results", {})
                product_list = search_data.get("products", [])
                for p in product_list[:limit]:
                    products.append(_normalize_scraped_product({
                        "id": p.get("productId"),
                        "title": p.get("productName", ""),
                        "brand": p.get("brand", ""),
                        "price": p.get("price") or p.get("discountedPrice"),
                        "original_price": p.get("mrp") or p.get("price"),
                        "rating": p.get("rating", 0),
                        "reviews_count": p.get("ratingCount", 0),
                        "image_url": p.get("searchImage", ""),
                        "product_url": f"https://www.myntra.com/{p.get('landingPageUrl', '')}",
                        "sizes": p.get("sizes", []),
                        "category": category,
                    }, "myntra"))
                print(f"✅ [myntra] __myx extracted {len(products)} products")
                return products[:limit], None
            except Exception as e:
                print(f"⚠️ [myntra] __myx parse failed: {e}")

        # Strategy 2: Look for application/ld+json structured data
        ld_json_matches = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', page_html, re.DOTALL)
        for ld_raw in ld_json_matches:
            try:
                ld = json.loads(ld_raw)
                items = ld if isinstance(ld, list) else ld.get("itemListElement", [])
                for item in items[:limit]:
                    obj = item.get("item", item) if isinstance(item, dict) else item
                    if not isinstance(obj, dict):
                        continue
                    products.append(_normalize_scraped_product({
                        "title": obj.get("name", ""),
                        "brand": obj.get("brand", {}).get("name", "") if isinstance(obj.get("brand"), dict) else str(obj.get("brand", "")),
                        "price": obj.get("offers", {}).get("price", 0) if isinstance(obj.get("offers"), dict) else 0,
                        "image_url": obj.get("image", ""),
                        "product_url": obj.get("url", ""),
                        "category": category,
                    }, "myntra"))
            except (json.JSONDecodeError, KeyError):
                continue

        # Strategy 3: Regex fallback on product card HTML
        if not products:
            card_pattern = re.compile(
                r'<li[^>]*class="[^"]*product-base[^"]*"[^>]*>.*?'
                r'<a[^>]*href="([^"]*)"[^>]*>.*?'
                r'<img[^>]*(?:src|data-src)="([^"]*)"[^>]*>.*?'
                r'<h3[^>]*class="[^"]*product-brand[^"]*"[^>]*>(.*?)</h3>.*?'
                r'<h4[^>]*class="[^"]*product-product[^"]*"[^>]*>(.*?)</h4>',
                re.DOTALL | re.IGNORECASE
            )
            for m in card_pattern.finditer(page_html):
                link, img, brand_html, title_html = m.groups()
                products.append(_normalize_scraped_product({
                    "title": html.unescape(title_html.strip()),
                    "brand": html.unescape(brand_html.strip()),
                    "image_url": img,
                    "product_url": f"https://www.myntra.com{link}" if link.startswith("/") else link,
                    "category": category,
                }, "myntra"))
                if len(products) >= limit:
                    break

        print(f"✅ [myntra] Scraped {len(products)} products")
        return products[:limit], None

    except Exception as e:
        print(f"❌ [myntra] Exception: {e}")
        return products[:limit] if products else [], str(e)[:200]


def _scrape_flipkart(query: str, category: str, price_min: int, price_max: int, limit: int) -> Tuple[List[dict], Optional[str]]:
    """
    Scrape Flipkart for products.
    Strategy: Parse product cards from HTML + ld+json structured data.
    """
    print(f"🛒 [flipkart] Scraping: query='{query}' category='{category}' limit={limit}")
    products = []
    try:
        params = {"q": query, "sort": "relevance"}
        if price_min and price_min > 0:
            params["p[]"] = f"facets.price_range.from={price_min}&facets.price_range.to={price_max or 100000}"
        url = f"https://www.flipkart.com/search?{urllib.parse.urlencode(params)}"

        page_html, err = _fetch_page(url, "flipkart")
        if err:
            print(f"⚠️ [flipkart] Fetch error: {err}")
            return [], err

        # Strategy 1: ld+json structured data
        ld_json_matches = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', page_html, re.DOTALL)
        for ld_raw in ld_json_matches:
            try:
                ld = json.loads(ld_raw)
                items = []
                if isinstance(ld, list):
                    items = ld
                elif isinstance(ld, dict):
                    if ld.get("@type") == "ItemList":
                        items = ld.get("itemListElement", [])
                    elif ld.get("@type") == "Product":
                        items = [ld]
                for item in items[:limit]:
                    obj = item.get("item", item) if isinstance(item, dict) else {}
                    if not isinstance(obj, dict):
                        continue
                    offers = obj.get("offers", {})
                    if isinstance(offers, list) and offers:
                        offers = offers[0]
                    elif not isinstance(offers, dict):
                        offers = {}
                    products.append(_normalize_scraped_product({
                        "title": obj.get("name", ""),
                        "brand": obj.get("brand", {}).get("name", "") if isinstance(obj.get("brand"), dict) else str(obj.get("brand", "")),
                        "price": offers.get("price", 0),
                        "image_url": obj.get("image", ""),
                        "product_url": obj.get("url", ""),
                        "rating": obj.get("aggregateRating", {}).get("ratingValue", 0) if isinstance(obj.get("aggregateRating"), dict) else 0,
                        "reviews_count": obj.get("aggregateRating", {}).get("reviewCount", 0) if isinstance(obj.get("aggregateRating"), dict) else 0,
                        "category": category,
                    }, "flipkart"))
            except (json.JSONDecodeError, KeyError):
                continue

        # Strategy 2: HTML product card parsing
        if not products:
            # Flipkart product card patterns (multiple layouts)
            title_pattern = re.compile(
                r'<a[^>]*href="(/[^"]*)"[^>]*title="([^"]*)"[^>]*>.*?'
                r'<img[^>]*(?:src|data-src)="([^"]*)"',
                re.DOTALL | re.IGNORECASE
            )
            price_pattern = re.compile(r'₹\s*([\d,]+)', re.IGNORECASE)

            for m in title_pattern.finditer(page_html):
                link, title_text, img = m.groups()
                # Find nearby price
                nearby = page_html[m.start():m.start() + 2000]
                price_m = price_pattern.search(nearby)
                price_val = price_m.group(1).replace(",", "") if price_m else "0"

                products.append(_normalize_scraped_product({
                    "title": html.unescape(title_text.strip()),
                    "price": price_val,
                    "image_url": img,
                    "product_url": f"https://www.flipkart.com{link}" if link.startswith("/") else link,
                    "category": category,
                }, "flipkart"))
                if len(products) >= limit:
                    break

        print(f"✅ [flipkart] Scraped {len(products)} products")
        return products[:limit], None

    except Exception as e:
        print(f"❌ [flipkart] Exception: {e}")
        return products[:limit] if products else [], str(e)[:200]


def _scrape_ajio(query: str, category: str, price_min: int, price_max: int, limit: int) -> Tuple[List[dict], Optional[str]]:
    """
    Scrape AJIO for products.
    Strategy: Try internal JSON API first, fall back to HTML scraping.
    """
    print(f"👗 [ajio] Scraping: query='{query}' category='{category}' limit={limit}")
    products = []
    try:
        # Strategy 1: AJIO internal search API
        params = {
            "searchQuery": query,
            "sortBy": "relevance",
            "gridColumns": 3,
            "text": query,
        }
        if price_min and price_min > 0:
            params["priceRange"] = f"{price_min}-{price_max or 100000}"
        api_url = f"https://www.ajio.com/api/search?{urllib.parse.urlencode(params)}"

        data, err = _fetch_json(api_url, "ajio", extra_headers={
            "Referer": "https://www.ajio.com/",
            "X-Requested-With": "XMLHttpRequest",
        })

        if not err and data and isinstance(data, dict):
            product_list = data.get("products", [])
            if not product_list:
                # Try nested response structure
                product_list = data.get("searchResponse", {}).get("products", [])
            for p in product_list[:limit]:
                if not isinstance(p, dict):
                    continue
                img = p.get("images", [{}])
                image_url = img[0].get("url", "") if isinstance(img, list) and img else p.get("fnlColorVariantData", {}).get("colorSwatchUrl", "")
                if not image_url:
                    image_url = p.get("imageUrl", "") or p.get("img", "")

                products.append(_normalize_scraped_product({
                    "id": p.get("code", ""),
                    "title": p.get("name", ""),
                    "brand": p.get("fnlColorVariantData", {}).get("brandName", "") or p.get("brandName", ""),
                    "price": p.get("price", {}).get("value", 0) if isinstance(p.get("price"), dict) else p.get("price", 0),
                    "original_price": p.get("wasPriceData", {}).get("value", 0) if isinstance(p.get("wasPriceData"), dict) else p.get("mrp", 0),
                    "rating": p.get("rating", 0),
                    "reviews_count": p.get("numberOfReviews", 0),
                    "image_url": f"https://assets.ajio.com/medias/{image_url}" if image_url and not image_url.startswith("http") else image_url,
                    "product_url": f"https://www.ajio.com{p.get('url', '')}" if p.get("url", "").startswith("/") else p.get("url", ""),
                    "category": category,
                    "sizes": [s.get("value", "") for s in p.get("allSizes", []) if isinstance(s, dict)] if isinstance(p.get("allSizes"), list) else [],
                }, "ajio"))
            if products:
                print(f"✅ [ajio] API extracted {len(products)} products")
                return products[:limit], None

        # Strategy 2: Fall back to HTML scraping
        print(f"⚠️ [ajio] API failed ({err or 'empty'}), falling back to HTML scraping")
        html_url = f"https://www.ajio.com/search/?text={urllib.parse.quote(query)}"
        page_html, html_err = _fetch_page(html_url, "ajio")
        if html_err:
            return [], html_err

        # Parse embedded JSON in __PRELOADED_STATE__ or script blocks
        state = _extract_json_block(page_html, "window.__PRELOADED_STATE__ = ")
        if state:
            try:
                grid = state.get("grid", {}).get("entities", {})
                for pid, p in grid.items():
                    if not isinstance(p, dict):
                        continue
                    products.append(_normalize_scraped_product({
                        "id": pid,
                        "title": p.get("name", ""),
                        "brand": p.get("brandName", ""),
                        "price": p.get("price", 0),
                        "original_price": p.get("wasPrice", 0),
                        "image_url": p.get("images", [""])[0] if p.get("images") else "",
                        "product_url": f"https://www.ajio.com{p.get('url', '')}",
                        "category": category,
                    }, "ajio"))
                    if len(products) >= limit:
                        break
            except Exception as e:
                print(f"⚠️ [ajio] __PRELOADED_STATE__ parse failed: {e}")

        print(f"✅ [ajio] HTML scraped {len(products)} products")
        return products[:limit], None

    except Exception as e:
        print(f"❌ [ajio] Exception: {e}")
        return products[:limit] if products else [], str(e)[:200]


def _scrape_amazon(query: str, category: str, price_min: int, price_max: int, limit: int) -> Tuple[List[dict], Optional[str]]:
    """
    Scrape Amazon.in for products.
    Strategy: Parse product cards by data-asin attributes.
    Handles captcha detection gracefully.
    """
    print(f"📦 [amazon] Scraping: query='{query}' category='{category}' limit={limit}")
    products = []
    try:
        params = {"k": query, "ref": "nb_sb_noss"}
        if price_min and price_min > 0:
            rh_parts = []
            rh_parts.append(f"p_36:{price_min * 100}-{(price_max or 100000) * 100}")
            params["rh"] = ",".join(rh_parts)
        url = f"https://www.amazon.in/s?{urllib.parse.urlencode(params)}"

        page_html, err = _fetch_page(url, "amazon")
        if err:
            print(f"⚠️ [amazon] Fetch error: {err}")
            return [], err

        # Captcha detection
        captcha_indicators = ["captcha", "robot check", "sorry, we just need to make sure",
                              "enter the characters you see", "Type the characters"]
        html_lower = page_html.lower()
        if any(indicator.lower() in html_lower for indicator in captcha_indicators):
            print(f"🤖 [amazon] Captcha detected — returning empty results")
            return [], "captcha_detected"

        # Parse product cards with data-asin
        asin_pattern = re.compile(r'data-asin="([A-Z0-9]{10})"', re.IGNORECASE)
        asins_seen = set()

        # Split page into product card segments
        card_segments = re.split(r'data-asin="([A-Z0-9]{10})"', page_html, flags=re.IGNORECASE)

        # Process pairs: (asin, card_html)
        for i in range(1, len(card_segments) - 1, 2):
            if len(products) >= limit:
                break
            asin = card_segments[i]
            if not asin or asin in asins_seen or asin == "":
                continue
            asins_seen.add(asin)
            card_html = card_segments[i + 1] if (i + 1) < len(card_segments) else ""

            # Extract title
            title_match = re.search(
                r'<span[^>]*class="[^"]*a-(?:size-medium|text-normal)[^"]*"[^>]*>(.*?)</span>',
                card_html, re.DOTALL | re.IGNORECASE
            )
            title = html.unescape(title_match.group(1).strip()) if title_match else ""
            if not title:
                # Fallback title extraction
                alt_match = re.search(r'<img[^>]*alt="([^"]{10,})"', card_html, re.IGNORECASE)
                title = html.unescape(alt_match.group(1).strip()) if alt_match else ""
            if not title:
                continue

            # Extract price
            price_match = re.search(r'<span[^>]*class="[^"]*a-price-whole[^"]*"[^>]*>([\d,]+)', card_html, re.IGNORECASE)
            price_val = price_match.group(1).replace(",", "") if price_match else "0"

            # Extract original price (strikethrough)
            orig_price_match = re.search(
                r'<span[^>]*class="[^"]*a-price[^"]*a-text-price[^"]*"[^>]*>.*?<span[^>]*>(₹?\s*[\d,]+)',
                card_html, re.DOTALL | re.IGNORECASE
            )
            orig_price_val = orig_price_match.group(1).replace("₹", "").replace(",", "").strip() if orig_price_match else price_val

            # Extract image
            img_match = re.search(r'<img[^>]*(?:src|data-src)="(https://m\.media-amazon\.com/images/[^"]*)"', card_html, re.IGNORECASE)
            if not img_match:
                img_match = re.search(r'<img[^>]*(?:src|data-src)="(https://[^"]*images[^"]*)"', card_html, re.IGNORECASE)
            image_url = img_match.group(1) if img_match else ""

            # Extract rating
            rating_match = re.search(r'(\d+\.?\d*)\s*out of\s*5', card_html, re.IGNORECASE)
            rating = rating_match.group(1) if rating_match else "0"

            # Extract review count
            review_match = re.search(r'<span[^>]*class="[^"]*a-size-base[^"]*s-underline-text[^"]*"[^>]*>([\d,]+)', card_html, re.IGNORECASE)
            if not review_match:
                review_match = re.search(r'aria-label="([\d,]+)\s*(?:ratings|reviews)', card_html, re.IGNORECASE)
            reviews = review_match.group(1).replace(",", "") if review_match else "0"

            products.append(_normalize_scraped_product({
                "asin": asin,
                "title": title,
                "price": price_val,
                "original_price": orig_price_val,
                "rating": rating,
                "reviews_count": reviews,
                "image_url": image_url,
                "product_url": f"https://www.amazon.in/dp/{asin}",
                "category": category,
            }, "amazon"))

        print(f"✅ [amazon] Scraped {len(products)} products")
        return products[:limit], None

    except Exception as e:
        print(f"❌ [amazon] Exception: {e}")
        return products[:limit] if products else [], str(e)[:200]


# ---------------------------------------------------------------------------
# ORCHESTRATORS
# ---------------------------------------------------------------------------

SCRAPER_MAP = {
    "myntra":   _scrape_myntra,
    "flipkart": _scrape_flipkart,
    "ajio":     _scrape_ajio,
    "amazon":   _scrape_amazon,
}


def _search_products(query: str, platform: str, category: str,
                     price_min: int, price_max: int, limit: int) -> dict:
    """
    Search products across one or more platforms. Uses threading for parallel
    scraping when platform='all'.
    """
    start_time = time.time()
    platforms_to_scrape = SUPPORTED_PLATFORMS if platform == "all" else [platform]
    all_products = []
    platform_stats = {}
    errors_list = []

    def _run_scraper(plat: str):
        scraper = SCRAPER_MAP.get(plat)
        if not scraper:
            platform_stats[plat] = {"count": 0, "status": "unsupported"}
            return
        try:
            per_platform_limit = max(5, limit // len(platforms_to_scrape)) if platform == "all" else limit
            results, err = scraper(query, category, price_min, price_max, per_platform_limit)
            platform_stats[plat] = {
                "count": len(results),
                "status": "success" if not err else f"partial:{err}",
            }
            if err:
                errors_list.append({"platform": plat, "error": err})
            all_products.extend(results)
        except Exception as e:
            platform_stats[plat] = {"count": 0, "status": f"error:{str(e)[:100]}"}
            errors_list.append({"platform": plat, "error": str(e)[:200]})

    if len(platforms_to_scrape) > 1:
        # Parallel scraping with threads
        threads = []
        for plat in platforms_to_scrape:
            t = threading.Thread(target=_run_scraper, args=(plat,), daemon=True)
            threads.append(t)
            t.start()
        for t in threads:
            t.join(timeout=30)
    else:
        for plat in platforms_to_scrape:
            _run_scraper(plat)

    # Apply price filter post-scrape
    if price_min and price_min > 0:
        all_products = [p for p in all_products if p.get("price", 0) >= price_min]
    if price_max and price_max > 0:
        all_products = [p for p in all_products if p.get("price", 0) <= price_max or p.get("price", 0) == 0]

    # Sort by rating (descending), then price (ascending)
    all_products.sort(key=lambda p: (-float(p.get("rating", 0) or 0), float(p.get("price", 0) or 0)))
    all_products = all_products[:limit]

    elapsed = round((time.time() - start_time) * 1000)
    print(f"📊 [search_products] Total: {len(all_products)} products in {elapsed}ms across {list(platform_stats.keys())}")

    return {
        "success": True,
        "query": query,
        "total_results": len(all_products),
        "platforms": platform_stats,
        "products": all_products,
        "processing_time_ms": elapsed,
        "errors": errors_list if errors_list else None,
    }


def _dedup_hash(product: dict) -> str:
    """Create a deduplication hash from title + brand + price."""
    raw = f"{(product.get('title', '') or '').lower().strip()}|{(product.get('brand', '') or '').lower().strip()}|{product.get('price', 0)}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _ingest_products(query: str, platform: str, category: str,
                     price_min: int, price_max: int, limit: int,
                     generate_embeddings: bool) -> dict:
    """
    Full ingestion pipeline:
    1. Search products across platforms
    2. Deduplicate by title+brand+price hash
    3. Optionally generate OpenAI text-embedding-3-small vectors
    4. Upsert into Supabase global_inventory
    5. Log scrape audit
    """
    start_time = time.time()
    print(f"📥 [ingest_products] Starting ingestion: query='{query}' generate_embeddings={generate_embeddings}")

    # Step 1: Search
    search_result = _search_products(query, platform, category, price_min, price_max, limit)
    raw_products = search_result.get("products", [])
    platform_stats = search_result.get("platforms", {})

    if not raw_products:
        return {
            "success": True,
            "query": query,
            "stats": {
                "total_scraped": 0,
                "deduplicated": 0,
                "ingested": 0,
                "embeddings_generated": 0,
            },
            "platforms": platform_stats,
            "processing_time_ms": round((time.time() - start_time) * 1000),
        }

    # Step 2: Deduplicate
    seen_hashes = set()
    unique_products = []
    for p in raw_products:
        h = _dedup_hash(p)
        if h not in seen_hashes:
            seen_hashes.add(h)
            unique_products.append(p)
    dedup_removed = len(raw_products) - len(unique_products)
    print(f"🔀 [ingest] Dedup: {len(raw_products)} → {len(unique_products)} (removed {dedup_removed} dupes)")

    # Step 3: Optionally generate embeddings
    embeddings_generated = 0
    if generate_embeddings and OPENAI_AVAILABLE:
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if api_key:
            try:
                client = OpenAI(api_key=api_key)
                for p in unique_products:
                    emb_text = f"{p.get('title', '')} | {p.get('brand', '')} | {p.get('category', '')} | {p.get('description', '')}"
                    emb_text = emb_text.strip()
                    if not emb_text or emb_text == "| | |":
                        continue
                    try:
                        resp = client.embeddings.create(model="text-embedding-3-small", input=emb_text)
                        vec = resp.data[0].embedding if resp and resp.data else []
                        if vec:
                            p["embedding"] = vec
                            embeddings_generated += 1
                    except Exception as emb_err:
                        print(f"⚠️ [ingest] Embedding error for '{p.get('title', '')[:30]}': {emb_err}")
                print(f"🧠 [ingest] Generated {embeddings_generated} embeddings")
            except Exception as e:
                print(f"⚠️ [ingest] OpenAI client error: {e}")
        else:
            print(f"⚠️ [ingest] OPENAI_API_KEY not set — skipping embeddings")

    # Step 4: Upsert to Supabase
    upsert_rows = []
    for p in unique_products:
        row = {
            "network": p.get("network", p.get("source_platform", "")),
            "external_product_id": p.get("external_product_id", ""),
            "title": p.get("title", ""),
            "brand": p.get("brand", ""),
            "category": p.get("category", ""),
            "description": p.get("description", ""),
            "price": p.get("price", 0),
            "original_price": p.get("original_price", 0),
            "discount_pct": p.get("discount_pct", 0),
            "currency": "INR",
            "image_url": p.get("image_url", ""),
            "flat_lay_url": p.get("flat_lay_url", ""),
            "checkout_url": p.get("checkout_url", ""),
            "affiliate_url": p.get("affiliate_url", p.get("checkout_url", "")),
            "rating": p.get("rating", 0),
            "reviews_count": p.get("reviews_count", 0),
            "sizes": json.dumps(p.get("sizes", [])),
            "source_platform": p.get("source_platform", ""),
            "quality_score": 0.7,
            "is_clean": True,
            "filter_reason": "marketplace_scrape",
            "scrape_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        if p.get("embedding"):
            row["embedding"] = p["embedding"]
        upsert_rows.append(row)

    ingested_count = 0
    upsert_err = None
    if upsert_rows:
        # Batch in chunks of 50 to avoid payload limits
        for i in range(0, len(upsert_rows), 50):
            batch = upsert_rows[i:i + 50]
            result, err = _sb_upsert_global_inventory(batch)
            if err:
                upsert_err = err
                print(f"⚠️ [ingest] Supabase upsert error (batch {i // 50}): {err}")
            else:
                ingested_count += (result or {}).get("inserted", len(batch))

    # Step 5: Log scrape audit
    elapsed = round((time.time() - start_time) * 1000)
    for plat, stats in platform_stats.items():
        _sb_log_scrape(
            platform=plat,
            query=query,
            category=category or "",
            products_found=stats.get("count", 0),
            products_ingested=ingested_count,
            errors=search_result.get("errors", []),
            duration_ms=elapsed,
        )

    print(f"✅ [ingest_products] Done: {ingested_count} ingested in {elapsed}ms")

    return {
        "success": upsert_err is None,
        "query": query,
        "stats": {
            "total_scraped": len(raw_products),
            "deduplicated": len(unique_products),
            "duplicates_removed": dedup_removed,
            "ingested": ingested_count,
            "embeddings_generated": embeddings_generated,
        },
        "platforms": platform_stats,
        "processing_time_ms": elapsed,
        "error": upsert_err,
    }


def _get_product(product_url: str) -> dict:
    """
    Fetch a single product by URL. Detects platform from URL and scrapes
    the product page for details.
    """
    print(f"🔍 [get_product] URL: {product_url}")
    url_lower = (product_url or "").lower()
    platform = "unknown"
    if "myntra.com" in url_lower:
        platform = "myntra"
    elif "flipkart.com" in url_lower:
        platform = "flipkart"
    elif "ajio.com" in url_lower:
        platform = "ajio"
    elif "amazon.in" in url_lower or "amazon.co.in" in url_lower:
        platform = "amazon"

    if platform == "unknown":
        return {"success": False, "error": "Unsupported platform URL. Supported: Myntra, Flipkart, AJIO, Amazon.in"}

    page_html, err = _fetch_page(product_url, platform, timeout=20)
    if err:
        return {"success": False, "error": f"Failed to fetch product page: {err}"}

    product_data = {"source_platform": platform, "product_url": product_url, "category": ""}

    # Extract ld+json product data (most reliable across platforms)
    ld_json_matches = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', page_html, re.DOTALL)
    for ld_raw in ld_json_matches:
        try:
            ld = json.loads(ld_raw)
            if isinstance(ld, dict) and ld.get("@type") == "Product":
                product_data["title"] = ld.get("name", "")
                product_data["brand"] = ld.get("brand", {}).get("name", "") if isinstance(ld.get("brand"), dict) else str(ld.get("brand", ""))
                product_data["description"] = ld.get("description", "")
                product_data["image_url"] = ld.get("image", "")
                offers = ld.get("offers", {})
                if isinstance(offers, list) and offers:
                    offers = offers[0]
                if isinstance(offers, dict):
                    product_data["price"] = offers.get("price", 0)
                    product_data["original_price"] = offers.get("highPrice", offers.get("price", 0))
                agg = ld.get("aggregateRating", {})
                if isinstance(agg, dict):
                    product_data["rating"] = agg.get("ratingValue", 0)
                    product_data["reviews_count"] = agg.get("reviewCount", 0)
                break
        except (json.JSONDecodeError, KeyError):
            continue

    # Fallback: extract title from <title> tag
    if not product_data.get("title"):
        title_match = re.search(r"<title[^>]*>(.*?)</title>", page_html, re.DOTALL | re.IGNORECASE)
        if title_match:
            product_data["title"] = html.unescape(title_match.group(1).strip())

    if not product_data.get("title"):
        return {"success": False, "error": "Could not extract product data from page"}

    normalized = _normalize_scraped_product(product_data, platform)
    return {"success": True, "product": normalized, "platform": platform}


# ============================================================================
#  VERCEL SERVERLESS HANDLER
# ============================================================================

class handler(BaseHTTPRequestHandler):
    """
    POST /api/marketplace_scraper
    ─────────────────────────────
    Indian e-commerce marketplace product scraper.

    Actions:
      search_products  — Search across Myntra, Flipkart, AJIO, Amazon.in
      ingest_products  — Search + deduplicate + embed + upsert to Supabase
      get_product      — Fetch single product by URL

    GET  /api/marketplace_scraper → Health check
    """

    def _cors_headers(self):
        """Set CORS headers for cross-origin requests."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS, GET")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Max-Age", "86400")

    def _respond(self, status: int, data: dict):
        """Send a JSON response with CORS headers."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self._cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode("utf-8"))

    def _error(self, status: int, message: str):
        """Send an error JSON response."""
        self._respond(status, {"success": False, "error": message})

    def _success(self, data: dict):
        """Send a success JSON response."""
        data["success"] = True
        self._respond(200, data)

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(200)
        self._cors_headers()
        self.end_headers()

    def do_GET(self):
        """Health check returning supported platforms and status."""
        self._respond(200, {
            "service": "My Narrative — Marketplace Scraper",
            "version": "1.0.0",
            "status": "operational",
            "supported_platforms": SUPPORTED_PLATFORMS,
            "supported_categories": list(CATEGORY_MAP.keys()),
            "rate_limits": RATE_LIMITS,
            "supabase_configured": bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_KEY")),
            "openai_configured": OPENAI_AVAILABLE and bool(os.environ.get("OPENAI_API_KEY")),
        })

    def do_POST(self):
        """Main POST handler — dispatches to action handlers."""
        # ─── Parse request body ───
        content_length = int(self.headers.get("Content-Length", 0))

        # Vercel Hobby plan limit: 4.5 MB
        MAX_BODY_SIZE = 4.5 * 1024 * 1024
        if content_length > MAX_BODY_SIZE:
            self._error(413, "Payload too large. Max 4.5 MB.")
            return

        raw_body = b""
        if content_length > 0:
            raw_body = self.rfile.read(content_length)

        if not raw_body:
            self._error(400, "Empty request body. Please provide valid JSON.")
            return

        try:
            body = json.loads(raw_body)
        except json.JSONDecodeError:
            self._error(400, "Invalid JSON in request body.")
            return

        action = body.get("action", "").strip().lower()
        if not action:
            self._error(400, "Missing 'action' field. Valid: search_products, ingest_products, get_product")
            return

        # ─── ACTION: search_products ───
        if action == "search_products":
            query = (body.get("query") or "").strip()
            if not query:
                self._error(400, "Missing 'query' field for search_products.")
                return
            platform = (body.get("platform") or "all").strip().lower()
            if platform != "all" and platform not in SUPPORTED_PLATFORMS:
                self._error(400, f"Invalid platform '{platform}'. Valid: all, {', '.join(SUPPORTED_PLATFORMS)}")
                return
            category = (body.get("category") or "").strip().lower()
            price_min = int(body.get("price_min") or 0)
            price_max = int(body.get("price_max") or 0)
            limit = min(100, max(1, int(body.get("limit") or 20)))

            result = _search_products(query, platform, category, price_min, price_max, limit)
            self._respond(200, result)
            return

        # ─── ACTION: ingest_products ───
        if action == "ingest_products":
            query = (body.get("query") or "").strip()
            if not query:
                self._error(400, "Missing 'query' field for ingest_products.")
                return

            # Check Supabase configuration
            sb_url = os.environ.get("SUPABASE_URL", "").strip()
            sb_key = os.environ.get("SUPABASE_KEY", "").strip()
            if not sb_url or not sb_key:
                self._error(500, "SUPABASE_URL and SUPABASE_KEY must be configured for ingestion.")
                return

            platform = (body.get("platform") or "all").strip().lower()
            if platform != "all" and platform not in SUPPORTED_PLATFORMS:
                self._error(400, f"Invalid platform '{platform}'. Valid: all, {', '.join(SUPPORTED_PLATFORMS)}")
                return
            category = (body.get("category") or "").strip().lower()
            price_min = int(body.get("price_min") or 0)
            price_max = int(body.get("price_max") or 0)
            limit = min(100, max(1, int(body.get("limit") or 20)))
            generate_embeddings = bool(body.get("generate_embeddings", False))

            result = _ingest_products(query, platform, category, price_min, price_max, limit, generate_embeddings)
            self._respond(200, result)
            return

        # ─── ACTION: get_product ───
        if action == "get_product":
            product_url = (body.get("product_url") or body.get("url") or "").strip()
            if not product_url or not product_url.startswith("http"):
                self._error(400, "Missing or invalid 'product_url'. Must be a valid HTTP(S) URL.")
                return
            result = _get_product(product_url)
            self._respond(200, result)
            return

        # ─── Unknown action ───
        self._error(400, f"Unknown action: '{action}'. Valid: search_products, ingest_products, get_product")

    def log_message(self, format, *args):
        """Suppress default stderr logging in production."""
        pass
