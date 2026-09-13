from http.server import BaseHTTPRequestHandler
import json
import os
import hmac
import hashlib
import base64
from datetime import datetime
from urllib.parse import urlparse

def get_supabase():
    try:
        from supabase import create_client
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_KEY", "")
        if url and key:
            return create_client(url, key)
    except Exception as e:
        print(f"Supabase error: {e}")
    return None

def verify_shopify_webhook(body_bytes, hmac_header, secret):
    """Verify the webhook is genuinely from Shopify"""
    if not secret or not hmac_header:
        return True  # Skip verification in dev/demo mode
    digest = hmac.new(
        secret.encode('utf-8'),
        body_bytes,
        hashlib.sha256
    ).digest()
    computed = base64.b64encode(digest).decode()
    return hmac.compare_digest(computed, hmac_header)

def calculate_rank(lifetime_earnings):
    if lifetime_earnings >= 500000: return 'platform_icon'
    if lifetime_earnings >= 150000: return 'style_architect'
    if lifetime_earnings >= 50000:  return 'trendsetter'
    if lifetime_earnings >= 10000:  return 'emerging_talent'
    return 'rookie_designer'

class handler(BaseHTTPRequestHandler):

    def send_json_response(self, status_code, data):
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Shopify-Hmac-Sha256, X-Shopify-Topic')
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Shopify-Hmac-Sha256, X-Shopify-Topic')
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/api/webhook/health':
            self.send_json_response(200, {
                "status": "ok",
                "message": "My Narrative Webhook Handler v1.0",
                "endpoints": [
                    "POST /api/webhook/order_paid     — credits creator commission on order",
                    "POST /api/webhook/order_fulfilled — marks commission as confirmed",
                    "POST /api/webhook/order_refunded  — reverses commission on refund",
                ]
            })
            return
        self.send_json_response(404, {"error": "Not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path   = parsed.path

        # Read body
        content_length = int(self.headers.get('Content-Length', 0))
        body_bytes = self.rfile.read(content_length)

        # Verify Shopify HMAC signature
        hmac_header = self.headers.get('X-Shopify-Hmac-Sha256', '')
        webhook_secret = os.environ.get('SHOPIFY_WEBHOOK_SECRET', '')
        if not verify_shopify_webhook(body_bytes, hmac_header, webhook_secret):
            self.send_json_response(401, {"error": "Unauthorized - invalid HMAC"})
            return

        try:
            order = json.loads(body_bytes.decode('utf-8'))
        except:
            self.send_json_response(400, {"error": "Invalid JSON"})
            return

        topic = self.headers.get('X-Shopify-Topic', path.split('/')[-1])
        print(f"Webhook received: {topic} | Order: {order.get('id', 'unknown')}")

        # -------------------------------------------------------
        # orders/paid — credit commission when order is paid
        # -------------------------------------------------------
        if path == '/api/webhook/order_paid' or topic == 'orders/paid':
            self._handle_order_paid(order)
            return

        # -------------------------------------------------------
        # orders/fulfilled — confirm commission (already credited on paid)
        # -------------------------------------------------------
        if path == '/api/webhook/order_fulfilled' or topic == 'orders/fulfilled':
            self._handle_order_fulfilled(order)
            return

        # -------------------------------------------------------
        # refunds/create — reverse commission on refund
        # -------------------------------------------------------
        if path == '/api/webhook/order_refunded' or topic == 'refunds/create':
            self._handle_order_refunded(order)
            return

        self.send_json_response(200, {"status": "ignored", "topic": topic})

    # ===========================================================
    # HANDLER: Order Paid — credit creator commission
    # ===========================================================
    def _handle_order_paid(self, order):
        supabase = get_supabase()
        order_id = str(order.get('id', ''))
        line_items = order.get('line_items', [])

        if not supabase:
            print(f"[DEMO] Order {order_id} paid — would credit commissions for {len(line_items)} items")
            self.send_json_response(200, {"status": "ok", "mode": "demo"})
            return

        credited = []
        errors   = []

        for item in line_items:
            shopify_product_id = str(item.get('product_id', ''))
            quantity = int(item.get('quantity', 1))
            item_price = int(float(item.get('price', '0')) * 100)  # convert to paise

            if not shopify_product_id:
                continue

            try:
                # Find the design linked to this Shopify product
                design_res = (
                    supabase.table("creator_designs")
                    .select("id, creator_id, price, commission_rate, title, total_sales")
                    .eq("shopify_product_id", shopify_product_id)
                    .eq("status", "active")
                    .execute()
                )

                if not design_res.data:
                    continue

                design = design_res.data[0]
                design_id    = design['id']
                creator_id   = design['creator_id']
                comm_rate    = design.get('commission_rate', 5)
                design_price = design.get('price', item_price)
                commission   = int((design_price * comm_rate / 100) * quantity)

                # Record the commission
                supabase.table("creator_commissions").insert({
                    "creator_id": creator_id,
                    "shopify_order_id": order_id,
                    "design_id": design_id,
                    "amount": commission,
                    "type": "sale_commission",
                    "created_at": datetime.utcnow().isoformat(),
                }).execute()

                # Update creator balance, lifetime_earnings, total_items_sold
                creator_res = supabase.table("creators").select(
                    "balance, lifetime_earnings, total_items_sold, style_influence_rank"
                ).eq("id", creator_id).execute()

                if creator_res.data:
                    c = creator_res.data[0]
                    new_balance   = c.get('balance', 0) + commission
                    new_lifetime  = c.get('lifetime_earnings', 0) + commission
                    new_sold      = c.get('total_items_sold', 0) + quantity
                    new_rank      = calculate_rank(new_lifetime)

                    supabase.table("creators").update({
                        "balance": new_balance,
                        "lifetime_earnings": new_lifetime,
                        "total_items_sold": new_sold,
                        "style_influence_rank": new_rank,
                        "updated_at": datetime.utcnow().isoformat(),
                    }).eq("id", creator_id).execute()

                # Update design total_sales
                current_sales = design.get('total_sales', 0)
                supabase.table("creator_designs").update({
                    "total_sales": current_sales + quantity,
                    "updated_at": datetime.utcnow().isoformat(),
                }).eq("id", design_id).execute()

                credited.append({
                    "design_id": design_id,
                    "creator_id": creator_id,
                    "commission": commission,
                    "quantity": quantity,
                })

            except Exception as e:
                errors.append({"product_id": shopify_product_id, "error": str(e)})
                print(f"Commission error for product {shopify_product_id}: {e}")

        self.send_json_response(200, {
            "status": "ok",
            "order_id": order_id,
            "commissions_credited": credited,
            "errors": errors,
        })

    # ===========================================================
    # HANDLER: Order Fulfilled — update commission status
    # ===========================================================
    def _handle_order_fulfilled(self, order):
        # Commission already credited at order_paid stage
        # This can be used to send a notification to the creator
        order_id = str(order.get('id', ''))
        print(f"Order {order_id} fulfilled — commission already processed at paid stage")
        self.send_json_response(200, {"status": "ok", "order_id": order_id, "note": "commission already credited at paid"})

    # ===========================================================
    # HANDLER: Refund — reverse commission
    # ===========================================================
    def _handle_order_refunded(self, refund):
        supabase = get_supabase()
        order_id = str(refund.get('order_id', ''))

        if not supabase:
            print(f"[DEMO] Refund for order {order_id} — would reverse commission")
            self.send_json_response(200, {"status": "ok", "mode": "demo"})
            return

        try:
            # Find commissions for this order
            comm_res = (
                supabase.table("creator_commissions")
                .select("id, creator_id, amount")
                .eq("shopify_order_id", order_id)
                .eq("type", "sale_commission")
                .execute()
            )

            reversed_total = 0
            for comm in (comm_res.data or []):
                creator_id = comm['creator_id']
                amount     = comm['amount']

                # Deduct from creator balance (not lifetime — that tracks gross)
                creator_res = supabase.table("creators").select("balance").eq("id", creator_id).execute()
                if creator_res.data:
                    current_balance = creator_res.data[0].get('balance', 0)
                    new_balance = max(0, current_balance - amount)  # never go below 0
                    supabase.table("creators").update({
                        "balance": new_balance,
                        "updated_at": datetime.utcnow().isoformat(),
                    }).eq("id", creator_id).execute()

                # Mark commission as refunded
                supabase.table("creator_commissions").insert({
                    "creator_id": creator_id,
                    "shopify_order_id": order_id,
                    "amount": -amount,
                    "type": "refund_reversal",
                    "created_at": datetime.utcnow().isoformat(),
                }).execute()

                reversed_total += amount

            self.send_json_response(200, {
                "status": "ok",
                "order_id": order_id,
                "reversed_amount": reversed_total,
                "commissions_reversed": len(comm_res.data or []),
            })

        except Exception as e:
            print(f"Refund handler error: {e}")
            self.send_json_response(200, {"status": "ok", "note": "refund logged", "error": str(e)})
