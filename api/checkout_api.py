"""
MY NARRATIVE — Unified Cart, Checkout & Payment API
====================================================
Single-file implementation for Vercel serverless compatibility.
Uses in-memory store when DB tables don't exist yet.

Payment Flow: Shopify Checkout (Razorpay already connected)
1. Customer adds items to cart via our API
2. Customer clicks "Checkout"
3. Our API creates order record + calculates commissions
4. Returns Shopify checkout URL
5. Customer completes payment on Shopify (Razorpay)
6. Shopify webhook confirms order → we update status

Change ID: MOD-CHK-002-260922
Scope: Checkout System
Risk: HIGH — Core payment flow
Revert: Restore previous version of api/checkout_api.py
"""

import os
import json
import hashlib
import hmac
import secrets
from datetime import datetime
import urllib.request
import urllib.error
from urllib.parse import urlencode

# ── Config ──────────────────────────────────────────────────────────
SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://fmganuxtqbquubtvvqdo.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
SHOPIFY_STORE_URL = os.environ.get('SHOPIFY_STORE_URL', 'https://mynarrative.store')
SHOPIFY_ACCESS_TOKEN = os.environ.get('SHOPIFY_ACCESS_TOKEN', '')
SHOPIFY_WEBHOOK_SECRET = os.environ.get('SHOPIFY_WEBHOOK_SECRET', '')

# Commission rates
PLATFORM_COMMISSION_RATE = 10.0   # 10% to My Narrative
HOST_AFFILIATE_RATE = 7.0         # 7% to host brand (when cross-brand)
SHIPPING_THRESHOLD = 999          # Free shipping above this (INR)
SHIPPING_FEE = 49                 # Flat shipping fee (INR)
GST_RATE = 18.0                   # GST rate (India)

# ── In-memory fallback stores ────────────────────────────────────────
_tables_checked = {}
_db_available = {}
_carts = {}
_addresses = {}
_orders = {}


# ── Supabase helper ──────────────────────────────────────────────────
def _sb(table, method='GET', data=None, query=None):
    global _tables_checked, _db_available
    if table not in _tables_checked:
        url = f"{SUPABASE_URL}/rest/v1/{table}?select=id&limit=1"
        headers = {'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}'}
        try:
            req = urllib.request.Request(url, headers=headers, method='GET')
            with urllib.request.urlopen(req, timeout=5) as resp:
                _db_available[table] = True
        except Exception as e:
            err = str(e).lower()
            if any(kw in err for kw in ('does not exist', 'relation', '404', 'pgrst205', 'could not find', 'not found')):
                _db_available[table] = False
            else:
                _db_available[table] = True
        _tables_checked[table] = True

    if not _db_available.get(table, False):
        return None

    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json',
        'Prefer': 'return=representation'
    }
    body = json.dumps(data).encode() if data else None
    if query:
        url += f"?{query}"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def _gen_order_number():
    now = datetime.now()
    rand = secrets.randbelow(9999)
    return f"MN-{now.strftime('%Y%m%d')}-{rand:04d}"


# ============================================
# CART
# ============================================

def get_cart(query):
    uid_vals = query.get('user_id', [])
    sid_vals = query.get('session_id', [])
    user_id = uid_vals[0] if uid_vals else None
    session_id = sid_vals[0] if sid_vals else None
    if not user_id and not session_id:
        return {'items': [], 'total': 0, 'item_count': 0, 'brands': [], 'brand_count': 0}

    store_key = user_id or session_id
    items = None

    if user_id:
        items = _sb('narrative_cart', query=f'user_id=eq.{user_id}&order=added_at.asc')
    elif session_id:
        items = _sb('narrative_cart', query=f'session_id=eq.{session_id}&order=added_at.asc')

    if items is None or (isinstance(items, dict) and 'error' in items):
        items = _carts.get(store_key, [])

    total = sum(i.get('price', 0) * i.get('quantity', 1) for i in items)
    item_count = sum(i.get('quantity', 1) for i in items)
    brands = {}
    for item in items:
        bid = item.get('brand_id', 'unknown')
        if bid not in brands:
            brands[bid] = {'brand_id': bid, 'items': [], 'subtotal': 0}
        brands[bid]['items'].append(item)
        brands[bid]['subtotal'] += item.get('price', 0) * item.get('quantity', 1)

    return {
        'items': items,
        'total': round(total, 2),
        'item_count': item_count,
        'brands': list(brands.values()),
        'brand_count': len(brands)
    }


def add_to_cart(body):
    user_id = body.get('user_id')
    session_id = body.get('session_id')
    product = body.get('product', {})
    quantity = body.get('quantity', 1)

    if not user_id and not session_id:
        return {'error': 'user_id or session_id required'}, 400
    if not product.get('brand_id') or not product.get('product_id'):
        return {'error': 'brand_id and product_id required'}, 400

    store_key = user_id or session_id

    # Try DB first
    db_result = None
    if user_id:
        db_result = _sb('narrative_cart', query=f'product_id=eq.{product["product_id"]}&user_id=eq.{user_id}')

    if db_result is not None and not (isinstance(db_result, dict) and 'error' in db_result):
        if isinstance(db_result, list) and len(db_result) > 0:
            existing = db_result[0]
            new_qty = existing['quantity'] + quantity
            _sb('narrative_cart', method='PATCH', data={'quantity': new_qty}, query=f'id=eq.{existing["id"]}')
        else:
            item = {
                'user_id': user_id or '', 'session_id': session_id if not user_id else None,
                'brand_id': product['brand_id'], 'product_id': product['product_id'],
                'variant_id': product.get('variant_id'), 'title': product.get('title', ''),
                'image_url': product.get('image_url'), 'price': product.get('price', 0),
                'compare_at_price': product.get('compare_at_price'), 'quantity': quantity,
                'size': product.get('size'), 'color': product.get('color'),
                'category': product.get('category'), 'product_url': product.get('product_url'),
                'added_at': datetime.utcnow().isoformat() + 'Z'
            }
            _sb('narrative_cart', method='POST', data=item)
    else:
        cart = _carts.get(store_key, [])
        found = False
        for item in cart:
            if item.get('product_id') == product['product_id']:
                item['quantity'] = item.get('quantity', 1) + quantity
                found = True
                break
        if not found:
            cart.append({
                'id': str(secrets.token_hex(8)),
                'user_id': user_id or '', 'session_id': session_id if not user_id else None,
                'brand_id': product['brand_id'], 'product_id': product['product_id'],
                'variant_id': product.get('variant_id'), 'title': product.get('title', ''),
                'image_url': product.get('image_url'), 'price': product.get('price', 0),
                'compare_at_price': product.get('compare_at_price'), 'quantity': quantity,
                'size': product.get('size'), 'color': product.get('color'),
                'category': product.get('category'), 'product_url': product.get('product_url'),
                'added_at': datetime.utcnow().isoformat() + 'Z'
            })
        _carts[store_key] = cart

    return get_cart({'user_id': [user_id] if user_id else [], 'session_id': [session_id] if session_id else []})


def update_cart_item(body):
    item_id = body.get('item_id')
    quantity = body.get('quantity', 1)
    user_id = body.get('user_id')
    if not item_id:
        return {'error': 'item_id required'}, 400

    if quantity <= 0:
        _sb('narrative_cart', method='DELETE', query=f'id=eq.{item_id}')
    else:
        _sb('narrative_cart', method='PATCH', data={'quantity': quantity}, query=f'id=eq.{item_id}')

    store_key = user_id or 'anon'
    cart = _carts.get(store_key, [])
    if quantity <= 0:
        _carts[store_key] = [i for i in cart if i.get('id') != item_id]
    else:
        for item in cart:
            if item.get('id') == item_id:
                item['quantity'] = quantity
                break

    return get_cart({'user_id': [user_id] if user_id else [], 'session_id': []})


def remove_from_cart(body):
    item_id = body.get('item_id') or (body.get('item_id', [None])[0] if isinstance(body.get('item_id'), list) else None)
    user_id = body.get('user_id')
    if not item_id:
        return {'error': 'item_id required'}, 400

    _sb('narrative_cart', method='DELETE', query=f'id=eq.{item_id}')
    store_key = user_id or 'anon'
    cart = _carts.get(store_key, [])
    _carts[store_key] = [i for i in cart if i.get('id') != item_id]

    return get_cart({'user_id': [user_id] if user_id else [], 'session_id': []})


def clear_cart(body):
    user_id = body.get('user_id') or (body.get('user_id', [None])[0] if isinstance(body.get('user_id'), list) else None)
    session_id = body.get('session_id')
    if user_id:
        _sb('narrative_cart', method='DELETE', query=f'user_id=eq.{user_id}')
        _carts.pop(user_id, None)
    elif session_id:
        _sb('narrative_cart', method='DELETE', query=f'session_id=eq.{session_id}')
        _carts.pop(session_id, None)
    return {'items': [], 'total': 0, 'item_count': 0, 'brands': [], 'brand_count': 0}


# ============================================
# ADDRESSES
# ============================================

def get_addresses(query):
    uid_vals = query.get('user_id', [])
    user_id = uid_vals[0] if uid_vals else None
    if not user_id:
        return {'error': 'user_id required'}, 400
    addrs = _sb('narrative_addresses', query=f'user_id=eq.{user_id}&order=is_default.desc')
    if addrs is None or (isinstance(addrs, dict) and 'error' in addrs):
        addrs = _addresses.get(user_id, [])
    return {'addresses': addrs}


def save_address(body):
    user_id = body.get('user_id')
    if not user_id:
        return {'error': 'user_id required'}, 400
    addr = {
        'user_id': user_id,
        'full_name': body.get('full_name', body.get('name', '')),
        'phone': body.get('phone', ''),
        'address_line1': body.get('address_line1', body.get('line1', '')),
        'address_line2': body.get('address_line2', body.get('line2', '')),
        'city': body.get('city', ''),
        'state': body.get('state', ''),
        'pincode': body.get('pincode', ''),
        'country': body.get('country', 'IN'),
        'label': body.get('label', 'Home'),
        'is_default': body.get('is_default', False),
    }
    db_result = _sb('narrative_addresses', method='POST', data=addr)
    if db_result is None or (isinstance(db_result, dict) and 'error' in db_result):
        addr['id'] = str(secrets.token_hex(8))
        _addresses.setdefault(user_id, []).append(addr)
    return get_addresses({'user_id': [user_id]})


# ============================================
# ORDERS
# ============================================

def get_orders(query):
    uid_vals = query.get('user_id', [])
    user_id = uid_vals[0] if uid_vals else None
    if not user_id:
        return {'error': 'user_id required'}, 400
    orders = _sb('narrative_orders', query=f'user_id=eq.{user_id}&order=created_at.desc')
    if orders is None or (isinstance(orders, dict) and 'error' in orders):
        orders = _orders.get(user_id, [])
    return {'orders': orders}


def get_order_detail(order_id):
    order = _sb('narrative_orders', query=f'id=eq.{order_id}')
    if order is None or (isinstance(order, dict) and 'error' in order):
        for uid_orders in _orders.values():
            for o in uid_orders:
                if o.get('id') == order_id or o.get('order_number') == order_id:
                    return {'order': o}
        return {'error': 'order not found'}, 404
    if isinstance(order, list) and len(order) > 0:
        order = order[0]

    items = _sb('narrative_order_items', query=f'order_id=eq.{order_id}') or []
    order['items'] = items if isinstance(items, list) else []

    payments = _sb('narrative_payments', query=f'order_id=eq.{order_id}') or []
    order['payments'] = payments if isinstance(payments, list) else []

    commissions = _sb('narrative_commissions', query=f'order_id=eq.{order_id}') or []
    order['commissions'] = commissions if isinstance(commissions, list) else []

    return {'order': order}


def create_order(body):
    """
    Create order and return Shopify checkout URL.

    Flow:
    1. Validate cart
    2. Calculate totals (subtotal + shipping + GST)
    3. Split by brand, calculate commissions
    4. Build Shopify checkout URL with cart items
    5. Save order to DB + in-memory
    6. Return order + checkout_url for redirect

    Change ID: MOD-CHK-002-260922
    """
    user_id = body.get('user_id')
    address_id = body.get('address_id')
    payment_method = body.get('payment_method', 'shopify')
    currency = body.get('currency', 'INR')
    return_url = body.get('return_url', f'{SHOPIFY_STORE_URL}/pages/order-confirmation')

    if not user_id:
        return {'error': 'user_id required'}, 400

    cart = get_cart({'user_id': [user_id]})
    if not cart.get('items'):
        return {'error': 'cart is empty'}, 400

    # Fetch address for snapshot
    address_snapshot = None
    if address_id:
        addrs = _sb('narrative_addresses', query=f'id=eq.{address_id}')
        if isinstance(addrs, list) and len(addrs) > 0:
            address_snapshot = addrs[0]

    order_number = _gen_order_number()
    now = datetime.utcnow().isoformat() + 'Z'
    subtotal = cart['total']
    shipping = 0 if subtotal >= SHIPPING_THRESHOLD else SHIPPING_FEE
    gst = round(subtotal * GST_RATE / 100, 2)
    total = round(subtotal + shipping + gst, 2)

    # ── Build parent order ───────────────────────────────────────
    order_id = str(secrets.token_hex(16))
    order = {
        'id': order_id,
        'order_number': order_number,
        'user_id': user_id,
        'address_id': address_id,
        'address_snapshot': address_snapshot,
        'subtotal': subtotal,
        'shipping_fee': shipping,
        'tax': gst,
        'discount': 0,
        'total': total,
        'currency': currency,
        'payment_method': payment_method,
        'payment_status': 'pending',
        'status': 'pending',
        'created_at': now,
    }

    # ── Split by brand + calculate commissions ───────────────────
    brand_splits = cart.get('brands', [])
    total_platform_commission = 0
    total_host_affiliate = 0
    order_items = []
    commissions = []

    # Host brand = first brand in cart (the store owner)
    host_brand_id = brand_splits[0]['brand_id'] if brand_splits else None

    for brand_split in brand_splits:
        brand_id = brand_split['brand_id']
        brand_subtotal = brand_split['subtotal']

        # Platform commission (always 10%)
        platform_fee = round(brand_subtotal * PLATFORM_COMMISSION_RATE / 100, 2)

        # Host affiliate commission (7% on cross-brand purchases only)
        host_affiliate = 0
        if brand_id != host_brand_id and host_brand_id:
            host_affiliate = round(brand_subtotal * HOST_AFFILIATE_RATE / 100, 2)

        brand_payout = round(brand_subtotal - platform_fee - host_affiliate, 2)
        total_platform_commission += platform_fee
        total_host_affiliate += host_affiliate

        brand_order_id = str(secrets.token_hex(8))
        brand_order = {
            'id': brand_order_id,
            'parent_order_id': order_id,
            'order_number': f"{order_number}-{brand_id[:8]}",
            'brand_id': brand_id,
            'user_id': user_id,
            'subtotal': brand_subtotal,
            'shipping_fee': round(shipping * (brand_subtotal / subtotal), 2) if subtotal > 0 else 0,
            'tax': round(brand_subtotal * GST_RATE / 100, 2),
            'total': round(brand_subtotal + (shipping * brand_subtotal / subtotal if subtotal > 0 else 0) + round(brand_subtotal * GST_RATE / 100, 2), 2),
            'payment_status': 'pending',
            'status': 'pending',
            'created_at': now,
        }

        for item in brand_split['items']:
            item_record = {
                'id': str(secrets.token_hex(8)),
                'order_id': order_id,
                'brand_id': brand_id,
                'brand_name': brand_id,
                'product_id': item['product_id'],
                'variant_id': item.get('variant_id'),
                'title': item.get('title', ''),
                'image_url': item.get('image_url'),
                'price': item['price'],
                'quantity': item.get('quantity', 1),
                'size': item.get('size'),
                'color': item.get('color'),
                'category': item.get('category'),
                'status': 'pending',
                'brand_order_id': brand_order_id,
                'commission_rate': PLATFORM_COMMISSION_RATE,
                'commission_amount': round(item['price'] * item.get('quantity', 1) * PLATFORM_COMMISSION_RATE / 100, 2),
                'brand_payout': round(item['price'] * item.get('quantity', 1) * (1 - PLATFORM_COMMISSION_RATE / 100), 2),
            }
            order_items.append(item_record)
            _sb('narrative_order_items', method='POST', data=item_record)

        # Commission record
        commission = {
            'id': str(secrets.token_hex(8)),
            'order_id': order_id,
            'order_item_id': brand_order_id,
            'brand_id': brand_id,
            'gross_amount': brand_subtotal,
            'commission_rate': PLATFORM_COMMISSION_RATE,
            'commission_amount': platform_fee,
            'platform_fee': platform_fee,
            'brand_payout': brand_payout,
            'status': 'pending',
            'created_at': now,
        }
        commissions.append(commission)
        _sb('narrative_commissions', method='POST', data=commission)
        _sb('narrative_orders', method='POST', data=brand_order)

    # ── Save parent order ────────────────────────────────────────
    order['total_platform_commission'] = total_platform_commission
    order['total_host_affiliate'] = total_host_affiliate
    order['items'] = order_items
    order['commissions'] = commissions
    _sb('narrative_orders', method='POST', data=order)

    # ── Build Shopify checkout URL ───────────────────────────────
    # Format: https://mynarrative.store/cart/{variant_id}:{quantity}
    # For products without variant IDs, use product_id as fallback
    cart_items = []
    for item in cart['items']:
        variant_id = item.get('variant_id') or item.get('product_id')
        qty = item.get('quantity', 1)
        if variant_id:
            cart_items.append(f"{variant_id}:{qty}")

    if cart_items:
        checkout_url = f"{SHOPIFY_STORE_URL}/cart/{','.join(cart_items)}"
    else:
        checkout_url = f"{SHOPIFY_STORE_URL}/cart"

    # Add note with order number for webhook matching
    checkout_url += f"?note=Order+{order_number}+by+user+{user_id}"

    # ── Clear cart ───────────────────────────────────────────────
    _orders.setdefault(user_id, []).append(order)
    _carts.pop(user_id, None)
    _sb('narrative_cart', method='DELETE', query=f'user_id=eq.{user_id}')

    return {
        'order': order,
        'checkout_url': checkout_url,
        'order_number': order_number,
    }


# ============================================
# SHOPIFY WEBHOOK HANDLER
# ============================================

def handle_shopify_webhook(body, headers):
    """
    Handle Shopify order webhook for payment confirmation.
    Triggered when customer completes checkout on Shopify.

    Change ID: MOD-CHK-003-260922
    """
    # ── Verify HMAC signature ────────────────────────────────────
    if SHOPIFY_WEBHOOK_SECRET:
        hmac_header = headers.get('x-shopify-hmac-sha256', '')
        raw_body = json.dumps(body).encode()
        expected = hmac.new(
            SHOPIFY_WEBHOOK_SECRET.encode(),
            raw_body,
            hashlib.sha256
        ).hexdigest()
        if expected != hmac_header:
            return {'error': 'invalid webhook signature'}, 403

    topic = headers.get('x-shopify-topic', '')
    shop_domain = headers.get('x-shopify-shop-domain', '')

    if topic == 'orders/create':
        return _handle_shopify_order_create(body)
    elif topic == 'orders/updated':
        return _handle_shopify_order_updated(body)
    elif topic == 'orders/paid':
        return _handle_shopify_order_paid(body)
    elif topic == 'orders/fulfilled':
        return _handle_shopify_order_fulfilled(body)
    elif topic == 'orders/cancelled':
        return _handle_shopify_order_cancelled(body)

    return {'ok': True, 'topic': topic}


def _handle_shopify_order_create(order_data):
    """Process new Shopify order — match to our internal order."""
    shopify_order_id = str(order_data.get('id', ''))
    order_number = order_data.get('order_number', '')
    note = order_data.get('note', '')
    total_price = float(order_data.get('total_price', 0))
    financial_status = order_data.get('financial_status', '')
    fulfillment_status = order_data.get('fulfillment_status', '')

    # Extract our order number from note
    our_order_number = None
    if 'Order MN-' in note:
        parts = note.split('Order ')
        if len(parts) > 1:
            our_order_number = parts[1].split(' ')[0].strip()

    # Find our order
    our_order = None
    if our_order_number:
        orders = _sb('narrative_orders', query=f'order_number=eq.{our_order_number}')
        if isinstance(orders, list) and len(orders) > 0:
            our_order = orders[0]

    if not our_order:
        # Try matching by note containing user_id
        if 'user ' in note:
            user_id = note.split('user ')[-1].strip()
            orders = _sb('narrative_orders', query=f'user_id=eq.{user_id}&status=eq.pending&order=created_at.desc')
            if isinstance(orders, list) and len(orders) > 0:
                our_order = orders[0]

    if not our_order:
        return {'ok': True, 'note': 'no matching internal order found'}

    our_order_id = our_order['id']
    now = datetime.utcnow().isoformat() + 'Z'

    # Update payment status based on Shopify's financial_status
    payment_status_map = {
        'paid': 'captured',
        'authorized': 'authorized',
        'pending': 'pending',
        'refunded': 'refunded',
        'partially_refunded': 'partially_refunded',
        'voided': 'failed',
    }
    payment_status = payment_status_map.get(financial_status, 'pending')

    # Update order
    _sb('narrative_orders', method='PATCH', data={
        'shopify_order_id': shopify_order_id,
        'shopify_order_number': str(order_number),
        'payment_status': payment_status,
        'status': 'confirmed' if payment_status == 'captured' else 'pending',
        'updated_at': now,
    }, query=f'id=eq.{our_order_id}')

    # Update payment record
    _sb('narrative_payments', method='PATCH', data={
        'shopify_order_id': shopify_order_id,
        'status': payment_status,
    }, query=f'order_id=eq.{our_order_id}')

    # Update commissions
    if payment_status == 'captured':
        _sb('narrative_commissions', method='PATCH', data={
            'status': 'approved',
        }, query=f'order_id=eq.{our_order_id}')

        # Update brand sub-orders
        _sb('narrative_orders', method='PATCH', data={
            'payment_status': 'captured',
            'status': 'confirmed',
        }, query=f'parent_order_id=eq.{our_order_id}')

        # Update order items
        _sb('narrative_order_items', method='PATCH', data={
            'status': 'confirmed',
        }, query=f'order_id=eq.{our_order_id}')

    # Update in-memory
    for uid, orders in _orders.items():
        for o in orders:
            if o.get('id') == our_order_id:
                o['payment_status'] = payment_status
                o['status'] = 'confirmed' if payment_status == 'captured' else 'pending'
                o['shopify_order_id'] = shopify_order_id
                break

    return {'success': True, 'order_id': our_order_id, 'shopify_order_id': shopify_order_id}


def _handle_shopify_order_updated(order_data):
    """Process order update — track fulfillment status."""
    shopify_order_id = str(order_data.get('id', ''))
    fulfillment_status = order_data.get('fulfillment_status', '')
    financial_status = order_data.get('financial_status', '')

    # Find our order by shopify_order_id
    orders = _sb('narrative_orders', query=f'shopify_order_id=eq.{shopify_order_id}')
    if not isinstance(orders, list) or len(orders) == 0:
        return {'ok': True, 'note': 'no matching order'}

    our_order = orders[0]
    our_order_id = our_order['id']
    now = datetime.utcnow().isoformat() + 'Z'

    # Map fulfillment status
    status_map = {
        None: 'confirmed',
        '': 'confirmed',
        'partial': 'processing',
        'fulfilled': 'delivered',
    }
    new_status = status_map.get(fulfillment_status, 'processing')

    _sb('narrative_orders', method='PATCH', data={
        'status': new_status,
        'updated_at': now,
    }, query=f'id=eq.{our_order_id}')

    # Update brand sub-orders
    _sb('narrative_orders', method='PATCH', data={
        'status': new_status,
    }, query=f'parent_order_id=eq.{our_order_id}')

    # Update order items
    _sb('narrative_order_items', method='PATCH', data={
        'status': new_status,
    }, query=f'order_id=eq.{our_order_id}')

    return {'success': True, 'status': new_status}


def _handle_shopify_order_paid(order_data):
    """Process payment confirmation."""
    return _handle_shopify_order_create(order_data)


def _handle_shopify_order_fulfilled(order_data):
    """Process fulfillment notification."""
    shopify_order_id = str(order_data.get('id', ''))
    fulfillments = order_data.get('fulfillments', [])

    orders = _sb('narrative_orders', query=f'shopify_order_id=eq.{shopify_order_id}')
    if not isinstance(orders, list) or len(orders) == 0:
        return {'ok': True}

    our_order_id = orders[0]['id']
    now = datetime.utcnow().isoformat() + 'Z'

    # Extract tracking URLs
    tracking_urls = []
    tracking_numbers = []
    for f in fulfillments:
        if f.get('tracking_url'):
            tracking_urls.append(f['tracking_url'])
        if f.get('tracking_number'):
            tracking_numbers.append(f['tracking_number'])

    _sb('narrative_orders', method='PATCH', data={
        'status': 'shipped',
        'tracking_urls': tracking_urls,
        'tracking_numbers': tracking_numbers,
        'shipped_at': now,
        'updated_at': now,
    }, query=f'id=eq.{our_order_id}')

    _sb('narrative_orders', method='PATCH', data={
        'status': 'shipped',
    }, query=f'parent_order_id=eq.{our_order_id}')

    _sb('narrative_order_items', method='PATCH', data={
        'status': 'shipped',
    }, query=f'order_id=eq.{our_order_id}')

    return {'success': True, 'status': 'shipped'}


def _handle_shopify_order_cancelled(order_data):
    """Process order cancellation."""
    shopify_order_id = str(order_data.get('id', ''))

    orders = _sb('narrative_orders', query=f'shopify_order_id=eq.{shopify_order_id}')
    if not isinstance(orders, list) or len(orders) == 0:
        return {'ok': True}

    our_order_id = orders[0]['id']
    now = datetime.utcnow().isoformat() + 'Z'

    _sb('narrative_orders', method='PATCH', data={
        'status': 'cancelled',
        'payment_status': 'refunded',
        'updated_at': now,
    }, query=f'id=eq.{our_order_id}')

    _sb('narrative_orders', method='PATCH', data={
        'status': 'cancelled',
    }, query=f'parent_order_id=eq.{our_order_id}')

    _sb('narrative_order_items', method='PATCH', data={
        'status': 'cancelled',
    }, query=f'order_id=eq.{our_order_id}')

    _sb('narrative_commissions', method='PATCH', data={
        'status': 'refunded',
    }, query=f'order_id=eq.{our_order_id}')

    return {'success': True, 'status': 'cancelled'}


# ============================================
# ORDER STATUS UPDATES (manual)
# ============================================

def update_order_status(body):
    """
    Update order/brand-sub-order status manually.
    Used by brands to mark items as processing, shipped, delivered.
    """
    order_id = body.get('order_id')
    status = body.get('status')
    tracking_url = body.get('tracking_url')
    brand_id = body.get('brand_id')

    if not order_id or not status:
        return {'error': 'order_id and status required'}, 400

    valid_statuses = ('pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled', 'refunded')
    if status not in valid_statuses:
        return {'error': f'invalid status. Must be one of: {valid_statuses}'}, 400

    now = datetime.utcnow().isoformat() + 'Z'
    update_data = {'status': status, 'updated_at': now}

    if tracking_url:
        update_data['tracking_url'] = tracking_url

    _sb('narrative_orders', method='PATCH', data=update_data, query=f'id=eq.{order_id}')

    if brand_id:
        _sb('narrative_order_items', method='PATCH', data={'status': status}, query=f'order_id=eq.{order_id}&brand_id=eq.{brand_id}')

    return {'success': True, 'order_id': order_id, 'status': status}
