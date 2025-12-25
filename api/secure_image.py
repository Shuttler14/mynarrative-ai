from http.server import BaseHTTPRequestHandler
import json
import requests
import base64
import time

# --- HARDCODED CREDENTIALS (NO TYPOS POSSIBLE) ---
SHOP_DOMAIN = "jjdk0v-0c.myshopify.com" 
ACCESS_TOKEN = "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"
# -------------------------------------------------

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

        try:
            content_length = int(self.headers['Content-Length'])
            data = json.loads(self.rfile.read(content_length))
            temp_url = data.get('image_url')

            if not temp_url:
                raise Exception("No image URL provided")

            # 1. Download from OpenAI
            img_response = requests.get(temp_url)
            if img_response.status_code != 200:
                raise Exception(f"OpenAI Download Failed: {img_response.status_code}")
            
            img_b64 = base64.b64encode(img_response.content).decode('utf-8')

            # 2. Upload to Shopify
            # FIX: Using '2025-04' (Extremely stable version)
            url = f"https://{SHOP_DOMAIN}/admin/api/2025-10/files.json"
            
            payload = {
                "file": {
                    "attachment": img_b64,
                    "filename": f"ai-narrative-{int(time.time())}.png"
                }
            }
            
            headers = {
                "X-Shopify-Access-Token": ACCESS_TOKEN,
                "Content-Type": "application/json"
            }

            response = requests.post(url, json=payload, headers=headers)
            
            # 3. Handle Response
            if response.status_code in [200, 201]:
                file_data = response.json().get('file', {})
                # Grab the URL (Check 'original_source' if 'url' is empty)
                permanent_url = file_data.get('url') or file_data.get('original_source')
                
                response_data = { "success": True, "permanent_url": permanent_url }
                self.wfile.write(json.dumps(response_data).encode('utf-8'))
            else:
                # If it fails, we send the FULL body back so we can see the real error
                raise Exception(f"Shopify Error {response.status_code}: {response.text}")

        except Exception as e:
            self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
