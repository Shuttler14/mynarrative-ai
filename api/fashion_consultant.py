from http.server import BaseHTTPRequestHandler
import json
import os
from openai import OpenAI

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
                # 👤 SELF MODE PROMPT (Standard)
                contexts = ", ".join(ctx.get('contexts', ['Daily Wear']))
                loudness = ctx.get('loudness', 'Balanced')
                system_instruction = f"""
                You are an elite fashion stylist.
                User Identity: {identity.get('coreExpression')}
                Context: {contexts}
                Loudness: {loudness}
                Task: Suggest 4 visual details and 1 vibe direction.
                Output JSON: {{ "direction": "...", "suggestions": ["...", "...", "...", "..."] }}
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
                response_payload = data

            self.wfile.write(json.dumps(response_payload).encode('utf-8'))

        except Exception as e:
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
