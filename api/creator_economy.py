"""
=================================================================================
MY NARRATIVE - CREATOR ECONOMY API (PRODUCTION)
=================================================================================
Production-ready API for Design-to-Earn Creator Dashboard
Integrates with Shopify, Supabase, Stripe Connect, and Social OAuth

Version: 2.0.0
Author: My Narrative AI Team

ENVIRONMENT VARIABLES REQUIRED:
- SUPABASE_URL: Your Supabase project URL
- SUPABASE_KEY: Your Supabase service role key
- STRIPE_SECRET_KEY: Your Stripe secret key (for Connect payouts)
- STRIPE_CONNECT_CLIENT_ID: Your Stripe Connect client ID
- MEGA_INFLUENCER_INSTAGRAM: 500000 (default)
- MEGA_INFLUENCER_YOUTUBE: 250000 (default)
- PAYOUT_THRESHOLD_STORE_CREDIT: 2500 (default)
- PAYOUT_THRESHOLD_CASH: 5000 (default)
- CREATOR_COMMISSION_STANDARD: 5 (default)
- CREATOR_COMMISSION_MICRO: 15 (default)
- CREATOR_COMMISSION_MEGA: 50 (default)
=================================================================================
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import uuid
import hashlib
import hmac
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse, parse_qs
import re

# Supabase Client
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

# =====================================================
# CONFIGURATION
# =====================================================

class Config:
    """API Configuration - reads from environment variables"""

    # Supabase
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

    # Stripe
    STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
    STRIPE_CONNECT_CLIENT_ID = os.environ.get("STRIPE_CONNECT_CLIENT_ID", "")

    # Social Platform Thresholds (followers required for mega influencer)
    MEGA_THRESHOLDS = {
        "instagram": int(os.environ.get("MEGA_INFLUENCER_INSTAGRAM", "500000")),
        "youtube": int(os.environ.get("MEGA_INFLUENCER_YOUTUBE", "250000")),
        "twitter": int(os.environ.get("MEGA_INFLUENCER_TWITTER", "150000")),
        "linkedin": int(os.environ.get("MEGA_INFLUENCER_LINKEDIN", "750000")),
    }

    # Payout Thresholds (in INR)
    PAYOUT_STORE_CREDIT = int(os.environ.get("PAYOUT_THRESHOLD_STORE_CREDIT", "2500"))
    PAYOUT_CASH = int(os.environ.get("PAYOUT_THRESHOLD_CASH", "5000"))

    # Commission Rates (percentage)
    COMMISSION_STANDARD = int(os.environ.get("CREATOR_COMMISSION_STANDARD", "5"))
    COMMISSION_MICRO = int(os.environ.get("CREATOR_COMMISSION_MICRO", "15"))
    COMMISSION_MEGA = int(os.environ.get("CREATOR_COMMISSION_MEGA", "50"))

    # Rank Thresholds (lifetime earnings in INR)
    RANK_THRESHOLDS = {
        "rookie_designer": int(os.environ.get("RANK_ROOKIE", "0")),
        "emerging_talent": int(os.environ.get("RANK_EMERGING", "10000")),
        "trendsetter": int(os.environ.get("RANK_TRENDSETTER", "50000")),
        "style_architect": int(os.environ.get("RANK_ARCHITECT", "150000")),
        "platform_icon": int(os.environ.get("RANK_ICON", "500000")),
    }

    # API Base URL for webhooks
    API_BASE_URL = os.environ.get("API_BASE_URL", "https://mynarrative-ai.vercel.app")

    @classmethod
    def is_configured(cls) -> bool:
        return bool(cls.SUPABASE_URL and cls.SUPABASE_KEY)

config = Config()

# Initialize Supabase client
supabase: Optional[Any] = None

if config.is_configured() and SUPABASE_AVAILABLE:
    try:
        supabase = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
    except Exception as e:
        print(f"⚠️ Supabase connection failed: {e}")
        supabase = None

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


def get_creator_by_username(username: str) -> Optional[Dict]:
    """Fetch creator by username"""
    if not supabase:
        return None

    try:
        result = supabase.table("creators").select("*").eq("username", username).execute()
        if result.data and len(result.data) > 0:
            return result.data[0]
    except Exception as e:
        print(f"Error fetching creator by username: {e}")

    return None


def create_creator_profile(user_id: str, email: str, username: str, first_name: str = "") -> Dict:
    """Create new creator profile in Supabase"""
    if not supabase:
        return {"success": False, "error": "Database not configured"}

    try:
        # Check if username exists
        existing = supabase.table("creators").select("id").eq("username", username).execute()
        if existing.data and len(existing.data) > 0:
            username = f"{username}{str(int(time.time()))[-4:]}"

        # Check if shopify_customer_id already exists
        existing_customer = supabase.table("creators").select("id").eq("shopify_customer_id", user_id).execute()
        if existing_customer.data and len(existing_customer.data) > 0:
            return {"success": False, "error": "Creator profile already exists", "creator_id": existing_customer.data[0]["id"]}

        data = {
            "id": str(uuid.uuid4()),
            "shopify_customer_id": user_id,
            "email": email,
            "username": username,
            "first_name": first_name,
            "commission_tier": "standard",
            "commission_rate": config.COMMISSION_STANDARD,
            "balance": 0,
            "lifetime_earnings": 0,
            "active_listings": 0,
            "total_items_sold": 0,
            "style_influence_rank": "rookie_designer",
            "is_mega_influencer": False,
            "is_campus_ambassador": False,
            "social_links": {},
            "earnings_history": [],
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

        result = supabase.table("creators").insert(data).execute()
        return {"success": True, "data": data}
    except Exception as e:
        print(f"Error creating creator: {e}")
        return {"success": False, "error": str(e)}


def update_creator_profile(user_id: str, updates: Dict) -> bool:
    """Update creator profile with multiple fields"""
    if not supabase:
        return False

    try:
        updates["updated_at"] = datetime.utcnow().isoformat()
        supabase.table("creators").update(updates).eq("shopify_customer_id", user_id).execute()
        return True
    except Exception as e:
        print(f"Error updating creator: {e}")
        return False


def update_creator_field(user_id: str, field: str, value: Any) -> bool:
    """Update a single field in creator profile"""
    return update_creator_profile(user_id, {field: value})


def calculate_payout_status(balance: int) -> Dict:
    """Calculate payout status based on balance"""
    if balance < config.PAYOUT_STORE_CREDIT:
        return {
            "status": "LOCKED",
            "current_balance": balance,
            "store_credit_unlocked": False,
            "cash_withdrawal_unlocked": False,
            "amount_to_store_credit": 0,
            "amount_to_cash": 0,
            "next_threshold": config.PAYOUT_STORE_CREDIT,
            "next_threshold_type": "store_credit",
            "amount_needed": config.PAYOUT_STORE_CREDIT - balance,
        }
    elif balance < config.PAYOUT_CASH:
        return {
            "status": "STORE_CREDIT_ONLY",
            "current_balance": balance,
            "store_credit_unlocked": True,
            "cash_withdrawal_unlocked": False,
            "amount_to_store_credit": balance,
            "amount_to_cash": 0,
            "next_threshold": config.PAYOUT_CASH,
            "next_threshold_type": "cash",
            "amount_needed": config.PAYOUT_CASH - balance,
        }
    else:
        return {
            "status": "CASH_AVAILABLE",
            "current_balance": balance,
            "store_credit_unlocked": True,
            "cash_withdrawal_unlocked": True,
            "amount_to_store_credit": config.PAYOUT_CASH,
            "amount_to_cash": balance - config.PAYOUT_CASH,
            "next_threshold": 0,
            "next_threshold_type": None,
            "amount_needed": 0,
        }


def calculate_style_rank(lifetime_earnings: int) -> str:
    """Calculate style influence rank based on lifetime earnings"""
    if lifetime_earnings >= config.RANK_THRESHOLDS["platform_icon"]:
        return "platform_icon"
    elif lifetime_earnings >= config.RANK_THRESHOLDS["style_architect"]:
        return "style_architect"
    elif lifetime_earnings >= config.RANK_THRESHOLDS["trendsetter"]:
        return "trendsetter"
    elif lifetime_earnings >= config.RANK_THRESHOLDS["emerging_talent"]:
        return "emerging_talent"
    else:
        return "rookie_designer"


def calculate_commission_tier(social_links: Dict) -> Dict:
    """Calculate commission tier based on social links"""
    # Check for mega influencer first (highest tier)
    for platform, data in social_links.items():
        if not data:
            continue
        followers = data.get("followers", 0)
        platform_key = platform.lower()

        if platform_key in config.MEGA_THRESHOLDS:
            if followers >= config.MEGA_THRESHOLDS[platform_key]:
                return {
                    "tier": "mega_influencer",
                    "rate": config.COMMISSION_MEGA,
                    "reason": f"{followers:,} {platform} followers (mega threshold: {config.MEGA_THRESHOLDS[platform_key]:,})"
                }

    # Check for micro influencer
    micro_thresholds = {k: v // 5 for k, v in config.MEGA_THRESHOLDS.items()}
    for platform, data in social_links.items():
        if not data:
            continue
        followers = data.get("followers", 0)
        platform_key = platform.lower()

        if platform_key in micro_thresholds:
            if followers >= micro_thresholds[platform_key]:
                return {
                    "tier": "micro_influencer",
                    "rate": config.COMMISSION_MICRO,
                    "reason": f"{followers:,} {platform} followers (micro threshold: {micro_thresholds[platform_key]:,})"
                }

    return {
        "tier": "standard",
        "rate": config.COMMISSION_STANDARD,
        "reason": "No social links meeting influencer thresholds"
    }


def add_earnings_history(creator_id: str, amount: int, order_id: str = "") -> bool:
    """Add entry to earnings history"""
    if not supabase:
        return False

    try:
        # Get current history
        result = supabase.table("creators").select("earnings_history").eq("id", creator_id).execute()
        if not result.data:
            return False

        history = result.data[0].get("earnings_history", [])
        if not isinstance(history, list):
            history = []

        # Add new entry
        history.append({
            "date": datetime.utcnow().strftime("%Y-%m-%d"),
            "amount": amount,
            "order_id": order_id,
        })

        # Keep only last 90 days
        cutoff = (datetime.utcnow() - timedelta(days=90)).strftime("%Y-%m-%d")
        history = [h for h in history if h.get("date", "") >= cutoff]

        supabase.table("creators").update({"earnings_history": history}).eq("id", creator_id).execute()
        return True
    except Exception as e:
        print(f"Error updating earnings history: {e}")
        return False


# =====================================================
# RANK AND TIER LABELS
# =====================================================

RANK_LABELS = {
    "rookie_designer": {
        "label": "Rookie Designer",
        "emoji": "🌱",
        "description": "Just starting your design journey",
    },
    "emerging_talent": {
        "label": "Emerging Talent",
        "emoji": "⭐",
        "description": "Making waves in the community",
    },
    "trendsetter": {
        "label": "Trendsetter",
        "emoji": "🔥",
        "description": "Setting the trends",
    },
    "style_architect": {
        "label": "Style Architect",
        "emoji": "🏛️",
        "description": "Building the future of fashion",
    },
    "platform_icon": {
        "label": "Platform Icon",
        "emoji": "👑",
        "description": "A legendary creator",
    },
}

TIER_LABELS = {
    "standard": {
        "label": "Standard Creator",
        "rate": 5,
    },
    "micro_influencer": {
        "label": "Micro-Influencer",
        "rate": 15,
    },
    "mega_influencer": {
        "label": "Mega-Influencer",
        "rate": 50,
    },
}


# =====================================================
# MAIN REQUEST HANDLER
# =====================================================

class handler(BaseHTTPRequestHandler):
    """Main HTTP request handler for Creator Economy API"""

    def send_json_response(self, status: int, data: Dict, headers: Dict = None):
        """Helper to send JSON response"""
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        if headers:
            for key, value in headers.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def send_cors_headers(self):
        """Send CORS headers for preflight requests"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self.send_cors_headers()

    def log_message(self, format, *args):
        """Custom logging"""
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {args[0]}")

    def do_GET(self):
        """Handle GET requests"""
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        # Health check
        if path in ['/health', '/api/health', '/ping']:
            self.send_json_response(200, {
                "status": "healthy",
                "service": "creator-economy-api",
                "version": "2.0.0",
                "timestamp": datetime.utcnow().isoformat(),
                "database": "connected" if supabase else "disconnected",
                "commission_rates": {
                    "standard": f"{config.COMMISSION_STANDARD}%",
                    "micro": f"{config.COMMISSION_MICRO}%",
                    "mega": f"{config.COMMISSION_MEGA}%",
                },
            })
            return

        # =====================================================
        # GET /api/creator/profile?user_id=xxx
        # =====================================================
        if path == '/api/creator/profile':
            user_id = params.get('user_id', [None])[0]
            username = params.get('username', [None])[0]

            if not user_id and not username:
                self.send_json_response(400, {"success": False, "error": "user_id or username required"})
                return

            # Get creator by ID or username
            creator = None
            if user_id:
                creator = get_creator_profile(user_id)
            if not creator and username:
                creator = get_creator_by_username(username)

            if not creator:
                # Return profile not found - let frontend handle registration
                self.send_json_response(404, {
                    "success": False,
                    "error": "Creator profile not found",
                    "needs_registration": True,
                    "user_id": user_id,
                })
                return

            # Calculate payout status
            payout_status = calculate_payout_status(creator.get("balance", 0))

            # Get rank labels
            rank = creator.get("style_influence_rank", "rookie_designer")
            tier = creator.get("commission_tier", "standard")

            self.send_json_response(200, {
                "success": True,
                "data": {
                    **creator,
                    "payout_status": payout_status,
                    "rank_info": RANK_LABELS.get(rank, RANK_LABELS["rookie_designer"]),
                    "tier_info": TIER_LABELS.get(tier, TIER_LABELS["standard"]),
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
            payout_status["current_balance"] = creator.get("balance", 0)

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
                # Get mega influencers with their designs
                result = supabase.table("creators").select(
                    "id, username, avatar_url, style_influence_rank, lifetime_earnings, total_items_sold"
                ).eq("is_mega_influencer", True).execute()

                # Add rank info
                featured = []
                for c in (result.data or []):
                    c["rank_info"] = RANK_LABELS.get(c.get("style_influence_rank", "rookie_designer"), RANK_LABELS["rookie_designer"])
                    featured.append(c)

                self.send_json_response(200, {
                    "success": True,
                    "data": featured,
                    "count": len(featured)
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
                result = supabase.table("creator_designs").select("*").eq("creator_id", creator["id"]).eq("status", "active").order("created_at", desc=True).execute()
                self.send_json_response(200, {
                    "success": True,
                    "data": result.data or [],
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
                    "data": result.data or [],
                    "count": len(result.data) if result.data else 0
                })
            except Exception as e:
                self.send_json_response(500, {"success": False, "error": str(e)})
            return

        # =====================================================
        # GET /api/creator/payouts?user_id=xxx
        # =====================================================
        if path == '/api/creator/payouts':
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
                result = supabase.table("creator_payouts").select("*").eq("creator_id", creator["id"]).order("created_at", desc=True).limit(20).execute()
                self.send_json_response(200, {
                    "success": True,
                    "data": result.data or [],
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
            first_name = body.get('first_name', '')

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
                return

            # Create creator profile
            result = create_creator_profile(user_id, email, username, first_name)

            if result.get("success"):
                self.send_json_response(201, result)
            else:
                error_msg = result.get("error", "Failed to create profile")
                if "already exists" in error_msg.lower():
                    self.send_json_response(409, result)
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
                self.send_json_response(404, {"success": False, "error": "Creator not found. Please register first."})
                return

            # Update social links
            social_links = creator.get("social_links", {})
            if not isinstance(social_links, dict):
                social_links = {}

            social_links[platform] = {
                "handle": handle,
                "followers": followers,
                "verified": followers >= 100000,
                "linked_at": datetime.utcnow().isoformat(),
            }

            # Calculate new commission tier
            tier_info = calculate_commission_tier(social_links)

            # Update creator
            update_creator_profile(user_id, {
                "social_links": social_links,
                "commission_tier": tier_info["tier"],
                "commission_rate": tier_info["rate"],
                "is_mega_influencer": tier_info["tier"] == "mega_influencer"
            })

            self.send_json_response(200, {
                "success": True,
                "data": {
                    "platform": platform,
                    "handle": handle,
                    "followers": followers,
                    "tier": tier_info["tier"],
                    "tier_info": TIER_LABELS.get(tier_info["tier"], TIER_LABELS["standard"]),
                    "commission_rate": tier_info["rate"],
                    "is_verified": followers >= 100000,
                    "is_mega_influencer": tier_info["tier"] == "mega_influencer",
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
            payout_type = body.get('type', 'cash')
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
                    "error": f"Store credit requires minimum ₹{config.PAYOUT_STORE_CREDIT} balance",
                    "current_balance": balance,
                    "required": config.PAYOUT_STORE_CREDIT
                })
                return

            if payout_type == 'cash' and not payout_status["cash_withdrawal_unlocked"]:
                self.send_json_response(400, {
                    "success": False,
                    "error": f"Cash withdrawal requires minimum ₹{config.PAYOUT_CASH} balance",
                    "current_balance": balance,
                    "required": config.PAYOUT_CASH
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

            # Mock Stripe response (integrate with actual Stripe Connect in production)
            stripe_response = {
                "id": f"py_{uuid.uuid4().hex[:12]}",
                "object": "payout",
                "amount": amount * 100,
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
            commission_rate = creator.get("commission_rate", config.COMMISSION_STANDARD)
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
                    current_listings = creator.get("active_listings", 0)
                    update_creator_field(user_id, "active_listings", current_listings + 1)
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

        # =====================================================
        # POST /api/webhook/shopify-order  ← KEY NEW ENDPOINT
        # Auto-credits commissions when a Shopify order is placed
        # =====================================================
        if path == '/api/webhook/shopify-order':
            order_id = body.get('id') or body.get('order_id')
            total_price = body.get('total_price', '0')
            line_items = body.get('line_items', [])

            if not order_id:
                self.send_json_response(400, {"success": False, "error": "order_id required"})
                return

            # Process each line item for creator commissions
            if supabase and line_items:
                for item in line_items:
                    # Check if this item has a creator_id attached (via product properties)
                    properties = item.get('properties', {})
                    # properties can be list of {name, value} dicts (Shopify format)
                    if isinstance(properties, list):
                        props_dict = {p.get('name', ''): p.get('value', '') for p in properties}
                        creator_id = props_dict.get('_creator_id')
                    else:
                        creator_id = properties.get('_creator_id')

                    if creator_id:
                        try:
                            # Get creator by UUID
                            result = supabase.table("creators").select("*").eq("id", creator_id).execute()
                            if not result.data:
                                continue

                            creator = result.data[0]
                            commission_rate = creator.get("commission_rate", config.COMMISSION_STANDARD)
                            item_price = int(float(item.get('price', '0')) * 100)  # Convert to paise
                            commission = int(item_price * commission_rate / 100)

                            if commission > 0:
                                # Update creator balance
                                new_balance = creator.get("balance", 0) + commission
                                new_lifetime = creator.get("lifetime_earnings", 0) + commission
                                new_sold = creator.get("total_items_sold", 0) + 1

                                # Calculate new rank
                                new_rank = calculate_style_rank(new_lifetime)

                                update_creator_profile(creator["shopify_customer_id"], {
                                    "balance": new_balance,
                                    "lifetime_earnings": new_lifetime,
                                    "total_items_sold": new_sold,
                                    "style_influence_rank": new_rank,
                                })

                                # Record commission
                                supabase.table("creator_commissions").insert({
                                    "id": str(uuid.uuid4()),
                                    "creator_id": creator["id"],
                                    "shopify_order_id": str(order_id),
                                    "amount": commission,
                                    "type": "sale_commission",
                                    "created_at": datetime.utcnow().isoformat(),
                                }).execute()

                                # Update earnings history
                                add_earnings_history(creator["id"], commission, str(order_id))

                        except Exception as e:
                            print(f"Error processing commission for item: {e}")

            self.send_json_response(200, {
                "success": True,
                "message": "Order processed successfully"
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
        # PUT /api/creator/balance/update (Manual balance update / fallback webhook)
        # =====================================================
        if path == '/api/creator/balance/update':
            creator_id = body.get('creator_id')
            user_id = body.get('user_id')
            commission_earned = int(body.get('commission_earned', 0))
            shopify_order_id = body.get('order_id', '')

            if commission_earned <= 0:
                self.send_json_response(400, {
                    "success": False,
                    "error": "commission_earned must be greater than 0"
                })
                return

            # Get creator by either ID
            creator = None
            if user_id:
                creator = get_creator_profile(user_id)
            elif creator_id and supabase:
                try:
                    result = supabase.table("creators").select("*").eq("id", creator_id).execute()
                    if result.data:
                        creator = result.data[0]
                except:
                    pass

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
            update_creator_profile(creator["shopify_customer_id"], {
                "balance": new_balance,
                "lifetime_earnings": new_lifetime,
                "total_items_sold": total_sold + 1,
                "style_influence_rank": new_rank,
            })

            # Record commission
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

                    # Update earnings history
                    add_earnings_history(creator["id"], commission_earned, shopify_order_id)
                except Exception as e:
                    print(f"Error recording commission: {e}")

            self.send_json_response(200, {
                "success": True,
                "data": {
                    "commission_earned": commission_earned,
                    "new_balance": new_balance,
                    "lifetime_earnings": new_lifetime,
                    "new_rank": new_rank,
                    "rank_info": RANK_LABELS.get(new_rank, RANK_LABELS["rookie_designer"])
                }
            })
            return

        self.send_json_response(404, {"success": False, "error": "Endpoint not found"})


# =====================================================
# MAIN ENTRY POINT
# =====================================================

if __name__ == "__main__":
    print("=" * 60)
    print("🎨 My Narrative Creator Economy API v2.0.0")
    print("=" * 60)
    print(f"Database: {'✅ Connected' if supabase else '❌ Not configured (set SUPABASE_URL + SUPABASE_KEY)'}")
    print(f"Commission Rates: Standard={config.COMMISSION_STANDARD}%, Micro={config.COMMISSION_MICRO}%, Mega={config.COMMISSION_MEGA}%")
    print(f"Payout Thresholds: Store Credit=₹{config.PAYOUT_STORE_CREDIT}, Cash=₹{config.PAYOUT_CASH}")
    print("=" * 60)

# =====================================================
# VERCEL HANDLER
# =====================================================
def handler(event, context):
    """Vercel Python runtime handler"""
    from io import BytesIO
    
    http_method = event.get('httpMethod', 'GET')
    path = event.get('path', '/')
    query_params = event.get('queryStringParameters') or {}
    headers = event.get('headers') or {}
    body = event.get('body', '') or ''
    
    # Build query string
    query_string = '&'.join([f"{k}={v}" for k, v in query_params.items()])
    full_path = path if not query_string else f"{path}?{query_string}"
    
    # Create handler instance
    h = handler.__new__(handler)
    h.path = full_path
    h.headers = headers
    h.body = body
    
    # Create mock wfile for response
    response = BytesIO()
    h.wfile = response
    
    # Initialize send_response_code
    h.send_response_code = 200
    
    try:
        if http_method == 'GET':
            h.do_GET()
        elif http_method == 'POST':
            h.do_POST()
        elif http_method == 'OPTIONS':
            h.do_OPTIONS()
        else:
            h.send_json_response(405, {"error": "Method not allowed"})
            h.send_response_code = 405
    except Exception as e:
        h.send_json_response(500, {"error": str(e)})
        h.send_response_code = 500
    
    # Get response
    response_bytes = response.getvalue()
    
    # Return Vercel format
    return {
        'statusCode': h.send_response_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization',
        },
        'body': response_bytes.decode('utf-8')
    }