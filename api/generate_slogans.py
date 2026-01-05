from http.server import BaseHTTPRequestHandler
import json
import os
from openai import OpenAI

# Initialize OpenAI Client (Uses the same key as your Image Generator)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

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
            
            topic = body.get('topic', 'fashion')
            tone = body.get('tone', 'motivational')

            # 3. The "Creative Director" Prompt (Adapted for GPT)
            system_instruction = "You are a visionary Creative Director for a high-end streetwear brand. You understand subcultures, internet humor, and deep human psychology."
            
            user_prompt = f"""
            The user wants a t-shirt design based on:
            TOPIC: {topic}
            TONE: {tone}
            
            Task: Generate 10 unique, punchy, and highly resonant slogans.
            
            CRITICAL RULES:
            1. NO CLICHÉS: Avoid generic phrases like "Eat Sleep Repeat."
            2. THE UNSAID TRUTH: Don't describe the topic; reveal the hidden feeling behind it.
            3. AESTHETIC: The text must look good on a shirt. Minimalist, bold, or gritty.
            4. VARY LENGTH: Mix short 2-word punches with 5-6 word statements.
            
            OUTPUT FORMAT:
            Return ONLY a raw JSON array of strings. 
            Example: ["Slogan 1", "Slogan 2", "Slogan 3"]
            """

            # 4. Call OpenAI API
            completion = client.chat.completions.create(
                model="gpt-4o-mini", # Smart, Fast, Cost-Effective
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.8 # High creativity
            )

            # 5. Clean & Parse Response
            raw_text = completion.choices[0].message.content.strip()
            
            # Remove Markdown formatting if GPT adds it (e.g. ```json ... ```)
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:-3]
            elif raw_text.startswith("```"):
                raw_text = raw_text[3:-3]

            slogans = json.loads(raw_text)

            self.wfile.write(json.dumps({
                "success": True, 
                "quotes": slogans
            }).encode('utf-8'))

        except Exception as e:
            self.wfile.write(json.dumps({
                "success": False, 
                "error": str(e)
            }).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
