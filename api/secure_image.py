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
        # 1. CORS Setup
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

        try:
            # 2. Get the OpenAI URL
            content_length = int(self.headers['Content-Length'])
            data = json.loads(self.rfile.read(content_length))
            temp_url = data.get('image_url')

            if not temp_url:
                raise Exception("No image URL provided")

            # 3. Use GraphQL to Save File (More robust than REST)
            # We tell Shopify: "Here is a URL, go fetch it and save it as a file."
            graphql_url = f"https://{SHOP_DOMAIN}/admin/api/2025-10/graphql.json"
            
            mutation = """
            mutation fileCreate($files: [FileCreateInput!]!) {
              fileCreate(files: $files) {
                files {
                  id
                  fileStatus
                  alt
                  createdAt
                }
                userErrors {
                  field
                  message
                }
              }
            }
            """
            
            variables = {
              "files": [
                {
                  "originalSource": temp_url,
                  "filename": f"ai-narrative-{int(time.time())}.png",
                  "contentType": "IMAGE" 
                }
              ]
            }

            headers = {
                "X-Shopify-Access-Token": ACCESS_TOKEN,
                "Content-Type": "application/json"
            }

            response = requests.post(
                graphql_url, 
                json={"query": mutation, "variables": variables}, 
                headers=headers
            )
            
            # 4. Handle Response
            if response.status_code == 200:
                result = response.json()
                
                # Check for GraphQL logic errors
                user_errors = result.get('data', {}).get('fileCreate', {}).get('userErrors', [])
                if user_errors:
                    msg = user_errors[0]['message']
                    raise Exception(f"GraphQL Error: {msg}")

                # Success! 
                # Note: GraphQL returns the File ID immediately. The URL generates in the background.
                # Since we can't wait 5 seconds for the URL, we return the 'temp_url' to the cart
                # BUT the file IS saved in your admin for you to print later.
                
                # We return the temp_url to the cart so the user sees it instantly.
                # In your Admin > Files, the PERMANENT version will appear in a few seconds.
                
                response_data = { 
                    "success": True, 
                    "permanent_url": temp_url,
                    "message": "File is being processed by Shopify in the background"
                }
                self.wfile.write(json.dumps(response_data).encode('utf-8'))
            else:
                raise Exception(f"Shopify HTTP Error: {response.status_code} | {response.text}")

        except Exception as e:
            self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
