"""Shared Supabase request helper for B2B platform modules."""
import json
import os
import requests


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
    full_url = f"{url.rstrip('/')}{path}"
    try:
        if method == "GET":
            resp = requests.get(full_url, headers=headers, timeout=15)
        elif method == "POST":
            resp = requests.post(full_url, json=payload, headers=headers, timeout=15)
        elif method == "PATCH":
            resp = requests.patch(full_url, json=payload, headers=headers, timeout=15)
        elif method == "DELETE":
            resp = requests.delete(full_url, headers=headers, timeout=15)
        else:
            resp = requests.request(method, full_url, json=payload, headers=headers, timeout=15)
        return resp.json() if resp.text else None
    except Exception:
        return None
