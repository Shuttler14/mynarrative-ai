"""
Cloth Detection API - Vercel Serverless Function (Enhanced)
===========================================================
Production-grade clothing detection ported from enhanced_cloth_detector.py.
Features: Name normalization, Indian fashion taxonomy, occasion/season detection,
style tags, deduplication, item_id, rich prompt (fit, fabric, gender, sub_category).
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import base64
import re
import uuid

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


# ---------------------------------------------------------------------------
# INDIAN FASHION TAXONOMY
# ---------------------------------------------------------------------------

INDIAN_FASHION_TAXONOMY = {
    "T-Shirt":       {"category": "Topwear",    "style": "Western",    "sub_category": "crew neck"},
    "Shirt":         {"category": "Topwear",    "style": "Western",    "sub_category": "casual shirt"},
    "Hoodie":        {"category": "Topwear",    "style": "Western",    "sub_category": "pullover"},
    "Blouse":        {"category": "Topwear",    "style": "Western",    "sub_category": "crop top"},
    "Jeans":         {"category": "Bottomwear", "style": "Western",    "sub_category": "slim"},
    "Trousers":      {"category": "Bottomwear", "style": "Western",    "sub_category": "formal"},
    "Shorts":        {"category": "Bottomwear", "style": "Western",    "sub_category": "casual"},
    "Skirt":         {"category": "Bottomwear", "style": "Western",    "sub_category": "midi"},
    "Kurta":         {"category": "Topwear",    "style": "Ethnic",     "sub_category": "straight cut"},
    "Kurti":         {"category": "Topwear",    "style": "Ethnic",     "sub_category": "short"},
    "Sherwani":      {"category": "Topwear",    "style": "Ethnic",     "sub_category": "bandhgala"},
    "Nehru Jacket":  {"category": "Topwear",    "style": "Ethnic",     "sub_category": "classic"},
    "Angavastram":   {"category": "Topwear",    "style": "Ethnic",     "sub_category": "drape"},
    "Dhoti":         {"category": "Bottomwear", "style": "Ethnic",     "sub_category": "traditional"},
    "Lungi":         {"category": "Bottomwear", "style": "Ethnic",     "sub_category": "cotton"},
    "Palazzo":       {"category": "Bottomwear", "style": "Ethnic",     "sub_category": "wide leg"},
    "Leggings":      {"category": "Bottomwear", "style": "Ethnic",     "sub_category": "churidar"},
    "Saree":         {"category": "Dress",      "style": "Ethnic",     "sub_category": "cotton"},
    "Lehenga":       {"category": "Dress",      "style": "Ethnic",     "sub_category": "party"},
    "Salwar Kameez": {"category": "Dress",      "style": "Ethnic",     "sub_category": "straight"},
    "Jacket":        {"category": "Outerwear",  "style": "Western",    "sub_category": "denim"},
    "Blazer":        {"category": "Outerwear",  "style": "Formal",     "sub_category": "single breasted"},
    "Coat":          {"category": "Outerwear",  "style": "Western",    "sub_category": "wool"},
    "Dupatta":       {"category": "Accessory",  "style": "Ethnic",     "sub_category": "chiffon"},
    "Scarf":         {"category": "Accessory",  "style": "Western",    "sub_category": "silk"},
    "Mojaris":       {"category": "Footwear",   "style": "Ethnic",     "sub_category": "embroidered"},
    "Juttis":        {"category": "Footwear",   "style": "Ethnic",     "sub_category": "Punjabi"},
    "Kolhapuris":    {"category": "Footwear",   "style": "Ethnic",     "sub_category": "leather"},
    "Footwear":      {"category": "Footwear",   "style": "Western",    "sub_category": ""},
    "Dress":         {"category": "Dress",      "style": "Western",    "sub_category": "midi"},
    "Jewellery":     {"category": "Accessory",  "style": "Ethnic",     "sub_category": ""},
    "Watch":         {"category": "Accessory",  "style": "Western",    "sub_category": ""},
    "Bag":           {"category": "Accessory",  "style": "Western",    "sub_category": ""},
    "Headwear":      {"category": "Accessory",  "style": "Western",    "sub_category": ""},
    "Accessories":   {"category": "Accessory",  "style": "Western",    "sub_category": ""},
}


# ---------------------------------------------------------------------------
# NAME NORMALIZATION (regex -> standard name)
# ---------------------------------------------------------------------------

NAME_NORMALIZATION = [
    (r"\btee\b",                    "T-Shirt"),
    (r"\btshirt\b",                 "T-Shirt"),
    (r"\bpolo\s*shirt\b",           "T-Shirt"),
    (r"\btop\b(?!\s+wear)",         "T-Shirt"),
    (r"\bdenim(s)?\b",              "Jeans"),
    (r"\bdenim\s*jeans\b",          "Jeans"),
    (r"\bpants?\b",                 "Trousers"),
    (r"\bformal\s*pants\b",         "Trousers"),
    (r"\bcargo\s*pants\b",          "Trousers"),
    (r"\bchinos?\b",                "Trousers"),
    (r"\bkurti\b",                  "Kurta"),
    (r"\bkurta\s*set\b",            "Kurta"),
    (r"\banarkali\b",               "Kurta"),
    (r"\bpathani\b",                "Kurta"),
    (r"\bangavastram\b",            "Angavastram"),
    (r"\bsari\b",                   "Saree"),
    (r"\b drape\b",                 "Saree"),
    (r"\bsalwar\s*kameez\b",        "Salwar Kameez"),
    (r"\bsalwar\b",                 "Salwar Kameez"),
    (r"\bsandals?\b",               "Footwear"),
    (r"\bshoes?\b",                 "Footwear"),
    (r"\bsneakers?\b",              "Footwear"),
    (r"\bboots?\b",                 "Footwear"),
    (r"\bheels?\b",                 "Footwear"),
    (r"\bmojaris?\b",               "Mojaris"),
    (r"\bjuttis?\b",                "Juttis"),
    (r"\bkolhapuris?\b",            "Kolhapuris"),
    (r"\bdupatta\b",                "Dupatta"),
    (r"\bodhni\b",                  "Dupatta"),
    (r"\bstole\b",                  "Scarf"),
    (r"\bshawl\b",                  "Scarf"),
    (r"\bpashmina\b",               "Scarf"),
    (r"\bnehru\s*jacket\b",         "Nehru Jacket"),
    (r"\bwaistcoat\b",              "Nehru Jacket"),
    (r"\bghagra\b",                 "Lehenga"),
    (r"\bcholi\b",                  "Lehenga"),
    (r"\blungi\b",                  "Lungi"),
    (r"\bmundu\b",                  "Lungi"),
    (r"\bjhumka\b",                 "Jewellery"),
    (r"\bbangles?\b",               "Jewellery"),
    (r"\bnecklace\b",               "Jewellery"),
    (r"\bearrings?\b",              "Jewellery"),
    (r"\bring\b",                   "Jewellery"),
    (r"\bbracelet\b",               "Jewellery"),
    (r"\bmaang\s*tikka\b",          "Jewellery"),
    (r"\bturban\b",                 "Headwear"),
    (r"\bcap\b",                    "Headwear"),
    (r"\bhat\b",                    "Headwear"),
    (r"\bhandbag\b",                "Bag"),
    (r"\bclutch\b",                 "Bag"),
    (r"\bbackpack\b",               "Bag"),
    (r"\btote\b",                   "Bag"),
    (r"\bpurse\b",                  "Bag"),
    (r"\bbelt\b",                   "Accessories"),
    (r"\bsunglasses?\b",            "Accessories"),
    (r"\btie\b",                    "Accessories"),
]


# ---------------------------------------------------------------------------
# OCCASION KEYWORDS
# ---------------------------------------------------------------------------

OCCASION_KEYWORDS = {
    "Festive":   ["festival", "festive", "wedding", "ceremony", "pooja", "diwali", "holi", "bridal", "reception"],
    "Formal":    ["formal", "office", "business", "professional", "meeting", "suit"],
    "Party":     ["party", "night", "club", "celebration", "cocktail", "evening"],
    "Workwear":  ["office", "work", "professional", "corporate"],
    "Sports":    ["gym", "workout", "sports", "exercise", "running", "athleisure", "jogger"],
    "Beach":     ["beach", "vacation", "swim", "pool", "summer"],
    "Casual":    ["casual", "everyday", "relaxed", "simple", "basic", "daily"],
}


# ---------------------------------------------------------------------------
# SEASON KEYWORDS
# ---------------------------------------------------------------------------

SEASON_KEYWORDS = {
    "Summer":     ["summer", "hot", "lightweight", "cotton", "linen", "breezy"],
    "Winter":     ["winter", "cold", "wool", "warm", "heavy", "knitted", "fleece", "thermal"],
    "Monsoon":    ["rain", "monsoon", "waterproof", "quick dry"],
    "Festive":    ["festival", "wedding", "silk", "embroidery", "zari", "brocade"],
}


# ---------------------------------------------------------------------------
# DETECTION PROMPT (enhanced — matches enhanced_cloth_detector.py quality)
# ---------------------------------------------------------------------------

DETECTION_PROMPT = """You are a fashion vision expert trained in global and Indian clothing styles.

Analyze the uploaded image and do TWO things:

━━━ PART 1: PERSON ANALYSIS ━━━
Analyze the person in the photo and determine:
- gender: "man" / "woman" / "person" (non-binary)
- body_build: "lean" / "athletic" / "broad" / "slim" / "regular" / "heavy"
- skin_tone: "fair" / "wheatish" / "medium" / "dusky" / "deep"
- undertone: "warm" / "cool" / "neutral" (based on visible skin warmth/coolness)
- jewelry_recommendations: Array of 3-5 jewelry types that would suit this person best based on their skin tone, build, and style. Each item should have: type (e.g. "Gold Chain", "Silver Bracelet"), reason (why it suits them), and metal ("gold" / "silver" / "rose_gold" / "oxidized")

━━━ PART 2: CLOTHING DETECTION ━━━
Extract ALL clothing items worn by the person(s).

For EACH detected clothing item, return these fields:
1. name          - Precise garment name, including color/fit descriptor (e.g. "Black Oversized T-Shirt", "Navy Slim Fit Jeans", "Ivory Silk Kurta")
2. confidence    - Your confidence level 0.0-1.0
3. closet_section - Closet section from the list below
4. category      - Topwear / Bottomwear / Dress / Outerwear / Footwear / Accessory
5. description   - One sentence describing the item in detail
6. color         - Primary color (e.g. "Navy Blue", "Ivory White", "Mustard Yellow") or null
7. pattern       - solid / printed / embroidered / striped / floral / checked / geometric / tie-dye / bandhani / block-printed / null
8. fabric        - cotton / silk / denim / linen / chiffon / georgette / velvet / polyester / wool / khadi / null
9. fit           - slim / regular / loose / oversized / relaxed / tailored / flared / null
10. gender       - Men / Women / Unisex
11. style        - Western / Ethnic / Fusion / Athleisure / Formal

CLOSET SECTIONS (classify each item into exactly one):
- Kurta (Kurti, Anarkali, Angavastram, Pathani, Achkan)
- Shirt (formal, casual, oxford, chambray shirts)
- T-Shirt (tees, tops, polos, blouses, tank tops)
- Jeans (denim jeans, all cuts)
- Trousers (pants, chinos, formal trousers, cargo pants)
- Palazzo (wide-leg pants, palazzo trousers)
- Leggings (churidar, salwar, leggings, tights)
- Dhoti
- Lungap (Lungi, Mundu)
- Sherwani
- Nehru Jacket (waistcoat, bandhgala jacket)
- Blazer (blazers, suit jackets, coats)
- Jacket (casual jackets, denim jackets, bomber jackets, hoodies, sweatshirts)
- Saree
- Lehenga (Choli, Ghagra, bridal skirts)
- Chunni (Dupatta, Odhni as head/shoulder drape)
- Scarf (decorative stoles, shawls, pashmina, mufflers)
- Dress (western dresses, gowns, frocks, jumpsuits, co-ord sets)
- Footwear (shoes, sandals, sneakers, boots, heels, juttis, mojaris, kolhapuris, bellies)
- Accessories (belts, sunglasses, ties, pocket squares, watches listed separately)
- Bag (handbags, clutches, backpacks, tote bags, wallets)
- Watch
- Jewellery (bangles, jhumkas, necklaces, earrings, rings, maang tikka, bracelets, nose rings)
- Headwear (hats, caps, turbans, pagdis)
- Topwear (any upper-body garment not in above categories)
- Bottomwear (any lower-body garment not in above categories)

CRITICAL RULES:
- Detect EVERY visible item — shirt under jacket = 2 separate items
- Be specific: "Embroidered Red Silk Kurta" NOT just "Kurta"
- Include accessories, footwear, jewellery if visible
- Do NOT hallucinate items not clearly visible
- Return ONLY a valid raw JSON object — no markdown, no ```json, no explanations

Return format (JSON object with person_analysis and detected_items):
{
  "person_analysis": {
    "gender": "man",
    "body_build": "athletic",
    "skin_tone": "medium",
    "undertone": "warm",
    "jewelry_recommendations": [
      { "type": "Gold Chain", "reason": "Warm undertone complements gold beautifully", "metal": "gold" },
      { "type": "Leather Bracelet", "reason": "Matches the casual athletic build", "metal": "oxidized" },
      { "type": "Analog Watch (Gold)", "reason": "Classic piece that elevates any outfit", "metal": "gold" }
    ]
  },
  "detected_items": [
    {
      "name": "Black Oversized T-Shirt",
      "confidence": 0.94,
      "closet_section": "T-Shirt",
      "category": "Topwear",
      "description": "A relaxed-fit black crew neck t-shirt with minimal design.",
      "color": "Black",
      "pattern": "Solid",
      "fabric": "Cotton",
      "fit": "Oversized",
      "gender": "Unisex",
      "style": "Western"
    }
  ]
}"""


# ---------------------------------------------------------------------------
# NAME NORMALIZATION
# ---------------------------------------------------------------------------

def normalize_name(name: str) -> str:
    name_lower = name.lower().strip()
    for pattern, replacement in NAME_NORMALIZATION:
        if re.search(pattern, name_lower, re.IGNORECASE):
            return replacement
    return name.title()


# ---------------------------------------------------------------------------
# OCCASION DETECTION
# ---------------------------------------------------------------------------

def detect_occasion(name: str, description: str, fabric: str) -> str:
    text = f"{name} {description} {fabric}".lower()
    for occasion, keywords in OCCASION_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return occasion
    return "Casual"


# ---------------------------------------------------------------------------
# SEASON DETECTION
# ---------------------------------------------------------------------------

def detect_season(name: str, fabric: str, description: str) -> str:
    text = f"{name} {fabric} {description}".lower()
    for season, keywords in SEASON_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return season
    return "All Season"


# ---------------------------------------------------------------------------
# STYLE TAGS GENERATION
# ---------------------------------------------------------------------------

def generate_style_tags(item: dict) -> list:
    tags = []
    pattern = (item.get("pattern") or "").lower()
    fit = (item.get("fit") or "").lower()
    style = (item.get("style") or "").lower()
    fabric = (item.get("fabric") or "").lower()

    if "printed" in pattern:   tags.append("Printed")
    if "embroidered" in pattern: tags.append("Embroidered")
    if "solid" in pattern:     tags.append("Solid Color")
    if "striped" in pattern:   tags.append("Striped")
    if "floral" in pattern:    tags.append("Floral")
    if "bandhani" in pattern:  tags.append("Bandhani")
    if "block" in pattern:     tags.append("Block Print")
    if "checked" in pattern:   tags.append("Checked")

    if "oversized" in fit:     tags.append("Oversized")
    if "slim" in fit:          tags.append("Slim Fit")
    if "loose" in fit:         tags.append("Loose Fit")
    if "regular" in fit:       tags.append("Regular Fit")
    if "flared" in fit:        tags.append("Flared")
    if "tailored" in fit:      tags.append("Tailored")

    if "ethnic" in style:      tags.append("Ethnic Chic")
    if "fusion" in style:      tags.append("Fusion")
    if "western" in style:     tags.append("Western")
    if "formal" in style:      tags.append("Formal Wear")
    if "athleisure" in style:  tags.append("Athleisure")

    if "silk" in fabric:       tags.append("Silk")
    if "denim" in fabric:      tags.append("Denim")
    if "khadi" in fabric:      tags.append("Khadi")

    return tags[:6]


# ---------------------------------------------------------------------------
# DEDUPLICATION (name similarity check)
# ---------------------------------------------------------------------------

def names_similar(n1: str, n2: str) -> bool:
    a = n1.lower().strip()
    b = n2.lower().strip()
    if a == b:
        return True
    if a in b or b in a:
        return True
    words_a = set(a.split())
    words_b = set(b.split())
    overlap = words_a & words_b
    if len(overlap) >= min(len(words_a), len(words_b)) * 0.5:
        return True
    return False


def deduplicate(items: list) -> list:
    unique = []
    for item in items:
        is_dup = False
        for existing in unique:
            if names_similar(item["name"], existing["name"]):
                if item["confidence"] > existing["confidence"]:
                    unique.remove(existing)
                    unique.append(item)
                is_dup = True
                break
        if not is_dup:
            unique.append(item)
    return unique


# ---------------------------------------------------------------------------
# PARSE GPT RESPONSE
# ---------------------------------------------------------------------------

def parse_detection_response(response_text: str):
    """Parse GPT response. Returns (detected_items_list, person_analysis_dict)."""
    text = response_text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    text = text.strip()

    person_analysis = None
    raw_items = []

    # Try parsing as JSON object first (new format with person_analysis + detected_items)
    try:
        start_obj = text.find('{')
        end_obj = text.rfind('}')
        if start_obj != -1 and end_obj != -1:
            parsed = json.loads(text[start_obj:end_obj + 1])
            if isinstance(parsed, dict):
                if 'person_analysis' in parsed:
                    person_analysis = parsed['person_analysis']
                if 'detected_items' in parsed and isinstance(parsed['detected_items'], list):
                    raw_items = parsed['detected_items']
                elif not raw_items:
                    # Fallback: maybe the dict contains item-like keys directly
                    pass
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: try parsing as a JSON array (legacy format)
    if not raw_items:
        try:
            start = text.find('[')
            end = text.rfind(']')
            if start != -1 and end != -1:
                raw_items = json.loads(text[start:end + 1])
        except (json.JSONDecodeError, ValueError):
            return [], None

    validated = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        raw_name = item.get('name', '').strip()
        if not raw_name:
            continue

        # Normalize name
        normalized_name = normalize_name(raw_name)

        # Clamp confidence — use 0.5 default (never drop items silently)
        try:
            confidence = max(0.0, min(1.0, float(item.get('confidence', 0.7))))
        except (TypeError, ValueError):
            confidence = 0.7

        # Get taxonomy info
        tax = INDIAN_FASHION_TAXONOMY.get(normalized_name, {})
        category = item.get('category') or tax.get('category', 'Unknown')
        sub_category = tax.get('sub_category', '')
        style = item.get('style') or tax.get('style', 'Western')

        fabric = item.get('fabric') or None
        fit = item.get('fit') or None
        description = item.get('description', '') or ''
        color = item.get('color') or None
        pattern = item.get('pattern') or None
        gender = item.get('gender') or 'Unisex'

        # Enrichment
        occasion = detect_occasion(normalized_name, description, fabric or '')
        season = detect_season(normalized_name, fabric or '', description)
        style_tags = generate_style_tags({
            'pattern': pattern, 'fit': fit, 'style': style, 'fabric': fabric
        })

        # closet_section: trust GPT if valid, else fall back to taxonomy category
        closet_section = item.get('closet_section', '') or category

        validated.append({
            'item_id':       str(uuid.uuid4())[:8],
            'name':          normalized_name,
            'original_name': raw_name,
            'confidence':    confidence,
            'closet_section': closet_section,
            'category':      category,
            'sub_category':  sub_category,
            'description':   description,
            'color':         color,
            'pattern':       pattern,
            'fabric':        fabric,
            'fit':           fit,
            'gender':        gender,
            'style':         style,
            'occasion':      occasion,
            'season':        season,
            'style_tags':    style_tags,
        })

    return validated, person_analysis


# ---------------------------------------------------------------------------
# GENERATE SUMMARY
# ---------------------------------------------------------------------------

def generate_summary(items: list) -> str:
    if not items:
        return "No clothing items detected."

    by_category = {}
    for item in items:
        cat = item.get('category', 'Unknown')
        by_category.setdefault(cat, []).append(item)

    parts = []
    for cat in ['Topwear', 'Bottomwear', 'Dress', 'Outerwear', 'Footwear', 'Accessory']:
        cat_items = by_category.get(cat, [])
        if cat_items:
            names = [i['name'] + (f" ({i['color']})" if i.get('color') else '') for i in cat_items]
            parts.append(f"{cat}: {', '.join(names)}")

    return ' | '.join(parts) if parts else f"{len(items)} clothing item(s) detected."


# ---------------------------------------------------------------------------
# COUNT SECTIONS
# ---------------------------------------------------------------------------

def count_sections(items: list) -> dict:
    counts = {}
    for item in items:
        s = item.get('closet_section', 'Unknown')
        counts[s] = counts.get(s, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# MIME TYPE HELPER
# ---------------------------------------------------------------------------

def get_mime_type(data_url: str) -> str:
    match = re.match(r'data:([^;]+);base64,', data_url)
    return match.group(1) if match else 'image/jpeg'


# ---------------------------------------------------------------------------
# VERCEL SERVERLESS HANDLER
# ---------------------------------------------------------------------------

class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_POST(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self._send_cors_headers()
        self.end_headers()

        try:
            # 1. Validate API key
            api_key = os.environ.get('OPENAI_API_KEY')
            if not api_key:
                self._write_error('Server configuration error: OPENAI_API_KEY not set.')
                return
            if OpenAI is None:
                self._write_error('Server dependency error: openai package not installed.')
                return

            client = OpenAI(api_key=api_key)

            # 2. Parse body
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._write_error('Empty request body.')
                return
            body = json.loads(self.rfile.read(content_length))

            # 3. Build image content
            image_content = None

            if 'image' in body:
                data_url = body['image']
                if not data_url:
                    self._write_error('image field is empty.')
                    return
                if data_url.startswith('data:'):
                    mime_type = get_mime_type(data_url)
                    b64_data = data_url.split(',', 1)[1] if ',' in data_url else data_url
                else:
                    mime_type = 'image/jpeg'
                    b64_data = data_url
                try:
                    base64.b64decode(b64_data, validate=True)
                except Exception:
                    self._write_error('Invalid base64 image data.')
                    return
                image_content = {
                    'type': 'image_url',
                    'image_url': {'url': f'data:{mime_type};base64,{b64_data}', 'detail': 'high'}
                }

            elif 'image_url' in body:
                image_url = body['image_url']
                if not image_url or not image_url.startswith('http'):
                    self._write_error('Invalid image_url.')
                    return
                image_content = {
                    'type': 'image_url',
                    'image_url': {'url': image_url, 'detail': 'high'}
                }

            else:
                self._write_error('Request must include "image" (base64) or "image_url".')
                return

            # 4. Call GPT-4o-mini with enhanced prompt
            response = client.chat.completions.create(
                model='gpt-4o-mini',
                messages=[{
                    'role': 'user',
                    'content': [
                        {'type': 'text', 'text': DETECTION_PROMPT},
                        image_content
                    ]
                }],
                max_tokens=4000,
                temperature=0.2
            )

            raw_content = response.choices[0].message.content

            # 5. Parse + normalize + enrich
            detected_items, person_analysis = parse_detection_response(raw_content)

            # 6. Deduplicate
            detected_items = deduplicate(detected_items)

            # 7. Sort: highest confidence first
            detected_items.sort(key=lambda x: x['confidence'], reverse=True)

            if not detected_items:
                self._write_json({
                    'success': True,
                    'detected_items': [],
                    'person_analysis': person_analysis,
                    'summary': 'No clothing items detected. Please try a clearer photo with better lighting.',
                    'count': 0,
                    'sections': {},
                    'categories': {}
                })
                return

            summary = generate_summary(detected_items)
            sections = count_sections(detected_items)
            categories = {}
            for item in detected_items:
                cat = item.get('category', 'Unknown')
                categories[cat] = categories.get(cat, 0) + 1

            self._write_json({
                'success': True,
                'detected_items': detected_items,
                'person_analysis': person_analysis,
                'summary': summary,
                'count': len(detected_items),
                'sections': sections,
                'categories': categories
            })

        except json.JSONDecodeError as e:
            self._write_error(f'Invalid JSON in request: {e}')
        except Exception as e:
            self._write_error(f'Detection failed: {str(e)}')

    def _send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def _write_json(self, data: dict):
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def _write_error(self, message: str):
        self.wfile.write(json.dumps({
            'success': False,
            'error': message,
            'detected_items': [],
            'count': 0,
            'sections': {}
        }).encode('utf-8'))

    def log_message(self, format, *args):
        pass
