from http.server import BaseHTTPRequestHandler
import os
import json
import requests
import base64
import time

SHOP_DOMAIN = os.environ.get("SHOPIFY_DOMAIN")
ACCESS_TOKEN = os.environ.get("SHOPIFY_ACCESS_TOKEN")

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

        try:
            # 1. Parse Input
            content_length = int(self.headers['Content-Length'])
            data = json.loads(self.rfile.read(content_length))
            temp_url = data.get('image_url')

            if not temp_url:
                raise Exception("No image URL provided")

            # 2. Download Image to Vercel Memory (Bypassing Shopify Fetch Limits)
            img_response = requests.get(temp_url)
            if img_response.status_code != 200:
                raise Exception("Could not download image from OpenAI")
            
            # Encode as Base64
            img_b64 = base64.b64encode(img_response.content).decode('utf-8')

            # 3. Upload to Shopify (Using 'attachment' instead of 'original_source')
            # Use 2024-04 API version for stability
            url = f"https://{SHOP_DOMAIN}/admin/api/2024-04/files.json"
            
            payload = {
                "file": {
                    "attachment": img_b64, # Sending raw data
                    "filename": f"ai-design-{int(time.time())}.png",
                    "content_type": "image/png"
                }
            }
            
            headers = {
                "X-Shopify-Access-Token": ACCESS_TOKEN,
                "Content-Type": "application/json"
            }

            response = requests.post(url, json=payload, headers=headers)
            
            # 4. Handle Response
            if response.status_code == 201:
                response_json = response.json()
                file_data = response_json.get('file', {})
                
                # We need to wait for the public URL, but usually 'url' is provided in the response
                # If it's null, we might need to use the 'original_source' or fallback
                # For this method, 'url' should be available or 'preview_image' > 'src'
                
                permanent_url = file_data.get('url')
                if not permanent_url:
                     # Fallback if URL isn't ready instantly (rare with base64)
                     permanent_url = "File Uploaded to Shopify Admin (Processing)"

                response_data = {
                    "success": True, 
                    "permanent_url": permanent_url 
                }
                self.wfile.write(json.dumps(response_data).encode('utf-8'))
            else:
                # IMPORTANT: pass back the exact error text from Shopify for debugging
                raise Exception(f"Shopify Rejected: {response.text}")

        except Exception as e:
            self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
