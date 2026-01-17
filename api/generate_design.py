from http.server import BaseHTTPRequestHandler
import os
import json
import base64
from io import BytesIO
from openai import OpenAI
import requests
from PIL import Image, ImageDraw

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # 1. Read Data
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)

        # 2. Setup Headers
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

        try:
            # 3. Parse Inputs
            data = json.loads(post_data)
            quote = data.get('quote', 'No Slogan')
            style = data.get('style', 'Streetwear')

            # 4. FAST GENERATION (DALL-E 2) - < 5 Seconds
            test_prompt = f"Vector style badge. Streetwear graphic. Minimalist. Theme: {style}. Text: '{quote}'"

            response = client.images.generate(
                model="dall-e-2", 
                prompt=test_prompt,
                size="512x512",
                n=1,
            )
            
            # 5. Process Image
            temp_url = response.data[0].url
            
            # Download & Watermark
            img_response = requests.get(temp_url)
            img = Image.open(BytesIO(img_response.content))
            
            # Resize for speed (Optional, but helps)
            img = img.resize((400, 400)) 

            buffered = BytesIO()
            img.convert("RGB").save(buffered, format="JPEG", quality=50)
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")

            # 6. Success Output
            self.wfile.write(json.dumps({
                "success": True,
                "image_preview": f"data:image/jpeg;base64,{img_str}",
                "temp_url": temp_url
            }).encode('utf-8'))

        except Exception as e:
            self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
