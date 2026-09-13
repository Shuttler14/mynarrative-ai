"""User identity handler — fingerprint-based cross-brand identification."""
import json
import os
import urllib.request

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")


def _sb_request(method, path, payload=None):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    body = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(f"{SUPABASE_URL.rstrip('/')}{path}", data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode() or "null")
    except Exception:
        return None


def handle_identify(body: dict) -> dict:
    """Identify or create user by fingerprint. Returns existing user or creates new."""
    fingerprint = body.get("fingerprint", "")
    brand_id = body.get("brand_id", "")

    if not fingerprint:
        return {"error": "fingerprint required"}

    # Check if user exists
    existing = _sb_request("GET", f"/rest/v1/users?fingerprint_id=eq.{fingerprint}&select=id,display_name,closet_item_count,preferred_brands")
    if existing and len(existing) > 0:
        user = existing[0]
        # Add brand to preferred_brands if not already there
        if brand_id and brand_id not in (user.get("preferred_brands") or []):
            brands = user.get("preferred_brands") or []
            brands.append(brand_id)
            _sb_request("PATCH", f"/rest/v1/users?id=eq.{user['id']}", {
                "preferred_brands": brands,
                "last_seen_at": "now()"
            })
        return {
            "user_id": user["id"],
            "is_new": False,
            "display_name": user.get("display_name", "Fashion Explorer"),
            "closet_item_count": user.get("closet_item_count", 0)
        }

    # Create new anonymous user
    new_user = _sb_request("POST", "/rest/v1/users", {
        "fingerprint_id": fingerprint,
        "is_anonymous": True,
        "preferred_brands": [brand_id] if brand_id else []
    })

    if new_user and len(new_user) > 0:
        return {
            "user_id": new_user[0]["id"],
            "is_new": True,
            "display_name": "Fashion Explorer",
            "closet_item_count": 0
        }

    return {"error": "Failed to create user"}
