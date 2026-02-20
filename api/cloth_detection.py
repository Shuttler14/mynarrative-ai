"""
Cloth Detection API - Vercel Serverless Function
=================================================
Detects clothing items from uploaded images using GPT-4o-mini vision.
Designed for the MY NARRATIVE AI Stylist on Shopify.

Accepts:
  POST with JSON body: { "image": "<base64_data_url>" }
  OR:                  { "image_url": "<https://...>" }

Returns:
  JSON: { success, detected_items, summary, count, sections }
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import base64
import re

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


# ---------------------------------------------------------------------------
# Indian Fashion Detection Prompt
# ---------------------------------------------------------------------------

DETECTION_PROMPT = """You are an expert Indian fashion stylist and clothing classifier.
Analyze the provided image and detect ALL visible clothing items worn by the person.

For each clothing item detected, provide:
1. name        - The exact name of the garment (e.g. "Kurta", "Slim Fit Jeans", "Lehenga")
2. confidence  - Your confidence level (0.0 to 1.0)
3. closet_section - Which digital closet section it belongs to (see list below)
4. description - Brief description of the item
5. color       - Primary color if visible (or null)
6. pattern     - Any pattern: solid, striped, floral, embroidered, printed, etc. (or null)
7. material    - Fabric/material if identifiable: cotton, silk, denim, etc. (or null)
8. style       - Style variant: Western, Ethnic, Fusion (or null)
9. region      - Which region of India this is commonly from: North/South/East/West/All India (or null)

CLASSIFY INTO THESE CLOSET SECTIONS:
- Kurta (includes Kurti, Anarkali, Angavastram, Pathani, Achkan)
- Shirt (formal shirts, casual shirts, oxford shirts)
- T-Shirt (tshirts, tops, polos, blouses)
- Jeans (jeans, denim trousers)
- Trousers (pants, formal trousers, chinos, cargo pants)
- Palazzo (palazzo pants, wide-leg pants)
- Leggings (churidar, salwar, leggings, tights)
- Dhoti
- Lungap (Lungi, Mundu)
- Sherwani
- Nehru Jacket
- Blazer (blazers, coats, suit jackets)
- Jacket (casual jackets, denim jackets, bomber jackets, hoodies)
- Saree
- Lehenga (includes Choli, Ghagra, Skirt)
- Chunni (Dupatta, Odhni, stoles worn as head/shoulder covering)
- Scarf (scarves, stoles worn decoratively, shawls, pashmina)
- Dress (gowns, frocks, western dresses, jumpsuits)
- Footwear (shoes, sandals, slippers, sneakers, boots, heels, juttis, mojaris, kolhapuris)
- Accessories (belts, sunglasses, ties, pocket squares)
- Bag (handbags, clutches, wallets, backpacks, tote bags)
- Watch
- Jewellery (bangles, jhumkas, necklaces, earrings, rings, bracelets, maang tikka)
- Headwear (hats, caps, turbans, dupattas on head)
- Topwear (any upper body garment not fitting above categories)
- Bottomwear (any lower body garment not fitting above categories)

IMPORTANT RULES:
- Detect ALL items visible — including multiple layers (shirt + jacket = 2 items)
- Recognize both Indian ethnic wear AND western wear
- Do NOT hallucinate items that are not clearly visible
- Be specific and precise with Indian fashion terminology
- Include footwear and accessories if they are visible in the frame
- If the image does not contain a person or any clothing, return an empty array []
- Return ONLY a valid JSON array — no markdown, no code blocks, no explanations

Return format — a JSON array only:
[
  {
    "name": "string",
    "confidence": 0.0,
    "closet_section": "string",
    "description": "string",
    "color": "string or null",
    "pattern": "string or null",
    "material": "string or null",
    "style": "string or null",
    "region": "string or null"
  }
]"""


# ---------------------------------------------------------------------------
# Helper: Parse GPT response into list of items
# ---------------------------------------------------------------------------

def parse_detection_response(response_text: str) -> list:
    """Extract and parse JSON array from GPT response."""
    # Strip markdown code blocks if present
    text = response_text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    text = text.strip()

    # Find JSON array bounds
    start = text.find('[')
    end = text.rfind(']')

    if start == -1 or end == -1:
        return []

    json_str = text[start:end + 1]
    items = json.loads(json_str)

    # Validate and normalise each item
    validated = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get('name', '').strip()
        if not name:
            continue
        # Clamp confidence between 0 and 1
        raw_conf = item.get('confidence', 0.7)
        try:
            confidence = max(0.0, min(1.0, float(raw_conf)))
        except (TypeError, ValueError):
            confidence = 0.7

        validated.append({
            'name': name,
            'confidence': confidence,
            'closet_section': item.get('closet_section', 'Unknown') or 'Unknown',
            'description': item.get('description', '') or '',
            'color': item.get('color') or None,
            'pattern': item.get('pattern') or None,
            'material': item.get('material') or None,
            'style': item.get('style') or None,
            'region': item.get('region') or None,
        })

    return validated


# ---------------------------------------------------------------------------
# Helper: Generate human-readable summary
# ---------------------------------------------------------------------------

def generate_summary(items: list) -> str:
    """Generate a concise summary of detected clothing items."""
    if not items:
        return "No clothing items detected."

    topwear_sections = {"Kurta", "Shirt", "T-Shirt", "Sherwani", "Nehru Jacket",
                        "Blazer", "Jacket", "Topwear", "Dress"}
    bottomwear_sections = {"Jeans", "Trousers", "Palazzo", "Leggings",
                           "Dhoti", "Lungap", "Bottomwear", "Lehenga"}
    accessory_sections = {"Accessories", "Bag", "Watch", "Jewellery",
                          "Headwear", "Scarf", "Chunni", "Saree"}

    parts = []
    tops = [i for i in items if i['closet_section'] in topwear_sections]
    bottoms = [i for i in items if i['closet_section'] in bottomwear_sections]
    footwear = [i for i in items if i['closet_section'] == 'Footwear']
    accessories = [i for i in items if i['closet_section'] in accessory_sections]

    def fmt(item):
        return item['name'] + (f" ({item['color']})" if item.get('color') else "")

    if tops:
        parts.append("Top: " + ", ".join(fmt(i) for i in tops))
    if bottoms:
        parts.append("Bottom: " + ", ".join(fmt(i) for i in bottoms))
    if footwear:
        parts.append("Footwear: " + ", ".join(i['name'] for i in footwear))
    if accessories:
        parts.append("Accessories: " + ", ".join(i['name'] for i in accessories))

    return " | ".join(parts) if parts else f"{len(items)} clothing item(s) detected."


# ---------------------------------------------------------------------------
# Helper: Count items by closet section
# ---------------------------------------------------------------------------

def count_sections(items: list) -> dict:
    counts = {}
    for item in items:
        section = item.get('closet_section', 'Unknown')
        counts[section] = counts.get(section, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Helper: Detect MIME type from base64 data URL
# ---------------------------------------------------------------------------

def get_mime_type(data_url: str) -> str:
    """Extract MIME type from a data URL, defaulting to image/jpeg."""
    match = re.match(r'data:([^;]+);base64,', data_url)
    if match:
        return match.group(1)
    return 'image/jpeg'


# ---------------------------------------------------------------------------
# Vercel Serverless Handler
# ---------------------------------------------------------------------------

class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_POST(self):
        """Main cloth detection endpoint."""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self._send_cors_headers()
        self.end_headers()

        try:
            # ── 1. Validate OpenAI client ──────────────────────────────────
            api_key = os.environ.get('OPENAI_API_KEY')
            if not api_key:
                self._write_error('Server configuration error: OPENAI_API_KEY not set.', 500)
                return

            if OpenAI is None:
                self._write_error('Server dependency error: openai package not installed.', 500)
                return

            client = OpenAI(api_key=api_key)

            # ── 2. Parse request body ──────────────────────────────────────
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._write_error('Empty request body.', 400)
                return

            raw_body = self.rfile.read(content_length)
            body = json.loads(raw_body)

            # ── 3. Build image content for OpenAI ─────────────────────────
            image_content = None

            if 'image' in body:
                # Base64 data URL from browser FileReader
                data_url = body['image']

                if not data_url:
                    self._write_error('image field is empty.', 400)
                    return

                # Handle both raw base64 and full data URLs
                if data_url.startswith('data:'):
                    mime_type = get_mime_type(data_url)
                    # Strip the data URL header to get pure base64
                    b64_data = data_url.split(',', 1)[1] if ',' in data_url else data_url
                else:
                    # Assume raw base64, default mime
                    mime_type = 'image/jpeg'
                    b64_data = data_url

                # Validate it's actually base64
                try:
                    base64.b64decode(b64_data, validate=True)
                except Exception:
                    self._write_error('Invalid base64 image data.', 400)
                    return

                image_content = {
                    'type': 'image_url',
                    'image_url': {
                        'url': f'data:{mime_type};base64,{b64_data}',
                        'detail': 'high'
                    }
                }

            elif 'image_url' in body:
                # Direct URL to an image
                image_url = body['image_url']
                if not image_url or not image_url.startswith('http'):
                    self._write_error('Invalid image_url.', 400)
                    return

                image_content = {
                    'type': 'image_url',
                    'image_url': {
                        'url': image_url,
                        'detail': 'high'
                    }
                }

            else:
                self._write_error(
                    'Request must include either "image" (base64 data URL) or "image_url" (https URL).',
                    400
                )
                return

            # ── 4. Call GPT-4o-mini Vision ─────────────────────────────────
            response = client.chat.completions.create(
                model='gpt-4o-mini',
                messages=[
                    {
                        'role': 'user',
                        'content': [
                            {'type': 'text', 'text': DETECTION_PROMPT},
                            image_content
                        ]
                    }
                ],
                max_tokens=2000,
                temperature=0.2   # Low temp for consistent, factual classification
            )

            raw_content = response.choices[0].message.content

            # ── 5. Parse response ──────────────────────────────────────────
            detected_items = parse_detection_response(raw_content)

            if not detected_items:
                # GPT returned empty array — no clothing detected
                self._write_json({
                    'success': True,
                    'detected_items': [],
                    'summary': 'No clothing items detected. Please try a clearer photo with better lighting.',
                    'count': 0,
                    'sections': {}
                })
                return

            # ── 6. Build response ──────────────────────────────────────────
            summary = generate_summary(detected_items)
            sections = count_sections(detected_items)

            self._write_json({
                'success': True,
                'detected_items': detected_items,
                'summary': summary,
                'count': len(detected_items),
                'sections': sections
            })

        except json.JSONDecodeError as e:
            self._write_error(f'Invalid JSON in request: {e}', 400)
        except Exception as e:
            # Surface the real error message for debugging
            self._write_error(f'Detection failed: {str(e)}', 500)

    # ── Private helpers ────────────────────────────────────────────────────

    def _send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def _write_json(self, data: dict):
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def _write_error(self, message: str, status_code: int = 500):
        # We already sent 200 in do_POST before reading the body,
        # so we just return an error payload in the body.
        self.wfile.write(json.dumps({
            'success': False,
            'error': message,
            'detected_items': [],
            'count': 0,
            'sections': {}
        }).encode('utf-8'))

    def log_message(self, format, *args):
        # Suppress default HTTP server logging on Vercel
        pass
