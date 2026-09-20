"""
Shopify Webhook Handler — Receives real-time product/order events from Shopify.
Handles: product/create, product/update, product/delete, orders/paid, etc.
"""
from __future__ import annotations
import os
import sys
import json
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.core.supabase import sb_request
from api.shopify.sync import handle_shopify_product_webhook


SHOPIFY_WEBHOOK_SECRET = os.environ.get("SHOPIFY_WEBHOOK_SECRET", "")


def _verify_shopify_webhook(data: bytes, hmac_header: str) -> bool:
    """Verify Shopify webhook HMAC signature."""
    if not SHOPIFY_WEBHOOK_SECRET:
        return True  # Skip verification if no secret configured
    computed = hmac.new(SHOPIFY_WEBHOOK_SECRET.encode(), data, hashlib.sha256).digest()
    import base64
    computed_b64 = base64.b64encode(computed).decode()
    return hmac.compare_digest(computed_b64, hmac_header)


class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        try:
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/")
            query = parse_qs(parsed.query)

            # Get brand_id from query param
            brand_id = query.get("brand_id", [""])[0]

            # Read body
            content_length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(content_length)

            # Verify webhook
            hmac_header = self.headers.get("X-Shopify-Hmac-SHA256", "")
            if not _verify_shopify_webhook(raw_body, hmac_header):
                self._respond(401, {"error": "invalid_hmac"})
                return

            # Parse body
            body = json.loads(raw_body) if content_length > 0 else {}

            # Determine topic
            topic = self.headers.get("X-Shopify-Topic", "")

            if path == "/api/shopify/product-webhook":
                if not brand_id:
                    self._respond(400, {"error": "brand_id required"})
                    return
                result = handle_shopify_product_webhook(brand_id, topic, body)
                self._respond(200, result)

            else:
                self._respond(404, {"error": "not_found"})

        except json.JSONDecodeError:
            self._respond(400, {"error": "invalid_json"})
        except Exception as e:
            self._respond(500, {"error": str(e)})

    def do_GET(self):
        """Health check for webhook endpoint."""
        self._respond(200, {"status": "ok", "endpoint": "shopify_webhook"})

    def _respond(self, status: int, data: dict):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args):
        pass
