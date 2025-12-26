from http.server import BaseHTTPRequestHandler
import json
import requests

# --- YOUR CREDENTIALS ---
SHOP_DOMAIN = "jjdk0v-0c.myshopify.com"
ACCESS_TOKEN = "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"
# ------------------------

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain') # Plain text for easier reading
        self.end_headers()

        log = []
        log.append(f"Testing Connection to: {SHOP_DOMAIN}")
        
        # We will try 3 different API versions to see which one your store accepts
        versions_to_try = ["2025-10", "2025-07", "2025-04"]
        
        success_version = None

        for version in versions_to_try:
            url = f"https://{SHOP_DOMAIN}/admin/api/{version}/shop.json"
            log.append(f"\n--- Trying Version: {version} ---")
            
            headers = {
                "X-Shopify-Access-Token": ACCESS_TOKEN,
                "Content-Type": "application/json",
                "Accept": "application/json" # CRITICAL FIX for 406 Errors
            }

            try:
                response = requests.get(url, headers=headers)
                log.append(f"Status Code: {response.status_code}")
                
                if response.status_code == 200:
                    shop_name = response.json().get('shop', {}).get('name', 'Unknown')
                    log.append(f"✅ SUCCESS! Connected to shop: '{shop_name}'")
                    success_version = version
                    break # We found a working version!
                else:
                    log.append(f"❌ Failed. Response: {response.text}")

            except Exception as e:
                log.append(f"❌ Network Error: {str(e)}")

        # Output results
        if success_version:
            log.append(f"\n\nFINAL RESULT: Use API Version '{success_version}'")
        else:
            log.append(f"\n\nFINAL RESULT: All versions failed. Check Token permissions.")
            
        self.wfile.write("\n".join(log).encode('utf-8'))
