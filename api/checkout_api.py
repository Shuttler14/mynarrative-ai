"""
MY NARRATIVE — Unified Cart & Checkout API
Single-file implementation for Vercel serverless compatibility.
Uses in-memory store when DB tables don't exist yet.
"""

import os
import json
import hashlib
import hmac
import secrets
from datetime import datetime
from urllib.parse import urlparse, parse_qs
import urllib.request

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://fmganuxtqbquubtvvqdo.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZtZ2FudXh0cWJxdXVidHZ2cWRvIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTQ0Njk5OSwiZXhwIjoyMDg3MDIyOTk5fQ.CEdZM4fbkonyxsCmjccgHhwxpLcNvQT_GdiXOB5D6cU')
RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID', '')
RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', '')
PLATFORM_COMMISSION_RATE = 10.0

_tables_checked = {}
_db_available = {}

_carts = {}
_addresses = {}
_orders = {}
_commissions = {}


def _sb(table, method='GET', data=None, query=None):
    global _tables_checked, _db_available
    if table not in _tables_checked:
        url = f"{SUPABASE_URL}/rest/v1/{table}?select=id&limit=1"
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
        }
        try:
            req = urllib.request.Request(url, headers=headers, method='GET')
            with urllib.request.urlopen(req, timeout=5) as resp:
                _db_available[table] = True
        except Exception as e:
            err = str(e).lower()
            if 'does not exist' in err or 'relation' in err or '404' in err or 'pgrst205' in err or 'could not find' in err or 'not found' in err:
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
    except Exception as e:
        return None


def _gen_order_number():
    now = datetime.now()
    rand = secrets.randbelow(9999)
    return f"MN-{now.strftime('%Y%m%d')}-{rand:04d}"


# ============================================
# CART
# ============================================

def get_cart(query):
    user_id = query.get('user_id', [None])[0]
    session_id = query.get('session_id', [None])[0]
    if not user_id and not session_id:
        return {'items': [], 'total': 0, 'item_count': 0, 'brands': [], 'brand_count': 0}

    items = _sb('narrative_cart', query=f'user_id=eq.{user_id}&order=added_at.asc') if user_id else \
            _sb('narrative_cart', query=f'session_id=eq.{session_id}&order=added_at.asc')

    if items is None:
        store_key = user_id or session_id
        items = _carts.get(store_key, [])
    elif isinstance(items, dict) and 'error' in items:
        store_key = user_id or session_id
        items = _carts.get(store_key, [])
    else:
        store_key = user_id or session_id

    total = sum(i.get('price', 0) * i.get('quantity', 1) for i in items)
    item_count = sum(i.get('quantity', 1) for i in items)
    brands = {}
    for item in items:
        bid = item.get('brand_id', 'unknown')
        if bid not in brands:
            brands[bid] = {'brand_id': bid, 'items': [], 'subtotal': 0}
        brands[bid]['items'].append(item)
        brands[bid]['subtotal'] += item.get('price', 0) * item.get('quantity', 1)
    return {'items': items, 'total': round(total, 2), 'item_count': item_count, 'brands': list(brands.values()), 'brand_count': len(brands)}


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

    db_result = _sb('narrative_cart', query=f'product_id=eq.{product["product_id"]}&user_id=eq.{user_id}') if user_id else None

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

    db_result = _sb('narrative_cart', method='DELETE', query=f'id=eq.{item_id}') if quantity <= 0 else \
                _sb('narrative_cart', method='PATCH', data={'quantity': quantity}, query=f'id=eq.{item_id}')

    if db_result is None:
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
    user_id = query.get('user_id', [None])[0]
    if not user_id:
        return {'error': 'user_id required'}, 400
    addrs = _sb('narrative_addresses', query=f'user_id=eq.{user_id}&order=is_default.desc')
    if addrs is None:
        addrs = _addresses.get(user_id, [])
    elif isinstance(addrs, dict) and 'error' in addrs:
        addrs = _addresses.get(user_id, [])
    return {'addresses': addrs}


def save_address(body):
    user_id = body.get('user_id')
    if not user_id:
        return {'error': 'user_id required'}, 400
    addr = {
        'user_id': user_id,
        'name': body.get('name', ''),
        'phone': body.get('phone', ''),
        'line1': body.get('line1', ''),
        'line2': body.get('line2', ''),
        'city': body.get('city', ''),
        'state': body.get('state', ''),
        'pincode': body.get('pincode', ''),
        'country': body.get('country', 'IN'),
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
    user_id = query.get('user_id', [None])[0]
    if not user_id:
        return {'error': 'user_id required'}, 400
    orders = _sb('narrative_orders', query=f'user_id=eq.{user_id}&order=created_at.desc')
    if orders is None:
        orders = _orders.get(user_id, [])
    elif isinstance(orders, dict) and 'error' in orders:
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
    return {'order': order}


def create_order(body):
    user_id = body.get('user_id')
    address_id = body.get('address_id')
    payment_method = body.get('payment_method', 'razorpay')

    if not user_id:
        return {'error': 'user_id required'}, 400

    cart = get_cart({'user_id': [user_id]})
    if not cart.get('items'):
        return {'error': 'cart is empty'}, 400

    order_number = _gen_order_number()
    now = datetime.utcnow().isoformat() + 'Z'
    subtotal = cart['total']
    shipping = 0 if subtotal >= 999 else 49
    gst = round(subtotal * 0.18, 2)
    total = round(subtotal + shipping + gst, 2)

    order = {
        'id': str(secrets.token_hex(16)),
        'order_number': order_number,
        'user_id': user_id,
        'address_id': address_id,
        'subtotal': subtotal,
        'shipping': shipping,
        'gst': gst,
        'total': total,
        'payment_method': payment_method,
        'payment_status': 'pending',
        'status': 'pending',
        'created_at': now,
    }

    brand_splits = cart.get('brands', [])
    commission_total = 0
    order_items = []
    commissions = []

    for brand_split in brand_splits:
        brand_id = brand_split['brand_id']
        brand_subtotal = brand_split['subtotal']
        brand_commission = round(brand_subtotal * PLATFORM_COMMISSION_RATE / 100, 2)
        commission_total += brand_commission

        brand_order_id = str(secrets.token_hex(8))
        brand_order = {
            'id': brand_order_id,
            'parent_order_id': order['id'],
            'order_number': f"{order_number}-{brand_id[:8]}",
            'brand_id': brand_id,
            'user_id': user_id,
            'subtotal': brand_subtotal,
            'shipping': round(shipping * (brand_subtotal / subtotal), 2) if subtotal > 0 else 0,
            'gst': round(brand_subtotal * 0.18, 2),
            'total': round(brand_subtotal * (1 + PLATFORM_COMMISSION_RATE / 100) + (shipping * brand_subtotal / subtotal if subtotal > 0 else 0), 2),
            'payment_status': 'pending',
            'status': 'pending',
            'created_at': now,
        }

        for item in brand_split['items']:
            item_record = {
                'id': str(secrets.token_hex(8)),
                'parent_order_id': order['id'],
                'order_id': brand_order_id,
                'product_id': item['product_id'],
                'variant_id': item.get('variant_id'),
                'brand_id': brand_id,
                'title': item.get('title', ''),
                'price': item['price'],
                'quantity': item.get('quantity', 1),
                'size': item.get('size'),
                'color': item.get('color'),
                'image_url': item.get('image_url'),
            }
            order_items.append(item_record)
            _sb('narrative_order_items', method='POST', data=item_record)

        commission = {
            'id': str(secrets.token_hex(8)),
            'parent_order_id': order['id'],
            'order_id': brand_order_id,
            'brand_id': brand_id,
            'gross_amount': brand_subtotal,
            'commission_rate': PLATFORM_COMMISSION_RATE,
            'commission_amount': brand_commission,
            'net_amount': round(brand_subtotal - brand_commission, 2),
            'status': 'pending',
            'created_at': now,
        }
        commissions.append(commission)
        _sb('narrative_commissions', method='POST', data=commission)
        _sb('narrative_orders', method='POST', data=brand_order)

    order['commission_total'] = commission_total
    order['items'] = order_items
    order['commissions'] = commissions
    _sb('narrative_orders', method='POST', data=order)

    _orders.setdefault(user_id, []).append(order)
    _carts.pop(user_id, None)
    _sb('narrative_cart', method='DELETE', query=f'user_id=eq.{user_id}')

    return {'order': order, 'razorpay_key': RAZORPAY_KEY_ID}


def verify_payment(body):
    razorpay_order_id = body.get('razorpay_order_id')
    razorpay_payment_id = body.get('razorpay_payment_id')
    razorpay_signature = body.get('razorpay_signature')
    order_id = body.get('order_id')

    if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature, order_id]):
        return {'error': 'all payment fields required'}, 400

    if RAZORPAY_KEY_SECRET:
        expected = hmac.new(
            RAZORPAY_KEY_SECRET.encode(),
            f"{razorpay_order_id}|{razorpay_payment_id}".encode(),
            hashlib.sha256
        ).hexdigest()
        if expected != razorpay_signature:
            return {'error': 'invalid payment signature'}, 400

    now = datetime.utcnow().isoformat() + 'Z'
    _sb('narrative_orders', method='PATCH', data={
        'payment_status': 'paid',
        'status': 'confirmed',
        'razorpay_payment_id': razorpay_payment_id,
        'razorpay_order_id': razorpay_order_id,
        'paid_at': now,
    }, query=f'id=eq.{order_id}')

    _sb('narrative_commissions', method='PATCH', data={
        'status': 'captured',
        'captured_at': now,
    }, query=f'parent_order_id=eq.{order_id}')

    for uid, orders in _orders.items():
        for o in orders:
            if o.get('id') == order_id:
                o['payment_status'] = 'paid'
                o['status'] = 'confirmed'
                break

    return {'success': True, 'order_id': order_id, 'payment_id': razorpay_payment_id}
