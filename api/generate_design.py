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
        # --- 1. CRITICAL FIX: READ THE DATA FIRST ---
        # These lines were missing, causing the "post_data not defined" error
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)

        # --- 2. SEND HEADERS ---
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*') 
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

        try:
            # --- 3. PARSE DATA ---
            data = json.loads(post_data)
            quote = data.get('quote', 'No Slogan')
            style = data.get('style', 'Streetwear') 

            # --- 4. FAST GENERATION (DALL-E 2) ---
            # Using DALL-E 2 for <4 second generation to test coordinates
            test_prompt = f"A cool, high-contrast streetwear graphic design badge. Minimalist vector style. Theme: {style}. Text content: '{quote}'"

            response = client.images.generate(
                model="dall-e-2", 
                prompt=test_prompt,
                size="512x512",
                n=1,
            )

            image_url = response.data[0].url
            temp_url = image_url 

            # --- 5. WATERMARK & PREVIEW ---
            img_response = requests.get(temp_url)
            img = Image.open(BytesIO(img_response.content))
            draw = ImageDraw.Draw(img)
            
            # Simple Watermark
            width, height = img.size
            for x in range(0, width, 400):
                for y in range(0, height, 400):
                    draw.text((x+50, y+50), "PREVIEW", fill=(200, 200, 200))

            buffered = BytesIO()
            img.convert("RGB").save(buffered, format="JPEG", quality=40)
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")

            # --- 6. SEND SUCCESS RESPONSE ---
            response_data = {
                "success": True, 
                "image_preview": f"data:image/jpeg;base64,{img_str}",
                "temp_url": temp_url 
            }
            self.wfile.write(json.dumps(response_data).encode('utf-8'))

        except Exception as e:
            # Send Error Response so you see it in the popup
            self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
