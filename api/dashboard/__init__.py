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


def handle_dashboard_overview(brand_id: str) -> dict:
    """Return dashboard overview: stats, recent activity, network status."""
    try:
        # Get brand info
        brand = sb_request("GET", f"/rest/v1/brands?id=eq.{brand_id}&select=name,widget_config,network_mode", single=True)

        # Get product count
        products = sb_request("GET", f"/rest/v1/brand_products?brand_id=eq.{brand_id}&select=id", limit=1000)
        product_count = len(products) if isinstance(products, list) else 0

        # Get campaign stats
        campaigns = sb_request("GET", f"/rest/v1/sponsored_campaigns?brand_id=eq.{brand_id}&select=id,status,budget_spent,impressions,clicks,conversions",
                              limit=100)
        if not isinstance(campaigns, list):
            campaigns = []

        active_campaigns = [c for c in campaigns if c.get("status") == "active"]
        total_spent = sum(float(c.get("budget_spent", 0) or 0) for c in campaigns)
        total_impressions = sum(int(c.get("impressions", 0) or 0) for c in campaigns)
        total_clicks = sum(int(c.get("clicks", 0) or 0) for c in campaigns)
        total_conversions = sum(int(c.get("conversions", 0) or 0) for c in campaigns)

        # Get network events (last 30 days)
        thirty_days_ago = (datetime.utcnow() - timedelta(days=30)).isoformat()
        events = sb_request("GET",
            f"/rest/v1/network_events?host_brand_id=eq.{brand_id}&created_at=gt.{thirty_days_ago}&select=event_type,created_at",
            limit=100)
        if not isinstance(events, list):
            events = []

        # Get network settings
        settings = sb_request("GET", f"/rest/v1/host_preferences?brand_id=eq.{brand_id}&select=*",
                             single=True)
        if not isinstance(settings, dict):
            settings = {}

        # Calculate trends (mock for now — would compare to previous period)
        ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
        conversion_rate = (total_conversions / total_clicks * 100) if total_clicks > 0 else 0

        # Recent activity
        activity = []
        for evt in events[:10]:
            activity.append({
                "type": evt.get("event_type", "unknown"),
                "date": evt.get("created_at", ""),
                "description": _event_description(evt.get("event_type", "")),
            })

        return {
            "success": True,
            "brand_name": brand.get("name", "Brand") if isinstance(brand, dict) else "Brand",
            "stats": {
                "vton_sessions": total_impressions,
                "cross_brand_impressions": total_impressions,
                "clicks": total_clicks,
                "conversions": total_conversions,
                "revenue": round(total_spent * 2.5, 2),  # Mock revenue
                "ctr": round(ctr, 1),
                "conversion_rate": round(conversion_rate, 1),
                "active_campaigns": len(active_campaigns),
                "total_products": product_count,
            },
            "network_status": {
                "vton_enabled": settings.get("vton_enabled", True),
                "receive_recommendations": settings.get("receive_recommendations", True),
                "distribute_products": settings.get("distribute_products", False),
                "promote_products": settings.get("promote_products", False),
            },
            "activity": activity,
            "campaigns": [{
                "id": c.get("id"),
                "name": c.get("name", "Campaign"),
                "status": c.get("status"),
                "spent": c.get("budget_spent", 0),
                "impressions": c.get("impressions", 0),
                "clicks": c.get("clicks", 0),
            } for c in active_campaigns[:5]],
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_dashboard_products(brand_id: str) -> dict:
    """Return brand's products for the dashboard."""
    try:
        products = sb_request("GET",
            f"/rest/v1/brand_products?brand_id=eq.{brand_id}&select=*&order=created_at.desc",
            limit=200)
        if not isinstance(products, list):
            products = []

        return {
            "success": True,
            "products": [{
                "id": p.get("id"),
                "title": p.get("title", ""),
                "price": p.get("price", 0),
                "category": p.get("category", ""),
                "image_url": p.get("image_url", ""),
                "product_url": p.get("product_url", ""),
                "eligible": p.get("eligible", True),
                "stock": p.get("stock", "in_stock"),
                "created_at": p.get("created_at", ""),
            } for p in products],
            "total": len(products),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_dashboard_network_settings(brand_id: str, update: dict = None) -> dict:
    """Get or update network settings for the brand."""
    try:
        if update:
            # Update settings
            existing = sb_request("GET", f"/rest/v1/host_preferences?brand_id=eq.{brand_id}&select=id", single=True)
            if isinstance(existing, dict) and existing.get("id"):
                sb_request("PATCH", f"/rest/v1/host_preferences?brand_id=eq.{brand_id}", update)
            else:
                update["brand_id"] = brand_id
                sb_request("POST", "/rest/v1/host_preferences", update)
            return {"success": True, "message": "Settings updated"}

        # Get settings
        settings = sb_request("GET",
            f"/rest/v1/host_preferences?brand_id=eq.{brand_id}&select=*",
            single=True)
        if not isinstance(settings, dict):
            settings = {}

        # Get category rules
        rules = sb_request("GET",
            f"/rest/v1/host_category_rules?host_brand_id=eq.{brand_id}&select=*",
            limit=50)
        if not isinstance(rules, list):
            rules = []

        # Get exclusions
        exclusions = sb_request("GET",
            f"/rest/v1/brand_exclusions?host_brand_id=eq.{brand_id}&select=*",
            limit=50)
        if not isinstance(exclusions, list):
            exclusions = []

        return {
            "success": True,
            "vton_enabled": settings.get("vton_enabled", True),
            "receive_recommendations": settings.get("receive_recommendations", True),
            "distribute_products": settings.get("distribute_products", False),
            "promote_products": settings.get("promote_products", False),
            "promotion_budget": settings.get("promotion_budget", 0),
            "max_cpc_bid": settings.get("max_cpc_bid", 0),
            "cross_brand_density": settings.get("cross_brand_density", 0.3),
            "category_rules": rules,
            "competitor_exclusions": exclusions,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_dashboard_analytics(brand_id: str, days: int = 30) -> dict:
    """Return analytics data for charts."""
    try:
        start_date = (datetime.utcnow() - timedelta(days=days)).isoformat()

        # Get network events grouped by day
        events = sb_request("GET",
            f"/rest/v1/network_events?host_brand_id=eq.{brand_id}&created_at=gt.{start_date}"
            f"&select=event_type,created_at,product_id",
            limit=1000)
        if not isinstance(events, list):
            events = []

        # Aggregate by day
        daily_data = {}
        for evt in events:
            day = evt.get("created_at", "")[:10]
            if day not in daily_data:
                daily_data[day] = {"impressions": 0, "clicks": 0, "conversions": 0, "revenue": 0}
            evt_type = evt.get("event_type", "")
            if evt_type in ("impression", "view"):
                daily_data[day]["impressions"] += 1
            elif evt_type in ("click", "interaction"):
                daily_data[day]["clicks"] += 1
            elif evt_type in ("purchase", "conversion"):
                daily_data[day]["conversions"] += 1
                daily_data[day]["revenue"] += 500  # Mock revenue per conversion

        # Fill missing days
        dates = []
        for i in range(days):
            d = (datetime.utcnow() - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
            dates.append(d)
            if d not in daily_data:
                daily_data[d] = {"impressions": 0, "clicks": 0, "conversions": 0, "revenue": 0}

        # Build chart data
        labels = dates
        impressions = [daily_data[d]["impressions"] for d in dates]
        clicks = [daily_data[d]["clicks"] for d in dates]
        conversions = [daily_data[d]["conversions"] for d in dates]
        revenue = [daily_data[d]["revenue"] for d in dates]

        # Revenue by category (mock)
        categories = {"Tops": 35, "Bottoms": 25, "Footwear": 20, "Accessories": 15, "Outerwear": 5}

        # Top products (mock)
        top_products = [
            {"name": "Product A", "impressions": 1200, "clicks": 89, "conversions": 12},
            {"name": "Product B", "impressions": 980, "clicks": 67, "conversions": 8},
            {"name": "Product C", "impressions": 750, "clicks": 45, "conversions": 5},
        ]

        total_impressions = sum(impressions)
        total_clicks = sum(clicks)
        total_conversions = sum(conversions)
        total_revenue = sum(revenue)

        return {
            "success": True,
            "period_days": days,
            "charts": {
                "line": {
                    "labels": labels,
                    "impressions": impressions,
                    "clicks": clicks,
                    "conversions": conversions,
                    "revenue": revenue,
                },
                "doughnut": {
                    "labels": list(categories.keys()),
                    "values": list(categories.values()),
                },
                "bar": {
                    "labels": [p["name"] for p in top_products],
                    "impressions": [p["impressions"] for p in top_products],
                    "clicks": [p["clicks"] for p in top_products],
                },
            },
            "metrics": {
                "outfit_completion_rate": 38.2,
                "cross_brand_conversion": round((total_conversions / total_clicks * 100) if total_clicks > 0 else 0, 1),
                "vton_interaction_rate": 24.5,
                "avg_order_value": round((total_revenue / total_conversions) if total_conversions > 0 else 0, 0),
                "total_impressions": total_impressions,
                "total_clicks": total_clicks,
                "total_conversions": total_conversions,
                "total_revenue": total_revenue,
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_dashboard_wallet(brand_id: str) -> dict:
    """Return wallet balance and transaction history."""
    try:
        # Get wallet/balance from brand record
        brand = sb_request("GET",
            f"/rest/v1/brands?id=eq.{brand_id}&select=wallet_balance",
            single=True)
        balance = 0
        if isinstance(brand, dict):
            balance = float(brand.get("wallet_balance", 0) or 0)

        # Get transactions
        transactions = sb_request("GET",
            f"/rest/v1/wallet_transactions?brand_id=eq.{brand_id}&select=*&order=created_at.desc",
            limit=50)
        if not isinstance(transactions, list):
            transactions = []

        return {
            "success": True,
            "balance": balance,
            "currency": "INR",
            "transactions": [{
                "id": t.get("id"),
                "date": t.get("created_at", ""),
                "description": t.get("description", ""),
                "amount": t.get("amount", 0),
                "type": t.get("type", "debit"),
                "balance_after": t.get("balance_after", 0),
            } for t in transactions],
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def _event_description(event_type: str) -> str:
    """Human-readable event description."""
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
