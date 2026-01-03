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

            prompt = f"""
            You are a creative streetwear copywriter.
            Topic: {topic}
            Tone: {tone}
            
            Task: Write 4 short, punchy, unique slogans (max 6 words each) for a t-shirt/hoodie design.
            
            STRICT OUTPUT RULES:
            - Return ONLY a raw JSON array of strings.
            - No markdown formatting (no ```json or ```).
            - No numbering (1., 2.).
            - Example output: ["Dream Big", "Stay Wild", "No Limits", "Just Do It"]
            """

            response = model.generate_content(prompt)
            
            # Clean response text just in case Gemini adds Markdown
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
