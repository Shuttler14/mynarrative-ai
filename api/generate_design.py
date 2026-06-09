from http.server import BaseHTTPRequestHandler
import os
import json
import base64
from io import BytesIO
import requests
from PIL import Image, ImageDraw
import replicate

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*') 
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

        try:
            data = json.loads(post_data)
            quote = data.get('quote') or data.get('slogan') or 'No Slogan'
            style = data.get('style', 'Streetwear')
            color = data.get('color', 'black')
            source_input = data.get('source_input', '')

            color_clause = f", {color} ink on contrasting background" if color else ""
            source_clause = f", inspired by: {source_input}" if source_input else ""

            prompt = (
                f"Vector graphic logo design. High contrast, minimalist{color_clause}. "
                f"Theme: {style}. Text: '{quote}'{source_clause}. "
                f"No human faces, no photographic elements, clean vector lines, no watermarks."
            )
            output = replicate.run(
                "black-forest-labs/flux-schnell",
                input={
                    "prompt": prompt,
                    "aspect_ratio": "1:1",
                    "output_format": "jpg",
                    "output_quality": 80,
                },
            )
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
