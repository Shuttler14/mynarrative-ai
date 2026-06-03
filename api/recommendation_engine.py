"""
================================================================================
  MY NARRATIVE AI — UNIFIED OUTFIT RECOMMENDATION ENGINE
  api/recommendation_engine.py
================================================================================

  PURPOSE:
  Vercel Serverless Function that orchestrates AI outfit recommendations
  with deep Indian cultural context, marketplace product matching via
  Supabase vector search, and optional auto-trigger virtual try-on.

  ACTIONS:
    recommend_outfit  — Full outfit recommendation pipeline
    get_festivals     — Upcoming Indian festivals for a date + region
    get_style_profiles— Available style profiles / archetypes

  ENDPOINT:
    POST /api/recommendation_engine  — All actions via JSON body
    GET  /api/recommendation_engine   — Health check

  COST GUIDE:
    GPT-4o recommendation:        ~₹1.50–₹3.00  per call
    text-embedding-3-small:       ~₹0.02–₹0.05  per piece
    Total per recommendation:     ~₹2.00–₹4.00

  REQUIRED ENVIRONMENT VARIABLES:
  ──────────────────────────────────
  OPENAI_API_KEY      → OpenAI API key (GPT-4o + embeddings)
  SUPABASE_URL        → Supabase project REST URL
  SUPABASE_KEY        → Supabase anon/service key

  OPTIONAL:
  REPLICATE_API_TOKEN → For auto virtual try-on
  VTON_ENDPOINT       → Override VTON compositor URL

================================================================================
"""

from http.server import BaseHTTPRequestHandler
import hashlib
import json
import math
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


# ---------------------------------------------------------------------------
# CONFIGURATION & CONSTANTS
# ---------------------------------------------------------------------------

VERSION = "1.0.0"
SERVICE_NAME = "recommendation_engine"

# Cache TTL: 1 hour
RECOMMENDATION_CACHE_TTL_SECONDS = 3600

# Embedding model — cost-optimised
EMBEDDING_MODEL = "text-embedding-3-small"

# GPT model — quality matters for recommendations
GPT_MODEL = "gpt-4o"


# ---------------------------------------------------------------------------
# MONK SKIN TONE (MST) SCALE — same as stylist_pipeline.py
# ---------------------------------------------------------------------------

MST_LABELS = {
    1: "Very Light", 2: "Light", 3: "Light-Medium", 4: "Medium-Light",
    5: "Medium", 6: "Medium-Tan", 7: "Tan", 8: "Dark-Tan",
    9: "Dark", 10: "Very Dark",
}

MST_COLOR_THEORY = {
    1: {"best": ["Navy", "Emerald", "Burgundy", "Charcoal"], "avoid": ["Pale Yellow", "Beige"], "note": "Cool jewel tones create striking contrast."},
    2: {"best": ["Forest Green", "Plum", "Cobalt Blue", "Rust"], "avoid": ["Neon Yellow"], "note": "Rich earth tones and deep jewels balance lighter skin."},
    3: {"best": ["Teal", "Coral", "Olive", "Mustard"], "avoid": ["Washed-out Pastels"], "note": "Warm mid-tones with subtle saturation work best."},
    4: {"best": ["Burnt Orange", "Royal Blue", "Sage Green", "Maroon"], "avoid": ["Khaki"], "note": "Warm undertones pair beautifully with earth-inspired shades."},
    5: {"best": ["Hot Pink", "Turquoise", "Gold", "Wine Red"], "avoid": ["Muddy Brown"], "note": "Medium tones can carry both warm and cool palettes."},
    6: {"best": ["Tangerine", "Electric Blue", "Lavender", "Cream"], "avoid": ["Dark Brown"], "note": "High-contrast brights create editorial impact."},
    7: {"best": ["White", "Bright Yellow", "Fuchsia", "Sky Blue"], "avoid": ["Dark Navy"], "note": "Vibrant, saturated colors pop against warm tan skin."},
    8: {"best": ["Ivory", "Gold", "Coral Red", "Emerald"], "avoid": ["Charcoal Grey"], "note": "Warm metallics and bright jewel tones celebrate deep warmth."},
    9: {"best": ["White", "Canary Yellow", "Hot Pink", "Cobalt"], "avoid": ["Dark Olive"], "note": "High-saturation pure colors create maximum visual impact."},
    10: {"best": ["Pure White", "Bright Orange", "Electric Green", "Gold"], "avoid": ["Dark Brown", "Black"], "note": "Bold, luminous colors create stunning contrast."},
}

SKIN_TONE_TO_MST = {
    "Fair": 2, "Light": 2, "Medium": 5, "Olive": 4,
    "Brown": 7, "Dark": 9, "Deep": 10,
}

COMPLEXION_MAP = {
    "warm": "warm golden undertone",
    "cool": "cool pinkish undertone",
    "neutral": "neutral balanced undertone",
}

BODY_TYPE_MAP = {
    "slim_athletic": "slim athletic build",
    "average": "average medium build",
    "muscular": "well-built muscular build",
    "plus_size": "plus size build",
    "tall_lean": "tall lean frame",
    "short_stocky": "compact stocky build",
}


# ---------------------------------------------------------------------------
# INDIAN FESTIVAL CALENDAR — static data enriched by region
# ---------------------------------------------------------------------------

FESTIVAL_CALENDAR = [
    {
        "name": "Makar Sankranti / Pongal",
        "months": [1],
        "day_range": (13, 16),
        "regions": ["all"],
        "dress_code": "Traditional regional wear — silk sarees, bright colors for South India; Gujarati kite-festival casuals for West",
        "colors": ["Red", "Orange", "Gold", "Green"],
        "keywords": ["silk saree", "pattu pavadai", "kite festival", "traditional south indian"],
        "style_note": "Pongal (South): Silk sarees, veshti. Sankranti (North/West): Bright festive casuals.",
    },
    {
        "name": "Republic Day",
        "months": [1],
        "day_range": (25, 27),
        "regions": ["all"],
        "dress_code": "Tricolor-inspired smart casuals or Indo-western",
        "colors": ["Saffron", "White", "Green", "Navy"],
        "keywords": ["tricolor outfit", "patriotic fashion"],
        "style_note": "Subtle tri-color accents — saffron pocket square, white kurta, green dupatta.",
    },
    {
        "name": "Holi",
        "months": [3],
        "day_range": (1, 25),
        "regions": ["all"],
        "dress_code": "Whites preferred, disposable casual fabrics, avoid expensive pieces",
        "colors": ["White", "Cream", "Off-White"],
        "keywords": ["white kurta", "holi outfit", "cotton casual"],
        "style_note": "White is mandatory base. Wear old cotton clothes that can take colour. Avoid silk.",
    },
    {
        "name": "Eid ul-Fitr",
        "months": [3, 4],
        "day_range": (1, 31),
        "regions": ["all"],
        "dress_code": "Elegant ethnic — sherwanis, embroidered kurtas, salwar kameez",
        "colors": ["Emerald Green", "Royal Blue", "White", "Gold"],
        "keywords": ["sherwani", "embroidered kurta", "eid outfit", "pathani suit"],
        "style_note": "Emphasis on fine embroidery, luxurious fabrics. Men: sherwani + mojari. Women: anarkali + statement dupatta.",
    },
    {
        "name": "Independence Day",
        "months": [8],
        "day_range": (14, 16),
        "regions": ["all"],
        "dress_code": "Tricolor-themed smart ethnic or casual",
        "colors": ["Saffron", "White", "Green"],
        "keywords": ["independence day outfit", "tricolor"],
        "style_note": "Similar to Republic Day but often more casual — cotton kurtas with tri-color accents.",
    },
    {
        "name": "Onam",
        "months": [8, 9],
        "day_range": (1, 30),
        "regions": ["Kerala", "South", "Kochi", "Thiruvananthapuram", "Kozhikode"],
        "dress_code": "Kerala kasavu — white with gold border, mundu-veshti",
        "colors": ["White", "Gold", "Cream", "Off-White"],
        "keywords": ["kerala kasavu", "mundu", "set saree", "onam outfit"],
        "style_note": "Quintessential Kerala elegance — kasavu sarees with gold zari border, white mundu for men.",
    },
    {
        "name": "Navratri / Durga Puja",
        "months": [9, 10],
        "day_range": (1, 31),
        "regions": ["all"],
        "dress_code": "Nine colors of Navratri, chaniya choli, garba outfits for Gujarat; sarees for Bengal",
        "colors": ["Yellow", "Green", "Grey", "Orange", "White", "Red", "Royal Blue", "Pink", "Purple"],
        "keywords": ["chaniya choli", "garba outfit", "navratri colors", "durga puja saree"],
        "style_note": "Gujarat: chaniya choli + oxidised jewellery for garba. Bengal: silk sarees for Durga Puja pandal-hopping.",
    },
    {
        "name": "Dussehra / Vijayadashami",
        "months": [10],
        "day_range": (1, 20),
        "regions": ["all"],
        "dress_code": "Rich ethnic — silk kurtas, traditional sarees",
        "colors": ["Red", "Gold", "Maroon", "Orange"],
        "keywords": ["dussehra outfit", "vijayadashami", "silk kurta"],
        "style_note": "Victory vibes — bold reds and golds. South India: silk pattu sarees. North: embroidered kurtas.",
    },
    {
        "name": "Diwali",
        "months": [10, 11],
        "day_range": (1, 30),
        "regions": ["all"],
        "dress_code": "Rich fabrics, gold accents, heavy traditional ethnic",
        "colors": ["Gold", "Red", "Maroon", "Royal Blue", "Deep Purple"],
        "keywords": ["diwali outfit", "heavy ethnic", "gold accents", "silk kurta", "lehenga"],
        "style_note": "The grand Indian festival — go all out. Men: brocade sherwanis, silk kurtas. Women: lehengas, heavy sarees, anarkalis.",
    },
    {
        "name": "Christmas / New Year",
        "months": [12, 1],
        "day_range": (20, 5),
        "regions": ["all"],
        "dress_code": "Western party wear, cocktail dresses, smart-casual celebration looks",
        "colors": ["Red", "Green", "Gold", "Black", "Silver", "White"],
        "keywords": ["christmas party", "new year outfit", "cocktail dress", "party wear"],
        "style_note": "Western-leaning celebration wear — sequins allowed. Mix Indo-western for unique flair.",
    },
]


# ---------------------------------------------------------------------------
# REGIONAL STYLE MAP
# ---------------------------------------------------------------------------

REGIONAL_STYLES = {
    "Punjab": {"style": "Phulkari, Patiala suits, bright turbans", "fabrics": ["Phulkari", "Cotton", "Silk"], "brands": ["Manyavar", "FabIndia"], "note": "Bold, colourful, statement-making"},
    "Chandigarh": {"style": "Phulkari, Patiala suits, bright turbans", "fabrics": ["Phulkari", "Cotton", "Silk"], "brands": ["Manyavar", "FabIndia"], "note": "Bold, colourful, statement-making"},
    "Delhi": {"style": "Chikankari, Lucknowi, metro-fusion", "fabrics": ["Chikankari", "Georgette", "Chanderi"], "brands": ["FabIndia", "Good Earth", "Nicobar"], "note": "Mix of traditional and contemporary metro style"},
    "Lucknow": {"style": "Chikankari embroidery, Lucknowi kurtas", "fabrics": ["Chikankari muslin", "Cotton", "Georgette"], "brands": ["FabIndia", "Manyavar"], "note": "Delicate threadwork is the signature"},
    "Mumbai": {"style": "Bollywood-inspired, streetwear fusion, lightweight fabrics", "fabrics": ["Linen", "Cotton", "Rayon"], "brands": ["Snitch", "Rare Rabbit", "Jack & Jones"], "note": "Fashion-forward, comfort-meets-style for humid weather"},
    "Bangalore": {"style": "Smart-casual tech-meets-ethnic, South Indian silk accents", "fabrics": ["Cotton", "Silk", "Linen"], "brands": ["Rare Rabbit", "Jack & Jones", "FabIndia"], "note": "Startup casual with occasional traditional flair"},
    "Chennai": {"style": "Kanjivaram silk, traditional South Indian", "fabrics": ["Kanjivaram Silk", "Cotton", "Madras checks"], "brands": ["Nalli", "FabIndia", "Pothys"], "note": "Silk sarees are wardrobe staples, cotton for daily wear"},
    "Kolkata": {"style": "Tant cotton, Jamdani, intellectual-artistic", "fabrics": ["Tant cotton", "Jamdani", "Tussar silk"], "brands": ["Aarong", "FabIndia", "Byloom"], "note": "Handloom-first aesthetic, artistic draping"},
    "Hyderabad": {"style": "Bidri work accents, Hyderabadi pearls, Indo-Islamic fusion", "fabrics": ["Ikat", "Silk", "Khadi"], "brands": ["Manyavar", "FabIndia", "Kalanjali"], "note": "Nawabi elegance — rich fabrics, pearl accessories"},
    "Jaipur": {"style": "Bandhani, Rajasthani mirror work, block prints", "fabrics": ["Bandhani", "Block print cotton", "Mirror work"], "brands": ["Anokhi", "FabIndia", "Good Earth"], "note": "Heritage crafts — vibrant colours and textile artistry"},
    "Gujarat": {"style": "Bandhani, patola, mirror work", "fabrics": ["Bandhani", "Patola silk", "Mirror work"], "brands": ["FabIndia", "Manyavar"], "note": "Garba-ready chaniya cholis, vibrant textile tradition"},
    "Kerala": {"style": "Kerala kasavu, mundu, minimalist gold-bordered white", "fabrics": ["Kasavu cotton", "White muslin", "Linen"], "brands": ["FabIndia", "Seematti"], "note": "Understated elegance — white and gold is the signature palette"},
    "Goa": {"style": "Beach-casual, resort wear, Indo-Portuguese fusion", "fabrics": ["Linen", "Cotton", "Light silk"], "brands": ["Nicobar", "Bewakoof", "Global Desi"], "note": "Laid-back luxury — resort silhouettes with Indian prints"},
    "North": {"style": "Chikankari, Lucknowi embroidery, shawls", "fabrics": ["Chikankari", "Pashmina", "Chanderi"], "brands": ["FabIndia", "Manyavar", "Raymond"], "note": "Rich textures for cold winters, lightweight for summers"},
    "South": {"style": "Silk sarees, Kanjivaram, temple jewellery", "fabrics": ["Silk", "Cotton", "Handloom"], "brands": ["Nalli", "FabIndia", "Pothys"], "note": "Silk is king — sarees for women, silk kurtas for men"},
    "West": {"style": "Bandhani, mirror work, Bollywood-inspired", "fabrics": ["Bandhani", "Mirror work", "Rayon"], "brands": ["FabIndia", "Snitch", "W"], "note": "Vibrant textiles meets Bollywood glamour"},
    "East": {"style": "Tant, Jamdani, handloom cotton, artistic draping", "fabrics": ["Tant", "Jamdani", "Tussar"], "brands": ["Aarong", "Byloom", "FabIndia"], "note": "Intellectual handloom aesthetic"},
}


# ---------------------------------------------------------------------------
# EVENT DRESS CODE MAP
# ---------------------------------------------------------------------------

EVENT_DRESS_CODES = {
    "wedding_sangeet": {
        "label": "Wedding — Sangeet",
        "direction": "Heavy embroidery, bright colours, dance-friendly silhouettes",
        "must_have": ["embroidered outfit", "statement jewellery", "juttis/mojari"],
        "avoid": ["white", "black", "casual denim"],
        "fabric_preference": ["Silk", "Brocade", "Georgette"],
    },
    "wedding_mehendi": {
        "label": "Wedding — Mehendi",
        "direction": "Yellow/green palette, printed casual ethnic, floral motifs",
        "must_have": ["yellow/green outfit", "floral accessories", "comfortable footwear"],
        "avoid": ["heavy embroidery", "dark colours"],
        "fabric_preference": ["Cotton", "Chanderi", "Printed georgette"],
    },
    "wedding_reception": {
        "label": "Wedding — Reception",
        "direction": "Elegant, muted, sophisticated — think cocktail-meets-ethnic",
        "must_have": ["saree or gown", "structured blazer or bandhgala", "polished footwear"],
        "avoid": ["casual wear", "loud prints"],
        "fabric_preference": ["Satin", "Silk", "Velvet"],
    },
    "wedding_haldi": {
        "label": "Wedding — Haldi",
        "direction": "Yellow is mandatory. Avoid silk (turmeric stains). Fun casual ethnic",
        "must_have": ["yellow outfit", "washable fabric", "waterproof accessories"],
        "avoid": ["silk", "expensive fabrics", "white"],
        "fabric_preference": ["Cotton", "Linen", "Rayon"],
    },
    "diwali": {
        "label": "Diwali",
        "direction": "Rich fabrics, gold accents, traditional glamour",
        "must_have": ["silk/brocade piece", "gold jewellery", "ethnic footwear"],
        "avoid": ["casual western", "athleisure"],
        "fabric_preference": ["Silk", "Brocade", "Velvet"],
    },
    "holi": {
        "label": "Holi",
        "direction": "White base, disposable fabrics, fun casual",
        "must_have": ["white t-shirt/kurta", "old comfortable clothes"],
        "avoid": ["expensive pieces", "silk", "delicate fabrics"],
        "fabric_preference": ["Old cotton", "Polyester blend"],
    },
    "eid": {
        "label": "Eid",
        "direction": "Elegant ethnic — fine embroidery, luxurious fabrics",
        "must_have": ["embroidered kurta/sherwani", "attar/perfume", "traditional footwear"],
        "avoid": ["casual western"],
        "fabric_preference": ["Silk", "Georgette", "Lawn cotton"],
    },
    "navratri": {
        "label": "Navratri",
        "direction": "Nine colours rotation, garba-ready, chaniya choli for women",
        "must_have": ["day-specific colour outfit", "oxidised jewellery", "ghungroo"],
        "avoid": ["plain blacks"],
        "fabric_preference": ["Cotton", "Bandhani", "Mirror work"],
    },
    "pongal": {
        "label": "Pongal / Sankranti",
        "direction": "Traditional South Indian — silk sarees, bright festive colours",
        "must_have": ["silk/pattu outfit", "traditional jewellery"],
        "avoid": ["western casuals"],
        "fabric_preference": ["Kanjivaram silk", "Pattu", "Cotton"],
    },
    "onam": {
        "label": "Onam",
        "direction": "Kerala kasavu — white with gold border, minimal elegance",
        "must_have": ["kasavu saree/mundu", "gold jewellery"],
        "avoid": ["dark colours", "heavy prints"],
        "fabric_preference": ["Kasavu cotton", "White linen"],
    },
    "date_night": {
        "label": "Date Night",
        "direction": "Elevated casual to semi-formal — stylish, confident, approachable",
        "must_have": ["well-fitted outfit", "statement accessory", "good footwear"],
        "avoid": ["athleisure", "over-formal"],
        "fabric_preference": ["Linen", "Cotton blend", "Knit"],
    },
    "office": {
        "label": "Office / Work",
        "direction": "Smart casual to business formal — polished, professional",
        "must_have": ["structured top/shirt", "tailored trousers/saree", "clean footwear"],
        "avoid": ["shorts", "flip-flops", "graphic tees"],
        "fabric_preference": ["Cotton", "Linen", "Wool blend"],
    },
    "party": {
        "label": "Party",
        "direction": "Statement-making party wear — bold, confident, head-turning",
        "must_have": ["statement piece", "party footwear", "bold accessory"],
        "avoid": ["office formals", "athleisure"],
        "fabric_preference": ["Sequin", "Satin", "Velvet"],
    },
    "casual": {
        "label": "Casual / Everyday",
        "direction": "Effortless daily wear — comfortable, stylish, practical",
        "must_have": ["good basics", "comfortable footwear"],
        "avoid": ["over-dressing"],
        "fabric_preference": ["Cotton", "Jersey", "Denim"],
    },
    "airport_look": {
        "label": "Airport Look",
        "direction": "Comfortable yet polished travel wear",
        "must_have": ["comfortable layers", "easy footwear", "crossbody bag"],
        "avoid": ["uncomfortable heels", "heavy embroidery"],
        "fabric_preference": ["Knit", "Stretch cotton", "Linen"],
    },
    "college": {
        "label": "College",
        "direction": "Trendy, youthful, statement streetwear",
        "must_have": ["graphic tee/hoodie", "sneakers", "backpack"],
        "avoid": ["formals"],
        "fabric_preference": ["Cotton", "Denim", "Jersey"],
    },
    "gym": {
        "label": "Gym / Workout",
        "direction": "Performance activewear — breathable, moisture-wicking",
        "must_have": ["dry-fit top", "training shoes", "performance bottoms"],
        "avoid": ["cotton heavy", "denim"],
        "fabric_preference": ["Dry-fit", "Polyester", "Spandex blend"],
    },
    "beach": {
        "label": "Beach / Resort",
        "direction": "Relaxed resort wear — breezy, sun-ready",
        "must_have": ["light shirt/kaftan", "shorts/sarong", "sandals/slides"],
        "avoid": ["heavy fabrics", "dark colours"],
        "fabric_preference": ["Linen", "Cotton", "Rayon"],
    },
}


# ---------------------------------------------------------------------------
# WEATHER MAP — Indian cities typical weather for fabric advice
# ---------------------------------------------------------------------------

CITY_WEATHER = {
    "Delhi": {"summer": "Very hot (40°C+), dry", "winter": "Cold (5-15°C), foggy", "monsoon": "Humid, heavy rain", "default": "Extreme seasons — layer in winter, lightweight in summer"},
    "Mumbai": {"summer": "Hot & extremely humid", "winter": "Mild (18-28°C)", "monsoon": "Very heavy rain", "default": "Humid year-round — breathable fabrics essential"},
    "Bangalore": {"summer": "Pleasant (25-35°C)", "winter": "Cool (15-25°C)", "monsoon": "Moderate rain", "default": "Moderate climate — layering works year-round"},
    "Chennai": {"summer": "Very hot & humid", "winter": "Warm (22-30°C)", "monsoon": "Heavy (Oct-Dec)", "default": "Hot & humid — cotton and linen preferred"},
    "Kolkata": {"summer": "Very hot & humid", "winter": "Cool (12-22°C)", "monsoon": "Heavy", "default": "Humid summers, pleasant winters"},
    "Hyderabad": {"summer": "Hot (35-42°C)", "winter": "Mild (15-28°C)", "monsoon": "Moderate", "default": "Hot summers, pleasant winters"},
    "Jaipur": {"summer": "Scorching (42°C+)", "winter": "Cold (5-18°C)", "monsoon": "Low rainfall", "default": "Desert climate — extreme hot/cold swings"},
    "Pune": {"summer": "Hot (35-40°C)", "winter": "Cool (12-25°C)", "monsoon": "Heavy", "default": "Pleasant except peak summer"},
    "Ahmedabad": {"summer": "Very hot (42°C+)", "winter": "Mild (12-28°C)", "monsoon": "Moderate", "default": "Hot arid climate — lightweight cotton essential"},
    "Chandigarh": {"summer": "Hot (38°C+)", "winter": "Cold (5-15°C)", "monsoon": "Moderate", "default": "North Indian continental — layer for winter"},
    "Lucknow": {"summer": "Very hot (42°C+)", "winter": "Cold (5-15°C)", "monsoon": "Moderate", "default": "UP plains — extreme summers, cold winters"},
    "Kochi": {"summer": "Hot & humid", "winter": "Warm (22-30°C)", "monsoon": "Very heavy", "default": "Tropical — humidity is constant, choose breathable fabrics"},
    "Goa": {"summer": "Hot & humid", "winter": "Pleasant (20-32°C)", "monsoon": "Very heavy", "default": "Coastal tropical — linen and resort wear ideal"},
}


# ---------------------------------------------------------------------------
# STYLE PROFILES / ARCHETYPES
# ---------------------------------------------------------------------------

STYLE_PROFILES = {
    "minimal": {"label": "Minimal", "description": "Clean lines, neutral palette, understated elegance", "keywords": ["basics", "monochrome", "structured"]},
    "ethnic": {"label": "Ethnic", "description": "Traditional Indian wear — kurtas, sarees, ethnic fusion", "keywords": ["kurta", "saree", "ethnic", "handloom"]},
    "indo_western": {"label": "Indo-Western", "description": "Fusion of Indian crafts with western silhouettes", "keywords": ["fusion", "nehru jacket", "modern kurta", "dhoti pants"]},
    "streetwear": {"label": "Streetwear", "description": "Urban street style — oversized, graphic, sneaker culture", "keywords": ["oversized", "graphic", "sneakers", "hoodie"]},
    "smart_casual": {"label": "Smart Casual", "description": "Polished everyday — chinos, polos, loafers", "keywords": ["chinos", "polo", "blazer", "loafers"]},
    "bohemian": {"label": "Bohemian", "description": "Free-spirited — prints, layers, earthy tones", "keywords": ["boho", "prints", "earthy", "layered"]},
    "preppy": {"label": "Preppy", "description": "Classic academic — oxfords, sweaters, structured fits", "keywords": ["oxford", "sweater vest", "structured", "classic"]},
    "athletic": {"label": "Athletic / Athleisure", "description": "Sporty meets casual — joggers, sneakers, performance fabrics", "keywords": ["joggers", "sneakers", "dry-fit", "sporty"]},
}


# ---------------------------------------------------------------------------
# INDIAN BRAND KNOWLEDGE
# ---------------------------------------------------------------------------

INDIAN_BRANDS = {
    "men_ethnic": ["Manyavar", "FabIndia", "Raymond", "Peter England", "Louis Philippe"],
    "women_ethnic": ["Biba", "W", "Global Desi", "FabIndia", "Libas", "Aurelia"],
    "men_casual": ["Rare Rabbit", "Jack & Jones", "Snitch", "Bewakoof", "H&M", "Zara"],
    "women_casual": ["Urbanic", "H&M", "Zara", "ONLY", "Vero Moda", "Bewakoof"],
    "unisex_streetwear": ["Bewakoof", "Snitch", "The Souled Store", "Bonkers Corner"],
    "premium": ["Good Earth", "Nicobar", "Raw Mango", "Tarun Tahiliani", "Sabyasachi"],
    "footwear": ["Woodland", "Red Tape", "Metro", "Bata", "Puma India", "Nike India"],
    "accessories": ["Titan", "Fastrack", "Chumbak", "Accessorize"],
}


# ---------------------------------------------------------------------------
# RECOMMENDATION MODES
# ---------------------------------------------------------------------------

RECOMMENDATION_MODES = {
    "event_driven": "Build a complete outfit for a specific event or occasion",
    "style_upgrade": "Upgrade the user's existing style with strategic additions",
    "budget_outfit": "Maximum style impact within strict budget constraints",
    "seasonal_refresh": "Seasonal wardrobe refresh based on upcoming weather changes",
    "mix_and_match": "Build an outfit around an anchor piece from the user's closet",
}


# ---------------------------------------------------------------------------
# SUPABASE REST HELPERS (mirrors stylist_pipeline.py pattern)
# ---------------------------------------------------------------------------

def _sb_headers() -> Tuple[str, str, dict]:
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_KEY", "").strip()
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    return url, key, headers


def _sb_configured() -> bool:
    url, key, _ = _sb_headers()
    return bool(url and key)


def _sb_request(method: str, path: str, payload: Any = None,
                extra_headers: Optional[dict] = None,
                timeout: int = 20) -> Tuple[Any, Optional[str]]:
    """Execute a Supabase REST API request. Returns (data, error_string)."""
    url, key, headers = _sb_headers()
    if not url or not key:
        return None, "supabase_not_configured"
    if extra_headers:
        headers.update(extra_headers)
    full_url = f"{url.rstrip('/')}{path}"
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(full_url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
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


# ---------------------------------------------------------------------------
# OPENAI HELPERS
# ---------------------------------------------------------------------------

def _get_openai_client() -> Tuple[Optional["OpenAI"], Optional[str]]:
    """Initialize OpenAI client. Returns (client, error)."""
    if not OPENAI_AVAILABLE:
        return None, "openai package not installed. Run: pip install openai"
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None, "OPENAI_API_KEY is not set in environment variables."
    return OpenAI(api_key=api_key), None


def _get_text_embedding(client: "OpenAI", text: str) -> list:
    """Generate text embedding using text-embedding-3-small."""
    text = (text or "").strip()
    if not text:
        return []
    try:
        result = client.embeddings.create(model=EMBEDDING_MODEL, input=text)
        vec = result.data[0].embedding if result and result.data else []
        return vec if isinstance(vec, list) else []
    except Exception as e:
        print(f"⚠️ [embedding] {e}")
        return []


def _cosine_similarity(a: list, b: list) -> float:
    """Compute cosine similarity between two vectors."""
    if not a or not b:
        return 0.0
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    dot = na = nb = 0.0
    for i in range(n):
        x, y = float(a[i] or 0.0), float(b[i] or 0.0)
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


# ---------------------------------------------------------------------------
# CACHE HELPERS
# ---------------------------------------------------------------------------

def _build_cache_key(user_id: str, event: str, mode: str,
                     budget_min: float, budget_max: float,
                     gender: str) -> str:
    """Deterministic SHA-256 cache key for recommendation deduplication."""
    raw = f"{user_id}|{event}|{mode}|{budget_min}|{budget_max}|{gender}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _cache_lookup(cache_key: str) -> Tuple[Optional[dict], Optional[str]]:
    """Check recommendation_cache for a valid (non-expired) entry."""
    if not _sb_configured():
        return None, None
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    path = (
        f"/rest/v1/recommendation_cache"
        f"?cache_key=eq.{urllib.parse.quote(cache_key)}"
        f"&expires_at=gt.{urllib.parse.quote(now_iso)}"
        f"&select=recommendation,marketplace_matches"
        f"&limit=1"
    )
    data, err = _sb_request("GET", path)
    if err:
        print(f"⚠️ [cache_lookup] {err}")
        return None, err
    if isinstance(data, list) and data:
        print(f"✅ [cache] HIT for {cache_key[:16]}...")
        return data[0], None
    return None, None


def _cache_store(cache_key: str, user_id: str, recommendation: dict,
                 marketplace_matches: list):
    """Store recommendation in cache with TTL."""
    if not _sb_configured():
        return
    expires = time.strftime(
        "%Y-%m-%dT%H:%M:%SZ",
        time.gmtime(time.time() + RECOMMENDATION_CACHE_TTL_SECONDS),
    )
    row = {
        "cache_key": cache_key,
        "user_id": user_id,
        "recommendation": json.dumps(recommendation) if isinstance(recommendation, dict) else recommendation,
        "marketplace_matches": json.dumps(marketplace_matches) if isinstance(marketplace_matches, list) else marketplace_matches,
        "expires_at": expires,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    extra = {"Prefer": "resolution=merge-duplicates,return=minimal"}
    _, err = _sb_request("POST", "/rest/v1/recommendation_cache", row, extra_headers=extra)
    if err:
        print(f"⚠️ [cache_store] {err}")
    else:
        print(f"💾 [cache] Stored for {cache_key[:16]}...")


# ---------------------------------------------------------------------------
# STEP 1 — INDIAN CULTURAL CONTEXT BUILDER
# ---------------------------------------------------------------------------

def _get_current_season(month: int) -> str:
    """Return Indian season name for a given month."""
    if month in (3, 4, 5):
        return "summer"
    elif month in (6, 7, 8, 9):
        return "monsoon"
    elif month in (10, 11):
        return "autumn"
    else:
        return "winter"


def _get_upcoming_festivals(date_str: str = "", region: str = "",
                            lookahead_days: int = 30) -> List[dict]:
    """Return festivals upcoming within lookahead_days from date, optionally filtered by region."""
    try:
        if date_str:
            dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        else:
            dt = datetime.utcnow()
    except (ValueError, TypeError):
        dt = datetime.utcnow()

    region_lower = (region or "").strip().lower()
    results = []

    for fest in FESTIVAL_CALENDAR:
        # Check if current month or next month overlaps with festival months
        for month_offset in range(2):  # check current and next month
            check_date = dt + timedelta(days=month_offset * 30)
            if check_date.month in fest["months"]:
                # Region filter
                if "all" not in fest["regions"]:
                    if region_lower and not any(
                        r.lower() in region_lower or region_lower in r.lower()
                        for r in fest["regions"]
                    ):
                        continue

                results.append({
                    "name": fest["name"],
                    "dress_code": fest["dress_code"],
                    "colors": fest["colors"],
                    "style_note": fest["style_note"],
                    "keywords": fest["keywords"],
                })
                break  # avoid duplicates

    return results


def _build_cultural_context(event: str, location: str, gender: str,
                            date_str: str = "") -> str:
    """
    Build a rich cultural context string combining:
    - Festival calendar
    - Regional styles
    - Event dress codes
    - Weather / climate
    """
    parts = []

    # 1. Event dress code
    event_info = EVENT_DRESS_CODES.get(event)
    if event_info:
        parts.append(f"EVENT DRESS CODE — {event_info['label']}:")
        parts.append(f"  Direction: {event_info['direction']}")
        parts.append(f"  Must-have: {', '.join(event_info['must_have'])}")
        parts.append(f"  Avoid: {', '.join(event_info['avoid'])}")
        parts.append(f"  Preferred fabrics: {', '.join(event_info['fabric_preference'])}")

    # 2. Regional style
    region_key = (location or "").strip()
    region_info = None
    for key, val in REGIONAL_STYLES.items():
        if key.lower() in region_key.lower() or region_key.lower() in key.lower():
            region_info = val
            region_key = key
            break
    if region_info:
        parts.append(f"\nREGIONAL STYLE — {region_key}:")
        parts.append(f"  Style: {region_info['style']}")
        parts.append(f"  Signature fabrics: {', '.join(region_info['fabrics'])}")
        parts.append(f"  Note: {region_info['note']}")

    # 3. Weather
    city_key = (location or "").strip()
    weather_info = None
    for key, val in CITY_WEATHER.items():
        if key.lower() in city_key.lower() or city_key.lower() in key.lower():
            weather_info = val
            city_key = key
            break
    if weather_info:
        now = datetime.utcnow()
        season = _get_current_season(now.month)
        season_weather = weather_info.get(season, weather_info.get("default", ""))
        parts.append(f"\nWEATHER — {city_key} ({season}):")
        parts.append(f"  {season_weather}")
        parts.append(f"  General: {weather_info.get('default', '')}")

    # 4. Upcoming festivals
    festivals = _get_upcoming_festivals(date_str=date_str, region=location)
    if festivals:
        parts.append("\nUPCOMING FESTIVALS:")
        for f in festivals[:3]:
            parts.append(f"  • {f['name']}: {f['dress_code']}")
            parts.append(f"    Style note: {f['style_note']}")

    return "\n".join(parts) if parts else "General Indian fashion context — versatile, contemporary with ethnic sensibility."


# ---------------------------------------------------------------------------
# STEP 2 — GPT-4o RECOMMENDATION GENERATION
# ---------------------------------------------------------------------------

def _build_gpt_prompt(body: dict, cultural_context: str) -> str:
    """Build the complete GPT-4o prompt for outfit recommendation."""
    # Extract body profile
    profile = body.get("body_profile", {})
    skin_tone = profile.get("skin_tone", "Medium")
    body_type = profile.get("body_type", "average")
    height = profile.get("height_cm", 170)
    complexion = profile.get("complexion", "neutral")

    # MST color science
    mst = SKIN_TONE_TO_MST.get(skin_tone, 5)
    color_data = MST_COLOR_THEORY.get(mst, MST_COLOR_THEORY[5])
    best_colors = ", ".join(color_data["best"])
    avoid_colors = ", ".join(color_data["avoid"])
    color_note = color_data["note"]

    # Body type description
    body_desc = BODY_TYPE_MAP.get(body_type, body_type)
    complexion_desc = COMPLEXION_MAP.get(complexion, complexion)

    # Mode
    mode = body.get("mode", "event_driven")
    mode_desc = RECOMMENDATION_MODES.get(mode, RECOMMENDATION_MODES["event_driven"])

    # Event
    event = body.get("event", "casual")
    event_info = EVENT_DRESS_CODES.get(event, {})
    event_label = event_info.get("label", event.replace("_", " ").title())

    # Budget
    budget_min = body.get("budget_min", 500)
    budget_max = body.get("budget_max", 5000)

    # Gender
    gender = body.get("gender", "unisex")

    # Style preferences
    prefs = body.get("style_preferences", [])
    style_prefs = ", ".join(prefs) if prefs else "versatile"

    # Existing closet
    closet = body.get("existing_closet_items", [])
    closet_str = ", ".join(closet) if closet else "No closet items provided"

    # Anchor piece (for mix_and_match)
    anchor = body.get("anchor_piece", "")

    # Location
    location = body.get("location", "")

    # Brand knowledge
    if gender == "men":
        brands = INDIAN_BRANDS["men_ethnic"] + INDIAN_BRANDS["men_casual"]
    elif gender == "women":
        brands = INDIAN_BRANDS["women_ethnic"] + INDIAN_BRANDS["women_casual"]
    else:
        brands = INDIAN_BRANDS["unisex_streetwear"] + INDIAN_BRANDS["men_casual"]
    brand_str = ", ".join(list(dict.fromkeys(brands)))  # deduplicate

    prompt = f"""You are the AI Outfit Architect at MY NARRATIVE — a psychology-first styling engine deeply rooted in Indian fashion culture.

═══════════════════════════════════════════
USER PROFILE
═══════════════════════════════════════════

• Skin Tone: {skin_tone} (Monk Scale {mst}/10)
• Body Type: {body_desc}
• Height: {height} cm
• Complexion: {complexion_desc}
• Gender: {gender}
• Location: {location or 'Not specified'}
• Style Preferences: {style_prefs}

═══════════════════════════════════════════
COLOR SCIENCE (Monk Skin Tone based)
═══════════════════════════════════════════

Best colors: {best_colors}
Avoid: {avoid_colors}
Note: {color_note}

═══════════════════════════════════════════
RECOMMENDATION MODE: {mode.upper().replace('_', ' ')}
═══════════════════════════════════════════

{mode_desc}

═══════════════════════════════════════════
EVENT: {event_label}
═══════════════════════════════════════════

{cultural_context}

═══════════════════════════════════════════
BUDGET: ₹{budget_min} — ₹{budget_max}
═══════════════════════════════════════════

Total outfit cost MUST stay within this range. All prices in INR (₹).

═══════════════════════════════════════════
EXISTING CLOSET
═══════════════════════════════════════════

{closet_str}

IMPORTANT: If any recommended piece closely matches an item in the user's closet, set "owned": true and "owned_match": "the matching closet item name". This helps minimize spend.

{"═══════════════════════════════════════════" if anchor else ""}
{"ANCHOR PIECE (build outfit around this): " + anchor if anchor else ""}
{"═══════════════════════════════════════════" if anchor else ""}

═══════════════════════════════════════════
BRAND AWARENESS (Indian market)
═══════════════════════════════════════════

Recommend from these brands where possible: {brand_str}
Also consider: Manyavar, FabIndia, Raymond, Biba, W, Global Desi, Rare Rabbit, Jack & Jones, Bewakoof, Snitch, Urbanic

═══════════════════════════════════════════
RESPONSE FORMAT (Strict JSON)
═══════════════════════════════════════════

{{
  "outfit_concept": "2-3 sentence styling direction explaining the creative vision",
  "pieces": [
    {{
      "slot": "top|bottom|footwear|accessory|outerwear|dupatta",
      "name": "Embroidered Silk Kurta",
      "color": "Royal Blue",
      "hex": "#2B4F9E",
      "fabric": "Silk",
      "pattern": "Chikankari embroidery",
      "style": "ethnic",
      "search_query": "men royal blue silk chikankari kurta",
      "price_range": {{"min": 1200, "max": 2500}},
      "owned": false,
      "owned_match": null
    }}
  ],
  "color_palette": ["#2B4F9E", "#F5E6CC", "#8B4513"],
  "styling_tips": ["tip 1", "tip 2", "tip 3"],
  "cultural_note": "Why this outfit works for this event in Indian context",
  "brand_suggestions": ["Fabindia", "Manyavar", "Raymond"],
  "total_estimated_cost": 4500
}}

RULES:
1. Generate 4-6 pieces for a COMPLETE head-to-toe look (top + bottom + footwear + at least 1 accessory).
2. Each piece must have a specific, searchable "search_query" for marketplace matching.
3. Mark pieces from the user's closet as "owned": true, "owned_match": "matching item".
4. Keep total_estimated_cost within ₹{budget_min}–₹{budget_max} (owned pieces cost ₹0).
5. Use culturally appropriate suggestions for the event and region.
6. Include Indian brands in brand_suggestions.
7. "hex" must be a valid hex colour code matching the "color" field.
8. "style" must be one of: minimal, ethnic, indo-western, streetwear, smart-casual, bohemian, preppy, athletic, formal.
"""
    return prompt


def _generate_recommendation(client: "OpenAI", body: dict,
                             cultural_context: str) -> Tuple[dict, Optional[str]]:
    """Call GPT-4o to generate outfit recommendation. Returns (recommendation, error)."""
    prompt = _build_gpt_prompt(body, cultural_context)

    try:
        print(f"🤖 [GPT-4o] Generating recommendation...")
        t_start = time.time()

        completion = client.chat.completions.create(
            model=GPT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a world-class Indian fashion stylist AI. "
                        "Always respond with valid JSON. Be specific, culturally "
                        "aware, and body-positive in all recommendations."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.85,
        )

        result = json.loads(completion.choices[0].message.content)
        elapsed = int((time.time() - t_start) * 1000)
        print(f"✅ [GPT-4o] Recommendation generated in {elapsed}ms — "
              f"{len(result.get('pieces', []))} pieces")
        return result, None

    except json.JSONDecodeError as e:
        print(f"❌ [GPT-4o] JSON parse error: {e}")
        return {}, f"GPT returned invalid JSON: {e}"
    except Exception as e:
        print(f"❌ [GPT-4o] Error: {e}")
        return {}, str(e)


# ---------------------------------------------------------------------------
# STEP 3 — MARKETPLACE PRODUCT MATCHING
# ---------------------------------------------------------------------------

def _match_single_piece(client: "OpenAI", piece: dict) -> dict:
    """
    Match a single outfit piece to global_inventory via vector similarity.
    Returns the match result dict.
    """
    search_query = piece.get("search_query", "")
    slot = piece.get("slot", "")

    if not search_query:
        return {
            "slot": slot,
            "recommended": piece,
            "matched_product": None,
            "flat_lay_available": False,
            "match_method": "no_query",
        }

    # Generate embedding
    embedding = _get_text_embedding(client, search_query)
    if not embedding:
        return {
            "slot": slot,
            "recommended": piece,
            "matched_product": None,
            "flat_lay_available": False,
            "match_method": "embedding_failed",
        }

    # Try RPC match first
    payload = {
        "query_embedding": embedding,
        "query_category": None,
        "match_count": 3,
    }
    matches, err = _sb_request("POST", "/rest/v1/rpc/match_global_inventory", payload)

    # Fallback to manual cosine similarity if RPC fails
    if err or not matches:
        print(f"⚠️ [match] RPC failed for '{slot}', trying fallback: {err}")
        matches, err = _fallback_similarity_search(embedding, limit=3)

    if err or not matches:
        return {
            "slot": slot,
            "recommended": piece,
            "matched_product": None,
            "flat_lay_available": False,
            "match_method": "no_match",
            "search_query": search_query,
        }

    # Pick best match
    best = matches[0] if isinstance(matches, list) else None
    if not best:
        return {
            "slot": slot,
            "recommended": piece,
            "matched_product": None,
            "flat_lay_available": False,
            "match_method": "empty_result",
            "search_query": search_query,
        }

    flat_lay_url = best.get("flat_lay_url") or best.get("image_url", "")

    return {
        "slot": slot,
        "recommended": piece,
        "matched_product": {
            "id": best.get("id"),
            "title": best.get("title", ""),
            "brand": best.get("brand", ""),
            "price": float(best.get("price", 0)),
            "currency": best.get("currency", "INR"),
            "image_url": best.get("image_url", ""),
            "flat_lay_url": flat_lay_url,
            "checkout_url": best.get("checkout_url") or best.get("affiliate_url", ""),
            "source_platform": best.get("network", ""),
            "similarity": float(best.get("similarity", 0)),
        },
        "flat_lay_available": bool(flat_lay_url),
        "match_method": "vector_search",
    }


def _fallback_similarity_search(query_embedding: list, category: str = "",
                                limit: int = 3) -> Tuple[list, Optional[str]]:
    """Fallback cosine similarity search against global_inventory rows."""
    cat = (category or "").strip().lower()
    path = (
        "/rest/v1/global_inventory"
        "?select=id,network,title,brand,category,price,currency,"
        "image_url,flat_lay_url,checkout_url,affiliate_url,embedding,quality_score"
        "&is_clean=eq.true&limit=120"
    )
    if cat:
        path += f"&category=eq.{urllib.parse.quote(cat)}"

    rows, err = _sb_request("GET", path)
    if err:
        return [], err

    scored = []
    for row in (rows or []):
        emb = row.get("embedding")
        if not isinstance(emb, list):
            continue
        sim = _cosine_similarity(query_embedding, emb)
        item = dict(row)
        item["similarity"] = round(sim, 6)
        scored.append(item)

    scored.sort(key=lambda x: x.get("similarity", 0.0), reverse=True)
    return scored[:max(1, min(20, limit))], None


def _match_marketplace_products(client: "OpenAI",
                                pieces: list) -> List[dict]:
    """
    Match all non-owned pieces to marketplace products.
    Uses threading for parallel embedding + search.
    """
    results = []
    non_owned = []

    for piece in pieces:
        if piece.get("owned"):
            results.append({
                "slot": piece.get("slot", ""),
                "recommended": piece,
                "matched_product": None,
                "flat_lay_available": False,
                "match_method": "owned",
            })
        else:
            non_owned.append(piece)

    if not non_owned or not _sb_configured():
        # Return without marketplace matching
        for piece in non_owned:
            results.append({
                "slot": piece.get("slot", ""),
                "recommended": piece,
                "matched_product": None,
                "flat_lay_available": False,
                "match_method": "supabase_not_configured" if not _sb_configured() else "none",
            })
        return results

    # Parallel matching via threads
    match_results = [None] * len(non_owned)
    lock = threading.Lock()

    def _match_worker(idx: int, piece: dict):
        try:
            result = _match_single_piece(client, piece)
            with lock:
                match_results[idx] = result
        except Exception as e:
            print(f"⚠️ [match_worker] Error for slot '{piece.get('slot')}': {e}")
            with lock:
                match_results[idx] = {
                    "slot": piece.get("slot", ""),
                    "recommended": piece,
                    "matched_product": None,
                    "flat_lay_available": False,
                    "match_method": f"error:{str(e)[:80]}",
                }

    threads = []
    for i, piece in enumerate(non_owned):
        t = threading.Thread(target=_match_worker, args=(i, piece))
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=25)

    for r in match_results:
        if r is not None:
            results.append(r)

    return results


# ---------------------------------------------------------------------------
# STEP 4 — AUTO VIRTUAL TRY-ON (optional)
# ---------------------------------------------------------------------------

def _auto_tryon(body_image: str, face_image: str,
                marketplace_matches: list) -> Tuple[str, Optional[str]]:
    """
    Trigger virtual try-on by calling /api/vton_compositor internally.
    Returns (tryon_image_url, error).
    """
    # Collect flat-lay URLs from matched products
    garments = []
    for m in marketplace_matches:
        product = m.get("matched_product")
        if not product:
            continue
        flat_lay = product.get("flat_lay_url", "")
        if not flat_lay:
            continue
        # Determine category based on slot
        slot = m.get("slot", "")
        if slot in ("top", "outerwear"):
            category = "upper_body"
        elif slot in ("bottom",):
            category = "lower_body"
        elif slot in ("dupatta",):
            continue  # Skip dupatta for VTON
        else:
            continue  # Skip accessories, footwear
        garments.append({
            "flat_lay_url": flat_lay,
            "category": category,
            "description": product.get("title", "clothing item"),
        })

    if not garments:
        return "", "no_garments_with_flat_lay"

    # Call VTON compositor
    vton_endpoint = os.environ.get("VTON_ENDPOINT", "").strip()
    if not vton_endpoint:
        # Try internal Vercel function URL
        vercel_url = os.environ.get("VERCEL_URL", "").strip()
        if vercel_url:
            proto = "https" if not vercel_url.startswith("http") else ""
            vton_endpoint = f"{proto}://{vercel_url}/api/vton_compositor" if proto else f"{vercel_url}/api/vton_compositor"
        else:
            return "", "vton_endpoint_not_configured"

    payload = {
        "action": "compose_outfit",
        "body_image": body_image,
        "face_image": face_image or body_image,
        "garments": garments,
        "quality": "preview",
    }

    try:
        print(f"👗 [auto_tryon] Calling VTON with {len(garments)} garments...")
        req_body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            vton_endpoint,
            data=req_body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        if result.get("success"):
            tryon_url = result.get("result_image", "")
            print(f"✅ [auto_tryon] Try-on complete: {tryon_url[:80]}...")
            return tryon_url, None
        else:
            return "", result.get("error", "vton_failed")

    except Exception as e:
        print(f"⚠️ [auto_tryon] Error: {e}")
        return "", str(e)


# ---------------------------------------------------------------------------
# ACTION HANDLERS
# ---------------------------------------------------------------------------

def _action_recommend_outfit(client: "OpenAI", body: dict) -> dict:
    """
    Main recommendation pipeline:
      1. Build Indian cultural context
      2. Check cache
      3. Generate GPT-4o recommendation
      4. Match to marketplace products
      5. Optional auto try-on
      6. Cache & return
    """
    t_start = time.time()

    # ── Extract inputs ──
    user_id = body.get("user_id", "anonymous")
    mode = body.get("mode", "event_driven")
    event = body.get("event", "casual")
    location = body.get("location", "")
    budget_min = float(body.get("budget_min", 500))
    budget_max = float(body.get("budget_max", 5000))
    gender = body.get("gender", "unisex")
    auto_tryon_flag = bool(body.get("auto_tryon", False))
    body_image = body.get("body_image", "")
    face_image = body.get("face_image", "")

    print(f"\n{'━' * 60}")
    print(f"🎯 [recommend_outfit] user={user_id} mode={mode} event={event}")
    print(f"   budget=₹{budget_min}–₹{budget_max} gender={gender} location={location}")
    print(f"{'━' * 60}")

    # ── Validate mode ──
    if mode not in RECOMMENDATION_MODES:
        mode = "event_driven"

    # ── Check cache ──
    cache_key = _build_cache_key(user_id, event, mode, budget_min, budget_max, gender)
    cached, cache_err = _cache_lookup(cache_key)
    if cached:
        recommendation = cached.get("recommendation", {})
        if isinstance(recommendation, str):
            try:
                recommendation = json.loads(recommendation)
            except (json.JSONDecodeError, TypeError):
                recommendation = {}

        marketplace_matches = cached.get("marketplace_matches", [])
        if isinstance(marketplace_matches, str):
            try:
                marketplace_matches = json.loads(marketplace_matches)
            except (json.JSONDecodeError, TypeError):
                marketplace_matches = []

        pieces = recommendation.get("pieces", [])
        owned_count = sum(1 for p in pieces if p.get("owned"))

        return {
            "success": True,
            "cached": True,
            "outfit": recommendation,
            "marketplace_matches": marketplace_matches,
            "tryon_image": None,
            "owned_pieces_count": owned_count,
            "pieces_to_buy": len(pieces) - owned_count,
            "estimated_cost": recommendation.get("total_estimated_cost", 0),
            "cultural_context": _build_cultural_context(event, location, gender),
            "processing_time_ms": int((time.time() - t_start) * 1000),
        }

    # ── Step 1: Build cultural context ──
    print("📚 [Step 1] Building Indian cultural context...")
    cultural_context = _build_cultural_context(event, location, gender)

    # ── Step 2: GPT-4o recommendation ──
    print("🤖 [Step 2] Generating GPT-4o recommendation...")
    recommendation, gpt_err = _generate_recommendation(client, body, cultural_context)
    if gpt_err:
        return {
            "success": False,
            "error": f"Recommendation generation failed: {gpt_err}",
            "processing_time_ms": int((time.time() - t_start) * 1000),
        }

    pieces = recommendation.get("pieces", [])
    owned_count = sum(1 for p in pieces if p.get("owned"))
    non_owned_pieces = [p for p in pieces if not p.get("owned")]

    # ── Step 3: Marketplace matching ──
    print(f"🛒 [Step 3] Matching {len(non_owned_pieces)} pieces to marketplace...")
    marketplace_matches = _match_marketplace_products(client, pieces)

    # ── Step 4: Auto try-on (optional) ──
    tryon_image = None
    if auto_tryon_flag and body_image:
        print("👗 [Step 4] Auto virtual try-on...")
        tryon_url, tryon_err = _auto_tryon(body_image, face_image, marketplace_matches)
        if tryon_url:
            tryon_image = tryon_url
        else:
            print(f"⚠️ [Step 4] Try-on skipped: {tryon_err}")
    else:
        print("⏭️ [Step 4] Auto try-on not requested")

    # ── Cache result ──
    _cache_store(cache_key, user_id, recommendation, marketplace_matches)

    total_time = int((time.time() - t_start) * 1000)
    print(f"🎉 [recommend_outfit] Complete in {total_time}ms — "
          f"{len(pieces)} pieces, {owned_count} owned, "
          f"{len(non_owned_pieces)} to buy")

    return {
        "success": True,
        "cached": False,
        "outfit": recommendation,
        "marketplace_matches": marketplace_matches,
        "tryon_image": tryon_image,
        "owned_pieces_count": owned_count,
        "pieces_to_buy": len(non_owned_pieces),
        "estimated_cost": recommendation.get("total_estimated_cost", 0),
        "cultural_context": cultural_context,
        "processing_time_ms": total_time,
    }


def _action_get_festivals(body: dict) -> dict:
    """Return upcoming Indian festivals for a given date and region."""
    date_str = body.get("date", "")
    region = body.get("region", "")
    lookahead = int(body.get("lookahead_days", 30))

    print(f"🎊 [get_festivals] date={date_str} region={region} lookahead={lookahead}")

    festivals = _get_upcoming_festivals(
        date_str=date_str, region=region, lookahead_days=lookahead,
    )

    # Enrich with dress code suggestions
    enriched = []
    for f in festivals:
        enriched.append({
            "name": f["name"],
            "dress_code": f["dress_code"],
            "recommended_colors": f["colors"],
            "style_note": f["style_note"],
            "search_keywords": f["keywords"],
        })

    return {
        "success": True,
        "date": date_str or datetime.utcnow().strftime("%Y-%m-%d"),
        "region": region or "all",
        "festivals": enriched,
        "count": len(enriched),
    }


def _action_get_style_profiles(body: dict) -> dict:
    """Return available style profiles / archetypes."""
    print("🎨 [get_style_profiles] Returning all profiles")
    profiles = []
    for key, val in STYLE_PROFILES.items():
        profiles.append({
            "id": key,
            "label": val["label"],
            "description": val["description"],
            "keywords": val["keywords"],
        })
    return {
        "success": True,
        "profiles": profiles,
        "count": len(profiles),
    }


# ---------------------------------------------------------------------------
# HEALTH CHECK
# ---------------------------------------------------------------------------

def _health_check() -> dict:
    """Service health check — validate configuration."""
    checks = {
        "openai_package": OPENAI_AVAILABLE,
        "openai_key": bool(os.environ.get("OPENAI_API_KEY", "").strip()),
        "supabase_configured": _sb_configured(),
        "replicate_token": bool(os.environ.get("REPLICATE_API_TOKEN", "").strip()),
    }

    all_ok = checks["openai_package"] and checks["openai_key"]

    return {
        "success": True,
        "status": "healthy" if all_ok else "degraded",
        "service": SERVICE_NAME,
        "version": VERSION,
        "checks": checks,
        "supported_actions": ["recommend_outfit", "get_festivals", "get_style_profiles"],
        "supported_modes": list(RECOMMENDATION_MODES.keys()),
        "supported_events": list(EVENT_DRESS_CODES.keys()),
        "cost_estimate": {
            "per_recommendation": "₹2.00–₹4.00",
            "gpt4o_call": "~₹1.50–₹3.00",
            "embedding_per_piece": "~₹0.02–₹0.05",
        },
    }


# ---------------------------------------------------------------------------
# ACTION ROUTER
# ---------------------------------------------------------------------------

ACTION_MAP = {
    "recommend_outfit": "requires_openai",
    "get_festivals": "standalone",
    "get_style_profiles": "standalone",
}


# ---------------------------------------------------------------------------
# VERCEL SERVERLESS HANDLER
# ---------------------------------------------------------------------------

class handler(BaseHTTPRequestHandler):
    """
    Vercel Serverless Function handler for the Unified Recommendation Engine.

    POST /api/recommendation_engine — All actions via JSON body { "action": "..." }
    GET  /api/recommendation_engine  — Health check
    """

    def _cors_headers(self):
        """Set CORS headers for cross-origin requests."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
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
        self._respond(status, {"success": False, "error": message})

    def _success(self, data: dict):
        self._respond(200, data)

    # --- OPTIONS (CORS preflight) ---
    def do_OPTIONS(self):
        self.send_response(200)
        self._cors_headers()
        self.end_headers()

    # --- GET (Health check) ---
    def do_GET(self):
        try:
            result = _health_check()
            self._success(result)
        except Exception as e:
            self._error(500, f"Health check failed: {str(e)}")

    # --- POST (All actions) ---
    def do_POST(self):
        try:
            # ── Parse request body ──
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length <= 0:
                self._error(400, "Empty request body. Provide valid JSON.")
                return

            # Vercel Hobby plan limit
            MAX_BODY = 4.5 * 1024 * 1024
            if content_length > MAX_BODY:
                self._error(413, "Payload too large. Maximum is 4.5 MB.")
                return

            raw = self.rfile.read(content_length)
            try:
                body = json.loads(raw)
            except json.JSONDecodeError:
                self._error(400, "Invalid JSON in request body.")
                return

            if not isinstance(body, dict):
                self._error(400, "Request body must be a JSON object.")
                return

            # ── Route by action ──
            action = (body.get("action") or "").strip().lower()
            if not action:
                self._error(400,
                    "Missing 'action' field. Supported: "
                    + ", ".join(ACTION_MAP.keys()))
                return

            if action not in ACTION_MAP:
                self._error(400,
                    f"Unknown action: '{action}'. Supported: "
                    + ", ".join(ACTION_MAP.keys()))
                return

            print(f"\n{'━' * 60}")
            print(f"📦 [{SERVICE_NAME}] action={action}")
            print(f"{'━' * 60}")

            # ── Dispatch ──
            action_type = ACTION_MAP[action]

            if action_type == "requires_openai":
                # Initialize OpenAI client
                client, client_err = _get_openai_client()
                if client_err:
                    self._error(500, f"OpenAI configuration error: {client_err}")
                    return

                if action == "recommend_outfit":
                    result = _action_recommend_outfit(client, body)
                else:
                    self._error(400, f"Unhandled action: {action}")
                    return
            else:
                # Standalone actions (no external API needed)
                if action == "get_festivals":
                    result = _action_get_festivals(body)
                elif action == "get_style_profiles":
                    result = _action_get_style_profiles(body)
                else:
                    self._error(400, f"Unhandled action: {action}")
                    return

            # ── Send response ──
            if result.get("success"):
                self._success(result)
            else:
                self._error(500, result.get("error", "Unknown error"))

        except json.JSONDecodeError as e:
            self._error(400, f"Invalid JSON: {e}")
        except Exception as e:
            print(f"💥 [{SERVICE_NAME}] Unhandled error: {e}")
            self._error(500, f"Internal server error: {str(e)}")

    def log_message(self, format, *args):
        """Suppress default BaseHTTPRequestHandler logging."""
        pass
