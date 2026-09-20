"""
Sponsored Campaign Management — API handlers for campaign CRUD and performance tracking.
"""
from __future__ import annotations
import json
import os
from typing import Optional


def _sb_request(method: str, path: str, payload: dict = None) -> Optional[list | dict]:
    """Raw Supabase REST request."""
    import requests as _requests
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY", "")
    if not url or not key:
        return None
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    full_url = f"{url.rstrip('/')}{path}"
    try:
        if method == "GET":
            resp = _requests.get(full_url, headers=headers, timeout=15)
        elif method == "POST":
            resp = _requests.post(full_url, json=payload, headers=headers, timeout=15)
        elif method == "PATCH":
            resp = _requests.patch(full_url, json=payload, headers=headers, timeout=15)
        else:
            resp = _requests.request(method, full_url, json=payload, headers=headers, timeout=15)
        return resp.json() if resp.text else None
    except Exception:
        return None


# ── Campaign Pricing Tiers ─────────────────────────────────────────────────

CAMPAIGN_TIERS = {
    "starter": {
        "name": "Starter",
        "min_budget": 10000,
        "max_boost": 0.05,
        "max_categories": 3,
        "description": "Get started with cross-brand promotion",
    },
    "growth": {
        "name": "Growth",
        "min_budget": 50000,
        "max_boost": 0.10,
        "max_categories": 5,
        "description": "Scale your product visibility across the network",
    },
    "enterprise": {
        "name": "Enterprise",
        "min_budget": 200000,
        "max_boost": 0.15,
        "max_categories": "all",
        "description": "Maximum exposure across the entire network",
    },
}


def handle_create_campaign(body: dict, brand_id: str) -> dict:
    """
    Create a new sponsored campaign.

    Expected body:
    {
        "name": "Summer Collection Push",
        "budget": 50000,
        "target_brand_ids": ["uuid1", "uuid2"],  // optional: specific hosts
        "target_categories": ["tops", "bottoms"],
        "target_occasions": ["casual", "brunch"],
        "target_price_min": 1500,
        "target_price_max": 5000,
        "objective": "vton_impressions",  // or "clicks" or "purchases"
    }
    """
    name = body.get("name", "")
    budget = float(body.get("budget", 0))

    if not name:
        return {"error": "Campaign name required"}
    if budget < 1000:
        return {"error": "Minimum budget is ₹1,000"}

    # Determine tier and max boost
    tier = "starter"
    max_boost = 0.05
    for tier_name, config in CAMPAIGN_TIERS.items():
        if budget >= config["min_budget"]:
            tier = tier_name
            max_boost = config["max_boost"]

    campaign = {
        "brand_id": brand_id,
        "name": name,
        "budget": budget,
        "target_brand_ids": body.get("target_brand_ids", []),
        "target_categories": body.get("target_categories", []),
        "target_occasions": body.get("target_occasions", []),
        "target_price_min": float(body.get("target_price_min", 0)),
        "target_price_max": float(body.get("target_price_max", 999999)),
        "objective": body.get("objective", "vton_impressions"),
        "boost_pct": max_boost,
        "status": "active",
    }

    result = _sb_request("POST", "/rest/v1/sponsored_campaigns", campaign)

    # Supabase returns the created record(s) directly
    if result:
        if isinstance(result, list) and len(result) > 0:
            created = result[0]
        elif isinstance(result, dict):
            created = result
        else:
            created = None
        if created and created.get("id"):
            return {
                "success": True,
                "campaign_id": created["id"],
                "tier": tier,
                "boost_pct": max_boost,
                "budget": budget,
                "status": "active",
            }

    return {"error": "Failed to create campaign"}


def handle_list_campaigns(brand_id: str) -> dict:
    """List all campaigns for a brand."""
    result = _sb_request(
        "GET",
        f"/rest/v1/sponsored_campaigns?brand_id=eq.{brand_id}&select=*&order=created_at.desc"
    )

    campaigns = result if isinstance(result, list) else []

    return {
        "campaigns": campaigns,
        "total": len(campaigns),
        "active": sum(1 for c in campaigns if c.get("status") == "active"),
        "total_budget": sum(float(c.get("budget", 0)) for c in campaigns),
        "total_spent": sum(float(c.get("spent", 0)) for c in campaigns),
    }


def handle_campaign_performance(campaign_id: str) -> dict:
    """Get detailed performance metrics for a campaign."""
    result = _sb_request(
        "GET",
        f"/rest/v1/sponsored_campaigns?id=eq.{campaign_id}&select=*"
    )

    if not result or not isinstance(result, list) or len(result) == 0:
        return {"error": "Campaign not found"}

    campaign = result[0]

    impressions = int(campaign.get("impressions", 0))
    clicks = int(campaign.get("clicks", 0))
    purchases = int(campaign.get("purchases", 0))
    spent = float(campaign.get("spent", 0))
    budget = float(campaign.get("budget", 0))
    attributed_gmv = float(campaign.get("attributed_gmv", 0))

    ctr = (clicks / impressions * 100) if impressions > 0 else 0
    conversion_rate = (purchases / clicks * 100) if clicks > 0 else 0
    roas = (attributed_gmv / spent) if spent > 0 else 0
    cpa = (spent / purchases) if purchases > 0 else 0

    return {
        "campaign_id": campaign_id,
        "name": campaign.get("name", ""),
        "status": campaign.get("status", ""),
        "budget": budget,
        "spent": spent,
        "remaining": budget - spent,
        "boost_pct": campaign.get("boost_pct", 0),
        "metrics": {
            "impressions": impressions,
            "vton_appearances": int(campaign.get("vton_appearances", 0)),
            "clicks": clicks,
            "purchases": purchases,
            "ctr": round(ctr, 2),
            "conversion_rate": round(conversion_rate, 2),
            "attributed_gmv": attributed_gmv,
            "roas": round(roas, 2),
            "cpa": round(cpa, 2),
        },
    }


def handle_update_campaign(campaign_id: str, body: dict, brand_id: str) -> dict:
    """Update campaign settings (budget, targets, status)."""
    # Verify ownership
    existing = _sb_request(
        "GET",
        f"/rest/v1/sponsored_campaigns?id=eq.{campaign_id}&brand_id=eq.{brand_id}&select=id"
    )
    if not existing or not isinstance(existing, list) or len(existing) == 0:
        return {"error": "Campaign not found or access denied"}

    updates = {}
    allowed_fields = [
        "name", "budget", "target_brand_ids", "target_categories",
        "target_occasions", "target_price_min", "target_price_max",
        "objective", "status",
    ]
    for field in allowed_fields:
        if field in body:
            updates[field] = body[field]

    if not updates:
        return {"error": "No valid fields to update"}

    # Recalculate boost if budget changed
    if "budget" in updates:
        budget = float(updates["budget"])
        for tier_name, config in CAMPAIGN_TIERS.items():
            if budget >= config["min_budget"]:
                updates["boost_pct"] = config["max_boost"]

    result = _sb_request(
        "PATCH",
        f"/rest/v1/sponsored_campaigns?id=eq.{campaign_id}",
        updates,
    )

    return {"success": True, "updated_fields": list(updates.keys())}


def handle_pause_campaign(campaign_id: str, brand_id: str) -> dict:
    """Pause an active campaign."""
    return handle_update_campaign(campaign_id, {"status": "paused"}, brand_id)


def handle_resume_campaign(campaign_id: str, brand_id: str) -> dict:
    """Resume a paused campaign."""
    return handle_update_campaign(campaign_id, {"status": "active"}, brand_id)


def handle_delete_campaign(campaign_id: str, brand_id: str) -> dict:
    """Delete a campaign (only if not yet spent)."""
    existing = _sb_request(
        "GET",
        f"/rest/v1/sponsored_campaigns?id=eq.{campaign_id}&brand_id=eq.{brand_id}&select=id,spent"
    )
    if not existing or not isinstance(existing, list) or len(existing) == 0:
        return {"error": "Campaign not found or access denied"}

    if float(existing[0].get("spent", 0)) > 0:
        return {"error": "Cannot delete campaign with existing spend. Pause it instead."}

    _sb_request("DELETE", f"/rest/v1/sponsored_campaigns?id=eq.{campaign_id}")
    return {"success": True}


def handle_pricing_tiers() -> dict:
    """Get available campaign pricing tiers."""
    return {
        "tiers": CAMPAIGN_TIERS,
        "pricing_models": [
            {
                "name": "CPM",
                "description": "Pay per 1000 VTON impressions",
                "best_for": "Brand awareness",
            },
            {
                "name": "CPC",
                "description": "Pay per product click",
                "best_for": "Traffic generation",
            },
            {
                "name": "CPA",
                "description": "Pay per purchase",
                "best_for": "Direct ROI",
            },
        ],
        "currency": "INR",
    }
