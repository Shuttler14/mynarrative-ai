"""
Garment Extraction & Flat Lay Pipeline
Extracts clothing from model photos → generates clean flat lay images for VTON.
Uses Replicate background removal + image processing.
"""
import json
import os
import requests
import base64
import io
from typing import Optional, Dict

# ── Replicate client (lazy import) ────────────────────────────────────────
_replicate_client = None

def _get_replicate():
    global _replicate_client
    if _replicate_client is None:
        try:
            import replicate
            token = os.environ.get("REPLICATE_API_TOKEN") or os.getenv("REPLICATE_API_TOKEN")
            if not token:
                return None
            _replicate_client = replicate.Client(api_token=token)
        except ImportError:
            return None
    return _replicate_client


# ── Background Removal ─────────────────────────────────────────────────────
def remove_background(image_url: str) -> Optional[str]:
    """
    Remove background from a product/model image.
    Returns URL of background-removed image (transparent PNG).
    Uses cjwbw/rembg or similar Replicate model.
    """
    client = _get_replicate()
    if not client:
        return None

    try:
        model = client.models.get("cjwbw/rembg")
        latest = model.latest_version
        version_id = latest.id if latest else "fb8af171cfa1616ddcf1242c093f9c46bcada5ad4cf6f2fbe8b81b330ec5c003"

        output = client.run(
            f"cjwbw/rembg:{version_id}",
            input={"image": image_url}
        )
        return str(output) if output else None
    except Exception as e:
        print(f"⚠️ [remove_background] {e}")
        return None


# ── Garment Classification ─────────────────────────────────────────────────
GARMENT_CATEGORIES = {
    "upper_body": ["t-shirt", "shirt", "blouse", "top", "kurta", "kurti", "hoodie",
                    "sweatshirt", "sweater", "cardigan", "jacket", "blazer", "polo",
                    "tee", "tank top", "camisole", "henley"],
    "lower_body": ["jeans", "trousers", "pants", "shorts", "skirt", "chinos",
                    "joggers", "leggings", "dhoti", "palazzo", "culottes"],
    "full_body":  ["dress", "gown", "saree", "lehenga", "salwar", "anarkali",
                    "sherwani", "suit", "jumpsuit", "romper", "kaftan"],
    "footwear":   ["sneakers", "shoes", "sandals", "heels", "boots", "flats",
                    "loafers", "slides", "mules"],
    "accessory":  ["bag", "watch", "necklace", "earring", "bracelet", "scarf",
                    "belt", "hat", "sunglasses", "clutch", "stole"],
}

def classify_garment(title: str, category: str = "") -> str:
    """Classify garment into VTON category (upper_body, lower_body, full_body)."""
    text = f"{title} {category}".lower()
    for cat, keywords in GARMENT_CATEGORIES.items():
        for kw in keywords:
            if kw in text:
                return cat
    return "upper_body"


# ── Flat Lay Generation ────────────────────────────────────────────────────
def generate_flat_lay(
    image_url: str,
    garment_category: str = "upper_body",
    style: str = "minimal"
) -> Optional[str]:
    """
    Generate a flat lay / ghost mannequin image from a product photo.
    Pipeline: remove bg → compose flat lay → return URL.
    """
    # Step 1: Remove background
    bg_removed = remove_background(image_url)
    if not bg_removed:
        return image_url

    # Step 2: For flat lay, we can use the bg-removed image directly
    # or compose it on a clean background using PIL/Canvas
    # For now, return the bg-removed image as the flat lay
    # TODO: Add canvas composition for professional flat lay
    return bg_removed


# ── Full Garment Processing Pipeline ───────────────────────────────────────
def process_product_for_vton(
    image_url: str,
    title: str = "",
    category: str = "",
    existing_flat_lay: str = "",
) -> Dict:
    """
    Process a product image for VTON readiness.
    - If flat_lay_url already exists, use it
    - Otherwise, extract garment and generate flat lay
    Returns dict with vton_ready_url, category, processing_status.
    """
    if existing_flat_lay:
        return {
            "vton_ready_url": existing_flat_lay,
            "category": classify_garment(title, category),
            "processing_status": "existing_flat_lay",
        }

    # Extract garment from model photo
    flat_lay_url = generate_flat_lay(image_url, classify_garment(title, category))

    if flat_lay_url and flat_lay_url != image_url:
        return {
            "vton_ready_url": flat_lay_url,
            "category": classify_garment(title, category),
            "processing_status": "extracted",
        }

    # Fallback: use original image (VTON can handle model photos to some extent)
    return {
        "vton_ready_url": image_url,
        "category": classify_garment(title, category),
        "processing_status": "fallback_original",
    }


# ── Batch Process Products ─────────────────────────────────────────────────
def batch_process_products(products: list, max_concurrent: int = 3) -> list:
    """Process multiple products for VTON readiness."""
    results = []
    for p in products[:max_concurrent]:
        result = process_product_for_vton(
            image_url=p.get("image_url", ""),
            title=p.get("title", ""),
            category=p.get("category", ""),
            existing_flat_lay=p.get("flat_lay_url", ""),
        )
        results.append({**p, **result})
    return results
