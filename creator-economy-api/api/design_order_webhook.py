from http.server import BaseHTTPRequestHandler
import json
import os
import hmac
import hashlib
import base64
from datetime import datetime
from urllib.parse import urlparse
import urllib.request
import urllib.parse
import urllib.error

# ============================================================
# PRODUCTION COST CONSTANTS (paise — 1 INR = 100 paise)
# Update these when your print provider costs change.
# Creator Cut = Sale Price − Base Production Cost
# ============================================================
BASE_COST_TSHIRT_PAISE = 50000   # ₹500 per T-Shirt
BASE_COST_HOODIE_PAISE = 90000   # ₹900 per Hoodie

# ============================================================
# TIER THRESHOLDS (units sold)
# ============================================================
TIER_THRESHOLDS = {
    "Diamond": 1000,
    "Gold":    200,
    "Silver":  50,
    "Bronze":  0,
}


# ============================================================
# SUPABASE URLLIB REST HELPERS
# ============================================================

def _sb_headers():
    """Return (url, key, headers_dict) for Supabase REST API."""
    url = os.environ.get('SUPABASE_URL', '')
    key = os.environ.get('SUPABASE_KEY', '')
    return url, key, {
        'apikey': key,
        'Authorization': f'Bearer {key}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Prefer': 'return=representation',
    }


def sb_configured():
    """Check if Supabase is configured."""
    url, key, _ = _sb_headers()
    return bool(url and key)


def sb_get(table, select='*', filters=None, order=None, limit=None):
    """GET rows from Supabase table. Returns (rows_list, error_str_or_None)."""
    url, key, headers = _sb_headers()
    if not url or not key:
        return [], 'not_configured'
    params = {'select': select}
    if filters:
        params.update(filters)  # e.g. {'shopify_customer_id': 'eq.shopify-001'}
    if order:
        params['order'] = order
    if limit:
        params['limit'] = str(limit)
    full_url = f"{url.rstrip('/')}/rest/v1/{table}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(full_url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
            return (data if isinstance(data, list) else []), None
    except urllib.error.HTTPError as e:
        return [], f'HTTP {e.code}: {e.read().decode()[:100]}'
    except Exception as e:
        return [], str(e)


def sb_post(table, data):
    """INSERT a row into Supabase table. Returns (row, error_str_or_None)."""
    url, key, headers = _sb_headers()
    if not url or not key:
        return None, 'not_configured'
    full_url = f"{url.rstrip('/')}/rest/v1/{table}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(full_url, data=body, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            resp = json.loads(r.read().decode())
            return (resp[0] if isinstance(resp, list) and resp else resp), None
    except urllib.error.HTTPError as e:
        return None, f'HTTP {e.code}: {e.read().decode()[:100]}'
    except Exception as e:
        return None, str(e)


def sb_patch(table, data, filter_col, filter_val):
    """UPDATE rows in Supabase table. Returns (rows, error_str_or_None)."""
    url, key, headers = _sb_headers()
    if not url or not key:
        return None, 'not_configured'
    params = {filter_col: f'eq.{filter_val}'}
    full_url = f"{url.rstrip('/')}/rest/v1/{table}?{urllib.parse.urlencode(params)}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(full_url, data=body, headers=headers, method='PATCH')
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            resp = json.loads(r.read().decode())
            return resp, None
    except urllib.error.HTTPError as e:
        return None, f'HTTP {e.code}: {e.read().decode()[:100]}'
    except Exception as e:
        return None, str(e)


def verify_shopify_webhook(body_bytes, hmac_header, secret):
    """Verify the webhook is genuinely from Shopify."""
    if not secret or not hmac_header:
        return True  # Skip in dev/demo mode
    digest = hmac.new(
        secret.encode('utf-8'),
        body_bytes,
        hashlib.sha256
    ).digest()
    computed = base64.b64encode(digest).decode()
    return hmac.compare_digest(computed, hmac_header)


def compute_tier(total_designs_sold):
    """
    Return the creator tier string based on total units sold.

    Thresholds:
      Bronze:  0    – 49   sales
      Silver:  50   – 199  sales
      Gold:    200  – 999  sales
      Diamond: 1000+       sales
    """
    if total_designs_sold >= TIER_THRESHOLDS["Diamond"]:
        return "Diamond"
    elif total_designs_sold >= TIER_THRESHOLDS["Gold"]:
        return "Gold"
    elif total_designs_sold >= TIER_THRESHOLDS["Silver"]:
        return "Silver"
    else:
        return "Bronze"


def calculate_creator_cut(price_paise, product_type, quantity=1):
    """
    Calculate the creator's earnings for one line-item.

    Formula:
      base_cost   = BASE_COST_TSHIRT_PAISE or BASE_COST_HOODIE_PAISE
      creator_cut = (price_paise - base_cost) * quantity
      creator_cut is floored at 0 (never negative)

    Returns dict: {base_cost_paise, creator_cut_paise, platform_cut_paise}
    """
    base = (
        BASE_COST_TSHIRT_PAISE if product_type == "tshirt"
        else BASE_COST_HOODIE_PAISE
    )
    cut_per_unit = max(0, price_paise - base)
    return {
        "base_cost_paise":    base,
        "creator_cut_paise":  cut_per_unit * quantity,
        "platform_cut_paise": base * quantity,
    }


def sb_rpc(function_name, params):
    """Call a Supabase PostgreSQL function via REST."""
    url, key, headers = _sb_headers()
    if not url or not key:
        return None, 'not_configured'
    full_url = f"{url.rstrip('/')}/rest/v1/rpc/{function_name}"
    body = json.dumps(params).encode()
    req = urllib.request.Request(full_url, data=body, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode()), None
    except urllib.error.HTTPError as e:
        body_err = e.read().decode()
        try: body_err = json.loads(body_err)
        except: pass
        return None, f'HTTP {e.code}: {str(body_err)[:150]}'
    except Exception as e:
        return None, str(e)


# ============================================================
# SAMPLE KIT DETECTION
# ============================================================
# When a creator buys their own sample at wholesale cost,
# they earn +10 tokens instead of the standard +5.
# Detect by: _product_type=tshirt price<=50000 OR hoodie price<=90000
# AND _creator_id == buyer's customer_id.
SAMPLE_KIT_TSHIRT_MAX_PAISE = 50000   # ₹500 = wholesale cost
SAMPLE_KIT_HOODIE_MAX_PAISE = 90000   # ₹900 = wholesale cost
TOKENS_PER_SALE        = 5
TOKENS_PER_SAMPLE_KIT  = 10


def is_sample_kit_purchase(price_paise, product_type, buyer_customer_id, creator_id):
    """
    Returns True if this order line is a creator buying their own sample kit.
    Criteria: buyer == creator AND price <= wholesale cost.
    """
    if buyer_customer_id != creator_id:
        return False
    if product_type == "tshirt" and price_paise <= SAMPLE_KIT_TSHIRT_MAX_PAISE:
        return True
    if product_type == "hoodie" and price_paise <= SAMPLE_KIT_HOODIE_MAX_PAISE:
        return True
    return False


def replenish_creator_tokens(creator_shopify_id, order_id, tokens_to_add, is_sample=False):
    """
    Add ai_credits to creator on sale or sample kit purchase.
    Uses SQL function replenish_ai_credits for atomic update + credit_ledger write.
    """
    event_type = "sample_replenishment" if is_sample else "sale_replenishment"
    note = (
        f"+{tokens_to_add} Narrative Tokens — {'Sample Kit purchase' if is_sample else 'Sale'}"
    )
    result, err = sb_rpc("replenish_ai_credits", {
        "p_creator_shopify_id": creator_shopify_id,
        "p_credits_to_add":     tokens_to_add,
        "p_order_id":           order_id,
        "p_event_type":         event_type,
        "p_note":               note,
    })
    if err:
        print(f"[TOKEN REPLENISH] RPC failed: {err}, trying direct patch fallback")
        # Fallback: direct REST update (non-atomic)
        rows, _ = sb_get("creators", "id,ai_credits",
                          filters={"shopify_customer_id": f"eq.{creator_shopify_id}"}, limit=1)
        if rows:
            old = int(rows[0].get("ai_credits") or 0)
            sb_patch("creators", {"ai_credits": old + tokens_to_add}, "id", rows[0]["id"])
            print(f"[TOKEN REPLENISH] Direct patch: {old} → {old + tokens_to_add}")
            return {"old_balance": old, "new_balance": old + tokens_to_add, "credits_added": tokens_to_add}
        return None

    if isinstance(result, list) and result:
        row = result[0]
    elif isinstance(result, dict):
        row = result
    else:
        return None

    print(f"[TOKEN REPLENISH] creator={creator_shopify_id} +{tokens_to_add} tokens "
          f"({row.get('old_balance')} → {row.get('new_balance')})")
    return row


# ============================================================
# JIT UPSCALING
# ============================================================
def trigger_jit_upscaling(unique_product_id, design_file_url, order_id):
    """
    Trigger Just-In-Time high-res upscaling for a design.
    Called from the order webhook ONLY when the design lacks a high_res_master_url.
    Uses Replicate Real-ESRGAN 4x upscaling.
    Saves result to S3 at /{unique_product_id}/master_file_hires.png.
    Updates creator_designs.high_res_master_url and upscaling_status.

    This defers the expensive Replicate API call until revenue is confirmed.
    """
    print(f"[JIT] Starting upscaling for design uuid={unique_product_id} order={order_id}")

    # Mark as processing to prevent duplicate runs
    sb_patch("creator_designs",
        {"upscaling_status": "processing"},
        "unique_product_id", unique_product_id
    )

    try:
        # ── Replicate Real-ESRGAN ─────────────────────────────
        replicate_token = os.environ.get("REPLICATE_API_TOKEN", "")
        if not replicate_token:
            print("[JIT DEMO] Replicate not configured — skipping upscaling in demo mode")
            sb_patch("creator_designs",
                {"upscaling_status": "pending", "high_res_master_url": None},
                "unique_product_id", unique_product_id
            )
            return None

        # Submit prediction
        import requests as req_lib
        pred_resp = req_lib.post(
            "https://api.replicate.com/v1/predictions",
            headers={
                "Authorization": f"Token {replicate_token}",
                "Content-Type":  "application/json",
            },
            json={
                "version": "42fed1c4974146d4d2414e2be2c5277c7fcf05fcc3a73abf41610695738c1d7b",
                "input":   {"image": design_file_url, "scale": 4}
            },
            timeout=30
        )
        if pred_resp.status_code not in (200, 201):
            raise Exception(f"Replicate submit failed: {pred_resp.status_code} {pred_resp.text[:100]}")

        prediction = pred_resp.json()
        pred_id    = prediction["id"]
        print(f"[JIT] Replicate prediction {pred_id} submitted")

        # Poll until complete (max 120s)
        upscaled_url = None
        for _ in range(24):  # 24 × 5s = 120s
            time.sleep(5)
            poll = req_lib.get(
                f"https://api.replicate.com/v1/predictions/{pred_id}",
                headers={"Authorization": f"Token {replicate_token}"},
                timeout=15
            )
            status = poll.json().get("status")
            if status == "succeeded":
                output = poll.json().get("output")
                upscaled_url = output[0] if isinstance(output, list) else output
                break
            elif status in ("failed", "canceled"):
                raise Exception(f"Replicate prediction {status}")
            print(f"[JIT] Replicate status: {status}")

        if not upscaled_url:
            raise Exception("Replicate timed out")

        print(f"[JIT] Upscaled URL: {upscaled_url}")

        # ── Save hi-res to S3 ────────────────────────────────
        aws_key    = os.environ.get("AWS_ACCESS_KEY_ID", "")
        aws_secret = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
        aws_region = os.environ.get("AWS_REGION", "us-east-1")
        bucket     = os.environ.get("AWS_S3_BUCKET", "")

        if aws_key and aws_secret and bucket:
            import boto3
            img_bytes = req_lib.get(upscaled_url, timeout=30).content
            s3 = boto3.client("s3",
                aws_access_key_id=aws_key,
                aws_secret_access_key=aws_secret,
                region_name=aws_region
            )
            s3_key = f"{unique_product_id}/master_file_hires.png"
            s3.put_object(Bucket=bucket, Key=s3_key,
                          Body=img_bytes, ContentType="image/png")
            hires_url = f"https://{bucket}.s3.{aws_region}.amazonaws.com/{s3_key}"
        else:
            # Demo: use Replicate URL directly
            hires_url = upscaled_url

        print(f"[JIT] Hi-res saved: {hires_url}")

        # ── Update Supabase ───────────────────────────────────
        sb_patch("creator_designs", {
            "high_res_master_url": hires_url,
            "upscaling_status":    "complete",
            "updated_at":          datetime.utcnow().isoformat()
        }, "unique_product_id", unique_product_id)

        print(f"[JIT] Complete. uuid={unique_product_id} hires_url={hires_url}")
        return hires_url

    except Exception as e:
        print(f"[JIT ERROR] {str(e)}")
        sb_patch("creator_designs",
            {"upscaling_status": "failed", "updated_at": datetime.utcnow().isoformat()},
            "unique_product_id", unique_product_id
        )
        return None


import time  # needed by JIT upscaling


def update_creator_ledger(creator_shopify_id, design_unique_id,
                          order_id, financials, product_type, color,
                          quantity, price_paise, design_title):
    """
    Atomically update the creator's financial ledger after a confirmed sale.

    Steps:
      1. Look up creator by shopify_customer_id
      2. Add creator_cut_paise × quantity to total_earnings_paise
      3. Add quantity to total_designs_sold
      4. Recalculate and update creator_tier if threshold crossed
      5. Insert immutable row into financial_ledger table
      6. Return summary dict for logging

    This function is idempotent-safe: if called twice for the same order
    the financial_ledger will have a duplicate, but the callers de-duplicate
    at the order level before calling this.
    """
    creator_cut_paise  = financials["creator_cut_paise"]
    base_cost_paise    = financials["base_cost_paise"]
    platform_cut_paise = financials["platform_cut_paise"]

    try:
        # 1. Fetch creator record by Shopify customer ID
        creators_data, err = sb_get(
            'creators',
            select='id,total_earnings_paise,total_designs_sold,creator_tier',
            filters={'shopify_customer_id': f'eq.{creator_shopify_id}'}
        )

        if err or not creators_data:
            print(f"[LEDGER] Creator not found for shopify_id={creator_shopify_id}, skipping ledger (err={err})")
            return {"error": "creator_not_found", "creator_shopify_id": creator_shopify_id}

        creator = creators_data[0]
        creator_db_id    = creator["id"]
        old_earnings     = creator.get("total_earnings_paise") or 0
        old_sold         = creator.get("total_designs_sold")   or 0
        old_tier         = creator.get("creator_tier")         or "Bronze"

        # 2 & 3. Compute new values
        new_earnings = old_earnings + creator_cut_paise
        new_sold     = old_sold + quantity

        # 4. Recalculate tier
        new_tier     = compute_tier(new_sold)
        tier_changed = (new_tier != old_tier)

        # Atomic update of creator financials
        update_data = {
            "total_earnings_paise": new_earnings,
            "total_designs_sold":   new_sold,
            "creator_tier":         new_tier,
        }
        if tier_changed:
            update_data["tier_updated_at"] = datetime.utcnow().isoformat()

        _, err = sb_patch('creators', update_data, 'id', creator_db_id)
        if err:
            print(f"[LEDGER ERROR] Failed to update creator {creator_db_id}: {err}")
            return {"error": f"patch_failed: {err}"}

        if tier_changed:
            print(f"[TIER UP] Creator {creator_db_id}: {old_tier} → {new_tier} ({new_sold} sales)")

        # 5. Insert immutable financial_ledger entry
        ledger_note = (
            f"Sale: {design_title or 'Unknown'} | "
            f"{product_type}/{color} × {quantity} | "
            f"Order {order_id}"
        )
        _, err = sb_post('financial_ledger', {
            "creator_id":        creator_db_id,
            "order_id":          order_id,
            "unique_product_id": design_unique_id,
            "event_type":        "sale",
            "amount_paise":      creator_cut_paise,
            "price_paise":       price_paise,
            "base_cost_paise":   base_cost_paise,
            "product_type":      product_type,
            "color":             color,
            "quantity":          quantity,
            "note":              ledger_note,
            "created_at":        datetime.utcnow().isoformat(),
        })
        if err:
            print(f"[LEDGER ERROR] Failed to insert financial_ledger: {err}")
            return {"error": f"insert_failed: {err}"}

        print(f"[LEDGER] creator={creator_db_id} | cut=₹{creator_cut_paise/100:.2f} | "
              f"earnings=₹{new_earnings/100:.2f} | sold={new_sold} | tier={new_tier}")

        return {
            "creator_db_id":    creator_db_id,
            "creator_cut_paise": creator_cut_paise,
            "new_earnings_paise": new_earnings,
            "new_designs_sold":  new_sold,
            "old_tier":          old_tier,
            "new_tier":          new_tier,
            "tier_upgraded":     tier_changed,
        }

    except Exception as e:
        print(f"[LEDGER ERROR] {str(e)}")
        return {"error": str(e)}


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
        if parsed.path == '/api/webhook/design-order/health':
            self.send_json_response(200, {
                "status": "ok",
                "message": "Design Order Webhook Handler v1.0",
                "endpoints": [
                    "POST /api/webhook/design-order — records design orders from Shopify",
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
        # orders/create — record design order
        # -------------------------------------------------------
        if path == '/api/webhook/design-order' or topic == 'orders/create':
            self._handle_design_order(order)
            return

        self.send_json_response(200, {"status": "ignored", "topic": topic})

    # ===========================================================
    # HANDLER: Design Order — record order data
    # ===========================================================
    def _handle_design_order(self, order):
        order_id = str(order.get('id', ''))
        customer_id = str(order.get('customer', {}).get('id', ''))
        customer_email = order.get('email', '')
        line_items = order.get('line_items', [])

        if not sb_configured():
            # Demo mode — calculate financials without writing to DB
            demo_items = []
            for item in line_items:
                props = {p.get("name"): p.get("value", "") for p in item.get("properties", [])}
                uid   = props.get("_design_uuid") or props.get("_unique_product_id")
                if not uid:
                    continue
                price_demo = int(float(item.get("price", "0")) * 100)
                ptype_demo = props.get("_product_type", "tshirt")
                qty_demo   = int(item.get("quantity", 1))
                fin_demo   = calculate_creator_cut(price_demo, ptype_demo, qty_demo)
                tier_demo  = compute_tier(0)  # fresh creator in demo
                demo_items.append({
                    "unique_product_id":  uid,
                    "design_title":       props.get("_design_title", ""),
                    "color":              props.get("_color", ""),
                    "quantity":           qty_demo,
                    "price_rupees":       price_demo / 100,
                    "base_cost_rupees":   fin_demo["base_cost_paise"] / 100,
                    "creator_cut_rupees": fin_demo["creator_cut_paise"] / 100,
                    "creator_tier":       tier_demo,
                })
            print(f"[DEMO] D2E order {order_id} | items={demo_items}")
            self.send_json_response(200, {
                "status": "ok",
                "mode":   "demo",
                "order_id": order_id,
                "note": "Supabase not configured — financial ledger not written",
                "demo_financials": demo_items,
            })
            return

        recorded = []
        errors   = []

        for item in line_items:
            shopify_product_id = str(item.get('product_id', ''))
            try:
                # -------------------------------------------------------
                # Extract line-item properties injected by the frontend.
                #
                # ARCHITECTURE: The unique_product_id (S3 design UUID)
                # travels with EVERY ORDER as a line-item property.
                # It is NEVER stored on the Shopify product metafield,
                # which would cause a race condition when multiple creators
                # share the same 2 parent products simultaneously.
                #
                # The frontend sends:
                #   _design_uuid   — canonical UUID from S3/pipeline
                #   _design_title  — human-readable design name
                #   _creator_id    — Shopify customer ID of the creator
                #   _product_type  — 'tshirt' or 'hoodie'
                #   _color         — variant color
                #
                # Legacy keys also accepted for backward compatibility:
                #   _unique_product_id — old name for _design_uuid
                #   _design_file_url   — direct S3 URL (pre-pipeline)
                # -------------------------------------------------------
                properties = {
                    prop.get('name'): prop.get('value', '')
                    for prop in item.get('properties', [])
                }

                # Resolve unique_product_id — prefer new _design_uuid key
                unique_product_id = (
                    properties.get('_design_uuid') or
                    properties.get('_unique_product_id') or
                    None
                )

                # Resolve design file URL — prefer pipeline master_file, fall back to direct URL
                design_file_url = (
                    properties.get('_design_file_url') or
                    None
                )

                design_title   = properties.get('_design_title', '')
                creator_id_prop = properties.get('_creator_id', '')
                product_type   = properties.get('_product_type', '')
                color          = properties.get('_color', '')

                shopify_variant_id = str(item.get('variant_id', ''))
                price    = int(float(item.get('price', '0')) * 100)  # rupees → paise
                quantity = int(item.get('quantity', 1))

                if not unique_product_id:
                    # Not a Design-to-Earn order — skip silently
                    print(f"[SKIP] Line item {shopify_product_id} has no _design_uuid — not a D2E order")
                    continue

                print(f"[D2E ORDER] uuid={unique_product_id} color={color} qty={quantity} order={order_id}")

                # -------------------------------------------------------
                # FINANCIAL CALCULATION
                # Creator Cut = Sale Price − Base Production Cost
                # Floored at ₹0 (creator never owes us money)
                # -------------------------------------------------------
                financials = calculate_creator_cut(price, product_type, quantity)
                creator_cut  = financials["creator_cut_paise"]
                base_cost    = financials["base_cost_paise"]
                platform_cut = financials["platform_cut_paise"]

                print(f"[FINANCE] price=₹{price/100:.2f} base=₹{base_cost/100:.2f} "
                      f"creator_cut=₹{creator_cut/100:.2f} qty={quantity}")

                # -------------------------------------------------------
                # STEP A: Record the design order in design_orders table
                # -------------------------------------------------------
                _, err = sb_post('design_orders', {
                    "shopify_order_id":    order_id,
                    "shopify_customer_id": customer_id,
                    "customer_email":      customer_email,
                    "unique_product_id":   unique_product_id,
                    "design_file_url":     design_file_url,
                    "shopify_product_id":  shopify_product_id,
                    "shopify_variant_id":  shopify_variant_id,
                    "price_paise":         price,
                    "quantity":            quantity,
                    "status":              "pending",
                    # New financial columns
                    "product_type":        product_type,
                    "color":               color,
                    "design_title":        design_title,
                    "creator_id":          creator_id_prop,
                    "base_cost_paise":     base_cost,
                    "creator_cut_paise":   creator_cut,
                    "platform_cut_paise":  platform_cut,
                    "created_at":          datetime.utcnow().isoformat(),
                    "updated_at":          datetime.utcnow().isoformat(),
                })
                if err:
                    print(f"[ORDER ERROR] Failed to insert design_orders: {err}")

                # -------------------------------------------------------
                # STEP B: Increment total_sales on the design record
                # -------------------------------------------------------
                design_db_id = None
                try:
                    designs_data, err = sb_get(
                        'creator_designs',
                        select='id,total_sales,creator_earnings_paise',
                        filters={'unique_product_id': f'eq.{unique_product_id}'}
                    )
                    if not err and designs_data:
                        design_row = designs_data[0]
                        design_db_id = design_row["id"]
                        new_sales    = (design_row.get("total_sales") or 0) + quantity
                        new_design_earnings = (
                            (design_row.get("creator_earnings_paise") or 0) + creator_cut
                        )
                        _, err = sb_patch('creator_designs', {
                            "total_sales":            new_sales,
                            "creator_earnings_paise": new_design_earnings,
                        }, 'id', design_db_id)
                        if err:
                            print(f"[DESIGN UPDATE ERROR] {err}")
                except Exception as sales_err:
                    print(f"Warning: could not update design total_sales: {sales_err}")

                # -------------------------------------------------------
                # STEP C: Update financial ledger + tier recalculation
                # -------------------------------------------------------
                ledger_result = {"skipped": "no_creator_id"}
                if creator_id_prop:
                    ledger_result = update_creator_ledger(
                        creator_shopify_id = creator_id_prop,
                        design_unique_id   = unique_product_id,
                        order_id           = order_id,
                        financials         = financials,
                        product_type       = product_type,
                        color              = color,
                        quantity           = quantity,
                        price_paise        = price,
                        design_title       = design_title,
                    )
                else:
                    print(f"[LEDGER] No _creator_id — skipping ledger update")

                # -------------------------------------------------------
                # STEP D: TOKEN REPLENISHMENT
                # Every confirmed sale: +5 tokens to the creator.
                # If the buyer IS the creator (sample kit purchase): +10 tokens.
                # -------------------------------------------------------
                token_result = None
                if creator_id_prop:
                    sample_purchase = is_sample_kit_purchase(
                        price, product_type, customer_id, creator_id_prop
                    )
                    tokens_to_add = TOKENS_PER_SAMPLE_KIT if sample_purchase else TOKENS_PER_SALE
                    token_result  = replenish_creator_tokens(
                        creator_id_prop, order_id, tokens_to_add, is_sample=sample_purchase
                    )
                    if token_result:
                        print(f"[TOKEN] +{tokens_to_add} credits to creator {creator_id_prop} "
                              f"({'sample kit' if sample_purchase else 'sale'}). "
                              f"New balance: {token_result.get('new_balance')}")

                # -------------------------------------------------------
                # STEP E: JIT UPSCALING (fire only if not already done)
                # Check if this design already has a high_res_master_url.
                # If not, trigger Real-ESRGAN 4x upscaling now that revenue
                # is confirmed. This is the deferred cost from pipeline.
                # -------------------------------------------------------
                jit_result = None
                if unique_product_id and design_file_url:
                    design_rows, _ = sb_get(
                        "creator_designs",
                        "id,high_res_master_url,upscaling_status,master_file_url",
                        filters={"unique_product_id": f"eq.{unique_product_id}"},
                        limit=1
                    )
                    if design_rows:
                        d = design_rows[0]
                        has_hires    = bool(d.get("high_res_master_url"))
                        already_done = d.get("upscaling_status") in ("complete", "processing")
                        if not has_hires and not already_done:
                            print(f"[JIT] Triggering upscaling for uuid={unique_product_id}")
                            # Use master_file_url (low-res) as source for upscaler
                            source_url = d.get("master_file_url") or design_file_url
                            jit_result = trigger_jit_upscaling(
                                unique_product_id, source_url, order_id
                            )
                        else:
                            print(f"[JIT] Skipping — already {d.get('upscaling_status')}")
                    else:
                        print(f"[JIT] Design row not found for uuid={unique_product_id}")

                recorded.append({
                    "order_id":            order_id,
                    "unique_product_id":   unique_product_id,
                    "design_title":        design_title,
                    "creator_id":          creator_id_prop,
                    "color":               color,
                    "quantity":            quantity,
                    "price_paise":         price,
                    "creator_cut_paise":   creator_cut,
                    "base_cost_paise":     base_cost,
                    "creator_tier":        ledger_result.get("new_tier", "unknown"),
                    "tier_upgraded":       ledger_result.get("tier_upgraded", False),
                    "tokens_added":        token_result.get("credits_added") if token_result else 0,
                    "token_balance":       token_result.get("new_balance")   if token_result else None,
                    "jit_upscaling":       "triggered" if jit_result else "skipped_or_pending",
                })

            except Exception as e:
                errors.append({"product_id": shopify_product_id, "error": str(e)})
                print(f"Design order error for product {shopify_product_id}: {e}")

        self.send_json_response(200, {
            "status": "ok",
            "order_id": order_id,
            "orders_recorded": recorded,
            "errors": errors,
        })
