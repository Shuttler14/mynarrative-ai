from http.server import BaseHTTPRequestHandler
import json
import requests
import os

# --- HARDCODED CREDENTIALS ---
SHOP_DOMAIN = "jjdk0v-0c.myshopify.com" 
ACCESS_TOKEN = "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"
# -----------------------------

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

        try:
            # Try to fetch basic Shop Info (The simplest request possible)
            url = f"https://{SHOP_DOMAIN}/admin/api/2025-01/shop.json"
            
            headers = {
                "X-Shopify-Access-Token": ACCESS_TOKEN,
                "Content-Type": "application/json"
            }

            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                shop_name = response.json()['shop']['name']
                self.wfile.write(json.dumps({
                    "status": "SUCCESS", 
                    "message": f"Connected to shop: {shop_name}",
                    "token_valid": True
                }).encode('utf-8'))
            else:
                self.wfile.write(json.dumps({
                    "status": "FAILED", 
                    "code": response.status_code,
                    "error": response.text,
                    "token_valid": False
                }).encode('utf-8'))

        except Exception as e:
            self.wfile.write(json.dumps({"status": "ERROR", "message": str(e)}).encode('utf-8'))
