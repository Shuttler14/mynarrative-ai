"""Core authentication module for B2B platform."""
import hashlib
import json
import os
import time
import urllib.request


def _get_supabase_url():
    return os.environ.get("SUPABASE_URL", "")


def _get_supabase_key():
    return os.environ.get("SUPABASE_KEY", "")


def _sb_request(method, path, payload=None):
    url = _get_supabase_url()
    key = _get_supabase_key()
    if not url or not key:
        return None
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }
    body = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(f"{url.rstrip('/')}{path}", data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode() or "null")
    except Exception:
        return None


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def validate_api_key(api_key: str) -> str:
    """Validate API key and return brand_id if valid."""
    if not api_key:
        return None
    key_hash = hash_api_key(api_key)
    result = _sb_request("GET", f"/rest/v1/api_keys?key_hash=eq.{key_hash}&is_active=eq.true&select=brand_id")
    if result and len(result) > 0:
        brand_id = result[0].get("brand_id")
        # Update last_used_at
        _sb_request("PATCH", f"/rest/v1/api_keys?key_hash=eq.{key_hash}", {"last_used_at": "now()"})
        return brand_id
    return None


def create_session_token(brand_id: str, user_id: str) -> str:
    """Create a simple session token (JWT-like)."""
    import base64
    payload = {
        "brand_id": brand_id,
        "user_id": user_id,
        "iat": int(time.time()),
        "exp": int(time.time()) + 86400  # 24 hours
    }
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()


def decode_session_token(token: str) -> dict:
    """Decode session token."""
    import base64
    try:
        payload = json.loads(base64.urlsafe_b64decode(token + "=="))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None
