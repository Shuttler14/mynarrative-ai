from http.server import BaseHTTPRequestHandler
import json
import os
import google.generativeai as genai

# Configure Gemini
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

        try:
            content_length = int(self.headers['Content-Length'])
            body = json.loads(self.rfile.read(content_length))
            
            topic = body.get('topic', 'fashion')
            tone = body.get('tone', 'motivational')

            # Use Gemini 1.5 Flash for speed
            model = genai.GenerativeModel('gemini-1.5-flash')

            # --- THE "NERVE-TOUCHING" PROMPT ---
            prompt = f"""
            Role: You are a visionary Creative Director for a high-end streetwear brand. You understand subcultures, internet humor, and deep human psychology.
            
            Context: The user wants a design based on:
            TOPIC: {topic}
            TONE: {tone}
            
            Task: Generate 10 unique, punchy, and highly resonant slogans.
            
            CRITICAL RULES FOR "NERVE-TOUCHING" IMPACT:
            1. NO CLICHÉS: Avoid generic phrases like "Eat Sleep Repeat" or "Keep Calm."
            2. THE UNSAID TRUTH: Don't describe the topic; reveal the hidden feeling behind it. (e.g., Instead of "I love coffee," say "Survival Juice" or "Caffeine until I feel feelings.")
            3. VARY THE LENGTH: Mix 2-word punches with 5-6 word statements.
            4. AESTHETIC: The text must look good on a shirt. Minimalist, bold, or gritty.
            
            TONE SPECIFICS:
            - If Sarcastic: Be dry, witty, slightly mean, or self-deprecating.
            - If Dark: Be gothic, nihilistic, mysterious.
            - If Motivational: Be aggressive, stoic, disciplined (not cheesy).
            - If Luxury: Be arrogant, minimal, expensive, exclusive.
            
            OUTPUT FORMAT:
            Return ONLY a raw JSON array of strings. No markdown.
            Example: ["Slogan 1", "Slogan 2", "Slogan 3"]
            """

            response = model.generate_content(prompt)
            
            # Clean response text
            clean_text = response.text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:-3]
            elif clean_text.startswith("```"):
                clean_text = clean_text[3:-3]

            slogans = json.loads(clean_text)

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
