"""
fashion_services.py — Consolidated Fashion Services
Routes:
  POST /api/fashion/consultant — AI Fashion Consultant (self/gift mode)
  POST /api/fashion/pipeline   — Full AI Stylist Pipeline (OpenAI + Replicate FLUX)
  POST /api/fashion/try-on     — Virtual Try-On (IDM-VTON or FLUX)
"""

from http.server import BaseHTTPRequestHandler
import base64
import json
import os
import sys
import time
import math
import threading
import urllib.parse
import requests
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from currency_utils import detect_currency_from_headers, convert_price_rupees, format_price

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


# ═════════════════════════════════════════════════════════════════════════════
# SHARED CONSTANTS
# ═════════════════════════════════════════════════════════════════════════════

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

MST_LABELS = {
    1: "Very Light", 2: "Light", 3: "Light-Medium", 4: "Medium-Light",
    5: "Medium", 6: "Medium-Tan", 7: "Tan", 8: "Dark-Tan", 9: "Dark", 10: "Very Dark",
}

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

VIBE_PRESETS = {
    "caffeine_survivor": {"label": "Surviving on Caffeine", "flux_modifier": "oversized cozy hoodie, distressed denim, messy-chic hair, coffee shop aesthetic", "style_persona": "effortlessly unbothered"},
    "sarcastic_rizzler": {"label": "The Sarcastic Rizzler", "flux_modifier": "sharp tailored blazer, statement sneakers, confident pose, editorial lighting", "style_persona": "sharp-witted trendsetter"},
    "main_character": {"label": "Main Character Energy", "flux_modifier": "dramatic flowing outfit, cinematic backlighting, street style, golden hour", "style_persona": "the protagonist of every scene"},
    "quiet_luxury": {"label": "Quiet Luxury", "flux_modifier": "minimal neutral tones, cashmere texture, understated elegance, clean silhouette", "style_persona": "old-money minimalist"},
}

OCCASION_PRESETS = {
    "date_night": {"label": "Date Night", "flux_context": "romantic evening setting, warm ambient lighting, upscale restaurant vibes", "style_direction": "elevated casual to semi-formal"},
    "office": {"label": "Office", "flux_context": "modern corporate office, clean backdrop, professional lighting", "style_direction": "smart casual to business formal"},
    "sangeet": {"label": "Sangeet", "flux_context": "vibrant Indian wedding sangeet celebration, colorful lighting, festive atmosphere", "style_direction": "festive ethnic with modern fusion"},
    "airport_look": {"label": "Airport Look", "flux_context": "luxury airport terminal, travel aesthetic, natural daylight", "style_direction": "comfortable yet polished travel wear"},
}

PRICE_TIERS = {
    "value": {"label": "Value", "range": "Under \u20B91,500", "min": 0, "max": 1500},
    "premium": {"label": "Premium", "range": "\u20B91,500 \u2013 \u20B93,500", "min": 1500, "max": 3500},
    "luxury": {"label": "Luxury", "range": "Above \u20B93,500", "min": 3500, "max": 99999},
}

BRAND_SUGGESTIONS = {
    "office": {
        "style": "Formal & Office Wear",
        "value": {
            "global": ["Peter England", "Max Fashion", "Netplay", "Code", "Zudio", "Excalibur"],
            "indian": ["Peter England", "Max Fashion", "Netplay", "Code", "Zudio", "Excalibur"],
        },
        "premium": {
            "global": ["Van Heusen", "Allen Solly", "Louis Philippe", "Arrow", "Marks & Spencer", "FableStreet"],
            "indian": ["Van Heusen", "Allen Solly", "Louis Philippe", "Arrow", "Marks & Spencer", "FableStreet"],
        },
        "luxury": {
            "global": ["Brooks Brothers", "Hugo Boss", "Massimo Dutti", "Raymond", "Tommy Hilfiger", "Calvin Klein"],
            "indian": ["Brooks Brothers", "Hugo Boss", "Massimo Dutti", "Raymond", "Tommy Hilfiger", "Calvin Klein"],
        },
    },
    "date_night": {
        "style": "Party & Evening Wear",
        "value": {
            "global": ["Berrylush", "SASSAFRAS", "Athena", "Tokyo Talkies", "FabAlley", "Zudio"],
            "indian": ["Berrylush", "SASSAFRAS", "Athena", "Tokyo Talkies", "FabAlley", "Zudio"],
        },
        "premium": {
            "global": ["Kazo", "Twenty Dresses", "Rareism", "Mango", "Vero Moda", "RSVP"],
            "indian": ["Kazo", "Twenty Dresses", "Rareism", "Mango", "Vero Moda", "RSVP"],
        },
        "luxury": {
            "global": ["ASOS Design", "Revolve", "House of CB", "Forever New", "Bebe", "Zara Studio"],
            "indian": ["ASOS Design", "Revolve", "House of CB", "Forever New", "Bebe", "Zara Studio"],
        },
    },
    "sangeet": {
        "style": "Ethnic & Festive Wear",
        "value": {
            "global": ["Anouk", "Libas", "Sangria", "Vishudh", "Aurelia", "Soch"],
            "indian": ["Anouk", "Libas", "Sangria", "Vishudh", "Aurelia", "Soch"],
        },
        "premium": {
            "global": ["BIBA", "W for Woman", "Global Desi", "Fabindia", "Indya", "Koskii"],
            "indian": ["BIBA", "W for Woman", "Global Desi", "Fabindia", "Indya", "Koskii"],
        },
        "luxury": {
            "global": ["Kalki Fashion", "Manyavar", "Ritu Kumar", "Anita Dongre", "House of Masaba", "Nalli"],
            "indian": ["Kalki Fashion", "Manyavar", "Ritu Kumar", "Anita Dongre", "House of Masaba", "Nalli"],
        },
    },
    "airport_look": {
        "style": "Travel & Utility Wear",
        "value": {
            "global": ["Quechua", "Forclaz", "Wildcraft", "Bombay Trooper", "Trekman", "Fuaark"],
            "indian": ["Quechua", "Forclaz", "Wildcraft", "Bombay Trooper", "Trekman", "Fuaark"],
        },
        "premium": {
            "global": ["Gokyo", "Columbia", "WROGN", "Woodland", "Royal Enfield", "Quiksilver"],
            "indian": ["Gokyo", "Columbia", "WROGN", "Woodland", "Royal Enfield", "Quiksilver"],
        },
        "luxury": {
            "global": ["The North Face", "Patagonia", "Arc'teryx", "Vuori", "Salomon", "Columbia Tech"],
            "indian": ["The North Face", "Patagonia", "Arc'teryx", "Vuori", "Salomon", "Columbia Tech"],
        },
    },
}

SKIN_TONE_TO_MST = {"Fair": 2, "Light": 2, "Medium": 5, "Olive": 4, "Brown": 7, "Dark": 9, "Deep": 10}
BODY_SHAPE_MAP = {"slim_athletic": "slim athletic physique", "average": "medium build", "muscular": "well-built athletic physique", "plus_size": "plus size body type", "tall_lean": "tall lean physique", "short_stocky": "compact stocky build"}
GENDER_MAP = {"men": "man", "women": "woman"}


# ═════════════════════════════════════════════════════════════════════════════
# FASHION CONSULTANT — Self/Gift Mode
# ═════════════════════════════════════════════════════════════════════════════

def _is_generic_marketplace_link(url: str) -> bool:
    if not isinstance(url, str) or not url.strip():
        return True
    u = url.strip().lower()
    if u in ("https://myntra.com", "https://www.myntra.com", "https://ajio.com", "https://www.ajio.com"):
        return True
    if u.startswith("https://www.amazon.") and ("/dp/" not in u and "/gp/product/" not in u):
        return True
    if "://myntra.com/" in u or "://www.myntra.com/" in u:
        return "/buy" not in u and "/p/" not in u
    if "://www.flipkart.com/" in u:
        return "/p/" not in u and "pid=" not in u
    return False


def _pick_catalog_for_piece(piece: dict) -> dict:
    text = " ".join([str(piece.get("slot", "")), str(piece.get("type", "")), str(piece.get("name", "")), str(piece.get("why", ""))]).lower()
    wants_jacket = ("jacket" in text) or ("varsity" in text) or (piece.get("slot") == "outerwear")
    wants_hoodie = ("hoodie" in text) or ("sweatshirt" in text)
    wants_tee = ("tee" in text) or ("t-shirt" in text) or ("tshirt" in text) or (piece.get("slot") == "top")
    iitian_hint = "iit" in text

    if wants_jacket:
        for item in MY_NARRATIVE_CATALOG:
            if "varsity-jacket" in item["handle"]:
                return item
    if wants_hoodie:
        for item in MY_NARRATIVE_CATALOG:
            if "hoodies" in item["handle"] and ((iitian_hint and "iitian" in item["handle"]) or (not iitian_hint and "nitian" in item["handle"])):
                return item
    if wants_tee:
        for item in MY_NARRATIVE_CATALOG:
            if "t-shirt" in item["handle"] and ((iitian_hint and "iitian" in item["handle"]) or (not iitian_hint and "nitian" in item["handle"])):
                return item
    return MY_NARRATIVE_CATALOG[2]


def _attach_exact_links(outfit_pieces: list, currency: str = "INR") -> list:
    normalized = []
    for piece in outfit_pieces or []:
        p = dict(piece)
        if p.get("owned") is True:
            p["shop_links"] = []
            normalized.append(p)
            continue
        selected = _pick_catalog_for_piece(p)
        existing_links = [l for l in (p.get("shop_links") or []) if isinstance(l, dict) and not _is_generic_marketplace_link(l.get("url", ""))]
        mn_link = {
            "platform": "MY NARRATIVE",
            "url": selected["product_url"],
            "price": format_price(convert_price_rupees(selected['price'], currency), currency),
            "handle": selected["handle"],
            "flat_lay_url": selected["flat_lay_url"],
        }
        p["shop_links"] = [mn_link] + existing_links[:1]
        p["my_narrative_product"] = {
            "handle": selected["handle"],
            "title": selected["title"],
            "price": selected["price"],
            "product_url": selected["product_url"],
            "flat_lay_url": selected["flat_lay_url"],
        }
        normalized.append(p)
    return normalized


def _handle_fashion_consultant(body):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("Missing API Key on Server")
    client = OpenAI(api_key=api_key)
    currency = body.get("_currency", "INR")

    identity = body.get('identity', {})
    ctx = body.get('currentContext', {})
    mode = ctx.get('mode', 'self')

    if mode == 'gift':
        recipient = ctx.get('recipient', 'Someone')
        occasion = ctx.get('occasion', 'Special Occasion')
        unspoken = ctx.get('unspoken', '')
        core_expr = identity.get('coreExpression', 'Balanced')
        presence = identity.get('presence', 'Thoughtful')
        signal = identity.get('signal', 'Growth')

        system_instruction = f"""
You are the creative director at MY NARRATIVE — a premium streetwear and merch brand where every piece of clothing carries a personal story. Your specialty is crafting short, powerful slogans that get printed on t-shirts, hoodies, caps, and tote bags.

ABOUT THE GIFT-GIVER:
• Core Style Expression: {core_expr}
• How They Show Up in the World: {presence}
• Current Life Signal: {signal}

THE GIFT CONTEXT:
• Who is receiving this: {recipient}
• The occasion: {occasion}
• The unspoken message: "{unspoken}"

Generate exactly 5 slogans. Each must be 2–7 words maximum, printability tested, no hashtags/emojis/quotes, no generic motivational language.

RESPONSE FORMAT (Strict JSON):
{{
  "direction": "1-2 sentence creative brief",
  "slogans": ["First slogan", "Second slogan", "Third slogan", "Fourth slogan", "Fifth slogan"],
  "suggestions": ["Design/styling tip", "Emotional context tip", "Personalization tip"]
}}
"""
    else:
        contexts = ", ".join(ctx.get('contexts', ['Daily Wear']))
        loudness = ctx.get('loudness', 'Balanced')
        core_expr = identity.get('coreExpression', 'Balanced')
        presence = identity.get('presence', 'Adaptive')
        signal = identity.get('signal', 'Growth')
        archetype = identity.get('archetype', {})
        archetype_name = archetype.get('name', 'The Original')
        height = identity.get('height', 'Not provided')
        build = identity.get('build', 'Not provided')
        gender = identity.get('gender', 'Not specified')
        skin_tone = identity.get('skinTone', 'Not provided')
        undertone = identity.get('undertone', 'Not provided')
        region = identity.get('region', 'Not provided')
        climate = identity.get('climate', 'Not provided')
        budget = identity.get('budget', 'Not provided')
        digital_closet = identity.get('digital_closet', [])
        simple_closet = identity.get('closet', [])

        if digital_closet:
            closet_lines = []
            for i, item in enumerate(digital_closet, 1):
                name = item.get('original_name') or item.get('name', 'Unknown item')
                color = item.get('color', '')
                fabric = item.get('fabric', '')
                fit = item.get('fit', '')
                pattern = item.get('pattern', '')
                section = item.get('closet_section', '')
                occasion = item.get('occasion', '')
                season = item.get('season', '')
                tags = ', '.join(item.get('style_tags', [])) if item.get('style_tags') else ''
                item_id = item.get('item_id', f'item_{i}')
                descriptor_parts = [p for p in [color, pattern, fabric, fit + ' fit' if fit else ''] if p]
                descriptor = ' '.join(descriptor_parts)
                line = f"  [{item_id}] {name}"
                if descriptor:
                    line += f" — {descriptor}"
                if section:
                    line += f" ({section})"
                if occasion:
                    line += f" | Best for: {occasion}"
                if season:
                    line += f" | Season: {season}"
                if tags:
                    line += f" | Tags: {tags}"
                closet_lines.append(line)
            closet_str = "\n".join(closet_lines)
            closet_str += f"\n\n  Total: {len(digital_closet)} items detected by AI from uploaded photos."
        elif simple_closet:
            closet_str = ", ".join(simple_closet)
        else:
            closet_str = "No closet items provided yet."

        system_instruction = f"""
You are the AI Fashion Consultant at MY NARRATIVE — a psychology-first styling engine for the Indian market.

USER IDENTITY PROFILE:
• Core Expression: {core_expr}
• World Presence: {presence}
• Current Signal: {signal}
• Archetype: {archetype_name}
• Height: {height} cm | Build: {build} | Gender: {gender}
• Skin Tone: {skin_tone} | Undertone: {undertone}
• Region: {region} | Climate: {climate} | Budget: {budget}

EXISTING CLOSET:
{closet_str}

CURRENT REQUEST:
• Context: {contexts}
• Loudness: {loudness}

STYLING RULES:
1. BODY-AWARE: Consider build and height for cut/fit recommendations.
2. COLOR-SCIENCE: Recommend colors based on skin tone + undertone.
3. CLIMATE-SMART: Factor in the user's primary climate.
4. BUDGET-REALISTIC: Stay within the budget range.
5. CLOSET-AWARE: Prioritize items they ALREADY OWN (owned: true).
6. INDIA-SPECIFIC: Include Indian brands and platform links.
7. ARCHETYPE-ALIGNED: Ensure direction matches psychological archetype.

RESPONSE FORMAT (Strict JSON):
{{
  "direction": "1-2 sentence styling direction",
  "outfit_pieces": [
    {{
      "slot": "top|bottom|footwear|accessory|outerwear",
      "name": "Specific item name",
      "type": "shirt|tshirt|jeans|chinos|sneakers|boots|watch|etc",
      "color": "#hex color code",
      "owned": true,
      "item_id": "matching item_id from closet if owned, else null",
      "why": "One sentence: why this piece works",
      "shop_links": [{{ "platform": "Myntra", "url": "https://myntra.com", "price": "₹approx" }}]
    }}
  ],
  "suggestions": ["Full body fashion photograph prompt 1", "Full body fashion photograph prompt 2", "Full body fashion photograph prompt 3", "Close-up detail shot prompt"],
  "styling_tips": ["tip 1", "tip 2", "tip 3"],
  "color_science": "A sentence explaining why these colors work",
  "archetype_note": "A personal note connecting this outfit to their archetype"
}}

Generate 4-6 outfit pieces. At least 1-2 must be owned items (owned: true).
"""

    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": "Generate JSON response."}
        ],
        response_format={"type": "json_object"},
        temperature=0.85
    )

    data = json.loads(completion.choices[0].message.content)

    if mode == 'gift':
        return {
            "direction": data.get("direction", "Curated for you."),
            "suggestions": data.get("slogans", []),
            "styling_tips": data.get("suggestions", [])
        }
    else:
        outfit_pieces = _attach_exact_links(data.get("outfit_pieces", []), currency)
        return {
            "direction": data.get("direction", "Styled for you."),
            "outfit_pieces": outfit_pieces,
            "suggestions": data.get("suggestions", []),
            "styling_tips": data.get("styling_tips", []),
            "color_science": data.get("color_science", ""),
            "archetype_note": data.get("archetype_note", ""),
            "my_narrative_catalog": MY_NARRATIVE_CATALOG,
            "vton_ready_products": [p.get("my_narrative_product") for p in outfit_pieces if p.get("my_narrative_product")][:6],
        }


# ═════════════════════════════════════════════════════════════════════════════
# PIPELINE HELPERS — OpenAI + Replicate + Supabase
# ═════════════════════════════════════════════════════════════════════════════

def _sb_headers():
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_KEY", "").strip()
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "application/json"}
    return url, key, headers


def sb_configured() -> bool:
    url, key, _ = _sb_headers()
    return bool(url and key)


def _sb_request(method: str, path: str, payload: Any = None):
    url, key, headers = _sb_headers()
    if not url or not key:
        return None, "supabase_not_configured"
    full_url = f"{url.rstrip('/')}{path}"
    try:
        kwargs = {"headers": headers, "timeout": 20}
        if payload is not None:
            kwargs["json"] = payload
        resp = requests.request(method, full_url, **kwargs)
        resp.raise_for_status()
        raw = resp.text or "null"
        return json.loads(raw), None
    except requests.exceptions.HTTPError as e:
        detail = e.response.text[:260] if e.response else str(e)
        code = e.response.status_code if e.response else 0
        return None, f"http_{code}:{detail}"
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
    try:
        resp = requests.post(
            f"{url.rstrip('/')}/rest/v1/global_inventory",
            json=rows,
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = json.loads(resp.text or "[]")
        return {"inserted": len(data) if isinstance(data, list) else len(rows)}, None
    except requests.exceptions.HTTPError as e:
        detail = e.response.text[:300] if e.response else str(e)
        code = e.response.status_code if e.response else 0
        return None, f"http_{code}:{detail}"
    except Exception as e:
        return None, str(e)


def sb_match_global_inventory(query_embedding: list, category: str = "", limit: int = 6):
    payload = {"query_embedding": query_embedding, "query_category": category or None, "match_count": max(1, min(20, int(limit or 6)))}
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
    dot = na = nb = 0.0
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
    return scored[:max(1, min(20, int(limit or 6)))], None


def get_text_embedding(client, text: str) -> list:
    text = (text or "").strip()
    if not text:
        return []
    try:
        emb = client.embeddings.create(model="text-embedding-3-small", input=text)
        vec = emb.data[0].embedding if emb and emb.data else []
        return vec if isinstance(vec, list) else []
    except Exception:
        return []


def _download_bytes(url: str, timeout: int = 15) -> bytes:
    if not url:
        return b""
    resp = requests.get(url, headers={"User-Agent": "MN-AI-Stylist/1.0"}, timeout=timeout)
    resp.raise_for_status()
    return resp.content


def classify_affiliate_image(image_url: str) -> dict:
    lowered = (image_url or "").lower()
    hard_reject_tokens = ["lookbook", "lifestyle", "on-model", "model", "celebrity", "person", "people", "street-style", "outfit", "selfie", "influencer", "runway", "editorial", "portrait"]
    hard_pass_tokens = ["flatlay", "flat-lay", "ghost", "mockup", "hanger", "product-only", "product", "packshot"]
    if any(tok in lowered for tok in hard_reject_tokens):
        return {"approved": False, "reason": "url_pattern_human_lifestyle", "quality_score": 0.1}
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
            reject_labels = {"person", "human", "face", "head", "hand", "finger", "arm", "leg", "foot", "crowd", "city", "street", "room", "furniture", "indoor", "outdoor", "building"}
            clutter_hits = [n for n in names if n in reject_labels]
            if face_count > 0 or clutter_hits:
                return {"approved": False, "reason": "rekognition_detected_human_body_or_clutter", "quality_score": 0.12, "faces": face_count, "labels": clutter_hits[:6]}
            return {"approved": True, "reason": "rekognition_clean_product", "quality_score": 0.9}
        except Exception:
            pass
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
    for key in ["products", "items", "data", "results", "result", "offers"]:
        arr = payload.get(key)
        if isinstance(arr, list):
            return [x for x in arr if isinstance(x, dict)]
    if isinstance(payload.get("product"), dict):
        return [payload["product"]]
    return []


def normalize_partner_product(raw: dict, network: str, fallback_brand: str, fallback_category: str) -> dict:
    title = str(_first_non_empty(raw, ["title", "productName", "name", "product_name"], "")).strip()
    price_raw = _first_non_empty(raw, ["price", "salePrice", "priceValue", "current_price", "amount"], "")
    try:
        price_str = str(price_raw).strip() if str(price_raw).strip() else "0"
        price_str = price_str.replace(",", "").replace("₹", "").replace("$", "").replace("£", "").replace("€", "").replace("د.إ", "").replace("A$", "")
        price = float(price_str) if price_str else 0.0
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


def generate_fashion_recommendation(client, biometrics: dict, occasion: str, vibe_id: str) -> dict:
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
    token = os.environ.get("REPLICATE_API_TOKEN")
    mst_label = biometrics.get("mst_label", "Medium")
    body_type = biometrics.get("body_type", "average")
    gender = biometrics.get("gender_presentation", "person")
    vibe = VIBE_PRESETS.get(vibe_id, VIBE_PRESETS["caffeine_survivor"])
    occ = OCCASION_PRESETS.get(occasion, OCCASION_PRESETS["date_night"])
    body_description = BODY_SHAPE_MAP.get(body_type, body_type)

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
            output = client.run(
                "black-forest-labs/flux-schnell",
                input={"prompt": prompt, "aspect_ratio": "3:4", "num_inference_steps": 4, "output_format": "webp", "output_quality": 90},
            )
            image_url = str(output[0]) if output else None
            if image_url:
                return image_url
            else:
                raise Exception("FLUX returned empty output")
        except Exception as e:
            print(f"❌ [generate_flux_image] FLUX API error: {e}")
            return "https://placehold.co/768x1024/1a1a2e/e94560?text=FLUX+Generated+Image"

    return "https://placehold.co/768x1024/1a1a2e/e94560?text=FLUX+Generated+Image"


def get_gamification_state(user_id: str) -> dict:
    return {
        "mascot_quest": {
            "cards_collected": 1, "cards_total": 5,
            "current_card": {"name": "The Street Style Phantom", "rarity": "Common", "unlock_method": "Complete your first AI editorial"},
            "next_card": {"name": "The Boardroom Shapeshifter", "rarity": "Rare", "unlock_method": "Checkout any recommended item"},
            "checkout_cta": "Checkout to unlock your next physical Mascot Card!",
        },
        "style_graph": {
            "photos_uploaded": 1, "photos_required": 4, "progress_pct": 25,
            "reward_unlocked": False,
            "reward_description": "Upload 3 more OOTD photos to train your AI and unlock 5% Store Credit",
            "credit_amount": "5%", "credit_type": "Store Credit",
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
    if "sangeet" in occ:
        return [MY_NARRATIVE_CATALOG[0], MY_NARRATIVE_CATALOG[3]]
    elif "airport" in occ or "office" in occ:
        return [MY_NARRATIVE_CATALOG[1], MY_NARRATIVE_CATALOG[4]]
    elif "gym" in occ or "caffeine" in vibe:
        return [MY_NARRATIVE_CATALOG[2], MY_NARRATIVE_CATALOG[1]]
    else:
        return [MY_NARRATIVE_CATALOG[2], MY_NARRATIVE_CATALOG[5]]


def generate_my_narrative_recommendation(client, biometrics: dict, occasion: str, vibe_id: str, currency: str = "INR") -> dict:
    catalog_lines = "\n".join([f"- {p['handle']} | {p['title']} | ₹{p['price']} | {p['product_url']}" for p in MY_NARRATIVE_CATALOG])
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
"""
    selected = []
    direction = "Curated from My Narrative exclusive drops."
    tips = ["Keep the upper silhouette clean so the slogan stays legible.", "Pair with neutral bottoms for stronger visual focus.", "Use one statement layer only to avoid clutter."]
    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "Return valid JSON only."}, {"role": "user", "content": prompt}],
            response_format={"type": "json_object"}, temperature=0.6,
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
            "name": p["title"], "type": ptype, "color": "#39A596", "owned": False,
            "why": "Selected from My Narrative catalog to match your occasion and vibe.",
            "shop_links": [{"platform": "MY NARRATIVE", "url": p["product_url"], "add_to_cart_url": p["product_url"], "product_url": p["product_url"], "exact_product_url": p["product_url"], "price": format_price(convert_price_rupees(p['price'], currency), currency), "handle": p["handle"], "flat_lay_url": p["flat_lay_url"]}],
            "my_narrative_product": {"handle": p["handle"], "title": p["title"], "price": p["price"], "product_url": p["product_url"], "flat_lay_url": p["flat_lay_url"]}
        })

    return {
        "direction": direction, "styling_tips": tips[:3], "suggestions": tips[:3],
        "outfit_pieces": outfit_pieces, "selected_products": selected_products,
        "color_science_note": MST_COLOR_THEORY.get(biometrics.get("monk_skin_tone", 5), MST_COLOR_THEORY[5]).get("undertone_note", ""),
    }


def run_idm_vton(user_image: str, garment_image: str, description: str) -> str:
    token = os.environ.get("REPLICATE_API_TOKEN")
    if not token or not REPLICATE_AVAILABLE or not user_image or not garment_image:
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
            input={"human_img": user_image, "garm_img": garment_image, "garment_des": description or "streetwear top", "category": "upper_body", "crop": False, "seed": 42, "steps": 30, "force_dc": False, "mask_only": False}
        )
        return str(output) if output else ""
    except Exception as e:
        print(f"⚠️ [run_idm_vton] {e}")
        return ""


def normalize_replicate_image_ref(image_value: str) -> str:
    v = (image_value or "").strip()
    if not v:
        return ""
    lowered = v.lower()
    if lowered.startswith("http://") or lowered.startswith("https://") or lowered.startswith("data:image/"):
        return v
    return "data:image/jpeg;base64," + v


def maybe_face_swap(base_image_url: str, user_image: str) -> str:
    token = os.environ.get("REPLICATE_API_TOKEN")
    if not token or not REPLICATE_AVAILABLE or not user_image:
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


def build_global_outfit_pieces(recommendation: dict, affiliate_recommendations: list, currency: str = "INR") -> list:
    rec = recommendation or {}
    links = []
    for item in affiliate_recommendations[:3]:
        raw_price = item.get('price')
        price_str = format_price(convert_price_rupees(raw_price, currency), currency) if raw_price else ""
        links.append({"platform": item.get("platform", "Shop"), "url": item.get("affiliate_url", ""), "affiliate_url": item.get("affiliate_url", ""), "price": price_str})
    return [
        {"slot": "top", "name": (rec.get("top", {}) or {}).get("name", "Styled Top"), "type": "top", "color": (rec.get("top", {}) or {}).get("hex", "#39A596"), "owned": False, "why": "Matched to your tone, body profile and selected vibe.", "shop_links": links[:1]},
        {"slot": "bottom", "name": (rec.get("bottom", {}) or {}).get("name", "Styled Bottom"), "type": "bottom", "color": (rec.get("bottom", {}) or {}).get("hex", "#5f6368"), "owned": False, "why": "Balanced silhouette for a complete look.", "shop_links": links[1:2]},
        {"slot": "footwear", "name": (rec.get("footwear", {}) or {}).get("name", "Footwear"), "type": "footwear", "color": (rec.get("footwear", {}) or {}).get("hex", "#ffffff"), "owned": False, "why": "Completes the outfit with contrast and structure.", "shop_links": links[2:3] or links[:1]},
    ]


def build_style_query_from_recommendation(recommendation: dict, occasion: str, vibe_label: str) -> str:
    rec = recommendation or {}
    top = (rec.get("top", {}) or {}).get("name", "")
    bottom = (rec.get("bottom", {}) or {}).get("name", "")
    footwear = (rec.get("footwear", {}) or {}).get("name", "")
    color = (rec.get("top", {}) or {}).get("color", "")
    parts = [top, bottom, footwear, color, occasion.replace("_", " "), vibe_label]
    return " | ".join([p for p in parts if str(p).strip()])


def generate_global_style_query(client, biometrics: dict, occasion: str, vibe_id: str, user_image: str = "") -> dict:
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
"""
    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "Return valid JSON only."}, {"role": "user", "content": prompt}],
            response_format={"type": "json_object"}, temperature=0.35,
        )
        data = json.loads(completion.choices[0].message.content)
        q = str(data.get("style_query", "")).strip() or default_query
        cat = str(data.get("category", "")).strip().lower() or default_category
        return {"style_query": q, "category": cat}
    except Exception:
        return {"style_query": default_query, "category": default_category}


def _run_path_a_global(client, biometrics: dict, occasion: str, vibe_id: str, user_image: str, currency: str = "INR", preferred_brands: list = None, price_tier: str = ""):
    vibe_label = VIBE_PRESETS.get(vibe_id, {}).get("label", "stylish look")
    occasion_key = occasion.replace("_", " ")

    recommendation = {}
    try:
        recommendation = generate_fashion_recommendation(client=client, biometrics=biometrics, occasion=occasion, vibe_id=vibe_id)
    except Exception:
        recommendation = {}

    matches = []

    # ── Brand-based search: try uploaded catalogs first ────────────────────
    if preferred_brands:
        from brand_catalog import search_brand_products
        for brand_name in preferred_brands[:3]:
            brand_prods = search_brand_products(
                brand=brand_name,
                gender=biometrics.get("gender_presentation", ""),
                limit=4,
                currency=currency,
            )
            for p in brand_prods:
                matches.append({
                    "id": p.get("id"), "network": "BRAND_CATALOG", "title": p.get("title"),
                    "brand": p.get("brand"), "category": p.get("category"), "price": p.get("price"),
                    "currency": currency, "image_url": p.get("image_url"),
                    "flat_lay_url": p.get("flat_lay_url") or p.get("image_url"),
                    "checkout_url": "", "affiliate_url": "",
                    "similarity": 0.5, "quality_score": 0.8,
                })

    # ── Fallback: vector similarity search from global inventory ──────────
    if not matches:
        query_obj = generate_global_style_query(client=client, biometrics=biometrics, occasion=occasion, vibe_id=vibe_id, user_image=user_image)
        style_query = query_obj.get("style_query", "")
        query_category = query_obj.get("category", "")
        inventory_result = search_global_inventory(client=client, style_query=style_query, category=query_category, limit=6)
        matches = inventory_result.get("matches", []) if inventory_result.get("success") else []
    else:
        query_obj = {"style_query": f"brand search: {', '.join(preferred_brands[:3])}", "category": ""}
        style_query = query_obj["style_query"]
        query_category = ""

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
                "product_name": m.get("title"), "brand": m.get("brand") or m.get("network"),
                "price": m.get("price"), "currency": m.get("currency", "INR"),
                "affiliate_url": checkout_url, "checkout_url": checkout_url,
                "exact_product_url": checkout_url, "product_url": checkout_url,
                "flat_lay_url": m.get("flat_lay_url") or m.get("image_url"),
                "image_url": m.get("image_url"), "platform": m.get("network", "GLOBAL"),
                "recommended_for": f"{vibe_label} {occasion_key} look",
                "gap_item": {"description": m.get("title"), "is_owned": False},
                "similarity": m.get("similarity", 0.0),
            })
        selected_match = matches[0]
        final_image_url = run_idm_vton(user_image=user_image, garment_image=selected_match.get("flat_lay_url") or selected_match.get("image_url") or "", description=selected_match.get("title", "global product"))
        vton_applied = bool(final_image_url)

    if not final_image_url:
        try:
            flux_image_url = generate_flux_image(biometrics=biometrics, occasion=occasion, vibe_id=vibe_id, recommendation=recommendation)
        except Exception:
            flux_image_url = "https://placehold.co/768x1024/1a1a2e/e94560?text=AI+Styled+Look"
        final_image_url = maybe_face_swap(flux_image_url, user_image)

    outfit_pieces = build_global_outfit_pieces(recommendation, affiliate_recommendations, currency)
    return {
        "recommendation": recommendation, "affiliate_recommendations": affiliate_recommendations,
        "outfit_pieces": outfit_pieces, "final_image_url": final_image_url, "flux_image_url": flux_image_url,
        "style_query": style_query, "vector_category": query_category, "vector_top_match": selected_match, "vton_applied": vton_applied,
    }


def search_global_inventory(client, style_query: str, category: str = "", limit: int = 6):
    emb = get_text_embedding(client, style_query)
    if not emb:
        return {"success": False, "error": "embedding_failed", "matches": []}
    rows, err = sb_match_global_inventory(query_embedding=emb, category=category, limit=limit)
    if err:
        rows, fallback_err = sb_fallback_similarity_search(query_embedding=emb, category=category, limit=limit)
        if fallback_err:
            return {"success": False, "error": f"{err}; fallback:{fallback_err}", "matches": []}
    matches = []
    for r in rows[:max(1, min(20, int(limit or 6)))]:
        matches.append({
            "id": r.get("id"), "network": r.get("network", "").upper(), "title": r.get("title"),
            "brand": r.get("brand"), "category": r.get("category"), "price": r.get("price"),
            "currency": r.get("currency", "INR"), "image_url": r.get("image_url"),
            "flat_lay_url": r.get("flat_lay_url") or r.get("image_url"),
            "checkout_url": r.get("checkout_url") or r.get("affiliate_url"),
            "affiliate_url": r.get("affiliate_url"),
            "similarity": float(r.get("similarity", 0.0) or 0.0), "quality_score": float(r.get("quality_score", 0.0) or 0.0),
        })
    return {"success": True, "matches": matches, "embedding_size": len(emb)}


def _handle_stylist_pipeline(body):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")
    client = OpenAI(api_key=api_key)
    currency = body.get("_currency", "INR")

    action = body.get("action", "full_pipeline")

    if action == "get_vibes":
        return {"success": True, "vibes": [{"id": vid, "label": vdata["label"], "persona": vdata["style_persona"]} for vid, vdata in VIBE_PRESETS.items()]}

    if action == "get_occasions":
        return {"success": True, "occasions": [{"id": oid, "label": odata["label"], "direction": odata["style_direction"], "brands": BRAND_SUGGESTIONS.get(oid, {})} for oid, odata in OCCASION_PRESETS.items()], "price_tiers": PRICE_TIERS}

    if action == "get_gamification":
        return {"success": True, "gamification": get_gamification_state(body.get("user_id", "anonymous"))}

    if action == "ingest_affiliate_feed":
        if not sb_configured():
            raise ValueError("Supabase not configured")
        try:
            from ._ingest import ingest_partner_feed
        except ImportError:
            raise ValueError("ingest_affiliate_feed module not available. Deploy _ingest.py to enable this action.")
        result = ingest_partner_feed(client=client, network=body.get("network", ""), query=body.get("query", ""), brand=body.get("brand", ""), category=body.get("category", ""), limit=body.get("limit", 30), dry_run=bool(body.get("dry_run", False)))
        return result

    if action == "search_global_inventory":
        result = search_global_inventory(client=client, style_query=body.get("style_query", ""), category=body.get("category", ""), limit=body.get("limit", 6))
        return result

    if action == "upload_brand_catalog":
        from brand_catalog import parse_catalog_file, upload_brand_catalog
        brand_name = body.get("brand_name", "")
        marketplace = body.get("marketplace", "generic")
        file_content = body.get("file_content", "")
        filename = body.get("filename", "catalog.csv")
        if not brand_name or not file_content:
            raise ValueError("brand_name and file_content required")
        products = parse_catalog_file(file_content, filename, marketplace)
        if not products:
            raise ValueError("No valid products found in file. Check format matches marketplace template.")
        result = upload_brand_catalog(brand_name, products, marketplace, uploaded_by=body.get("uploaded_by", "api"))
        return result

    if action == "search_brand_catalog":
        from brand_catalog import search_brand_products
        brand = body.get("brand", "")
        category = body.get("category", "")
        gender = body.get("gender", "")
        min_price = float(body.get("min_price", 0))
        max_price = float(body.get("max_price", 999999))
        limit = int(body.get("limit", 20))
        vibe = body.get("vibe", "")
        color_pref = body.get("color_pref", "")
        products = search_brand_products(brand=brand, category=category, gender=gender, min_price=min_price, max_price=max_price, limit=limit, currency=currency, vibe=vibe, color_pref=color_pref)
        return {"success": True, "products": products, "count": len(products)}

    if action == "get_brand_catalogs":
        from brand_catalog import get_brand_catalog_summary
        brands = get_brand_catalog_summary()
        return {"success": True, "brands": brands}

    if action == "delete_brand_catalog":
        from brand_catalog import delete_brand_catalog
        brand = body.get("brand", "")
        if not brand:
            raise ValueError("brand name required")
        result = delete_brand_catalog(brand)
        return result

    if action == "search_brands_for_occasion":
        from brand_catalog import search_brand_products
        occasion = body.get("occasion", "")
        price_range = body.get("price_range", "premium")
        brands_for_occasion = BRAND_SUGGESTIONS.get(occasion, {}).get(price_range, [])
        all_products = []
        for b in brands_for_occasion:
            prods = search_brand_products(brand=b, limit=5, currency=currency)
            all_products.extend(prods)
        return {"success": True, "products": all_products, "brands": brands_for_occasion, "count": len(all_products)}

    if action == "full_pipeline":
        pipeline_start = time.time()

        user_id = body.get("user_id")
        occasion = body.get("occasion")
        vibe_id = body.get("vibe_id")
        price_tier = body.get("price_tier")
        preferred_brands = body.get("preferred_brands") or []
        skin_tone = body.get("skin_tone", "Medium")
        body_shape = body.get("body_shape", "average")
        gender = body.get("gender", "men")
        source_preference = (body.get("source_preference") or body.get("sourcePreference") or "global_market").strip().lower()
        if source_preference not in ("global_market", "my_narrative"):
            source_preference = "global_market"

        user_image = body.get("user_image_data_url") or body.get("user_image")
        user_image = normalize_replicate_image_ref(user_image or "")

        if not all([user_id, occasion, vibe_id]):
            raise ValueError("Missing required fields: user_id, occasion, vibe_id")

        mst_value = SKIN_TONE_TO_MST.get(skin_tone, 5)
        gender_presentation = GENDER_MAP.get(gender, gender or "person")
        body_type = BODY_SHAPE_MAP.get(body_shape, "medium build")

        biometrics_result = {
            "face_detected": True, "monk_skin_tone": mst_value,
            "mst_label": MST_LABELS.get(mst_value, "Medium"),
            "body_type": body_shape.replace("_", " ") if body_shape else "average",
            "gender_presentation": gender_presentation, "confidence": 0.95,
        }

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

        if source_preference == "global_market":
            path_a = _run_path_a_global(client=client, biometrics=biometrics_result, occasion=occasion, vibe_id=vibe_id, user_image=user_image, currency=currency, preferred_brands=preferred_brands, price_tier=price_tier or "")
            recommendation = path_a.get("recommendation", {}) or {}
            affiliate_recommendations = path_a.get("affiliate_recommendations", []) or []
            outfit_pieces = path_a.get("outfit_pieces", []) or []
            final_image_url = path_a.get("final_image_url", "") or ""
            flux_image_url = path_a.get("flux_image_url", "") or ""
            vton_product = path_a.get("vector_top_match")
            global_style_query = path_a.get("style_query", "") or ""
            global_query_category = path_a.get("vector_category", "") or ""
            vton_applied = bool(path_a.get("vton_applied", False))
        else:
            recommendation = generate_my_narrative_recommendation(client=client, biometrics=biometrics_result, occasion=occasion, vibe_id=vibe_id, currency=currency)
            outfit_pieces = recommendation.get("outfit_pieces", [])
            selected_products = recommendation.get("selected_products", [])
            vton_product = selected_products[0] if selected_products else _fallback_my_narrative_selection(occasion, vibe_id)[0]
            vton_img = run_idm_vton(user_image=user_image, garment_image=vton_product.get("flat_lay_url", ""), description=vton_product.get("title", "streetwear top"))
            vton_applied = bool(vton_img)
            final_image_url = vton_img or vton_product.get("flat_lay_url") or "https://placehold.co/768x1024/0b0b0f/39A596?text=MY+NARRATIVE+LOOK"
            for p in selected_products[:3]:
                affiliate_recommendations.append({
                    "product_name": p.get("title"), "brand": "MY NARRATIVE", "price": p.get("price"),
                    "original_price": p.get("price"), "discount_pct": 0, "currency": currency,
                    "affiliate_url": p.get("product_url"), "add_to_cart_url": p.get("product_url"),
                    "exact_product_url": p.get("product_url"), "product_url": p.get("product_url"),
                    "flat_lay_url": p.get("flat_lay_url"), "platform": "MY NARRATIVE",
                    "recommended_for": f"My Narrative {occasion_key} look",
                    "gap_item": {"description": p.get("title"), "is_owned": False},
                })

        pipeline_duration = round(time.time() - pipeline_start, 2)

        return {
            "success": True, "pipeline_duration_seconds": pipeline_duration,
            "biometrics": {"monk_skin_tone": mst_value, "mst_label": MST_LABELS.get(mst_value, "Medium"), "body_type": biometrics_result.get("body_type"), "gender_presentation": biometrics_result.get("gender_presentation"), "confidence": biometrics_result.get("confidence")},
            "ghost_closet": {"success": True, "user_id": user_id, "items_saved": 0, "item_ids": []},
            "wardrobe": {"items_detected": 4, "items": [
                {"id": "wd_1", "slot": "top", "category": "Topwear", "sub_category": recommendation.get("top", {}).get("name", "Stylish Top") if recommendation else "Stylish Top", "color": recommendation.get("top", {}).get("color", "Neutral") if recommendation else "Neutral", "pattern": "solid", "style": "Western", "confidence": 0.95, "description": "AI-recommended top"},
                {"id": "wd_2", "slot": "bottom", "category": "Bottomwear", "sub_category": recommendation.get("bottom", {}).get("name", "Slim Trousers") if recommendation else "Slim Trousers", "color": recommendation.get("bottom", {}).get("color", "Dark") if recommendation else "Dark", "pattern": "solid", "style": "Western", "confidence": 0.93, "description": "AI-recommended bottoms"},
                {"id": "wd_3", "slot": "footwear", "category": "Footwear", "sub_category": recommendation.get("footwear", {}).get("name", "Clean Sneakers") if recommendation else "Clean Sneakers", "color": recommendation.get("footwear", {}).get("color", "White") if recommendation else "White", "pattern": "solid", "style": "Western", "confidence": 0.88, "description": "AI-recommended footwear"},
                {"id": "wd_4", "slot": "accessory", "category": "Accessory", "sub_category": recommendation.get("accessory", {}).get("name", "Watch") if recommendation else "Watch", "color": recommendation.get("accessory", {}).get("color", "Silver") if recommendation else "Silver", "pattern": "solid", "style": "Western", "confidence": 0.78, "description": "AI-recommended accessory"},
            ]},
            "editorial": {"flux_prompt": f"AI-styled {vibe_label} look for {occasion_key}", "flux_image_url": flux_image_url, "final_image_url": final_image_url, "vton_image_url": final_image_url if source_mode == "my_narrative" else "", "vton_applied": vton_applied, "occasion": OCCASION_PRESETS.get(occasion, {}), "vibe": VIBE_PRESETS.get(vibe_id, {}), "source_mode": source_mode},
            "color_theory": {"mst_value": mst_value, "best_colors": color_theory["best_colors"], "avoid_colors": color_theory["avoid"], "undertone_note": color_theory["undertone_note"], "tooltip_text": f"Based on your Monk Skin Tone ({MST_LABELS.get(mst_value)}), {color_theory['undertone_note']} Best colors: {', '.join(color_theory['best_colors'])}."},
            "affiliate_upsells": affiliate_recommendations, "my_narrative_catalog": MY_NARRATIVE_CATALOG,
            "outfit_completion_pct": 100, "source_mode": source_mode, "source_preference": source_mode,
            "vton_applied": vton_applied, "global_style_query": global_style_query, "global_query_category": global_query_category,
            "direction": (recommendation or {}).get("direction") or (recommendation or {}).get("outfit_description") or f"Styled {vibe_label} look for {occasion_key}.",
            "outfit_pieces": outfit_pieces,
            "suggestions": (recommendation or {}).get("suggestions") or (recommendation or {}).get("styling_tips") or [],
            "styling_tips": (recommendation or {}).get("styling_tips") or [],
            "color_science": (recommendation or {}).get("color_science_note") or color_theory.get("undertone_note", ""),
            "my_narrative_product": vton_product if source_mode == "my_narrative" else None,
            "gamification": get_gamification_state(user_id),
            "user_profile_data": {
                "physique": {"skin_tone": mst_value, "skin_tone_label": MST_LABELS.get(mst_value, "Medium"), "body_type": biometrics_result.get("body_type"), "gender": biometrics_result.get("gender_presentation")},
                "color_theory": {"best_colors": color_theory["best_colors"], "avoid_colors": color_theory["avoid"], "undertone_note": color_theory["undertone_note"]},
                "profile_face_card_url": final_image_url, "generated_at": time.time(),
            },
            "recommendation": recommendation,
        }

    raise ValueError(f"Unknown action: '{action}'. Valid: full_pipeline, get_vibes, get_occasions, get_gamification, ingest_affiliate_feed, search_global_inventory")


# ═════════════════════════════════════════════════════════════════════════════
# VIRTUAL TRY-ON — IDM-VTON and FLUX
# ═════════════════════════════════════════════════════════════════════════════

def _handle_virtual_try_on(body):
    if not REPLICATE_AVAILABLE:
        raise ValueError("replicate package not installed")
    token = os.environ.get("REPLICATE_API_TOKEN")
    if not token:
        raise ValueError("REPLICATE_API_TOKEN is not set")

    client_replicate = replicate.Client(api_token=token)
    mode = body.get('mode', 'flux')

    if mode == 'vton':
        human_img = body.get('user_image')
        garm_img = body.get('garment_image')
        category = body.get('category', 'upper_body')
        try:
            model = client_replicate.models.get("cuuupid/idm-vton")
            version_id = model.latest_version.id
        except Exception:
            version_id = "c871bb9b046607b680449ecbae55fd8c6d945e0a1948644bf2361b3d021d3ff4"
        output = client_replicate.run(
            f"cuuupid/idm-vton:{version_id}",
            input={"human_img": human_img, "garm_img": garm_img, "garment_des": body.get('description', "clothing item"), "category": category, "crop": False, "seed": 42, "steps": 30, "force_dc": False, "mask_only": False}
        )
        output_url = str(output) if hasattr(output, '__str__') else output
    elif mode == 'flux':
        prompt = body.get('prompt')
        if not prompt:
            gender = body.get('gender', 'man')
            skin = body.get('skin', 'medium')
            outfit = body.get('outfit', 'stylish streetwear')
            context = body.get('context', 'studio lighting')
            prompt = f"A photorealistic full-body shot of an Indian {gender} with {skin} skin tone, wearing {outfit}. Background is {context}. Cinematic lighting, 4k, texture rich, fashion photography."
        output = client_replicate.run("black-forest-labs/flux-schnell", input={"prompt": prompt, "aspect_ratio": "3:4", "num_inference_steps": 4})
        generated_image_url = output[0]
        user_face = body.get('user_image')
        if user_face:
            swap_output = client_replicate.run(
                "lucataco/faceswap:9a4298548422074c3f57258c5d544497314ae4112df80d116f0d2109bd068e9c",
                input={"target_image": generated_image_url, "swap_image": user_face}
            )
            output_url = str(swap_output)
        else:
            output_url = generated_image_url
    else:
        raise ValueError(f"Unknown mode: {mode}")

    return {"success": True, "image": output_url}


# ═════════════════════════════════════════════════════════════════════════════
# VERCEL SERVERLESS HANDLER — Path-based routing
# ═════════════════════════════════════════════════════════════════════════════

class handler(BaseHTTPRequestHandler):

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS, GET")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Max-Age", "86400")

    def _respond(self, status: int, data: dict):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self._cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors_headers()
        self.end_headers()

    def do_GET(self):
        self._respond(200, {
            "service": "Fashion Services",
            "endpoints": {
                "POST /api/fashion/consultant": "AI Fashion Consultant (self/gift mode)",
                "POST /api/fashion/pipeline": "Full AI Stylist Pipeline (with brand search)",
                "POST /api/fashion/try-on": "Virtual Try-On (IDM-VTON / FLUX)",
                "POST /api/fashion/pipeline (action=upload_brand_catalog)": "Upload brand catalog (CSV/JSON)",
                "POST /api/fashion/pipeline (action=search_brand_catalog)": "Search brand catalog products",
                "POST /api/fashion/pipeline (action=get_brand_catalogs)": "List all brands in catalog",
                "POST /api/fashion/pipeline (action=delete_brand_catalog)": "Soft-delete brand catalog",
                "POST /api/fashion/pipeline (action=search_brands_for_occasion)": "Search brands by occasion + price tier",
            }
        })

    def do_POST(self):
        try:
            from urllib.parse import urlparse
            parsed = urlparse(self.path)
            path = parsed.path.rstrip('/')
            currency = detect_currency_from_headers(self.headers)

            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                body = {}
            else:
                body = json.loads(self.rfile.read(content_length))
            body["_currency"] = currency

            if path == '/api/fashion/consultant':
                result = _handle_fashion_consultant(body)
                self._respond(200, result)

            elif path == '/api/fashion/pipeline':
                result = _handle_stylist_pipeline(body)
                self._respond(200, result)

            elif path == '/api/fashion/try-on':
                result = _handle_virtual_try_on(body)
                self._respond(200, result)

            else:
                self._respond(404, {"error": "Not found. Use /api/fashion/consultant, /api/fashion/pipeline, or /api/fashion/try-on"})

        except json.JSONDecodeError as e:
            self._respond(400, {"success": False, "error": f"Invalid JSON: {e}"})
        except ValueError as e:
            self._respond(400, {"success": False, "error": str(e)})
        except Exception as e:
            error_msg = str(e)
            if '402' in error_msg or 'payment' in error_msg.lower() or 'credit' in error_msg.lower():
                error_msg = '💳 Replicate credits exhausted. Add credits at replicate.com/account/billing'
            elif '422' in error_msg or 'version' in error_msg.lower():
                error_msg = '⚠️ AI model version error. Please contact support.'
            elif '401' in error_msg or 'unauthorized' in error_msg.lower() or 'token' in error_msg.lower():
                error_msg = '🔑 Invalid REPLICATE_API_TOKEN. Please check your Vercel environment variables.'
            self._respond(500, {"success": False, "error": error_msg})

    def log_message(self, format, *args):
        pass
