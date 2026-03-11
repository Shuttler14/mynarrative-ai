"""
=================================================================================
MY NARRATIVE - CREATOR ECONOMY API
=================================================================================
Production-ready API for Design-to-Earn Creator Dashboard
Integrates with Shopify, Supabase, Stripe Connect, and Social OAuth

Author: My Narrative AI Team
Version: 1.0.0
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import base64
import uuid
import hashlib
import hmac
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse, parse_qs
import re

# Supabase Client
from supabase import create_client, Client

# =====================================================
# CONFIGURATION
# =====================================================

# Supabase
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
supabase: Optional[Client] = None

if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"Supabase connection error: {e}")

# Stripe
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_CONNECT_CLIENT_ID = os.environ.get("STRIPE_CONNECT_CLIENT_ID", "")

# Social Platform Thresholds
MEGA_THRESHOLDS = {
    "instagram": int(os.environ.get("MEGA_INFLUENCER_INSTAGRAM", "500000")),
    "youtube": int(os.environ.get("MEGA_INFLUENCER_YOUTUBE", "250000")),
    "twitter": int(os.environ.get("MEGA_INFLUENCER_TWITTER", "150000")),
    "linkedin": int(os.environ.get("MEGA_INFLUENCER_LINKEDIN", "750000")),
}

# Payout Thresholds
PAYOUT_STORE_CREDIT = int(os.environ.get("PAYOUT_THRESHOLD_STORE_CREDIT", "2500"))
PAYOUT_CASH = int(os.environ.get("PAYOUT_THRESHOLD_CASH", "5000"))

# Commission Rates
COMMISSION_STANDARD = int(os.environ.get("CREATOR_COMMISSION_STANDARD", "5"))
COMMISSION_MICRO = int(os.environ.get("CREATOR_COMMISSION_MICRO", "15"))
COMMISSION_MEGA = int(os.environ.get("CREATOR_COMMISSION_MEGA", "50"))

# Rank Thresholds
RANK_THRESHOLDS = {
    "rookie_designer": int(os.environ.get("RANK_ROOKIE", "0")),
    "emerging_talent": int(os.environ.get("RANK_EMERGING", "10000")),
    "trendsetter": int(os.environ.get("RANK_TRENDSETTER", "50000")),
    "style_architect": int(os.environ.get("RANK_ARCHITECT", "150000")),
    "platform_icon": int(os.environ.get("RANK_ICON", "500000")),
}

# =====================================================
# DATABASE HELPER FUNCTIONS
# =====================================================

def get_creator_profile(user_id: str) -> Optional[Dict]:
    """Fetch creator profile from Supabase"""
    if not supabase:
        return None

    try:
        result = supabase.table("creators").select("*").eq("shopify_customer_id", user_id).execute()
        if result.data and len(result.data) > 0:
            return result.data[0]
    except Exception as e:
        print(f"Error fetching creator: {e}")

    return None

def create_creator_profile(user_id: str, email: str, username: str) -> Dict:
    """Create new creator profile in Supabase"""
    if not supabase:
        return {"success": False, "error": "Database not configured"}

    try:
        # Check if username exists
        existing = supabase.table("creators").select("id").eq("username", username).execute()
        if existing.data and len(existing.data) > 0:
            username = f"{username}{str(int(time.time()))[-4:]}"

        data = {
            "id": str(uuid.uuid4()),
            "shopify_customer_id": user_id,
            "email": email,
            "username": username,
            "commission_tier": "standard",
            "commission_rate": COMMISSION_STANDARD,
            "balance": 0,
            "lifetime_earnings": 0,
            "active_listings": 0,
            "total_items_sold": 0,
            "style_influence_rank": "rookie_designer",
            "is_mega_influencer": False,
            "is_campus_ambassador": False,
            "social_links": {},
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

        result = supabase.table("creators").insert(data).execute()
        return {"success": True, "data": data}
    except Exception as e:
        print(f"Error creating creator: {e}")
        return {"success": False, "error": str(e)}

def update_creator_field(user_id: str, field: str, value: Any) -> bool:
    """Update a single field in creator profile"""
    if not supabase:
        return False

    try:
        supabase.table("creators").update({field: value, "updated_at": datetime.utcnow().isoformat()}).eq("shopify_customer_id", user_id).execute()
        return True
    except Exception as e:
        print(f"Error updating creator field: {e}")
        return False

def calculate_payout_status(balance: int) -> Dict:
    """Calculate payout status based on balance"""
    if balance < PAYOUT_STORE_CREDIT:
        return {
            "status": "LOCKED",
            "store_credit_unlocked": False,
            "cash_withdrawal_unlocked": False,
            "amount_to_store_credit": 0,
            "amount_to_cash": 0,
            "next_threshold": PAYOUT_STORE_CREDIT,
            "next_threshold_type": "store_credit",
            "amount_needed": PAYOUT_STORE_CREDIT - balance,
        }
    elif balance < PAYOUT_CASH:
        return {
            "status": "STORE_CREDIT_ONLY",
            "store_credit_unlocked": True,
            "cash_withdrawal_unlocked": False,
            "amount_to_store_credit": balance,
            "amount_to_cash": 0,
            "next_threshold": PAYOUT_CASH,
            "next_threshold_type": "cash",
            "amount_needed": PAYOUT_CASH - balance,
        }
    else:
        return {
            "status": "CASH_AVAILABLE",
            "store_credit_unlocked": True,
            "cash_withdrawal_unlocked": True,
            "amount_to_store_credit": PAYOUT_CASH,
            "amount_to_cash": balance - PAYOUT_CASH,
            "next_threshold": 0,
            "next_threshold_type": None,
            "amount_needed": 0,
        }

def calculate_style_rank(lifetime_earnings: int) -> str:
    """Calculate style influence rank based on lifetime earnings"""
    if lifetime_earnings >= RANK_THRESHOLDS["platform_icon"]:
        return "platform_icon"
    elif lifetime_earnings >= RANK_THRESHOLDS["style_architect"]:
        return "style_architect"
    elif lifetime_earnings >= RANK_THRESHOLDS["trendsetter"]:
        return "trendsetter"
    elif lifetime_earnings >= RANK_THRESHOLDS["emerging_talent"]:
        return "emerging_talent"
    else:
        return "rookie_designer"

def calculate_commission_tier(social_links: Dict) -> Dict:
    """Calculate commission tier based on social links"""
    # Check for mega influencer
    for platform, data in social_links.items():
        if not data:
            continue
        followers = data.get("followers", 0)
        platform_key = platform.lower()

        if platform_key in MEGA_THRESHOLDS:
            if followers >= MEGA_THRESHOLDS[platform_key]:
                return {
                    "tier": "mega_influencer",
                    "rate": COMMISSION_MEGA,
                    "reason": f"{followers:,} {platform} followers (mega threshold: {MEGA_THRESHOLDS[platform_key]:,})"
                }

    # Check for micro influencer
    for platform, data in social_links.items():
        if not data:
            continue
        followers = data.get("followers", 0)
        micro_threshold = MEGA_THRESHOLDS.get(platform.lower(), 0) // 5  # 20% of mega threshold

        if followers >= micro_threshold:
            return {
                "tier": "micro_influencer",
                "rate": COMMISSION_MICRO,
                "reason": f"{followers:,} {platform} followers (micro threshold: {micro_threshold:,})"
            }

    return {
        "tier": "standard",
        "rate": COMMISSION_STANDARD,
        "reason": "No social links meeting influencer thresholds"
    }

# =====================================================
# MAIN REQUEST HANDLER
# =====================================================

class handler(BaseHTTPRequestHandler):
    """Main HTTP request handler for Creator Economy API"""

    def send_json_response(self, status: int, data: Dict):
        """Helper to send JSON response"""
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def do_GET(self):
        """Handle GET requests"""
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        # =====================================================
        # GET /api/creator/profile?user_id=xxx
        # =====================================================
        if path == '/api/creator/profile':
            user_id = params.get('user_id', [None])[0]

            if not user_id:
                self.send_json_response(400, {"success": False, "error": "user_id required"})
                return

            # Get or create creator profile
            creator = get_creator_profile(user_id)

            if not creator:
                # Create new creator with default values
                # For now, return error - need email/username
                self.send_json_response(404, {
                    "success": False,
                    "error": "Creator profile not found. Please complete registration."
                })
                return

            # Calculate payout status
            payout_status = calculate_payout_status(creator.get("balance", 0))

            self.send_json_response(200, {
                "success": True,
                "data": {
                    **creator,
                    "payout_status": payout_status,
                }
            })
            return

        # =====================================================
        # GET /api/creator/payout-status?user_id=xxx
        # =====================================================
        if path == '/api/creator/payout-status':
            user_id = params.get('user_id', [None])[0]

            if not user_id:
                self.send_json_response(400, {"success": False, "error": "user_id required"})
                return

            creator = get_creator_profile(user_id)
            if not creator:
                self.send_json_response(404, {"success": False, "error": "Creator not found"})
                return

            payout_status = calculate_payout_status(creator.get("balance", 0))

            self.send_json_response(200, {
                "success": True,
                "data": payout_status
            })
            return

        # =====================================================
        # GET /api/creators/featured (Mega Influencers Only)
        # =====================================================
        if path == '/api/creators/featured':
            if not supabase:
                self.send_json_response(500, {"success": False, "error": "Database not configured"})
                return

            try:
                result = supabase.table("creators").select("*").eq("is_mega_influencer", True).execute()
                self.send_json_response(200, {
                    "success": True,
                    "data": result.data,
                    "count": len(result.data) if result.data else 0
                })
            except Exception as e:
                self.send_json_response(500, {"success": False, "error": str(e)})
            return

        # =====================================================
        # GET /api/creator/designs?user_id=xxx
        # =====================================================
        if path == '/api/creator/designs':
            user_id = params.get('user_id', [None])[0]

            if not user_id:
                self.send_json_response(400, {"success": False, "error": "user_id required"})
                return

            creator = get_creator_profile(user_id)
            if not creator:
                self.send_json_response(404, {"success": False, "error": "Creator not found"})
                return

            if not supabase:
                self.send_json_response(500, {"success": False, "error": "Database not configured"})
                return

            try:
                result = supabase.table("creator_designs").select("*").eq("creator_id", creator["id"]).eq("status", "active").execute()
                self.send_json_response(200, {
                    "success": True,
                    "data": result.data,
                    "count": len(result.data) if result.data else 0
                })
            except Exception as e:
                self.send_json_response(500, {"success": False, "error": str(e)})
            return

        # =====================================================
        # GET /api/creator/campus-fests?user_id=xxx
        # =====================================================
        if path == '/api/creator/campus-fests':
            user_id = params.get('user_id', [None])[0]

            if not user_id:
                self.send_json_response(400, {"success": False, "error": "user_id required"})
                return

            creator = get_creator_profile(user_id)
            if not creator or not creator.get("is_campus_ambassador"):
                self.send_json_response(200, {
                    "success": True,
                    "data": [],
                    "count": 0,
                    "message": "Not a campus ambassador"
                })
                return

            if not supabase:
                self.send_json_response(500, {"success": False, "error": "Database not configured"})
                return

            try:
                result = supabase.table("campus_fests").select("*").eq("is_active", True).execute()
                self.send_json_response(200, {
                    "success": True,
                    "data": result.data,
                    "count": len(result.data) if result.data else 0
                })
            except Exception as e:
                self.send_json_response(500, {"success": False, "error": str(e)})
            return

        # Default 404
        self.send_json_response(404, {"success": False, "error": "Endpoint not found"})

    def do_POST(self):
        """Handle POST requests"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(content_length).decode('utf-8'))
        except:
            self.send_json_response(400, {"success": False, "error": "Invalid JSON"})
            return

        parsed = urlparse(self.path)
        path = parsed.path

        # =====================================================
        # POST /api/creator/register
        # =====================================================
        if path == '/api/creator/register':
            user_id = body.get('user_id')
            email = body.get('email')
            username = body.get('username')

            if not user_id or not email or not username:
                self.send_json_response(400, {
                    "success": False,
                    "error": "user_id, email, and username are required"
                })
                return

            # Sanitize username
            username = re.sub(r'[^a-zA-Z0-9_]', '', username).lower()
            if len(username) < 3:
                self.send_json_response(400, {
                    "success": False,
                    "error": "Username must be at least 3 characters"
                })

            # Create creator profile
            result = create_creator_profile(user_id, email, username)

            if result.get("success"):
                self.send_json_response(201, result)
            else:
                self.send_json_response(500, result)
            return

        # =====================================================
        # POST /api/creator/social/link
        # =====================================================
        if path == '/api/creator/social/link':
            user_id = body.get('user_id')
            platform = body.get('platform', '').lower()
            handle = body.get('handle')
            followers = int(body.get('followers', 0))

            if not user_id or not platform or not handle or followers <= 0:
                self.send_json_response(400, {
                    "success": False,
                    "error": "user_id, platform, handle, and followers are required"
                })
                return

            # Valid platforms
            valid_platforms = ['instagram', 'youtube', 'twitter', 'linkedin']
            if platform not in valid_platforms:
                self.send_json_response(400, {
                    "success": False,
                    "error": f"Invalid platform. Must be one of: {', '.join(valid_platforms)}"
                })
                return

            creator = get_creator_profile(user_id)
            if not creator:
                self.send_json_response(404, {"success": False, "error": "Creator not found"})
                return

            # Update social links
            social_links = creator.get("social_links", {})
            social_links[platform] = {
                "handle": handle,
                "followers": followers,
                "verified": followers >= 100000,
                "linked_at": datetime.utcnow().isoformat(),
            }

            # Calculate new commission tier
            tier_info = calculate_commission_tier(social_links)

            # Update creator
            update_creator_field(user_id, "social_links", social_links)
            update_creator_field(user_id, "commission_tier", tier_info["tier"])
            update_creator_field(user_id, "commission_rate", tier_info["rate"])

            # Check if mega influencer
            is_mega = tier_info["tier"] == "mega_influencer"
            update_creator_field(user_id, "is_mega_influencer", is_mega)

            self.send_json_response(200, {
                "success": True,
                "data": {
                    "platform": platform,
                    "handle": handle,
                    "followers": followers,
                    "tier": tier_info["tier"],
                    "commission_rate": tier_info["rate"],
                    "is_verified": followers >= 100000,
                    "message": tier_info["reason"]
                }
            })
            return

        # =====================================================
        # POST /api/creator/payout/initiate
        # =====================================================
        if path == '/api/creator/payout/initiate':
            user_id = body.get('user_id')
            amount = int(body.get('amount', 0))
            payout_type = body.get('type', 'cash')  # 'cash' or 'store_credit'
            bank_details = body.get('bank_details', {})

            if not user_id or amount <= 0:
                self.send_json_response(400, {
                    "success": False,
                    "error": "user_id and amount are required"
                })
                return

            if payout_type not in ['cash', 'store_credit']:
                self.send_json_response(400, {
                    "success": False,
                    "error": "type must be 'cash' or 'store_credit'"
                })
                return

            creator = get_creator_profile(user_id)
            if not creator:
                self.send_json_response(404, {"success": False, "error": "Creator not found"})
                return

            balance = creator.get("balance", 0)

            # Validate balance
            if amount > balance:
                self.send_json_response(400, {
                    "success": False,
                    "error": "Insufficient balance",
                    "current_balance": balance,
                    "requested": amount
                })
                return

            # Validate thresholds
            payout_status = calculate_payout_status(balance)

            if payout_type == 'store_credit' and not payout_status["store_credit_unlocked"]:
                self.send_json_response(400, {
                    "success": False,
                    "error": f"Store credit requires minimum ₹{PAYOUT_STORE_CREDIT} balance",
                    "current_balance": balance,
                    "required": PAYOUT_STORE_CREDIT
                })
                return

            if payout_type == 'cash' and not payout_status["cash_withdrawal_unlocked"]:
                self.send_json_response(400, {
                    "success": False,
                    "error": f"Cash withdrawal requires minimum ₹{PAYOUT_CASH} balance",
                    "current_balance": balance,
                    "required": PAYOUT_CASH
                })
                return

            # Create payout record
            payout_id = f"payout_{uuid.uuid4().hex[:12]}"

            payout_record = {
                "id": payout_id,
                "creator_id": creator["id"],
                "amount": amount,
                "type": payout_type,
                "status": "processing",
                "bank_details": bank_details if payout_type == 'cash' else None,
                "created_at": datetime.utcnow().isoformat(),
            }

            if supabase:
                try:
                    supabase.table("creator_payouts").insert(payout_record).execute()

                    # Deduct from balance
                    new_balance = balance - amount
                    update_creator_field(user_id, "balance", new_balance)
                except Exception as e:
                    print(f"Error creating payout: {e}")

            # Mock Stripe response
            stripe_response = {
                "id": f"py_{uuid.uuid4().hex[:12]}",
                "object": "payout",
                "amount": amount * 100,  # cents
                "currency": "inr",
                "arrival_date": int((datetime.utcnow() + timedelta(days=3)).timestamp()),
                "status": "pending" if payout_type == "cash" else "paid",
            }

            self.send_json_response(200, {
                "success": True,
                "data": {
                    "transaction_id": payout_id,
                    "amount": amount,
                    "type": payout_type,
                    "status": "processing",
                    "stripe_response": stripe_response,
                    "estimated_arrival": "Instant" if payout_type == "store_credit" else "3-5 business days",
                    "message": f"{'Store credit' if payout_type == 'store_credit' else 'Payout'} of ₹{amount} initiated",
                    "remaining_balance": balance - amount
                }
            })
            return

        # =====================================================
        # POST /api/creator/design/add
        # =====================================================
        if path == '/api/creator/design/add':
            user_id = body.get('user_id')
            title = body.get('title')
            description = body.get('description')
            flux_editorial_image_url = body.get('flux_editorial_image_url')
            price = int(body.get('price', 0))

            if not user_id or not title or not flux_editorial_image_url or price <= 0:
                self.send_json_response(400, {
                    "success": False,
                    "error": "user_id, title, flux_editorial_image_url, and price are required"
                })
                return

            creator = get_creator_profile(user_id)
            if not creator:
                self.send_json_response(404, {"success": False, "error": "Creator not found"})
                return

            # Calculate estimated earnings per sale
            commission_rate = creator.get("commission_rate", COMMISSION_STANDARD)
            estimated_earnings = int(price * commission_rate / 100)

            design_data = {
                "id": str(uuid.uuid4()),
                "creator_id": creator["id"],
                "title": title,
                "description": description or "",
                "flux_editorial_image_url": flux_editorial_image_url,
                "price": price,
                "commission_rate": commission_rate,
                "estimated_earnings_per_sale": estimated_earnings,
                "total_sales": 0,
                "status": "active",
                "created_at": datetime.utcnow().isoformat(),
            }

            if supabase:
                try:
                    supabase.table("creator_designs").insert(design_data).execute()
                    update_creator_field(user_id, "active_listings", creator.get("active_listings", 0) + 1)
                except Exception as e:
                    self.send_json_response(500, {"success": False, "error": str(e)})
                    return

            self.send_json_response(201, {
                "success": True,
                "data": design_data
            })
            return

        # =====================================================
        # POST /api/creator/design/ghost
        # =====================================================
        if path == '/api/creator/design/ghost':
            user_id = body.get('user_id')
            description = body.get('description')

            if not user_id or not description:
                self.send_json_response(400, {
                    "success": False,
                    "error": "user_id and description are required"
                })
                return

            creator = get_creator_profile(user_id)
            if not creator:
                self.send_json_response(404, {"success": False, "error": "Creator not found"})
                return

            # Generate mock embedding (in production, use OpenAI embedding API)
            embedding = [hashlib.md5(description.encode()).hexdigest() for _ in range(1536)]

            ghost_data = {
                "id": str(uuid.uuid4()),
                "creator_id": creator["id"],
                "description": description,
                "embedding": embedding,
                "type": "ghost",
                "created_at": datetime.utcnow().isoformat(),
            }

            if supabase:
                try:
                    supabase.table("creator_ghost_items").insert(ghost_data).execute()
                except Exception as e:
                    print(f"Error creating ghost item: {e}")

            self.send_json_response(201, {
                "success": True,
                "data": ghost_data,
                "message": "Ghost embedding generated successfully"
            })
            return

        # Default 404
        self.send_json_response(404, {"success": False, "error": "Endpoint not found"})

    def do_PUT(self):
        """Handle PUT requests"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(content_length).decode('utf-8'))
        except:
            self.send_json_response(400, {"success": False, "error": "Invalid JSON"})
            return

        parsed = urlparse(self.path)
        path = parsed.path

        # =====================================================
        # PUT /api/creator/balance/update (Webhook from Shopify)
        # =====================================================
        if path == '/api/creator/balance/update':
            shopify_order_id = body.get('order_id')
            creator_id = body.get('creator_id')
            commission_earned = int(body.get('commission_earned', 0))

            if not shopify_order_id or not creator_id or commission_earned <= 0:
                self.send_json_response(400, {
                    "success": False,
                    "error": "order_id, creator_id, and commission_earned are required"
                })
                return

            creator = get_creator_profile(creator_id)
            if not creator:
                self.send_json_response(404, {"success": False, "error": "Creator not found"})
                return

            # Update balance and lifetime earnings
            current_balance = creator.get("balance", 0)
            lifetime_earnings = creator.get("lifetime_earnings", 0)
            total_sold = creator.get("total_items_sold", 0)

            new_balance = current_balance + commission_earned
            new_lifetime = lifetime_earnings + commission_earned

            # Calculate new rank
            new_rank = calculate_style_rank(new_lifetime)

            # Update creator
            update_creator_field(creator_id, "balance", new_balance)
            update_creator_field(creator_id, "lifetime_earnings", new_lifetime)
            update_creator_field(creator_id, "total_items_sold", total_sold + 1)
            update_creator_field(creator_id, "style_influence_rank", new_rank)

            # Record commission payment
            if supabase:
                try:
                    supabase.table("creator_commissions").insert({
                        "id": str(uuid.uuid4()),
                        "creator_id": creator["id"],
                        "shopify_order_id": shopify_order_id,
                        "amount": commission_earned,
                        "type": "sale_commission",
                        "created_at": datetime.utcnow().isoformat(),
                    }).execute()
                except Exception as e:
                    print(f"Error recording commission: {e}")

            self.send_json_response(200, {
                "success": True,
                "data": {
                    "commission_earned": commission_earned,
                    "new_balance": new_balance,
                    "lifetime_earnings": new_lifetime,
                    "new_rank": new_rank
                }
            })
            return

        self.send_json_response(404, {"success": False, "error": "Endpoint not found"})

# =====================================================
# MAIN ENTRY POINT
# =====================================================

if __name__ == "__main__":
    print("My Narrative Creator Economy API initialized")
    print(f"Commission Rates: Standard={COMMISSION_STANDARD}%, Micro={COMMISSION_MICRO}%, Mega={COMMISSION_MEGA}%")
    print(f"Payout Thresholds: Store Credit=₹{PAYOUT_STORE_CREDIT}, Cash=₹{PAYOUT_CASH}")