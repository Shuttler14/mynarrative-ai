"""Syndicate API Gateway — Hardened with rate limiting, input validation, error sanitization."""
from http.server import BaseHTTPRequestHandler
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.security import (
    security_check, sanitize_error, check_rate_limit, get_client_ip,
    sanitize_body, security_headers, is_bot_request,
    verify_request_signature, validate_api_key_format,
)
from api.core import validate_api_key
from api.syndicate import (
    get_syndicate_rules, update_syndicate_rules,
    request_pairing, approve_pairing, reject_pairing, get_brand_partners,
    find_partner_products, create_cart_handoff,
    record_affiliate_transaction, get_syndicate_metrics,
)

ALLOWED_ORIGINS = [
    "https://mynarrative.store",
    "https://www.mynarrative.store",
]


class handler(BaseHTTPRequestHandler):

    def _cors_headers(self, origin: str = ""):
        is_allowed = origin in ALLOWED_ORIGINS
        self.send_header("Access-Control-Allow-Origin", origin if is_allowed else ALLOWED_ORIGINS[0])
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-API-Key, X-User-ID, X-Request-Signature, X-Timestamp")
        self.send_header("Access-Control-Max-Age", "86400")

    def _security_headers(self):
        for key, val in security_headers().items():
            self.send_header(key, val)

    def _respond(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self._cors_headers(self.headers.get("Origin", ""))
        self._security_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode("utf-8"))

    def _rate_limit_check(self, tier="default"):
        ip = get_client_ip(self.headers)
        key = f"syndicate:{tier}:{ip}"
        allowed, info = check_rate_limit(key, tier)
        if not allowed:
            self._respond(429, {"error": "rate_limit_exceeded", "retry_after": info.get("retry_after", 60)})
            return False
        return True

    def _auth_check(self):
        ua = self.headers.get("User-Agent", "")
        if is_bot_request(ua):
            self._respond(403, {"error": "forbidden"})
            return None

        api_key = self.headers.get("X-API-Key", "")
        if not validate_api_key_format(api_key):
            self._respond(401, {"error": "invalid_api_key_format"})
            return None

        brand_id = validate_api_key(api_key)
        if not brand_id:
            self._respond(401, {"error": "invalid_api_key"})
            return None

        return brand_id

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors_headers(self.headers.get("Origin", ""))
        self._security_headers()
        self.end_headers()

    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        params = parse_qs(parsed.query)

        if not self._rate_limit_check():
            return

        brand_id = self._auth_check()
        if not brand_id:
            return

        if path == "/api/syndicate/rules":
            result = get_syndicate_rules(brand_id)
            self._respond(200, result)

        elif path == "/api/syndicate/partners":
            result = get_brand_partners(brand_id)
            self._respond(200, result)

        elif path == "/api/syndicate/metrics":
            period = min(int(params.get("period", ["30"])[0]), 365)
            result = get_syndicate_metrics(brand_id, period)
            self._respond(200, result)

        elif path == "/api/syndicate/find-partners":
            category = params.get("category", [""])[0][:100]
            result = find_partner_products(brand_id, category=category)
            self._respond(200, {"products": result, "count": len(result)})

        else:
            self._respond(404, {"error": "not_found"})

    def do_POST(self):
        try:
            from urllib.parse import urlparse
            path = urlparse(self.path).path.rstrip("/")

            if not self._rate_limit_check():
                return

            brand_id = self._auth_check()
            if not brand_id:
                return

            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 512000:
                self._respond(413, {"error": "payload_too_large"})
                return

            body = json.loads(self.rfile.read(content_length)) if content_length > 0 else {}
            user_id = self.headers.get("X-User-ID", "")

            if path == "/api/syndicate/rules":
                body = sanitize_body(body, allowed_fields={
                    "allowed_categories", "blocked_categories",
                    "min_partner_price", "max_partner_price",
                    "allowed_tiers", "approved_partner_brand_ids",
                    "blocked_partner_brand_ids",
                    "affiliate_commission_rate", "cpa_rate", "is_active",
                })
                result = update_syndicate_rules(brand_id, body)
                self._respond(200, result)

            elif path == "/api/syndicate/request-pairing":
                body = sanitize_body(body, allowed_fields={"guest_brand_id"})
                guest_brand_id = body.get("guest_brand_id", "")
                if not guest_brand_id:
                    self._respond(400, {"error": "guest_brand_id required"})
                    return
                result = request_pairing(brand_id, guest_brand_id)
                self._respond(200, result)

            elif path == "/api/syndicate/approve-pairing":
                body = sanitize_body(body, allowed_fields={"guest_brand_id"})
                guest_brand_id = body.get("guest_brand_id", "")
                result = approve_pairing(brand_id, guest_brand_id)
                self._respond(200, result)

            elif path == "/api/syndicate/reject-pairing":
                body = sanitize_body(body, allowed_fields={"guest_brand_id"})
                guest_brand_id = body.get("guest_brand_id", "")
                result = reject_pairing(brand_id, guest_brand_id)
                self._respond(200, result)

            elif path == "/api/syndicate/cart-handoff":
                body = sanitize_body(body, allowed_fields={
                    "guest_brand_id", "product", "session_id",
                })
                guest_brand_id = body.get("guest_brand_id", "")
                product = body.get("product", {})
                session_id = body.get("session_id", "")[:100]
                result = create_cart_handoff(brand_id, guest_brand_id, user_id, product, session_id)
                self._respond(200, result)

            elif path == "/api/syndicate/record-transaction":
                body = sanitize_body(body, allowed_fields={
                    "guest_brand_id", "order_data",
                })
                guest_brand_id = body.get("guest_brand_id", "")
                order_data = body.get("order_data", {})
                order_data["user_id"] = user_id
                result = record_affiliate_transaction(brand_id, guest_brand_id, order_data)
                self._respond(200, result)

            elif path == "/api/syndicate/find-partners":
                body = sanitize_body(body, allowed_fields={
                    "category", "occasion", "price_tier", "limit",
                })
                category = body.get("category", "")[:100]
                occasion = body.get("occasion", "")[:50]
                price_tier = body.get("price_tier", "mid")[:20]
                limit = min(int(body.get("limit", 6)), 20)
                result = find_partner_products(brand_id, category=category, occasion=occasion, price_tier=price_tier, limit=limit)
                self._respond(200, {"products": result, "count": len(result)})

            else:
                self._respond(404, {"error": "not_found"})

        except json.JSONDecodeError:
            self._respond(400, {"error": "invalid_json"})
        except Exception as e:
            self._respond(500, {"error": sanitize_error(e)})

    def log_message(self, format, *args):
        pass
