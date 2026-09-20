"""
Shopify Product Sync — Automatically pulls products + ratings from a brand's Shopify store.

Flow:
1. Brand provides Shopify shop URL + Admin API token during onboarding
2. This module pulls ALL products via Shopify Admin REST API (paginated)
3. For each product: title, description, images, price, variants, category, tags, stock
4. Pulls product ratings via Shopify Product Reviews (metafields or app)
5. Stores everything in Supabase brand_products table
6. Supports incremental sync via webhooks (product/create, product/update, product/delete)
"""
from __future__ import annotations
import os
import sys
import json
import requests
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.core.supabase import sb_request


# ─── Shopify Admin API Helpers ───────────────────────────────────────────────

def _shopify_get(shop_url: str, token: str, endpoint: str, params: dict = None) -> dict | list | None:
    """Make a GET request to Shopify Admin REST API."""
    url = f"https://{shop_url}/admin/api/2024-01/{endpoint}"
    headers = {
        "X-Shopify-Access-Token": token,
        "Content-Type": "application/json",
    }
    try:
        resp = requests.get(url, headers=headers, params=params or {}, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        print(f"[shopify] GET {endpoint} returned {resp.status_code}: {resp.text[:200]}")
        return None
    except Exception as e:
        print(f"[shopify] GET {endpoint} error: {e}")
        return None


def _shopify_get_all(shop_url: str, token: str, endpoint: str, params: dict = None, key: str = "products") -> list:
    """Paginate through all Shopify resources."""
    all_items = []
    params = params or {}
    params["limit"] = 250  # Max per page

    while True:
        data = _shopify_get(shop_url, token, endpoint, params)
        if not data:
            break
        items = data.get(key, [])
        all_items.extend(items)

        # Check for next page
        link_header = data.get("link") or ""
        if 'rel="next"' not in str(data):
            # Check if there's a page_info in the response
            break

        # Extract page_info from link header
        # Shopify uses cursor-based pagination
        if isinstance(items, list) and len(items) < 250:
            break

        # For products, use since_id for simple pagination
        if items:
            params["since_id"] = items[-1].get("id")
        else:
            break

    return all_items


# ─── Product Sync ────────────────────────────────────────────────────────────

def sync_brand_products(brand_id: str, shop_url: str, access_token: str) -> dict:
    """
    Pull ALL products from a Shopify store and store in brand_products.
    Returns sync summary.
    """
    try:
        # Normalize shop URL
        shop_url = shop_url.replace("https://", "").replace("http://", "").rstrip("/")

        # Verify connection
        shop_data = _shopify_get(shop_url, access_token, "shop.json")
        if not shop_data:
            return {"success": False, "error": "Could not connect to Shopify store. Check credentials."}

        shop_name = shop_data.get("shop", {}).get("name", shop_url)

        # Store/update brand's Shopify credentials
        sb_request("PATCH", f"/rest/v1/brands?id=eq.{brand_id}", {
            "shopify_shop_url": shop_url,
            "shopify_access_token": access_token,
            "shopify_shop_name": shop_name,
            "last_sync_at": datetime.utcnow().isoformat() + "Z",
        })

        # Pull all products
        products = _shopify_get_all(shop_url, access_token, "products.json", key="products")

        # Pull ratings/reviews via metafields (Shopify Product Reviews app stores ratings here)
        ratings_map = _pull_product_ratings(shop_url, access_token, products)

        # Transform and store
        synced = 0
        errors = 0
        for product in products:
            try:
                _store_product(brand_id, product, ratings_map.get(str(product.get("id", "")), {}))
                synced += 1
            except Exception as e:
                print(f"[sync] Error storing product {product.get('id')}: {e}")
                errors += 1

        # Update sync status
        sb_request("PATCH", f"/rest/v1/brands?id=eq.{brand_id}", {
            "last_sync_at": datetime.utcnow().isoformat() + "Z",
            "product_count": synced,
            "sync_status": "completed",
        })

        return {
            "success": True,
            "shop_name": shop_name,
            "products_synced": synced,
            "products_errors": errors,
            "total_products": len(products),
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


def _store_product(brand_id: str, product: dict, ratings: dict):
    """Transform a Shopify product and store in brand_products."""
    product_id = str(product.get("id", ""))
    title = product.get("title", "")
    description = product.get("body_html", "") or product.get("description", "")
    product_type = product.get("product_type", "")
    vendor = product.get("vendor", "")
    tags = product.get("tags", "")
    handle = product.get("handle", "")
    status = product.get("status", "active")
    created_at = product.get("created_at", "")
    updated_at = product.get("updated_at", "")

    # Get main image
    images = product.get("images", [])
    image_url = images[0].get("src", "") if images else ""

    # Get first variant for price/stock
    variants = product.get("variants", [])
    price = 0
    compare_at_price = 0
    stock = "in_stock"
    sku = ""
    if variants:
        v = variants[0]
        price = float(v.get("price", 0) or 0)
        compare_at_price = float(v.get("compare_at_price", 0) or 0)
        inventory_qty = v.get("inventory_quantity", 0) or 0
        stock = "in_stock" if inventory_qty > 0 or v.get("inventory_policy") == "continue" else "out_of_stock"
        sku = v.get("sku", "")

    # Calculate discount
    discount_pct = 0
    if compare_at_price > 0 and price > 0 and compare_at_price > price:
        discount_pct = round((compare_at_price - price) / compare_at_price * 100)

    # Map product type to our categories
    category = _map_shopify_type(product_type, tags, title)

    # Map gender from tags or product type
    gender = _map_gender(tags, product_type, title)

    # Build all variants data
    all_variants = []
    for v in variants:
        all_variants.append({
            "id": str(v.get("id", "")),
            "title": v.get("title", ""),
            "price": float(v.get("price", 0) or 0),
            "compare_at_price": float(v.get("compare_at_price", 0) or 0),
            "sku": v.get("sku", ""),
            "inventory_quantity": v.get("inventory_quantity", 0) or 0,
            "option1": v.get("option1", ""),
            "option2": v.get("option2", ""),
            "option3": v.get("option3", ""),
        })

    # Build all images
    all_images = [img.get("src", "") for img in images if img.get("src")]

    # Ratings from metafields
    avg_rating = ratings.get("average_rating", 0)
    review_count = ratings.get("reviews_count", 0)

    # Upsert into brand_products
    product_url = f"https://{brand_id}.myshopify.com/products/{handle}" if handle else ""

    # Check if product exists
    existing = sb_request("GET",
        f"/rest/v1/brand_products?brand_id=eq.{brand_id}&external_id=eq.{product_id}&select=id",
        limit=1)
    if isinstance(existing, list) and existing:
        # Update
        product_uuid = existing[0]["id"]
        sb_request("PATCH", f"/rest/v1/brand_products?id=eq.{product_uuid}", {
            "title": title,
            "description": description[:2000] if description else "",
            "price": price,
            "compare_at_price": compare_at_price,
            "discount_pct": discount_pct,
            "category": category,
            "gender": gender,
            "image_url": image_url,
            "images": json.dumps(all_images[:5]),
            "product_url": product_url,
            "tags": tags if isinstance(tags, str) else ",".join(tags),
            "stock": stock,
            "sku": sku,
            "variants": json.dumps(all_variants[:10]),
            "avg_rating": avg_rating,
            "review_count": review_count,
            "shopify_status": status,
            "updated_at": updated_at or datetime.utcnow().isoformat(),
        })
    else:
        # Insert
        sb_request("POST", "/rest/v1/brand_products", {
            "brand_id": brand_id,
            "external_id": product_id,
            "title": title,
            "description": (description or "")[:2000],
            "price": price,
            "compare_at_price": compare_at_price,
            "discount_pct": discount_pct,
            "category": category,
            "gender": gender,
            "image_url": image_url,
            "images": json.dumps(all_images[:5]),
            "product_url": product_url,
            "tags": tags if isinstance(tags, str) else ",".join(tags),
            "stock": stock,
            "sku": sku,
            "variants": json.dumps(all_variants[:10]),
            "avg_rating": avg_rating,
            "review_count": review_count,
            "shopify_status": status,
            "created_at": created_at or datetime.utcnow().isoformat(),
        })


# ─── Ratings / Reviews ───────────────────────────────────────────────────────

def _pull_product_ratings(shop_url: str, token: str, products: list) -> dict:
    """
    Pull product ratings from Shopify.
    Tries multiple approaches:
    1. Product Reviews app metafields (judge.me, yotpo, etc.)
    2. Shopify native rating metafields
    3. Returns empty if no review app found
    """
    ratings_map = {}

    # Approach 1: Check for common review app metafields
    review_apps = [
        {"namespace": "judge.me", "key": "rating"},
        {"namespace": "judge.me", "key": "review_count"},
        {"namespace": "yotpo", "key": "average_score"},
        {"namespace": "yotpo", "key": "review_count"},
        {"namespace": "stamped", "key": "rating"},
        {"namespace": "loox", "key": "rating"},
        {"namespace": "reviews", "key": "rating"},
        {"namespace": "shopify", "key": "rating"},
    ]

    # Sample first 10 products to detect review app
    sample_ids = [str(p.get("id", "")) for p in products[:10] if p.get("id")]
    detected_app = None

    for app in review_apps:
        for pid in sample_ids[:3]:
            metafields = _shopify_get(shop_url, token,
                f"products/{pid}/metafields.json",
                {"namespace": app["namespace"], "key": app["key"]})
            if metafields and metafields.get("metafields"):
                detected_app = app
                break
        if detected_app:
            break

    if not detected_app:
        print("[sync] No review app detected — ratings will be empty")
        return ratings_map

    print(f"[sync] Detected review app: {detected_app['namespace']}")

    # Pull ratings for all products
    rating_key = detected_app["key"]
    count_key = "review_count" if detected_app["key"] != "review_count" else "rating"

    for product in products:
        pid = str(product.get("id", ""))
        metafields = _shopify_get(shop_url, token,
            f"products/{pid}/metafields.json",
            {"namespace": detected_app["namespace"]})

        if metafields and metafields.get("metafields"):
            ratings = {}
            for mf in metafields["metafields"]:
                if mf.get("key") == rating_key:
                    try:
                        ratings["average_rating"] = float(mf.get("value", 0))
                    except (ValueError, TypeError):
                        ratings["average_rating"] = 0
                elif mf.get("key") == count_key:
                    try:
                        ratings["reviews_count"] = int(mf.get("value", 0))
                    except (ValueError, TypeError):
                        ratings["reviews_count"] = 0
            if ratings:
                ratings_map[pid] = ratings

    return ratings_map


# ─── Webhook Handlers ────────────────────────────────────────────────────────

def handle_shopify_product_webhook(brand_id: str, topic: str, product_data: dict) -> dict:
    """
    Handle product/create, product/update, product/delete webhooks.
    Enables real-time inventory sync.
    """
    try:
        product_id = str(product_data.get("id", ""))

        if topic in ("product/create", "product/update"):
            # Sync single product
            _store_product(brand_id, product_data, {})
            return {"success": True, "action": "synced", "product_id": product_id}

        elif topic == "product/delete":
            # Mark as deleted / remove
            sb_request("DELETE", f"/rest/v1/brand_products?brand_id=eq.{brand_id}&external_id=eq.{product_id}")
            return {"success": True, "action": "deleted", "product_id": product_id}

        return {"success": False, "error": f"Unknown topic: {topic}"}

    except Exception as e:
        return {"success": False, "error": str(e)}


# ─── Onboarding Flow ─────────────────────────────────────────────────────────

def start_shopify_sync(brand_id: str, shop_url: str, access_token: str) -> dict:
    """
    Called during brand onboarding to kick off initial product sync.
    Returns immediately — sync runs in background on Vercel.
    """
    # Validate credentials first
    shop_url = shop_url.replace("https://", "").replace("http://", "").rstrip("/")
    shop_data = _shopify_get(shop_url, access_token, "shop.json")
    if not shop_data:
        return {"success": False, "error": "Invalid Shopify credentials. Could not connect to store."}

    # Store credentials
    sb_request("PATCH", f"/rest/v1/brands?id=eq.{brand_id}", {
        "shopify_shop_url": shop_url,
        "shopify_access_token": access_token,
        "shopify_shop_name": shop_data.get("shop", {}).get("name", shop_url),
        "sync_status": "syncing",
    })

    # Run sync (Vercel has 60s timeout, so we do a best-effort sync)
    result = sync_brand_products(brand_id, shop_url, access_token)

    return result


def register_shopify_webhooks(brand_id: str, shop_url: str, access_token: str) -> dict:
    """Register webhooks for real-time product sync."""
    topics = [
        ("product/create", "product"),
        ("product/update", "product"),
        ("product/delete", "product"),
    ]

    webhook_url = "https://drishti-api-blond.vercel.app/api/shopify/product-webhook"
    registered = []

    for topic, format_ in topics:
        data = _shopify_post(shop_url, access_token, "webhooks.json", {
            "webhook": {
                "topic": topic,
                "address": f"{webhook_url}?brand_id={brand_id}",
                "format": format_,
            }
        })
        if data and data.get("webhook"):
            registered.append(topic)

    return {"success": len(registered) > 0, "registered": registered}


def _shopify_post(shop_url: str, token: str, endpoint: str, payload: dict) -> dict | None:
    """Make a POST request to Shopify Admin REST API."""
    url = f"https://{shop_url}/admin/api/2024-01/{endpoint}"
    headers = {
        "X-Shopify-Access-Token": token,
        "Content-Type": "application/json",
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        if resp.status_code in (200, 201):
            return resp.json()
        print(f"[shopify] POST {endpoint} returned {resp.status_code}: {resp.text[:200]}")
        return None
    except Exception as e:
        print(f"[shopify] POST {endpoint} error: {e}")
        return None


# ─── Category / Gender Mapping ───────────────────────────────────────────────

CATEGORY_MAP = {
    "shirts": "tops", "blouses": "tops", "t-shirts": "tops", "tops": "tops",
    "tank tops": "tops", "polo shirts": "tops", "sweaters": "tops",
    "cardigans": "outerwear", "jackets": "outerwear", "coats": "outerwear",
    "blazers": "outerwear", "vests": "outerwear", "outerwear": "outerwear",
    "jeans": "bottoms", "trousers": "bottoms", "pants": "bottoms",
    "shorts": "bottoms", "skirts": "bottoms", "leggings": "bottoms",
    "bottoms": "bottoms",
    "dresses": "dresses", "jumpsuits": "dresses", "rompers": "dresses",
    "sneakers": "footwear", "boots": "footwear", "heels": "footwear",
    "sandals": "footwear", "flats": "footwear", "loafers": "footwear",
    "footwear": "footwear", "shoes": "footwear",
    "bags": "accessories", "hats": "accessories", "scarves": "accessories",
    "jewelry": "accessories", "watches": "accessories", "belts": "accessories",
    "sunglasses": "accessories", "accessories": "accessories",
}

GENDER_KEYWORDS = {
    "women": ["women", "woman", "ladies", "female", "feminine", "girls"],
    "men": ["men", "man", "male", "masculine", "boys"],
    "unisex": ["unisex", "gender neutral"],
}


def _map_shopify_type(product_type: str, tags: str, title: str) -> str:
    """Map Shopify product_type to our category system."""
    combined = f"{product_type} {tags} {title}".lower()
    for keyword, category in CATEGORY_MAP.items():
        if keyword in combined:
            return category
    return "tops"  # Default


def _map_gender(tags: str, product_type: str, title: str) -> str:
    """Detect gender from product data."""
    combined = f"{tags} {product_type} {title}".lower()
    for gender, keywords in GENDER_KEYWORDS.items():
        for kw in keywords:
            if kw in combined:
                return gender
    return "unisex"
