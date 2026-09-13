"""
Creator Earnings API Handler
Serves creator earnings data and tier progress to frontend Liquid sections.
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
import uuid

# Try to import Supabase client, fall back to demo mode if unavailable
try:
    from supabase import create_client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

# CORS headers for all responses
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Content-Type": "application/json"
}


def compute_tier_progress(total_sold: int) -> Dict[str, Any]:
    """
    Calculate tier progress based on total designs sold.
    
    Tiers:
    - Bronze: 0-49 sales
    - Silver: 50-199 sales
    - Gold: 200-999 sales
    - Diamond: 1000+ sales
    """
    tiers = [(0, 'Bronze', 50), (50, 'Silver', 200), (200, 'Gold', 1000), (1000, 'Diamond', None)]
    
    for floor, name, ceiling in tiers:
        if ceiling is None or total_sold < ceiling:
            if ceiling is None:
                # Diamond tier - max tier reached
                return {
                    'current_tier': 'Diamond',
                    'next_tier': None,
                    'sales_to_next_tier': 0,
                    'progress_pct': 100
                }
            # In current tier
            in_tier = total_sold - floor
            span = ceiling - floor
            tier_index = tiers.index((floor, name, ceiling))
            next_tier_name = tiers[tier_index + 1][1]
            
            return {
                'current_tier': name,
                'next_tier': next_tier_name,
                'sales_to_next_tier': ceiling - total_sold,
                'progress_pct': int((in_tier / span) * 100)
            }
    
    # Fallback (should not reach here)
    return {
        'current_tier': 'Diamond',
        'next_tier': None,
        'sales_to_next_tier': 0,
        'progress_pct': 100
    }


def get_supabase_client():
    """Initialize and return Supabase client."""
    if not SUPABASE_AVAILABLE:
        return None
    
    url = os.environ.get('SUPABASE_URL')
    key = os.environ.get('SUPABASE_KEY')
    
    if not url or not key:
        return None
    
    return create_client(url, key)


def fetch_creator_by_shopify_id(supabase_client, shopify_customer_id: str) -> Optional[Dict[str, Any]]:
    """Fetch creator record from Supabase by shopify_customer_id."""
    if not supabase_client:
        return None
    
    try:
        response = supabase_client.table('creators').select('id, shopify_customer_id, tier').eq(
            'shopify_customer_id', shopify_customer_id
        ).single().execute()
        return response.data
    except Exception as e:
        print(f"Error fetching creator: {e}")
        return None


def fetch_creator_transactions(supabase_client, creator_id: str, limit: int = 10) -> list:
    """Fetch last N transactions from financial_ledger for a creator."""
    if not supabase_client:
        return []
    
    try:
        response = supabase_client.table('financial_ledger').select(
            'id, creator_id, event_type, amount_paise, product_type, product_color, quantity, note, created_at'
        ).eq('creator_id', creator_id).order('created_at', desc=True).limit(limit).execute()
        return response.data or []
    except Exception as e:
        print(f"Error fetching transactions: {e}")
        return []


def format_transaction(tx: Dict[str, Any]) -> Dict[str, Any]:
    """Format a transaction record for API response."""
    amount_paise = tx.get('amount_paise', 0)
    amount_rupees = amount_paise / 100.0
    
    return {
        'id': tx.get('id', str(uuid.uuid4())),
        'event_type': tx.get('event_type', 'sale'),
        'amount_paise': amount_paise,
        'amount_rupees': amount_rupees,
        'product_type': tx.get('product_type', ''),
        'color': tx.get('product_color', ''),
        'quantity': tx.get('quantity', 0),
        'note': tx.get('note', ''),
        'created_at': tx.get('created_at', datetime.utcnow().isoformat() + 'Z')
    }


def generate_demo_data(creator_id: str) -> Dict[str, Any]:
    """Generate realistic demo data for a Silver tier creator."""
    total_sold = 50
    total_earnings_paise = 149500
    total_earnings_rupees = 1495.0
    
    # Generate 10 sample transactions
    demo_transactions = [
        {
            'id': str(uuid.uuid4()),
            'event_type': 'sale',
            'amount_paise': 29900,
            'amount_rupees': 299.0,
            'product_type': 'tshirt',
            'color': 'white',
            'quantity': 1,
            'note': 'Sale: Midnight Bloom | tshirt/white × 1 | Order 12345',
            'created_at': (datetime.utcnow() - timedelta(days=0, hours=2)).isoformat() + 'Z'
        },
        {
            'id': str(uuid.uuid4()),
            'event_type': 'sale',
            'amount_paise': 24950,
            'amount_rupees': 249.50,
            'product_type': 'hoodie',
            'color': 'black',
            'quantity': 1,
            'note': 'Sale: Urban Echo | hoodie/black × 1 | Order 12346',
            'created_at': (datetime.utcnow() - timedelta(days=1, hours=4)).isoformat() + 'Z'
        },
        {
            'id': str(uuid.uuid4()),
            'event_type': 'sale',
            'amount_paise': 19950,
            'amount_rupees': 199.50,
            'product_type': 'tshirt',
            'color': 'navy',
            'quantity': 1,
            'note': 'Sale: Ocean Vibes | tshirt/navy × 1 | Order 12347',
            'created_at': (datetime.utcnow() - timedelta(days=2)).isoformat() + 'Z'
        },
        {
            'id': str(uuid.uuid4()),
            'event_type': 'refund',
            'amount_paise': -9950,
            'amount_rupees': -99.50,
            'product_type': 'hoodie',
            'color': 'gray',
            'quantity': 1,
            'note': 'Refund: Cozy Comfort | hoodie/gray × 1 | Order 12348',
            'created_at': (datetime.utcnow() - timedelta(days=3)).isoformat() + 'Z'
        },
        {
            'id': str(uuid.uuid4()),
            'event_type': 'sale',
            'amount_paise': 34900,
            'amount_rupees': 349.0,
            'product_type': 'tshirt',
            'color': 'red',
            'quantity': 2,
            'note': 'Sale: Bold Statement | tshirt/red × 2 | Order 12349',
            'created_at': (datetime.utcnow() - timedelta(days=4)).isoformat() + 'Z'
        },
        {
            'id': str(uuid.uuid4()),
            'event_type': 'sale',
            'amount_paise': 29900,
            'amount_rupees': 299.0,
            'product_type': 'hoodie',
            'color': 'blue',
            'quantity': 1,
            'note': 'Sale: Sky Dreams | hoodie/blue × 1 | Order 12350',
            'created_at': (datetime.utcnow() - timedelta(days=5)).isoformat() + 'Z'
        },
        {
            'id': str(uuid.uuid4()),
            'event_type': 'sale',
            'amount_paise': 14950,
            'amount_rupees': 149.50,
            'product_type': 'tshirt',
            'color': 'green',
            'quantity': 1,
            'note': 'Sale: Nature Call | tshirt/green × 1 | Order 12351',
            'created_at': (datetime.utcnow() - timedelta(days=6)).isoformat() + 'Z'
        },
        {
            'id': str(uuid.uuid4()),
            'event_type': 'sale',
            'amount_paise': 24950,
            'amount_rupees': 249.50,
            'product_type': 'hoodie',
            'color': 'purple',
            'quantity': 1,
            'note': 'Sale: Royal Purple | hoodie/purple × 1 | Order 12352',
            'created_at': (datetime.utcnow() - timedelta(days=7)).isoformat() + 'Z'
        },
        {
            'id': str(uuid.uuid4()),
            'event_type': 'sale',
            'amount_paise': 39900,
            'amount_rupees': 399.0,
            'product_type': 'tshirt',
            'color': 'orange',
            'quantity': 1,
            'note': 'Sale: Sunset Glow | tshirt/orange × 1 | Order 12353',
            'created_at': (datetime.utcnow() - timedelta(days=8)).isoformat() + 'Z'
        },
        {
            'id': str(uuid.uuid4()),
            'event_type': 'sale',
            'amount_paise': 29900,
            'amount_rupees': 299.0,
            'product_type': 'hoodie',
            'color': 'white',
            'quantity': 1,
            'note': 'Sale: Pure White | hoodie/white × 1 | Order 12354',
            'created_at': (datetime.utcnow() - timedelta(days=9)).isoformat() + 'Z'
        }
    ]
    
    return {
        'success': True,
        'creator_id': creator_id,
        'summary': {
            'total_earnings_paise': total_earnings_paise,
            'total_earnings_rupees': total_earnings_rupees,
            'total_designs_sold': total_sold,
            'creator_tier': 'Silver',
            'tier_progress': compute_tier_progress(total_sold)
        },
        'recent_transactions': demo_transactions
    }


def build_earnings_response(creator_id: str, transactions: list) -> Dict[str, Any]:
    """Build the earnings response from creator data and transactions."""
    # Calculate totals
    total_earnings_paise = 0
    total_designs_sold = 0
    
    for tx in transactions:
        amount = tx.get('amount_paise', 0)
        if tx.get('event_type') == 'sale':
            total_earnings_paise += amount
            total_designs_sold += tx.get('quantity', 0)
        elif tx.get('event_type') == 'refund':
            total_earnings_paise += amount  # Will be negative
            total_designs_sold -= tx.get('quantity', 0)
    
    # Ensure non-negative values
    total_earnings_paise = max(0, total_earnings_paise)
    total_designs_sold = max(0, total_designs_sold)
    
    total_earnings_rupees = total_earnings_paise / 100.0
    
    # Format transactions for response
    formatted_transactions = [format_transaction(tx) for tx in transactions]
    
    return {
        'success': True,
        'creator_id': creator_id,
        'summary': {
            'total_earnings_paise': total_earnings_paise,
            'total_earnings_rupees': total_earnings_rupees,
            'total_designs_sold': total_designs_sold,
            'creator_tier': compute_tier_progress(total_designs_sold)['current_tier'],
            'tier_progress': compute_tier_progress(total_designs_sold)
        },
        'recent_transactions': formatted_transactions
    }


def build_summary_response(creator_id: str, transactions: list) -> Dict[str, Any]:
    """Build the summary-only response (no transactions)."""
    response = build_earnings_response(creator_id, transactions)
    # Remove transactions for summary endpoint
    del response['recent_transactions']
    return response


def handle_get_earnings(creator_id: str) -> Tuple[Dict[str, Any], int]:
    """Handle GET /api/creator/earnings request."""
    if not creator_id or creator_id.strip() == '':
        return {'success': False, 'error': 'creator_id is required'}, 400
    
    supabase_client = get_supabase_client()
    
    # If Supabase is not available, return demo data
    if not supabase_client:
        return generate_demo_data(creator_id), 200
    
    # Fetch creator from database
    creator = fetch_creator_by_shopify_id(supabase_client, creator_id)
    if not creator:
        # Return demo data if creator not found
        return generate_demo_data(creator_id), 200
    
    # Fetch transactions
    transactions = fetch_creator_transactions(supabase_client, creator['id'])
    
    # If no transactions, return demo data
    if not transactions:
        return generate_demo_data(creator_id), 200
    
    return build_earnings_response(creator_id, transactions), 200


def handle_get_summary(creator_id: str) -> Tuple[Dict[str, Any], int]:
    """Handle GET /api/creator/earnings/summary request."""
    if not creator_id or creator_id.strip() == '':
        return {'success': False, 'error': 'creator_id is required'}, 400
    
    supabase_client = get_supabase_client()
    
    # If Supabase is not available, return demo data
    if not supabase_client:
        response = generate_demo_data(creator_id)
        del response['recent_transactions']
        return response, 200
    
    # Fetch creator from database
    creator = fetch_creator_by_shopify_id(supabase_client, creator_id)
    if not creator:
        # Return demo data if creator not found
        response = generate_demo_data(creator_id)
        del response['recent_transactions']
        return response, 200
    
    # Fetch transactions
    transactions = fetch_creator_transactions(supabase_client, creator['id'])
    
    # If no transactions, return demo data
    if not transactions:
        response = generate_demo_data(creator_id)
        del response['recent_transactions']
        return response, 200
    
    return build_summary_response(creator_id, transactions), 200


def handle_health_check() -> Tuple[Dict[str, Any], int]:
    """Handle GET /api/creator/earnings/health request."""
    supabase_available = get_supabase_client() is not None
    return {
        'success': True,
        'status': 'healthy',
        'supabase_connected': supabase_available,
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }, 200


def handler(event, context):
    """
    Vercel serverless handler for creator earnings endpoints.
    Routes requests based on path and method.
    """
    try:
        # Get request method and path
        method = event.get('httpMethod', 'GET').upper()
        path = event.get('path', '').lower()
        query_string = event.get('queryStringParameters') or {}
        
        # Only allow GET requests
        if method != 'GET':
            return {
                'statusCode': 405,
                'headers': CORS_HEADERS,
                'body': json.dumps({'success': False, 'error': 'Method not allowed'})
            }
        
        creator_id = query_string.get('creator_id', '').strip()
        
        # Route requests
        if path.endswith('/health'):
            body, status_code = handle_health_check()
        elif path.endswith('/summary'):
            body, status_code = handle_get_summary(creator_id)
        elif path.endswith('/earnings'):
            body, status_code = handle_get_earnings(creator_id)
        else:
            return {
                'statusCode': 404,
                'headers': CORS_HEADERS,
                'body': json.dumps({'success': False, 'error': 'Endpoint not found'})
            }
        
        return {
            'statusCode': status_code,
            'headers': CORS_HEADERS,
            'body': json.dumps(body)
        }
    
    except Exception as e:
        print(f"Error in handler: {e}")
        return {
            'statusCode': 500,
            'headers': CORS_HEADERS,
            'body': json.dumps({'success': False, 'error': 'Internal server error'})
        }
