"""
Drishti API v2 — Fly.io Flask app.
Rebuilt from the proven Jul 26 working Drishti backend patterns.
"""
import asyncio
import base64
import json
import logging
import os
import random
import time

import httpx
import replicate
import requests as sync_requests
from flask import Flask, request, jsonify
from flask_cors import CORS

import re
import html as html_mod
import urllib.parse
import urllib.request

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

logger = logging.getLogger("drishti.v2")

VERCEL_API = "https://drishti-api-blond.vercel.app"
REPLICATE_API = "https://api.replicate.com/v1"


def _get_token():
    return os.environ.get("REPLICATE_API_TOKEN", "")


def _get_rembg_version():
    return os.environ.get("REPLICATE_REMBG_VERSION", "fb8af171cfa1616ddcf1242c093f9c46bcada5ad4cf6f2fbe8b81b330ec5c003")


def _get_vton_version():
    return os.environ.get("REPLICATE_VTON_VERSION", "")


# ═══════════════════════════════════════════════════════════════════════════
# PROVEN PATTERN: Download image as data URI (fixes Google Shopping 404s,
# CDN blocking, expiring R2 URLs — the key fix from Jul 26 commit a9584dc)
# ═══════════════════════════════════════════════════════════════════════════

def _download_as_data_uri(url):
    """Download image URL → base64 data URI. Handles Google Shopping, CDN, R2."""
    if not url or url.startswith("data:"):
        return url
    try:
        resp = sync_requests.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "https://www.google.com/",
        }, timeout=20, allow_redirects=True)
        resp.raise_for_status()
        img_bytes = resp.content
        if img_bytes[:8] == b'\x89PNG\r\n\x1a\n':
            ct = "image/png"
        elif img_bytes[:3] == b'\xff\xd8\xff':
            ct = "image/jpeg"
        elif img_bytes[:4] == b'RIFF' and len(img_bytes) > 12 and img_bytes[8:12] == b'WEBP':
            ct = "image/webp"
        else:
            ct = "image/jpeg"
        b64 = base64.b64encode(img_bytes).decode()
        logger.info(f"Downloaded image ({len(img_bytes)} bytes) -> data URI")
        return f"data:{ct};base64,{b64}"
    except Exception as e:
        logger.error(f"Failed to download image ({url[:80]}): {e}")
        raise ValueError(f"Cannot fetch image: {e}")


def _make_images_accessible(recommendations):
    """Proxy inaccessible image URLs (Google Shopping thumbnails) as data URIs.
    
    Critical pattern from Jul 26: encrypted-tbn3.gstatic.com returns 404
    when accessed from servers. Download locally and convert to data URIs.
    """
    out = []
    for rec in recommendations[:6]:
        url = rec.get("image_url", "")
        if not url or url.startswith("data:") or "myshopify.com" in url or "r2.cloudflarestorage.com" in url:
            out.append(rec)
            continue
        # Only proxy Google Shopping CDN URLs
        if "gstatic.com" in url or "google" in url:
            try:
                rec_copy = dict(rec)
                rec_copy["image_url"] = _download_as_data_uri(url)
                out.append(rec_copy)
                continue
            except Exception as e:
                logger.warning(f"Failed to proxy image: {e}")
        out.append(rec)
    return out


# ═══════════════════════════════════════════════════════════════════════════
# Marketplace scrapers — ported from Drishti Jul 26 working backend
# (api/services/price_scraper.py + api/services/marketplace_reco.py)
# ═══════════════════════════════════════════════════════════════════════════

_SCRAPER_CACHE = {}
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
]
_OCCASION_CATEGORIES = {
    "casual": ["tshirt", "casual shirt", "jeans"],
    "work": ["formal shirt", "formal trousers"],
    "office": ["formal shirt", "blazer"],
    "wedding": ["kurta", "nehru jacket"],
    "party": ["party shirt", "blazer"],
    "date": ["shirt", "jeans"],
    "gym": ["gym tshirt", "track pants"],
    "festive": ["kurta", "ethnic wear"],
    "travel": ["tshirt", "travel jeans"],
    "college": ["tshirt", "jeans casual"],
}
_STYLE_KEYWORDS = {
    "minimalist": ["plain solid"], "streetwear": ["oversized"],
    "classic": ["classic", "polo"], "boho": ["bohemian", "floral"],
    "athleisure": ["athleisure"], "corporate": ["formal"],
    "glam": ["designer"], "y2k": ["retro"], "cottagecore": ["floral"],
}
_GENDER_Q = {"male": "men", "female": "women"}


def _build_search_queries(occasion="", style="", gender=""):
    occ = (occasion or "casual").lower()
    cats = _OCCASION_CATEGORIES.get(occ, ["tshirt", "casual shirt"])
    gs = _GENDER_Q.get((gender or "").lower(), "")
    queries = []
    for cat in cats[:3]:
        parts = [cat, gs]
        if style and style.lower() not in cat.lower():
            kw = _STYLE_KEYWORDS.get(style.lower(), [])
            if kw and kw[0] not in cat.lower():
                parts.insert(0, kw[0])
        queries.append(" ".join(parts))
    return queries


def _fetch_html(url, timeout=15):
    headers = {"User-Agent": random.choice(_USER_AGENTS),
               "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
               "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8"}
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _scrape_amazon(query, max_results=8):
    search_url = f"https://www.amazon.in/s?k={query.replace(' ', '+')}&ref=nb_sb_noss"
    try:
        html = _fetch_html(search_url)
    except Exception as e:
        print(f"[Amazon] fetch failed: {e}", flush=True)
        return []
    products = []
    matches = list(re.finditer(r'data-component-type="s-search-result"', html))
    for i, m in enumerate(matches[:max_results]):
        chunk = html[m.start():matches[i+1].start() if i+1 < len(matches) else m.start()+8000]
        asin_m = re.search(r'data-asin="([A-Z0-9]{10})"', chunk)
        if not asin_m:
            continue
        asin = asin_m.group(1)
        h2s = re.findall(r'<h2[^>]*>(.*?)</h2>', chunk, re.DOTALL)
        title = html_mod.unescape(re.sub(r'<[^>]+>', '', h2s[-1]).strip()) if h2s else ""
        if not title:
            tm = re.search(r'class="a-text-normal"[^>]*>([^<]+)<', chunk)
            title = html_mod.unescape(tm.group(1).strip()) if tm else ""
        pm = re.search(r'class="a-price-whole"[^>]*>([0-9,]+)<', chunk)
        price = int(pm.group(1).replace(",", "")) if pm else 0
        im = re.search(r'<img[^>]*src="(https://m\.media-amazon\.com/[^"]+)"', chunk)
        image_url = im.group(1) if im else ""
        if title and price > 0:
            products.append({"source": "amazon", "product_id": asin, "title": title,
                             "price": price, "image_url": image_url,
                             "url": f"https://www.amazon.in/dp/{asin}"})
    print(f"[Amazon] {len(products)} products for '{query[:40]}'", flush=True)
    return products


def _scrape_flipkart(query, max_results=8):
    search_url = f"https://www.flipkart.com/search?q={query.replace(' ', '+')}"
    try:
        html = _fetch_html(search_url)
    except Exception as e:
        print(f"[Flipkart] fetch failed: {e}", flush=True)
        return []
    products = []
    try:
        m = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.+)', html, re.DOTALL)
        if m:
            raw = m.group(1)
            for marker in [';\n', ';\r', ';</script>', ';\nwindow.']:
                idx = raw.find(marker)
                if 0 < idx < len(raw):
                    raw = raw[:idx]
                    break
            state = json.loads(raw)
            page_data = state.get("pageDataV4", {}).get("page", {}).get("data", {})
            for key, val in page_data.items():
                if not isinstance(val, list):
                    continue
                for item in val:
                    if not isinstance(item, dict):
                        continue
                    pi = item.get("productInfo", {}).get("value", {})
                    if not pi:
                        continue
                    titles = pi.get("titles", {})
                    pricing = pi.get("pricing", {})
                    prices_list = pricing.get("prices", [])
                    base_url = pi.get("baseUrl", "")
                    pid = pi.get("id", "")
                    title = titles.get("title") or titles.get("newTitle", "")
                    brand = titles.get("superTitle", "")
                    selling_price = 0
                    for p in prices_list:
                        if p.get("priceType") == "SPECIAL_PRICE":
                            selling_price = int(p.get("value", 0))
                    if not selling_price and prices_list:
                        selling_price = int(prices_list[-1].get("value", 0))
                    images = pi.get("media", {}).get("images", [])
                    image_url = ""
                    if images:
                        raw_img = images[0].get("url", "")
                        image_url = raw_img.replace("{@width}", "300").replace("{@height}", "300").replace("{@quality}", "70")
                    link = f"https://www.flipkart.com{base_url.split('?')[0]}" if base_url else ""
                    if title and selling_price > 0:
                        products.append({"source": "flipkart", "product_id": pid,
                                         "title": f"{brand} {title}".strip() if brand else title,
                                         "price": selling_price, "image_url": image_url,
                                         "url": link or search_url})
    except Exception as e:
        print(f"[Flipkart] JSON parse: {e}", flush=True)
    if not products:
        data_ids = list(re.finditer(r'data-id="([^"]+)"', html))
        for i, dm in enumerate(data_ids[:max_results]):
            chunk = html[dm.start():data_ids[i+1].start() if i+1 < len(data_ids) else dm.start()+8000]
            pid = dm.group(1)
            lm = re.search(r'href="(/[^"]+?/p/itm[A-Za-z0-9]+[^"]*)"', chunk)
            link = f"https://www.flipkart.com{lm.group(1).split('?')[0]}" if lm else ""
            title = ""
            tm = re.search(r'href="[^"]*"[^>]*title="([^"]+)"', chunk)
            if tm:
                title = html_mod.unescape(tm.group(1).strip())
            if not title:
                for t_m in re.finditer(r'>([A-Z][^<]{15,80})</(?:a|span|div)', chunk):
                    t = t_m.group(1).strip()
                    if len(t) > 15 and not t.startswith('\u20b9'):
                        title = html_mod.unescape(t)
                        break
            prices = re.findall(r'\u20b9([\d,]+)', chunk)
            price = int(prices[0].replace(",", "")) if prices else 0
            if title and price > 0:
                products.append({"source": "flipkart", "product_id": pid, "title": title,
                                 "price": price, "image_url": "", "url": link or search_url})
    print(f"[Flipkart] {len(products)} products for '{query[:40]}'", flush=True)
    return products[:max_results]


def _search_marketplace_products(occasion, style, gender, count=12):
    queries = _build_search_queries(occasion, style, gender)
    logger.info(f"[Marketplace] queries: {queries}")
    all_products = []
    seen_ids = set()
    for query in queries[:2]:
        try:
            for p in _scrape_amazon(query, 5):
                pid = f"{p['source']}:{p['product_id']}"
                if pid not in seen_ids:
                    seen_ids.add(pid)
                    all_products.append(p)
        except Exception as e:
            logger.error(f"[Marketplace] Amazon error for '{query}': {e}")
        try:
            for p in _scrape_flipkart(query, 5):
                pid = f"{p['source']}:{p['product_id']}"
                if pid not in seen_ids:
                    seen_ids.add(pid)
                    all_products.append(p)
        except Exception as e:
            logger.error(f"[Marketplace] Flipkart error for '{query}': {e}")
    all_products.sort(key=lambda x: x.get("price", 99999))
    logger.info(f"[Marketplace] Total: {len(all_products)} products")
    return all_products[:count]


# ═══════════════════════════════════════════════════════════════════════════
# PROVEN PATTERN: Garment extraction before VTON (Jul 26 commit a9584dc)
# Extracts clean flat-lay from marketplace product photos via rembg
# ═══════════════════════════════════════════════════════════════════════════

def _replicate_remove_bg(image_url):
    """Remove background via Replicate rembg. Downloads image first as data URI."""
    token = _get_token()
    if not token:
        return None

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Download image first and convert to data URI (avoids CDN DNS issues)
    image_input = image_url
    try:
        img_bytes = sync_requests.get(image_url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }, timeout=15, allow_redirects=True).content
        b64 = base64.b64encode(img_bytes).decode()
        if img_bytes[:8] == b'\x89PNG\r\n\x1a\n':
            ct = "image/png"
        elif img_bytes[:3] == b'\xff\xd8\xff':
            ct = "image/jpeg"
        elif img_bytes[:4] == b'RIFF' and len(img_bytes) > 12 and img_bytes[8:12] == b'WEBP':
            ct = "image/webp"
        else:
            ct = "image/jpeg"
        image_input = f"data:{ct};base64,{b64}"
    except Exception as e:
        logger.warning(f"Failed to download for rembg, passing URL directly: {e}")

    payload = {
        "version": _get_rembg_version(),
        "input": {"image": image_input},
    }

    try:
        pred_id = None
        for attempt in range(3):
            resp = sync_requests.post(f"{REPLICATE_API}/predictions", headers=headers, json=payload, timeout=30)
            if resp.status_code == 429:
                wait = 10 * (attempt + 1)
                logger.warning(f"Replicate rembg rate limited (429), retrying in {wait}s")
                time.sleep(wait)
                continue
            if resp.status_code != 201:
                logger.error(f"Replicate rembg create failed: {resp.status_code}")
                return None
            pred_id = resp.json()["id"]
            break

        if not pred_id:
            return None

        for _ in range(30):
            time.sleep(2)
            resp = sync_requests.get(f"{REPLICATE_API}/predictions/{pred_id}", headers=headers, timeout=15)
            if resp.status_code != 200:
                continue
            d = resp.json()
            status = d.get("status")
            if status == "succeeded":
                output = d.get("output", "")
                if isinstance(output, list) and output:
                    return output[0]
                elif isinstance(output, str) and output:
                    return output
                return None
            elif status in ("failed", "canceled"):
                logger.error(f"Replicate rembg failed: {d.get('error')}")
                return None
        return None
    except Exception as e:
        logger.error(f"Replicate rembg error: {e}")
        return None


def _post_process_garment(image_bytes):
    """Post-process: crop to bounding box, clean edges, white background."""
    from PIL import Image
    import io
    import numpy as np
    from scipy import ndimage

    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    alpha = np.array(img.split()[3], dtype=np.uint8)
    binary = (alpha > 128).astype(np.uint8)
    if binary.sum() == 0:
        return image_bytes

    binary = ndimage.binary_closing(binary, iterations=2).astype(np.uint8)
    binary = ndimage.binary_opening(binary, iterations=1).astype(np.uint8)
    result = img.copy()
    clean_alpha = Image.fromarray((binary * 255).astype(np.uint8), mode="L")
    result.putalpha(clean_alpha)

    bbox = result.getbbox()
    if bbox:
        x1, y1, x2, y2 = bbox
        w, h = x2 - x1, y2 - y1
        pad_x = max(5, int(w * 0.05))
        pad_y = max(5, int(h * 0.05))
        x1 = max(0, x1 - pad_x)
        y1 = max(0, y1 - pad_y)
        x2 = min(img.width, x2 + pad_x)
        y2 = min(img.height, y2 + pad_y)
        result = result.crop((x1, y1, x2, y2))

    bg = Image.new("RGBA", result.size, (255, 255, 255, 255))
    bg.paste(result, mask=result.split()[3])
    result = bg.convert("RGB")
    buf = io.BytesIO()
    result.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _preprocess_garment_for_vton(garment_url, should_extract=True):
    """Extract clean garment from marketplace URLs before VTON.
    
    From Jul 26: marketplace photos (Amazon, Myntra, Flipkart) have backgrounds
    that confuse VTON. Extract clean flat-lay first.
    
    IMPORTANT: We extract from ALL images (including data URIs from reco endpoint)
    because reco returns raw marketplace photos as data URIs, and VTON needs
    clean flat-lay garments without model backgrounds.
    """
    if not should_extract or not garment_url:
        return garment_url

    logger.info(f"[vton] Extracting garment from: {garment_url[:80]}")
    no_bg_url = _replicate_remove_bg(garment_url)
    if no_bg_url:
        try:
            no_bg_bytes = sync_requests.get(no_bg_url, headers={
                "User-Agent": "Mozilla/5.0"
            }, timeout=15).content
            garment_bytes = _post_process_garment(no_bg_bytes)
            b64 = base64.b64encode(garment_bytes).decode()
            logger.info(f"[vton] Garment extracted successfully ({len(garment_bytes)} bytes)")
            return f"data:image/png;base64,{b64}"
        except Exception as e:
            logger.warning(f"[vton] Garment post-processing failed: {e}")
    logger.warning("[vton] Garment extraction failed, using original")

    return garment_url


# ═══════════════════════════════════════════════════════════════════════════
# PROVEN PATTERN: VTON via prunaai/p-image-try-on (Jul 26 working model)
# with data URI downloads + retry logic
# ═══════════════════════════════════════════════════════════════════════════

def _create_try_on_job(person_image_url, garment_image_url, garment_type="top"):
    """Submit VTON to Replicate via prunaai/p-image-try-on.
    
    Key Jul 26 patterns:
    1. Downloads BOTH images as data URIs (fixes Google Shopping 404s)
    2. Uses prunaai/p-image-try-on (proven working model)
    3. Retries on 429 rate limits with exponential backoff
    4. Polls every 2s for up to 120s
    """
    token = _get_token()
    if not token:
        return {"status": "error", "detail": "REPLICATE_API_TOKEN not set"}

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Download both images as data URIs (critical pattern from Jul 26)
    try:
        person_data_uri = _download_as_data_uri(person_image_url)
        garment_data_uri = _download_as_data_uri(garment_image_url)
    except ValueError as e:
        return {"status": "error", "detail": str(e)}

    payload = {
        "version": _get_vton_version(),
        "input": {
            "person_image": person_data_uri,
            "garment_images": [garment_data_uri],
            "preserve_input_size": True,
            "output_format": "png",
        },
    }

    start = time.time()
    max_retries = 3

    try:
        pred_id = None
        for attempt in range(max_retries):
            resp = sync_requests.post(f"{REPLICATE_API}/predictions", headers=headers, json=payload, timeout=30)
            if resp.status_code == 429:
                wait = 10 * (attempt + 1)
                logger.warning(f"Replicate rate limited (429), retrying in {wait}s (attempt {attempt+1}/{max_retries})")
                time.sleep(wait)
                continue
            if resp.status_code != 201:
                logger.error(f"Replicate create failed: {resp.status_code} {resp.text[:200]}")
                return {"status": "error", "detail": f"Replicate API error: {resp.status_code}"}
            pred = resp.json()
            pred_id = pred["id"]
            logger.info(f"Replicate prediction created: {pred_id}")
            break

        if not pred_id:
            return {"status": "error", "detail": "Replicate API rate limited after retries"}

        for _ in range(60):
            time.sleep(2)
            resp = sync_requests.get(f"{REPLICATE_API}/predictions/{pred_id}", headers=headers, timeout=15)
            d = resp.json() if resp.status_code == 200 else {}
            status = d.get("status")
            if status == "succeeded":
                output = d.get("output", "")
                if isinstance(output, list) and output:
                    result_url = output[0]
                elif isinstance(output, str) and output:
                    result_url = output
                else:
                    result_url = None
                elapsed = int((time.time() - start) * 1000)
                return {
                    "status": "completed",
                    "result_image": result_url,
                    "processing_time_ms": elapsed,
                    "quality_score": 0.92,
                    "engine": "prunaai/p-image-try-on",
                }
            elif status in ("failed", "canceled"):
                return {"status": "error", "detail": d.get("error", "Prediction failed")}

        return {"status": "error", "detail": "VTON timed out after 120s"}
    except Exception as e:
        logger.error(f"VTON error: {e}")
        return {"status": "error", "detail": str(e)}


# ═══════════════════════════════════════════════════════════════════════════
# PROVEN PATTERN: IDM-VTON fallback (for when category matters — dresses)
# ═══════════════════════════════════════════════════════════════════════════

def _create_idm_vton_job(person_image_url, garment_image_url, category="upper_body", description="clothing item"):
    """IDM-VTON via cuuupid/idm-vton (fallback for category-specific try-on)."""
    token = _get_token()
    if not token:
        return {"status": "error", "detail": "REPLICATE_API_TOKEN not set"}

    client = replicate.Client(api_token=token)
    valid_categories = ("upper_body", "lower_body", "dresses")
    if category not in valid_categories:
        category = "upper_body"
    force_dc = category == "dresses"
    seed = random.randint(0, 999999)

    try:
        try:
            model = client.models.get("cuuupid/idm-vton")
            version_id = model.latest_version.id
        except Exception:
            version_id = "c871bb9b046607b680449ecbae55fd8c6d945e0a1948644bf2361b3d021d3ff4"

        output = client.run(
            f"cuuupid/idm-vton:{version_id}",
            input={
                "human_img": person_image_url,
                "garm_img": garment_image_url,
                "garment_des": description,
                "category": category,
                "crop": False,
                "seed": seed,
                "steps": 30,
                "force_dc": force_dc,
                "mask_only": False,
            },
        )
        output_url = str(output) if hasattr(output, "__str__") else output
        return {"status": "completed", "result_image": output_url, "engine": "idm-vton"}
    except Exception as e:
        error_msg = str(e)
        if "402" in error_msg or "payment" in error_msg.lower():
            error_msg = "Replicate credits exhausted"
        elif "401" in error_msg or "unauthorized" in error_msg.lower():
            error_msg = "Invalid REPLICATE_API_TOKEN"
        return {"status": "error", "detail": error_msg}


# ═══════════════════════════════════════════════════════════════════════════
# Health
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "drishti-api-v2",
        "version": "2.1.0",
        "replicate_token_set": bool(_get_token()),
    })


# ═══════════════════════════════════════════════════════════════════════════
# Weather (with condition field for fabric recommendations)
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/api/weather/current", methods=["POST", "OPTIONS"])
def weather():
    if request.method == "OPTIONS":
        return "", 204, cors_headers()
    body = request.get_json(force=True) or {}
    city = body.get("city", "Mumbai")

    # Try OpenWeatherMap first (if key set), then wttr.in fallback
    owm_key = os.environ.get("OPENWEATHERMAP_API_KEY", "")
    if owm_key:
        try:
            resp = sync_requests.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"q": city, "units": "metric", "appid": owm_key},
                timeout=10,
            )
            if resp.status_code == 200:
                d = resp.json()
                main = d.get("main", {})
                wl = d.get("weather", [{}])
                wm = wl[0].get("main", "Clear") if wl else "Clear"
                wd = wl[0].get("description", "Clear Sky") if wl else "Clear Sky"
                wind = d.get("wind", {})
                icons = {"Clear": "\u2600\uFE0F", "Clouds": "\u2601\uFE0F", "Rain": "\uD83C\uDF27\uFE0F",
                         "Drizzle": "\uD83C\uDF26\uFE0F", "Thunderstorm": "\u26C8\uFE0F", "Snow": "\u2744\uFE0F",
                         "Mist": "\uD83C\uDF2B\uFE0F", "Haze": "\uD83C\uDF2B\uFE0F"}
                return jsonify({
                    "temp_c": round(main.get("temp", 0), 1),
                    "feels_like_c": round(main.get("feels_like", 0), 1),
                    "description": wd.title(),
                    "icon": icons.get(wm, "\uD83C\uDF24\uFE0F"),
                    "city": d.get("name", city),
                    "humidity": main.get("humidity", 0),
                    "wind_speed": wind.get("speed", 0),
                    "condition": wm,
                })
        except Exception as e:
            logger.warning(f"OpenWeatherMap failed: {e}")

    # Fallback: wttr.in (no API key needed)
    try:
        r = sync_requests.get(
            f"https://wttr.in/{city}?format=j1",
            headers={"User-Agent": "curl/7.68.0"},
            timeout=10,
        )
        d = r.json()
        current = d.get("current_condition", [{}])[0]
        desc = current.get("weatherDesc", [{}])[0].get("value", "Clear")
        # Map wttr.in description to condition
        condition = "Clear"
        desc_lower = desc.lower()
        if "rain" in desc_lower: condition = "Rain"
        elif "cloud" in desc_lower: condition = "Clouds"
        elif "thunder" in desc_lower: condition = "Thunderstorm"
        elif "snow" in desc_lower: condition = "Snow"
        elif "mist" in desc_lower or "fog" in desc_lower: condition = "Mist"
        elif "haze" in desc_lower: condition = "Haze"
        return jsonify({
            "temp_c": int(current.get("temp_C", 28)),
            "feels_like_c": int(current.get("FeelsLikeC", 28)),
            "description": desc,
            "icon": "\u2600\uFE0F",
            "city": city,
            "humidity": int(current.get("humidity", 50)),
            "wind_speed": float(current.get("windspeedKmph", 5)),
            "condition": condition,
        })
    except Exception:
        return jsonify({
            "temp_c": 28, "feels_like_c": 28, "description": "Clear Sky", "icon": "\u2600\uFE0F",
            "city": city, "humidity": 50, "wind_speed": 5, "condition": "Clear",
        })


# ═══════════════════════════════════════════════════════════════════════════
# Upload Person (returns data URL — simple and reliable)
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/api/vton/upload-person", methods=["POST", "OPTIONS"])
def upload_person():
    if request.method == "OPTIONS":
        return "", 204, cors_headers()
    try:
        if request.files:
            f = request.files.get("file")
            if f:
                raw = f.read()
                b64 = base64.b64encode(raw).decode()
                mime = f.content_type or "image/jpeg"
                data_url = f"data:{mime};base64,{b64}"
                return jsonify({"success": True, "url": data_url, "person_image_url": data_url, "image_url": data_url})
        data = request.get_data()
        if data and len(data) < 1000000:
            try:
                j = json.loads(data)
                if "image" in j or "url" in j:
                    url = j.get("url") or j.get("image")
                    return jsonify({"success": True, "url": url, "person_image_url": url, "image_url": url})
            except Exception:
                pass
        b64 = base64.b64encode(data).decode()
        data_url = f"data:image/jpeg;base64,{b64}"
        return jsonify({"success": True, "url": data_url, "person_image_url": data_url, "image_url": data_url})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ═══════════════════════════════════════════════════════════════════════════
# Body Analysis (multi-model pipeline from Jul 26)
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/api/analysis/body/upload", methods=["POST", "OPTIONS"])
def body_analysis():
    if request.method == "OPTIONS":
        return "", 204, cors_headers()
    try:
        image_data_url = None
        if request.files:
            f = request.files.get("file")
            if f:
                raw = f.read()
                b64 = base64.b64encode(raw).decode()
                mime = f.content_type or "image/jpeg"
                image_data_url = f"data:{mime};base64,{b64}"
        if not image_data_url:
            return jsonify({
                "success": True,
                "body_data": {"body_type": "average", "skin_tone": "medium", "height": "average", "build": "regular"},
                "confidence": 0.7, "source": "defaults",
            })

        # Try OpenAI GPT-4o-mini (primary — works well for body analysis)
        openai_key = os.environ.get("OPENAI_API_KEY", "")
        if openai_key:
            try:
                resp = sync_requests.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [
                            {"role": "system", "content": (
                                "Analyze this person's appearance for a fashion styling app. "
                                "Return ONLY a JSON object with these fields: "
                                '{"skin_tone": "fair|light|medium|olive|tan|brown|dark|deep", '
                                '"body_shape": "hourglass|pear|apple|rectangle|inverted_triangle|athletic|curvy", '
                                '"face_shape": "oval|round|square|heart|oblong|diamond|triangle", '
                                '"hair_color": "black|brown|blonde|red|auburn|gray|white|highlighted", '
                                '"hair_style": "straight|wavy|curly|coily|bob|ponytail|bun|short_crop", '
                                '"fitness_level": "slim|average|athletic|muscular|plus_size", '
                                '"complexion": "clear|freckled|tanned|dusky|radiant|matte", '
                                '"undertone": "warm|cool|neutral|olive"}'
                            )},
                            {"role": "user", "content": [
                                {"type": "image_url", "image_url": {"url": image_data_url, "detail": "high"}},
                                {"type": "text", "text": "Analyze this person's body type and appearance."}
                            ]}
                        ],
                        "max_tokens": 300,
                    },
                    timeout=30,
                )
                result = resp.json()
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "{}")
                # Handle OpenAI safety filter
                refusal = ["i'm sorry", "i can't assist", "i cannot assist"]
                if any(r in content.lower() for r in refusal):
                    raise ValueError("OpenAI refused")
                # Extract JSON
                if "```" in content:
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:]
                    content = content.strip()
                start = content.find("{")
                end = content.rfind("}") + 1
                if start >= 0 and end > start:
                    body_data = json.loads(content[start:end])
                    # Validate against known enumerations
                    VALID = {
                        "skin_tone": ["fair", "light", "medium", "olive", "tan", "brown", "dark", "deep"],
                        "body_shape": ["hourglass", "pear", "apple", "rectangle", "inverted_triangle", "athletic", "curvy"],
                        "fitness_level": ["slim", "average", "athletic", "muscular", "plus_size"],
                    }
                    for key, valid_vals in VALID.items():
                        val = (body_data.get(key) or "").lower().strip()
                        if val not in valid_vals:
                            body_data[key] = valid_vals[1]  # default to second option
                    # Normalize keys for frontend wizard v4
                    if "fitness_level" in body_data and "fitness" not in body_data:
                        body_data["fitness"] = body_data["fitness_level"]
                    if "body_shape" in body_data and "body_type" not in body_data:
                        body_data["body_type"] = body_data["body_shape"]
                    return jsonify({"success": True, "body_data": body_data, "confidence": 0.88, "source": "gpt-4o-mini"})
            except Exception as e:
                logger.warning(f"OpenAI body analysis failed: {e}")

        return jsonify({
            "success": True,
            "body_data": {"body_type": "average", "skin_tone": "medium", "height": "average", "build": "regular",
                          "face_shape": "oval", "fitness_level": "average", "fitness": "average",
                          "complexion": "clear", "undertone": "neutral",
                          "hair_color": "black", "hair_style": "straight"},
            "confidence": 0.6, "source": "defaults",
        })
    except Exception as e:
        return jsonify({"success": True, "body_data": {"body_type": "average", "skin_tone": "medium"}, "confidence": 0.5, "source": "error"})


# ═══════════════════════════════════════════════════════════════════════════
# Recommendations (reco/outfits) — diverse garment search pipeline
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/api/reco/outfits", methods=["POST", "OPTIONS"])
def reco_outfits():
    if request.method == "OPTIONS":
        return "", 204, cors_headers()
    body = request.get_json(force=True) or {}
    occasion = body.get("occasion", "casual")
    style = body.get("style", "minimalist")
    gender = body.get("gender", "men")
    brands = body.get("brands", [])

    try:
        # Primary: marketplace search (Amazon + Flipkart) — Jul 26 working pipeline
        products = _search_marketplace_products(occasion, style, gender, count=6)
        logger.info(f"[reco] marketplace returned {len(products)} products")
        if products:
            recs = []
            for p in products:
                recs.append({
                    "product_id": p.get("product_id", ""),
                    "title": p.get("title", "Recommended"),
                    "price": p.get("price", 0),
                    "url": p.get("url", "#"),
                    "image_url": p.get("image_url", ""),
                    "flat_lay_url": p.get("image_url", ""),
                    "score": 0.85,
                    "source": p.get("source", "marketplace"),
                })
            recs = _make_images_accessible(recs)
            return jsonify({"success": True, "recommendations": recs, "outfits": recs, "source": "marketplace_search"})

        # Fallback: Vercel fashion consultant (My Narrative catalog)
        resp = sync_requests.post(
            f"{VERCEL_API}/api/fashion/consultant",
            headers={
                "Content-Type": "application/json",
                "x-api-key": os.environ.get("TEST_API_KEY", "mn_test_62e9df6e8017487a482b82568de935e02166dce90b3942a4"),
            },
            json={
                "user_id": body.get("user_id", "widget_user"),
                "occasion": occasion,
                "vibe_id": style,
                "currency": body.get("currency", "INR"),
                "brands": brands,
                "gender": gender,
                "body_data": body.get("body_data", {}),
                "person_image_url": body.get("person_image_url", ""),
            },
            timeout=60,
        )
        data = resp.json()
        recs = []
        for piece in data.get("outfit_pieces", []):
            shop = piece.get("shop_links", [{}])[0] if piece.get("shop_links") else {}
            product = piece.get("my_narrative_product", {})
            recs.append({
                "product_id": product.get("handle", piece.get("name", "")),
                "title": piece.get("name", "Recommended"),
                "price": 0,
                "url": product.get("product_url", ""),
                "image_url": shop.get("flat_lay_url", "") or product.get("flat_lay_url", ""),
                "flat_lay_url": product.get("flat_lay_url", ""),
                "score": 0.85,
                "source": "mynarrative",
            })
        recs = _make_images_accessible(recs)
        return jsonify({"success": True, "recommendations": recs, "outfits": recs, "data": data})
    except Exception as e:
        logger.error(f"[reco/outfits] Error: {e}")
        return jsonify({"success": True, "recommendations": [], "outfits": [], "error": str(e)})


# ═══════════════════════════════════════════════════════════════════════════
# Price Comparison
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/api/pricing/compare/shopify/<product_id>", methods=["GET", "OPTIONS"])
def pricing_compare(product_id):
    if request.method == "OPTIONS":
        return "", 204, cors_headers()
    return jsonify({
        "success": True,
        "results": [
            {"platform": "MY NARRATIVE", "price": 0, "url": f"/products/{product_id}", "is_best": True, "original_price": 0}
        ],
    })


# ═══════════════════════════════════════════════════════════════════════════
# VTON — Primary: prunaai/p-image-try-on (Jul 26 proven model)
#         Fallback: cuuupid/idm-vton (for category-specific)
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/api/virtual-tryon", methods=["POST", "OPTIONS"])
@app.route("/api/vton/try-on", methods=["POST", "OPTIONS"])
def virtual_tryon():
    if request.method == "OPTIONS":
        return "", 204, cors_headers()

    body = request.get_json(force=True) or {}
    human_img = body.get("user_image") or body.get("person_image_url")
    garm_img = body.get("garment_image") or body.get("garment_image_url")
    category = body.get("category", "upper_body")
    description = body.get("description") or body.get("garment_description", "clothing item")
    engine = body.get("engine", "prunaai")  # "prunaai" (default) or "idm-vton"

    if not human_img or not garm_img:
        return jsonify({"success": False, "error": "Missing person_image_url or garment_image_url"}), 400

    # PROVEN PATTERN: Preprocess garment (extract from marketplace if needed)
    should_extract = body.get("extract_garment", True)
    garm_img = _preprocess_garment_for_vton(garm_img, should_extract=should_extract)

    # PROVEN PATTERN: Use prunaai/p-image-try-on (Jul 26 working model)
    if engine == "prunaai":
        result = _create_try_on_job(human_img, garm_img, garment_type=category)
    else:
        result = _create_idm_vton_job(human_img, garm_img, category=category, description=description)

    if result.get("status") == "completed":
        return jsonify({
            "success": True,
            "image": result.get("result_image"),
            "result_image": result.get("result_image"),
            "processing_time_ms": result.get("processing_time_ms"),
            "engine": result.get("engine", "prunaai"),
        })
    else:
        return jsonify({"success": False, "error": result.get("detail", "VTON failed")}), 500


# ═══════════════════════════════════════════════════════════════════════════
# Catch-All Proxy to Vercel
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/api/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
def proxy_to_vercel(path):
    if request.method == "OPTIONS":
        return "", 204, cors_headers()
    url = f"{VERCEL_API}/api/{path}"
    try:
        headers = {k: v for k, v in request.headers if k.lower() != "host"}
        if not headers.get("x-api-key"):
            headers["x-api-key"] = os.environ.get("TEST_API_KEY", "mn_test_62e9df6e8017487a482b82568de935e02166dce90b3942a4")
        if request.method in ("POST", "PUT"):
            resp = sync_requests.request(method=request.method, url=url, headers=headers, data=request.get_data(), timeout=60)
        else:
            resp = sync_requests.request(method=request.method, url=url, headers=headers, params=request.args, timeout=30)
        resp_headers = {k: v for k, v in resp.headers.items() if k.lower() not in ("transfer-encoding", "content-encoding", "connection")}
        return resp.content, resp.status_code, resp_headers
    except Exception as e:
        return jsonify({"error": str(e)}), 502


def cors_headers():
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization, x-api-key",
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
