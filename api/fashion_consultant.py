from http.server import BaseHTTPRequestHandler
import json
import os
from openai import OpenAI

# Initialize Client (Secure Server-Side)
client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY") # This reads from Vercel Environment Variables
)

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # 1. Handle CORS (Allow Shopify to talk to Vercel)
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*') 
        self.send_header('Access-Control-Allow-Methods', 'POST')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

        try:
            # 2. Read Data from Shopify
            content_length = int(self.headers['Content-Length'])
            body = json.loads(self.rfile.read(content_length))
            
            # Extract Identity & Context
            identity = body.get('identity', {})
            context = body.get('context', {})
            
            # 3. Construct the "Stylist" System Prompt
            system_prompt = f"""
            You are an elite fashion curator for 'My Narrative'. 
            User Identity: {identity.get('coreExpression')} / {identity.get('presence')}
            Current Context: {context.get('mode')}
            
            Task: Suggest 4 specific outfit details and 1 poetic direction.
            Tone: Short, punchy, high-fashion directives. No fluff.
            """

            # 4. Call OpenAI (Securely)
            completion = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "Generate Stylist Recommendations. Return JSON: { \"direction\": \"...\", \"suggestions\": [...] }"}
                ],
                response_format={ "type": "json_object" }
            )

            # 5. Send Response back to Shopify
            response_content = completion.choices[0].message.content
            self.wfile.write(response_content.encode('utf-8'))

        except Exception as e:
            error_msg = json.dumps({"error": str(e)})
            self.wfile.write(error_msg.encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
