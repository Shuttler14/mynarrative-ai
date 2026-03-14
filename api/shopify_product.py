from http.server import BaseHTTPRequestHandler
import json
import os
import base64
import requests
from urllib.parse import urlparse, parse_qs

class handler(BaseHTTPRequestHandler):
    def send_json_response(self, status_code, data):
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(content_length).decode('utf-8'))
        except:
            self.send_json_response(400, {"success": False, "error": "Invalid JSON"})
            return

        parsed = urlparse(self.path)
        path = parsed.path
        
        if 'path' in body:
            path = body['path']

        if path == '/api/shopify/create_draft_product':
            self._create_draft_product(body)
            return

        if path == '/api/shopify/add_to_cart':
            self._add_to_cart(body)
            return

        if path == '/api/shopify/get_checkout_url':
            self._get_checkout_url(body)
            return

        self.send_json_response(404, {"error": "Not found"})

    def _get_shopify_headers(self):
        return {
            "X-Shopify-Access-Token": os.environ.get("SHOPIFY_ACCESS_TOKEN", ""),
            "Content-Type": "application/json"
        }

    def _get_shopify_domain(self):
        return os.environ.get("SHOP_DOMAIN", "mynarrative.in")

    def _create_draft_product(self, body):
        creator_id = body.get('creator_id')
        design_title = body.get('title')
        design_description = body.get('description')
        image_url = body.get('image_url')
        price = body.get('price', 1299)
        customer_id = body.get('customer_id')
        
        if not all([creator_id, design_title, image_url]):
            self.send_json_response(400, {"success": False, "error": "Missing required fields"})
            return
        
        shop_domain = self._get_shopify_domain()
        access_token = os.environ.get("SHOPIFY_ACCESS_TOKEN", "")
        
        if not access_token:
            self.send_json_response(200, {
                "success": True,
                "message": "Demo mode - product created",
                "data": {
                    "product_id": f"DEMO_{creator_id[:8]}",
                    "status": "draft",
                    "checkout_url": f"https://{shop_domain}/cart/demo"
                }
            })
            return
        
        try:
            download_response = requests.get(image_url, timeout=10)
            if download_response.status_code == 200:
                image_b64 = base64.b64encode(download_response.content).decode('utf-8')
            else:
                image_b64 = None
            
            product_data = {
                "product": {
                    "title": design_title,
                    "body_html": f"<p>{design_description}</p><p><em>Creator Design - Buy to Publish</em></p>",
                    "vendor": "My Narrative Creators",
                    "product_type": "Creator Design",
                    "status": "draft",
                    "variants": [{
                        "price": str(price),
                        "inventory_management": "shopify",
                        "inventory_policy": "deny",
                        "requires_shipping": True,
                    }],
                    "tags": ["creator-design", "buy-to-publish", f"creator_{creator_id}"],
                    "metafields": [
                        {
                            "namespace": "creator",
                            "key": "creator_id",
                            "value": creator_id,
                            "type": "single_line_text_field"
                        },
                        {
                            "namespace": "creator",
                            "key": "is_draft_design",
                            "value": "true",
                            "type": "single_line_text_field"
                        }
                    ]
                }
            }
            
            if image_b64:
                product_data["product"]["images"] = [{
                    "attachment": image_b64
                }]
            
            api_url = f"https://{shop_domain}/admin/api/2025-01/products.json"
            
            response = requests.post(
                api_url,
                json=product_data,
                headers=self._get_shopify_headers(),
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                product = response.json().get("product", {})
                product_id = str(product.get("id", ""))
                variant_id = product.get("variants", [{}])[0].get("id", "")
                
                self.send_json_response(200, {
                    "success": True,
                    "data": {
                        "product_id": product_id,
                        "variant_id": variant_id,
                        "status": "draft",
                        "title": product.get("title"),
                    }
                })
            else:
                self.send_json_response(400, {
                    "success": False,
                    "error": f"Shopify error: {response.status_code}",
                    "details": response.text[:200]
                })
                
        except Exception as e:
            self.send_json_response(500, {"success": False, "error": str(e)})

    def _add_to_cart(self, body):
        variant_id = body.get('variant_id')
        quantity = body.get('quantity', 1)
        
        if not variant_id:
            self.send_json_response(400, {"success": False, "error": "variant_id required"})
            return
        
        shop_domain = self._get_shopify_domain()
        
        self.send_json_response(200, {
            "success": True,
            "data": {
                "cart_url": f"https://{shop_domain}/cart/{variant_id}:{quantity}",
                "message": "Redirect to cart to complete purchase"
            }
        })

    def _get_checkout_url(self, body):
        variant_ids = body.get('variant_ids', [])
        
        if not variant_ids:
            self.send_json_response(400, {"success": False, "error": "variant_ids required"})
            return
        
        shop_domain = self._get_shopify_domain()
        
        cart_items = ",".join([f"{vid}:1" for vid in variant_ids])
        checkout_url = f"https://{shop_domain}/cart/{cart_items}"
        
        self.send_json_response(200, {
            "success": True,
            "data": {
                "checkout_url": checkout_url
            }
        })
