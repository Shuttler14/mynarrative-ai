from http.server import BaseHTTPRequestHandler
import json
import requests
import base64
import time

# --- CREDENTIALS (VERIFIED WORKING) ---
SHOP_DOMAIN = "jjdk0v-0c.myshopify.com"
ACCESS_TOKEN = "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"
# --------------------------------------

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # 1. Handle CORS (Allows your store to talk to this server)
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

        try:
            # 2. Parse Incoming Data
            content_length = int(self.headers['Content-Length'])
            data = json.loads(self.rfile.read(content_length))
            temp_url = data.get('image_url')

            if not temp_url:
                raise Exception("No image URL provided")

            # 3. Download from OpenAI
            img_response = requests.get(temp_url)
            if img_response.status_code != 200:
                raise Exception(f"OpenAI Download Failed: {img_response.status_code}")
            
            img_b64 = base64.b64encode(img_response.content).decode('utf-8')

            # 4. Upload to Shopify
            # FIX: Using the verified working version 2025-10
            url = f"https://{SHOP_DOMAIN}/admin/api/2025-10/files.json"
            
            payload = {
                "file": {
                    "attachment": img_b64,
                    "filename": f"ai-narrative-{int(time.time())}.png"
                }
            }
            
            headers = {
                "X-Shopify-Access-Token": ACCESS_TOKEN,
                "Content-Type": "application/json",
                "Accept": "application/json" # <--- THIS WAS THE MISSING KEY TO FIX ERROR 406
            }

            response = requests.post(url, json=payload, headers=headers)
            
            # 5. Handle Response
            if response.status_code in [200, 201]:
                file_data = response.json().get('file', {})
                # Get the permanent URL
                permanent_url = file_data.get('url') or file_data.get('original_source')
                
                response_data = { "success": True, "permanent_url": permanent_url }
                self.wfile.write(json.dumps(response_data).encode('utf-8'))
            else:
                # If it fails, return the full error text
                raise Exception(f"Shopify Error {response.status_code}: {response.text}")

        except Exception as e:
            self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
