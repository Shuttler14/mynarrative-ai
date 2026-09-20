"""Widget bootstrap handler."""
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


def handle_bootstrap(body: dict) -> dict:
    """Initialize widget session. Validates API key, checks subscription, returns config."""
    api_key = body.get("api_key", "")
    fingerprint = body.get("fingerprint", "")
    brand_domain = body.get("brand_domain", "")

    if not api_key:
        return {"error": "api_key required"}

    # Validate API key
    import hashlib
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    key_result = _sb_request("GET", f"/rest/v1/api_keys?key_hash=eq.{key_hash}&is_active=eq.true&select=brand_id,permissions")
    if not key_result or len(key_result) == 0:
        return {"error": "Invalid API key"}

    brand_id = key_result[0]["brand_id"]

    # Check subscription
    sub_result = _sb_request("GET", f"/rest/v1/brand_subscriptions?brand_id=eq.{brand_id}&select=status,current_period_end,plan_tier")
    if sub_result and len(sub_result) > 0:
        sub = sub_result[0]
        if sub.get("status") not in ("active", "trialing"):
            brand_result = _sb_request("GET", f"/rest/v1/brands?id=eq.{brand_id}&select=slug")
            slug = brand_result[0]["slug"] if brand_result else ""
            return {"error": "subscription_expired", "redirect_url": f"https://mynarrative.store/brand/{slug}"}

    # Get or create user
    user_id = body.get("user_id")
    if not user_id and fingerprint:
        user_result = _sb_request("GET", f"/rest/v1/users?fingerprint_id=eq.{fingerprint}&select=id")
        if user_result and len(user_result) > 0:
            user_id = user_result[0]["id"]
        else:
            new_user = _sb_request("POST", "/rest/v1/users", {
                "fingerprint_id": fingerprint,
                "is_anonymous": True,
                "preferred_brands": [brand_id]
            })
            user_id = new_user[0]["id"] if new_user and len(new_user) > 0 else None

    # Get widget config
    brand_result = _sb_request("GET", f"/rest/v1/brands?id=eq.{brand_id}&select=widget_config,name,slug")
    widget_config = brand_result[0].get("widget_config", {}) if brand_result else {}
    brand_name = brand_result[0].get("name", "AI Stylist") if brand_result else "AI Stylist"

    # Get network mode
    network_mode = "brand_only"
    network_config = {}
    host_prefs = _sb_request("GET", f"/rest/v1/host_preferences?brand_id=eq.{brand_id}&select=network_mode")
    if host_prefs and isinstance(host_prefs, list) and len(host_prefs) > 0:
        network_mode = host_prefs[0].get("network_mode", "brand_only")
        if network_mode != "brand_only":
            # Load category rules and exclusions for frontend display
            cat_rules = _sb_request("GET", f"/rest/v1/host_category_rules?brand_id=eq.{brand_id}&select=*")
            brand_excl = _sb_request("GET", f"/rest/v1/brand_exclusions?host_brand_id=eq.{brand_id}&select=excluded_brand_id")
            network_config = {
                "show_cross_brand": network_mode in ("curated_network", "open_network"),
                "show_sponsored_badge": True,
                "category_count": len(cat_rules) if isinstance(cat_rules, list) else 0,
                "excluded_brand_count": len(brand_excl) if isinstance(brand_excl, list) else 0,
            }

    # Create session token
    import base64
    session_payload = {
        "brand_id": brand_id,
        "user_id": user_id,
        "iat": __import__("time").time(),
        "exp": __import__("time").time() + 86400
    }
    session_token = base64.urlsafe_b64encode(json.dumps(session_payload).encode()).decode()

    return {
        "session_token": session_token,
        "user_id": user_id,
        "widget_config": {
            "primary_color": widget_config.get("primary_color", "#39A596"),
            "position": widget_config.get("position", "bottom-right"),
            "greeting": widget_config.get("greeting", f"Hi! I'm {brand_name}'s AI stylist."),
            "brand_name": brand_name,
        },
        "network_mode": network_mode,
        "network_config": network_config,
        "subscription_status": "active",
    }
