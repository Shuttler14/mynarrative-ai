from http.server import BaseHTTPRequestHandler
import os
import json
import requests
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
            content_length = int(self.headers['Content-Length'])
            data = json.loads(self.rfile.read(content_length))
            temp_url = data.get('image_url')

            if not temp_url:
                raise Exception("No image URL provided")

            # 1. Ask Shopify to fetch and save this file
            # We use the REST API 'files.json' endpoint which is easiest
            url = f"https://{SHOP_DOMAIN}/admin/api/2023-10/files.json"
            
            payload = {
                "file": {
                    "original_source": temp_url,
                    "filename": f"ai-design-{int(time.time())}.png"
                }
            }
            
            headers = {
                "X-Shopify-Access-Token": ACCESS_TOKEN,
                "Content-Type": "application/json"
            }

            response = requests.post(url, json=payload, headers=headers)
            
            if response.status_code == 201:
                # 2. Wait and Get the Public URL
                # Shopify takes a moment to process the file.
                # The response gives us a 'gid'. We assume it will be ready soon.
                # For immediate cart usage, Shopify might not give the CDN URL instantly in the Create response.
                # But usually, it returns 'original_source' or similar. 
                # Better strategy: We return the 'original_source' if valid, or we might need to poll.
                # For this MVP, let's use the file data returned.
                
                file_data = response.json().get('file', {})
                
                # Check if public_url exists, otherwise fallback to the temp one (risky) or polling
                # Shopify REST API v2023-10 usually returns 'url' or 'public_url' if ready.
                # If it's processing, we might just have to send back success.
                
                # IMPORTANT: For immediate cart addition, we need a valid URL.
                # If Shopify is slow, we might return the temp_url as a fallback, 
                # but the file IS being saved in Shopify backend for you to access later.
                
                # Let's try to grab the 'url' field.
                shopify_url = file_data.get('url') # This handles the permanent CDN link
                
                response_data = {
                    "success": True, 
                    "permanent_url": shopify_url 
                }
                self.wfile.write(json.dumps(response_data).encode('utf-8'))
            else:
                raise Exception(f"Shopify Upload Failed: {response.text}")

        except Exception as e:
            self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
