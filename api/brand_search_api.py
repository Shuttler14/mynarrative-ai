"""
Brand Search API — Hardened with rate limiting, input validation, error sanitization.
"""
from http.server import BaseHTTPRequestHandler
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.security import (
    sanitize_error, check_rate_limit, get_client_ip, sanitize_body,
    security_headers, is_bot_request, validate_api_key_format,
)
from api.brand_catalog import search_brand_products, get_brand_catalog_summary
from api.garment_pipeline import process_product_for_vton, classify_garment
from api.currency_utils import detect_currency_from_headers, convert_price_rupees, format_price


ALLOWED_ORIGINS = [
    "https://mynarrative.store",
    "https://www.mynarrative.store",
    "https://widget.mynarrative.store",
]


class handler(BaseHTTPRequestHandler):

    def _cors_headers(self, origin: str = ""):
        is_allowed = origin in ALLOWED_ORIGINS
        self.send_header("Access-Control-Allow-Origin", origin if is_allowed else ALLOWED_ORIGINS[0])
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS, GET")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Country, X-Currency, X-API-Key")
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

    def _rate_limit_check(self, tier="brand_search"):
        ip = get_client_ip(self.headers)
        key = f"brand:{tier}:{ip}"
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
        # Bot check
        ua = self.headers.get("User-Agent", "")
        if is_bot_request(ua):
            self._respond(403, {"error": "forbidden"})
            return

        if not self._rate_limit_check():
            return

        brands = get_brand_catalog_summary()
        self._respond(200, {
            "service": "Brand Search API",
            "brands": brands,
            "endpoints": {
                "POST /api/brand/search": "Search products by brand, category, price, gender",
                "POST /api/brand/search-for-occasion": "Search brands by occasion + price tier",
                "GET /api/brand/catalogs": "List all brand catalogs",
            }
        })

    def do_POST(self):
        try:
            from urllib.parse import urlparse
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/")
            currency = detect_currency_from_headers(self.headers)

            # Bot check
            ua = self.headers.get("User-Agent", "")
            if is_bot_request(ua):
                self._respond(403, {"error": "forbidden"})
                return

            if not self._rate_limit_check():
                return

            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 512000:
                self._respond(413, {"error": "payload_too_large"})
                return

            body = json.loads(self.rfile.read(content_length)) if content_length > 0 else {}

            if path == "/api/brand/search":
                body = sanitize_body(body, allowed_fields={
                    "brand", "category", "gender", "min_price", "max_price",
                    "limit", "vibe", "color_pref", "process_vton",
                })
                result = self._handle_brand_search(body, currency)
                self._respond(200, result)

            elif path == "/api/brand/search-for-occasion":
                body = sanitize_body(body, allowed_fields={
                    "occasion", "price_range", "gender", "limit", "process_vton",
                })
                result = self._handle_occasion_search(body, currency)
                self._respond(200, result)

            else:
                self._respond(404, {"error": "not_found"})

        except json.JSONDecodeError:
            self._respond(400, {"error": "invalid_json"})
        except Exception as e:
            self._respond(500, {"error": sanitize_error(e)})

    def _handle_brand_search(self, body, currency):
        brand = sanitize_string(body.get("brand", ""), 100)
        category = sanitize_string(body.get("category", ""), 50)
        gender = sanitize_string(body.get("gender", ""), 20)
        min_price = max(0, float(body.get("min_price", 0)))
        max_price = min(999999, float(body.get("max_price", 999999)))
        limit = min(int(body.get("limit", 20)), 30)
        vibe = sanitize_string(body.get("vibe", ""), 50)
        color_pref = sanitize_string(body.get("color_pref", ""), 50)
        process_vton = bool(body.get("process_vton", False))

        products = search_brand_products(
            brand=brand, category=category, gender=gender,
            min_price=min_price, max_price=max_price,
            limit=limit, currency=currency,
            vibe=vibe, color_pref=color_pref,
        )

        if process_vton and products:
            for p in products[:3]:
                try:
                    vton_result = process_product_for_vton(
                        image_url=p.get("image_url", ""),
                        title=p.get("title", ""),
                        category=p.get("category", ""),
                        existing_flat_lay=p.get("flat_lay_url", ""),
                    )
                    p["vton_ready_url"] = vton_result.get("vton_ready_url", p.get("image_url"))
                    p["vton_category"] = vton_result.get("category", "upper_body")
                    p["processing_status"] = vton_result.get("processing_status", "none")
                except Exception:
                    p["processing_status"] = "error"

        return {"success": True, "products": products, "count": len(products), "currency": currency}

    def _handle_occasion_search(self, body, currency):
        from api.fashion_services import BRAND_SUGGESTIONS

        occasion = sanitize_string(body.get("occasion", ""), 50)
        price_range = sanitize_string(body.get("price_range", "premium"), 20)
        gender = sanitize_string(body.get("gender", ""), 20)
        limit = min(int(body.get("limit", 6)), 20)
        process_vton = bool(body.get("process_vton", False))

        brands_for_occasion = BRAND_SUGGESTIONS.get(occasion, {}).get(price_range, [])

        all_products = []
        for brand_name in brands_for_occasion[:5]:
            prods = search_brand_products(
                brand=brand_name, gender=gender,
                limit=limit, currency=currency,
            )
            all_products.extend(prods)

        if process_vton and all_products:
            for p in all_products[:6]:
                try:
                    vton_result = process_product_for_vton(
                        image_url=p.get("image_url", ""),
                        title=p.get("title", ""),
                        category=p.get("category", ""),
                        existing_flat_lay=p.get("flat_lay_url", ""),
                    )
                    p["vton_ready_url"] = vton_result.get("vton_ready_url", p.get("image_url"))
                    p["vton_category"] = vton_result.get("category", "upper_body")
                    p["processing_status"] = vton_result.get("processing_status", "none")
                except Exception:
                    p["processing_status"] = "error"

        return {
            "success": True,
            "products": all_products,
            "brands": brands_for_occasion,
            "count": len(all_products),
            "currency": currency,
        }

    def log_message(self, format, *args):
        pass


def sanitize_string(value, max_length=500):
    """Local sanitize helper."""
    import re
    if not isinstance(value, str):
        return ""
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', value)
    return cleaned.strip()[:max_length]
