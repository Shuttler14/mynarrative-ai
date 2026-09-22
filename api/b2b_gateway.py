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

# Auth/Profile helpers (inline to avoid proxy issues)
import hashlib, time as _time, secrets as _secrets
_AUTH_OTP_STORE = {}
_AUTH_OTP_TTL = 300
from api.core import validate_api_key, create_session_token
from api.core.supabase import sb_request
from api.widget.bootstrap import handle_bootstrap
from api.user.identify import handle_identify
from api.closet.upload import handle_closet_upload
from api.closet.items import handle_closet_items
from api.recommend.generate import handle_recommend
from api.subscription.status import handle_subscription_status
from api.health.check import handle_health
from api.sponsored.campaigns import (
    handle_create_campaign, handle_list_campaigns, handle_campaign_performance,
    handle_update_campaign, handle_pause_campaign, handle_resume_campaign,
    handle_delete_campaign, handle_pricing_tiers,
)
from api.analytics import (
    track_network_event, get_brand_network_report, get_product_performance,
)
from api.recommend.eligibility import EligibilityEngine
from api.recommend.network_compatibility import NetworkCompatibilityScorer
from api.dashboard import (
    handle_dashboard_overview, handle_dashboard_products,
    handle_dashboard_network_settings, handle_dashboard_analytics,
    handle_dashboard_wallet, handle_network_partners,
)
from api.shopify.sync import start_shopify_sync, register_shopify_webhooks
from api.checkout_api import (
    get_cart, get_addresses, get_orders, get_order_detail
)
from api.recommend.outfits import handle_recommend
from api.sponsored.campaigns import handle_list_campaigns, handle_create_campaign
from api.sponsored.pricing import handle_pricing_tiers
from api.analytics import handle_network_event, handle_pricing_ping
from api.attribution import (
    handle_product_registration, handle_click_record,
    handle_merchant_pixel_event, run_reconciliation,
    handle_commission_summary, handle_attribution_report,
)
from api.brand.register import handle_brand_register
from api.brand_catalog import handle_catalog_sync
from api.brand_search_api import handle_brand_search
from api.subscription.status import handle_subscription_status
from api.subscription.payment_providers import handle_provider_pay, handle_provider_webhook
from api.widget.bootstrap import handle_bootstrap
from api.core import validate_api_key, validate_api_key_format, sb_request
from api.closet.items import handle_closet_list, handle_closet_add
from api.closet.upload import handle_closet_upload
from api.user.identify import handle_identify
    get_cart, add_to_cart, update_cart_item, remove_from_cart, clear_cart,
    create_order, verify_payment, save_address, get_addresses, get_orders, get_order_detail,
    handle_razorpay_webhook, update_order_status, handle_shopify_webhook,
)
from api.tracking import (
    handle_click_record, handle_tracking_redirect, handle_merchant_pixel_event,
    handle_shopify_app_proxy, handle_product_registration,
)
from api.attribution import (
    get_commission_summary, run_reconciliation,
    batch_advance_pending_commissions, batch_advance_confirmed_to_payable,
)

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

    # ── Auth Helpers (inline) ──────────────────────────────────────────
    def _auth_generate_otp(self):
        return f"{_secrets.randbelow(900000) + 100000}"

    def _auth_create_token(self, user_id, email):
        payload = f"{user_id}:{email}:{int(_time.time())}"
        sig = hashlib.sha256(f"{payload}:mn_secret".encode()).hexdigest()[:16]
        return f"{payload}:{sig}"

    def _auth_verify_token(self, token):
        try:
            parts = token.split(":")
            if len(parts) != 4:
                return None
            user_id, email, ts, sig = parts
            expected = hashlib.sha256(f"{user_id}:{email}:{ts}:mn_secret".encode()).hexdigest()[:16]
            if sig != expected:
                return None
            if int(_time.time()) - int(ts) > 86400 * 30:
                return None
            return user_id
        except Exception:
            return None

    def _auth_send_otp(self, body):
        email = (body.get("email") or "").strip().lower()
        if not email or "@" not in email:
            self._respond(400, {"error": "Valid email required"})
            return
        otp = self._auth_generate_otp()
        _AUTH_OTP_STORE[email] = {"otp": otp, "ts": _time.time(), "attempts": 0}
        # In prod, send via Resend/SendGrid. For now, log it.
        print(f"[AUTH] OTP for {email}: {otp}")
        try:
            users = sb_request("GET", f"/rest/v1/mn_user_profiles?email=eq.{email}&select=user_id")
            is_new = len(users) == 0
        except Exception:
            is_new = True
        self._respond(200, {"ok": True, "is_new_user": is_new})

    def _auth_verify_otp(self, body):
        email = (body.get("email") or "").strip().lower()
        otp = (body.get("otp") or "").strip()
        if not email or not otp:
            self._respond(400, {"error": "Email and OTP required"})
            return
        stored = _AUTH_OTP_STORE.get(email)
        if not stored:
            self._respond(400, {"error": "No code requested. Send a new one."})
            return
        if _time.time() - stored["ts"] > _AUTH_OTP_TTL:
            del _AUTH_OTP_STORE[email]
            self._respond(400, {"error": "Code expired. Send a new one."})
            return
        if stored["attempts"] >= 5:
            del _AUTH_OTP_STORE[email]
            self._respond(400, {"error": "Too many attempts. Send a new code."})
            return
        stored["attempts"] += 1
        if stored["otp"] != otp:
            self._respond(400, {"error": f"Wrong code. {5 - stored['attempts']} attempts left."})
            return
        del _AUTH_OTP_STORE[email]
        user_id = f"mn_{hashlib.sha256(email.encode()).hexdigest()[:16]}"
        try:
            users = sb_request("GET", f"/rest/v1/mn_user_profiles?email=eq.{email}&select=user_id")
            if users:
                user_id = users[0]["user_id"]
                is_new = False
            else:
                sb_request("POST", "/rest/v1/mn_user_profiles", {"user_id": user_id, "email": email})
                is_new = True
        except Exception:
            is_new = True
        token = self._auth_create_token(user_id, email)
        self._respond(200, {"ok": True, "token": token, "user_id": user_id, "email": email, "is_new_user": is_new})

    def _auth_complete_profile(self, body):
        email = (body.get("email") or "").strip().lower()
        name = (body.get("name") or "").strip()
        gender = (body.get("gender") or "").strip()
        if not email:
            self._respond(400, {"error": "Email required"})
            return
        user_id = f"mn_{hashlib.sha256(email.encode()).hexdigest()[:16]}"
        updates = {}
        if name:
            updates["display_name"] = name
        if gender:
            updates["gender"] = gender
        if updates:
            try:
                sb_request("PATCH", f"/rest/v1/mn_user_profiles?user_id=eq.{user_id}", updates)
            except Exception:
                try:
                    sb_request("POST", "/rest/v1/mn_user_profiles", {"user_id": user_id, "email": email, **updates})
                except Exception:
                    pass
        token = self._auth_create_token(user_id, email)
        self._respond(200, {"ok": True, "token": token, "user_id": user_id, "email": email, "display_name": name, "gender": gender})

    # ── User Profile Handlers ──────────────────────────────────────────
    def _handle_user_profile(self, uid):
        try:
            users = sb_request("GET", f"/rest/v1/mn_user_profiles?user_id=eq.{uid}&select=*")
            profile = users[0] if users else None
        except Exception:
            profile = None
        if not profile:
            self._respond(200, {"user_id": uid, "exists": False})
            return
        for table, key in [("mn_person_profiles","person_count"),("mn_saved_cards","card_count"),
                           ("mn_saved_outfits","outfit_count"),("mn_tryon_sessions","tryon_count")]:
            try:
                rows = sb_request("GET", f"/rest/v1/{table}?user_id=eq.{uid}&select=user_id")
                profile[key] = len(rows)
            except Exception:
                profile[key] = 0
        self._respond(200, profile)

    def _handle_user_cards(self, uid):
        try:
            cards = sb_request("GET", f"/rest/v1/mn_saved_cards?user_id=eq.{uid}&select=*&order=is_primary.desc,created_at.desc")
        except Exception:
            cards = []
        for c in cards:
            try:
                offers = sb_request("GET", f"/rest/v1/mn_merchant_offers?bank_name=eq.{c['bank_name']}&is_active=eq.true&select=offer_id")
                c["active_offers"] = len(offers)
            except Exception:
                c["active_offers"] = 0
        self._respond(200, cards)

    def _handle_user_persons(self, uid):
        try:
            persons = sb_request("GET", f"/rest/v1/mn_person_profiles?user_id=eq.{uid}&select=*&order=is_self.desc,created_at.desc")
        except Exception:
            persons = []
        self._respond(200, persons)

    def _handle_user_outfits(self, uid):
        try:
            outfits = sb_request("GET", f"/rest/v1/mn_saved_outfits?user_id=eq.{uid}&select=*&order=created_at.desc&limit=50")
        except Exception:
            outfits = []
        self._respond(200, outfits)

    def _handle_user_stats(self, uid):
        stats = {}
        for table, key in [("mn_person_profiles","persons"),("mn_saved_cards","cards"),
                           ("mn_saved_outfits","outfits"),("mn_tryon_sessions","tryons")]:
            try:
                rows = sb_request("GET", f"/rest/v1/{table}?user_id=eq.{uid}&select=user_id")
                stats[key] = len(rows)
            except Exception:
                stats[key] = 0
        self._respond(200, stats)

    def _update_user_profile(self, uid, body):
        allowed = {"display_name","gender","age_range","height_cm","body_type",
                    "preferred_styles","preferred_colors","avoid_colors","preferred_patterns","fit_preference"}
        updates = {k: v for k, v in body.items() if k in allowed and v is not None}
        if not updates:
            self._respond(400, {"error": "No valid fields to update"})
            return
        try:
            sb_request("PATCH", f"/rest/v1/mn_user_profiles?user_id=eq.{uid}", updates)
            self._respond(200, {"ok": True})
        except Exception as e:
            self._respond(500, {"error": str(e)})

    def _add_user_card(self, uid, body):
        required = {"bank_name", "card_type", "card_variant"}
        if not all(k in body for k in required):
            self._respond(400, {"error": "bank_name, card_type, card_variant required"})
            return
        card_id = f"card_{int(_time.time())}_{hashlib.sha256(f'{uid}{body[\"card_variant\"]}'.encode()).hexdigest()[:8]}"
        card = {"card_id": card_id, "user_id": uid, "bank_name": body["bank_name"],
                "card_type": body["card_type"], "card_variant": body["card_variant"],
                "card_network": body.get("card_network"), "is_primary": body.get("is_primary", False)}
        try:
            result = sb_request("POST", "/rest/v1/mn_saved_cards", card)
            self._respond(201, result[0] if result else card)
        except Exception as e:
            self._respond(500, {"error": str(e)})

    def _add_user_person(self, uid, body):
        person_id = f"person_{int(_time.time())}_{hashlib.sha256(f'{uid}{body.get(\"label\",\"\")}'.encode()).hexdigest()[:8]}"
        person = {"person_id": person_id, "user_id": uid,
                  "relationship": body.get("relationship", "self"),
                  "label": body.get("label", "Me"),
                  "is_self": body.get("is_self", body.get("relationship", "self") == "self"),
                  "preferred_styles": body.get("preferred_styles", []),
                  "preferred_colors": body.get("preferred_colors", []),
                  "fit_preference": body.get("fit_preference"),
                  "height_cm": body.get("height_cm"),
                  "body_type": body.get("body_type")}
        try:
            result = sb_request("POST", "/rest/v1/mn_person_profiles", person)
            self._respond(201, result[0] if result else person)
        except Exception as e:
            self._respond(500, {"error": str(e)})

    def _save_user_outfit(self, uid, body):
        outfit_id = f"outfit_{int(_time.time())}_{hashlib.sha256(json.dumps(body.get('items',[])).encode()).hexdigest()[:8]}"
        outfit = {"outfit_id": outfit_id, "user_id": uid, "person_id": body.get("person_id"),
                  "outfit_name": body.get("outfit_name"), "occasion": body.get("occasion"),
                  "items": body.get("items", []), "total_price": body.get("total_price"),
                  "best_price": body.get("best_price"), "best_offer": body.get("best_offer"),
                  "vton_image_url": body.get("vton_image_url"), "card_id": body.get("card_id")}
        try:
            result = sb_request("POST", "/rest/v1/mn_saved_outfits", outfit)
            self._respond(201, result[0] if result else outfit)
        except Exception as e:
            self._respond(500, {"error": str(e)})

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors_headers(self.headers.get("Origin", ""))
        self._security_headers()
        self.end_headers()

    def _proxy_to_handler(self, handler_cls, method):
        """Legacy proxy - unused"""
        pass

    def do_GET(self):
        try:
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/")
            query = parse_qs(parsed.query)

            ua = self.headers.get("User-Agent", "")
            if is_bot_request(ua):
                self._respond(403, {"error": "forbidden"})
                return

            # ── Public GET endpoints (no auth) ────────────────────────
            if path == "/api/health":
                if not self._rate_limit_check("default"):
                    return
                self._respond(200, handle_health())

            elif path.startswith("/api/track/c/"):
                # Tracking redirect: go.mynarrative.store/c/{click_id}
                if not self._rate_limit_check("default"):
                    return
                click_id = path.split("/")[-1]
                result = handle_tracking_redirect(click_id)
                if result.get("redirect"):
                    self.send_response(302)
                    self.send_header("Location", result["redirect"])
                    self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
                    self._cors_headers(self.headers.get("Origin", ""))
                    self._security_headers()
                    self.end_headers()
                else:
                    self._respond(404, result)

            elif path == "/api/sponsored/pricing":
                if not self._rate_limit_check("default"):
                    return
                self._respond(200, handle_pricing_tiers())

            elif path == "/api/cart":
                if not self._rate_limit_check("default"):
                    return
                self._respond(200, get_cart(query))

            elif path == "/api/checkout/address":
                if not self._rate_limit_check("default"):
                    return
                self._respond(200, get_addresses(query))

            elif path == "/api/orders":
                if not self._rate_limit_check("default"):
                    return
                self._respond(200, get_orders(query))

            elif path.startswith("/api/orders/"):
                if not self._rate_limit_check("default"):
                    return
                order_id = path.split("/")[-1]
                self._respond(200, get_order_detail(order_id))

            # ── User Auth & Profile GET (no API key) ─────────────────
            elif path.startswith("/api/auth/me"):
                token = self.headers.get("Authorization", "").replace("Bearer ", "")
                uid = self._auth_verify_token(token)
                if not uid:
                    self._respond(401, {"error": "Invalid session"})
                else:
                    try:
                        users = sb_request("GET", f"/rest/v1/mn_user_profiles?user_id=eq.{uid}&select=*")
                        user = users[0] if users else {"user_id": uid}
                        self._respond(200, user)
                    except Exception:
                        self._respond(200, {"user_id": uid})

            elif path.startswith("/api/user/"):
                token = self.headers.get("Authorization", "").replace("Bearer ", "")
                uid = self._auth_verify_token(token)
                if not uid:
                    self._respond(401, {"error": "Authentication required"})
                elif path == "/api/user/profile":
                    self._handle_user_profile(uid)
                elif path == "/api/user/cards":
                    self._handle_user_cards(uid)
                elif path == "/api/user/persons":
                    self._handle_user_persons(uid)
                elif path == "/api/user/outfits":
                    self._handle_user_outfits(uid)
                elif path == "/api/user/stats":
                    self._handle_user_stats(uid)
                else:
                    self._respond(404, {"error": "Not found"})

            # ── Authenticated GET endpoints ───────────────────────────────
            else:
                api_key = self.headers.get("X-API-Key", "")
                if not validate_api_key_format(api_key):
                    self._respond(401, {"error": "invalid_api_key_format"})
                    return
                brand_id = validate_api_key(api_key)
                if not brand_id:
                    self._respond(401, {"error": "invalid_api_key"})
                    return

                if path == "/api/sponsored/campaigns":
                    if not self._rate_limit_check("default"):
                        return
                    self._respond(200, handle_list_campaigns(brand_id))

                elif path.startswith("/api/sponsored/campaigns/") and path.endswith("/performance"):
                    if not self._rate_limit_check("default"):
                        return
                    campaign_id = path.split("/")[-2]
                    self._respond(200, handle_campaign_performance(campaign_id))

                elif path == "/api/network/report":
                    if not self._rate_limit_check("default"):
                        return
                    days = int(query.get("days", ["30"])[0])
                    self._respond(200, get_brand_network_report(brand_id, days))

                elif path.startswith("/api/network/product/") and path.endswith("/performance"):
                    if not self._rate_limit_check("default"):
                        return
                    product_id = path.split("/")[-2]
                    days = int(query.get("days", ["30"])[0])
                    self._respond(200, get_product_performance(product_id, days))

                elif path == "/api/recommend/compatibility":
                    if not self._rate_limit_check("default"):
                        return
                    other_brand_id = query.get("brand_id", [""])[0]
                    if not other_brand_id:
                        self._respond(400, {"error": "brand_id query param required"})
                        return
                    try:
                        scorer = NetworkCompatibilityScorer()
                        score = scorer.compute_pair_score(brand_id, other_brand_id)
                        self._respond(200, score)
                    except Exception as e:
                        self._respond(500, {"error": str(e)})

                elif path == "/api/dashboard/overview":
                    if not self._rate_limit_check("default"):
                        return
                    self._respond(200, handle_dashboard_overview(brand_id))

                elif path == "/api/dashboard/products":
                    if not self._rate_limit_check("default"):
                        return
                    self._respond(200, handle_dashboard_products(brand_id))

                elif path == "/api/dashboard/network-settings":
                    if not self._rate_limit_check("default"):
                        return
                    self._respond(200, handle_dashboard_network_settings(brand_id))

                elif path == "/api/dashboard/analytics":
                    if not self._rate_limit_check("default"):
                        return
                    days = int(query.get("days", ["30"])[0])
                    self._respond(200, handle_dashboard_analytics(brand_id, days))

                elif path == "/api/dashboard/wallet":
                    if not self._rate_limit_check("default"):
                        return
                    self._respond(200, handle_dashboard_wallet(brand_id))

                elif path == "/api/network/partners":
                    if not self._rate_limit_check("default"):
                        return
                    self._respond(200, handle_network_partners(brand_id))

                else:
                    self._respond(404, {"error": "not_found"})

        except Exception as e:
            self._respond(500, {"error": sanitize_error(e)})

    def do_POST(self):
        try:
            from urllib.parse import urlparse
            path = urlparse(self.path).path.rstrip("/")

            # Bot check
            ua = self.headers.get("User-Agent", "")
            if is_bot_request(ua):
                self._respond(403, {"error": "forbidden"})
                return

            # ── User Auth & Profile POST (proxy BEFORE reading body) ──
            if path.startswith("/api/auth/send-otp"):
                body = json.loads(self.rfile.read(content_length)) if content_length > 0 else {}
                self._auth_send_otp(body)
                return
            elif path.startswith("/api/auth/verify-otp"):
                body = json.loads(self.rfile.read(content_length)) if content_length > 0 else {}
                self._auth_verify_otp(body)
                return
            elif path.startswith("/api/auth/complete-profile"):
                body = json.loads(self.rfile.read(content_length)) if content_length > 0 else {}
                self._auth_complete_profile(body)
                return
            elif path.startswith("/api/auth/session"):
                body = json.loads(self.rfile.read(content_length)) if content_length > 0 else {}
                token = body.get("token", "")
                uid = self._auth_verify_token(token)
                if not uid:
                    self._respond(401, {"error": "Invalid session"})
                else:
                    self._respond(200, {"user_id": uid})
                return
            elif path.startswith("/api/user/profile"):
                token = self.headers.get("Authorization", "").replace("Bearer ", "")
                uid = self._auth_verify_token(token)
                if not uid:
                    self._respond(401, {"error": "Authentication required"})
                else:
                    body = json.loads(self.rfile.read(content_length)) if content_length > 0 else {}
                    self._update_user_profile(uid, body)
                return
            elif path.startswith("/api/user/cards"):
                token = self.headers.get("Authorization", "").replace("Bearer ", "")
                uid = self._auth_verify_token(token)
                if not uid:
                    self._respond(401, {"error": "Authentication required"})
                else:
                    body = json.loads(self.rfile.read(content_length)) if content_length > 0 else {}
                    self._add_user_card(uid, body)
                return
            elif path.startswith("/api/user/persons"):
                token = self.headers.get("Authorization", "").replace("Bearer ", "")
                uid = self._auth_verify_token(token)
                if not uid:
                    self._respond(401, {"error": "Authentication required"})
                else:
                    body = json.loads(self.rfile.read(content_length)) if content_length > 0 else {}
                    self._add_user_person(uid, body)
                return
            elif path.startswith("/api/user/outfits"):
                token = self.headers.get("Authorization", "").replace("Bearer ", "")
                uid = self._auth_verify_token(token)
                if not uid:
                    self._respond(401, {"error": "Authentication required"})
                else:
                    body = json.loads(self.rfile.read(content_length)) if content_length > 0 else {}
                    self._save_user_outfit(uid, body)
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

            # ── Public: Cart & Checkout POST (user_id based) ────────
            elif path == "/api/cart/add":
                if not self._rate_limit_check("default"):
                    return
                self._respond(200, add_to_cart(body))

            elif path == "/api/cart/update":
                if not self._rate_limit_check("default"):
                    return
                self._respond(200, update_cart_item(body))

            elif path == "/api/cart/remove":
                if not self._rate_limit_check("default"):
                    return
                self._respond(200, remove_from_cart({'item_id': [body.get('item_id')]}))

            elif path == "/api/cart/clear":
                if not self._rate_limit_check("default"):
                    return
                self._respond(200, clear_cart({'user_id': [body.get('user_id')]}))

            elif path == "/api/checkout/create":
                if not self._rate_limit_check("default"):
                    return
                self._respond(200, create_order(body))

            elif path == "/api/checkout/verify":
                if not self._rate_limit_check("default"):
                    return
                self._respond(200, verify_payment(body))

            elif path == "/api/checkout/address":
                if not self._rate_limit_check("default"):
                    return
                self._respond(200, save_address(body))

            # ── Public: Shopify Webhook (no auth, HMAC verified internally) ──
            elif path == "/api/webhooks/shopify":
                self._respond(200, handle_shopify_webhook(body, dict(self.headers)))

            # ── Public: Order Status Update (for brands) ──
            elif path == "/api/orders/status":
                if not self._rate_limit_check("default"):
                    return
                self._respond(200, update_order_status(body))

            # ── Public: Recommend (customer-facing widget, no API key) ──
            elif path == "/api/recommend":
                if not self._rate_limit_check("recommend"):
                    return
                body = sanitize_body(body, allowed_fields={
                    "user_id", "session_token", "occasion", "price_tier",
                    "include_closet", "outfit_count", "brand_id", "user_id",
                    "price_range_min", "price_range_max", "gender", "style",
                    "vibe", "skin_tone", "body_shape", "anchor_item",
                    "user_context", "currency", "user_image",
                    "brand_name",
                })
                body["brand_id"] = body.get("brand_id", "")
                body["user_id"] = body.get("user_id", "")
                result = handle_recommend(body)
                self._respond(200, result)

            # ── Public: Tracking & Attribution (no auth) ──────────────
            elif path == "/api/track/click":
                if not self._rate_limit_check("default"):
                    return
                result = handle_click_record(body, dict(self.headers))
                self._respond(200, result)

            elif path == "/api/webhooks/merchant-pixel":
                if not self._rate_limit_check("default"):
                    return
                result = handle_merchant_pixel_event(body)
                self._respond(200, result)

            elif path == "/api/products/register":
                if not self._rate_limit_check("default"):
                    return
                result = handle_product_registration(body)
                self._respond(200, result)

            elif path == "/api/reconciliation/run":
                if not self._rate_limit_check("default"):
                    return
                result = run_reconciliation()
                self._respond(200, result)

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

                # ── Sponsored Campaign Endpoints ──────────────────────
                elif path == "/api/sponsored/campaigns":
                    if not self._rate_limit_check("default"):
                        return
                    result = handle_create_campaign(body, brand_id)
                    status = 400 if result.get("error") else 201
                    self._respond(status, result)

                elif path.startswith("/api/sponsored/campaigns/") and path.endswith("/update"):
                    if not self._rate_limit_check("default"):
                        return
                    campaign_id = path.split("/")[-2]
                    result = handle_update_campaign(campaign_id, body, brand_id)
                    self._respond(200, result)

                elif path.startswith("/api/sponsored/campaigns/") and path.endswith("/pause"):
                    if not self._rate_limit_check("default"):
                        return
                    campaign_id = path.split("/")[-2]
                    result = handle_pause_campaign(campaign_id, brand_id)
                    self._respond(200, result)

                elif path.startswith("/api/sponsored/campaigns/") and path.endswith("/resume"):
                    if not self._rate_limit_check("default"):
                        return
                    campaign_id = path.split("/")[-2]
                    result = handle_resume_campaign(campaign_id, brand_id)
                    self._respond(200, result)

                elif path.startswith("/api/sponsored/campaigns/") and path.endswith("/delete"):
                    if not self._rate_limit_check("default"):
                        return
                    campaign_id = path.split("/")[-2]
                    result = handle_delete_campaign(campaign_id, brand_id)
                    self._respond(200, result)

                # ── Network Event Tracking ────────────────────────────
                elif path == "/api/network/event":
                    if not self._rate_limit_check("default"):
                        return
                    result = track_network_event(
                        event_type=body.get("event_type", ""),
                        brand_id=body.get("brand_id", brand_id),
                        user_id=body.get("user_id", user_id),
                        product_id=body.get("product_id", ""),
                        session_id=body.get("session_id", ""),
                        host_brand_id=body.get("host_brand_id", brand_id),
                        campaign_id=body.get("campaign_id", ""),
                        event_data=body.get("event_data", {}),
                    )
                    self._respond(200, result)

                # ── Commission & Attribution Queries ──────────────────
                elif path == "/api/commissions/summary":
                    if not self._rate_limit_check("default"):
                        return
                    result = get_commission_summary(brand_id)
                    self._respond(200, result)

                elif path == "/api/commissions/advance":
                    if not self._rate_limit_check("default"):
                        return
                    result = batch_advance_pending_commissions()
                    self._respond(200, result)

                elif path == "/api/commissions/advance-payable":
                    if not self._rate_limit_check("default"):
                        return
                    result = batch_advance_confirmed_to_payable()
                    self._respond(200, result)

                # ── Eligibility Check ─────────────────────────────────
                elif path == "/api/recommend/eligibility":
                    if not self._rate_limit_check("default"):
                        return
                    engine = EligibilityEngine()
                    candidate = body.get("product", {})
                    host_prefs = body.get("host_preferences", {})
                    category_rules = body.get("category_rules", {})
                    user_context = body.get("user_context", {})
                    eligible, reason = engine.check(candidate, brand_id, host_prefs, category_rules, user_context)
                    self._respond(200, {"eligible": eligible, "reason": reason})

                # ── Dashboard POST Endpoints ──────────────────────────
                elif path == "/api/dashboard/network-settings":
                    if not self._rate_limit_check("default"):
                        return
                    body = sanitize_body(body, allowed_fields={
                        "vton_enabled", "receive_recommendations",
                        "distribute_products", "promote_products",
                        "promotion_budget", "max_cpc_bid",
                        "target_categories", "category_rules",
                        "competitor_exclusions", "cross_brand_density",
                        "price_min", "price_max", "positioning", "styles",
                        "men_accept_mode", "men_accept", "women_accept_mode", "women_accept",
                        "external_price_min", "external_price_max",
                        "exclude_brands", "exclude_categories", "block_competitors",
                        "place_vton", "place_complete_the_look", "place_product_page", "place_cart",
                        "dist_gender", "dist_host_categories", "dist_price_band",
                        "promo_budget", "promo_categories",
                    })
                    self._respond(200, handle_dashboard_network_settings(brand_id, body))

                elif path == "/api/dashboard/wallet/topup":
                    if not self._rate_limit_check("default"):
                        return
                    body = sanitize_body(body, allowed_fields={"amount", "payment_method"})
                    self._respond(200, {"error": "topup_not_implemented"})

                # ── Brand Onboarding (Shopify Sync) ─────────────────
                elif path == "/api/brand/onboard-shopify":
                    if not self._rate_limit_check("default"):
                        return
                    body = sanitize_body(body, allowed_fields={"shop_url", "access_token"})
                    if not body.get("shop_url") or not body.get("access_token"):
                        self._respond(400, {"error": "shop_url and access_token required"})
                        return
                    result = start_shopify_sync(brand_id, body["shop_url"], body["access_token"])
                    self._respond(200, result)

                elif path == "/api/brand/register-webhooks":
                    if not self._rate_limit_check("default"):
                        return
                    body = sanitize_body(body, allowed_fields={"shop_url", "access_token"})
                    if not body.get("shop_url") or not body.get("access_token"):
                        self._respond(400, {"error": "shop_url and access_token required"})
                        return
                    result = register_shopify_webhooks(brand_id, body["shop_url"], body["access_token"])
                    self._respond(200, result)

                else:
                    self._respond(404, {"error": "not_found"})

        except json.JSONDecodeError:
            self._respond(400, {"error": "invalid_json"})
        except Exception as e:
            self._respond(500, {"error": sanitize_error(e)})

    def do_DELETE(self):
        try:
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/")
            query = parse_qs(parsed.query)

            ua = self.headers.get("User-Agent", "")
            if is_bot_request(ua):
                self._respond(403, {"error": "forbidden"})
                return

            # ── User Profile DELETE (no API key) ─────────────────────
            if path.startswith("/api/user/"):
                token = self.headers.get("Authorization", "").replace("Bearer ", "")
                uid = self._auth_verify_token(token)
                if not uid:
                    self._respond(401, {"error": "Authentication required"})
                    return
                from urllib.parse import parse_qs
                query = parse_qs(parsed.query)
                if path == "/api/user/cards":
                    card_id = query.get("card_id", [None])[0]
                    if not card_id:
                        self._respond(400, {"error": "card_id required"})
                    else:
                        try:
                            sb_request("DELETE", f"/rest/v1/mn_saved_cards?card_id=eq.{card_id}&user_id=eq.{uid}")
                            self._respond(200, {"ok": True})
                        except Exception as e:
                            self._respond(500, {"error": str(e)})
                elif path == "/api/user/persons":
                    person_id = query.get("person_id", [None])[0]
                    if not person_id:
                        self._respond(400, {"error": "person_id required"})
                    else:
                        try:
                            sb_request("DELETE", f"/rest/v1/mn_person_profiles?person_id=eq.{person_id}&user_id=eq.{uid}")
                            self._respond(200, {"ok": True})
                        except Exception as e:
                            self._respond(500, {"error": str(e)})
                elif path == "/api/user/outfits":
                    outfit_id = query.get("outfit_id", [None])[0]
                    if not outfit_id:
                        self._respond(400, {"error": "outfit_id required"})
                    else:
                        try:
                            sb_request("DELETE", f"/rest/v1/mn_saved_outfits?outfit_id=eq.{outfit_id}&user_id=eq.{uid}")
                            self._respond(200, {"ok": True})
                        except Exception as e:
                            self._respond(500, {"error": str(e)})
                else:
                    self._respond(404, {"error": "not_found"})
                return

            self._respond(404, {"error": "not_found"})

        except Exception as e:
            self._respond(500, {"error": sanitize_error(e)})

    def log_message(self, format, *args):
        pass
