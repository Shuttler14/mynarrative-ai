"""Cross-Brand Syndicate API — manages brand pairings, affiliate revenue, and cart handoffs."""
import json
import os
import urllib.request
import urllib.parse
from datetime import datetime

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
PLATFORM_FEE_RATE = 0.03  # 3% platform fee


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
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode() or "null"
            return json.loads(raw)
    except Exception as e:
        print(f"⚠️ [sb_request] {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════
# BRAND SYNDICATE RULES
# ═══════════════════════════════════════════════════════════════════════════

def get_syndicate_rules(brand_id: str) -> dict:
    """Get syndicate rules for a brand."""
    result = _sb_request("GET", f"/rest/v1/brand_syndicate_rules?brand_id=eq.{brand_id}&select=*")
    if result and len(result) > 0:
        return result[0]
    return {
        "brand_id": brand_id,
        "allowed_categories": [],
        "blocked_categories": [],
        "min_partner_price": 0,
        "max_partner_price": 999999,
        "allowed_tiers": [],
        "approved_partner_brand_ids": [],
        "blocked_partner_brand_ids": [],
        "affiliate_commission_rate": 0.07,
        "cpa_rate": 0.10,
        "is_active": True
    }


def update_syndicate_rules(brand_id: str, rules: dict) -> dict:
    """Update syndicate rules for a brand."""
    existing = _sb_request("GET", f"/rest/v1/brand_syndicate_rules?brand_id=eq.{brand_id}&select=id")
    
    if existing and len(existing) > 0:
        _sb_request("PATCH", f"/rest/v1/brand_syndicate_rules?brand_id=eq.{brand_id}", rules)
    else:
        rules["brand_id"] = brand_id
        _sb_request("POST", "/rest/v1/brand_syndicate_rules", rules)
    
    return {"success": True, "rules": rules}


# ═══════════════════════════════════════════════════════════════════════════
# BRAND PAIRINGS
# ═══════════════════════════════════════════════════════════════════════════

def request_pairing(host_brand_id: str, guest_brand_id: str) -> dict:
    """Request a pairing with another brand."""
    # Check if guest brand allows this
    guest_rules = get_syndicate_rules(guest_brand_id)
    if guest_rules.get("blocked_partner_brand_ids") and host_brand_id in guest_rules["blocked_partner_brand_ids"]:
        return {"error": "This brand has blocked partnerships"}
    
    # Check existing pairing
    existing = _sb_request("GET", f"/rest/v1/brand_syndicate_pairings?host_brand_id=eq.{guest_brand_id}&guest_brand_id=eq.{host_brand_id}&select=id,status")
    if existing and len(existing) > 0:
        if existing[0]["status"] == "approved":
            return {"error": "Already paired"}
        return {"error": "Pairing request pending"}
    
    # Auto-approve if guest brand has no whitelist
    auto_approve = not guest_rules.get("approved_partner_brand_ids") or len(guest_rules.get("approved_partner_brand_ids", [])) == 0
    
    pairing = {
        "host_brand_id": host_brand_id,
        "guest_brand_id": guest_brand_id,
        "status": "approved" if auto_approve else "pending"
    }
    
    if auto_approve:
        pairing["approved_at"] = datetime.utcnow().isoformat() + "Z"
    
    result = _sb_request("POST", "/rest/v1/brand_syndicate_pairings", pairing)
    
    if result and len(result) > 0:
        return {"success": True, "pairing": result[0], "auto_approved": auto_approve}
    return {"error": "Failed to create pairing"}


def approve_pairing(host_brand_id: str, guest_brand_id: str) -> dict:
    """Approve a pending pairing request."""
    result = _sb_request("PATCH", 
        f"/rest/v1/brand_syndicate_pairings?host_brand_id=eq.{host_brand_id}&guest_brand_id=eq.{guest_brand_id}",
        {"status": "approved", "approved_at": datetime.utcnow().isoformat() + "Z"}
    )
    return {"success": True}


def reject_pairing(host_brand_id: str, guest_brand_id: str) -> dict:
    """Reject a pairing request."""
    _sb_request("PATCH",
        f"/rest/v1/brand_syndicate_pairings?host_brand_id=eq.{host_brand_id}&guest_brand_id=eq.{guest_brand_id}",
        {"status": "rejected"}
    )
    return {"success": True}


def get_brand_partners(brand_id: str) -> dict:
    """Get all partners for a brand (as host and guest)."""
    as_host = _sb_request("GET", 
        f"/rest/v1/brand_syndicate_pairings?host_brand_id=eq.{brand_id}&status=eq.approved&select=*,guest_brand:brands!guest_brand_id(name,slug,logo_url)")
    as_guest = _sb_request("GET",
        f"/rest/v1/brand_syndicate_pairings?guest_brand_id=eq.{brand_id}&status=eq.approved&select=*,host_brand:brands!host_brand_id(name,slug,logo_url)")
    
    return {
        "as_host": as_host or [],
        "as_guest": as_guest or []
    }


# ═══════════════════════════════════════════════════════════════════════════
# FIND PARTNER PRODUCTS
# ═══════════════════════════════════════════════════════════════════════════

def find_partner_products(host_brand_id: str, category: str = "", occasion: str = "", price_tier: str = "mid", limit: int = 6) -> list:
    """Find products from partner brands that complement the host brand's catalog."""
    
    # Get host brand's rules
    host_rules = get_syndicate_rules(host_brand_id)
    
    # Get approved partner brand IDs
    pairings = _sb_request("GET",
        f"/rest/v1/brand_syndicate_pairings?host_brand_id=eq.{host_brand_id}&status=eq.approved&select=guest_brand_id,host_commission_rate,guest_cpa_rate")
    
    if not pairings:
        return []
    
    partner_ids = [p["guest_brand_id"] for p in pairings]
    
    # Filter by rules
    if host_rules.get("blocked_partner_brand_ids"):
        partner_ids = [pid for pid in partner_ids if pid not in host_rules["blocked_partner_brand_ids"]]
    
    if host_rules.get("approved_partner_brand_ids") and len(host_rules["approved_partner_brand_ids"]) > 0:
        partner_ids = [pid for pid in partner_ids if pid in host_rules["approved_partner_brand_ids"]]
    
    if not partner_ids:
        return []
    
    # Price tier mapping
    price_ranges = {
        "value": (0, 1500),
        "budget": (0, 1500),
        "mid": (1500, 3500),
        "premium": (1500, 3500),
        "luxury": (3500, 999999),
        "high": (3500, 999999)
    }
    price_min, price_max = price_ranges.get(price_tier, (0, 999999))
    
    # Apply host's price constraints
    price_min = max(price_min, host_rules.get("min_partner_price", 0))
    price_max = min(price_max, host_rules.get("max_partner_price", 999999))
    
    # Allowed categories from host rules
    allowed_cats = host_rules.get("allowed_categories", [])
    
    # Build query
    partner_ids_str = ",".join([f'"{pid}"' for pid in partner_ids])
    
    query = f"/rest/v1/brand_products?select=*,brand_catalogs!catalog_id(brand_id)&catalog_id.brand_id=in.({partner_ids_str})&is_active=eq.true"
    
    if allowed_cats and category:
        if category not in allowed_cats:
            return []  # Host doesn't allow this category
    
    if category:
        query += f"&category=eq.{category}"
    
    query += f"&price=gte.{price_min}&price=lte.{price_max}"
    query += f"&order=price.asc&limit={min(limit * 2, 30)}"
    
    products = _sb_request("GET", query)
    
    if not products:
        return []
    
    # Enrich with commission info and brand info
    pairing_map = {p["guest_brand_id"]: p for p in pairings}
    results = []
    
    for product in products:
        catalog = product.get("brand_catalogs", {})
        brand_id = catalog.get("brand_id") if catalog else None
        pairing = pairing_map.get(brand_id, {})
        
        results.append({
            "id": product.get("id"),
            "title": product.get("title"),
            "price": float(product.get("price", 0)),
            "currency": product.get("currency", "INR"),
            "image_url": product.get("image_url"),
            "category": product.get("category"),
            "brand_id": brand_id,
            "host_commission_rate": float(pairing.get("host_commission_rate", 0.07)),
            "is_gap_item": True,
            "source": "partner_brand"
        })
    
    return results[:limit]


# ═══════════════════════════════════════════════════════════════════════════
# CART HANDOFF
# ═══════════════════════════════════════════════════════════════════════════

def create_cart_handoff(host_brand_id: str, guest_brand_id: str, user_id: str, product: dict, session_id: str = "") -> dict:
    """Create a cross-brand cart handoff URL."""
    
    # Get guest brand's checkout URL pattern
    guest_brand = _sb_request("GET", f"/rest/v1/brands?id=eq.{guest_brand_id}&select=domain,slug")
    if not guest_brand or len(guest_brand) == 0:
        return {"error": "Guest brand not found"}
    
    domain = guest_brand[0].get("domain", "")
    slug = guest_brand[0].get("slug", "")
    
    # Build checkout URL with product data
    # Format: https://brand.com/checkout?sku=XXX&size=M&color=Navy&ref=mynarrative
    checkout_url = f"https://{domain}/checkout"
    params = {
        "sku": product.get("sku", product.get("id", "")),
        "size": product.get("selected_size", ""),
        "color": product.get("selected_color", ""),
        "qty": "1",
        "ref": "mynarrative",
        "host": host_brand_id,
        "session": session_id
    }
    
    query_string = urllib.parse.urlencode({k: v for k, v in params.items() if v})
    full_url = f"{checkout_url}?{query_string}"
    
    # Save handoff record
    handoff = {
        "host_brand_id": host_brand_id,
        "guest_brand_id": guest_brand_id,
        "user_id": user_id,
        "widget_session_id": session_id,
        "target_checkout_url": full_url,
        "product_sku": product.get("sku", ""),
        "product_id": product.get("id", ""),
        "selected_size": product.get("selected_size", ""),
        "selected_color": product.get("selected_color", ""),
        "quantity": 1,
        "utm_source": "mynarrative_widget",
        "utm_medium": "syndicate",
        "utm_campaign": f"host_{host_brand_id}_guest_{guest_brand_id}"
    }
    
    result = _sb_request("POST", "/rest/v1/cart_handoffs", handoff)
    
    # Update pairing stats
    _sb_request("POST", "/rest/v1/rpc/increment_syndicate_clicks", {
        "p_host_brand_id": host_brand_id,
        "p_guest_brand_id": guest_brand_id
    })
    
    return {
        "checkout_url": full_url,
        "handoff_id": result[0]["id"] if result and len(result) > 0 else None
    }


# ═══════════════════════════════════════════════════════════════════════════
# AFFILIATE TRANSACTIONS
# ═══════════════════════════════════════════════════════════════════════════

def record_affiliate_transaction(host_brand_id: str, guest_brand_id: str, order_data: dict) -> dict:
    """Record an affiliate transaction and calculate commissions."""
    
    order_total = float(order_data.get("order_total", 0))
    
    # Get commission rates
    pairing = _sb_request("GET",
        f"/rest/v1/brand_syndicate_pairings?host_brand_id=eq.{host_brand_id}&guest_brand_id=eq.{guest_brand_id}&select=host_commission_rate,guest_cpa_rate")
    
    if pairing and len(pairing) > 0:
        host_rate = float(pairing[0].get("host_commission_rate", 0.07))
        guest_rate = float(pairing[0].get("guest_cpa_rate", 0.10))
    else:
        host_rate = 0.07
        guest_rate = 0.10
    
    host_commission = round(order_total * host_rate, 2)
    guest_cpa = round(order_total * guest_rate, 2)
    platform_fee = round(order_total * PLATFORM_FEE_RATE, 2)
    
    transaction = {
        "host_brand_id": host_brand_id,
        "guest_brand_id": guest_brand_id,
        "user_id": order_data.get("user_id"),
        "order_id": order_data.get("order_id"),
        "order_total": order_total,
        "currency": order_data.get("currency", "INR"),
        "product_id": order_data.get("product_id"),
        "product_title": order_data.get("product_title"),
        "product_sku": order_data.get("product_sku"),
        "product_price": order_data.get("product_price"),
        "quantity": order_data.get("quantity", 1),
        "host_commission_rate": host_rate,
        "host_commission_amount": host_commission,
        "guest_cpa_rate": guest_rate,
        "guest_cpa_amount": guest_cpa,
        "platform_fee_rate": PLATFORM_FEE_RATE,
        "platform_fee_amount": platform_fee,
        "widget_session_id": order_data.get("widget_session_id"),
        "referral_source": order_data.get("referral_source", "widget")
    }
    
    result = _sb_request("POST", "/rest/v1/affiliate_transactions", transaction)
    
    # Update pairing stats
    _sb_request("POST", "/rest/v1/rpc/increment_syndicate_conversions", {
        "p_host_brand_id": host_brand_id,
        "p_guest_brand_id": guest_brand_id,
        "p_revenue": order_total,
        "p_commission": host_commission
    })
    
    # Update handoff if exists
    if order_data.get("handoff_id"):
        _sb_request("PATCH", f"/rest/v1/cart_handoffs?id=eq.{order_data['handoff_id']}", {
            "converted": True,
            "order_id": order_data.get("order_id"),
            "order_value": order_total,
            "converted_at": datetime.utcnow().isoformat() + "Z"
        })
    
    return {
        "transaction_id": result[0]["id"] if result and len(result) > 0 else None,
        "host_commission": host_commission,
        "guest_cpa": guest_cpa,
        "platform_fee": platform_fee
    }


# ═══════════════════════════════════════════════════════════════════════════
# BRAND DASHBOARD METRICS
# ═══════════════════════════════════════════════════════════════════════════

def get_syndicate_metrics(brand_id: str, period_days: int = 30) -> dict:
    """Get syndicate performance metrics for a brand."""
    
    # As Host - earnings from partner sales
    host_transactions = _sb_request("GET",
        f"/rest/v1/affiliate_transactions?host_brand_id=eq.{brand_id}&created_at=gte.{_days_ago(period_days)}&select=order_total,host_commission_amount")
    
    host_revenue = sum(t.get("order_total", 0) for t in (host_transactions or []))
    host_earnings = sum(t.get("host_commission_amount", 0) for t in (host_transactions or []))
    host_conversions = len(host_transactions or [])
    
    # As Guest - costs for being promoted on other sites
    guest_transactions = _sb_request("GET",
        f"/rest/v1/affiliate_transactions?guest_brand_id=eq.{brand_id}&created_at=gte.{_days_ago(period_days)}&select=order_total,guest_cpa_amount")
    
    guest_revenue = sum(t.get("order_total", 0) for t in (guest_transactions or []))
    guest_costs = sum(t.get("guest_cpa_amount", 0) for t in (guest_transactions or []))
    guest_conversions = len(guest_transactions or [])
    
    # Pending payouts
    pending_host = _sb_request("GET",
        f"/rest/v1/affiliate_transactions?host_brand_id=eq.{brand_id}&host_commission_status=eq.pending&select=host_commission_amount")
    pending_payout = sum(t.get("host_commission_amount", 0) for t in (pending_host or []))
    
    # Active partnerships
    partners = _sb_request("GET",
        f"/rest/v1/brand_syndicate_pairings?or=(host_brand_id.eq.{brand_id},guest_brand_id.eq.{brand_id})&status=eq.approved&select=id")
    
    return {
        "as_host": {
            "revenue_generated": round(host_revenue, 2),
            "commissions_earned": round(host_earnings, 2),
            "conversions": host_conversions,
            "pending_payout": round(pending_payout, 2)
        },
        "as_guest": {
            "revenue_driven": round(guest_revenue, 2),
            "cpa_costs": round(guest_costs, 2),
            "conversions": guest_conversions
        },
        "net_earnings": round(host_earnings - guest_costs, 2),
        "active_partnerships": len(partners or []),
        "period_days": period_days
    }


def _days_ago(days: int) -> str:
    from datetime import datetime, timedelta
    return (datetime.utcnow() - timedelta(days=days)).isoformat() + "Z"
