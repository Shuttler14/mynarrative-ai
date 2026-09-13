"""
Brand Catalog Upload & Management API
Accepts CSV/JSON in Flipkart, Myntra, Amazon, Ajio format.
Stores products in Supabase brand_products table.
"""
import json
import csv
import io
import os
import sys
import uuid
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from currency_utils import parse_price, convert_price_rupees, format_price

# ── Supported marketplace formats ──────────────────────────────────────────
MARKETPLACE_FIELD_MAPS = {
    "flipkart": {
        "title": ["Product Name", "Title", "product_name", "title"],
        "brand": ["Brand", "brand", "Brand Name"],
        "price": [" Selling Price", "Price", "MRP", "selling_price", "price", "final_price"],
        "image_url": ["Image 1", "Image", "image_url", "Image URL", "product_image"],
        "category": ["Category", "category", "Product Category", "vertical"],
        "description": ["Description", "description", "Product Description"],
        "sku": ["SKU", "sku", "Listing ID", "Item ID"],
        "color": ["Color", "color", "Colour"],
        "size": ["Size", "size"],
        "material": ["Material", "material", "Fabric"],
        "gender": ["Gender", "gender", "Target Audience"],
    },
    "myntra": {
        "title": ["Product Name", "Title", "product_name", "title"],
        "brand": ["Brand", "brand", "Brand Name", "designer"],
        "price": ["MRP", "Price", "Selling Price", "price", "mrp"],
        "image_url": ["Image", "Image URL", "image_url", "product_image", "Front Image"],
        "category": ["Category", "category", "Product Type", "article_type"],
        "description": ["Description", "description"],
        "sku": ["SKU", "sku", "Style ID"],
        "color": ["Color", "color", "Colour", "base_colour"],
        "size": ["Size", "size"],
        "material": ["Material", "material", "Fabric", "fabric_detail"],
        "gender": ["Gender", "gender", "subject"],
    },
    "amazon": {
        "title": ["Product Name", "Title", "item_name", "title"],
        "brand": ["Brand Name", "Brand", "brand", "manufacturer"],
        "price": ["Price", "Buying Price", "price", "our_price", "listing_price"],
        "image_url": ["Image URL", "Main Image URL", "image_url", "product_image"],
        "category": ["Product Category", "category", "item_type"],
        "description": ["Description", "bullet_points", "description"],
        "sku": ["ASIN", "SKU", "item_sku", "sku"],
        "color": ["Color Name", "Color", "color"],
        "size": ["Size Name", "Size", "size"],
        "material": ["Material", "material", "fabric_type"],
        "gender": ["Target Audience", "gender", "department"],
    },
    "ajio": {
        "title": ["Product Name", "Title", "product_name"],
        "brand": ["Brand", "brand", "Brand Name", "designer_brand"],
        "price": ["MRP", "Price", "Selling Price", "price"],
        "image_url": ["Image", "Image URL", "image_url", "product_image"],
        "category": ["Category", "category", "Product Type"],
        "description": ["Description", "description"],
        "sku": ["SKU", "sku", "Style Code"],
        "color": ["Color", "color", "Colour"],
        "size": ["Size", "size"],
        "material": ["Material", "material"],
        "gender": ["Gender", "gender"],
    },
    "generic": {
        "title": ["title", "name", "product_name", "Product Name", "Title"],
        "brand": ["brand", "Brand", "brand_name", "Brand Name"],
        "price": ["price", "Price", "mrp", "MRP", "selling_price", "final_price"],
        "image_url": ["image_url", "image", "Image", "product_image", "Image URL", "image_url"],
        "category": ["category", "Category", "product_type"],
        "description": ["description", "Description"],
        "sku": ["sku", "SKU", "id", "product_id"],
        "color": ["color", "Color", "colour"],
        "size": ["size", "Size"],
        "material": ["material", "Material", "fabric"],
        "gender": ["gender", "Gender", "audience"],
    },
}

# ── Category normalization ─────────────────────────────────────────────────
CATEGORY_MAP = {
    "t-shirt": "top", "tshirt": "top", "shirt": "top", "blouse": "top",
    "kurta": "top", "kurti": "top", "top": "top", "tee": "top",
    "polo": "top", "henley": "top", "tank top": "top", "camisole": "top",
    "sweater": "top", "cardigan": "top", "hoodie": "top", "sweatshirt": "top",
    "jacket": "outerwear", "coat": "outerwear", "blazer": "outerwear",
    "vest": "outerwear", "windbreaker": "outerwear", "parka": "outerwear",
    "jeans": "bottom", "trousers": "bottom", "pants": "bottom",
    "shorts": "bottom", "skirt": "bottom", "chinos": "bottom",
    "joggers": "bottom", "leggings": "bottom", "dhoti": "bottom",
    "palazzo": "bottom", "culottes": "bottom",
    "dress": "dress", "gown": "dress", "frock": "dress",
    "saree": "ethnic", "lehenga": "ethnic", "salwar": "ethnic",
    "anarkali": "ethnic", "sharara": "ethnic", "dhoti set": "ethnic",
    "suit": "ethnic", "sherwani": "ethnic", "kurta set": "ethnic",
    "sneakers": "footwear", "shoes": "footwear", "sandals": "footwear",
    "heels": "footwear", "boots": "footwear", "flats": "footwear",
    "loafers": "footwear", "slides": "footwear",
    "bag": "accessory", "watch": "accessory", "jewellery": "accessory",
    "jewelry": "accessory", "necklace": "accessory", "earring": "accessory",
    "bracelet": "accessory", "scarf": "accessory", "belt": "accessory",
    "hat": "accessory", "sunglasses": "accessory", "clutch": "accessory",
}

def _normalize_category(raw: str) -> str:
    if not raw:
        return "top"
    low = raw.strip().lower()
    for key, cat in CATEGORY_MAP.items():
        if key in low:
            return cat
    return "top"


# ── Supabase helpers ───────────────────────────────────────────────────────
def _sb_headers():
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_KEY", "").strip()
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "application/json"}
    return url, key, headers

def _sb_request(method: str, path: str, payload: Any = None):
    url, key, headers = _sb_headers()
    if not url or not key:
        return None, "supabase_not_configured"
    full_url = f"{url.rstrip('/')}{path}"
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(full_url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
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


# ── Field extraction from row ──────────────────────────────────────────────
def _extract_field(row: Dict, field: str, marketplace: str = "generic") -> str:
    maps = MARKETPLACE_FIELD_MAPS.get(marketplace, MARKETPLACE_FIELD_MAPS["generic"])
    candidates = maps.get(field, [field])
    for col in candidates:
        if col in row and row[col] is not None and str(row[col]).strip():
            return str(row[col]).strip()
    return ""


# ── Parse CSV/JSON catalog ─────────────────────────────────────────────────
def parse_catalog_file(file_content: str, filename: str, marketplace: str = "generic") -> List[Dict]:
    """Parse uploaded CSV or JSON catalog into normalized product dicts."""
    products = []
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext == "json":
        try:
            data = json.loads(file_content)
            if isinstance(data, list):
                rows = data
            elif isinstance(data, dict):
                rows = data.get("products", data.get("items", data.get("data", [data])))
            else:
                return []
        except json.JSONDecodeError:
            return []
    elif ext == "csv":
        reader = csv.DictReader(io.StringIO(file_content))
        rows = list(reader)
    else:
        return []

    for row in rows:
        title = _extract_field(row, "title", marketplace)
        brand = _extract_field(row, "brand", marketplace)
        price_raw = _extract_field(row, "price", marketplace)
        image_url = _extract_field(row, "image_url", marketplace)
        category_raw = _extract_field(row, "category", marketplace)
        description = _extract_field(row, "description", marketplace)
        sku = _extract_field(row, "sku", marketplace)
        color = _extract_field(row, "color", marketplace)
        size = _extract_field(row, "size", marketplace)
        material = _extract_field(row, "material", marketplace)
        gender = _extract_field(row, "gender", marketplace)

        if not title or not image_url:
            continue

        price_num = parse_price(price_raw) if price_raw else 0.0
        category = _normalize_category(category_raw)

        gender_norm = "unisex"
        g = gender.lower()
        if any(w in g for w in ["women", "female", "woman", "girls", "womens"]):
            gender_norm = "women"
        elif any(w in g for w in ["men", "male", "man", "boys", "mens"]):
            gender_norm = "men"

        products.append({
            "title": title,
            "brand": brand,
            "price": price_num,
            "currency": "INR",
            "image_url": image_url,
            "category": category,
            "description": description,
            "sku": sku or str(uuid.uuid4())[:8],
            "color": color,
            "size": size,
            "material": material,
            "gender": gender_norm,
        })

    return products


# ── Upload catalog to Supabase ────────────────────────────────────────────
def upload_brand_catalog(
    brand_name: str,
    products: List[Dict],
    marketplace: str = "generic",
    uploaded_by: str = "api"
) -> Dict:
    """Upload parsed products to brand_products table.
    
    Handles two scenarios:
    1. If brand_catalogs table has a catalog for this brand, uses that catalog_id.
    2. If brand_products table doesn't require catalog_id (older schema), inserts directly.
    """
    url, key, headers = _sb_headers()
    if not url or not key:
        return {"error": "supabase_not_configured"}

    headers["Prefer"] = "resolution=merge-duplicates,return=representation"

    # Try to find existing catalog for this brand
    catalog_id = None
    catalog_result, _ = _sb_request("GET", f"/rest/v1/brand_catalogs?brand_id=eq.{brand_name.upper()}&select=id&limit=1")
    if catalog_result and len(catalog_result) > 0:
        catalog_id = catalog_result[0].get("id")

    # If no catalog exists, try to find brand by name (case-insensitive) in brands table
    if not catalog_id:
        brand_result, _ = _sb_request("GET", f"/rest/v1/brands?name=eq.{brand_name}&select=id&limit=1")
        if brand_result and len(brand_result) > 0:
            brand_id = brand_result[0]["id"]
            # Create a catalog for this brand
            new_catalog, _ = _sb_request("POST", "/rest/v1/brand_catalogs", {
                "brand_id": brand_id,
                "name": f"{brand_name} Catalog",
                "sync_status": "active",
                "product_count": len(products),
            })
            if new_catalog and len(new_catalog) > 0:
                catalog_id = new_catalog[0]["id"]

    rows = []
    for p in products:
        row = {
            "brand": brand_name.upper(),
            "title": p["title"],
            "price": p["price"],
            "currency": p.get("currency", "INR"),
            "image_url": p["image_url"],
            "category": p["category"],
            "description": p.get("description", ""),
            "sku": p.get("sku", ""),
            "color": p.get("color", ""),
            "size": p.get("size", ""),
            "material": p.get("material", ""),
            "gender": p.get("gender", "unisex"),
            "marketplace_source": marketplace,
            "uploaded_by": uploaded_by,
            "is_active": True,
        }
        # Add catalog_id and external_id if available (required by newer schema)
        if catalog_id:
            row["catalog_id"] = catalog_id
        row["external_id"] = p.get("sku", str(uuid.uuid4())[:8])
        rows.append(row)

    result, err = _sb_request("POST", "/rest/v1/brand_products", rows)
    if err:
        # If error mentions catalog_id, retry without it (for older schema)
        if "catalog_id" in str(err):
            for row in rows:
                row.pop("catalog_id", None)
            result, err = _sb_request("POST", "/rest/v1/brand_products", rows)
        if err:
            return {"error": err, "inserted": 0}

    inserted = len(result) if isinstance(result, list) else 0
    return {"inserted": inserted, "brand": brand_name, "marketplace": marketplace}


# ── Search brand products ──────────────────────────────────────────────────
def search_brand_products(
    brand: str,
    category: str = "",
    gender: str = "",
    min_price: float = 0,
    max_price: float = 999999,
    limit: int = 20,
    currency: str = "INR",
    vibe: str = "",
    color_pref: str = "",
) -> List[Dict]:
    """Search uploaded brand catalog products with filters."""
    filters = ["is_active eq.true"]
    if brand:
        filters.append(f"brand eq.{brand.upper()}")
    if category:
        filters.append(f"category eq.{_normalize_category(category)}")
    if gender and gender != "unisex":
        filters.append(f"or=(gender eq.{gender},gender eq.unisex)")
    if min_price > 0:
        filters.append(f"price gte.{min_price}")
    if max_price < 999999:
        filters.append(f"price lte.{max_price}")

    where = "&".join(filters)
    path = f"/rest/v1/brand_products?select=*&{where}&order=price.asc&limit={limit}"

    result, err = _sb_request("GET", path)
    if err or not result:
        return []

    products = []
    for row in result:
        price_inr = float(row.get("price", 0))
        products.append({
            "id": row.get("id"),
            "title": row.get("title", ""),
            "brand": row.get("brand", ""),
            "price": price_inr,
            "price_display": format_price(convert_price_rupees(price_inr, currency), currency),
            "currency": currency,
            "image_url": row.get("image_url", ""),
            "category": row.get("category", ""),
            "description": row.get("description", ""),
            "color": row.get("color", ""),
            "size": row.get("size", ""),
            "material": row.get("material", ""),
            "gender": row.get("gender", "unisex"),
            "marketplace_source": row.get("marketplace_source", ""),
            "flat_lay_url": row.get("flat_lay_url", ""),
        })

    return products


# ── Get all brands with product counts ────────────────────────────────────
def get_brand_catalog_summary() -> List[Dict]:
    """Get list of all brands in the catalog with product counts."""
    path = "/rest/v1/brand_products?select=brand,count&is_active eq.true"
    result, err = _sb_request("GET", path)
    if err or not result:
        return []

    brand_counts = {}
    for row in result:
        b = row.get("brand", "")
        if b:
            brand_counts[b] = brand_counts.get(b, 0) + 1

    return [{"brand": b, "product_count": c} for b, c in sorted(brand_counts.items(), key=lambda x: -x[1])]


# ── Delete brand catalog ──────────────────────────────────────────────────
def delete_brand_catalog(brand_name: str) -> Dict:
    """Soft-delete all products for a brand."""
    path = f"/rest/v1/brand_products?brand eq.{brand_name.upper()}"
    payload = {"is_active": False}
    result, err = _sb_request("PATCH", path, payload)
    if err:
        return {"error": err}
    return {"deleted": True, "brand": brand_name}
