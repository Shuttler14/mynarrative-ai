from http.server import BaseHTTPRequestHandler
import os
import json
from openai import OpenAI

# Initialize OpenAI Client
# Ensure you add OPENAI_API_KEY in your Vercel Environment Variables
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # 1. Handle CORS (So your Shopify store can talk to this backend)
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*') # Allow all domains (restrict to mynarrative.store in production)
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

        # 2. Parse the Incoming Data from Shopify
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data)

        topic = data.get('topic', 'fashion')
        tone = data.get('tone', 'motivational')

        # 3. The Prompt Engineering (The "Secret Sauce")
        # We force OpenAI to return a strict JSON format so our code doesn't break.
        system_instruction = (
            "You are a creative director for a premium streetwear brand. "
            "Generate 10 short, punchy, and trendy slogans/quotes based on the user's topic and tone. "
            "Keep them under 8 words. Do not use emojis. "
            "Return ONLY a raw JSON list of strings. Example: [\"Quote 1\", \"Quote 2\"]"
        )

        user_prompt = f"Topic: {topic}. Tone: {tone}."

        try:
            # 4. Call OpenAI API (GPT-4o-mini is cheap and fast)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.8, # Slightly creative
            )

            # 5. Extract and Clean Data
            raw_content = response.choices[0].message.content
            # Remove any markdown formatting if AI adds it (like ```json ... ```)
            cleaned_content = raw_content.replace("```json", "").replace("```", "").strip()
            quotes_list = json.loads(cleaned_content)

            # 6. Send Response back to Shopify
            response_data = {"success": True, "quotes": quotes_list}
            self.wfile.write(json.dumps(response_data).encode('utf-8'))

        except Exception as e:
            error_response = {"success": False, "error": str(e)}
            self.wfile.write(json.dumps(error_response).encode('utf-8'))

    def do_OPTIONS(self):
        # Handle pre-flight CORS check
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()