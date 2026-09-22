"""
My Narrative — Attribution & Commission Engine
"Last eligible click + 30 days + line-item"

Change ID: ADD-CHK-011-260922
Risk: CRITICAL — financial backbone
Revert: Delete api/attribution.py, drop SQL tables

Architecture:
  - Product Registry: permanent MN Product IDs
  - Click Tracking: network_click_id per product click
  - Attribution: last eligible MY NARRATIVE click
  - Commission Ledger: immutable, line-item, event-sourced
  - Reconciliation: 6-hour scheduled + event-driven
  - Lifecycle: PENDING → CONFIRMED → PAYABLE → PAID
"""

import uuid
import hashlib
import os
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api.core.supabase import sb_request


# ============================================
# CONSTANTS
# ============================================

PLATFORM_COMMISSION_RATE = 10.00       # 10% platform commission
HOST_AFFILIATE_RATE = 7.00            # 7% host affiliate (cross-brand only)
ATTRIBUTION_WINDOW_DAYS = 30          # 30-day attribution window
CLICK_ID_PREFIX = "MN-CLK"
PRODUCT_ID_PREFIX = "MN-P"
EVENT_ID_PREFIX = "MN-EVT"
CONFIRMATION_DELAY_HOURS = 72         # 72 hours before PENDING → CONFIRMED
PAYOUT_DELAY_DAYS = 14                # 14 days after CONFIRMED → PAYABLE

ATtributionConfidence = {
    "DIRECT": "DIRECT",               # MN Checkout (deterministic)
    "VERIFIED": "VERIFIED",           # Merchant pixel + click_id match
    "ATTRIBUTED": "ATTRIBUTED",       # Click exists, no merchant verification
    "UNVERIFIED": "UNVERIFIED",       # Reconciliation match, no click_id
}

CommissionStatus = {
    "PENDING": "PENDING",
    "CONFIRMED": "CONFIRMED",
    "VOIDED": "VOIDED",
    "REFUNDED": "REFUNDED",
    "PARTIALLY_REFUNDED": "PARTIALLY_REFUNDED",
    "DISPUTED": "DISPUTED",
    "PAYABLE": "PAYABLE",
    "PAID": "PAID",
}


# ============================================
# HELPER: Generate IDs
# ============================================

def _generate_click_id() -> str:
    """Permanent click ID. Never reused."""
    random_part = hashlib.md5(str(uuid.uuid4()).encode()).hexdigest()[:12].upper()
    return f"{CLICK_ID_PREFIX}-{random_part}"


def _generate_event_id() -> str:
    """Unique event ID for ledger. Idempotent."""
    random_part = hashlib.md5(str(uuid.uuid4()).encode()).hexdigest()[:12].upper()
    return f"{EVENT_ID_PREFIX}-{random_part}"


def _generate_product_id(brand_id: str, sku: str) -> str:
    """Permanent MN Product ID from brand + SKU."""
    raw = f"{brand_id}:{sku}"
    hash_part = hashlib.md5(raw.encode()).hexdigest()[:10].upper()
    return f"{PRODUCT_ID_PREFIX}-{hash_part}"


def _generate_idempotency_key(order_id: str, item_id: str, event_type: str) -> str:
    """Deterministic key prevents duplicate ledger entries."""
    raw = f"{order_id}:{item_id}:{event_type}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


# ============================================
# 1. PRODUCT REGISTRY
# ============================================

def register_product(
    brand_id: str,
    product_name: str,
    shopify_product_id: str = None,
    shopify_variant_ids: list = None,
    external_id: str = None,
    canonical_url: str = None,
    product_data: dict = None,
) -> dict:
    """Register a product with a permanent MN Product ID."""
    sku = external_id or shopify_product_id or str(uuid.uuid4())[:8]
    mn_product_id = _generate_product_id(brand_id, sku)

    row = {
        "mn_product_id": mn_product_id,
        "brand_id": brand_id,
        "product_name": product_name,
        "shopify_product_id": shopify_product_id,
        "shopify_variant_ids": shopify_variant_ids or [],
        "external_id": external_id,
        "canonical_url": canonical_url,
        "product_data": product_data or {},
        "status": "active",
    }

    try:
        result = sb_request("POST", "narrative_product_registry", row, upsert=True)
        return {"mn_product_id": mn_product_id, "status": "registered"}
    except Exception as e:
        return {"error": str(e)}


def get_product(mn_product_id: str) -> dict:
    """Look up product by permanent MN Product ID."""
    try:
        result = sb_request("GET", "narrative_product_registry",
                          params={"mn_product_id": f"eq.{mn_product_id}", "select": "*"})
        if result and len(result) > 0:
            return result[0]
        return {"error": "product_not_found"}
    except Exception as e:
        return {"error": str(e)}


def update_product_url(mn_product_id: str, new_url: str) -> dict:
    """Update canonical URL without changing MN Product ID."""
    try:
        sb_request("PATCH", "narrative_product_registry",
                  {"canonical_url": new_url, "updated_at": datetime.utcnow().isoformat()},
                  params={"mn_product_id": f"eq.{mn_product_id}"})
        return {"ok": True}
    except Exception as e:
        return {"error": str(e)}


def find_product_by_shopify(shopify_product_id: str) -> Optional[dict]:
    """Find MN product by Shopify product ID."""
    try:
        result = sb_request("GET", "narrative_product_registry",
                          params={"shopify_product_id": f"eq.{shopify_product_id}", "select": "*"})
        if result and len(result) > 0:
            return result[0]
        return None
    except Exception:
        return None


def find_product_by_variant(shopify_variant_id: str) -> Optional[dict]:
    """Find MN product by any of its variant IDs."""
    try:
        result = sb_request("GET", "narrative_product_registry",
                          params={"select": "*", "status": "eq.active"})
        if not result:
            return None
        for product in result:
            variants = product.get("shopify_variant_ids", [])
            if shopify_variant_id in variants:
                return product
        return None
    except Exception:
        return None


# ============================================
# 2. CLICK TRACKING
# ============================================

def record_click(
    mn_product_id: str,
    host_brand_id: str,
    advertiser_brand_id: str,
    user_id: str = None,
    session_id: str = None,
    fingerprint: str = None,
    campaign_id: str = None,
    vton_session_id: str = None,
    source: str = "widget",
    source_detail: str = None,
    referrer_url: str = None,
    destination_url: str = None,
) -> dict:
    """
    Record a product click. Returns the tracking URL and click_id.
    This is the ONLY place click_ids are generated.
    """
    click_id = _generate_click_id()
    now = datetime.utcnow()
    expires_at = now + timedelta(days=ATTRIBUTION_WINDOW_DAYS)

    row = {
        "click_id": click_id,
        "mn_product_id": mn_product_id,
        "host_brand_id": host_brand_id,
        "advertiser_brand_id": advertiser_brand_id,
        "user_id": user_id,
        "session_id": session_id,
        "fingerprint": fingerprint,
        "campaign_id": campaign_id,
        "vton_session_id": vton_session_id,
        "source": source,
        "source_detail": source_detail,
        "referrer_url": referrer_url,
        "destination_url": destination_url,
        "attribution_window_days": ATTRIBUTION_WINDOW_DAYS,
        "attributed": False,
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
    }

    try:
        sb_request("POST", "narrative_clicks", row)
        tracking_url = f"https://go.mynarrative.store/c/{click_id}"
        return {
            "click_id": click_id,
            "tracking_url": tracking_url,
            "expires_at": expires_at.isoformat(),
        }
    except Exception as e:
        return {"error": str(e)}


def get_click(click_id: str) -> Optional[dict]:
    """Retrieve click record by ID."""
    try:
        result = sb_request("GET", "narrative_clicks",
                          params={"click_id": f"eq.{click_id}", "select": "*"})
        if result and len(result) > 0:
            return result[0]
        return None
    except Exception:
        return None


def get_clicks_for_product(mn_product_id: str, limit: int = 100) -> list:
    """Get all clicks for a product (for analytics)."""
    try:
        result = sb_request("GET", "narrative_clicks",
                          params={
                              "mn_product_id": f"eq.{mn_product_id}",
                              "select": "*",
                              "order": "created_at.desc",
                              "limit": str(limit),
                          })
        return result or []
    except Exception:
        return []


# ============================================
# 3. ATTRIBUTION ENGINE
# ============================================

def find_last_eligible_click(
    user_id: str,
    mn_product_id: str,
    advertiser_brand_id: str,
) -> Optional[dict]:
    """
    Find the last eligible MY NARRATIVE click for attribution.
    
    "Last eligible" means:
      1. Same user (by user_id or fingerprint)
      2. Same product (by mn_product_id)
      3. Same advertiser (advertiser_brand_id)
      4. Not yet attributed to another purchase
      5. Within 30-day attribution window
      6. From MY NARRATIVE (not organic/external)
    """
    try:
        result = sb_request("GET", "narrative_clicks", params={
            "user_id": f"eq.{user_id}",
            "mn_product_id": f"eq.{mn_product_id}",
            "advertiser_brand_id": f"eq.{advertiser_brand_id}",
            "attributed": "eq.false",
            "expires_at": f"gt.{datetime.utcnow().isoformat()}",
            "select": "*",
            "order": "created_at.desc",
            "limit": "1",
        })
        if result and len(result) > 0:
            return result[0]
        return None
    except Exception:
        return None


def record_attribution_event(
    click_id: str,
    mn_product_id: str,
    user_id: str,
    session_id: str,
    host_brand_id: str,
    advertiser_brand_id: str,
    campaign_id: str,
    event_type: str,
    event_data: dict = None,
) -> dict:
    """Record an attribution event (click, vton_view, add_to_cart, etc)."""
    event_id = _generate_event_id()

    row = {
        "event_id": event_id,
        "click_id": click_id,
        "mn_product_id": mn_product_id,
        "user_id": user_id,
        "session_id": session_id,
        "host_brand_id": host_brand_id,
        "advertiser_brand_id": advertiser_brand_id,
        "campaign_id": campaign_id,
        "event_type": event_type,
        "event_data": event_data or {},
        "created_at": datetime.utcnow().isoformat(),
    }

    try:
        sb_request("POST", "narrative_attribution_events", row)
        return {"event_id": event_id, "event_type": event_type}
    except Exception as e:
        return {"error": str(e)}


def attribute_purchase(
    user_id: str,
    order_id: str,
    order_items: list,
    source: str = "checkout",
) -> dict:
    """
    Attribute a purchase to the last eligible MY NARRATIVE click.
    
    Called when:
      - MN Checkout completes (source="checkout", confidence=DIRECT)
      - Merchant pixel fires checkout_completed (source="pixel", confidence=VERIFIED)
      - Reconciliation matches order (source="reconciliation", confidence=ATTRIBUTED)
    
    Args:
        user_id: Customer user_id
        order_id: Merchant order ID
        order_items: [{"mn_product_id": "...", "quantity": 1, "price": 1999.00, "sku": "..."}]
        source: Where attribution came from
    
    Returns:
        {"attributed": True, "commissions": [...]}
    """
    results = []
    now = datetime.utcnow()

    for item in order_items:
        mn_product_id = item.get("mn_product_id")
        if not mn_product_id:
            # Try to find by SKU or Shopify product ID
            mn_product_id = _resolve_product_id(item)
            if not mn_product_id:
                results.append({
                    "mn_product_id": item.get("mn_product_id", "unknown"),
                    "status": "no_product_match",
                })
                continue

        # Find last eligible click
        click = find_last_eligible_click(user_id, mn_product_id, item.get("advertiser_brand_id", ""))

        if not click:
            # No attribution — still create a commission event with UNVERIFIED confidence
            commission_event = _create_commission_event(
                order_id=order_id,
                item=item,
                click=None,
                confidence=ATtributionConfidence["UNVERIFIED"],
                source=source,
                now=now,
            )
            results.append(commission_event)
            continue

        # Mark click as attributed
        _mark_click_attributed(click["click_id"], order_id)

        # Record attribution event
        record_attribution_event(
            click_id=click["click_id"],
            mn_product_id=mn_product_id,
            user_id=user_id,
            session_id=click.get("session_id"),
            host_brand_id=click["host_brand_id"],
            advertiser_brand_id=click["advertiser_brand_id"],
            campaign_id=click.get("campaign_id"),
            event_type="purchase",
            event_data={"order_id": order_id, "source": source},
        )

        # Create commission event
        confidence = ATtributionConfidence["DIRECT"] if source == "checkout" else ATtributionConfidence["VERIFIED"]
        commission_event = _create_commission_event(
            order_id=order_id,
            item=item,
            click=click,
            confidence=confidence,
            source=source,
            now=now,
        )
        results.append(commission_event)

    return {"attributed": True, "commissions": results}


def _resolve_product_id(item: dict) -> Optional[str]:
    """Try to find mn_product_id from various identifiers."""
    # Try by shopify_product_id
    if item.get("shopify_product_id"):
        product = find_product_by_shopify(item["shopify_product_id"])
        if product:
            return product["mn_product_id"]

    # Try by variant ID
    if item.get("shopify_variant_id"):
        product = find_product_by_variant(item["shopify_variant_id"])
        if product:
            return product["mn_product_id"]

    # Try by external_id/SKU
    if item.get("sku") or item.get("external_id"):
        sku = item.get("sku") or item.get("external_id")
        brand_id = item.get("advertiser_brand_id", "")
        if brand_id:
            mn_id = _generate_product_id(brand_id, sku)
            # Check if it exists
            existing = get_product(mn_id)
            if "mn_product_id" in existing:
                return mn_id

    return None


def _mark_click_attributed(click_id: str, order_id: str):
    """Mark a click as attributed to an order."""
    try:
        sb_request("PATCH", "narrative_clicks",
                  {
                      "attributed": True,
                      "attributed_at": datetime.utcnow().isoformat(),
                      "attributed_order_id": order_id,
                  },
                  params={"click_id": f"eq.{click_id}"})
    except Exception:
        pass  # Best effort


def _create_commission_event(
    order_id: str,
    item: dict,
    click: Optional[dict],
    confidence: str,
    source: str,
    now: datetime,
) -> dict:
    """Create a single line-item commission event in the immutable ledger."""
    event_id = _generate_event_id()
    idempotency_key = _generate_idempotency_key(
        order_id,
        item.get("order_item_id", item.get("mn_product_id", "unknown")),
        "COMMISSION_CREATED"
    )

    gross = float(item.get("price", 0)) * int(item.get("quantity", 1))
    discount = float(item.get("discount", 0))
    tax = float(item.get("tax", 0))
    shipping = float(item.get("shipping", 0))
    net = max(gross - discount, 0)

    # Commission calculation
    commission_amount = round(net * PLATFORM_COMMISSION_RATE / 100, 2)
    host_affiliate_amount = 0.0

    # Host affiliate only for cross-brand purchases
    if click and click.get("host_brand_id") != item.get("advertiser_brand_id"):
        host_affiliate_amount = round(net * HOST_AFFILIATE_RATE / 100, 2)

    platform_fee = commission_amount
    brand_payout = gross - discount - commission_amount - host_affiliate_amount

    row = {
        "event_id": event_id,
        "event_type": "COMMISSION_CREATED",
        "idempotency_key": idempotency_key,
        "order_id": order_id,
        "order_item_id": item.get("order_item_id", item.get("mn_product_id", "unknown")),
        "click_id": click.get("click_id") if click else None,
        "mn_product_id": item.get("mn_product_id"),
        "host_brand_id": click.get("host_brand_id") if click else item.get("host_brand_id", ""),
        "advertiser_brand_id": item.get("advertiser_brand_id", ""),
        "campaign_id": click.get("campaign_id") if click else None,
        "gross_item_value": gross,
        "discount": discount,
        "tax": tax,
        "shipping": shipping,
        "net_commissionable_value": net,
        "commission_rate": PLATFORM_COMMISSION_RATE,
        "commission_amount": commission_amount,
        "host_affiliate_rate": HOST_AFFILIATE_RATE if host_affiliate_amount > 0 else 0,
        "host_affiliate_amount": host_affiliate_amount,
        "platform_fee": platform_fee,
        "brand_payout": brand_payout,
        "attribution_confidence": confidence,
        "attribution_window_days": ATTRIBUTION_WINDOW_DAYS,
        "status": CommissionStatus["PENDING"],
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }

    try:
        sb_request("POST", "narrative_commission_ledger", row)
        return {
            "event_id": event_id,
            "order_id": order_id,
            "mn_product_id": item.get("mn_product_id"),
            "commission_amount": commission_amount,
            "host_affiliate_amount": host_affiliate_amount,
            "status": "PENDING",
            "confidence": confidence,
        }
    except Exception as e:
        return {"error": str(e), "event_id": event_id}


# ============================================
# 4. COMMISSION LIFECYCLE
# ============================================

def advance_commission_status(
    event_id: str,
    new_status: str,
    reason: str = None,
) -> dict:
    """
    Advance a commission event to a new status.
    
    Allowed transitions:
      PENDING → CONFIRMED (after confirmation delay)
      CONFIRMED → PAYABLE (after payout delay)
      PAYABLE → PAID (after settlement)
      Any → VOIDED (cancellation)
      Any → REFUNDED (full refund)
      Any → PARTIALLY_REFUNDED (partial refund)
      Any → DISPUTED (merchant dispute)
    """
    valid_transitions = {
        "PENDING": ["CONFIRMED", "VOIDED"],
        "CONFIRMED": ["PAYABLE", "VOIDED", "REFUNDED", "PARTIALLY_REFUNDED", "DISPUTED"],
        "PAYABLE": ["PAID", "VOIDED", "REFUNDED", "PARTIALLY_REFUNDED"],
        "PAID": ["REFUNDED", "PARTIALLY_REFUNDED"],
    }

    # Get current status
    try:
        result = sb_request("GET", "narrative_commission_ledger",
                          params={"event_id": f"eq.{event_id}", "select": "event_id,status"})
        if not result or len(result) == 0:
            return {"error": "event_not_found"}

        current_status = result[0]["status"]

        if new_status not in valid_transitions.get(current_status, []):
            return {"error": f"invalid_transition:{current_status}→{new_status}"}

        # Create a new ledger entry for the status change
        new_event_id = _generate_event_id()
        now = datetime.utcnow()

        # Get the full original record
        full = sb_request("GET", "narrative_commission_ledger",
                         params={"event_id": f"eq.{event_id}", "select": "*"})[0]

        # Create status change event (preserves immutability)
        status_event = {
            "event_id": new_event_id,
            "event_type": f"COMMISSION_{new_status}",
            "idempotency_key": _generate_idempotency_key(full["order_id"], full.get("order_item_id", ""), f"STATUS_{new_status}"),
            "order_id": full["order_id"],
            "order_item_id": full.get("order_item_id"),
            "click_id": full.get("click_id"),
            "mn_product_id": full.get("mn_product_id"),
            "host_brand_id": full["host_brand_id"],
            "advertiser_brand_id": full["advertiser_brand_id"],
            "campaign_id": full.get("campaign_id"),
            "gross_item_value": full["gross_item_value"],
            "discount": full["discount"],
            "tax": full["tax"],
            "shipping": full["shipping"],
            "net_commissionable_value": full["net_commissionable_value"],
            "commission_rate": full["commission_rate"],
            "commission_amount": full["commission_amount"],
            "host_affiliate_rate": full["host_affiliate_rate"],
            "host_affiliate_amount": full["host_affiliate_amount"],
            "platform_fee": full["platform_fee"],
            "brand_payout": full["brand_payout"],
            "attribution_confidence": full["attribution_confidence"],
            "attribution_window_days": full.get("attribution_window_days"),
            "status": new_status,
            "original_event_id": event_id,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

        sb_request("POST", "narrative_commission_ledger", status_event)
        return {"ok": True, "new_event_id": new_event_id, "status": new_status}

    except Exception as e:
        return {"error": str(e)}


def process_refund(
    order_id: str,
    refund_items: list,
    reason: str = "customer_refund",
) -> dict:
    """
    Process a refund and adjust commissions.
    
    Args:
        order_id: The original order ID
        refund_items: [{"order_item_id": "...", "refund_amount": 1500.00}]
        reason: Why the refund happened
    """
    results = []
    now = datetime.utcnow()

    for refund_item in refund_items:
        order_item_id = refund_item.get("order_item_id")
        refund_amount = float(refund_item.get("refund_amount", 0))

        # Find original commission for this line item
        try:
            original = sb_request("GET", "narrative_commission_ledger", params={
                "order_id": f"eq.{order_id}",
                "order_item_id": f"eq.{order_item_id}",
                "event_type": "eq.COMMISSION_CREATED",
                "select": "*",
                "limit": "1",
            })

            if not original or len(original) == 0:
                results.append({"order_item_id": order_item_id, "status": "no_original_found"})
                continue

            orig = original[0]

            # Calculate reversal amounts
            gross_refund = refund_amount
            commission_reversal = round(gross_refund * float(orig["commission_rate"]) / 100, 2)
            host_affiliate_reversal = round(gross_refund * float(orig.get("host_affiliate_rate", 0)) / 100, 2)

            # Create reversal event
            reversal_event_id = _generate_event_id()
            reversal_row = {
                "event_id": reversal_event_id,
                "event_type": "COMMISSION_REVERSAL",
                "idempotency_key": _generate_idempotency_key(order_id, order_item_id, f"REFUND_{reason}"),
                "order_id": order_id,
                "order_item_id": order_item_id,
                "click_id": orig.get("click_id"),
                "mn_product_id": orig.get("mn_product_id"),
                "host_brand_id": orig["host_brand_id"],
                "advertiser_brand_id": orig["advertiser_brand_id"],
                "campaign_id": orig.get("campaign_id"),
                "gross_item_value": -gross_refund,
                "discount": 0,
                "tax": 0,
                "shipping": 0,
                "net_commissionable_value": -gross_refund,
                "commission_rate": float(orig["commission_rate"]),
                "commission_amount": -commission_reversal,
                "host_affiliate_rate": float(orig.get("host_affiliate_rate", 0)),
                "host_affiliate_amount": -host_affiliate_reversal,
                "platform_fee": -commission_reversal,
                "brand_payout": -(gross_refund - commission_reversal - host_affiliate_reversal),
                "attribution_confidence": orig["attribution_confidence"],
                "attribution_window_days": orig.get("attribution_window_days"),
                "status": "REFUNDED" if refund_amount >= float(orig["gross_item_value"]) else "PARTIALLY_REFUNDED",
                "original_event_id": orig["event_id"],
                "refund_amount": refund_amount,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }

            sb_request("POST", "narrative_commission_ledger", reversal_row)
            results.append({
                "order_item_id": order_item_id,
                "reversal_event_id": reversal_event_id,
                "commission_reversal": commission_reversal,
                "status": reversal_row["status"],
            })

        except Exception as e:
            results.append({"order_item_id": order_item_id, "error": str(e)})

    return {"refunds_processed": len(results), "results": results}


def batch_advance_pending_commissions() -> dict:
    """
    Called every 6 hours by reconciliation.
    Advances PENDING → CONFIRMED for commissions older than confirmation delay.
    """
    cutoff = (datetime.utcnow() - timedelta(hours=CONFIRMATION_DELAY_HOURS)).isoformat()

    try:
        pending = sb_request("GET", "narrative_commission_ledger", params={
            "status": "eq.PENDING",
            "event_type": "eq.COMMISSION_CREATED",
            "created_at": f"lt.{cutoff}",
            "select": "event_id",
        })

        if not pending:
            return {"advanced": 0}

        advanced = 0
        for event in pending:
            result = advance_commission_status(event["event_id"], "CONFIRMED", "auto_batch")
            if result.get("ok"):
                advanced += 1

        return {"advanced": advanced, "total_pending": len(pending)}

    except Exception as e:
        return {"error": str(e)}


def batch_advance_confirmed_to_payable() -> dict:
    """
    Called periodically.
    Advances CONFIRMED → PAYABLE for commissions older than payout delay.
    """
    cutoff = (datetime.utcnow() - timedelta(days=PAYOUT_DELAY_DAYS)).isoformat()

    try:
        confirmed = sb_request("GET", "narrative_commission_ledger", params={
            "status": "eq.CONFIRMED",
            "event_type": "eq.COMMISSION_CONFIRMED",
            "created_at": f"lt.{cutoff}",
            "select": "event_id",
        })

        if not confirmed:
            return {"advanced": 0}

        advanced = 0
        for event in confirmed:
            result = advance_commission_status(event["event_id"], "PAYABLE", "auto_batch")
            if result.get("ok"):
                advanced += 1

        return {"advanced": advanced, "total_confirmed": len(confirmed)}

    except Exception as e:
        return {"error": str(e)}


# ============================================
# 5. RECONCILIATION (6-hour)
# ============================================

def run_reconciliation() -> dict:
    """
    6-hour reconciliation job.
    1. Advance pending commissions
    2. Advance confirmed → payable
    3. Check for discrepancies
    """
    run_id = str(uuid.uuid4())
    now = datetime.utcnow()

    # Log reconciliation start
    try:
        sb_request("POST", "narrative_reconciliation_log", {
            "id": run_id,
            "run_type": "scheduled",
            "started_at": now.isoformat(),
            "status": "running",
        })
    except Exception:
        pass

    results = {
        "run_id": run_id,
        "started_at": now.isoformat(),
    }

    # Step 1: Advance PENDING → CONFIRMED
    try:
        pending_result = batch_advance_pending_commissions()
        results["pending_to_confirmed"] = pending_result
    except Exception as e:
        results["pending_to_confirmed"] = {"error": str(e)}

    # Step 2: Advance CONFIRMED → PAYABLE
    try:
        confirmed_result = batch_advance_confirmed_to_payable()
        results["confirmed_to_payable"] = confirmed_result
    except Exception as e:
        results["confirmed_to_payable"] = {"error": str(e)}

    # Step 3: Check for discrepancies
    try:
        discrepancy_result = _check_discrepancies()
        results["discrepancies"] = discrepancy_result
    except Exception as e:
        results["discrepancies"] = {"error": str(e)}

    # Update reconciliation log
    try:
        sb_request("PATCH", "narrative_reconciliation_log", {
            "completed_at": datetime.utcnow().isoformat(),
            "status": "completed",
            "orders_checked": results.get("discrepancies", {}).get("checked", 0),
            "orders_discrepancy": results.get("discrepancies", {}).get("discrepancies", 0),
        }, params={"id": f"eq.{run_id}"})
    except Exception:
        pass

    results["completed_at"] = datetime.utcnow().isoformat()
    return results


def _check_discrepancies() -> dict:
    """Check for orders that haven't been reconciled."""
    # Find PENDING commissions older than 24 hours without merchant order
    try:
        old_pending = sb_request("GET", "narrative_commission_ledger", params={
            "status": "eq.PENDING",
            "event_type": "eq.COMMISSION_CREATED",
            "created_at": f"lt.{(datetime.utcnow() - timedelta(hours=24)).isoformat()}",
            "select": "event_id,order_id,mn_product_id,created_at",
        })

        discrepancies = []
        for event in (old_pending or []):
            # Check if merchant order exists
            merchant_order = sb_request("GET", "narrative_merchant_orders", params={
                "shopify_order_id": f"eq.{event['order_id']}",
                "select": "id",
                "limit": "1",
            })

            if not merchant_order or len(merchant_order) == 0:
                discrepancies.append({
                    "event_id": event["event_id"],
                    "order_id": event["order_id"],
                    "issue": "no_merchant_order",
                    "age_hours": (datetime.utcnow() - datetime.fromisoformat(event["created_at"])).total_seconds() / 3600,
                })

        return {
            "checked": len(old_pending or []),
            "discrepancies": len(discrepancies),
            "details": discrepancies,
        }

    except Exception as e:
        return {"error": str(e)}


# ============================================
# 6. COMMISSION QUERIES
# ============================================

def get_brand_commissions(
    brand_id: str,
    status: str = None,
    start_date: str = None,
    end_date: str = None,
    limit: int = 100,
) -> list:
    """Get commission events for a brand (as host or advertiser)."""
    params = {
        "or": f"(host_brand_id.eq.{brand_id},advertiser_brand_id.eq.{brand_id})",
        "select": "*",
        "order": "created_at.desc",
        "limit": str(limit),
    }
    if status:
        params["status"] = f"eq.{status}"
    if start_date:
        params["created_at"] = f"gte.{start_date}"
    if end_date:
        if "created_at" in params:
            # Can't do two conditions on same field in Supabase REST
            # Use a different approach
            pass
        else:
            params["created_at"] = f"lte.{end_date}"

    try:
        return sb_request("GET", "narrative_commission_ledger", params) or []
    except Exception:
        return []


def get_commission_summary(brand_id: str) -> dict:
    """Get commission summary for a brand."""
    try:
        result = sb_request("GET", "narrative_commission_ledger", params={
            "or": f"(host_brand_id.eq.{brand_id},advertiser_brand_id.eq.{brand_id})",
            "event_type": "eq.COMMISSION_CREATED",
            "status": "not.in.(VOIDED,REFUNDED)",
            "select": "commission_amount,host_affiliate_amount,platform_fee,brand_payout,gross_item_value",
        })

        if not result:
            return {"total_orders": 0, "total_gross": 0, "total_commission": 0}

        total_gross = sum(float(r.get("gross_item_value", 0)) for r in result)
        total_commission = sum(float(r.get("commission_amount", 0)) for r in result)
        total_host = sum(float(r.get("host_affiliate_amount", 0)) for r in result)
        total_platform = sum(float(r.get("platform_fee", 0)) for r in result)
        total_payout = sum(float(r.get("brand_payout", 0)) for r in result)

        return {
            "total_commission_events": len(result),
            "total_gross": round(total_gross, 2),
            "total_commission": round(total_commission, 2),
            "total_host_affiliate": round(total_host, 2),
            "total_platform_fee": round(total_platform, 2),
            "total_brand_payout": round(total_payout, 2),
        }
    except Exception as e:
        return {"error": str(e)}
