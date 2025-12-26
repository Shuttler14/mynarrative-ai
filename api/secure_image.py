from http.server import BaseHTTPRequestHandler
import json
import requests
import time

# --- CREDENTIALS ---
SHOP_DOMAIN = "jjdk0v-0c.myshopify.com"
ACCESS_TOKEN = "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"
# -------------------

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # 1. CORS Headers
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

        try:
            # 2. Parse Input
            content_length = int(self.headers['Content-Length'])
            data = json.loads(self.rfile.read(content_length))
            temp_url = data.get('image_url')

            if not temp_url:
                raise Exception("No image URL provided")

            # 3. Send URL to Shopify (Instead of Base64)
            # This is much lighter and prevents 406/Format errors
            url = f"https://{SHOP_DOMAIN}/admin/api/2025-10/files.json"
            
            payload = {
                "file": {
                    "original_source": temp_url, # <--- The Magic Change
                    "filename": f"ai-narrative-{int(time.time())}.png"
                }
            }
            
            headers = {
                "X-Shopify-Access-Token": ACCESS_TOKEN,
                "Content-Type": "application/json",
                "Accept": "application/json"
            }

            response = requests.post(url, json=payload, headers=headers)
            
            # 4. Handle Response
            if response.status_code in [200, 201]:
                file_data = response.json().get('file', {})
                # For "original_source", Shopify processes in background.
                # We might not get the final URL instantly, so we fallback to the source if needed.
                # Usually, it returns the 'original_source' immediately as a placeholder.
                
                permanent_url = file_data.get('url') or file_data.get('original_source') or temp_url
                
                response_data = { "success": True, "permanent_url": permanent_url }
                self.wfile.write(json.dumps(response_data).encode('utf-8'))
            else:
                raise Exception(f"Shopify Error {response.status_code}: {response.text}")

        except Exception as e:
            self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
