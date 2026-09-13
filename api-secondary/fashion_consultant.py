from http.server import BaseHTTPRequestHandler
import json
import os
from openai import OpenAI

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


def _is_generic_marketplace_link(url: str) -> bool:
    if not isinstance(url, str) or not url.strip():
        return True
    u = url.strip().lower()
    if u in ("https://myntra.com", "https://www.myntra.com", "https://ajio.com", "https://www.ajio.com"):
        return True
    if u.startswith("https://www.amazon.") and ("/dp/" not in u and "/gp/product/" not in u):
        return True
    if "://myntra.com/" in u or "://www.myntra.com/" in u:
        # Accept only deeper product pages.
        return "/buy" not in u and "/p/" not in u
    if "://www.flipkart.com/" in u:
        return "/p/" not in u and "pid=" not in u
    return False


def _pick_catalog_for_piece(piece: dict) -> dict:
    text = " ".join([
        str(piece.get("slot", "")),
        str(piece.get("type", "")),
        str(piece.get("name", "")),
        str(piece.get("why", "")),
    ]).lower()

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
    # Safe fallback: a tee product page.
    return MY_NARRATIVE_CATALOG[2]


def _attach_exact_links(outfit_pieces: list) -> list:
    normalized = []
    for piece in outfit_pieces or []:
        p = dict(piece)
        if p.get("owned") is True:
            p["shop_links"] = []
            normalized.append(p)
            continue

        selected = _pick_catalog_for_piece(p)
        existing_links = [l for l in (p.get("shop_links") or []) if isinstance(l, dict) and not _is_generic_marketplace_link(l.get("url", ""))]
        # Put MY NARRATIVE exact product as primary link for VTON-ready flow.
        mn_link = {
            "platform": "MY NARRATIVE",
            "url": selected["product_url"],
            "price": f"₹{selected['price']}",
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


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # 1. SETUP CORS
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

        try:
            # 2. AUTH & CLIENT
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("Missing API Key on Server")
            
            client = OpenAI(api_key=api_key)

            # 3. PARSE DATA
            content_length = int(self.headers['Content-Length'])
            body = json.loads(self.rfile.read(content_length))
            
            identity = body.get('identity', {})
            ctx = body.get('currentContext', {})
            mode = ctx.get('mode', 'self')

            # 4. PROMPT ENGINEERING
            if mode == 'gift':
                # 🎁 GIFT MODE PROMPT (Your Exact Logic)
                recipient = ctx.get('recipient', 'Someone')
                occasion = ctx.get('occasion', 'Special Occasion')
                unspoken = ctx.get('unspoken', '')
                
                core_expr = identity.get('coreExpression', 'Balanced')
                presence = identity.get('presence', 'Thoughtful')
                signal = identity.get('signal', 'Growth')

                system_instruction = f"""
You are the creative director at MY NARRATIVE — a premium streetwear and merch brand where every piece of clothing carries a personal story. Your specialty is crafting short, powerful slogans that get printed on t-shirts, hoodies, caps, and tote bags.

═══════════════════════════════════════════
ABOUT THE GIFT-GIVER (The Person Buying)
═══════════════════════════════════════════

This person has already been profiled. Their identity shapes the TONE and EMOTIONAL DEPTH of what they'd gift:

• Core Style Expression: {core_expr}
• How They Show Up in the World: {presence}
• Current Life Signal: {signal}

This matters because: a "Deep & Symbolic" person who is a "Thoughtful Introvert" in a "Healing Era" will gift something profoundly different from a "Bold & Expressive" person who is a "Creative Risk-Taker" with "Main Character Energy." The slogan should feel like it CAME FROM this specific person.

═══════════════════════════════════════════
THE GIFT CONTEXT
═══════════════════════════════════════════

• Who is receiving this: {recipient}
• The occasion: {occasion}
• The unspoken message (what the giver REALLY wants to say but might not say out loud): "{unspoken}"

═══════════════════════════════════════════
RELATIONSHIP × OCCASION EMOTIONAL MATRIX
═══════════════════════════════════════════

Use this to calibrate emotional intensity and tone:

RECIPIENT DYNAMICS:
- Friend → insider language, shared humor, loyalty, "I see you" energy
- Partner → vulnerability, desire, devotion, unspoken depth, intimacy
- Family → legacy, roots, unconditional love, pride, gentle strength
- Colleague → respect, subtle admiration, professional warmth, shared grind
- Someone Special → tension, longing, "this means more than I'm saying," deliberate ambiguity

OCCASION DYNAMICS:
- Birthday → celebration of WHO they are, not just the date
- First Date → memorable, flirty but not desperate, confidence as a gift
- Anniversary → reflection, growth together, "still choosing you"
- New Job → empowerment, belief in them, "go conquer" energy
- Breakup Support → healing, strength, "you're not defined by this"
- Motivation Gift → fuel, fire, "I believe in you more than you do"
- Inside Joke → only THEY would understand, warmth through humor
- Everyday Wear → timeless, wearable philosophy, identity statement

═══════════════════════════════════════════
SLOGAN REQUIREMENTS
═══════════════════════════════════════════

Generate exactly 5 slogans. Each must:

1. LENGTH: 2–7 words maximum. These go on clothing. Brevity is sacred.
2. PRINTABILITY: Must look powerful when printed in a single line on a t-shirt chest, hoodie front, or cap.
3. NO hashtags, no emojis, no quotation marks in the slogans themselves.
4. NO generic motivational poster language ("Live Laugh Love", "Be Yourself", "Stay Strong" — these are BANNED).
5. NO clichés. If you've seen it on a Pinterest board, don't use it.
6. VOICE: The slogan should sound like something the GIFT-GIVER would actually say or want to say — filtered through their identity profile.
7. EMOTIONAL PRECISION: The slogan must hit the exact emotional frequency of the recipient × occasion × unspoken message intersection.
8. WEARABILITY TEST: Would someone actually wear this in public and feel like it represents something real? If not, discard it.

STYLE SPECTRUM (calibrate based on identity):
- If identity is Calm/Minimal/Clean → crisp, architectural language, white space in words
- If identity is Bold/Expressive/Playful → punchy, rhythmic, slightly provocative  
- If identity is Deep/Symbolic/Emotional → layered meaning, poetic compression, metaphor
- If identity is Disciplined/Structured/Stoic → commanding, declarative, stripped-down power
- If identity is Dark/Mysterious/Free → subversive, enigmatic, double-meaning

═══════════════════════════════════════════
RESPONSE FORMAT (Strict JSON)
═══════════════════════════════════════════

{{
  "direction": "A 1-2 sentence creative brief explaining the emotional direction you chose and WHY these slogans work for this specific gift-giver → recipient → occasion combination.",
  "slogans": [
    "First slogan (your strongest recommendation)",
    "Second slogan (alternative angle)",
    "Third slogan (emotionally deeper cut)",
    "Fourth slogan (slightly bolder/edgier)",
    "Fifth slogan (wildcard — unexpected but perfect)"
  ],
  "suggestions": [
    "One specific design/styling tip",
    "One tip about the emotional context",
    "One tip about personalization"
  ]
}}
"""
            else:
                # 👤 SELF MODE PROMPT (Enhanced with all 13 dimensions)
                contexts = ", ".join(ctx.get('contexts', ['Daily Wear']))
                loudness = ctx.get('loudness', 'Balanced')
                
                # Extract all identity dimensions
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
                # Use rich digital_closet (from AI cloth detection) if available, else fallback to simple closet list
                digital_closet = identity.get('digital_closet', [])
                simple_closet = identity.get('closet', [])

                if digital_closet:
                    # Format rich closet items into a detailed, GPT-readable block
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
You are the AI Fashion Consultant at MY NARRATIVE — a psychology-first styling engine for the Indian market. You create precise, body-aware outfit recommendations based on the user's full profile.

═══════════════════════════════════════════
USER IDENTITY PROFILE
═══════════════════════════════════════════

PSYCHOLOGY (Phase 0):
• Core Expression: {core_expr}
• World Presence: {presence}
• Current Signal: {signal}
• Archetype: {archetype_name}

BODY DATA (Phase 2A):
• Height: {height} cm
• Build: {build}

PALETTE (Phase 2B):
• Skin Tone: {skin_tone}
• Undertone: {undertone}

WORLD (Phase 2C):
• Style Region: {region}
• Primary Climate: {climate}
• Budget Range: {budget}

EXISTING CLOSET (Phase 3):
{closet_str}

═══════════════════════════════════════════
CURRENT REQUEST
═══════════════════════════════════════════

• Context: {contexts}
• Loudness: {loudness}

═══════════════════════════════════════════
STYLING RULES
═══════════════════════════════════════════

1. BODY-AWARE: Consider build and height for cut/fit recommendations. "Lean" builds get structured pieces; "Broad" builds get clean lines without bulk.
2. COLOR-SCIENCE: Recommend colors based on skin tone + undertone. Warm undertones → earth tones, mustard, olive. Cool undertones → navy, emerald, silver. Neutral → both work.
3. CLIMATE-SMART: Factor in the user's primary climate for fabric and layering.
4. BUDGET-REALISTIC: Stay within the budget range. Budget = ₹500–1500, Mid = ₹1500–4000, Premium = ₹4000–10000, Luxury = ₹10000+.
5. CLOSET-AWARE: The user's AI-detected closet is listed above with item IDs in [brackets]. Prioritize building outfits around items they ALREADY OWN. For each outfit piece, if it matches something in their closet, set "owned": true and "item_id" to the matching ID. For new pieces to buy, set "owned": false. Always lead with at least 1–2 owned items to minimise spend.
6. INDIA-SPECIFIC: Include Indian brands (Bewakoof, Rare Rabbit, Mango Man, Fabindia, etc.) and platform links (Myntra, Ajio, Amazon.in).
7. ARCHETYPE-ALIGNED: Ensure the overall direction matches the user's psychological archetype.

═══════════════════════════════════════════
RESPONSE FORMAT (Strict JSON)
═══════════════════════════════════════════

{{
  "direction": "A 1-2 sentence styling direction that connects the outfit to the user's archetype and context.",
  "outfit_pieces": [
    {{
      "slot": "top|bottom|footwear|accessory|outerwear",
      "name": "Specific item name (e.g., 'Olive Linen Shirt')",
      "type": "shirt|tshirt|jeans|chinos|sneakers|boots|watch|etc",
      "color": "#hex color code",
      "owned": true,
      "item_id": "matching item_id from closet if owned, else null",
      "why": "One sentence: why this piece works for this user's body + tone + archetype. If owned, start with 'You already own this —'",
      "shop_links": [
        {{ "platform": "Myntra", "url": "https://myntra.com", "price": "₹approx" }},
        {{ "platform": "Ajio", "url": "https://ajio.com", "price": "₹approx" }}
      ]
    }}
  ],
  "suggestions": [
    "Full body fashion photograph prompt 1: A complete head-to-toe editorial shot of an Indian {build} {gender} model with {skin_tone} skin tone wearing [outfit piece 1] and [outfit piece 2], full body visible from head to feet including footwear, no cropping, clean studio background, cinematic lighting",
    "Full body fashion photograph prompt 2: Street-style full length photograph of the complete outfit look — entire figure visible top to bottom, high fashion editorial quality, Indian aesthetic",
    "Full body fashion photograph prompt 3: An alternative angle or styling variation of the same complete outfit, full body shot, head to toe, professional fashion photography",
    "Full body fashion photograph prompt 4: Close-up detail shot of the key statement piece from the outfit (this is the only non-full-body shot allowed)"
  ],
  "styling_tips": ["tip 1 about styling", "tip 2 about combinations", "tip 3 about occasion"],
  "color_science": "A sentence explaining why these specific colors complement the user's skin tone and undertone.",
  "archetype_note": "A personal note connecting this outfit to their archetype identity."
}}

Generate 4-6 outfit pieces that create a complete look. At least 1-2 must be items the user ALREADY OWNS (owned: true). For owned items, do NOT include shop_links (they already have it). For new items to buy, include shop_links with real Indian platform URLs and approximate prices.
"""

            # 5. GENERATE
            completion = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": "Generate JSON response."}
                ],
                response_format={ "type": "json_object" },
                temperature=0.85
            )

            # 6. RESPONSE MAPPING
            data = json.loads(completion.choices[0].message.content)
            
            response_payload = {}
            if mode == 'gift':
                # Map 'slogans' to 'suggestions' for frontend compatibility
                response_payload = {
                    "direction": data.get("direction", "Curated for you."),
                    "suggestions": data.get("slogans", []), 
                    "styling_tips": data.get("suggestions", [])
                }
            else:
                # Self mode: pass through the full enhanced response
                outfit_pieces = _attach_exact_links(data.get("outfit_pieces", []))
                response_payload = {
                    "direction": data.get("direction", "Styled for you."),
                    "outfit_pieces": outfit_pieces,
                    "suggestions": data.get("suggestions", []),
                    "styling_tips": data.get("styling_tips", []),
                    "color_science": data.get("color_science", ""),
                    "archetype_note": data.get("archetype_note", ""),
                    "my_narrative_catalog": MY_NARRATIVE_CATALOG,
                    "vton_ready_products": [p.get("my_narrative_product") for p in outfit_pieces if p.get("my_narrative_product")][:6],
                }

            self.wfile.write(json.dumps(response_payload).encode('utf-8'))

        except Exception as e:
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()