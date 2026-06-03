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

            # Create a unique filename
            saved_filename = f"ai-narrative-{int(time.time())}.png"

            graphql_url = f"https://{SHOP_DOMAIN}/admin/api/2025-10/graphql.json"
            
            mutation = """
            mutation fileCreate($files: [FileCreateInput!]!) {
              fileCreate(files: $files) {
                files {
                  id
                  fileStatus
                }
                userErrors {
                  message
                }
              }
            }
            """
            
            variables = {
              "files": [
                {
                  "originalSource": temp_url,
                  "filename": saved_filename, # We track this name
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
            
            if response.status_code == 200:
                result = response.json()
                user_errors = result.get('data', {}).get('fileCreate', {}).get('userErrors', [])
                if user_errors:
                    raise Exception(f"GraphQL Error: {user_errors[0]['message']}")

                # Return the FILENAME to the frontend
                response_data = { 
                    "success": True, 
                    "filename": saved_filename 
                }
                self.wfile.write(json.dumps(response_data).encode('utf-8'))
            else:
                raise Exception(f"Shopify Error: {response.status_code}")

        except Exception as e:
            self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
