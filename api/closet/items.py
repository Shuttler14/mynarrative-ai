"""Closet items handler — list user's closet items."""
import json
import os
import urllib.request

def _get_supabase_url():
    return os.environ.get("SUPABASE_URL", "")

def _get_supabase_key():
    return os.environ.get("SUPABASE_KEY", "")


def _sb_request(method, path, payload=None):
    supabase_url = _get_supabase_url()
    supabase_key = _get_supabase_key()
    if not supabase_url or not supabase_key:
        return None
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json"
    }
    body = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(f"{supabase_url.rstrip('/')}{path}", data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode() or "null")
    except Exception:
        return None


def handle_closet_items(user_id: str, query_string: str = "") -> dict:
    """List all items in user's closet."""
    if not user_id:
        return {"error": "user_id required"}

    # Parse query params
    params = {}
    if query_string:
        for pair in query_string.split("&"):
            if "=" in pair:
                k, v = pair.split("=", 1)
                params[k] = v

    category = params.get("category", "")
    page = int(params.get("page", "1"))
    limit = min(int(params.get("limit", "20")), 50)
    offset = (page - 1) * limit

    path = f"/rest/v1/user_closet_items?user_id=eq.{user_id}&order=created_at.desc&limit={limit}&offset={offset}"
    if category:
        path += f"&category=eq.{category}"

    items = _sb_request("GET", path)

    # Get total count
    count_path = f"/rest/v1/user_closet_items?user_id=eq.{user_id}&select=id"
    if category:
        count_path += f"&category=eq.{category}"
    count_result = _sb_request("GET", count_path)
    total = len(count_result) if count_result else 0

    return {
        "items": items or [],
        "total": total,
        "page": page,
        "has_more": offset + limit < total
    }
