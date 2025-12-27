from http.server import BaseHTTPRequestHandler
import json
import requests
import base64
import os

# --- HARDCODED CREDENTIALS ---
SHOP_DOMAIN = "jjdk0v-0c.myshopify.com" 
ACCESS_TOKEN = "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"
# -----------------------------

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # 1. Verify Request (Basic)
        self.send_response(200)
        self.end_headers()

        try:
            # Parse the Order Data from Shopify
            content_length = int(self.headers['Content-Length'])
            order_data = json.loads(self.rfile.read(content_length))
            
            order_id = order_data.get('name', 'UnknownOrder') # e.g., #1001
            line_items = order_data.get('line_items', [])

            saved_files = []

            # 2. Loop through items to find AI Designs
            for item in line_items:
                properties = item.get('properties', [])
                temp_url = None
                
                # Find the '_TempImage' property we set in the frontend
                for prop in properties:
                    if prop['name'] == '_TempImage':
                        temp_url = prop['value']
                        break
                
                if temp_url:
                    print(f"Found temp image for {order_id}: {temp_url}")
                    
                    # 3. Download the Image (Before it expires!)
                    img_res = requests.get(temp_url)
                    if img_res.status_code == 200:
                        img_b64 = base64.b64encode(img_res.content).decode('utf-8')
                        
                        # 4. Upload to Shopify Files PERMANENTLY
                        # Naming it "Order_1001_Design.png" makes it easy to find
                        filename = f"Order_{order_id}_Design_{item['id']}.png"
                        
                        upload_url = f"https://{SHOP_DOMAIN}/admin/api/2025-10/files.json"
                        payload = {
                            "file": {
                                "attachment": img_b64,
                                "filename": filename,
                                "content_type": "image/png"
                            }
                        }
                        headers = {
                            "X-Shopify-Access-Token": ACCESS_TOKEN,
                            "Content-Type": "application/json"
                        }
                        
                        save_res = requests.post(upload_url, json=payload, headers=headers)
                        if save_res.status_code == 201:
                            saved_files.append(filename)

            # Optional: Log success (In a real app, we might update the order Note)
            if saved_files:
                print(f"Successfully saved {len(saved_files)} images for {order_id}")

        except Exception as e:
            print(f"Webhook Error: {str(e)}")

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()
