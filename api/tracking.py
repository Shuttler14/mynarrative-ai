"""
My Narrative — Tracking Redirect & Merchant Pixel Receiver

Change ID: ADD-CHK-012-260922
Risk: HIGH — attribution backbone

Handles:
  - go.mynarrative.store/c/{click_id} → redirect to destination
  - /api/webhooks/merchant-pixel → receives Shopify Web Pixel events
  - /api/track/click → records click from widget (POST)
"""

import uuid
import hashlib
import os
import json
from datetime import datetime
from typing import Optional, Dict, Any

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api.core.supabase import sb_request
from api.attribution import (
    record_click,
    get_click,
    find_product_by_shopify,
    find_product_by_variant,
    record_attribution_event,
    _generate_event_id,
)


# ============================================
# 1. CLICK RECORDING (from widget)
# ============================================

def handle_click_record(body: dict, headers: dict) -> dict:
    """
    POST /api/track/click
    Called by MN widget when user clicks a product.
    Records click and returns tracking URL for redirect.
    """
    mn_product_id = body.get("mn_product_id")
    host_brand_id = body.get("host_brand_id")
    advertiser_brand_id = body.get("advertiser_brand_id")
    user_id = body.get("user_id")
    session_id = body.get("session_id")
    fingerprint = body.get("fingerprint")
    campaign_id = body.get("campaign_id")
    vton_session_id = body.get("vton_session_id")
    source = body.get("source", "widget")
    source_detail = body.get("source_detail")
    destination_url = body.get("destination_url")

    if not mn_product_id or not host_brand_id or not advertiser_brand_id:
        return {"error": "mn_product_id, host_brand_id, advertiser_brand_id required"}

    # Record the click
    result = record_click(
        mn_product_id=mn_product_id,
        host_brand_id=host_brand_id,
        advertiser_brand_id=advertiser_brand_id,
        user_id=user_id,
        session_id=session_id,
        fingerprint=fingerprint,
        campaign_id=campaign_id,
        vton_session_id=vton_session_id,
        source=source,
        source_detail=source_detail,
        referrer_url=headers.get("Referer", ""),
        destination_url=destination_url,
    )

    return result


# ============================================
# 2. TRACKING REDIRECT (go.mynarrative.store/c/{click_id})
# ============================================

def handle_tracking_redirect(click_id: str) -> dict:
    """
    GET /api/track/c/{click_id}
    Records attribution event, then returns destination URL for redirect.
    This runs server-side before the customer leaves MN.
    """
    click = get_click(click_id)

    if not click:
        return {"error": "click_not_found", "redirect": "https://mynarrative.store"}

    if click.get("attributed"):
        # Already attributed — still allow redirect but note it
        pass

    # Check if click has expired
    expires_at = click.get("expires_at")
    if expires_at:
        try:
            exp = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if exp < datetime.now(exp.tzinfo):
                return {"error": "click_expired", "redirect": click.get("destination_url", "https://mynarrative.store")}
        except (ValueError, TypeError):
            pass

    # Record attribution event (click → destination)
    record_attribution_event(
        click_id=click_id,
        mn_product_id=click["mn_product_id"],
        user_id=click.get("user_id"),
        session_id=click.get("session_id"),
        host_brand_id=click["host_brand_id"],
        advertiser_brand_id=click["advertiser_brand_id"],
        campaign_id=click.get("campaign_id"),
        event_type="click",
        event_data={
            "referrer": click.get("referrer_url"),
            "destination": click.get("destination_url"),
            "source": click.get("source"),
        },
    )

    # Return destination URL for redirect
    destination = click.get("destination_url", "https://mynarrative.store")
    return {"redirect": destination, "click_id": click_id}


# ============================================
# 3. MERCHANT PIXEL RECEIVER
# ============================================

def handle_merchant_pixel_event(body: dict) -> dict:
    """
    POST /api/webhooks/merchant-pixel
    Receives events from Shopify Web Pixel on merchant stores.
    
    Events:
      - product_viewed
      - product_added_to_cart
      - checkout_started
      - checkout_completed
    
    The pixel includes:
      - mn_click_id (stored in MN campaign UTM or localStorage)
      - shopify_customer_id
      - product/variant IDs
      - order data (for checkout_completed)
    """
    merchant_brand_id = body.get("merchant_brand_id")
    event_type = body.get("event_type")
    click_id = body.get("mn_click_id")
    user_id = body.get("user_id")
    session_id = body.get("session_id")
    product_data = body.get("product_data", {})
    order_data = body.get("order_data", {})

    if not merchant_brand_id or not event_type:
        return {"error": "merchant_brand_id and event_type required"}

    # Store pixel event
    event_id = str(uuid.uuid4())
    try:
        sb_request("POST", "narrative_pixel_events", {
            "id": event_id,
            "merchant_brand_id": merchant_brand_id,
            "click_id": click_id,
            "user_id": user_id,
            "session_id": session_id,
            "event_type": event_type,
            "product_data": product_data,
            "order_data": order_data,
            "created_at": datetime.utcnow().isoformat(),
        })
    except Exception as e:
        return {"error": str(e)}

    # Process checkout_completed → attribution
    if event_type == "checkout_completed" and click_id:
        _process_pixel_purchase(
            click_id=click_id,
            merchant_brand_id=merchant_brand_id,
            user_id=user_id,
            order_data=order_data,
            product_data=product_data,
        )

    return {"ok": True, "event_id": event_id}


def _process_pixel_purchase(
    click_id: str,
    merchant_brand_id: str,
    user_id: str,
    order_data: dict,
    product_data: dict,
):
    """Process a purchase event from the merchant pixel."""
    from api.attribution import attribute_purchase

    order_id = order_data.get("order_id") or order_data.get("id")
    if not order_id:
        return

    # Try to get user_id from click if not provided
    if not user_id:
        click = get_click(click_id)
        if click:
            user_id = click.get("user_id", "")

    if not user_id:
        return  # Can't attribute without user_id

    # Build order items from pixel data
    line_items = order_data.get("line_items", [])
    order_items = []
    for item in line_items:
        shopify_product_id = str(item.get("product_id", ""))
        shopify_variant_id = str(item.get("variant_id", ""))

        # Find MN Product ID
        product = find_product_by_shopify(shopify_product_id)
        if not product:
            product = find_product_by_variant(shopify_variant_id)

        mn_product_id = product["mn_product_id"] if product else None

        order_items.append({
            "mn_product_id": mn_product_id,
            "shopify_product_id": shopify_product_id,
            "shopify_variant_id": shopify_variant_id,
            "order_item_id": str(item.get("id", "")),
            "price": float(item.get("price", 0)),
            "quantity": int(item.get("quantity", 1)),
            "sku": item.get("sku"),
            "advertiser_brand_id": merchant_brand_id,
        })

    if order_items:
        attribute_purchase(
            user_id=user_id,
            order_id=str(order_id),
            order_items=order_items,
            source="pixel",
        )


# ============================================
# 4. SHOPIFY APP PROXY (for merchant stores)
# ============================================

def handle_shopify_app_proxy(query: dict, headers: dict) -> dict:
    """
    Handles requests from Shopify App Proxy.
    Merchant stores call this to get MN tracking info.
    
    Returns:
      - mn_click_id (if any)
      - product mapping (MN Product IDs)
      - campaign info
    """
    shopify_product_id = query.get("shopify_product_id")
    shopify_variant_id = query.get("shopify_variant_id")

    result = {"ok": True}

    if shopify_product_id:
        product = find_product_by_shopify(shopify_product_id)
        if product:
            result["mn_product_id"] = product["mn_product_id"]
            result["product_name"] = product.get("product_name")
            result["canonical_url"] = product.get("canonical_url")

    if shopify_variant_id and "mn_product_id" not in result:
        product = find_product_by_variant(shopify_variant_id)
        if product:
            result["mn_product_id"] = product["mn_product_id"]
            result["product_name"] = product.get("product_name")
            result["canonical_url"] = product.get("canonical_url")

    return result


# ============================================
# 5. PRODUCT REGISTRATION (batch)
# ============================================

def handle_product_registration(body: dict) -> dict:
    """
    POST /api/products/register
    Register products with permanent MN Product IDs.
    Called during brand onboarding or catalog sync.
    """
    from api.attribution import register_product

    brand_id = body.get("brand_id")
    products = body.get("products", [])

    if not brand_id or not products:
        return {"error": "brand_id and products required"}

    results = []
    for product in products:
        result = register_product(
            brand_id=brand_id,
            product_name=product.get("name", ""),
            shopify_product_id=product.get("shopify_product_id"),
            shopify_variant_ids=product.get("shopify_variant_ids", []),
            external_id=product.get("external_id"),
            canonical_url=product.get("canonical_url"),
            product_data=product.get("product_data", {}),
        )
        results.append(result)

    return {
        "registered": len([r for r in results if "mn_product_id" in r]),
        "errors": len([r for r in results if "error" in r]),
        "results": results,
    }
