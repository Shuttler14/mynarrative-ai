"""
Network Analytics — Tracks cross-brand performance for model improvement.
Full funnel: impression → vton_generated → click → cart → purchase → return
"""
from __future__ import annotations
import json
import os
from typing import Optional
from datetime import datetime, timedelta


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


def track_network_event(
    event_type: str,
    brand_id: str,
    user_id: str = "",
    product_id: str = "",
    session_id: str = "",
    host_brand_id: str = "",
    campaign_id: str = "",
    event_data: dict = None,
) -> dict:
    """
    Record a network event.

    Event types:
    - vton_impression: Product appeared in VTON result
    - product_click: User clicked on cross-brand product
    - add_to_cart: User added cross-brand product to cart
    - purchase: Cross-brand purchase completed
    - return: Product returned
    - campaign_impression: Sponsored product shown
    """
    event = {
        "event_type": event_type,
        "brand_id": brand_id or None,
        "user_id": user_id or None,
        "product_id": product_id or None,
        "session_id": session_id or None,
        "host_brand_id": host_brand_id or None,
        "campaign_id": campaign_id or None,
        "event_data": event_data or {},
    }

    result = _sb_request("POST", "/rest/v1/network_events", event)

    # Update campaign metrics if applicable
    if campaign_id and event_type in ("vton_impression", "product_click", "purchase"):
        _update_campaign_metrics(campaign_id, event_type)

    return {"recorded": True, "event_type": event_type}


def _update_campaign_metrics(campaign_id: str, event_type: str):
    """Increment campaign counters."""
    field_map = {
        "vton_impression": "vton_appearances",
        "product_click": "clicks",
        "purchase": "purchases",
    }
    field = field_map.get(event_type)
    if not field:
        return

    # Use RPC increment function
    _sb_request(
        "POST",
        f"/rest/v1/rpc/increment_campaign_{field}",
        {"p_campaign_id": campaign_id},
    )


def get_brand_network_report(brand_id: str, days: int = 30) -> dict:
    """
    Comprehensive network performance report for merchant dashboard.
    Shows both sides: your products on other sites + other products on your site.
    """
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat() + "Z"

    # ── Your products appearing on other brands' sites ────────────────
    as_supplier = _sb_request(
        "GET",
        f"/rest/v1/network_events?"
        f"brand_id=eq.{brand_id}&created_at=gte.{cutoff}&select=event_type,host_brand_id,created_at"
    )
    events_as_supplier = as_supplier if isinstance(as_supplier, list) else []

    impressions_as_supplier = sum(1 for e in events_as_supplier if e.get("event_type") == "vton_impression")
    clicks_as_supplier = sum(1 for e in events_as_supplier if e.get("event_type") == "product_click")
    purchases_as_supplier = sum(1 for e in events_as_supplier if e.get("event_type") == "purchase")

    # ── Other brands' products on your site ───────────────────────────
    as_host = _sb_request(
        "GET",
        f"/rest/v1/network_events?"
        f"host_brand_id=eq.{brand_id}&created_at=gte.{cutoff}&select=event_type,brand_id,created_at"
    )
    events_as_host = as_host if isinstance(as_host, list) else []

    impressions_as_host = sum(1 for e in events_as_host if e.get("event_type") == "vton_impression")
    clicks_as_host = sum(1 for e in events_as_host if e.get("event_type") == "product_click")
    purchases_as_host = sum(1 for e in events_as_host if e.get("event_type") == "purchase")

    # ── Revenue data ──────────────────────────────────────────────────
    supplier_tx = _sb_request(
        "GET",
        f"/rest/v1/cross_brand_transactions?"
        f"supplier_brand_id=eq.{brand_id}&created_at=gte.{cutoff}&select=supplier_cpa_amount,order_total"
    )
    host_tx = _sb_request(
        "GET",
        f"/rest/v1/cross_brand_transactions?"
        f"host_brand_id=eq.{brand_id}&created_at=gte.{cutoff}&select=host_commission_amount,order_total"
    )

    supplier_revenue = sum(float(tx.get("supplier_cpa_amount", 0)) for tx in (supplier_tx if isinstance(supplier_tx, list) else []))
    host_commission = sum(float(tx.get("host_commission_amount", 0)) for tx in (host_tx if isinstance(host_tx, list) else []))
    supplier_gmv = sum(float(tx.get("order_total", 0)) for tx in (supplier_tx if isinstance(supplier_tx, list) else []))
    host_gmv = sum(float(tx.get("order_total", 0)) for tx in (host_tx if isinstance(host_tx, list) else []))

    # ── Top performing categories ─────────────────────────────────────
    category_events = {}
    for e in events_as_supplier:
        if e.get("event_type") == "product_click":
            cat = e.get("event_data", {}).get("category", "unknown")
            category_events[cat] = category_events.get(cat, 0) + 1

    top_categories = sorted(category_events.items(), key=lambda x: x[1], reverse=True)[:5]

    # ── Top host websites ─────────────────────────────────────────────
    host_counts = {}
    for e in events_as_supplier:
        if e.get("event_type") == "product_click":
            hid = e.get("host_brand_id", "")
            host_counts[hid] = host_counts.get(hid, 0) + 1

    top_hosts = sorted(host_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "period_days": days,
        "as_supplier": {
            "impressions": impressions_as_supplier,
            "clicks": clicks_as_supplier,
            "purchases": purchases_as_supplier,
            "ctr": round((clicks_as_supplier / max(impressions_as_supplier, 1)) * 100, 2),
            "conversion_rate": round((purchases_as_supplier / max(clicks_as_supplier, 1)) * 100, 2),
            "attributed_gmv": round(supplier_gmv, 2),
            "revenue_earned": round(supplier_revenue, 2),
        },
        "as_host": {
            "impressions": impressions_as_host,
            "clicks": clicks_as_host,
            "purchases": purchases_as_host,
            "ctr": round((clicks_as_host / max(impressions_as_host, 1)) * 100, 2),
            "commission_earned": round(host_commission, 2),
            "cross_brand_gmv": round(host_gmv, 2),
        },
        "top_categories": [{"category": c, "clicks": n} for c, n in top_categories],
        "top_hosts": [{"brand_id": h, "clicks": n} for h, n in top_hosts],
        "summary": {
            "total_network_impressions": impressions_as_supplier + impressions_as_host,
            "total_network_clicks": clicks_as_supplier + clicks_as_host,
            "total_network_revenue": round(supplier_revenue + host_commission, 2),
        },
    }


def get_product_performance(product_id: str, days: int = 30) -> dict:
    """Get performance metrics for a specific product across the network."""
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat() + "Z"

    events = _sb_request(
        "GET",
        f"/rest/v1/network_events?"
        f"product_id=eq.{product_id}&created_at=gte.{cutoff}&select=event_type,host_brand_id,created_at"
    )
    event_list = events if isinstance(events, list) else []

    impressions = sum(1 for e in event_list if e.get("event_type") == "vton_impression")
    clicks = sum(1 for e in event_list if e.get("event_type") == "product_click")
    purchases = sum(1 for e in event_list if e.get("event_type") == "purchase")

    return {
        "product_id": product_id,
        "period_days": days,
        "impressions": impressions,
        "clicks": clicks,
        "purchases": purchases,
        "ctr": round((clicks / max(impressions, 1)) * 100, 2),
        "conversion_rate": round((purchases / max(clicks, 1)) * 100, 2),
    }
