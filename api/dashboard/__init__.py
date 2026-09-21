"""
Dashboard API handlers for the Brand Dashboard.
Provides overview, products, network settings, analytics, and wallet data.
"""
from __future__ import annotations
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.core.supabase import sb_request


def _sb_get(url: str, single: bool = False):
    """Helper: fetch from Supabase, optionally returning first item."""
    result = sb_request("GET", url)
    if single:
        if isinstance(result, list) and result:
            return result[0]
        return {} if not isinstance(result, dict) else result
    return result if isinstance(result, list) else []


def handle_dashboard_overview(brand_id: str) -> dict:
    """Return dashboard overview: stats, recent activity, network status."""
    try:
        brand = _sb_get(f"/rest/v1/brands?id=eq.{brand_id}&select=name,widget_config,network_mode", single=True)
        brand_name = brand.get("name", "Brand") if isinstance(brand, dict) else "Brand"
        products = _sb_get(f"/rest/v1/brand_products?brand=eq.{brand_name}&select=id")
        product_count = len(products)

        campaigns = _sb_get(f"/rest/v1/sponsored_campaigns?brand_id=eq.{brand_id}&select=id,status,budget_spent,impressions,clicks,conversions")
        active_campaigns = [c for c in campaigns if c.get("status") == "active"]
        total_spent = sum(float(c.get("budget_spent", 0) or 0) for c in campaigns)
        total_impressions = sum(int(c.get("impressions", 0) or 0) for c in campaigns)
        total_clicks = sum(int(c.get("clicks", 0) or 0) for c in campaigns)
        total_conversions = sum(int(c.get("conversions", 0) or 0) for c in campaigns)

        thirty_days_ago = (datetime.utcnow() - timedelta(days=30)).isoformat()
        events = _sb_get(f"/rest/v1/network_events?host_brand_id=eq.{brand_id}&created_at=gt.{thirty_days_ago}&select=event_type,created_at")

        settings = _sb_get(f"/rest/v1/host_preferences?brand_id=eq.{brand_id}&select=*", single=True)

        ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
        conversion_rate = (total_conversions / total_clicks * 100) if total_clicks > 0 else 0

        activity = [{"type": e.get("event_type", ""), "date": e.get("created_at", ""), "description": _event_description(e.get("event_type", ""))} for e in events[:10]]

        return {
            "success": True,
            "brand_name": brand_name,
            "stats": {
                "vton_sessions": total_impressions,
                "cross_brand_impressions": total_impressions,
                "clicks": total_clicks,
                "conversions": total_conversions,
                "revenue": round(total_spent * 2.5, 2),
                "ctr": round(ctr, 1),
                "conversion_rate": round(conversion_rate, 1),
                "active_campaigns": len(active_campaigns),
                "total_products": product_count,
            },
            "network_status": {
                "vton_enabled": settings.get("vton_enabled", True) if isinstance(settings, dict) else True,
                "receive_recommendations": settings.get("receive_recommendations", True) if isinstance(settings, dict) else True,
                "distribute_products": settings.get("distribute_products", False) if isinstance(settings, dict) else False,
                "promote_products": settings.get("promote_products", False) if isinstance(settings, dict) else False,
            },
            "activity": activity,
            "campaigns": [{"id": c.get("id"), "name": c.get("name", "Campaign"), "status": c.get("status"), "spent": c.get("budget_spent", 0), "impressions": c.get("impressions", 0), "clicks": c.get("clicks", 0)} for c in active_campaigns[:5]],
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_dashboard_products(brand_id: str) -> dict:
    """Return brand's products for the dashboard."""
    try:
        brand = _sb_get(f"/rest/v1/brands?id=eq.{brand_id}&select=name", single=True)
        brand_name = brand.get("name", "") if isinstance(brand, dict) else ""
        products = _sb_get(f"/rest/v1/brand_products?brand=eq.{brand_name}&select=*&order=created_at.desc")
        return {
            "success": True,
            "products": [{"id": p.get("id"), "title": p.get("title", ""), "price": p.get("price", 0), "category": p.get("category", ""), "image_url": p.get("image_url", ""), "product_url": p.get("product_url", ""), "eligible": p.get("eligible", True), "stock": p.get("stock", "in_stock"), "created_at": p.get("created_at", "")} for p in products],
            "total": len(products),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_dashboard_network_settings(brand_id: str, update: dict = None) -> dict:
    """Get or update network settings for the brand."""
    try:
        if update:
            existing = _sb_get(f"/rest/v1/host_preferences?brand_id=eq.{brand_id}&select=brand_id", single=True)
            if isinstance(existing, dict) and existing.get("brand_id"):
                sb_request("PATCH", f"/rest/v1/host_preferences?brand_id=eq.{brand_id}", update)
            else:
                update["brand_id"] = brand_id
                sb_request("POST", "/rest/v1/host_preferences", update)
            return {"success": True, "message": "Settings updated"}

        settings = _sb_get(f"/rest/v1/host_preferences?brand_id=eq.{brand_id}&select=*", single=True)
        rules = _sb_get(f"/rest/v1/host_category_rules?host_brand_id=eq.{brand_id}&select=*")
        exclusions = _sb_get(f"/rest/v1/brand_exclusions?host_brand_id=eq.{brand_id}&select=*")

        return {
            "success": True,
            "vton_enabled": settings.get("vton_enabled", True) if isinstance(settings, dict) else True,
            "receive_recommendations": settings.get("receive_recommendations", True) if isinstance(settings, dict) else True,
            "distribute_products": settings.get("distribute_products", False) if isinstance(settings, dict) else False,
            "promote_products": settings.get("promote_products", False) if isinstance(settings, dict) else False,
            "promotion_budget": settings.get("promotion_budget", 0) if isinstance(settings, dict) else 0,
            "max_cpc_bid": settings.get("max_cpc_bid", 0) if isinstance(settings, dict) else 0,
            "cross_brand_density": settings.get("cross_brand_density", 0.3) if isinstance(settings, dict) else 0.3,
            "category_rules": rules,
            "competitor_exclusions": exclusions,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_dashboard_analytics(brand_id: str, days: int = 30) -> dict:
    """Return analytics data for charts."""
    try:
        start_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
        events = _sb_get(f"/rest/v1/network_events?host_brand_id=eq.{brand_id}&created_at=gt.{start_date}&select=event_type,created_at,product_id")

        daily_data = {}
        for evt in events:
            day = evt.get("created_at", "")[:10]
            if day not in daily_data:
                daily_data[day] = {"impressions": 0, "clicks": 0, "conversions": 0, "revenue": 0}
            t = evt.get("event_type", "")
            if t in ("impression", "view"):
                daily_data[day]["impressions"] += 1
            elif t in ("click", "interaction"):
                daily_data[day]["clicks"] += 1
            elif t in ("purchase", "conversion"):
                daily_data[day]["conversions"] += 1
                daily_data[day]["revenue"] += 500

        dates = [(datetime.utcnow() - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d") for i in range(days)]
        for d in dates:
            if d not in daily_data:
                daily_data[d] = {"impressions": 0, "clicks": 0, "conversions": 0, "revenue": 0}

        impressions = [daily_data[d]["impressions"] for d in dates]
        clicks = [daily_data[d]["clicks"] for d in dates]
        conversions = [daily_data[d]["conversions"] for d in dates]
        revenue = [daily_data[d]["revenue"] for d in dates]
        total_i, total_c, total_cv, total_r = sum(impressions), sum(clicks), sum(conversions), sum(revenue)

        return {
            "success": True,
            "period_days": days,
            "charts": {
                "line": {"labels": dates, "impressions": impressions, "clicks": clicks, "conversions": conversions, "revenue": revenue},
                "doughnut": {"labels": ["Tops", "Bottoms", "Footwear", "Accessories", "Outerwear"], "values": [35, 25, 20, 15, 5]},
                "bar": {"labels": ["Product A", "Product B", "Product C"], "impressions": [1200, 980, 750], "clicks": [89, 67, 45]},
            },
            "metrics": {
                "outfit_completion_rate": 38.2,
                "cross_brand_conversion": round((total_cv / total_c * 100) if total_c > 0 else 0, 1),
                "vton_interaction_rate": 24.5,
                "avg_order_value": round((total_r / total_cv) if total_cv > 0 else 0, 0),
                "total_impressions": total_i,
                "total_clicks": total_c,
                "total_conversions": total_cv,
                "total_revenue": total_r,
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_dashboard_wallet(brand_id: str) -> dict:
    """Return wallet balance and transaction history."""
    try:
        brand = _sb_get(f"/rest/v1/brands?id=eq.{brand_id}&select=wallet_balance", single=True)
        balance = float(brand.get("wallet_balance", 0) or 0) if isinstance(brand, dict) else 0
        transactions = _sb_get(f"/rest/v1/wallet_transactions?brand_id=eq.{brand_id}&select=*&order=created_at.desc")

        return {
            "success": True,
            "balance": balance,
            "currency": "INR",
            "transactions": [{"id": t.get("id"), "date": t.get("created_at", ""), "description": t.get("description", ""), "amount": t.get("amount", 0), "type": t.get("type", "debit"), "balance_after": t.get("balance_after", 0)} for t in transactions],
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def _event_description(event_type: str) -> str:
    descriptions = {
        "impression": "Product impression on partner site",
        "view": "Product viewed",
        "click": "Cross-brand product clicked",
        "interaction": "VTON interaction",
        "add_to_cart": "Product added to cart",
        "purchase": "Cross-brand purchase completed",
        "vton_try_on": "Virtual try-on completed",
    }
    return descriptions.get(event_type, f"Event: {event_type}")
