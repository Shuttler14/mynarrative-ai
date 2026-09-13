"""Brand registration handler — create new brand account."""
import hashlib
import json
import os
import secrets
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
            raw = resp.read().decode() or "null"
            return json.loads(raw)
    except Exception as e:
        print(f"⚠️ [sb_request] {e}")
        return None


def _generate_api_key() -> str:
    """Generate a new API key with prefix."""
    prefix = "mn_live_"
    random_part = secrets.token_hex(24)
    return prefix + random_part


def handle_register(body: dict) -> dict:
    """Register a new brand."""
    name = body.get("name", "").strip()
    domain = body.get("domain", "").strip()
    contact_email = body.get("contact_email", "").strip()
    contact_name = body.get("contact_name", "").strip()
    plan_tier = body.get("plan_tier", "starter")

    if not name or not domain or not contact_email:
        return {"error": "name, domain, and contact_email are required"}

    # Generate slug
    slug = name.lower().replace(" ", "-").replace(".", "")
    slug = "".join(c for c in slug if c.isalnum() or c == "-")

    # Check if slug exists
    existing = _sb_request("GET", f"/rest/v1/brands?slug=eq.{slug}&select=id")
    if existing and len(existing) > 0:
        slug = f"{slug}-{secrets.token_hex(3)}"

    # Create brand
    brand = _sb_request("POST", "/rest/v1/brands", {
        "name": name,
        "slug": slug,
        "domain": domain,
        "contact_email": contact_email,
        "contact_name": contact_name,
        "is_active": True
    })

    if not brand or len(brand) == 0:
        return {"error": "Failed to create brand"}

    brand_id = brand[0]["id"]

    # Create subscription (trialing)
    from datetime import datetime, timedelta
    trial_end = (datetime.utcnow() + timedelta(days=14)).isoformat() + "Z"

    plan_limits = {
        "starter": {"monthly_recommendations_limit": 1000, "max_products_in_catalog": 500},
        "growth": {"monthly_recommendations_limit": 10000, "max_products_in_catalog": 5000},
        "enterprise": {"monthly_recommendations_limit": 999999, "max_products_in_catalog": 999999}
    }
    limits = plan_limits.get(plan_tier, plan_limits["starter"])

    _sb_request("POST", "/rest/v1/brand_subscriptions", {
        "brand_id": brand_id,
        "plan_tier": plan_tier,
        "status": "trialing",
        "trial_end": trial_end,
        "current_period_end": trial_end,
        "monthly_recommendations_limit": limits["monthly_recommendations_limit"],
        "max_products_in_catalog": limits["max_products_in_catalog"]
    })

    # Generate API key
    api_key = _generate_api_key()
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    key_prefix = api_key[:12] + "..."

    _sb_request("POST", "/rest/v1/api_keys", {
        "brand_id": brand_id,
        "key_hash": key_hash,
        "key_prefix": key_prefix,
        "name": "Default",
        "is_active": True
    })

    # Create catalog
    _sb_request("POST", "/rest/v1/brand_catalogs", {
        "brand_id": brand_id,
        "name": "Main Catalog",
        "sync_status": "idle"
    })

    return {
        "brand_id": brand_id,
        "slug": slug,
        "api_key": api_key,
        "plan_tier": plan_tier,
        "trial_end": trial_end,
        "message": f"Brand '{name}' registered successfully! Your API key is ready."
    }
