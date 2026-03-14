from http.server import BaseHTTPRequestHandler
import json
import os
import uuid
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse, parse_qs

SUPABASE_AVAILABLE = False
supabase_client = None

def get_supabase():
    global supabase_client, SUPABASE_AVAILABLE
    if supabase_client is not None:
        return supabase_client
    
    try:
        from supabase import create_client
        supabase_url = os.environ.get("SUPABASE_URL", "")
        supabase_key = os.environ.get("SUPABASE_KEY", "")
        
        if supabase_url and supabase_key and supabase_url != "https://your-project-id.supabase.co":
            supabase_client = create_client(supabase_url, supabase_key)
            SUPABASE_AVAILABLE = True
    except Exception as e:
        print(f"Supabase init error: {e}")
        supabase_client = None
    
    return supabase_client

class Config:
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
    PAYOUT_STORE_CREDIT = int(os.environ.get("PAYOUT_THRESHOLD_STORE_CREDIT", "2500"))
    PAYOUT_CASH = int(os.environ.get("PAYOUT_THRESHOLD_CASH", "5000"))
    COMMISSION_STANDARD = int(os.environ.get("CREATOR_COMMISSION_STANDARD", "5"))
    COMMISSION_MICRO = int(os.environ.get("CREATOR_COMMISSION_MICRO", "15"))
    COMMISSION_MEGA = int(os.environ.get("CREATOR_COMMISSION_MEGA", "50"))

config = Config()

RANK_LABELS = {
    "rookie_designer": {"label": "Rookie Designer", "emoji": "🌱"},
    "emerging_talent": {"label": "Emerging Talent", "emoji": "⭐"},
    "trendsetter": {"label": "Trendsetter", "emoji": "🔥"},
    "style_architect": {"label": "Style Architect", "emoji": "🏛️"},
    "platform_icon": {"label": "Platform Icon", "emoji": "👑"},
}

TIER_LABELS = {
    "standard": {"rate": 5, "label": "Standard Creator"},
    "micro_influencer": {"rate": 15, "label": "Micro-Influencer"},
    "mega_influencer": {"rate": 50, "label": "Mega-Influencer"},
}

class handler(BaseHTTPRequestHandler):
    def send_json_response(self, status_code, data):
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)
        
        if 'path' in params:
            path = params['path'][0]

        if path in ['/health', '/api/health', '/ping', '/api/creator_economy']:
            self.send_json_response(200, {
                "status": "healthy",
                "service": "creator-economy-api",
                "version": "2.0.0",
                "supabase_connected": SUPABASE_AVAILABLE,
                "supabase_url_set": bool(config.SUPABASE_URL and config.SUPABASE_URL != "https://your-project-id.supabase.co"),
            })
            return

        if path == '/api/creator/profile':
            user_id = params.get('user_id', [None])[0]
            if not user_id:
                self.send_json_response(400, {"success": False, "error": "user_id required"})
                return
            
            supabase = get_supabase()
            if not supabase:
                self.send_json_response(200, {
                    "success": True,
                    "data": {
                        "id": None,
                        "username": None,
                        "shopify_customer_id": user_id,
                        "balance": 0,
                        "lifetime_earnings": 0,
                        "total_items_sold": 0,
                        "commission_tier": "standard",
                        "commission_rate": config.COMMISSION_STANDARD,
                        "style_influence_rank": "rookie_designer",
                    }
                })
                return
            
            try:
                result = supabase.table("creators").select("*").eq("shopify_customer_id", user_id).execute()
                if result.data:
                    self.send_json_response(200, {"success": True, "data": result.data[0]})
                else:
                    self.send_json_response(200, {
                        "success": True,
                        "data": {
                            "id": None,
                            "username": None,
                            "shopify_customer_id": user_id,
                            "balance": 0,
                            "lifetime_earnings": 0,
                            "total_items_sold": 0,
                            "active_listings": 0,
                            "commission_tier": "standard",
                            "commission_rate": config.COMMISSION_STANDARD,
                            "style_influence_rank": "rookie_designer",
                            "social_links": {},
                        }
                    })
            except Exception as e:
                self.send_json_response(200, {
                    "success": True,
                    "data": {
                        "id": None,
                        "username": None,
                        "shopify_customer_id": user_id,
                        "balance": 0,
                        "lifetime_earnings": 0,
                        "total_items_sold": 0,
                        "active_listings": 0,
                        "commission_tier": "standard",
                        "commission_rate": config.COMMISSION_STANDARD,
                        "style_influence_rank": "rookie_designer",
                        "social_links": {},
                    }
                })
            return

        if path == '/api/creators/featured':
            supabase = get_supabase()
            if not supabase:
                self.send_json_response(200, {"success": True, "data": []})
                return
            
            try:
                result = supabase.table("creators").select("id, username, avatar_url, style_influence_rank, lifetime_earnings, total_items_sold").eq("is_mega_influencer", True).execute()
                featured = []
                for c in (result.data or []):
                    c["rank_info"] = RANK_LABELS.get(c.get("style_influence_rank", "rookie_designer"))
                    featured.append(c)
                self.send_json_response(200, {"success": True, "data": featured})
            except Exception as e:
                self.send_json_response(200, {"success": True, "data": []})
            return

        if path == '/api/creator/payout-status':
            user_id = params.get('user_id', [None])[0]
            if not user_id:
                self.send_json_response(400, {"success": False, "error": "user_id required"})
                return

            balance = 0
            supabase = get_supabase()
            if supabase:
                try:
                    result = supabase.table("creators").select("balance").eq("shopify_customer_id", user_id).execute()
                    if result.data:
                        balance = result.data[0].get("balance", 0)
                except:
                    pass

            if balance < config.PAYOUT_STORE_CREDIT:
                self.send_json_response(200, {
                    "success": True,
                    "data": {
                        "status": "LOCKED",
                        "current_balance": balance,
                        "amount_needed": config.PAYOUT_STORE_CREDIT - balance,
                        "store_credit_unlocked": False,
                        "cash_withdrawal_unlocked": False,
                    }
                })
            elif balance < config.PAYOUT_CASH:
                self.send_json_response(200, {
                    "success": True,
                    "data": {
                        "status": "STORE_CREDIT_ONLY",
                        "current_balance": balance,
                        "amount_needed": config.PAYOUT_CASH - balance,
                        "store_credit_unlocked": True,
                        "cash_withdrawal_unlocked": False,
                    }
                })
            else:
                self.send_json_response(200, {
                    "success": True,
                    "data": {
                        "status": "CASH_AVAILABLE",
                        "current_balance": balance,
                        "amount_to_cash": balance,
                        "amount_to_store_credit": balance,
                        "store_credit_unlocked": True,
                        "cash_withdrawal_unlocked": True,
                    }
                })
            return

        if path == '/api/creator/stats':
            user_id = params.get('user_id', [None])[0]
            if not user_id:
                self.send_json_response(400, {"success": False, "error": "user_id required"})
                return

            supabase = get_supabase()
            if not supabase:
                # Demo data for when Supabase is not connected
                self.send_json_response(200, {
                    "success": True,
                    "data": {
                        "total_earnings": 45280,
                        "earnings_change": 12,
                        "designs_sold": 248,
                        "sales_change": 8,
                        "rating": 4.8,
                        "rating_change": 0.2,
                        "followers": 2400,
                        "followers_change": 180,
                        "tier": "gold",
                        "tier_progress": 65,
                        "next_tier": "diamond",
                        "sales_for_next_tier": 50,
                    }
                })
                return

            try:
                result = supabase.table("creators").select("*").eq("shopify_customer_id", user_id).execute()
                if result.data:
                    creator = result.data[0]
                    self.send_json_response(200, {
                        "success": True,
                        "data": {
                            "total_earnings": creator.get("lifetime_earnings", 0),
                            "earnings_change": 0,
                            "designs_sold": creator.get("total_items_sold", 0),
                            "sales_change": 0,
                            "rating": creator.get("average_rating", 4.5),
                            "rating_change": 0,
                            "followers": creator.get("total_followers", 0),
                            "followers_change": 0,
                            "tier": creator.get("commission_tier", "standard"),
                            "tier_progress": creator.get("tier_progress", 0),
                            "next_tier": "diamond" if creator.get("commission_tier") == "gold" else "gold",
                            "sales_for_next_tier": creator.get("sales_for_next_tier", 50),
                        }
                    })
                else:
                    self.send_json_response(200, {
                        "success": True,
                        "data": {
                            "total_earnings": 0,
                            "earnings_change": 0,
                            "designs_sold": 0,
                            "sales_change": 0,
                            "rating": 0,
                            "rating_change": 0,
                            "followers": 0,
                            "followers_change": 0,
                            "tier": "standard",
                            "tier_progress": 0,
                            "next_tier": "gold",
                            "sales_for_next_tier": 50,
                        }
                    })
            except Exception as e:
                self.send_json_response(200, {
                    "success": True,
                    "data": {
                        "total_earnings": 0,
                        "earnings_change": 0,
                        "designs_sold": 0,
                        "sales_change": 0,
                        "rating": 0,
                        "rating_change": 0,
                        "followers": 0,
                        "followers_change": 0,
                        "tier": "standard",
                        "tier_progress": 0,
                        "next_tier": "gold",
                        "sales_for_next_tier": 50,
                    }
                })
            return

        if path == '/api/creator/orders':
            user_id = params.get('user_id', [None])[0]
            limit = int(params.get('limit', ['10'])[0])

            supabase = get_supabase()
            if not supabase:
                # Demo data for when Supabase is not connected
                demo_orders = [
                    {"id": "MN-2847", "product_name": "Floral Summer Dress", "amount": 1299, "status": "completed", "created_at": (datetime.now() - timedelta(hours=2)).isoformat()},
                    {"id": "MN-2845", "product_name": "Urban Graphic Tee", "amount": 899, "status": "completed", "created_at": (datetime.now() - timedelta(days=1)).isoformat()},
                    {"id": "MN-2842", "product_name": "Denim Jacket Classic", "amount": 2499, "status": "processing", "created_at": (datetime.now() - timedelta(days=2)).isoformat()},
                    {"id": "MN-2839", "product_name": "Straight Fit Jeans", "amount": 1799, "status": "completed", "created_at": (datetime.now() - timedelta(days=3)).isoformat()},
                    {"id": "MN-2835", "product_name": "Casual Hoodie", "amount": 1499, "status": "completed", "created_at": (datetime.now() - timedelta(days=4)).isoformat()},
                ]
                self.send_json_response(200, {"success": True, "data": demo_orders[:limit]})
                return

            try:
                result = supabase.table("creator_orders").select("*").eq("creator_id", user_id).order("created_at", desc=True).limit(limit).execute()
                orders = []
                for order in (result.data or []):
                    orders.append({
                        "id": order.get("order_id"),
                        "product_name": order.get("product_name", "Design Sale"),
                        "amount": order.get("amount", 0),
                        "status": order.get("status", "completed"),
                        "created_at": order.get("created_at"),
                    })
                self.send_json_response(200, {"success": True, "data": orders})
            except Exception as e:
                self.send_json_response(200, {"success": True, "data": []})
            return

        if path == '/api/creator/analytics':
            user_id = params.get('user_id', [None])[0]

            supabase = get_supabase()
            if not supabase:
                # Demo data for when Supabase is not connected
                self.send_json_response(200, {
                    "success": True,
                    "data": {
                        "monthly_earnings": [
                            {"month": "Oct", "amount": 8500},
                            {"month": "Nov", "amount": 12300},
                            {"month": "Dec", "amount": 15800},
                            {"month": "Jan", "amount": 11200},
                            {"month": "Feb", "amount": 18480},
                        ],
                        "top_products": [
                            {"name": "Floral Summer Dress", "sales": 45, "revenue": 58455},
                            {"name": "Urban Graphic Tee", "sales": 38, "revenue": 34162},
                            {"name": "Denim Jacket Classic", "sales": 22, "revenue": 54978},
                        ],
                        "demographics": {
                            "ages": {"18-24": 35, "25-34": 45, "35-44": 15, "45+": 5},
                            "locations": {"Mumbai": 30, "Delhi": 25, "Bangalore": 20, "Other": 25},
                        },
                    }
                })
                return

            try:
                result = supabase.table("creators").select("*").eq("shopify_customer_id", user_id).execute()
                if result.data:
                    creator = result.data[0]
                    self.send_json_response(200, {
                        "success": True,
                        "data": creator.get("analytics", {
                            "monthly_earnings": [],
                            "top_products": [],
                            "demographics": {},
                        })
                    })
                else:
                    self.send_json_response(200, {"success": True, "data": {}})
            except Exception as e:
                self.send_json_response(200, {"success": True, "data": {}})
            return

        self.send_json_response(404, {"error": "Not found"})

    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(content_length).decode('utf-8'))
        except:
            self.send_json_response(400, {"success": False, "error": "Invalid JSON"})
            return

        parsed = urlparse(self.path)
        path = parsed.path
        
        if 'path' in body:
            path = body['path']

        if path == '/api/creator/register':
            user_id = body.get('user_id')
            email = body.get('email')
            username = body.get('username')
            
            if not user_id or not email or not username:
                self.send_json_response(400, {"success": False, "error": "user_id, email, username required"})
                return
            
            username = re.sub(r'[^a-zA-Z0-9_]', '', username).lower()
            
            supabase = get_supabase()
            if not supabase:
                self.send_json_response(200, {"success": True, "message": "Registered (demo mode)"})
                return
            
            try:
                existing = supabase.table("creators").select("id").eq("shopify_customer_id", user_id).execute()
                if existing.data:
                    self.send_json_response(200, {"success": True, "message": "Already registered"})
                    return
                
                data = {
                    "shopify_customer_id": user_id,
                    "email": email,
                    "username": username,
                    "balance": 0,
                    "lifetime_earnings": 0,
                    "total_items_sold": 0,
                    "commission_tier": "standard",
                    "commission_rate": config.COMMISSION_STANDARD,
                    "style_influence_rank": "rookie_designer",
                    "is_mega_influencer": False,
                    "created_at": datetime.utcnow().isoformat(),
                }
                supabase.table("creators").insert(data).execute()
                self.send_json_response(200, {"success": True, "message": "Registered successfully"})
            except Exception as e:
                self.send_json_response(200, {"success": True, "message": "Registered (error handling)"})
            return

        if path == '/api/creator/social/link':
            user_id = body.get('user_id')
            platform = body.get('platform')
            handle = body.get('handle')
            followers = body.get('followers', 0)
            
            if not user_id or not platform or not handle:
                self.send_json_response(400, {"success": False, "error": "user_id, platform, handle required"})
                return
            
            supabase = get_supabase()
            if not supabase:
                is_mega = followers >= 500000
                self.send_json_response(200, {
                    "success": True,
                    "message": f"Linked {platform}",
                    "data": {"is_mega_influencer": is_mega}
                })
                return
            
            try:
                result = supabase.table("creators").select("social_links").eq("shopify_customer_id", user_id).execute()
                social_links = {}
                if result.data and result.data[0].get("social_links"):
                    social_links = result.data[0]["social_links"]
                
                social_links[platform] = {"handle": handle, "followers": followers}
                
                is_mega = (platform == "instagram" and followers >= 500000) or \
                          (platform == "youtube" and followers >= 250000) or \
                          (platform == "twitter" and followers >= 150000)
                
                supabase.table("creators").update({
                    "social_links": social_links,
                    "is_mega_influencer": is_mega,
                    "commission_tier": "mega_influencer" if is_mega else "standard",
                    "commission_rate": config.COMMISSION_MEGA if is_mega else config.COMMISSION_STANDARD,
                }).eq("shopify_customer_id", user_id).execute()
                
                self.send_json_response(200, {
                    "success": True,
                    "message": f"Linked {platform}",
                    "data": {"is_mega_influencer": is_mega}
                })
            except Exception as e:
                self.send_json_response(200, {"success": True, "message": "Linked (demo mode)"})
            return

        self.send_json_response(404, {"error": "Not found"})
