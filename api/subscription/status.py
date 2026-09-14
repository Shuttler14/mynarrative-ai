"""Subscription status handler."""
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


def handle_subscription_status(brand_id: str) -> dict:
    """Get current subscription status for a brand."""
    if not brand_id:
        return {"status": "unknown"}

    result = _sb_request("GET", f"/rest/v1/brand_subscriptions?brand_id=eq.{brand_id}&select=status,plan_tier,current_period_end,monthly_recommendations_used,monthly_recommendations_limit")
    if not result or len(result) == 0:
        return {"status": "no_subscription"}

    sub = result[0]

    # Check if period has ended
    from datetime import datetime
    period_end = sub.get("current_period_end")
    if period_end:
        try:
            end_dt = datetime.fromisoformat(period_end.replace("Z", "+00:00"))
            if end_dt < datetime.now(end_dt.tzinfo) and sub["status"] == "active":
                # Period ended, check if we need to update status
                pass
        except Exception:
            pass

    # Get brand slug
    brand_result = _sb_request("GET", f"/rest/v1/brands?id=eq.{brand_id}&select=slug")
    slug = brand_result[0]["slug"] if brand_result and len(brand_result) > 0 else ""

    return {
        "status": sub.get("status", "unknown"),
        "plan_tier": sub.get("plan_tier", "starter"),
        "current_period_end": sub.get("current_period_end"),
        "recommendations_used": sub.get("monthly_recommendations_used", 0),
        "recommendations_limit": sub.get("monthly_recommendations_limit", 1000),
        "slug": slug
    }
