"""
MyNarrative B2B Platform — API Gateway (Hardened)
Routes requests to appropriate handlers with full security.
"""
from http.server import BaseHTTPRequestHandler
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.security import (
    security_check, cors_headers, security_headers, sanitize_error,
    check_rate_limit, get_client_ip, sanitize_body, validate_api_key_format,
    is_bot_request, sign_request, verify_request_signature,
)
from api.core import validate_api_key, create_session_token
from api.core.supabase import sb_request
from api.widget.bootstrap import handle_bootstrap
from api.user.identify import handle_identify
from api.closet.upload import handle_closet_upload
from api.closet.items import handle_closet_items
from api.recommend.generate import handle_recommend
from api.subscription.status import handle_subscription_status
from api.health.check import handle_health

# Allowed CORS origins for B2B
ALLOWED_ORIGINS = [
    "https://mynarrative.store",
    "https://www.mynarrative.store",
    "https://widget.mynarrative.store",
]


class handler(BaseHTTPRequestHandler):

    def _cors_headers(self, origin: str = ""):
        is_allowed = origin in ALLOWED_ORIGINS
        self.send_header("Access-Control-Allow-Origin", origin if is_allowed else ALLOWED_ORIGINS[0])
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-API-Key, X-User-ID, X-Session-Token, X-Request-Signature, X-Timestamp")
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
        key = f"b2b:{tier}:{ip}"
        allowed, info = check_rate_limit(key, tier)
        if not allowed:
            self._respond(429, {"error": "rate_limit_exceeded", "retry_after": info.get("retry_after", 60)})
            return False
        return True

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors_headers(self.headers.get("Origin", ""))
        self._security_headers()
        self.end_headers()

    def do_GET(self):
        from urllib.parse import urlparse
        path = urlparse(self.path).path.rstrip("/")

        # Bot check
        ua = self.headers.get("User-Agent", "")
        if is_bot_request(ua):
            self._respond(403, {"error": "forbidden"})
            return

        if path == "/api/health":
            if not self._rate_limit_check("default"):
                return
            self._respond(200, handle_health())
        else:
            self._respond(404, {"error": "not_found"})

    def do_POST(self):
        try:
            from urllib.parse import urlparse
            path = urlparse(self.path).path.rstrip("/")

            # Bot check
            ua = self.headers.get("User-Agent", "")
            if is_bot_request(ua):
                self._respond(403, {"error": "forbidden"})
                return

            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 512000:
                self._respond(413, {"error": "payload_too_large"})
                return

            body = json.loads(self.rfile.read(content_length)) if content_length > 0 else {}

            # ── Public endpoints (no auth required) ────────────────────
            if path == "/api/widget/bootstrap":
                if not self._rate_limit_check("bootstrap"):
                    return
                body = sanitize_body(body, allowed_fields={
                    "api_key", "fingerprint", "user_id", "brand_domain",
                    "referrer", "version",
                })
                if not body.get("api_key"):
                    self._respond(400, {"error": "api_key required"})
                    return
                result = handle_bootstrap(body)
                status = 403 if result.get("error") == "subscription_expired" else 200
                self._respond(status, result)

            elif path == "/api/health":
                if not self._rate_limit_check("default"):
                    return
                self._respond(200, handle_health())

            # ── Authenticated endpoints ────────────────────────────────
            else:
                if not self._rate_limit_check("recommend"):
                    return

                api_key = self.headers.get("X-API-Key", "")
                session_token = self.headers.get("X-Session-Token", "")
                user_id = self.headers.get("X-User-ID", "")

                # Validate API key format first (fast, no DB hit)
                if not validate_api_key_format(api_key):
                    self._respond(401, {"error": "invalid_api_key_format"})
                    return

                # Validate API key against database
                brand_id = validate_api_key(api_key)
                if not brand_id:
                    self._respond(401, {"error": "invalid_api_key"})
                    return

                # Check subscription — auto-create trial if missing
                sub_status = handle_subscription_status(brand_id)
                if sub_status.get("status") not in ("active", "trialing"):
                    # Auto-create a 14-day trial subscription
                    from datetime import datetime, timedelta
                    now = datetime.utcnow()
                    trial_end = now + timedelta(days=14)
                    sb_request("POST", "/rest/v1/brand_subscriptions", {
                        "brand_id": brand_id,
                        "plan_tier": "starter",
                        "status": "trialing",
                        "trial_end": trial_end.isoformat() + "Z",
                        "current_period_start": now.isoformat() + "Z",
                        "current_period_end": trial_end.isoformat() + "Z",
                        "monthly_recommendations_limit": 1000,
                        "monthly_recommendations_used": 0,
                    })
                    sub_status["status"] = "trialing"

                # Sanitize body per-endpoint
                if path == "/api/widget/event":
                    body = sanitize_body(body, allowed_fields={
                        "session_token", "event_type", "event_data",
                    })
                    result = {"ok": True}
                    self._respond(200, result)

                elif path == "/api/user/identify":
                    body = sanitize_body(body, allowed_fields={
                        "fingerprint", "brand_id",
                    })
                    if not body.get("fingerprint"):
                        self._respond(400, {"error": "fingerprint required"})
                        return
                    body["brand_id"] = brand_id
                    result = handle_identify(body)
                    self._respond(200, result)

                elif path == "/api/closet/upload":
                    if not self._rate_limit_check("upload"):
                        return
                    body = sanitize_body(body, allowed_fields={
                        "image_url", "image_base64",
                    })
                    result = handle_closet_upload(body, user_id)
                    self._respond(200, result)

                elif path == "/api/closet/items":
                    result = handle_closet_items(user_id, self.headers.get("Query", ""))
                    self._respond(200, result)

                elif path == "/api/recommend":
                    if not self._rate_limit_check("recommend"):
                        return
                    body = sanitize_body(body, allowed_fields={
                        "user_id", "session_token", "occasion", "price_tier",
                        "include_closet", "outfit_count", "brand_id", "user_id",
                    })
                    body["brand_id"] = brand_id
                    body["user_id"] = user_id
                    result = handle_recommend(body)
                    self._respond(200, result)

                else:
                    self._respond(404, {"error": "not_found"})

        except json.JSONDecodeError:
            self._respond(400, {"error": "invalid_json"})
        except Exception as e:
            self._respond(500, {"error": sanitize_error(e)})

    def log_message(self, format, *args):
        pass
