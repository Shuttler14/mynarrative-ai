"""
================================================================================
  MY NARRATIVE AI STYLIST — BACKEND PIPELINE (OpenAI-Powered)
  api/stylist_pipeline.py
================================================================================

  PURPOSE:
  Vercel Serverless Function that orchestrates the AI Stylist pipeline
  using OpenAI GPT-4o for fashion recommendations and Replicate FLUX
  for image generation. No AWS Rekognition or Supabase dependencies.

  Flow:
    Step 1 (receive):  occasion + vibe_id + skin_tone + body_shape from frontend
    Step 2 (parallel):  GPT-4o fashion prompt + FLUX image generation
    Step 3 (return):    aggregated response to frontend

  REQUIRED ENVIRONMENT VARIABLES (set in Vercel Dashboard):
  ─────────────────────────────────────────────────────────
  OPENAI_API_KEY          → OpenAI API key (for GPT-4o)
  REPLICATE_API_TOKEN     → Replicate API token (for FLUX image generation)

================================================================================
"""

from http.server import BaseHTTPRequestHandler
import base64
import json
import os
import time
import math
import threading
import urllib.parse
import urllib.request
import urllib.error
from typing import Any, Dict, List

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import replicate
    REPLICATE_AVAILABLE = True
except ImportError:
    REPLICATE_AVAILABLE = False

try:
    import requests as http_requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    import boto3
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False


# ---------------------------------------------------------------------------
# CONFIGURATION & CONSTANTS
# ---------------------------------------------------------------------------

# Monk Skin Tone (MST) Scale — 10 tones from light to dark
MST_LABELS = {
    1: "Very Light",
    2: "Light",
    3: "Light-Medium",
    4: "Medium-Light",
    5: "Medium",
    6: "Medium-Tan",
    7: "Tan",
    8: "Dark-Tan",
    9: "Dark",
    10: "Very Dark",
}

# Color theory mapping: MST → complementary fashion tones
MST_COLOR_THEORY = {
    1: {"best_colors": ["Navy", "Emerald", "Burgundy", "Charcoal"], "avoid": ["Pale Yellow", "Beige"], "undertone_note": "Cool jewel tones create striking contrast."},
    2: {"best_colors": ["Forest Green", "Plum", "Cobalt Blue", "Rust"], "avoid": ["Neon Yellow"], "undertone_note": "Rich earth tones and deep jewels balance lighter skin."},
    3: {"best_colors": ["Teal", "Coral", "Olive", "Mustard"], "avoid": ["Washed-out Pastels"], "undertone_note": "Warm mid-tones with subtle saturation work best."},
    4: {"best_colors": ["Burnt Orange", "Royal Blue", "Sage Green", "Maroon"], "avoid": ["Khaki"], "undertone_note": "Warm undertones pair beautifully with earth-inspired shades."},
    5: {"best_colors": ["Hot Pink", "Turquoise", "Gold", "Wine Red"], "avoid": ["Muddy Brown"], "undertone_note": "Medium tones can carry both warm and cool palettes."},
    6: {"best_colors": ["Tangerine", "Electric Blue", "Lavender", "Cream"], "avoid": ["Dark Brown"], "undertone_note": "High-contrast brights create editorial impact."},
    7: {"best_colors": ["White", "Bright Yellow", "Fuchsia", "Sky Blue"], "avoid": ["Dark Navy"], "undertone_note": "Vibrant, saturated colors pop against warm tan skin."},
    8: {"best_colors": ["Ivory", "Gold", "Coral Red", "Emerald"], "avoid": ["Charcoal Grey"], "undertone_note": "Warm metallics and bright jewel tones celebrate deep warmth."},
    9: {"best_colors": ["White", "Canary Yellow", "Hot Pink", "Cobalt"], "avoid": ["Dark Olive"], "undertone_note": "High-saturation pure colors create maximum visual impact."},
    10: {"best_colors": ["Pure White", "Bright Orange", "Electric Green", "Gold"], "avoid": ["Dark Brown", "Black"], "undertone_note": "Bold, luminous colors create stunning contrast."},
}

# Vibe presets — map vibe_id to prompt modifiers
VIBE_PRESETS = {
    "caffeine_survivor": {
        "label": "Surviving on Caffeine",
        "flux_modifier": "oversized cozy hoodie, distressed denim, messy-chic hair, coffee shop aesthetic",
        "style_persona": "effortlessly unbothered",
    },
    "sarcastic_rizzler": {
        "label": "The Sarcastic Rizzler",
        "flux_modifier": "sharp tailored blazer, statement sneakers, confident pose, editorial lighting",
        "style_persona": "sharp-witted trendsetter",
    },
    "main_character": {
        "label": "Main Character Energy",
        "flux_modifier": "dramatic flowing outfit, cinematic backlighting, street style, golden hour",
        "style_persona": "the protagonist of every scene",
    },
    "quiet_luxury": {
        "label": "Quiet Luxury",
        "flux_modifier": "minimal neutral tones, cashmere texture, understated elegance, clean silhouette",
        "style_persona": "old-money minimalist",
    },
}

# Occasion presets — map occasion to prompt context
OCCASION_PRESETS = {
    "date_night": {
        "label": "Date Night",
        "flux_context": "romantic evening setting, warm ambient lighting, upscale restaurant vibes",
        "style_direction": "elevated casual to semi-formal",
    },
    "office": {
        "label": "Office",
        "flux_context": "modern corporate office, clean backdrop, professional lighting",
        "style_direction": "smart casual to business formal",
    },
    "sangeet": {
        "label": "Sangeet",
        "flux_context": "vibrant Indian wedding sangeet celebration, colorful lighting, festive atmosphere",
        "style_direction": "festive ethnic with modern fusion",
    },
    "airport_look": {
        "label": "Airport Look",
        "flux_context": "luxury airport terminal, travel aesthetic, natural daylight",
        "style_direction": "comfortable yet polished travel wear",
    },
}

# Skin tone label mapping (frontend sends labels, we need MST numbers)
SKIN_TONE_TO_MST = {
    "Fair": 2, "Light": 2,
    "Medium": 5, "Olive": 4,
    "Brown": 7, "Dark": 9,
    "Deep": 10,
}

BODY_SHAPE_MAP = {
    "slim_athletic": "slim athletic physique",
    "average": "medium build",
    "muscular": "well-built athletic physique",
    "plus_size": "plus size body type",
    "tall_lean": "tall lean physique",
    "short_stocky": "compact stocky build",
}

# Gender mapping from frontend
GENDER_MAP = {
    "men": "man",
    "women": "woman",
}

MY_NARRATIVE_CATALOG = [
    {
        "handle": "my-pet-name-is-iitian-custom-batch-year-unisexual-graphic-printed-varsity-jacket",
        "title": "IITian Varsity Jacket",
        "price": 1299,
        "flat_lay_url": "https://cdn.shopify.com/s/files/1/0680/5762/8864/files/minimalist-hoodie-mockup-with-front-design-against-dark-neutral-backdrop-095_3.jpg?v=1755435363",
    },
    {
        "handle": "my-pet-name-is-nitian-custom-name-unisexual-hoodies",
        "title": "NITian Name Hoodies",
        "price": 999,
        "flat_lay_url": "https://cdn.shopify.com/s/files/1/0680/5762/8864/files/minimalist-hoodie-mockup-with-front-design-against-dark-neutral-backdrop-095_2.jpg?v=1754661883",
    },
    {
        "handle": "my-pet-name-is-nitian-custom-name-unisexual-t-shirt",
        "title": "NITian Name Tee",
        "price": 549,
        "flat_lay_url": "https://cdn.shopify.com/s/files/1/0680/5762/8864/files/Ifalltorisebeautifully_O_5.png?v=1753449803",
    },
    {
        "handle": "my-pet-name-is-nitian-custom-batch-year-unisexual-t-shirt-copy",
        "title": "NITian Batch Year Hoodies",
        "price": 999,
        "flat_lay_url": "https://cdn.shopify.com/s/files/1/0680/5762/8864/files/floating-white-hoodie-mockup-front-view-clean-light-grey-background-minimalist-studio-lighting-soft-shadows-design-center-chest-0630_24.jpg?v=1749484980",
    },
    {
        "handle": "my-pet-name-is-nitian-custom-batch-year-unisexual-t-shirt",
        "title": "NITian Batch Year Tee",
        "price": 549,
        "flat_lay_url": "https://cdn.shopify.com/s/files/1/0680/5762/8864/files/boxy-blank-white-round-neck-unisex-t-shirt-mockup-back-view-on-hanger-draped-fabric-backdrop-soft-neutral-lighting-minimal-and-elegant-presentation-1009_baef7207-3c62-4b24-83c5-c838f5f3a425.jpg?v=1751661711",
    },
    {
        "handle": "my-pet-name-is-iitian-custom-batch-year-unisexual-t-shirt",
        "title": "IITian Batch Year Tee",
        "price": 549,
        "flat_lay_url": "https://cdn.shopify.com/s/files/1/0680/5762/8864/files/studio-display-hoodie-mockup-on-mannequin-with-neutral-gray-background-clean-and-professional-0280_27_7266e927-9122-4c2a-87da-c7ce996ea321.jpg?v=1749142018",
    },
]

for _item in MY_NARRATIVE_CATALOG:
    _item["product_url"] = f"/products/{_item['handle']}"


# ---------------------------------------------------------------------------
# GLOBAL INVENTORY PIPELINE HELPERS (CJ / RAKUTEN → SCRUB → VECTOR → SEARCH)
# ---------------------------------------------------------------------------

RAKUTEN_API_BASE = os.environ.get("RAKUTEN_API_BASE", "https://api.rakutenmarketing.com")
CJ_API_BASE = os.environ.get("CJ_API_BASE", "https://product-search.api.cj.com")
RAKUTEN_TOKEN_URL = os.environ.get("RAKUTEN_TOKEN_URL", "").strip()
RAKUTEN_TOKEN_TTL_SAFETY_SECONDS = 60

_rakuten_token_cache = {
    "access_token": "",
    "expires_at": 0,
}
_rakuten_token_lock = threading.Lock()


def _sb_headers():
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_KEY", "").strip()
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    return url, key, headers


def sb_configured() -> bool:
    url, key, _ = _sb_headers()
    return bool(url and key)


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
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8") or "null"
            return json.loads(raw), None
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8")
        except Exception:
            detail = str(e)
        return None, f"http_{e.code}:{detail[:260]}"
    except Exception as e:
        return None, str(e)


def sb_upsert_global_inventory(rows: list):
    if not rows:
        return {"inserted": 0}, None
    _, _, headers = _sb_headers()
    headers["Prefer"] = "resolution=merge-duplicates,return=representation"
    url, key, _ = _sb_headers()
    if not url or not key:
        return None, "supabase_not_configured"
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


def sb_match_global_inventory(query_embedding: list, category: str = "", limit: int = 6):
    payload = {
        "query_embedding": query_embedding,
        "query_category": category or None,
        "match_count": max(1, min(20, int(limit or 6))),
    }
    data, err = _sb_request("POST", "/rest/v1/rpc/match_global_inventory", payload)
    if err:
        return [], err
    return data if isinstance(data, list) else [], None


def _cosine_similarity(a: list, b: list) -> float:
    if not a or not b:
        return 0.0
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for i in range(n):
        x = float(a[i] or 0.0)
        y = float(b[i] or 0.0)
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def sb_fallback_similarity_search(query_embedding: list, category: str = "", limit: int = 6):
    cat = (category or "").strip().lower()
    query = "/rest/v1/global_inventory?select=id,network,external_product_id,title,brand,category,price,currency,image_url,flat_lay_url,checkout_url,affiliate_url,embedding,quality_score,is_clean&is_clean=eq.true&limit=120"
    if cat:
        query += "&category=eq." + urllib.parse.quote(cat)
    rows, err = _sb_request("GET", query, None)
    if err:
        return [], err
    scored = []
    for row in (rows or []):
        emb = row.get("embedding")
        if not isinstance(emb, list):
            continue
        s = _cosine_similarity(query_embedding, emb)
        item = dict(row)
        item["similarity"] = round(float(s), 6)
        scored.append(item)
    scored.sort(key=lambda x: x.get("similarity", 0.0), reverse=True)
    return scored[: max(1, min(20, int(limit or 6)))], None


def get_text_embedding(client: "OpenAI", text: str) -> list:
    text = (text or "").strip()
    if not text:
        return []
    try:
        emb = client.embeddings.create(model="text-embedding-3-small", input=text)
        vec = emb.data[0].embedding if emb and emb.data else []
        return vec if isinstance(vec, list) else []
    except Exception as e:
        print(f"⚠️ [embedding] {e}")
        return []


def _download_bytes(url: str, timeout: int = 15) -> bytes:
    if not url or not isinstance(url, str):
        return b""
    req = urllib.request.Request(url, headers={"User-Agent": "MN-AI-Stylist/1.0"}, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def classify_affiliate_image(image_url: str) -> dict:
    """
    Gatekeeper for VTON-ready products:
    reject if human face / hands / heavy lifestyle clutter.
    """
    lowered = (image_url or "").lower()
    hard_reject_tokens = [
        "lookbook", "lifestyle", "on-model", "model", "celebrity", "person", "people", "street-style",
        "outfit", "selfie", "influencer", "runway", "editorial", "portrait"
    ]
    hard_pass_tokens = ["flatlay", "flat-lay", "ghost", "mockup", "hanger", "product-only", "product", "packshot"]

    if any(tok in lowered for tok in hard_reject_tokens):
        return {"approved": False, "reason": "url_pattern_human_lifestyle", "quality_score": 0.1}

    # Primary classifier: AWS Rekognition (if configured).
    aws_key = os.environ.get("AWS_ACCESS_KEY_ID")
    aws_secret = os.environ.get("AWS_SECRET_ACCESS_KEY")
    aws_region = os.environ.get("AWS_REGION", "ap-south-1")
    if BOTO3_AVAILABLE and aws_key and aws_secret:
        try:
            image_bytes = _download_bytes(image_url)
            if not image_bytes:
                return {"approved": False, "reason": "image_download_failed", "quality_score": 0.0}
            rek = boto3.client("rekognition", region_name=aws_region)
            faces = rek.detect_faces(Image={"Bytes": image_bytes}, Attributes=["DEFAULT"])
            face_count = len(faces.get("FaceDetails", []))
            labels = rek.detect_labels(Image={"Bytes": image_bytes}, MaxLabels=25, MinConfidence=70)
            names = [str(x.get("Name", "")).lower() for x in labels.get("Labels", [])]
            reject_labels = {
                "person", "human", "face", "head", "hand", "finger", "arm", "leg", "foot",
                "crowd", "city", "street", "room", "furniture", "indoor", "outdoor", "building"
            }
            clutter_hits = [n for n in names if n in reject_labels]
            if face_count > 0 or clutter_hits:
                return {"approved": False, "reason": "rekognition_detected_human_body_or_clutter", "quality_score": 0.12, "faces": face_count, "labels": clutter_hits[:6]}
            return {"approved": True, "reason": "rekognition_clean_product", "quality_score": 0.9}
        except Exception as e:
            print(f"⚠️ [classify_affiliate_image] rekognition fallback: {e}")

    # Strong heuristic fallback (strict allow-list + reject-list)
    if any(tok in lowered for tok in hard_pass_tokens):
        return {"approved": True, "reason": "heuristic_product_only_token", "quality_score": 0.82}
    return {"approved": False, "reason": "heuristic_reject_uncertain_image", "quality_score": 0.08}


def _first_non_empty(d: dict, keys: list, default=""):
    for k in keys:
        v = d.get(k)
        if v is not None and str(v).strip() != "":
            return v
    return default


def _extract_partner_products(payload: dict) -> list:
    if not isinstance(payload, dict):
        return []
    roots = ["products", "items", "data", "results", "result", "offers"]
    for key in roots:
        arr = payload.get(key)
        if isinstance(arr, list):
            return [x for x in arr if isinstance(x, dict)]
    if isinstance(payload.get("product"), dict):
        return [payload["product"]]
    return []


def _rakuten_credentials():
    """
    Supports both naming conventions:
    - Preferred: RAKUTEN_CLIENT_ID + RAKUTEN_CLIENT_SECRET
    - Legacy:    RAKUTEN_APP_ID + RAKUTEN_TOKEN
    """
    client_id = os.environ.get("RAKUTEN_CLIENT_ID", "").strip() or os.environ.get("RAKUTEN_APP_ID", "").strip()
    client_secret = os.environ.get("RAKUTEN_CLIENT_SECRET", "").strip() or os.environ.get("RAKUTEN_TOKEN", "").strip()
    return client_id, client_secret


def _request_rakuten_access_token(client_id: str, client_secret: str):
    if not client_id or not client_secret:
        return "", 0, "missing_rakuten_oauth_credentials"

    token_url = RAKUTEN_TOKEN_URL or f"{RAKUTEN_API_BASE.rstrip('/')}/token"
    scope = os.environ.get("RAKUTEN_SCOPE", "").strip()
    payload = {"grant_type": "client_credentials"}
    if scope:
        payload["scope"] = scope

    basic = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("utf-8")
    req = urllib.request.Request(
        token_url,
        data=urllib.parse.urlencode(payload).encode("utf-8"),
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8") or "{}"
            token_payload = json.loads(raw)
        access_token = str(token_payload.get("access_token", "")).strip()
        expires_in = int(token_payload.get("expires_in", 3600) or 3600)
        if not access_token:
            return "", 0, f"rakuten_token_missing_access_token:{raw[:220]}"
        expires_at = int(time.time()) + max(60, expires_in) - RAKUTEN_TOKEN_TTL_SAFETY_SECONDS
        return access_token, expires_at, None
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8")
        except Exception:
            detail = str(e)
        return "", 0, f"rakuten_token_http_{e.code}:{detail[:260]}"
    except Exception as e:
        return "", 0, f"rakuten_token_error:{e}"


def get_rakuten_access_token(force_refresh: bool = False):
    # Optional manual override token for quick validation / emergency fallback.
    # Primary flow remains OAuth client_credentials.
    manual_access_token = os.environ.get("RAKUTEN_ACCESS_TOKEN", "").strip()
    if manual_access_token and not force_refresh:
        return manual_access_token, None

    client_id, client_secret = _rakuten_credentials()
    now = int(time.time())
    with _rakuten_token_lock:
        cached_token = _rakuten_token_cache.get("access_token", "")
        cached_exp = int(_rakuten_token_cache.get("expires_at", 0) or 0)
        if not force_refresh and cached_token and cached_exp > now:
            return cached_token, None

        token, expires_at, err = _request_rakuten_access_token(client_id, client_secret)
        if err:
            return "", err
        _rakuten_token_cache["access_token"] = token
        _rakuten_token_cache["expires_at"] = expires_at
        return token, None


def fetch_rakuten_products(query: str, brand: str, category: str, limit: int = 30):
    app_id = os.environ.get("RAKUTEN_APP_ID", "").strip() or os.environ.get("RAKUTEN_CLIENT_ID", "").strip()
    bearer, token_err = get_rakuten_access_token()
    if token_err:
        return [], token_err
    params = {
        "query": query or "",
        "brand": brand or "",
        "category": category or "",
        "limit": max(1, min(80, int(limit or 30))),
    }
    q = urllib.parse.urlencode({k: v for k, v in params.items() if str(v).strip() != ""})
    headers = {
        "Authorization": f"Bearer {bearer}",
        "Accept": "application/json",
    }
    if app_id:
        headers["X-Application-Id"] = app_id

    def _request_products(access_token: str):
        headers["Authorization"] = f"Bearer {access_token}"
        req = urllib.request.Request(
            f"{RAKUTEN_API_BASE.rstrip('/')}/products?{q}",
            headers=headers,
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=25) as resp:
            return json.loads(resp.read().decode("utf-8") or "{}")

    try:
        payload = _request_products(bearer)
        return _extract_partner_products(payload), None
    except urllib.error.HTTPError as e:
        # Access tokens are short-lived; one forced refresh before hard-fail.
        if e.code in (401, 403):
            refreshed, refresh_err = get_rakuten_access_token(force_refresh=True)
            if refresh_err:
                return [], refresh_err
            try:
                payload = _request_products(refreshed)
                return _extract_partner_products(payload), None
            except Exception as retry_err:
                return [], str(retry_err)
        try:
            detail = e.read().decode("utf-8")
        except Exception:
            detail = str(e)
        return [], f"rakuten_products_http_{e.code}:{detail[:260]}"
    except Exception as e:
        return [], str(e)


def fetch_cj_products(query: str, brand: str, category: str, limit: int = 30):
    dev_key = os.environ.get("CJ_DEVELOPER_KEY", "").strip()
    website_id = os.environ.get("CJ_WEBSITE_ID", "").strip()
    if not dev_key:
        return [], "missing_cj_credentials"
    params = {
        "keywords": query or "",
        "advertiser-name": brand or "",
        "serviceable-area": "IN",
        "records-per-page": max(1, min(80, int(limit or 30))),
    }
    if category:
        params["cat"] = category
    q = urllib.parse.urlencode({k: v for k, v in params.items() if str(v).strip() != ""})
    req = urllib.request.Request(
        f"{CJ_API_BASE.rstrip('/')}/v2/product-search?{q}",
        headers={
            "Authorization": dev_key,
            "x-cj-website-id": website_id,
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            payload = json.loads(resp.read().decode("utf-8") or "{}")
        return _extract_partner_products(payload), None
    except Exception as e:
        return [], str(e)


def normalize_partner_product(raw: dict, network: str, fallback_brand: str, fallback_category: str) -> dict:
    title = str(_first_non_empty(raw, ["title", "productName", "name", "product_name"], "")).strip()
    price_raw = _first_non_empty(raw, ["price", "salePrice", "priceValue", "current_price", "amount"], "")
    try:
        price = float(str(price_raw).replace(",", "").replace("₹", "").strip()) if str(price_raw).strip() else 0.0
    except Exception:
        price = 0.0
    return {
        "network": network.lower(),
        "external_product_id": str(_first_non_empty(raw, ["id", "sku", "productId", "product_id", "pid"], "")),
        "title": title,
        "brand": str(_first_non_empty(raw, ["brand", "brandName", "advertiser-name"], fallback_brand or "")).strip(),
        "category": str(_first_non_empty(raw, ["category", "productType", "type", "cat"], fallback_category or "")).strip().lower(),
        "price": price,
        "currency": str(_first_non_empty(raw, ["currency", "currencyCode"], "INR")).upper(),
        "image_url": str(_first_non_empty(raw, ["imageUrl", "image_url", "image", "imageLink", "image-link"], "")).strip(),
        "flat_lay_url": str(_first_non_empty(raw, ["flat_lay_url", "flatLayUrl", "product_image", "imageUrl", "image_url", "image"], "")).strip(),
        "checkout_url": str(_first_non_empty(raw, ["checkout_url", "checkoutUrl", "deepLink", "deeplink", "affiliate_url", "affiliateLink", "link", "buyUrl", "buy_url", "url"], "")).strip(),
        "affiliate_url": str(_first_non_empty(raw, ["affiliate_url", "affiliateLink", "link", "buyUrl", "buy_url", "url"], "")).strip(),
        "description": str(_first_non_empty(raw, ["description", "shortDescription"], "")).strip(),
    }


def ingest_partner_feed(client: "OpenAI", network: str, query: str, brand: str, category: str, limit: int = 30, dry_run: bool = False):
    net = (network or "").strip().lower()
    if net not in {"rakuten", "cj"}:
        return {"success": False, "error": "network must be 'rakuten' or 'cj'"}

    if net == "rakuten":
        raw_items, err = fetch_rakuten_products(query=query, brand=brand, category=category, limit=limit)
    else:
        raw_items, err = fetch_cj_products(query=query, brand=brand, category=category, limit=limit)
    if err:
        return {"success": False, "error": f"fetch_failed:{err}"}

    scanned = 0
    approved = 0
    rejected = 0
    upsert_rows = []
    samples = []
    for item in raw_items:
        scanned += 1
        p = normalize_partner_product(item, net, brand, category)
        if not p["title"] or not p["image_url"] or not (p["checkout_url"] or p["affiliate_url"]):
            rejected += 1
            continue
        quality = classify_affiliate_image(p["image_url"])
        if not quality.get("approved"):
            rejected += 1
            continue
        approved += 1
        emb_text = f"{p['title']} | {p['brand']} | {p['category']} | {p['description']}"
        emb = get_text_embedding(client, emb_text)
        row = {
            "network": p["network"],
            "external_product_id": p["external_product_id"] or f"{net}_{approved}_{int(time.time())}",
            "title": p["title"],
            "brand": p["brand"] or "",
            "category": p["category"] or "",
            "price": p["price"],
            "currency": p["currency"] or "INR",
            "image_url": p["image_url"],
            "flat_lay_url": p["flat_lay_url"] or p["image_url"],
            "checkout_url": p["checkout_url"] or p["affiliate_url"],
            "affiliate_url": p["affiliate_url"] or p["checkout_url"],
            "description": p["description"] or "",
            "embedding": emb,
            "quality_score": float(quality.get("quality_score", 0.0)),
            "is_clean": True,
            "filter_reason": str(quality.get("reason", "approved")),
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        upsert_rows.append(row)
        if len(samples) < 5:
            samples.append({
                "title": row["title"],
                "checkout_url": row["checkout_url"],
                "affiliate_url": row["affiliate_url"],
                "flat_lay_url": row["flat_lay_url"],
            })

    write_result = {"inserted": 0}
    write_err = None
    if not dry_run:
        write_result, write_err = sb_upsert_global_inventory(upsert_rows)

    return {
        "success": write_err is None,
        "network": net,
        "query": query,
        "brand": brand,
        "category": category,
        "scanned": scanned,
        "approved": approved,
        "rejected": rejected,
        "inserted": int((write_result or {}).get("inserted", 0)),
        "samples": samples,
        "error": write_err,
    }


def search_global_inventory(client: "OpenAI", style_query: str, category: str = "", limit: int = 6):
    emb = get_text_embedding(client, style_query)
    if not emb:
        return {"success": False, "error": "embedding_failed", "matches": []}

    rows, err = sb_match_global_inventory(query_embedding=emb, category=category, limit=limit)
    if err:
        rows, fallback_err = sb_fallback_similarity_search(query_embedding=emb, category=category, limit=limit)
        if fallback_err:
            return {"success": False, "error": f"{err}; fallback:{fallback_err}", "matches": []}

    matches = []
    for r in rows[: max(1, min(20, int(limit or 6)))]:
        matches.append({
            "id": r.get("id"),
            "network": r.get("network", "").upper(),
            "title": r.get("title"),
            "brand": r.get("brand"),
            "category": r.get("category"),
            "price": r.get("price"),
            "currency": r.get("currency", "INR"),
            "image_url": r.get("image_url"),
            "flat_lay_url": r.get("flat_lay_url") or r.get("image_url"),
            "checkout_url": r.get("checkout_url") or r.get("affiliate_url"),
            "affiliate_url": r.get("affiliate_url"),
            "similarity": float(r.get("similarity", 0.0) or 0.0),
            "quality_score": float(r.get("quality_score", 0.0) or 0.0),
        })
    return {"success": True, "matches": matches, "embedding_size": len(emb)}


# ============================================================================
#  SECTION 1: OPENAI + REPLICATE FUNCTIONS
#  Uses GPT-4o for fashion recommendations + Replicate FLUX for images
# ============================================================================

def infer_biometrics_from_input(skin_tone_label: str, body_shape: str, gender: str) -> dict:
    """
    Infer biometric data from user-selected inputs instead of AWS Rekognition.
    This is faster, cheaper, and more reliable than running ML models.
    """
    mst_value = SKIN_TONE_TO_MST.get(skin_tone_label, 5)
    gender_presentation = GENDER_MAP.get(gender, gender or "person")
    body_type = BODY_SHAPE_MAP.get(body_shape, "medium build")

    return {
        "face_detected": True,
        "monk_skin_tone": mst_value,
        "mst_label": MST_LABELS.get(mst_value, "Medium"),
        "body_type": body_shape.replace("_", " ") if body_shape else "average",
        "gender_presentation": gender_presentation,
        "confidence": 0.95,  # User-selected, so high confidence
    }


def generate_fashion_recommendation(client: 'OpenAI', biometrics: dict, occasion: str, vibe_id: str) -> dict:
    """
    Use GPT-4o to generate a complete fashion recommendation including
    outfit description, color palette, and styling tips.
    """
    mst_value = biometrics.get("monk_skin_tone", 5)
    mst_label = biometrics.get("mst_label", "Medium")
    body_type = biometrics.get("body_type", "average")
    gender = biometrics.get("gender_presentation", "person")
    body_description = BODY_SHAPE_MAP.get(body_type, body_type)

    vibe = VIBE_PRESETS.get(vibe_id, VIBE_PRESETS["caffeine_survivor"])
    occ = OCCASION_PRESETS.get(occasion, OCCASION_PRESETS["date_night"])

    color_data = MST_COLOR_THEORY.get(mst_value, MST_COLOR_THEORY[5])
    best_colors = ", ".join(color_data.get("best_colors", ["neutral tones"]))

    prompt = f"""You are the AI Fashion Consultant at MY NARRATIVE — a psychology-first styling engine.

USER PROFILE:
- Skin Tone: {mst_label} (Monk Scale {mst_value}/10)
- Body Type: {body_description}
- Gender: {gender}
- Occasion: {occ['label']}
- Vibe: {vibe['label']} — {vibe['style_persona']}

COLOR SCIENCE: Best colors for their skin tone: {best_colors}

Generate a complete outfit recommendation as JSON with these fields:
{{
  "outfit_description": "A vivid 2-3 sentence description of the complete look",
  "top": {{"name": "item name", "color": "color name", "hex": "#hexcode", "fabric": "fabric type"}},
  "bottom": {{"name": "item name", "color": "color name", "hex": "#hexcode", "fabric": "fabric type"}},
  "footwear": {{"name": "item name", "color": "color name", "hex": "#hexcode"}},
  "accessory": {{"name": "item name", "color": "color name", "hex": "#hexcode"}},
  "styling_tips": ["tip 1", "tip 2", "tip 3"],
  "color_science_note": "Why these colors work for this skin tone"
}}"""

    try:
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a fashion consultant AI. Always respond with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.85,
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        print(f"⚠️  [generate_fashion_recommendation] GPT-4o error: {e}")
        return {
            "outfit_description": f"A {vibe['style_persona']} look perfect for {occ['label']}.",
            "top": {"name": "Structured Blazer", "color": color_data["best_colors"][0], "hex": "#2C3E50", "fabric": "cotton blend"},
            "bottom": {"name": "Slim Fit Trousers", "color": "Charcoal", "hex": "#36454F", "fabric": "stretch wool"},
            "footwear": {"name": "Clean White Sneakers", "color": "White", "hex": "#FFFFFF"},
            "accessory": {"name": "Minimalist Watch", "color": "Silver", "hex": "#C0C0C0"},
            "styling_tips": ["Keep accessories minimal", "Confidence is the best accessory", "Fit matters more than brand"],
            "color_science_note": color_data["undertone_note"],
        }


def generate_flux_image(biometrics: dict, occasion: str, vibe_id: str, recommendation: dict = None) -> str:
    """
    Use Replicate FLUX to generate a fashion editorial image.
    Falls back to a placeholder if REPLICATE_API_TOKEN is not set.
    """
    token = os.environ.get("REPLICATE_API_TOKEN")

    mst_label = biometrics.get("mst_label", "Medium")
    body_type = biometrics.get("body_type", "average")
    gender = biometrics.get("gender_presentation", "person")

    vibe = VIBE_PRESETS.get(vibe_id, VIBE_PRESETS["caffeine_survivor"])
    occ = OCCASION_PRESETS.get(occasion, OCCASION_PRESETS["date_night"])

    body_description = BODY_SHAPE_MAP.get(body_type, body_type)

    # Build a focused FLUX prompt — include outfit details from GPT-4o recommendation
    outfit_desc = ""
    if recommendation:
        top_name = recommendation.get("top", {}).get("name", "")
        bottom_name = recommendation.get("bottom", {}).get("name", "")
        if top_name or bottom_name:
            outfit_desc = f"Wearing: {top_name} and {bottom_name}. "

    color_data = MST_COLOR_THEORY.get(biometrics.get("monk_skin_tone", 5), MST_COLOR_THEORY[5])
    best_colors = ", ".join(color_data.get("best_colors", ["neutral tones"]))

    prompt = (
        f"High-end fashion editorial full-body photograph of an Indian {gender} "
        f"with {mst_label} skin tone and {body_description}. "
        f"{outfit_desc}"
        f"Style aesthetic: {vibe['flux_modifier']}. "
        f"Setting: {occ['flux_context']}. "
        f"Natural lighting with cinematic touch, 4K ultra resolution, "
        f"texture-rich fabrics, realistic skin texture with natural pores, "
        f"fashion magazine editorial quality. "
        f"Full body shot from head to toe, clearly visible, facing camera directly, "
        f"no cropping, clean studio background with subtle gradient."
    )

    if token and REPLICATE_AVAILABLE:
        try:
            client = replicate.Client(api_token=token)
            print(f"🖼️  [generate_flux_image] Calling FLUX API...")

            output = client.run(
                "black-forest-labs/flux-schnell",
                input={
                    "prompt": prompt,
                    "aspect_ratio": "3:4",
                    "num_inference_steps": 4,
                    "output_format": "webp",
                    "output_quality": 90,
                },
            )
            image_url = str(output[0]) if output else None

            if image_url:
                print(f"✅ [generate_flux_image] Image generated: {image_url[:80]}...")
                return image_url
            else:
                raise Exception("FLUX returned empty output")

        except Exception as e:
            print(f"❌ [generate_flux_image] FLUX API error: {e}")
            # Fallback to placeholder
            return "https://placehold.co/768x1024/1a1a2e/e94560?text=FLUX+Generated+Image"

    # ─── FALLBACK (no Replicate token) ───
    print("⚠️  [generate_flux_image] Using MOCK image — connect REPLICATE_API_TOKEN for production")
    return "https://placehold.co/768x1024/1a1a2e/e94560?text=FLUX+Generated+Image"


def get_gamification_state(user_id: str) -> dict:
    """Returns mock gamification state — same as before."""
    return {
        "mascot_quest": {
            "cards_collected": 1,
            "cards_total": 5,
            "current_card": {
                "name": "The Street Style Phantom",
                "rarity": "Common",
                "unlock_method": "Complete your first AI editorial",
            },
            "next_card": {
                "name": "The Boardroom Shapeshifter",
                "rarity": "Rare",
                "unlock_method": "Checkout any recommended item",
            },
            "checkout_cta": "Checkout to unlock your next physical Mascot Card!",
        },
        "style_graph": {
            "photos_uploaded": 1,
            "photos_required": 4,
            "progress_pct": 25,
            "reward_unlocked": False,
            "reward_description": "Upload 3 more OOTD photos to train your AI and unlock 5% Store Credit",
            "credit_amount": "5%",
            "credit_type": "Store Credit",
        },
    }


def _product_type_from_title(title: str) -> str:
    t = (title or "").lower()
    if "jacket" in t:
        return "jacket"
    if "hoodie" in t:
        return "hoodie"
    return "tshirt"


def _fallback_my_narrative_selection(occasion: str, vibe_id: str) -> list:
    occ = (occasion or "").lower()
    vibe = (vibe_id or "").lower()
    picks = []
    if "sangeet" in occ:
        picks = [MY_NARRATIVE_CATALOG[0], MY_NARRATIVE_CATALOG[3]]
    elif "airport" in occ or "office" in occ:
        picks = [MY_NARRATIVE_CATALOG[1], MY_NARRATIVE_CATALOG[4]]
    elif "gym" in occ or "caffeine" in vibe:
        picks = [MY_NARRATIVE_CATALOG[2], MY_NARRATIVE_CATALOG[1]]
    else:
        picks = [MY_NARRATIVE_CATALOG[2], MY_NARRATIVE_CATALOG[5]]
    return picks


def generate_my_narrative_recommendation(client: 'OpenAI', biometrics: dict, occasion: str, vibe_id: str) -> dict:
    catalog_lines = "\n".join([
        f"- {p['handle']} | {p['title']} | ₹{p['price']} | {p['product_url']}"
        for p in MY_NARRATIVE_CATALOG
    ])
    prompt = f"""You are MY NARRATIVE's brand stylist. ONLY recommend from this exact catalog.

CATALOG:
{catalog_lines}

USER:
- Skin Tone: {biometrics.get('mst_label', 'Medium')}
- Body Type: {biometrics.get('body_type', 'average')}
- Gender: {biometrics.get('gender_presentation', 'person')}
- Occasion: {occasion}
- Vibe: {vibe_id}

Return STRICT JSON:
{{
  "direction": "1-2 sentence styling direction",
  "styling_tips": ["tip1", "tip2", "tip3"],
  "selected_handles": ["handle1", "handle2"]
}}
Rules:
- selected_handles MUST be from catalog handles only.
- Prefer one primary hero product and one alternate.
- Keep tips concise and practical.
"""
    selected = []
    direction = "Curated from My Narrative exclusive drops."
    tips = [
        "Keep the upper silhouette clean so the slogan stays legible.",
        "Pair with neutral bottoms for stronger visual focus.",
        "Use one statement layer only to avoid clutter."
    ]
    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Return valid JSON only."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.6,
        )
        data = json.loads(completion.choices[0].message.content)
        direction = data.get("direction") or direction
        tips = data.get("styling_tips") or tips
        selected = data.get("selected_handles") or []
    except Exception as e:
        print(f"⚠️ [my_narrative] GPT fallback: {e}")

    by_handle = {p["handle"]: p for p in MY_NARRATIVE_CATALOG}
    selected_products = [by_handle[h] for h in selected if h in by_handle][:2]
    if not selected_products:
        selected_products = _fallback_my_narrative_selection(occasion, vibe_id)

    outfit_pieces = []
    slot_map = ["top", "outerwear"]
    for idx, p in enumerate(selected_products):
        ptype = _product_type_from_title(p["title"])
        outfit_pieces.append({
            "slot": slot_map[idx] if idx < len(slot_map) else "top",
            "name": p["title"],
            "type": ptype,
            "color": "#39A596",
            "owned": False,
            "why": "Selected from My Narrative catalog to match your occasion and vibe.",
            "shop_links": [{
                "platform": "MY NARRATIVE",
                "url": p["product_url"],
                "add_to_cart_url": p["product_url"],
                "product_url": p["product_url"],
                "exact_product_url": p["product_url"],
                "price": f"₹{p['price']}",
                "handle": p["handle"],
                "flat_lay_url": p["flat_lay_url"],
            }],
            "my_narrative_product": {
                "handle": p["handle"],
                "title": p["title"],
                "price": p["price"],
                "product_url": p["product_url"],
                "flat_lay_url": p["flat_lay_url"],
            }
        })

    return {
        "direction": direction,
        "styling_tips": tips[:3],
        "suggestions": tips[:3],
        "outfit_pieces": outfit_pieces,
        "selected_products": selected_products,
        "color_science_note": MST_COLOR_THEORY.get(
            biometrics.get("monk_skin_tone", 5), MST_COLOR_THEORY[5]
        ).get("undertone_note", ""),
    }


def run_idm_vton(user_image: str, garment_image: str, description: str) -> str:
    token = os.environ.get("REPLICATE_API_TOKEN")
    if not token or not REPLICATE_AVAILABLE:
        return ""
    if not user_image or not garment_image:
        return ""
    try:
        client = replicate.Client(api_token=token)
        try:
            model = client.models.get("cuuupid/idm-vton")
            version_id = model.latest_version.id
        except Exception:
            version_id = "c871bb9b046607b680449ecbae55fd8c6d945e0a1948644bf2361b3d021d3ff4"

        output = client.run(
            f"cuuupid/idm-vton:{version_id}",
            input={
                "human_img": user_image,
                "garm_img": garment_image,
                "garment_des": description or "streetwear top",
                "category": "upper_body",
                "crop": False,
                "seed": 42,
                "steps": 30,
                "force_dc": False,
                "mask_only": False
            }
        )
        return str(output) if output else ""
    except Exception as e:
        print(f"⚠️ [run_idm_vton] {e}")
        return ""


def normalize_replicate_image_ref(image_value: str) -> str:
    """
    Replicate accepts URL or data URI. Frontend may send raw base64.
    Normalize raw base64 into data URI for better model compatibility.
    """
    v = (image_value or "").strip()
    if not v:
        return ""
    lowered = v.lower()
    if lowered.startswith("http://") or lowered.startswith("https://") or lowered.startswith("data:image/"):
        return v
    # Raw base64 fallback
    return "data:image/jpeg;base64," + v


def maybe_face_swap(base_image_url: str, user_image: str) -> str:
    token = os.environ.get("REPLICATE_API_TOKEN")
    if not token or not REPLICATE_AVAILABLE:
        return base_image_url
    if not user_image:
        return base_image_url
    try:
        client = replicate.Client(api_token=token)
        output = client.run(
            "lucataco/faceswap:9a4298548422074c3f57258c5d544497314ae4112df80d116f0d2109bd068e9c",
            input={"target_image": base_image_url, "swap_image": user_image}
        )
        return str(output) if output else base_image_url
    except Exception as e:
        print(f"⚠️ [maybe_face_swap] {e}")
        return base_image_url


def build_global_outfit_pieces(recommendation: dict, affiliate_recommendations: list) -> list:
    rec = recommendation or {}
    links = []
    for item in affiliate_recommendations[:3]:
        links.append({
            "platform": item.get("platform", "Shop"),
            "url": item.get("affiliate_url", ""),
            "affiliate_url": item.get("affiliate_url", ""),
            "price": f"₹{item.get('price')}" if item.get("price") else "",
        })
    return [
        {
            "slot": "top",
            "name": (rec.get("top", {}) or {}).get("name", "Styled Top"),
            "type": "top",
            "color": (rec.get("top", {}) or {}).get("hex", "#39A596"),
            "owned": False,
            "why": "Matched to your tone, body profile and selected vibe.",
            "shop_links": links[:1],
        },
        {
            "slot": "bottom",
            "name": (rec.get("bottom", {}) or {}).get("name", "Styled Bottom"),
            "type": "bottom",
            "color": (rec.get("bottom", {}) or {}).get("hex", "#5f6368"),
            "owned": False,
            "why": "Balanced silhouette for a complete look.",
            "shop_links": links[1:2],
        },
        {
            "slot": "footwear",
            "name": (rec.get("footwear", {}) or {}).get("name", "Footwear"),
            "type": "footwear",
            "color": (rec.get("footwear", {}) or {}).get("hex", "#ffffff"),
            "owned": False,
            "why": "Completes the outfit with contrast and structure.",
            "shop_links": links[2:3] or links[:1],
        },
    ]


def build_style_query_from_recommendation(recommendation: dict, occasion: str, vibe_label: str) -> str:
    rec = recommendation or {}
    top = (rec.get("top", {}) or {}).get("name", "")
    bottom = (rec.get("bottom", {}) or {}).get("name", "")
    footwear = (rec.get("footwear", {}) or {}).get("name", "")
    color = (rec.get("top", {}) or {}).get("color", "")
    parts = [top, bottom, footwear, color, occasion.replace("_", " "), vibe_label]
    return " | ".join([p for p in parts if str(p).strip()])


def generate_global_style_query(client: "OpenAI", biometrics: dict, occasion: str, vibe_id: str, user_image: str = "") -> dict:
    default_query = f"{biometrics.get('gender_presentation', 'person')} {occasion.replace('_', ' ')} {VIBE_PRESETS.get(vibe_id, {}).get('label', 'streetwear')} jacket"
    default_category = "jacket"
    prompt = f"""You are a senior fashion retrieval model for affiliate inventory search.
Create ONE highly specific product retrieval query for a single upper-body garment.

User profile:
- Skin tone: {biometrics.get('mst_label', 'Medium')}
- Body shape: {biometrics.get('body_type', 'average')}
- Gender presentation: {biometrics.get('gender_presentation', 'person')}
- Occasion: {occasion}
- Vibe: {vibe_id}
- Selfie provided: {"yes" if user_image else "no"}

Return strict JSON:
{{
  "style_query": "e.g. Men's oversized vintage brown leather jacket",
  "category": "jacket|hoodie|tshirt|shirt|sweatshirt"
}}
Rules:
- Keep style_query under 14 words.
- Query should be purchase-ready (material, fit, tone).
- Focus on one garment that is ideal for VTON upper-body try-on.
"""
    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Return valid JSON only."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.35,
        )
        data = json.loads(completion.choices[0].message.content)
        q = str(data.get("style_query", "")).strip() or default_query
        cat = str(data.get("category", "")).strip().lower() or default_category
        return {"style_query": q, "category": cat}
    except Exception as e:
        print(f"⚠️ [generate_global_style_query] {e}")
        return {"style_query": default_query, "category": default_category}


def _run_path_a_global(client: "OpenAI", biometrics: dict, occasion: str, vibe_id: str, user_image: str):
    """
    Vector-first global market runtime:
    1) GPT style query
    2) Supabase vector search
    3) IDM-VTON with winning flat-lay
    4) Fallback to FLUX if retrieval path fails
    """
    vibe_label = VIBE_PRESETS.get(vibe_id, {}).get("label", "stylish look")
    occasion_key = occasion.replace("_", " ")

    recommendation = {}
    try:
        recommendation = generate_fashion_recommendation(
            client=client,
            biometrics=biometrics,
            occasion=occasion,
            vibe_id=vibe_id,
        )
    except Exception as e:
        print(f"⚠️ [global] recommendation fallback: {e}")
        recommendation = {}

    query_obj = generate_global_style_query(
        client=client,
        biometrics=biometrics,
        occasion=occasion,
        vibe_id=vibe_id,
        user_image=user_image,
    )
    style_query = query_obj.get("style_query", "")
    query_category = query_obj.get("category", "")
    inventory_result = search_global_inventory(
        client=client,
        style_query=style_query,
        category=query_category,
        limit=6,
    )
    matches = inventory_result.get("matches", []) if inventory_result.get("success") else []

    affiliate_recommendations = []
    outfit_pieces = []
    final_image_url = ""
    flux_image_url = ""
    selected_match = None
    vton_applied = False

    if matches:
        for m in matches[:3]:
            checkout_url = m.get("checkout_url") or m.get("affiliate_url") or ""
            affiliate_recommendations.append({
                "product_name": m.get("title"),
                "brand": m.get("brand") or m.get("network"),
                "price": m.get("price"),
                "currency": m.get("currency", "INR"),
                "affiliate_url": checkout_url,
                "checkout_url": checkout_url,
                "exact_product_url": checkout_url,
                "product_url": checkout_url,
                "flat_lay_url": m.get("flat_lay_url") or m.get("image_url"),
                "image_url": m.get("image_url"),
                "platform": m.get("network", "GLOBAL"),
                "recommended_for": f"{vibe_label} {occasion_key} look",
                "gap_item": {"description": m.get("title"), "is_owned": False},
                "similarity": m.get("similarity", 0.0),
            })
        selected_match = matches[0]
        final_image_url = run_idm_vton(
            user_image=user_image,
            garment_image=selected_match.get("flat_lay_url") or selected_match.get("image_url") or "",
            description=selected_match.get("title", "global product"),
        )
        vton_applied = bool(final_image_url)
        if not final_image_url:
            print("🚨 [SEVERE] Global vector match found but IDM-VTON failed. Falling back to FLUX.")
    else:
        print("🚨 [SEVERE] Global vector inventory empty or retrieval failed. Falling back to FLUX.")

    if not final_image_url:
        try:
            flux_image_url = generate_flux_image(
                biometrics=biometrics,
                occasion=occasion,
                vibe_id=vibe_id,
                recommendation=recommendation,
            )
        except Exception as e:
            print(f"⚠️ [global] FLUX fallback failed: {e}")
            flux_image_url = "https://placehold.co/768x1024/1a1a2e/e94560?text=AI+Styled+Look"
        final_image_url = maybe_face_swap(flux_image_url, user_image)

    outfit_pieces = build_global_outfit_pieces(recommendation, affiliate_recommendations)
    return {
        "recommendation": recommendation,
        "affiliate_recommendations": affiliate_recommendations,
        "outfit_pieces": outfit_pieces,
        "final_image_url": final_image_url,
        "flux_image_url": flux_image_url,
        "style_query": style_query,
        "vector_category": query_category,
        "vector_top_match": selected_match,
        "vton_applied": vton_applied,
    }


# ============================================================================
#  SECTION 2: MAIN REQUEST HANDLER (Vercel Serverless Function)
# ============================================================================

class handler(BaseHTTPRequestHandler):
    """
    POST /api/stylist_pipeline
    ──────────────────────────
    Orchestrates the AI Stylist pipeline using OpenAI only.

    Request Body:
    {
        "action": "full_pipeline" | "get_vibes" | "get_occasions" | "get_gamification",
        "user_id": "shopify_customer_id",
        "occasion": "date_night" | "office" | "sangeet" | "airport_look" | ...,
        "vibe_id": "caffeine_survivor" | "sarcastic_rizzler" | "main_character" | "quiet_luxury",
        "user_image": "base64_encoded_image_string",
        "skin_tone": "Fair" | "Medium" | "Olive" | "Brown" | "Dark" | "Deep",
        "body_shape": "slim_athletic" | "average" | "muscular" | "plus_size" | "tall_lean" | "short_stocky",
        "gender": "men" | "women"
    }
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

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(200)
        self._cors_headers()
        self.end_headers()

    def do_GET(self):
        """Health check and metadata endpoint."""
        self._respond(200, {
            "service": "My Narrative AI Stylist Pipeline",
            "version": "3.0.0",
            "status": "operational",
            "engine": "OpenAI GPT-4o + Replicate FLUX",
            "available_vibes": list(VIBE_PRESETS.keys()),
            "available_occasions": list(OCCASION_PRESETS.keys()),
        })

    def do_POST(self):
        """
        Main pipeline orchestrator — OpenAI only, fast and reliable.
        """
        # ─── PARSE REQUEST ───
        content_length = int(self.headers.get("Content-Length", 0))

        # Check for oversized payload (Vercel Hobby plan limit: 4.5 MB)
        MAX_BODY_SIZE = 4.5 * 1024 * 1024
        if content_length > MAX_BODY_SIZE:
            self._respond(413, {
                "success": False,
                "error": "Payload too large. Image size exceeds 4.5 MB limit. Please use a smaller image.",
            })
            return

        body = b''
        if content_length > 0:
            body = self.rfile.read(content_length)

        if not body:
            self._respond(400, {
                "success": False,
                "error": "Empty request body. Please provide valid JSON data.",
            })
            return

        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            self._respond(400, {"success": False, "error": "Invalid JSON in request body"})
            return

        action = body.get("action", "full_pipeline")

        # ─── ACTION: Return available vibes ───
        if action == "get_vibes":
            vibes = []
            for vid, vdata in VIBE_PRESETS.items():
                vibes.append({"id": vid, "label": vdata["label"], "persona": vdata["style_persona"]})
            self._respond(200, {"success": True, "vibes": vibes})
            return

        # ─── ACTION: Return available occasions ───
        if action == "get_occasions":
            occasions = []
            for oid, odata in OCCASION_PRESETS.items():
                occasions.append({"id": oid, "label": odata["label"], "direction": odata["style_direction"]})
            self._respond(200, {"success": True, "occasions": occasions})
            return

        # ─── ACTION: Return gamification state ───
        if action == "get_gamification":
            user_id = body.get("user_id", "anonymous")
            gamification = get_gamification_state(user_id)
            self._respond(200, {"success": True, "gamification": gamification})
            return

        # ─── ACTION: Ingest partner affiliate feed into global_inventory ───
        if action == "ingest_affiliate_feed":
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                self._respond(500, {"success": False, "error": "OPENAI_API_KEY not configured"})
                return
            if not sb_configured():
                self._respond(500, {"success": False, "error": "Supabase not configured (SUPABASE_URL/SUPABASE_KEY)"})
                return
            client = OpenAI(api_key=api_key)
            result = ingest_partner_feed(
                client=client,
                network=body.get("network", ""),
                query=body.get("query", ""),
                brand=body.get("brand", ""),
                category=body.get("category", ""),
                limit=body.get("limit", 30),
                dry_run=bool(body.get("dry_run", False)),
            )
            self._respond(200 if result.get("success") else 400, result)
            return

        # ─── ACTION: Semantic search over curated global inventory ───
        if action == "search_global_inventory":
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                self._respond(500, {"success": False, "error": "OPENAI_API_KEY not configured"})
                return
            client = OpenAI(api_key=api_key)
            result = search_global_inventory(
                client=client,
                style_query=body.get("style_query", ""),
                category=body.get("category", ""),
                limit=body.get("limit", 6),
            )
            self._respond(200 if result.get("success") else 400, result)
            return

        # ─── ACTION: FULL PIPELINE ───
        if action == "full_pipeline":
            pipeline_start = time.time()

            # Validate required fields (user_image is optional now — we use skin_tone/body_shape instead)
            user_id = body.get("user_id")
            occasion = body.get("occasion")
            vibe_id = body.get("vibe_id")
            skin_tone = body.get("skin_tone", "Medium")
            body_shape = body.get("body_shape", "average")
            gender = body.get("gender", "men")
            source_preference = (body.get("source_preference") or body.get("sourcePreference") or "global_market").strip().lower()
            if source_preference not in ("global_market", "my_narrative"):
                source_preference = "global_market"

            # Support both new fields and legacy user_image
            user_image = body.get("user_image_data_url") or body.get("user_image")
            user_image = normalize_replicate_image_ref(user_image or "")

            print(f"📥 Request: user_id={user_id}, occasion={occasion}, vibe_id={vibe_id}, "
                  f"skin_tone={skin_tone}, body_shape={body_shape}, gender={gender}, "
                  f"source={source_preference}, image_size={len(user_image) if user_image else 0}")

            if not all([user_id, occasion, vibe_id]):
                self._respond(400, {
                    "success": False,
                    "error": "Missing required fields: user_id, occasion, vibe_id",
                    "required": ["user_id", "occasion", "vibe_id"],
                })
                return

            # ─── AUTH CHECK ───
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                self._respond(500, {
                    "success": False,
                    "error": "Server configuration error: OPENAI_API_KEY not set. Please configure in Vercel Dashboard.",
                })
                return

            client = OpenAI(api_key=api_key)

            # ═══════════════════════════════════════════════════════
            # STEP 1: Infer biometrics from user input (instant, no API call)
            # ═══════════════════════════════════════════════════════
            print("━" * 60)
            print("🚀 STEP 1: Inferring biometrics from user selections...")
            biometrics_result = infer_biometrics_from_input(skin_tone, body_shape, gender)

            print(f"✅ Biometrics inferred: MST={biometrics_result.get('monk_skin_tone')}, "
                  f"Gender={biometrics_result.get('gender_presentation')}, "
                  f"Body={biometrics_result.get('body_type')}")

            mst_value = biometrics_result.get("monk_skin_tone", 5)
            color_theory = MST_COLOR_THEORY.get(mst_value, MST_COLOR_THEORY[5])
            vibe_label = VIBE_PRESETS.get(vibe_id, {}).get("label", "stylish look")
            occasion_key = occasion.replace("_", " ")

            recommendation = None
            outfit_pieces = []
            affiliate_recommendations = []
            flux_image_url = ""
            final_image_url = ""
            source_mode = source_preference
            vton_product = None
            global_style_query = ""
            global_query_category = ""
            vton_applied = False

            # ═══════════════════════════════════════════════════════
            # PATH A: GLOBAL MARKET (FLUX + optional face swap + affiliates)
            # ═══════════════════════════════════════════════════════
            if source_preference == "global_market":
                print("\n🌍 PATH A: GLOBAL MARKET")
                path_a = _run_path_a_global(
                    client=client,
                    biometrics=biometrics_result,
                    occasion=occasion,
                    vibe_id=vibe_id,
                    user_image=user_image,
                )
                recommendation = path_a.get("recommendation", {}) or {}
                affiliate_recommendations = path_a.get("affiliate_recommendations", []) or []
                outfit_pieces = path_a.get("outfit_pieces", []) or []
                final_image_url = path_a.get("final_image_url", "") or ""
                flux_image_url = path_a.get("flux_image_url", "") or ""
                vton_product = path_a.get("vector_top_match")
                global_style_query = path_a.get("style_query", "") or ""
                global_query_category = path_a.get("vector_category", "") or ""
                vton_applied = bool(path_a.get("vton_applied", False))

            # ═══════════════════════════════════════════════════════
            # PATH B: MY NARRATIVE (Catalog match + IDM VTON)
            # ═══════════════════════════════════════════════════════
            else:
                print("\n✦ PATH B: MY NARRATIVE")
                recommendation = generate_my_narrative_recommendation(
                    client=client,
                    biometrics=biometrics_result,
                    occasion=occasion,
                    vibe_id=vibe_id,
                )
                outfit_pieces = recommendation.get("outfit_pieces", [])
                selected_products = recommendation.get("selected_products", [])
                if selected_products:
                    vton_product = selected_products[0]
                else:
                    vton_product = _fallback_my_narrative_selection(occasion, vibe_id)[0]

                # Primary output image must be VTON try-on for My Narrative path.
                vton_img = run_idm_vton(
                    user_image=user_image,
                    garment_image=vton_product.get("flat_lay_url", ""),
                    description=vton_product.get("title", "streetwear top"),
                )
                vton_applied = bool(vton_img)
                final_image_url = vton_img or vton_product.get("flat_lay_url") or "https://placehold.co/768x1024/0b0b0f/39A596?text=MY+NARRATIVE+LOOK"
                flux_image_url = ""

                for p in selected_products[:3]:
                    affiliate_recommendations.append({
                        "product_name": p.get("title"),
                        "brand": "MY NARRATIVE",
                        "price": p.get("price"),
                        "original_price": p.get("price"),
                        "discount_pct": 0,
                        "currency": "INR",
                        "affiliate_url": p.get("product_url"),
                        "add_to_cart_url": p.get("product_url"),
                        "exact_product_url": p.get("product_url"),
                        "product_url": p.get("product_url"),
                        "flat_lay_url": p.get("flat_lay_url"),
                        "platform": "MY NARRATIVE",
                        "recommended_for": f"My Narrative {occasion_key} look",
                        "gap_item": {"description": p.get("title"), "is_owned": False},
                    })

            # ═══════════════════════════════════════════════════════
            # STEP 5: Gamification state (instant)
            # ═══════════════════════════════════════════════════════
            gamification = get_gamification_state(user_id)

            # ═══════════════════════════════════════════════════════
            # ASSEMBLE FINAL RESPONSE
            # ═══════════════════════════════════════════════════════
            pipeline_duration = round(time.time() - pipeline_start, 2)
            print(f"\n{'━' * 60}")
            print(f"✅ PIPELINE COMPLETE in {pipeline_duration}s")
            print(f"{'━' * 60}")

            response = {
                "success": True,
                "pipeline_duration_seconds": pipeline_duration,

                # Biometric data inferred from user selections
                "biometrics": {
                    "monk_skin_tone": mst_value,
                    "mst_label": MST_LABELS.get(mst_value, "Medium"),
                    "body_type": biometrics_result.get("body_type"),
                    "gender_presentation": biometrics_result.get("gender_presentation"),
                    "confidence": biometrics_result.get("confidence"),
                },
                "ghost_closet": {
                    "success": True,
                    "user_id": user_id,
                    "items_saved": 0,
                    "item_ids": [],
                },

                # Wardrobe data (placeholder — would use cloth_detection in production)
                "wardrobe": {
                    "items_detected": 4,
                    "items": [
                        {"id": "wd_1", "slot": "top", "category": "Topwear", "sub_category": recommendation.get("top", {}).get("name", "Stylish Top") if recommendation else "Stylish Top", "color": recommendation.get("top", {}).get("color", "Neutral") if recommendation else "Neutral", "pattern": "solid", "style": "Western", "confidence": 0.95, "description": "AI-recommended top"},
                        {"id": "wd_2", "slot": "bottom", "category": "Bottomwear", "sub_category": recommendation.get("bottom", {}).get("name", "Slim Trousers") if recommendation else "Slim Trousers", "color": recommendation.get("bottom", {}).get("color", "Dark") if recommendation else "Dark", "pattern": "solid", "style": "Western", "confidence": 0.93, "description": "AI-recommended bottoms"},
                        {"id": "wd_3", "slot": "footwear", "category": "Footwear", "sub_category": recommendation.get("footwear", {}).get("name", "Clean Sneakers") if recommendation else "Clean Sneakers", "color": recommendation.get("footwear", {}).get("color", "White") if recommendation else "White", "pattern": "solid", "style": "Western", "confidence": 0.88, "description": "AI-recommended footwear"},
                        {"id": "wd_4", "slot": "accessory", "category": "Accessory", "sub_category": recommendation.get("accessory", {}).get("name", "Watch") if recommendation else "Watch", "color": recommendation.get("accessory", {}).get("color", "Silver") if recommendation else "Silver", "pattern": "solid", "style": "Western", "confidence": 0.78, "description": "AI-recommended accessory"},
                    ],
                },

                # Generated editorial image
                "editorial": {
                    "flux_prompt": f"AI-styled {vibe_label} look for {occasion_key}",
                    "flux_image_url": flux_image_url,
                    "final_image_url": final_image_url,
                    "vton_image_url": final_image_url if source_mode == "my_narrative" else "",
                    "vton_applied": vton_applied,
                    "occasion": OCCASION_PRESETS.get(occasion, {}),
                    "vibe": VIBE_PRESETS.get(vibe_id, {}),
                    "source_mode": source_mode,
                },

                # Color theory + Affiliate recommendations
                "color_theory": {
                    "mst_value": mst_value,
                    "best_colors": color_theory["best_colors"],
                    "avoid_colors": color_theory["avoid"],
                    "undertone_note": color_theory["undertone_note"],
                    "tooltip_text": (
                        f"Based on your Monk Skin Tone ({MST_LABELS.get(mst_value)}), "
                        f"{color_theory['undertone_note']} "
                        f"Best colors: {', '.join(color_theory['best_colors'])}."
                    ),
                },
                "affiliate_upsells": affiliate_recommendations,
                "my_narrative_catalog": MY_NARRATIVE_CATALOG,
                "outfit_completion_pct": 100,
                "source_mode": source_mode,
                "source_preference": source_mode,
                "vton_applied": vton_applied,
                "global_style_query": global_style_query,
                "global_query_category": global_query_category,
                "direction": (recommendation or {}).get("direction") or (recommendation or {}).get("outfit_description") or f"Styled {vibe_label} look for {occasion_key}.",
                "outfit_pieces": outfit_pieces,
                "suggestions": (recommendation or {}).get("suggestions") or (recommendation or {}).get("styling_tips") or [],
                "styling_tips": (recommendation or {}).get("styling_tips") or [],
                "color_science": (recommendation or {}).get("color_science_note") or color_theory.get("undertone_note", ""),
                "my_narrative_product": vton_product if source_mode == "my_narrative" else None,

                # Gamification + User Profile Data
                "gamification": gamification,

                # Auto-fill data for user dashboard
                "user_profile_data": {
                    "physique": {
                        "skin_tone": mst_value,
                        "skin_tone_label": MST_LABELS.get(mst_value, "Medium"),
                        "body_type": biometrics_result.get("body_type"),
                        "gender": biometrics_result.get("gender_presentation"),
                    },
                    "color_theory": {
                        "best_colors": color_theory["best_colors"],
                        "avoid_colors": color_theory["avoid"],
                        "undertone_note": color_theory["undertone_note"],
                    },
                    "profile_face_card_url": final_image_url,
                    "generated_at": time.time(),
                },

                # GPT-4o fashion recommendation data
                "recommendation": recommendation,
            }

            self._respond(200, response)
            return

        # Unknown action
        self._respond(400, {
            "success": False,
            "error": f"Unknown action: '{action}'. Valid: full_pipeline, get_vibes, get_occasions, get_gamification, ingest_affiliate_feed, search_global_inventory",
        })