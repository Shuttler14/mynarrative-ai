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
        # 1. READ THE INCOMING DATA (Critical for avoiding errors)
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)

        # 2. SEND BROWSER HEADERS
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*') 
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

        try:
            # 3. PARSE THE SIMPLE INPUTS
            data = json.loads(post_data)
            quote = data.get('quote') or data.get('slogan') or 'No Slogan'
            style = data.get('style', 'Streetwear')
            color = data.get('color', 'black')
            source_input = data.get('source_input', '')

            # 4. GENERATE IMAGE (gpt-image-1 first, Replicate FLUX as fallback)
            color_clause = f", {color} ink on contrasting background" if color else ""
            source_clause = f", inspired by: {source_input}" if source_input else ""
            image_url = None  # set in one of the two paths below
            try:
                response = client.images.generate(
                    model="gpt-image-1",
                    prompt=f"Vector graphic logo design. High contrast, minimalist{color_clause}. Theme: {style}. Text: '{quote}'{source_clause}. No human faces, no photographic elements, clean vector lines, no watermarks.",
                    size="1024x1024",
                    n=1,
                )
                # gpt-image-1 returns base64 directly (no URL)
                image_b64 = response.data[0].b64_json
                img = Image.open(BytesIO(base64.b64decode(image_b64)))
            except Exception as openai_err:
                # Fallback to Replicate FLUX (user has REPLICATE_API_TOKEN configured
                # and the stylist pipeline already uses it).
                replicate_token = os.environ.get("REPLICATE_API_TOKEN")
                if not replicate_token:
                    raise openai_err
                import replicate
                output = replicate.run(
                    "black-forest-labs/flux-schnell",
                    input={
                        "prompt": f"Vector graphic logo design. High contrast, minimalist{color_clause}. Theme: {style}. Text: '{quote}'{source_clause}. No human faces, no photographic elements, clean vector lines, no watermarks.",
                        "aspect_ratio": "1:1",
                        "output_format": "jpg",
                        "output_quality": 80
                    }
                )
                # FLUX returns a URL (or list of URLs)
                image_url = output[0] if isinstance(output, list) else output
                img_response = requests.get(image_url)
                img = Image.open(BytesIO(img_response.content))

            # 5. WATERMARK & PROCESS
            draw = ImageDraw.Draw(img)

            # Add simple watermark
            width, height = img.size
            for x in range(0, width, 400):
                for y in range(0, height, 400):
                    draw.text((x+50, y+50), "PREVIEW", fill=(200, 200, 200))

            # Convert to Base64 for the website
            buffered = BytesIO()
            img.convert("RGB").save(buffered, format="JPEG", quality=50)
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            image_data_uri = f"data:image/jpeg;base64,{img_str}"

            # 6. SEND BACK TO WEBSITE
            # Theme expects image_url (the data URI). Also return image_preview/temp_url for legacy callers.
            response_data = {
                "success": True,
                "image_url": image_data_uri,
                "image_preview": image_data_uri,
                "temp_url": image_url
            }
            self.wfile.write(json.dumps(response_data).encode('utf-8'))

        except Exception as e:
            # If anything breaks, tell the website why
            self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
