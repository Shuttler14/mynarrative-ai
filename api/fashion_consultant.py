from http.server import BaseHTTPRequestHandler
import json
import os
from openai import OpenAI

# Initialize Client
client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY")
)

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # 1. CORS Headers
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

        try:
            # 2. Parse Input
            content_length = int(self.headers['Content-Length'])
            body = json.loads(self.rfile.read(content_length))
            
            # Extract Data
            identity = body.get('identity', {})
            ctx = body.get('currentContext', {}) # This contains 'mode', 'contexts', 'recipient', etc.
            
            mode = ctx.get('mode', 'self')

            # 3. SELECT PROMPT STRATEGY
            if mode == 'gift':
                # 🎁 STRATEGY A: THE GIFT
                # Focus: The User's Taste -> Applied to the Recipient
                recipient = ctx.get('recipient', 'Someone')
                occasion = ctx.get('occasion', 'Special Day')
                unspoken = ctx.get('unspoken', '')

                system_instruction = f"""
                You are a high-end personal shopper for a user with this specific taste profile:
                - Vibe: {identity.get('coreExpression')}
                - Presence: {identity.get('presence')}
                
                MISSION:
                They are buying a gift for a "{recipient}" for "{occasion}".
                Unspoken Message: "{unspoken}"
                
                TASK:
                Suggest a design direction that feels like a thoughtful gift FROM this specific user.
                It should not look generic. It should look like the user picked it because it matches THEIR taste but fits the recipient.
                
                OUTPUT JSON:
                {{
                    "direction": "A single, poetic sentence explaining why this fits the occasion.",
                    "suggestions": ["Visual detail 1", "Visual detail 2", "Visual detail 3", "Visual detail 4"]
                }}
                """

            else:
                # 👤 STRATEGY B: DESIGN FOR SELF (Default)
                # Focus: Identity + Context + Loudness
                contexts = ", ".join(ctx.get('contexts', []))
                loudness = ctx.get('loudness', 'Balanced')

                system_instruction = f"""
                You are an elite fashion stylist for a user with this specific identity:
                - Vibe: {identity.get('coreExpression')}
                - Presence: {identity.get('presence')}
                - Signal: {identity.get('signal')}
                
                MISSION:
                They are dressing for: "{contexts}".
                Loudness Level: {loudness} (Scale: Subtle = texture/cut, Statement = graphic/bold).
                
                TASK:
                Translate their internal identity into a visual look for this specific context.
                
                OUTPUT JSON:
                {{
                    "direction": "A single, poetic sentence defining the vibe (e.g., 'Quiet dominance for the boardroom').",
                    "suggestions": ["Visual detail 1", "Visual detail 2", "Visual detail 3", "Visual detail 4"]
                }}
                """

            # 4. Call OpenAI
            completion = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": "Generate recommendation JSON."}
                ],
                response_format={ "type": "json_object" },
                temperature=0.8
            )

            # 5. Send Response
            self.wfile.write(completion.choices[0].message.content.encode('utf-8'))

        except Exception as e:
            error_msg = json.dumps({"error": str(e)})
            self.wfile.write(error_msg.encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
