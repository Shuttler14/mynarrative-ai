"""
MY NARRATIVE — Auth API
Email OTP login, profile management, session tokens
Change ID: ADD-USR-005-260922
"""

import os, json, time, hashlib, secrets
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

# In-memory OTP store (prod: use Redis/Supabase)
OTP_STORE = {}
OTP_TTL = 300  # 5 minutes
JWT_SECRET = os.environ.get("JWT_SECRET", "mn_" + hashlib.sha256(SUPABASE_KEY.encode()).hexdigest()[:32])


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


def generate_otp():
    return f"{secrets.randbelow(900000) + 100000}"


def hash_otp(email, otp):
    return hashlib.sha256(f"{email}:{otp}:{OTP_TTL}".encode()).hexdigest()[:16]


def create_session_token(user_id, email):
    """Simple HMAC token (prod: use JWT library)"""
    payload = f"{user_id}:{email}:{int(time.time())}"
    sig = hashlib.sha256(f"{payload}:{JWT_SECRET}".encode()).hexdigest()[:16]
    return f"{payload}:{sig}"


def verify_session_token(token):
    """Returns user_id, email if valid"""
    try:
        parts = token.split(":")
        if len(parts) != 4:
            return None, None
        user_id, email, ts, sig = parts
        expected = hashlib.sha256(f"{user_id}:{email}:{ts}:{JWT_SECRET}".encode()).hexdigest()[:16]
        if sig != expected:
            return None, None
        if int(time.time()) - int(ts) > 86400 * 30:  # 30 day expiry
            return None, None
        return user_id, email
    except Exception:
        return None, None


def send_otp_email(email, otp):
    """Send OTP via email. Returns True on success."""
    try:
        # Try Resend API if configured
        resend_key = os.environ.get("RESEND_API_KEY", "")
        if resend_key:
            import urllib.request
            payload = json.dumps({
                "from": "MY NARRATIVE <noreply@mynarrative.store>",
                "to": email,
                "subject": "Your MY NARRATIVE login code",
                "html": f"""
                <div style="font-family:sans-serif;max-width:400px;margin:40px auto;text-align:center">
                    <h2 style="color:#333">Your login code</h2>
                    <div style="font-size:32px;font-weight:bold;letter-spacing:0.3em;padding:20px;background:#f5f5f5;border-radius:12px;margin:20px 0;color:#00bcbc">{otp}</div>
                    <p style="color:#666;font-size:14px">This code expires in 5 minutes.</p>
                    <p style="color:#999;font-size:12px;margin-top:20px">If you didn't request this, ignore this email.</p>
                </div>
                """
            }).encode()
            req = urllib.request.Request(
                "https://api.resend.com/emails",
                data=payload,
                headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status == 200
        # Fallback: just log it
        print(f"[AUTH] OTP for {email}: {otp}")
        return True
    except Exception as e:
        print(f"[AUTH] Email send error: {e}")
        return False


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # Parse body
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}

        if path == "/api/auth/send-otp":
            return self._send_otp(body)
        elif path == "/api/auth/verify-otp":
            return self._verify_otp(body)
        elif path == "/api/auth/complete-profile":
            return self._complete_profile(body)
        elif path == "/api/auth/session":
            return self._get_session(body)
        else:
            self._json(404, {"error": "Not found"})

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/api/auth/me":
            auth = self.headers.get("Authorization", "")
            token = auth.replace("Bearer ", "") if auth.startswith("Bearer ") else ""
            user_id, email = verify_session_token(token)
            if not user_id:
                return self._json(401, {"error": "Invalid session"})
            try:
                users = sb_get(f"/mn_user_profiles?user_id=eq.{user_id}&select=*")
                user = users[0] if users else {"user_id": user_id, "email": email}
                return self._json(200, user)
            except Exception as e:
                return self._json(200, {"user_id": user_id, "email": email})
        else:
            self._json(404, {"error": "Not found"})

    def _send_otp(self, body):
        email = (body.get("email") or "").strip().lower()
        if not email or "@" not in email:
            return self._json(400, {"error": "Valid email required"})

        otp = generate_otp()
        OTP_STORE[email] = {"otp": otp, "ts": time.time(), "attempts": 0}

        sent = send_otp_email(email, otp)
        if not sent:
            return self._json(500, {"error": "Failed to send email"})

        # Check if user exists
        try:
            users = sb_get(f"/mn_user_profiles?email=eq.{email}&select=user_id")
            is_new = len(users) == 0
        except Exception:
            is_new = True

        return self._json(200, {"ok": True, "is_new_user": is_new})

    def _verify_otp(self, body):
        email = (body.get("email") or "").strip().lower()
        otp = (body.get("otp") or "").strip()

        if not email or not otp:
            return self._json(400, {"error": "Email and OTP required"})

        stored = OTP_STORE.get(email)
        if not stored:
            return self._json(400, {"error": "No code requested. Send a new one."})

        if time.time() - stored["ts"] > OTP_TTL:
            del OTP_STORE[email]
            return self._json(400, {"error": "Code expired. Send a new one."})

        if stored["attempts"] >= 5:
            del OTP_STORE[email]
            return self._json(400, {"error": "Too many attempts. Send a new code."})

        stored["attempts"] += 1

        if stored["otp"] != otp:
            return self._json(400, {"error": f"Wrong code. {5 - stored['attempts']} attempts left."})

        del OTP_STORE[email]

        # Get or create user
        try:
            users = sb_get(f"/mn_user_profiles?email=eq.{email}&select=user_id")
            if users:
                user_id = users[0]["user_id"]
                is_new = False
            else:
                user_id = f"mn_{hashlib.sha256(email.encode()).hexdigest()[:16]}"
                sb_post("/mn_user_profiles", {"user_id": user_id, "email": email})
                is_new = True
        except Exception as e:
            user_id = f"mn_{hashlib.sha256(email.encode()).hexdigest()[:16]}"
            is_new = True

        token = create_session_token(user_id, email)
        return self._json(200, {
            "ok": True,
            "token": token,
            "user_id": user_id,
            "email": email,
            "is_new_user": is_new
        })

    def _complete_profile(self, body):
        email = (body.get("email") or "").strip().lower()
        name = (body.get("name") or "").strip()
        gender = (body.get("gender") or "").strip()

        if not email:
            return self._json(400, {"error": "Email required"})

        user_id = f"mn_{hashlib.sha256(email.encode()).hexdigest()[:16]}"

        updates = {}
        if name:
            updates["display_name"] = name
        if gender:
            updates["gender"] = gender

        if updates:
            try:
                sb_patch(f"/mn_user_profiles?user_id=eq.{user_id}", updates)
            except Exception:
                try:
                    sb_post("/mn_user_profiles", {"user_id": user_id, "email": email, **updates})
                except Exception:
                    pass

        token = create_session_token(user_id, email)
        return self._json(200, {
            "ok": True,
            "token": token,
            "user_id": user_id,
            "email": email,
            "display_name": name,
            "gender": gender
        })

    def _get_session(self, body):
        token = body.get("token") or ""
        user_id, email = verify_session_token(token)
        if not user_id:
            return self._json(401, {"error": "Invalid session"})
        return self._json(200, {"user_id": user_id, "email": email})

    def _json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def log_message(self, fmt, *args):
        print(f"[AUTH] {args[0] if args else fmt}")
