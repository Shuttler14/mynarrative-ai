from http.server import BaseHTTPRequestHandler
import json
import requests
import base64
import os
from urllib.parse import urlparse, parse_qs

SUPABASE_AVAILABLE = False
supabase_client = None

def get_supabase():
    global supabase_client, SUPABASE_AVAILABLE
    if supabase_client is not None:
        return supabase_client
    
    try:
        from supabase import create_client
        supabase_url = os.environ.get("SUPABASE_URL", "")
        supabase_key = os.environ.get("SUPABASE_SERVICE_KEY", "")
        
        if supabase_url and supabase_key and "supabase.co" in supabase_url:
            supabase_client = create_client(supabase_url, supabase_key)
            SUPABASE_AVAILABLE = True
    except Exception as e:
        print(f"Supabase init error: {e}")
        supabase_client = None
    
    return supabase_client

SHOP_DOMAIN = os.environ.get("SHOP_DOMAIN", "mynarrative.in")
ACCESS_TOKEN = os.environ.get("SHOPIFY_ACCESS_TOKEN", "")

def get_shopify_headers():
    return {
        "X-Shopify-Access-Token": ACCESS_TOKEN,
        "Content-Type": "application/json"
    }

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

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)
        
        if path == '/api/webhook/health':
            self.send_json_response(200, {
                "status": "healthy",
                "service": "webhook-handler",
                "supabase_connected": SUPABASE_AVAILABLE
            })
            return
        
        self.send_json_response(404, {"error": "Not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        webhook_topic = self.headers.get('X-Shopify-Topic', '')
        print(f"Webhook received: {webhook_topic}")
        
        self.send_response(200)
        self.end_headers()

        try:
            content_length = int(self.headers['Content-Length'])
            order_data = json.loads(self.rfile.read(content_length))
            
            if webhook_topic == 'orders/create':
                self._handle_order_create(order_data)
            elif webhook_topic == 'products/update':
                self._handle_product_update(order_data)
            else:
                print(f"Unhandled webhook topic: {webhook_topic}")
                
        except Exception as e:
            print(f"Webhook Error: {str(e)}")

    def _handle_order_create(self, order_data):
        order_id = order_data.get('id')
        order_name = order_data.get('name', f'#{order_id}')
        customer_id = str(order_data.get('customer', {}).get('id', ''))
        line_items = order_data.get('line_items', [])
        
        print(f"Processing order: {order_name} for customer: {customer_id}")
        
        supabase = get_supabase()
        
        for item in line_items:
            product_id = str(item.get('product_id', ''))
            variant_id = str(item.get('variant_id', ''))
            properties = item.get('properties', [])
            
            creator_id = None
            is_draft_design = False
            
            for prop in properties:
                if prop.get('name') == '_CreatorId':
                    creator_id = prop.get('value')
                if prop.get('name') == '_IsDraftDesign':
                    is_draft_design = prop.get('value') == 'true'
            
            if not creator_id:
                product_meta = self._get_product_metadata(product_id)
                creator_id = product_meta.get('creator_id')
                is_draft_design = product_meta.get('is_draft_design', False)
            
            if creator_id and is_draft_design:
                print(f"Publishing draft design for creator: {creator_id}")
                
                self._publish_product(product_id)
                
                if supabase:
                    self._update_creator_design(supabase, creator_id, product_id, order_id)
                
                self._award_creator_commission(supabase, creator_id, item)
        
        if supabase and customer_id:
            self._ensure_creator_record(supabase, customer_id, order_data.get('customer', {}))

    def _get_product_metadata(self, product_id):
        if not ACCESS_TOKEN or not product_id:
            return {}
        
        try:
            url = f"https://{SHOP_DOMAIN}/admin/api/2025-01/products/{product_id}.json"
            response = requests.get(url, headers=get_shopify_headers(), timeout=10)
            
            if response.status_code == 200:
                product = response.json().get('product', {})
                metafields = product.get('metafields', [])
                
                result = {}
                for mf in metafields:
                    if mf.get('namespace') == 'creator':
                        key = mf.get('key')
                        value = mf.get('value')
                        if key == 'creator_id':
                            result['creator_id'] = value
                        elif key == 'is_draft_design':
                            result['is_draft_design'] = value == 'true'
                
                return result
        except Exception as e:
            print(f"Error fetching product metadata: {e}")
        
        return {}

    def _publish_product(self, product_id):
        if not ACCESS_TOKEN:
            print(f"Demo mode: would publish product {product_id}")
            return
        
        try:
            url = f"https://{SHOP_DOMAIN}/admin/api/2025-01/products/{product_id}.json"
            
            product_data = {
                "product": {
                    "status": "active",
                    "metafields": [
                        {
                            "namespace": "creator",
                            "key": "is_draft_design",
                            "value": "false",
                            "type": "single_line_text_field"
                        }
                    ]
                }
            }
            
            response = requests.put(url, json=product_data, headers=get_shopify_headers(), timeout=30)
            
            if response.status_code in [200, 201]:
                print(f"Successfully published product {product_id}")
            else:
                print(f"Failed to publish product: {response.status_code}")
                
        except Exception as e:
            print(f"Error publishing product: {e}")

    def _update_creator_design(self, supabase, creator_id, product_id, order_id):
        try:
            result = supabase.table("creator_designs").select("id").eq("shopify_product_id", product_id).execute()
            
            if result.data:
                supabase.table("creator_designs").update({
                    "status": "active",
                    "updated_at": "now()"
                }).eq("shopify_product_id", product_id).execute()
            else:
                creator_result = supabase.table("creators").select("id").eq("shopify_customer_id", creator_id).execute()
                
                if creator_result.data:
                    supabase.table("creator_designs").insert({
                        "creator_id": creator_result.data[0]["id"],
                        "shopify_product_id": product_id,
                        "title": "Creator Design",
                        "flux_editorial_image_url": "",
                        "price": 0,
                        "status": "active"
                    }).execute()
                    
        except Exception as e:
            print(f"Error updating creator design: {e}")

    def _award_creator_commission(self, supabase, creator_id, item):
        if not supabase:
            return
        
        try:
            price = int(float(item.get('price', 0)))
            quantity = item.get('quantity', 1)
            total_amount = price * quantity
            
            commission_rate = 15
            commission_amount = int(total_amount * (commission_rate / 100))
            
            creator_result = supabase.table("creators").select("id, balance, lifetime_earnings").eq("shopify_customer_id", creator_id).execute()
            
            if creator_result.data:
                creator = creator_result.data[0]
                new_balance = creator.get('balance', 0) + commission_amount
                new_lifetime = creator.get('lifetime_earnings', 0) + commission_amount
                
                supabase.table("creators").update({
                    "balance": new_balance,
                    "lifetime_earnings": new_lifetime,
                    "total_items_sold": creator.get('total_items_sold', 0) + quantity
                }).eq("shopify_customer_id", creator_id).execute()
                
                supabase.table("creator_commissions").insert({
                    "creator_id": creator["id"],
                    "shopify_order_id": str(item.get('id', '')),
                    "amount": commission_amount,
                    "type": "sale_commission"
                }).execute()
                
                print(f"Awarded {commission_amount} commission to creator {creator_id}")
                
        except Exception as e:
            print(f"Error awarding commission: {e}")

    def _ensure_creator_record(self, supabase, customer_id, customer_data):
        if not supabase:
            return
        
        try:
            existing = supabase.table("creators").select("id").eq("shopify_customer_id", customer_id).execute()
            
            if not existing.data:
                email = customer_data.get('email', '')
                first_name = customer_data.get('first_name', '')
                
                supabase.table("creators").insert({
                    "shopify_customer_id": customer_id,
                    "email": email,
                    "first_name": first_name,
                    "username": f"user_{customer_id[:8]}",
                    "balance": 0,
                    "lifetime_earnings": 0,
                    "commission_tier": "standard",
                    "commission_rate": 15,
                }).execute()
                
                print(f"Created creator record for customer {customer_id}")
                
        except Exception as e:
            print(f"Error creating creator record: {e}")

    def _handle_product_update(self, product_data):
        print(f"Product updated: {product_data.get('id')}")
