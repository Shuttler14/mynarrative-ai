from http.server import BaseHTTPRequestHandler
import json
import requests
import base64
import time

# --- DEBUG MODE: HARDCODED CREDENTIALS ---
# 1. Go to Shopify Admin > Settings > Domains. Copy the .myshopify.com one.
#    Example: "mynarrative.myshopify.com" (NO https://, NO slashes)
SHOP_DOMAIN = "jjdk0v-0c.myshopify.com" 

# 2. Go to Shopify Admin > Apps > Develop Apps > Credentials. Copy the shpat_ token.
ACCESS_TOKEN = "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"
# -----------------------------------------

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

            img_response = requests.get(temp_url)
            if img_response.status_code != 200:
                raise Exception("Could not download image from OpenAI")
            
            img_b64 = base64.b64encode(img_response.content).decode('utf-8')

            # Using 2024-01 API version which is very stable
            url = f"https://{SHOP_DOMAIN}/admin/api/2024-01/files.json"
            
            payload = {
                "file": {
                    "attachment": img_b64,
                    "filename": f"ai-design-{int(time.time())}.png",
                    "content_type": "image/png"
                }
            }
            
            headers = {
                "X-Shopify-Access-Token": ACCESS_TOKEN,
                "Content-Type": "application/json"
            }

            response = requests.post(url, json=payload, headers=headers)
            
            if response.status_code == 201:
                file_data = response.json().get('file', {})
                # Try to get the URL, fallback to 'original_source' if needed
                permanent_url = file_data.get('url') or file_data.get('original_source')
                
                response_data = { "success": True, "permanent_url": permanent_url }
                self.wfile.write(json.dumps(response_data).encode('utf-8'))
            else:
                # DEBUGGING: We are now printing the STATUS CODE + TEXT
                error_msg = f"Status: {response.status_code} | Body: {response.text}"
                raise Exception(f"Shopify Rejected: {error_msg}")

        except Exception as e:
            self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
