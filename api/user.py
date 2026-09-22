"""
MY NARRATIVE — User Profile API
Style Intelligence Profile, saved cards, person profiles, outfits
Change ID: ADD-USR-006-260922
"""

import os, json
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://fmganuxtqbquubtvvqdo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_REST = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}


def sb_get(path):
    import urllib.request
    req = urllib.request.Request(f"{SUPABASE_REST}{path}", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def sb_post(path, data):
    import urllib.request
    body = json.dumps(data).encode()
    req = urllib.request.Request(f"{SUPABASE_REST}{path}", data=body, headers=HEADERS, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def sb_patch(path, data):
    import urllib.request
    body = json.dumps(data).encode()
    req = urllib.request.Request(f"{SUPABASE_REST}{path}", data=body, headers=HEADERS, method="PATCH")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def sb_delete(path):
    import urllib.request
    req = urllib.request.Request(f"{SUPABASE_REST}{path}", headers=HEADERS, method="DELETE")
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status < 300


def get_user_id(headers):
    """Extract user_id from Authorization header"""
    auth = headers.get("Authorization", "")
    token = auth.replace("Bearer ", "") if auth.startswith("Bearer ") else ""
    if not token:
        return None
    try:
        from api.auth import verify_session_token
        uid, _ = verify_session_token(token)
        return uid
    except Exception:
        # Fallback: parse token directly
        import hashlib
        parts = token.split(":")
        if len(parts) >= 2:
            return parts[0]
        return None


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        qs = parse_qs(parsed.query)

        user_id = get_user_id(self.headers)
        if not user_id:
            return self._json(401, {"error": "Authentication required"})

        if path == "/api/user/profile":
            return self._get_profile(user_id)
        elif path == "/api/user/cards":
            return self._get_cards(user_id)
        elif path == "/api/user/persons":
            return self._get_persons(user_id)
        elif path == "/api/user/outfits":
            return self._get_outfits(user_id)
        elif path == "/api/user/media":
            return self._get_media(user_id)
        elif path == "/api/user/recommendations":
            return self._get_recommendations(user_id)
        elif path == "/api/user/stats":
            return self._get_stats(user_id)
        elif path == "/api/user/complete-profile":
            return self._get_profile(user_id)
        else:
            self._json(404, {"error": "Not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}

        user_id = get_user_id(self.headers)
        if not user_id:
            return self._json(401, {"error": "Authentication required"})

        if path == "/api/user/profile":
            return self._update_profile(user_id, body)
        elif path == "/api/user/cards":
            return self._add_card(user_id, body)
        elif path == "/api/user/persons":
            return self._add_person(user_id, body)
        elif path == "/api/user/outfits":
            return self._save_outfit(user_id, body)
        else:
            self._json(404, {"error": "Not found"})

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        qs = parse_qs(parsed.query)

        user_id = get_user_id(self.headers)
        if not user_id:
            return self._json(401, {"error": "Authentication required"})

        if path == "/api/user/cards":
            card_id = qs.get("card_id", [None])[0]
            if not card_id:
                return self._json(400, {"error": "card_id required"})
            sb_delete(f"/mn_saved_cards?card_id=eq.{card_id}&user_id=eq.{user_id}")
            return self._json(200, {"ok": True})
        elif path == "/api/user/persons":
            person_id = qs.get("person_id", [None])[0]
            if not person_id:
                return self._json(400, {"error": "person_id required"})
            sb_delete(f"/mn_person_profiles?person_id=eq.{person_id}&user_id=eq.{user_id}")
            return self._json(200, {"ok": True})
        elif path == "/api/user/outfits":
            outfit_id = qs.get("outfit_id", [None])[0]
            if not outfit_id:
                return self._json(400, {"error": "outfit_id required"})
            sb_delete(f"/mn_saved_outfits?outfit_id=eq.{outfit_id}&user_id=eq.{user_id}")
            return self._json(200, {"ok": True})
        else:
            self._json(404, {"error": "Not found"})

    def _get_profile(self, user_id):
        try:
            users = sb_get(f"/mn_user_profiles?user_id=eq.{user_id}&select=*")
            profile = users[0] if users else None
        except Exception:
            profile = None

        if not profile:
            return self._json(200, {"user_id": user_id, "exists": False})

        # Enrich with counts
        try:
            persons = sb_get(f"/mn_person_profiles?user_id=eq.{user_id}&select=person_id")
            profile["person_count"] = len(persons)
        except Exception:
            profile["person_count"] = 0

        try:
            cards = sb_get(f"/mn_saved_cards?user_id=eq.{user_id}&select=card_id")
            profile["card_count"] = len(cards)
        except Exception:
            profile["card_count"] = 0

        try:
            outfits = sb_get(f"/mn_saved_outfits?user_id=eq.{user_id}&select=outfit_id")
            profile["outfit_count"] = len(outfits)
        except Exception:
            profile["outfit_count"] = 0

        try:
            tryons = sb_get(f"/mn_tryon_sessions?user_id=eq.{user_id}&select=session_id")
            profile["tryon_count"] = len(tryons)
        except Exception:
            profile["tryon_count"] = 0

        return self._json(200, profile)

    def _update_profile(self, user_id, body):
        allowed = {"display_name", "gender", "age_range", "height_cm", "body_type",
                    "preferred_styles", "preferred_colors", "avoid_colors", "preferred_patterns",
                    "fit_preference"}
        updates = {k: v for k, v in body.items() if k in allowed and v is not None}

        if not updates:
            return self._json(400, {"error": "No valid fields to update"})

        try:
            result = sb_patch(f"/mn_user_profiles?user_id=eq.{user_id}", updates)
            return self._json(200, {"ok": True, "profile": result[0] if result else updates})
        except Exception as e:
            return self._json(500, {"error": str(e)})

    def _get_cards(self, user_id):
        try:
            cards = sb_get(f"/mn_saved_cards?user_id=eq.{user_id}&select=*,mn_bank_cards!inner(card_network)&order=is_primary.desc,created_at.desc")
        except Exception:
            try:
                cards = sb_get(f"/mn_saved_cards?user_id=eq.{user_id}&select=*&order=is_primary.desc,created_at.desc")
            except Exception:
                cards = []

        # Enrich with offer counts
        enriched = []
        for c in cards:
            try:
                offers = sb_get(f"/mn_merchant_offers?bank_name=eq.{c['bank_name']}&is_active=eq.true&select=offer_id")
                c["active_offers"] = len(offers)
            except Exception:
                c["active_offers"] = 0
            enriched.append(c)

        return self._json(200, enriched)

    def _add_card(self, user_id, body):
        required = {"bank_name", "card_type", "card_variant"}
        if not all(k in body for k in required):
            return self._json(400, {"error": "bank_name, card_type, card_variant required"})

        import hashlib, time
        card_id = f"card_{int(time.time())}_{hashlib.sha256(f'{user_id}{body[\"card_variant\"]}'.encode()).hexdigest()[:8]}"

        card = {
            "card_id": card_id,
            "user_id": user_id,
            "bank_name": body["bank_name"],
            "card_type": body["card_type"],
            "card_variant": body["card_variant"],
            "card_network": body.get("card_network"),
            "is_primary": body.get("is_primary", False)
        }

        try:
            result = sb_post("/mn_saved_cards", card)
            return self._json(201, result[0] if result else card)
        except Exception as e:
            return self._json(500, {"error": str(e)})

    def _get_persons(self, user_id):
        try:
            persons = sb_get(f"/mn_person_profiles?user_id=eq.{user_id}&select=*&order=is_self.desc,created_at.desc")
        except Exception:
            persons = []
        return self._json(200, persons)

    def _add_person(self, user_id, body):
        import hashlib, time
        person_id = f"person_{int(time.time())}_{hashlib.sha256(f'{user_id}{body.get(\"label\",\"\")}'.encode()).hexdigest()[:8]}"

        person = {
            "person_id": person_id,
            "user_id": user_id,
            "relationship": body.get("relationship", "self"),
            "label": body.get("label", "Me"),
            "is_self": body.get("is_self", body.get("relationship", "self") == "self"),
            "preferred_styles": body.get("preferred_styles", []),
            "preferred_colors": body.get("preferred_colors", []),
            "avoid_colors": body.get("avoid_colors", []),
            "preferred_patterns": body.get("preferred_patterns", []),
            "fit_preference": body.get("fit_preference"),
            "height_cm": body.get("height_cm"),
            "body_type": body.get("body_type")
        }

        try:
            result = sb_post("/mn_person_profiles", person)
            return self._json(201, result[0] if result else person)
        except Exception as e:
            return self._json(500, {"error": str(e)})

    def _get_outfits(self, user_id):
        try:
            outfits = sb_get(f"/mn_saved_outfits?user_id=eq.{user_id}&select=*&order=created_at.desc&limit=50")
        except Exception:
            outfits = []
        return self._json(200, outfits)

    def _save_outfit(self, user_id, body):
        import hashlib, time
        outfit_id = f"outfit_{int(time.time())}_{hashlib.sha256(json.dumps(body.get('items',[])).encode()).hexdigest()[:8]}"

        outfit = {
            "outfit_id": outfit_id,
            "user_id": user_id,
            "person_id": body.get("person_id"),
            "outfit_name": body.get("outfit_name"),
            "occasion": body.get("occasion"),
            "items": body.get("items", []),
            "total_price": body.get("total_price"),
            "best_price": body.get("best_price"),
            "best_offer": body.get("best_offer"),
            "vton_image_url": body.get("vton_image_url"),
            "card_id": body.get("card_id")
        }

        try:
            result = sb_post("/mn_saved_outfits", outfit)
            return self._json(201, result[0] if result else outfit)
        except Exception as e:
            return self._json(500, {"error": str(e)})

    def _get_media(self, user_id):
        try:
            media = sb_get(f"/mn_user_media?user_id=eq.{user_id}&select=*&order=created_at.desc&limit=50")
        except Exception:
            media = []
        return self._json(200, media)

    def _get_recommendations(self, user_id):
        try:
            recos = sb_get(f"/mn_recommendation_history?user_id=eq.{user_id}&select=*&order=created_at.desc&limit=20")
        except Exception:
            recos = []
        return self._json(200, recos)

    def _get_stats(self, user_id):
        stats = {}
        for table, key in [
            ("mn_person_profiles", "persons"),
            ("mn_saved_cards", "cards"),
            ("mn_saved_outfits", "outfits"),
            ("mn_tryon_sessions", "tryons"),
            ("mn_user_media", "media"),
            ("mn_recommendation_history", "recommendations")
        ]:
            try:
                rows = sb_get(f"/{table}?user_id=eq.{user_id}&select=user_id")
                stats[key] = len(rows)
            except Exception:
                stats[key] = 0
        return self._json(200, stats)

    def _json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def log_message(self, fmt, *args):
        print(f"[USER] {args[0] if args else fmt}")
