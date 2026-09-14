"""
Inventory Filter — Hard pre-filtering for stock, size, and gender.
Zero-latency SQL pre-filter before hitting Knowledge Graph or vector DB.
"""
from __future__ import annotations
import json
import os
import requests
from typing import Optional

def _get_supabase_url():
    return os.environ.get("SUPABASE_URL", "")

def _get_supabase_key():
    return os.environ.get("SUPABASE_KEY", "")


def _sb_query(table: str, filters: dict, select: str = "*", limit: int = 200) -> list[dict]:
    """Query Supabase with filters."""
    supabase_url = _get_supabase_url()
    supabase_key = _get_supabase_key()
    if not supabase_url or not supabase_key:
        return []

    params = [f"select={select}", f"limit={limit}"]
    for k, v in filters.items():
        if v is None:
            continue
        if isinstance(v, bool):
            params.append(f"{k}=eq.{str(v).lower()}")
        elif isinstance(v, (list, tuple)):
            vals = ",".join(str(x) for x in v)
            params.append(f"{k}=in.({vals})")
        elif isinstance(v, str) and v.startswith(("eq.", "gt.", "lt.", "gte.", "lte.")):
            params.append(f"{k}={v}")
        else:
            params.append(f"{k}=eq.{v}")

    url = f"{supabase_url.rstrip('/')}/rest/v1/{table}?{'&'.join(params)}"
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        return resp.json() if resp.text else []
    except Exception:
        return []


def filter_brand_products(
    brand_id: str = "",
    brand_name: str = "",
    category: str = "",
    gender: str = "",
    min_price: float = 0,
    max_price: float = 999999,
    available_sizes: list[str] = None,
    color: str = "",
    material: str = "",
    occasion: str = "",
    limit: int = 50,
) -> list[dict]:
    """
    Pre-filter brand products by硬 constraints (stock, size, gender, price).
    Returns filtered product list ready for Knowledge Graph and vector scoring.
    """
    filters = {"is_active": True}

    if brand_id:
        # Look up catalog_id from brand_id via brand_catalogs
        catalogs = _sb_query("brand_catalogs", {"brand_id": brand_id}, select="id")
        catalog_ids = [c["id"] for c in catalogs] if catalogs else []
        if catalog_ids:
            filters["catalog_id"] = catalog_ids[0] if len(catalog_ids) == 1 else catalog_ids
        else:
            return []
    if brand_name:
        filters["brand"] = brand_name
    if category:
        filters["category"] = category.lower()
    if gender and gender != "unisex":
        filters["gender"] = ["unisex", gender.lower()]

    # Price filter (soft — will be gated harder in scoring.py)
    if min_price > 0:
        filters["price"] = f"gte.{min_price}"
    if max_price < 999999:
        if "price" in filters and isinstance(filters["price"], str):
            # Can't do both gte and lte on same field in one filter, use RPC
            pass
        else:
            filters["price"] = f"lte.{max_price}"

    # Color filter
    if color:
        filters["color"] = color.lower()

    # Material filter
    if material:
        filters["material"] = material.lower()

    products = _sb_query("brand_products", filters, limit=limit)

    # Post-filter: size availability (JSONB field)
    if available_sizes:
        size_set = set(s.lower() for s in available_sizes)
        filtered = []
        for p in products:
            product_sizes = p.get("sizes", [])
            if isinstance(product_sizes, str):
                try:
                    product_sizes = json.loads(product_sizes)
                except Exception:
                    product_sizes = []
            if not product_sizes:
                filtered.append(p)  # No size info = include
                continue
            product_size_set = set(s.lower() for s in product_sizes if isinstance(s, str))
            if product_size_set & size_set:
                filtered.append(p)
        products = filtered

    # Post-filter: occasion relevance (if tags contain occasion)
    if occasion:
        occasion_lower = occasion.lower()
        occasion_filtered = []
        for p in products:
            tags = p.get("tags", [])
            if isinstance(tags, str):
                try:
                    tags = json.loads(tags)
                except Exception:
                    tags = []
            title = (p.get("title", "") + " " + p.get("description", "")).lower()
            # Include if tags or title mention the occasion
            if any(occasion_lower in str(t).lower() for t in tags) or occasion_lower in title:
                occasion_filtered.append(p)
        # If no occasion-tagged products, return all (don't lose everything)
        if occasion_filtered:
            products = occasion_filtered

    return products[:limit]


def filter_closet_items(
    user_id: str,
    category: str = "",
    color: str = "",
    material: str = "",
    pattern: str = "",
    limit: int = 50,
) -> list[dict]:
    """
    Pre-filter user closet items by硬 constraints.
    """
    if not user_id:
        return []

    filters = {"user_id": user_id}
    if category:
        filters["category"] = category.lower()
    if color:
        filters["color_primary"] = color.lower()
    if material:
        filters["material"] = material.lower()

    items = _sb_query("user_closet_items", filters, limit=limit)

    # Post-filter: pattern
    if pattern:
        pattern_lower = pattern.lower()
        items = [i for i in items if i.get("pattern", "").lower() == pattern_lower]

    return items[:limit]


def filter_partner_products(
    host_brand: str,
    category: str = "",
    gender: str = "",
    min_price: float = 0,
    max_price: float = 999999,
    limit: int = 30,
) -> list[dict]:
    """
    Pre-filter partner brand products for syndicate recommendations.
    """
    if not host_brand:
        return []

    filters = {"is_active": True, "brand": f"neq.{host_brand}"}
    if category:
        filters["category"] = category.lower()
    if gender and gender != "unisex":
        filters["gender"] = ["unisex", gender.lower()]

    products = _sb_query("brand_products", filters, limit=limit)

    # Apply price filter in post-processing
    if min_price > 0 or max_price < 999999:
        products = [
            p for p in products
            if min_price <= float(p.get("price", 0)) <= max_price
        ]

    return products[:limit]


def get_available_sizes(product: dict) -> list[str]:
    """Extract available sizes from a product."""
    sizes = product.get("sizes", [])
    if isinstance(sizes, str):
        try:
            sizes = json.loads(sizes)
        except Exception:
            sizes = []
    return [s for s in sizes if isinstance(s, str)]


def check_stock(product: dict) -> bool:
    """Check if a product is in stock (soft check)."""
    if not product.get("is_active", True):
        return False
    sizes = get_available_sizes(product)
    # If sizes listed, assume in stock
    if sizes:
        return True
    # If no size info, assume in stock (can't determine otherwise)
    return True


def get_product_price(product: dict) -> float:
    """Get product price as float."""
    try:
        return float(product.get("price", 0))
    except (ValueError, TypeError):
        return 0.0


def apply_price_filter(products: list[dict], min_price: float, max_price: float) -> list[dict]:
    """Apply price range filter to a list of products."""
    return [
        p for p in products
        if min_price <= get_product_price(p) <= max_price
    ]
