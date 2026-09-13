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
# URLLIB-BASED SUPABASE CLIENT HELPERS
# ============================================================
def _sb_headers():
    """Return (url, key, headers) for Supabase REST API."""
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
    """
    GET request to Supabase REST API.
    
    Args:
        table: Table name
        select: Comma-separated columns (default '*')
        filters: Dict of {column: f'eq.{value}'} for filtering
        order: Order clause (e.g., 'id.desc')
        limit: Row limit as string
    
    Returns:
        (data_list, error_str) tuple. data_list is [] if error.
    """
    url, key, headers = _sb_headers()
    if not url or not key:
        return [], 'not_configured'
    
    params = {'select': select}
    if filters:
        params.update(filters)
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
        error_body = e.read().decode()[:100]
        return [], f'HTTP {e.code}: {error_body}'
    except Exception as e:
        return [], str(e)


def sb_post(table, data):
    """
    POST request to Supabase REST API (insert).
    
    Args:
        table: Table name
        data: Dict to insert
    
    Returns:
        (response_obj, error_str) tuple. response_obj is None if error.
    """
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
        error_body = e.read().decode()[:100]
        return None, f'HTTP {e.code}: {error_body}'
    except Exception as e:
        return None, str(e)


def sb_patch(table, data, filter_col, filter_val, filter_col2=None, filter_val2=None):
    """
    PATCH request to Supabase REST API (update).
    
    Args:
        table: Table name
        data: Dict with fields to update
        filter_col: Column name for first filter
        filter_val: Value for first filter
        filter_col2: Optional second filter column
        filter_val2: Optional second filter value
    
    Returns:
        (response_obj, error_str) tuple. response_obj is None if error.
    """
    url, key, headers = _sb_headers()
    if not url or not key:
        return None, 'not_configured'
    
    params = {filter_col: f'eq.{filter_val}'}
    if filter_col2 and filter_val2:
        params[filter_col2] = f'eq.{filter_val2}'
    
    full_url = f"{url.rstrip('/')}/rest/v1/{table}?{urllib.parse.urlencode(params)}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(full_url, data=body, headers=headers, method='PATCH')
    
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            resp = json.loads(r.read().decode())
            return resp, None
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()[:100]
        return None, f'HTTP {e.code}: {error_body}'
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


def process_refund_ledger(creator_shopify_id, design_unique_id,
                          order_id, refund_amount_paise, product_type, color,
                          quantity, price_paise, design_title):
    """
    Atomically process a refund for a creator.

    Steps:
      1. Look up creator by shopify_customer_id
      2. Calculate new_earnings = max(0, current_earnings - refund_amount_paise)
      3. Decrement total_designs_sold by quantity (floor at 0)
      4. Recalculate tier using compute_tier(new_sold)
      5. If tier drops: update creator_tier and tier_updated_at
      6. Update creators table atomically
      7. Insert NEGATIVE row into financial_ledger (event_type='refund')
      8. Update creator_designs: decrement total_sales and creator_earnings_paise (floor at 0)
      9. Return dict with summary

    Returns dict with: creator_db_id, refund_amount_paise, new_earnings_paise,
                       new_designs_sold, old_tier, new_tier, tier_downgraded (bool)
    """
    try:
        # 1. Fetch creator record by Shopify customer ID
        creator_data, err = sb_get(
            'creators',
            'id,total_earnings_paise,total_designs_sold,creator_tier',
            filters={'shopify_customer_id': f'eq.{creator_shopify_id}'}
        )

        if err or not creator_data:
            print(f"[REFUND LEDGER] Creator not found for shopify_id={creator_shopify_id}, skipping refund ledger")
            return {"error": "creator_not_found", "creator_shopify_id": creator_shopify_id}

        creator = creator_data[0]
        creator_db_id    = creator["id"]
        old_earnings     = creator.get("total_earnings_paise") or 0
        old_sold         = creator.get("total_designs_sold")   or 0
        old_tier         = creator.get("creator_tier")         or "Bronze"

        # 2. Calculate new earnings (floor at 0, never go negative)
        new_earnings = max(0, old_earnings - refund_amount_paise)

        # 3. Decrement total_designs_sold (floor at 0)
        new_sold = max(0, old_sold - quantity)

        # 4. Recalculate tier
        new_tier = compute_tier(new_sold)
        tier_downgraded = (new_tier != old_tier) and (TIER_THRESHOLDS.get(new_tier, 0) < TIER_THRESHOLDS.get(old_tier, 0))

        # 6. Atomic update of creator financials
        update_data = {
            "total_earnings_paise": new_earnings,
            "total_designs_sold":   new_sold,
            "creator_tier":         new_tier,
        }
        if tier_downgraded:
            update_data["tier_updated_at"] = datetime.utcnow().isoformat()
        
        _, err = sb_patch('creators', update_data, 'id', creator_db_id)
        if err:
            print(f"[REFUND LEDGER] Failed to update creator: {err}")
            return {"error": f"creator_update_failed: {err}"}

        if tier_downgraded:
            print(f"[TIER DOWN] Creator {creator_db_id}: {old_tier} → {new_tier} ({new_sold} sales)")

        # 7. Insert NEGATIVE financial_ledger entry
        ledger_note = f"Refund: {design_title or 'Unknown'} | order {order_id}"
        _, err = sb_post('financial_ledger', {
            "creator_id":        creator_db_id,
            "order_id":          order_id,
            "unique_product_id": design_unique_id,
            "event_type":        "refund",
            "amount_paise":      -refund_amount_paise,  # NEGATIVE
            "price_paise":       price_paise,
            "product_type":      product_type,
            "color":             color,
            "quantity":          quantity,
            "note":              ledger_note,
            "created_at":        datetime.utcnow().isoformat(),
        })
        if err:
            print(f"[REFUND LEDGER] Failed to insert ledger entry: {err}")

        # 8. Update creator_designs: decrement total_sales and creator_earnings_paise (floor at 0)
        try:
            design_data, err = sb_get(
                'creator_designs',
                'id,total_sales,creator_earnings_paise',
                filters={'unique_product_id': f'eq.{design_unique_id}'}
            )

            if not err and design_data:
                design_row = design_data[0]
                design_db_id = design_row["id"]
                new_design_sales = max(0, (design_row.get("total_sales") or 0) - quantity)
                new_design_earnings = max(0, (design_row.get("creator_earnings_paise") or 0) - refund_amount_paise)

                _, err = sb_patch('creator_designs', {
                    "total_sales":            new_design_sales,
                    "creator_earnings_paise": new_design_earnings,
                }, 'id', design_db_id)
                if err:
                    print(f"Warning: could not update design total_sales on refund: {err}")
        except Exception as design_err:
            print(f"Warning: could not update design total_sales on refund: {design_err}")

        print(f"[REFUND LEDGER] creator={creator_db_id} | refund=₹{refund_amount_paise/100:.2f} | "
              f"earnings=₹{new_earnings/100:.2f} | sold={new_sold} | tier={new_tier}")

        return {
            "creator_db_id":       creator_db_id,
            "refund_amount_paise": refund_amount_paise,
            "new_earnings_paise":  new_earnings,
            "new_designs_sold":    new_sold,
            "old_tier":            old_tier,
            "new_tier":            new_tier,
            "tier_downgraded":     tier_downgraded,
        }

    except Exception as e:
        print(f"[REFUND LEDGER ERROR] {str(e)}")
        return {"error": str(e)}


class handler(BaseHTTPRequestHandler):

    def send_json_response(self, status_code, data):
        """Send JSON response with CORS headers."""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.send_header('Access-Control-Max-Age', '86400')
        self.end_headers()

    def do_GET(self):
        """Health check endpoint."""
        path = urlparse(self.path).path
        if path == "/api/webhook/design-refund/health":
            self.send_json_response(200, {
                "status": "ok",
                "service": "design-refund-webhook",
                "timestamp": datetime.utcnow().isoformat(),
            })
        else:
            self.send_json_response(404, {"error": "not_found"})

    def do_POST(self):
        """Main refund webhook handler."""
        path = urlparse(self.path).path

        if path != "/api/webhook/design-refund":
            self.send_json_response(404, {"error": "not_found"})
            return

        # Read request body
        content_length = int(self.headers.get('Content-Length', 0))
        body_bytes = self.rfile.read(content_length)

        # Verify HMAC signature
        hmac_header = self.headers.get('X-Shopify-Hmac-SHA256', '')
        secret = os.environ.get('SHOPIFY_WEBHOOK_SECRET', '')

        if not verify_shopify_webhook(body_bytes, hmac_header, secret):
            print("[REFUND WEBHOOK] HMAC verification failed")
            self.send_json_response(403, {"error": "invalid_hmac"})
            return

        try:
            payload = json.loads(body_bytes.decode('utf-8'))
        except json.JSONDecodeError:
            print("[REFUND WEBHOOK] Invalid JSON payload")
            self.send_json_response(400, {"error": "invalid_json"})
            return

        # Extract order_id from the payload (Shopify sends it in the webhook)
        order_id = payload.get("order_id")
        if not order_id:
            print("[REFUND WEBHOOK] No order_id in payload")
            self.send_json_response(400, {"error": "no_order_id"})
            return

        refund_line_items = payload.get("refund_line_items", [])

        processed = []
        errors = []

        # Demo mode (no Supabase)
        if not sb_configured():
            demo_items = []
            for refund_item in refund_line_items:
                line_item = refund_item.get("line_item", {})
                properties = {
                    prop.get("name"): prop.get("value", "")
                    for prop in line_item.get("properties", [])
                }

                design_uuid = properties.get("_design_uuid") or properties.get("_unique_product_id")
                if not design_uuid:
                    continue

                price_demo = int(float(line_item.get("price", "0")) * 100)
                ptype_demo = properties.get("_product_type", "tshirt")
                qty_demo = int(refund_item.get("quantity", 1))

                # Calculate what was originally refunded
                financials_demo = calculate_creator_cut(price_demo, ptype_demo, qty_demo)
                refund_demo = financials_demo["creator_cut_paise"]

                demo_items.append({
                    "unique_product_id":  design_uuid,
                    "design_title":       properties.get("_design_title", ""),
                    "quantity":           qty_demo,
                    "price_rupees":       price_demo / 100,
                    "refund_amount_rupees": refund_demo / 100,
                })

            print(f"[DEMO] D2E refund {order_id} | items={demo_items}")
            self.send_json_response(200, {
                "status": "ok",
                "mode": "demo",
                "order_id": order_id,
                "note": "Supabase not configured — financial ledger not written",
                "demo_refunds": demo_items,
            })
            return

        # Process each refund line item
        for refund_item in refund_line_items:
            line_item = refund_item.get("line_item", {})
            try:
                # Extract line-item properties
                properties = {
                    prop.get("name"): prop.get("value", "")
                    for prop in line_item.get("properties", [])
                }

                # Extract design UUID
                design_uuid = (
                    properties.get("_design_uuid") or
                    properties.get("_unique_product_id") or
                    None
                )

                if not design_uuid:
                    # Not a Design-to-Earn item — skip silently
                    print(f"[SKIP] Refund item has no _design_uuid — not a D2E item")
                    continue

                price = int(float(line_item.get("price", "0")) * 100)  # rupees → paise
                product_type = properties.get("_product_type", "tshirt")
                color = properties.get("_color", "")
                quantity = int(refund_item.get("quantity", 1))
                design_title = properties.get("_design_title", "")
                creator_shopify_id = properties.get("_creator_id", "")

                if not creator_shopify_id:
                    print(f"[SKIP] Refund item has no _creator_id — skipping")
                    continue

                print(f"[D2E REFUND] uuid={design_uuid} color={color} qty={quantity} order={order_id}")

                # Calculate refund amount (the creator's cut that was originally paid)
                financials = calculate_creator_cut(price, product_type, quantity)
                refund_amount = financials["creator_cut_paise"]

                print(f"[FINANCE] refund=₹{refund_amount/100:.2f} qty={quantity}")

                # -------------------------------------------------------
                # STEP 1: Update design_orders table to mark as refunded
                # -------------------------------------------------------
                _, err = sb_patch(
                    'design_orders',
                    {
                        "status": "refunded",
                        "updated_at": datetime.utcnow().isoformat(),
                    },
                    'shopify_order_id',
                    order_id,
                    'unique_product_id',
                    design_uuid
                )
                if err:
                    print(f"[REFUND] Failed to update design_orders: {err}")

                # -------------------------------------------------------
                # STEP 2: Process the refund ledger
                # -------------------------------------------------------
                ledger_result = process_refund_ledger(
                    creator_shopify_id=creator_shopify_id,
                    design_unique_id=design_uuid,
                    order_id=order_id,
                    refund_amount_paise=refund_amount,
                    product_type=product_type,
                    color=color,
                    quantity=quantity,
                    price_paise=price,
                    design_title=design_title,
                )

                processed.append({
                    "order_id":           order_id,
                    "unique_product_id":  design_uuid,
                    "design_title":       design_title,
                    "creator_id":         creator_shopify_id,
                    "quantity":           quantity,
                    "refund_amount_paise": refund_amount,
                    "new_earnings_paise": ledger_result.get("new_earnings_paise"),
                    "new_tier":           ledger_result.get("new_tier", "unknown"),
                    "tier_downgraded":    ledger_result.get("tier_downgraded", False),
                })

            except Exception as e:
                errors.append({"error": str(e)})
                print(f"[REFUND ERROR] {str(e)}")

        self.send_json_response(200, {
            "status": "ok",
            "order_id": order_id,
            "processed": processed,
            "errors": errors if errors else None,
        })


if __name__ == "__main__":
    pass
