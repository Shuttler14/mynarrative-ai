from http.server import BaseHTTPRequestHandler
import json
import os
from openai import OpenAI

# Initialize OpenAI Client
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

            # 3. The "Creative Director" System Instruction
            system_instruction = """
            You are the Head Designer for an underground luxury streetwear brand (like Off-White, Balenciaga, or Supreme). 
            You hate generic motivational quotes. You prefer raw, industrial, cryptic, or brutally honest text.
            """
            
            user_prompt = f"""
            Generate 10 t-shirt text designs for the topic: "{topic}"
            Vibe/Tone: {tone}
            
            STRICT RULES TO AVOID GENERIC OUTPUT:
            1. NO "Basic 3-Word Quotes" (e.g., "Never Give Up", "Hustle Harder" -> THESE ARE BANNED).
            2. MIX LENGTHS: I need a mix of short words and full sentences.
            3. AESTHETIC: Use modern internet syntax, lowercases, or dictionary definitions.
            
            GENERATE 10 DESIGNS USING THESE SPECIFIC STRUCTURES:
            - 2x "The Definition" style (e.g., "CHAOS (n.) - The art of being alive.")
            - 3x "The Statement" (Longer sentence, 6-10 words. e.g., "I don't need therapy, I need a plane ticket.")
            - 2x "Abstract/Cryptic" (e.g., "ERROR 404: FEELINGS NOT FOUND")
            - 3x "Visual/Industrial" (e.g., "HEAVY // TRAFFIC // MIND")
            
            Make them specific to the topic: {topic}.
            
            OUTPUT FORMAT:
            Return ONLY a raw JSON array of strings. 
            Example: ["Design 1", "Design 2", "Design 3"]
            """

            # 5. Call OpenAI API
            completion = client.chat.completions.create(
                model="gpt-4o-mini", 
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.85 # Slightly higher creativity for unique phrases
            )

            # 6. Clean & Parse Response
            raw_text = completion.choices[0].message.content.strip()
            
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

