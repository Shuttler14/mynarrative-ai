"""Closet items handler — list user's closet items."""
import json
import os
import requests

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
        "Content-Type": "application/json",
    }
    full_url = f"{url.rstrip('/')}{path}"
    try:
        if method == "GET":
            resp = requests.get(full_url, headers=headers, timeout=15)
        elif method == "POST":
            resp = requests.post(full_url, json=payload, headers=headers, timeout=15)
        elif method == "PATCH":
            resp = requests.patch(full_url, json=payload, headers=headers, timeout=15)
        else:
            resp = requests.request(method, full_url, json=payload, headers=headers, timeout=15)
        return resp.json() if resp.text else None
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
