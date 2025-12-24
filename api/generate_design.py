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
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*') # Update domain in production
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

        try:
            content_length = int(self.headers['Content-Length'])
            data = json.loads(self.rfile.read(content_length))
            quote = data.get('quote', 'Narrative')
            style = data.get('style', 'Minimalist')

            # 1. Generate Image (DALL-E 3)
            prompt = (
                f"A premium streetwear graphic design. Style: {style}. "
                f"Central text: '{quote}'. Vector art style, high contrast, "
                f"isolated on white background. Professional, 4k resolution."
            )
            response = client.images.generate(
                model="dall-e-3", prompt=prompt, size="1024x1024", quality="standard", n=1
            )
            
            # This is the TEMPORARY link (Expires in 1 hour)
            temp_url = response.data[0].url

            # 2. Create Base64 Preview (Watermarked) for Frontend Display
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

            # Return Temp URL (hidden) and Base64 (visible)
            # We send temp_url so the frontend can send it BACK to us if the user decides to buy.
            response_data = {
                "success": True, 
                "image_preview": f"data:image/jpeg;base64,{img_str}",
                "temp_url": temp_url 
            }
            self.wfile.write(json.dumps(response_data).encode('utf-8'))

        except Exception as e:
            self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
