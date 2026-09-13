"""Subscription status handler."""
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
