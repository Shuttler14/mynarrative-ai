"""
creator_tokens.py — Narrative Token Grant API
===============================================
Called after a successful Razorpay payment to credit tokens to a creator.

SECURITY:
  - Verifies Razorpay payment_id is genuine via Razorpay Fetch Payment API
  - Checks payment amount matches the bundle purchased (prevents spoofing)
  - Idempotent: stores payment_id in credit_ledger; duplicate calls are detected
  - Uses urllib (no httpx/httpcore — avoids [Errno 16] on Vercel)

Endpoints:
  POST /api/creator/tokens/grant   — grant tokens after Razorpay payment
  GET  /api/creator/tokens/balance?creator_id=<id> — get current token balance
  GET  /api/creator/tokens/health  — health check
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.request
import urllib.parse
import urllib.error
import base64
from datetime import datetime

# ─────────────────────────────────────────────────────────────
# TOKEN BUNDLE DEFINITIONS (must match frontend pricing)
# amount_paise: Razorpay amount in paise (₹1 = 100 paise)
# ─────────────────────────────────────────────────────────────
TOKEN_BUNDLES = {
    "Starter Pack":  {"tokens": 10, "amount_paise": 9900},
    "Creator Pack":  {"tokens": 25, "amount_paise": 19900},
    "Pro Pack":      {"tokens": 50, "amount_paise": 34900},
}

# Allow ±5% tolerance for amount verification
AMOUNT_TOLERANCE = 0.05


def _sb_headers():
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
    url, key, _ = _sb_headers()
    return bool(url and key)

def sb_get(table, select='*', filters=None, limit=None):
    url, key, headers = _sb_headers()
    if not url or not key:
        return [], 'not_configured'
    params = {'select': select}
    if filters: params.update(filters)
    if limit:   params['limit'] = str(limit)
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

def sb_patch(table, data, filter_col, filter_val):
    url, key, headers = _sb_headers()
    if not url or not key:
        return None, 'not_configured'
    params   = {filter_col: f'eq.{filter_val}'}
    full_url = f"{url.rstrip('/')}/rest/v1/{table}?{urllib.parse.urlencode(params)}"
    body     = json.dumps(data).encode()
    req      = urllib.request.Request(full_url, data=body, headers=headers, method='PATCH')
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode()), None
    except urllib.error.HTTPError as e:
        return None, f'HTTP {e.code}: {e.read().decode()[:100]}'
    except Exception as e:
        return None, str(e)

def sb_post(table, data):
    url, key, headers = _sb_headers()
    if not url or not key:
        return None, 'not_configured'
    full_url = f"{url.rstrip('/')}/rest/v1/{table}"
    body     = json.dumps(data).encode()
    req      = urllib.request.Request(full_url, data=body, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            resp = json.loads(r.read().decode())
            return (resp[0] if isinstance(resp, list) and resp else resp), None
    except urllib.error.HTTPError as e:
        return None, f'HTTP {e.code}: {e.read().decode()[:100]}'
    except Exception as e:
        return None, str(e)

def sb_rpc(function_name, params):
    url, key, headers = _sb_headers()
    if not url or not key:
        return None, 'not_configured'
    full_url = f"{url.rstrip('/')}/rest/v1/rpc/{function_name}"
    body     = json.dumps(params).encode()
    req      = urllib.request.Request(full_url, data=body, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode()), None
    except urllib.error.HTTPError as e:
        body_err = e.read().decode()
        try: body_err = json.loads(body_err)
        except: pass
        return None, f'HTTP {e.code}: {str(body_err)[:150]}'
    except Exception as e:
        return None, str(e)


def verify_razorpay_payment(payment_id, expected_amount_paise):
    """
    Verify a Razorpay payment is genuine by fetching it from the Razorpay API.
    Returns (is_valid: bool, payment_data: dict, error: str or None)

    Checks:
      1. Payment exists in Razorpay
      2. Payment status == 'captured'
      3. Amount matches expected (within tolerance)
    """
    rzp_key_id     = os.environ.get('RAZORPAY_KEY_ID', '')
    rzp_key_secret = os.environ.get('RAZORPAY_KEY_SECRET', '')

    if not rzp_key_id or not rzp_key_secret:
        # Demo mode — skip verification
        print(f"[TOKENS] Razorpay credentials not set — skipping payment verification (demo mode)")
        return True, {"id": payment_id, "status": "captured", "amount": expected_amount_paise}, None

    # Basic auth: base64(key_id:key_secret)
    credentials = base64.b64encode(f"{rzp_key_id}:{rzp_key_secret}".encode()).decode()

    url = f"https://api.razorpay.com/v1/payments/{payment_id}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Basic {credentials}")
    req.add_header("Accept", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            payment = json.loads(r.read().decode())

        # Check status
        if payment.get("status") != "captured":
            return False, payment, f"Payment status is '{payment.get('status')}', expected 'captured'"

        # Check amount (with tolerance)
        actual_amount = int(payment.get("amount", 0))
        tolerance_min = int(expected_amount_paise * (1 - AMOUNT_TOLERANCE))
        tolerance_max = int(expected_amount_paise * (1 + AMOUNT_TOLERANCE))

        if not (tolerance_min <= actual_amount <= tolerance_max):
            return False, payment, (
                f"Amount mismatch: expected ₹{expected_amount_paise/100:.0f} "
                f"(±{AMOUNT_TOLERANCE*100:.0f}%), got ₹{actual_amount/100:.0f}"
            )

        return True, payment, None

    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return False, {}, f"Razorpay API error {e.code}: {body[:100]}"
    except Exception as e:
        return False, {}, str(e)


def check_payment_already_processed(payment_id):
    """
    Idempotency check: has this payment_id already been used to grant tokens?
    Returns True if already processed.
    """
    rows, err = sb_get("credit_ledger",
        select="id,order_id,event_type",
        filters={"order_id": f"eq.{payment_id}", "event_type": "eq.razorpay_topup"}
    )
    return bool(rows and not err)


def grant_tokens_to_creator(creator_shopify_id, tokens, payment_id, amount_paise, bundle_label):
    """
    Credit tokens to a creator after verified Razorpay payment.
    Uses replenish_ai_credits SQL function for atomic update + ledger write.
    """
    note = f"Razorpay top-up: {bundle_label} ({tokens} tokens) — Payment {payment_id}"

    # Try RPC first (atomic)
    result, err = sb_rpc("replenish_ai_credits", {
        "p_creator_shopify_id": creator_shopify_id,
        "p_credits_to_add":     tokens,
        "p_order_id":           payment_id,
        "p_event_type":         "razorpay_topup",
        "p_note":               note,
    })

    if err:
        print(f"[TOKENS] RPC failed: {err}, falling back to direct update")
        # Fallback: direct REST update
        rows, _ = sb_get("creators", "id,ai_credits",
                         filters={"shopify_customer_id": f"eq.{creator_shopify_id}"}, limit=1)
        if not rows:
            return None, "creator_not_found"

        creator    = rows[0]
        old_balance = int(creator.get("ai_credits") or 0)
        new_balance = old_balance + tokens

        _, patch_err = sb_patch("creators", {
            "ai_credits":           new_balance,
            "total_credits_earned": None,  # will not update this in fallback
        }, "id", creator["id"])

        if patch_err:
            return None, f"Failed to update creator: {patch_err}"

        # Write ledger entry
        sb_post("credit_ledger", {
            "creator_id":  creator["id"],
            "event_type":  "razorpay_topup",
            "credits_delta": tokens,
            "balance_after": new_balance,
            "order_id":    payment_id,
            "note":        note,
            "created_at":  datetime.utcnow().isoformat(),
        })

        return {"old_balance": old_balance, "new_balance": new_balance, "credits_added": tokens}, None

    # Parse RPC result
    if isinstance(result, list) and result:
        row = result[0]
    elif isinstance(result, dict):
        row = result
    else:
        return None, "rpc_empty_result_creator_not_found"

    print(f"[TOKENS] Granted {tokens} tokens to {creator_shopify_id}: "
          f"{row.get('old_balance')} → {row.get('new_balance')}")
    return row, None


class handler(BaseHTTPRequestHandler):

    def send_json(self, status, data):
        body = json.dumps(data, default=str).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        path   = parsed.path

        if '/health' in path:
            return self.send_json(200, {
                "status":  "ok",
                "message": "Narrative Token Grant API v1.0",
                "bundles": TOKEN_BUNDLES,
                "razorpay_configured": bool(os.environ.get('RAZORPAY_KEY_ID')),
                "supabase_configured": sb_configured(),
                "endpoints": [
                    "POST /api/creator/tokens/grant",
                    "GET  /api/creator/tokens/balance?creator_id=<id>",
                    "GET  /api/creator/tokens/health",
                ]
            })

        if '/balance' in path:
            creator_id = params.get('creator_id', [''])[0].strip()
            if not creator_id:
                return self.send_json(400, {"error": "creator_id required"})

            rows, err = sb_get("creators",
                "ai_credits,total_credits_earned,total_credits_used",
                filters={"shopify_customer_id": f"eq.{creator_id}"},
                limit=1
            )
            if err or not rows:
                return self.send_json(200, {
                    "creator_id": creator_id,
                    "ai_credits": 3,
                    "demo_mode": not sb_configured(),
                })

            c = rows[0]
            return self.send_json(200, {
                "creator_id":          creator_id,
                "ai_credits":          int(c.get("ai_credits") or 0),
                "total_credits_earned": int(c.get("total_credits_earned") or 0),
                "total_credits_used":  int(c.get("total_credits_used") or 0),
            })

        self.send_json(404, {"error": "Not found"})

    def do_POST(self):
        from urllib.parse import urlparse
        parsed = urlparse(self.path)
        path   = parsed.path

        content_length = int(self.headers.get('Content-Length', 0))
        try:
            body = json.loads(self.rfile.read(content_length).decode('utf-8'))
        except Exception:
            return self.send_json(400, {"error": "Invalid JSON body"})

        if '/grant' in path:
            return self._handle_grant(body)

        self.send_json(404, {"error": "Not found"})

    def _handle_grant(self, body):
        """
        Grant Narrative Tokens after verified Razorpay payment.

        Required fields:
          creator_id    — Shopify customer ID
          payment_id    — Razorpay payment ID (e.g. pay_XXXXXXXX)
          tokens        — Number of tokens to grant
          amount_paise  — Amount paid in paise (for verification)
          bundle_label  — Bundle name (e.g. "Creator Pack")
          source        — Should be "razorpay_topup"
        """
        creator_id   = str(body.get('creator_id', '')).strip()
        payment_id   = str(body.get('payment_id', '')).strip()
        tokens       = body.get('tokens')
        amount_paise = body.get('amount_paise')
        bundle_label = str(body.get('bundle_label', 'Token Bundle')).strip()

        # ── Validate input ────────────────────────────────────
        if not creator_id:
            return self.send_json(400, {"error": "creator_id is required"})
        if not payment_id:
            return self.send_json(400, {"error": "payment_id is required"})
        try:
            tokens       = int(tokens)
            amount_paise = int(amount_paise)
        except (TypeError, ValueError):
            return self.send_json(400, {"error": "tokens and amount_paise must be integers"})

        if tokens <= 0 or tokens > 100:
            return self.send_json(400, {"error": "tokens must be between 1 and 100"})

        # ── Validate bundle amount ───────────────────────────
        bundle = TOKEN_BUNDLES.get(bundle_label)
        if bundle and abs(bundle["amount_paise"] - amount_paise) > bundle["amount_paise"] * AMOUNT_TOLERANCE:
            return self.send_json(400, {
                "error": f"Amount mismatch for {bundle_label}. Expected ₹{bundle['amount_paise']//100}, got ₹{amount_paise//100}"
            })

        # ── Idempotency check ───────────────────────────────
        if sb_configured() and check_payment_already_processed(payment_id):
            return self.send_json(409, {
                "error": "This payment has already been processed",
                "payment_id": payment_id,
            })

        # ── Verify payment with Razorpay ────────────────────
        is_valid, payment_data, verify_err = verify_razorpay_payment(payment_id, amount_paise)
        if not is_valid:
            print(f"[TOKENS] Payment verification failed: {verify_err}")
            return self.send_json(402, {
                "error": "Payment verification failed",
                "details": verify_err,
                "payment_id": payment_id,
            })

        print(f"[TOKENS] Payment verified: {payment_id} ₹{amount_paise/100:.0f} → granting {tokens} tokens to {creator_id}")

        # ── Grant tokens ────────────────────────────────────
        if not sb_configured():
            # Demo mode
            return self.send_json(200, {
                "success":     True,
                "demo_mode":   True,
                "creator_id":  creator_id,
                "tokens_added": tokens,
                "new_balance": tokens + 3,  # assume default 3
                "payment_id":  payment_id,
                "message":     f"{tokens} Narrative Tokens granted (demo mode — Supabase not configured)"
            })

        result, grant_err = grant_tokens_to_creator(
            creator_id, tokens, payment_id, amount_paise, bundle_label
        )

        if grant_err:
            print(f"[TOKENS ERROR] Grant failed for {creator_id}: {grant_err}")
            return self.send_json(500, {
                "error":      "Token grant failed — payment was successful",
                "details":    grant_err,
                "payment_id": payment_id,
                "action":     "Contact support@mynarrative.store with your payment ID for manual credit",
            })

        new_balance = int(result.get("new_balance", tokens))
        return self.send_json(200, {
            "success":      True,
            "creator_id":   creator_id,
            "tokens_added": tokens,
            "new_balance":  new_balance,
            "old_balance":  int(result.get("old_balance", 0)),
            "payment_id":   payment_id,
            "bundle":       bundle_label,
            "message":      f"{tokens} Narrative Tokens credited. Your new balance: {new_balance} tokens.",
        })
