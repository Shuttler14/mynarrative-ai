from http.server import BaseHTTPRequestHandler
import os
import json
import base64
from io import BytesIO
from openai import OpenAI
import requests
from PIL import Image, ImageDraw, ImageFont

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data)

        quote = data.get('quote', 'Hustle')
        style = data.get('style', 'Minimalist')

        # 1. The Art Direction Prompt
        prompt = (
            f"A high-fashion streetwear t-shirt graphic design. "
            f"Style: {style}. "
            f"The design should centrally feature the text: '{quote}'. "
            f"Use high contrast, vector art style, isolated on a white background."
        )

        try:
            # 2. Generate Image (DALL-E 3)
            # Note: DALL-E 3 takes 10-15s. If Vercel times out, we might need DALL-E 2.
            response = client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024",
                quality="standard",
                n=1,
            )

            image_url = response.data[0].url

            # 3. Download & Watermark
            img_response = requests.get(image_url)
            img = Image.open(BytesIO(img_response.content))

            # Add Watermark
            draw = ImageDraw.Draw(img)
            # We don't have a custom font file, so we use default. 
            # In a real app, you'd upload your font to the repo.
            text = "MY NARRATIVE PREVIEW"
            
            # Simple watermark logic
            width, height = img.size
            # Draw text in the center, semi-transparent logic requires RGBA
            img = img.convert("RGBA")
            txt_layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
            draw_txt = ImageDraw.Draw(txt_layer)
            
            # Position watermarks in a grid
            for x in range(0, width, 300):
                for y in range(0, height, 300):
                    draw_txt.text((x, y), text, fill=(255, 255, 255, 128))

            combined = Image.alpha_composite(img, txt_layer)

            # 4. Convert to Base64 to send back to browser
            buffered = BytesIO()
            combined.convert("RGB").save(buffered, format="JPEG")
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")

            response_data = {"success": True, "image": f"data:image/jpeg;base64,{img_str}"}
            self.wfile.write(json.dumps(response_data).encode('utf-8'))

        except Exception as e:
            error_response = {"success": False, "error": str(e)}
            self.wfile.write(json.dumps(error_response).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()