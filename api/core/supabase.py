"""Shared Supabase request helper for B2B platform modules."""
import json
import os
import urllib.request


def _get_supabase_url():
    return os.environ.get("SUPABASE_URL", "")


def _get_supabase_key():
    return os.environ.get("SUPABASE_KEY", "")


def sb_request(method: str, path: str, payload=None):
    """Make an authenticated request to Supabase REST API."""
    url = _get_supabase_url()
    key = _get_supabase_key()
    if not url or not key:
        return None
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    body = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        f"{url.rstrip('/')}{path}",
        data=body, headers=headers, method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode() or "null"
            return json.loads(raw)
    except Exception:
        return None
