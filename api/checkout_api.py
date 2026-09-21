"""
MY NARRATIVE — Unified Cart & Checkout API
Single-file implementation for Vercel serverless compatibility.
"""

import os
import json
import hashlib
import hmac
import secrets
from datetime import datetime

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://fmganuxtqbquubtvvqdo.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZtZ2FudXh0cWJxdXVidHZ2cWRvIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTQ0Njk5OSwiZXhwIjoyMDg3MDIyOTk5fQ.CEdZM4fbkonyxsCmjccgHhwxpLcNvQT_GdiXOB5D6cU')
RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID', '')
RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', '')
PLATFORM_COMMISSION_RATE = 10.0


def _sb(table, method='GET', data=None, query=None):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json',
        'Prefer': 'return=representation'
    }
    import urllib.request
    body = json.dumps(data).encode() if data else None
    if query:
        url += f"?{query}"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {'error': str(e)}


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
    if user_id:
        items = _sb('narrative_cart', query=f'user_id=eq.{user_id}&order=added_at.asc')
    else:
        items = _sb('narrative_cart', query=f'session_id=eq.{session_id}&order=added_at.asc')
    if isinstance(items, dict) and 'error' in items:
        items = []
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
    if not user_id and not session_id:
        return {'error': 'user_id or session_id required'}, 400
    if not product.get('brand_id') or not product.get('product_id'):
        return {'error': 'brand_id and product_id required'}, 400
    quantity = body.get('quantity', 1)
    existing = None
    if user_id:
        results = _sb('narrative_cart', query=f'user_id=eq.{user_id}&product_id=eq.{product["product_id"]}')
    else:
        results = _sb('narrative_cart', query=f'session_id=eq.{session_id}&product_id=eq.{product["product_id"]}')
    if isinstance(results, list) and len(results) > 0:
        existing = results[0]
    if existing:
        new_qty = existing['quantity'] + quantity
        _sb('narrative_cart', method='PATCH', data={'quantity': new_qty, 'updated_at': 'now()'}, query=f'id=eq.{existing["id"]}')
    else:
        item = {
            'user_id': user_id or '', 'session_id': session_id if not user_id else None,
            'brand_id': product['brand_id'], 'product_id': product['product_id'],
            'variant_id': product.get('variant_id'), 'title': product.get('title', ''),
            'image_url': product.get('image_url'), 'price': product.get('price', 0),
            'compare_at_price': product.get('compare_at_price'), 'quantity': quantity,
            'size': product.get('size'), 'color': product.get('color'),
            'category': product.get('category'), 'product_url': product.get('product_url')
        }
        _sb('narrative_cart', method='POST', data=item)
    return get_cart({'user_id': [user_id] if user_id else [], 'session_id': [session_id] if session_id else []})


def update_cart_item(body):
    item_id = body.get('item_id')
    quantity = body.get('quantity', 1)
    if not item_id:
        return {'error': 'item_id required'}, 400
    if quantity <= 0:
        _sb('narrative_cart', method='DELETE', query=f'id=eq.{item_id}')
    else:
        _sb('narrative_cart', method='PATCH', data={'quantity': quantity, 'updated_at': 'now()'}, query=f'id=eq.{item_id}')
    return {'success': True}


def remove_from_cart(body):
    item_id = body.get('item_id')
    if not item_id:
        return {'error': 'item_id required'}, 400
    _sb('narrative_cart', method='DELETE', query=f'id=eq.{item_id}')
    return {'success': True}


def clear_cart(body):
    user_id = body.get('user_id')
    session_id = body.get('session_id')
    if user_id:
        _sb('narrative_cart', method='DELETE', query=f'user_id=eq.{user_id}')
    elif session_id:
        _sb('narrative_cart', method='DELETE', query=f'session_id=eq.{session_id}')
    return {'success': True}


# ============================================
# CHECKOUT
# ============================================

def create_order(body):
    user_id = body.get('user_id')
    address_id = body.get('address_id')
    payment_id = body.get('payment_id')
    razorpay_order_id = body.get('razorpay_order_id')
    if not user_id:
        return {'error': 'user_id required'}, 400
    cart = get_cart({'user_id': [user_id]})
    items = cart.get('items', [])
    if not items:
        return {'error': 'Cart is empty'}, 400
    address_snapshot = None
    if address_id:
        addr_result = _sb('narrative_addresses', query=f'id=eq.{address_id}')
        if isinstance(addr_result, list) and addr_result:
            address_snapshot = addr_result[0]
    subtotal = cart['total']
    shipping_fee = 0 if subtotal >= 999 else 49
    tax = round(subtotal * 0.18, 2)
    total = round(subtotal + shipping_fee + tax, 2)
    order_number = _gen_order_number()
    order = {
        'order_number': order_number, 'user_id': user_id, 'status': 'confirmed',
        'subtotal': subtotal, 'shipping_fee': shipping_fee, 'tax': tax, 'discount': 0,
        'total': total, 'currency': 'INR', 'address_id': address_id,
        'address_snapshot': address_snapshot, 'payment_id': payment_id,
        'payment_method': 'razorpay', 'payment_status': 'captured' if payment_id else 'pending'
    }
    order_result = _sb('narrative_orders', method='POST', data=order)
    if isinstance(order_result, dict) and 'error' in order_result:
        return {'error': f'Failed to create order: {order_result["error"]}'}, 500
    order_id = order_result[0]['id'] if isinstance(order_result, list) and order_result else None
    for item in items:
        gross = item.get('price', 0) * item.get('quantity', 1)
        commission = round(gross * PLATFORM_COMMISSION_RATE / 100, 2)
        order_item = {
            'order_id': order_id, 'brand_id': item.get('brand_id'),
            'brand_name': item.get('brand_id'), 'product_id': item.get('product_id'),
            'variant_id': item.get('variant_id'), 'title': item.get('title'),
            'image_url': item.get('image_url'), 'price': item.get('price'),
            'quantity': item.get('quantity', 1), 'size': item.get('size'),
            'color': item.get('color'), 'category': item.get('category'),
            'status': 'confirmed', 'commission_rate': PLATFORM_COMMISSION_RATE,
            'commission_amount': commission, 'brand_payout': round(gross - commission, 2)
        }
        item_result = _sb('narrative_order_items', method='POST', data=order_item)
        if isinstance(item_result, list) and item_result:
            _sb('narrative_commissions', method='POST', data={
                'order_id': order_id, 'order_item_id': item_result[0]['id'],
                'brand_id': item.get('brand_id'), 'gross_amount': gross,
                'commission_rate': PLATFORM_COMMISSION_RATE, 'commission_amount': commission,
                'platform_fee': commission, 'brand_payout': round(gross - commission, 2),
                'status': 'pending'
            })
    if payment_id:
        _sb('narrative_payments', method='POST', data={
            'order_id': order_id, 'razorpay_payment_id': payment_id,
            'razorpay_order_id': razorpay_order_id, 'amount': total,
            'currency': 'INR', 'status': 'captured', 'fee': round(total * 0.02, 2),
            'net_amount': round(total * 0.98, 2)
        })
    clear_cart({'user_id': user_id})
    return {'success': True, 'order': {'id': order_id, 'order_number': order_number, 'total': total, 'status': 'confirmed'}}


def verify_payment(body):
    razorpay_order_id = body.get('razorpay_order_id')
    razorpay_payment_id = body.get('razorpay_payment_id')
    razorpay_signature = body.get('razorpay_signature')
    if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature]):
        return {'error': 'Missing payment parameters'}, 400
    if RAZORPAY_KEY_SECRET:
        expected = hmac.new(RAZORPAY_KEY_SECRET.encode(), f"{razorpay_order_id}|{razorpay_payment_id}".encode(), hashlib.sha256).hexdigest()
        if expected != razorpay_signature:
            return {'error': 'Invalid payment signature'}, 400
    _sb('narrative_payments', method='PATCH', data={'razorpay_signature': razorpay_signature, 'status': 'captured'}, query=f'razorpay_order_id=eq.{razorpay_order_id}')
    return {'verified': True}


def save_address(body):
    address = {
        'user_id': body.get('user_id'), 'label': body.get('label', 'Home'),
        'full_name': body.get('full_name'), 'phone': body.get('phone'),
        'address_line1': body.get('address_line1'), 'address_line2': body.get('address_line2'),
        'city': body.get('city'), 'state': body.get('state'), 'pincode': body.get('pincode'),
        'country': body.get('country', 'IN'), 'is_default': body.get('is_default', False)
    }
    result = _sb('narrative_addresses', method='POST', data=address)
    return {'success': True, 'address': result}


def get_addresses(query):
    user_id = query.get('user_id', [None])[0]
    if not user_id:
        return {'addresses': []}
    result = _sb('narrative_addresses', query=f'user_id=eq.{user_id}&order=is_default.desc,created_at.desc')
    if isinstance(result, dict) and 'error' in result:
        return {'addresses': []}
    return {'addresses': result}


def get_orders(query):
    user_id = query.get('user_id', [None])[0]
    if not user_id:
        return {'orders': []}
    orders = _sb('narrative_orders', query=f'user_id=eq.{user_id}&order=created_at.desc')
    if isinstance(orders, dict) and 'error' in orders:
        return {'orders': []}
    for order in orders:
        items = _sb('narrative_order_items', query=f'order_id=eq.{order["id"]}&order=created_at.asc')
        order['items'] = items if isinstance(items, list) else []
        order['item_count'] = sum(i.get('quantity', 1) for i in order['items'])
    return {'orders': orders}


def get_order_detail(order_id):
    orders = _sb('narrative_orders', query=f'id=eq.{order_id}')
    if not isinstance(orders, list) or not orders:
        return {'error': 'Order not found'}, 404
    order = orders[0]
    items = _sb('narrative_order_items', query=f'order_id=eq.{order_id}&order=created_at.asc')
    order['items'] = items if isinstance(items, list) else []
    payments = _sb('narrative_payments', query=f'order_id=eq.{order_id}')
    order['payments'] = payments if isinstance(payments, list) else []
    return {'order': order}
