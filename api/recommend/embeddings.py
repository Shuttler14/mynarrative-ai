"""
Embeddings Module — Dual pipeline: OpenAI text + image (Fashion-CLIP via Replicate).
Zero external cost. Falls back gracefully when image model unavailable.
"""
from __future__ import annotations
import json
import os
import re
import hashlib
import time
from typing import Optional

# In-memory embedding cache (TTL 1 hour)
_cache: dict[str, tuple[list[float], float]] = {}
CACHE_TTL = 3600

# ── Attribute Extraction ───────────────────────────────────────────────────

# Color keywords → normalized color name
_COLOR_KEYWORDS = {
    "black": "black", "white": "white", "red": "red", "blue": "blue",
    "navy": "navy", "green": "green", "olive": "olive", "emerald": "emerald",
    "teal": "teal", "purple": "purple", "lavender": "lavender", "pink": "pink",
    "hot pink": "hot_pink", "coral": "coral", "peach": "peach", "orange": "orange",
    "burnt orange": "burnt_orange", "yellow": "yellow", "mustard": "mustard",
    "gold": "gold", "beige": "beige", "cream": "cream", "tan": "tan",
    "brown": "brown", "camel": "camel", "burgundy": "burgundy", "maroon": "maroon",
    "mauve": "mauve", "rust": "rust", "terracotta": "terracotta", "sage": "sage",
    "mint": "mint", "aqua": "aqua", "royal blue": "royal_blue",
    "sky blue": "sky_blue", "charcoal": "charcoal", "grey": "grey",
    "gray": "grey", "silver": "silver", "stone": "stone", "khaki": "khaki",
    "ivory": "ivory", "off-white": "off_white", "chocolate": "chocolate",
    "wine": "wine", "forest green": "forest_green", "lime": "lime",
    "crimson": "crimson", "blush": "blush", "denim": "denim_blue",
}

_MATERIAL_KEYWORDS = {
    "cotton": "cotton", "linen": "linen", "silk": "silk", "satin": "satin",
    "wool": "wool", "cashmere": "cashmere", "denim": "denim", "leather": "leather",
    "suede": "suede", "velvet": "velvet", "chiffon": "chiffon", "nylon": "nylon",
    "polyester": "polyester", "fleece": "fleece", "chambray": "chambray",
    "crepe": "crepe", "sequin": "sequin", "rayon": "rayon", "spandex": "spandex",
    "neoprene": "neoprene", "vinyl": "vinyl", "tweed": "tweed", "corduroy": "corduroy",
    "organza": "organza", "taffeta": "taffeta", "lace": "lace",
}

_PATTERN_KEYWORDS = {
    "solid": "solid", "plain": "solid", "striped": "striped", "stripe": "striped",
    "plaid": "plaid", "flannel": "plaid", "floral": "floral", "flower": "floral",
    "geometric": "geometric", "polka dot": "polka_dot", "polka-dot": "polka_dot",
    "animal": "animal", "leopard": "animal", "zebra": "animal", "abstract": "abstract",
    "check": "check", "checked": "check", "houndstooth": "check",
    "camo": "camo", "camouflage": "camo",
}

_OCCASION_KEYWORDS = {
    "casual": "casual", "everyday": "casual", "work": "business_formal",
    "office": "business_formal", "professional": "business_formal",
    "business": "business_casual", "smart": "business_casual",
    "cocktail": "cocktail", "party": "cocktail", "evening": "cocktail",
    "formal": "black_tie", "gala": "gala", "black tie": "black_tie",
    "beach": "beach", "resort": "beach", "vacation": "beach", "pool": "beach",
    "date": "date_night", "romantic": "date_night",
    "brunch": "brunch", "weekend": "brunch", "sunday": "brunch",
    "gym": "workout", "workout": "workout", "athletic": "workout", "yoga": "workout",
    "street": "streetwear", "urban": "streetwear", "hip hop": "streetwear",
    "festival": "festival", "concert": "festival", "rave": "festival",
    "interview": "interview", "meeting": "interview",
    "wedding": "wedding_guest", "reception": "wedding_guest",
    "adventure": "outdoor_adventure", "hiking": "outdoor_adventure", "camping": "outdoor_adventure",
    "minimalist": "minimalist", "clean": "minimalist",
}

_STYLE_KEYWORDS = {
    "classic": "classic", "timeless": "classic", "refined": "classic",
    "minimalist": "minimalist", "clean": "minimalist", "simple": "minimalist",
    "bohemian": "bohemian", "boho": "bohemian", "free-spirited": "bohemian", "eclectic": "bohemian",
    "streetwear": "streetwear", "urban": "streetwear", "street": "streetwear",
    "romantic": "romantic", "feminine": "romantic", "soft": "romantic",
    "edgy": "edgy", "bold": "edgy", "rebellious": "edgy",
    "preppy": "preppy", "polished": "preppy", "prep": "preppy",
    "athleisure": "athleisure", "athletic": "athleisure", "sporty": "athleisure",
    "avant-garde": "avant_garde", "experimental": "avant_garde",
    "relaxed": "relaxed", "casual": "relaxed", "laid-back": "relaxed",
}

_CATEGORY_KEYWORDS = {
    "shirt": "top", "t-shirt": "top", "tee": "top", "blouse": "top",
    "tank": "top", "crop": "top", "sweater": "top", "hoodie": "top",
    "pullover": "top", "turtleneck": "top", "polo": "top", "knit": "top",
    "jeans": "bottom", "pants": "bottom", "trousers": "bottom",
    "shorts": "bottom", "skirt": "bottom", "leggings": "bottom",
    "chinos": "bottom", "cargo": "bottom", "culottes": "bottom",
    "dress": "dress", "gown": "dress", "maxi dress": "dress",
    "mini dress": "dress", "midi dress": "dress",
    "jacket": "outerwear", "coat": "outerwear", "blazer": "outerwear",
    "cardigan": "outerwear", "vest": "outerwear", "parka": "outerwear",
    "trench": "outerwear", "windbreaker": "outerwear", "puffer": "outerwear",
    "sneakers": "footwear", "shoes": "footwear", "boots": "footwear",
    "heels": "footwear", "flats": "footwear", "sandals": "footwear",
    "loafers": "footwear", "espadrilles": "footwear", "wedges": "footwear",
    "bag": "bag", "handbag": "bag", "tote": "bag", "clutch": "bag",
    "backpack": "bag", "crossbody": "bag", "purse": "bag",
    "necklace": "jewelry", "earring": "jewelry", "bracelet": "jewelry",
    "ring": "jewelry", "watch": "jewelry", "pendant": "jewelry",
    "scarf": "accessory", "hat": "accessory", "belt": "accessory",
    "sunglasses": "accessory", "gloves": "accessory",
}

_FORMALITY_SIGNALS = {
    "ultra_casual": ["sweatpants", "pajama", "slipper", "crocs"],
    "casual": ["t-shirt", "jeans", "sneakers", "hoodie", "shorts", "cap"],
    "smart_casual": ["chinos", "polo", "loafers", "blazer", "khaki"],
    "business_casual": ["button-down", "slacks", "oxford", "chinos"],
    "business": ["suit", "tie", "dress shoes", "pencil skirt"],
    "formal": ["gown", "tuxedo", "cocktail dress", "heels"],
    "black_tie": ["tuxedo", "ball gown", "stiletto", "clutch"],
}


def extract_attributes(product: dict) -> dict:
    """Extract structured fashion attributes from product data."""
    text = " ".join([
        product.get("title", ""),
        product.get("description", ""),
        " ".join(product.get("tags", [])),
        product.get("color", ""),
        product.get("material", ""),
        product.get("subcategory", ""),
    ]).lower()

    # Color
    detected_colors = []
    for keyword, color in _COLOR_KEYWORDS.items():
        if keyword in text:
            detected_colors.append(color)
    if not detected_colors and product.get("color"):
        c = product["color"].lower()
        detected_colors.append(_COLOR_KEYWORDS.get(c, c))

    # Material
    detected_materials = []
    for keyword, material in _MATERIAL_KEYWORDS.items():
        if keyword in text:
            detected_materials.append(material)
    if not detected_materials and product.get("material"):
        m = product["material"].lower()
        detected_materials.append(_MATERIAL_KEYWORDS.get(m, m))

    # Pattern
    detected_patterns = []
    for keyword, pattern in _PATTERN_KEYWORDS.items():
        if keyword in text:
            detected_patterns.append(pattern)
    if not detected_patterns:
        detected_patterns.append("solid")

    # Category
    detected_category = product.get("category", "")
    if not detected_category:
        for keyword, cat in _CATEGORY_KEYWORDS.items():
            if keyword in text:
                detected_category = cat
                break

    # Occasion
    detected_occasions = []
    for keyword, occ in _OCCASION_KEYWORDS.items():
        if keyword in text:
            detected_occasions.append(occ)

    # Style
    detected_styles = []
    for keyword, style in _STYLE_KEYWORDS.items():
        if keyword in text:
            detected_styles.append(style)

    # Formality
    formality = 3  # Default smart_casual
    for level, signals in _FORMALITY_SIGNALS.items():
        for signal in signals:
            if signal in text:
                mapping = {"ultra_casual": 1, "casual": 2, "smart_casual": 3,
                           "business_casual": 4, "business": 5, "formal": 6, "black_tie": 7}
                formality = mapping.get(level, 3)
                break

    # Gender
    gender = product.get("gender", "unisex")
    if "women" in text or "feminine" in text or "ladies" in text:
        gender = "women"
    elif "men" in text or "masculine" in text or "gentlemen" in text:
        gender = "men"

    return {
        "colors": list(set(detected_colors))[:3],
        "color": detected_colors[0] if detected_colors else "",
        "materials": list(set(detected_materials))[:2],
        "material": detected_materials[0] if detected_materials else "",
        "patterns": list(set(detected_patterns))[:2],
        "pattern": detected_patterns[0] if detected_patterns else "solid",
        "category": detected_category,
        "occasions": list(set(detected_occasions))[:3],
        "styles": list(set(detected_styles))[:2],
        "formality": formality,
        "gender": gender,
        "silhouette": _detect_silhouette(text),
    }


def _detect_silhouette(text: str) -> str:
    """Detect silhouette from text."""
    if any(w in text for w in ["oversized", "boxy", "loose", "relaxed"]):
        return "oversized"
    if any(w in text for w in ["slim", "fitted", "skinny", "tailored", "structured"]):
        return "fitted"
    if any(w in text for w in ["flowy", "flowing", "draped", "飘"]):
        return "flowy"
    if any(w in text for w in ["straight", "regular", "classic"]):
        return "straight"
    return "regular"


def build_enriched_description(product: dict, attrs: dict) -> str:
    """Build an enriched text description for embedding generation."""
    parts = []
    if attrs["category"]:
        parts.append(f"Category: {attrs['category']}")
    if attrs["colors"]:
        parts.append(f"Colors: {', '.join(attrs['colors'])}")
    if attrs["materials"]:
        parts.append(f"Material: {', '.join(attrs['materials'])}")
    if attrs["patterns"]:
        parts.append(f"Pattern: {', '.join(attrs['patterns'])}")
    if attrs["styles"]:
        parts.append(f"Style: {', '.join(attrs['styles'])}")
    if attrs["occasions"]:
        parts.append(f"Occasion: {', '.join(attrs['occasions'])}")
    if attrs["formality"] >= 5:
        parts.append("Formal wear")
    elif attrs["formality"] <= 2:
        parts.append("Casual wear")
    if attrs["silhouette"] != "regular":
        parts.append(f"Silhouette: {attrs['silhouette']}")
    if product.get("title"):
        parts.append(f"Item: {product['title']}")
    return " | ".join(parts) if parts else product.get("title", "fashion item")


# ── Embedding Cache ────────────────────────────────────────────────────────

def _cache_key(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


def _get_cached(text: str) -> Optional[list[float]]:
    key = _cache_key(text)
    if key in _cache:
        vec, ts = _cache[key]
        if time.time() - ts < CACHE_TTL:
            return vec
        del _cache[key]
    return None


def _set_cached(text: str, vec: list[float]):
    key = _cache_key(text)
    _cache[key] = (vec, time.time())
    # Evict old entries if cache is large
    if len(_cache) > 5000:
        oldest = sorted(_cache.items(), key=lambda x: x[1][1])[:1000]
        for k, _ in oldest:
            del _cache[k]


# ── OpenAI Text Embeddings ────────────────────────────────────────────────

def _openai_embed(text: str) -> list[float]:
    """Generate text embedding via OpenAI API."""
    import requests as _requests
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")

    cached = _get_cached(text)
    if cached:
        return cached

    resp = _requests.post(
        "https://api.openai.com/v1/embeddings",
        json={"model": "text-embedding-3-small", "input": text},
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=30,
    )
    data = resp.json()
    vec = data["data"][0]["embedding"]
    _set_cached(text, vec)
    return vec


# ── Image Embeddings via Replicate (Fashion-CLIP) ─────────────────────────

def _replicate_image_embed(image_url: str) -> Optional[list[float]]:
    """Generate image embedding via Replicate's Fashion-CLIP model."""
    import requests as _requests
    token = os.environ.get("REPLICATE_API_TOKEN", "")
    if not token:
        return None

    cached = _get_cached(f"img:{image_url}")
    if cached:
        return cached

    try:
        resp = _requests.post(
            "https://api.replicate.com/v1/predictions",
            json={
                "version": "פורס1999fashion-clip",
                "input": {"image": image_url},
            },
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        pred = resp.json()

        pred_id = pred.get("id", "")
        if not pred_id:
            return None

        for _ in range(30):
            time.sleep(2)
            poll_resp = _requests.get(
                f"https://api.replicate.com/v1/predictions/{pred_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            result = poll_resp.json()
            if result.get("status") == "succeeded":
                output = result.get("output", [])
                if isinstance(output, list) and len(output) > 0:
                    vec = output[0] if isinstance(output[0], list) else None
                    if vec:
                        _set_cached(f"img:{image_url}", vec)
                        return vec
                return None
            elif result.get("status") == "failed":
                return None

    except Exception:
        return None

    return None


# ── Image Embedding via OpenAI Vision (fallback) ──────────────────────────

def _openai_image_embed_via_text(image_url: str) -> Optional[list[float]]:
    """Describe image via GPT-4o-mini, then embed the description (free fallback)."""
    import requests as _requests
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return None

    try:
        resp = _requests.post(
            "https://api.openai.com/v1/chat/completions",
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "Describe this fashion item in detail: category, color, material, pattern, style, occasion, fit. Be concise. Output as structured attributes."},
                    {"role": "user", "content": [
                        {"type": "text", "text": "Describe this fashion item:"},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ]},
                ],
                "max_tokens": 200,
            },
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        data = resp.json()
        description = data["choices"][0]["message"]["content"]
        return _openai_embed(description)
    except Exception:
        return None


# ── Main Embedding Functions ───────────────────────────────────────────────

def generate_text_embedding(text: str) -> list[float]:
    """Generate a text embedding. Uses cache when available."""
    return _openai_embed(text)


def generate_product_embedding(product: dict) -> dict:
    """
    Generate a rich, multi-attribute embedding for a product.
    Returns: {embedding, attributes, description}
    """
    attrs = extract_attributes(product)
    enriched = build_enriched_description(product, attrs)
    embedding = _openai_embed(enriched)

    # Try image embedding if available
    image_url = product.get("image_url", "")
    image_embedding = None
    if image_url:
        image_embedding = _replicate_image_embed(image_url)
        if image_embedding is None:
            # Fallback: describe image then embed
            image_embedding = _openai_image_embed_via_text(image_url)

    # Combine text + image embeddings if both available
    if image_embedding and len(image_embedding) == len(embedding):
        # Weighted average: 60% text, 40% image
        combined = [(t * 0.6 + i * 0.4) for t, i in zip(embedding, image_embedding)]
        return {"embedding": combined, "attributes": attrs, "description": enriched, "has_image": True}

    return {"embedding": embedding, "attributes": attrs, "description": enriched, "has_image": False}


def generate_closet_embedding(image_url: str, description: str = "", attributes: dict = None) -> dict:
    """
    Generate embedding for a closet item (uploaded photo).
    Returns: {embedding, attributes, description}
    """
    attrs = attributes or {}

    # Try Fashion-CLIP image embedding first
    image_embedding = _replicate_image_embed(image_url)

    # If no image embedding, describe the image
    if image_embedding is None and image_url:
        image_embedding = _openai_image_embed_via_text(image_url)

    # Text embedding from description
    text_embedding = None
    if description:
        text_embedding = _openai_embed(description)

    # Combine
    if image_embedding and text_embedding and len(image_embedding) == len(text_embedding):
        combined = [(t * 0.5 + i * 0.5) for t, i in zip(text_embedding, image_embedding)]
        return {"embedding": combined, "attributes": attrs, "description": description, "source": "multimodal"}
    elif image_embedding:
        return {"embedding": image_embedding, "attributes": attrs, "description": description, "source": "image"}
    elif text_embedding:
        return {"embedding": text_embedding, "attributes": attrs, "description": description, "source": "text"}

    # Final fallback: generate from attributes
    fallback_text = build_enriched_description({"title": description, **attrs}, attrs)
    embedding = _openai_embed(fallback_text)
    return {"embedding": embedding, "attributes": attrs, "description": description, "source": "attributes"}


def generate_query_embedding(query_text: str, occasion: str = "", style: str = "", price_tier: str = "") -> list[float]:
    """Generate an embedding for a search/recommendation query."""
    parts = [query_text]
    if occasion:
        parts.append(f"Occasion: {occasion}")
    if style:
        parts.append(f"Style: {style}")
    if price_tier:
        parts.append(f"Budget: {price_tier}")
    enriched = " | ".join(parts)
    return _openai_embed(enriched)


def compute_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = sum(a * a for a in vec_a) ** 0.5
    norm_b = sum(b * b for b in vec_b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def compute_attribute_similarity(attrs_a: dict, attrs_b: dict) -> float:
    """Compute similarity between two sets of extracted attributes."""
    score = 0.0
    total = 0.0

    # Color match
    colors_a = set(attrs_a.get("colors", []))
    colors_b = set(attrs_b.get("colors", []))
    if colors_a and colors_b:
        total += 1.0
        overlap = len(colors_a & colors_b)
        if overlap > 0:
            score += 1.0
        elif colors_a & colors_b:
            score += 0.5

    # Material match
    mats_a = set(attrs_a.get("materials", []))
    mats_b = set(attrs_b.get("materials", []))
    if mats_a and mats_b:
        total += 1.0
        if mats_a & mats_b:
            score += 1.0

    # Category match
    cat_a = attrs_a.get("category", "")
    cat_b = attrs_b.get("category", "")
    if cat_a and cat_b:
        total += 1.0
        if cat_a == cat_b:
            score += 0.3  # Same category = ok but not ideal for outfit
        elif cat_a != cat_b:
            score += 0.8  # Different categories = good for outfit diversity

    # Style match
    styles_a = set(attrs_a.get("styles", []))
    styles_b = set(attrs_b.get("styles", []))
    if styles_a and styles_b:
        total += 1.0
        if styles_a & styles_b:
            score += 1.0

    # Formality match
    form_a = attrs_a.get("formality", 3)
    form_b = attrs_b.get("formality", 3)
    if form_a and form_b:
        total += 1.0
        diff = abs(form_a - form_b)
        if diff <= 1:
            score += 1.0
        elif diff <= 2:
            score += 0.6
        else:
            score += 0.2

    return score / max(total, 1.0)
