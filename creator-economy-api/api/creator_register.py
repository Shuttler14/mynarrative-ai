from http.server import BaseHTTPRequestHandler
import json
import os
import uuid
import re
import asyncio
import httpx
from datetime import datetime
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
        supabase_key = os.environ.get("SUPABASE_SERVICE_KEY", "")
        
        if supabase_url and supabase_key and "supabase.co" in supabase_url:
            supabase_client = create_client(supabase_url, supabase_key)
            SUPABASE_AVAILABLE = True
    except Exception as e:
        print(f"Supabase init error: {e}")
        supabase_client = None
    
    return supabase_client

class Config:
    SHOP_DOMAIN = os.environ.get("SHOP_DOMAIN", "mynarrative.in")
    SHOPIFY_ACCESS_TOKEN = os.environ.get("SHOPIFY_ACCESS_TOKEN", "")
    
    ELITE_THRESHOLDS = {
        "instagram": 500000,
        "youtube": 300000,
        "twitter": 200000,
        "linkedin": 150000,
    }
    
    COMMISSION_MIN = 30
    COMMISSION_MAX = 45
    COMMISSION_ELITE = 45
    COMMISSION_MICRO = 20
    COMMISSION_STANDARD = 15

config = Config()

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

        if path in ['/api/creator_register', '/health', '/api/health', '/ping']:
            self.send_json_response(200, {
                "status": "healthy",
                "service": "creator-register-api",
                "version": "1.0.0",
                "endpoints": ["/api/creator/auto_register", "/api/creator/setup_brand", "/api/creator/complete_onboarding", "/api/creator/verify_social"]
            })
            return

        if path == '/api/creator/verify_social':
            platform = params.get('platform', [None])[0]
            handle = params.get('handle', [None])[0]
            
            if not platform or not handle:
                self.send_json_response(400, {"success": False, "error": "platform and handle required"})
                return
            
            self.send_json_response(200, {
                "success": True,
                "data": {
                    "platform": platform,
                    "handle": handle,
                    "verified": True,
                    "followers": 0,
                    "message": "Verification endpoint - use POST for actual validation"
                }
            })
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

        if path == '/api/creator/auto_register':
            user_id = body.get('user_id')
            email = body.get('email')
            first_name = body.get('first_name', '')
            
            if not user_id or not email:
                self.send_json_response(400, {"success": False, "error": "user_id and email required"})
                return
            
            supabase = get_supabase()
            if not supabase:
                self.send_json_response(200, {"success": True, "message": "Auto-registered (demo mode)", "data": {"is_new": True}})
                return
            
            try:
                existing = supabase.table("creators").select("id, username").eq("shopify_customer_id", user_id).execute()
                
                if existing.data:
                    self.send_json_response(200, {
                        "success": True,
                        "message": "Creator exists",
                        "data": {"is_new": False, "creator_id": existing.data[0]["id"]}
                    })
                    return
                
                username = self._generate_username(first_name, email)
                
                data = {
                    "shopify_customer_id": user_id,
                    "email": email,
                    "first_name": first_name,
                    "username": username,
                    "brand_name": "",
                    "balance": 0,
                    "lifetime_earnings": 0,
                    "total_items_sold": 0,
                    "active_listings": 0,
                    "commission_tier": "standard",
                    "commission_rate": config.COMMISSION_STANDARD,
                    "tier": "basic",
                    "is_verified": False,
                    "is_invite_only": False,
                    "total_followers": 0,
                    "onboarding_completed": False,
                    "social_links": {},
                    "created_at": datetime.utcnow().isoformat(),
                }
                
                result = supabase.table("creators").insert(data).execute()
                
                self.send_json_response(200, {
                    "success": True,
                    "message": "Creator profile created",
                    "data": {"is_new": True, "creator_id": result.data[0]["id"] if result.data else None}
                })
            except Exception as e:
                print(f"Auto-register error: {e}")
                self.send_json_response(200, {"success": True, "message": "Auto-registered", "data": {"is_new": True}})
            return

        if path == '/api/creator/verify_social':
            user_id = body.get('user_id')
            platform = body.get('platform')
            handle = body.get('handle')
            
            if not user_id or not platform or not handle:
                self.send_json_response(400, {"success": False, "error": "user_id, platform, handle required"})
                return
            
            asyncio.run(self._verify_social_async(user_id, platform, handle, self))
            return

        if path == '/api/creator/setup_brand':
            user_id = body.get('user_id')
            brand_name = body.get('brand_name')
            
            if not user_id or not brand_name:
                self.send_json_response(400, {"success": False, "error": "user_id and brand_name required"})
                return
            
            supabase = get_supabase()
            if not supabase:
                self.send_json_response(200, {"success": True, "message": "Brand updated (demo)"})
                return
            
            try:
                supabase.table("creators").update({
                    "brand_name": brand_name,
                }).eq("shopify_customer_id", user_id).execute()
                
                self.send_json_response(200, {"success": True, "message": "Brand name saved"})
            except Exception as e:
                self.send_json_response(200, {"success": False, "error": str(e)})
            return

        if path == '/api/creator/complete_onboarding':
            user_id = body.get('user_id')
            
            if not user_id:
                self.send_json_response(400, {"success": False, "error": "user_id required"})
                return
            
            supabase = get_supabase()
            if not supabase:
                self.send_json_response(200, {"success": True, "message": "Onboarding completed (demo)"})
                return
            
            try:
                supabase.table("creators").update({
                    "onboarding_completed": True,
                    "onboarding_completed_at": datetime.utcnow().isoformat(),
                }).eq("shopify_customer_id", user_id).execute()
                
                self.send_json_response(200, {"success": True, "message": "Onboarding completed"})
            except Exception as e:
                self.send_json_response(200, {"success": False, "error": str(e)})
            return

        self.send_json_response(404, {"error": "Not found"})

    def _generate_username(self, first_name, email):
        base = first_name.lower() if first_name else email.split('@')[0]
        base = re.sub(r'[^a-zA-Z0-9_]', '', base)
        
        if not base:
            base = "creator"
        
        suffix = str(uuid.uuid4())[:4]
        return f"{base}{suffix}"

    async def _verify_social_async(self, user_id, platform, handle, handler_instance):
        verified = False
        followers = 0
        profile_url = ""
        avatar_url = ""
        
        platform = platform.lower()
        
        if platform == "instagram":
            profile_url = f"https://instagram.com/{handle.replace('@', '')}"
        elif platform == "youtube":
            profile_url = f"https://youtube.com/@{handle.replace('@', '')}"
        elif platform == "twitter" or platform == "x":
            profile_url = f"https://x.com/{handle.replace('@', '')}"
        elif platform == "linkedin":
            profile_url = f"https://linkedin.com/in/{handle.replace('@', '')}"
        
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(profile_url, follow_redirects=True)
                verified = response.status_code == 200
                
                if verified:
                    if platform == "instagram":
                        if 'instagram.com/' in profile_url:
                            username = profile_url.split('instagram.com/')[-1].strip('/')
                            followers = await self._get_instagram_followers(username)
                    elif platform == "youtube":
                        if 'youtube.com/@' in profile_url:
                            username = profile_url.split('@')[-1].strip('/')
                            followers = await self._get_youtube_subscribers(username)
                    elif platform == "twitter" or platform == "x":
                        if 'x.com/' in profile_url:
                            username = profile_url.split('x.com/')[-1].strip('/')
                            followers = await self._get_twitter_followers(username)
                    elif platform == "linkedin":
                        followers = await self._get_linkin_followers(handle)
        except Exception as e:
            print(f"Social verification error: {e}")
        
        supabase = get_supabase()
        
        if supabase and user_id:
            try:
                result = supabase.table("creators").select("social_links, total_followers").eq("shopify_customer_id", user_id).execute()
                
                if result.data:
                    social_links = result.data[0].get("social_links", {})
                    current_followers = result.data[0].get("total_followers", 0)
                    
                    social_links[platform] = {
                        "handle": handle,
                        "followers": followers,
                        "verified": verified,
                        "avatar_url": avatar_url,
                        "profile_url": profile_url
                    }
                    
                    total_followers = sum(
                        link.get("followers", 0) 
                        for link in social_links.values() 
                        if isinstance(link, dict)
                    )
                    
                    tier_info = self._calculate_tier(total_followers, social_links)
                    
                    update_data = {
                        "social_links": social_links,
                        "total_followers": total_followers,
                        "tier": tier_info["tier"],
                        "commission_rate": tier_info["commission_rate"],
                        "commission_tier": tier_info["commission_tier"],
                        "is_verified": verified,
                    }
                    
                    if tier_info.get("primary_platform"):
                        update_data["primary_platform"] = tier_info["primary_platform"]
                    
                    if tier_info.get("avatar_url"):
                        update_data["avatar_url"] = tier_info["avatar_url"]
                    
                    if tier_info.get("username"):
                        update_data["username"] = tier_info["username"]
                    
                    supabase.table("creators").update(update_data).eq("shopify_customer_id", user_id).execute()
                    
                    handler_instance.send_json_response(200, {
                        "success": True,
                        "data": {
                            "verified": verified,
                            "followers": followers,
                            "platform": platform,
                            "handle": handle,
                            "total_followers": total_followers,
                            "tier": tier_info["tier"],
                            "commission_rate": tier_info["commission_rate"],
                            "is_elite": tier_info["is_elite"],
                        }
                    })
                    return
            except Exception as e:
                print(f"Update creator error: {e}")
        
        handler_instance.send_json_response(200, {
            "success": True,
            "data": {
                "verified": verified,
                "followers": followers,
                "platform": platform,
                "handle": handle,
            }
        })

    async def _get_instagram_followers(self, username):
        return 0

    async def _get_youtube_subscribers(self, username):
        return 0

    async def _get_twitter_followers(self, username):
        return 0

    async def _get_linkin_followers(self, handle):
        return 0

    def _calculate_tier(self, total_followers, social_links):
        is_elite = (
            (social_links.get("instagram", {}).get("followers", 0) >= config.ELITE_THRESHOLDS["instagram"]) or
            (social_links.get("youtube", {}).get("followers", 0) >= config.ELITE_THRESHOLDS["youtube"]) or
            (social_links.get("twitter", {}).get("followers", 0) >= config.ELITE_THRESHOLDS["twitter"]) or
            (social_links.get("linkedin", {}).get("followers", 0) >= config.ELITE_THRESHOLDS["linkedin"])
        )
        
        if is_elite:
            return {
                "tier": "elite",
                "commission_rate": config.COMMISSION_ELITE,
                "commission_tier": "elite",
                "is_elite": True,
            }
        
        if total_followers >= 100000:
            return {
                "tier": "influencer",
                "commission_rate": config.COMMISSION_MICRO,
                "commission_tier": "micro_influencer",
                "is_elite": False,
            }
        
        return {
            "tier": "basic",
            "commission_rate": config.COMMISSION_STANDARD,
            "commission_tier": "standard",
            "is_elite": False,
        }

    def _get_best_platform(self, social_links):
        best_platform = None
        best_followers = 0
        best_avatar = ""
        
        for platform, data in social_links.items():
            if isinstance(data, dict):
                followers = data.get("followers", 0)
                avatar = data.get("avatar_url", "")
                
                if followers > best_followers:
                    best_followers = followers
                    best_platform = platform
                    best_avatar = avatar
        
        return {
            "primary_platform": best_platform,
            "avatar_url": best_avatar,
            "followers": best_followers
        }
