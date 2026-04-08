from http.server import BaseHTTPRequestHandler
import json
import os
import uuid
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
        supabase_key = os.environ.get("SUPABASE_KEY", "")
        if supabase_url and supabase_key and supabase_url != "https://your-project-id.supabase.co":
            supabase_client = create_client(supabase_url, supabase_key)
            SUPABASE_AVAILABLE = True
    except Exception as e:
        print(f"Supabase init error: {e}")
        supabase_client = None
    return supabase_client

# -----------------------------------------------------------
# Demo data – shown when Supabase is not connected
# -----------------------------------------------------------
DEMO_DESIGNS = [
    {
        "id": "d1",
        "title": "Midnight Bloom",
        "description": "Dark floral oversized tee — where nature meets streetwear.",
        "creator_username": "aria_styles",
        "creator_avatar": "https://api.dicebear.com/7.x/avataaars/svg?seed=aria",
        "creator_tier": "trendsetter",
        "image_url": "https://images.unsplash.com/photo-1523381210434-271e8be1f52b?w=600&q=80",
        "price": 1299,
        "total_sales": 248,
        "total_likes": 1420,
        "category": "tee",
        "tags": ["floral", "dark", "oversized"],
        "created_at": "2026-03-20T10:00:00Z",
        "shopify_product_id": "",
        "shopify_product_url": "/collections/all",
    },
    {
        "id": "d2",
        "title": "Urban Cipher",
        "description": "Bold geometric graphic hoodie. Code your own aesthetic.",
        "creator_username": "zayan.creates",
        "creator_avatar": "https://api.dicebear.com/7.x/avataaars/svg?seed=zayan",
        "creator_tier": "emerging_talent",
        "image_url": "https://images.unsplash.com/photo-1556821840-3a63f15732ce?w=600&q=80",
        "price": 1899,
        "total_sales": 134,
        "total_likes": 980,
        "category": "hoodie",
        "tags": ["geometric", "graphic", "urban"],
        "created_at": "2026-03-18T14:00:00Z",
        "shopify_product_id": "",
        "shopify_product_url": "/collections/all",
    },
    {
        "id": "d3",
        "title": "Chaos Theory",
        "description": "Abstract splatter art on premium drop-shoulder tee.",
        "creator_username": "meera.ink",
        "creator_avatar": "https://api.dicebear.com/7.x/avataaars/svg?seed=meera",
        "creator_tier": "platform_icon",
        "image_url": "https://images.unsplash.com/photo-1586790170083-2f9ceadc732d?w=600&q=80",
        "price": 1499,
        "total_sales": 512,
        "total_likes": 3200,
        "category": "tee",
        "tags": ["abstract", "art", "splatter"],
        "created_at": "2026-03-15T09:00:00Z",
        "shopify_product_id": "",
        "shopify_product_url": "/collections/all",
    },
    {
        "id": "d4",
        "title": "Neon Jungle",
        "description": "Tropical neon print jacket — stand out in the urban jungle.",
        "creator_username": "rio_vision",
        "creator_avatar": "https://api.dicebear.com/7.x/avataaars/svg?seed=rio",
        "creator_tier": "rookie_designer",
        "image_url": "https://images.unsplash.com/photo-1551698618-1dfe5d97d256?w=600&q=80",
        "price": 2499,
        "total_sales": 67,
        "total_likes": 445,
        "category": "jacket",
        "tags": ["neon", "tropical", "jacket"],
        "created_at": "2026-03-22T16:00:00Z",
        "shopify_product_id": "",
        "shopify_product_url": "/collections/all",
    },
    {
        "id": "d5",
        "title": "Serenity Script",
        "description": "Minimalist calligraphy tee. Wear your calm.",
        "creator_username": "priya.minimal",
        "creator_avatar": "https://api.dicebear.com/7.x/avataaars/svg?seed=priya",
        "creator_tier": "emerging_talent",
        "image_url": "https://images.unsplash.com/photo-1503341338985-95c5adae8b3a?w=600&q=80",
        "price": 999,
        "total_sales": 189,
        "total_likes": 1100,
        "category": "tee",
        "tags": ["minimal", "calligraphy", "clean"],
        "created_at": "2026-03-21T11:00:00Z",
        "shopify_product_id": "",
        "shopify_product_url": "/collections/all",
    },
    {
        "id": "d6",
        "title": "Retro Wave",
        "description": "80s synthwave vibes on a cropped sweatshirt. Nostalgia hits different.",
        "creator_username": "karan_retro",
        "creator_avatar": "https://api.dicebear.com/7.x/avataaars/svg?seed=karan",
        "creator_tier": "trendsetter",
        "image_url": "https://images.unsplash.com/photo-1576566588028-4147f3842f27?w=600&q=80",
        "price": 1699,
        "total_sales": 303,
        "total_likes": 2100,
        "category": "sweatshirt",
        "tags": ["retro", "80s", "synthwave"],
        "created_at": "2026-03-19T08:00:00Z",
        "shopify_product_id": "",
        "shopify_product_url": "/collections/all",
    },
]

RANK_LABELS = {
    "rookie_designer":  {"label": "Rookie Designer",  "emoji": "🌱"},
    "emerging_talent":  {"label": "Emerging Talent",  "emoji": "⭐"},
    "trendsetter":      {"label": "Trendsetter",       "emoji": "🔥"},
    "style_architect":  {"label": "Style Architect",   "emoji": "🏛️"},
    "platform_icon":    {"label": "Platform Icon",     "emoji": "👑"},
}

class handler(BaseHTTPRequestHandler):

    def send_json_response(self, status_code, data):
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    # ===========================================================
    # GET ROUTES
    # ===========================================================
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        # ------ GET /api/designs/feed ------
        # Public feed of all active designs (newest first)
        if path == '/api/designs/feed':
            page      = int(params.get('page', ['1'])[0])
            per_page  = int(params.get('per_page', ['12'])[0])
            category  = params.get('category', [None])[0]
            sort      = params.get('sort', ['newest'])[0]   # newest | trending | top_selling
            creator   = params.get('creator', [None])[0]    # filter by username

            supabase = get_supabase()
            if not supabase:
                designs = list(DEMO_DESIGNS)
                if category:
                    designs = [d for d in designs if d.get('category') == category]
                if creator:
                    designs = [d for d in designs if d.get('creator_username') == creator]
                if sort == 'trending':
                    designs.sort(key=lambda x: x.get('total_likes', 0), reverse=True)
                elif sort == 'top_selling':
                    designs.sort(key=lambda x: x.get('total_sales', 0), reverse=True)
                else:
                    designs.sort(key=lambda x: x.get('created_at', ''), reverse=True)
                start  = (page - 1) * per_page
                paged  = designs[start:start + per_page]
                self.send_json_response(200, {
                    "success": True,
                    "data": paged,
                    "total": len(designs),
                    "page": page,
                    "per_page": per_page,
                    "has_more": start + per_page < len(designs),
                })
                return

            try:
                query = (
                    supabase.table("creator_designs")
                    .select(
                        "id, title, description, flux_editorial_image_url, flat_image_url, "
                        "price, total_sales, total_likes, category, tags, created_at, "
                        "shopify_product_id, status, "
                        "creators(username, avatar_url, style_influence_rank, commission_tier)"
                    )
                    .eq("status", "active")
                )
                if category:
                    query = query.eq("category", category)
                if creator:
                    # filter by creator username via join — done client-side below for simplicity
                    pass

                if sort == 'trending':
                    query = query.order("total_likes", desc=True)
                elif sort == 'top_selling':
                    query = query.order("total_sales", desc=True)
                else:
                    query = query.order("created_at", desc=True)

                result = query.range((page-1)*per_page, page*per_page - 1).execute()
                designs = []
                for d in (result.data or []):
                    creator_info = d.pop("creators", {}) or {}
                    if creator and creator_info.get('username') != creator:
                        continue
                    rank = creator_info.get('style_influence_rank', 'rookie_designer')
                    designs.append({
                        **d,
                        "image_url": d.get("flux_editorial_image_url") or d.get("flat_image_url", ""),
                        "creator_username": creator_info.get("username", "creator"),
                        "creator_avatar": creator_info.get("avatar_url", ""),
                        "creator_tier": rank,
                        "creator_tier_label": RANK_LABELS.get(rank, {}).get("label", ""),
                        "creator_tier_emoji": RANK_LABELS.get(rank, {}).get("emoji", ""),
                        "shopify_product_url": (
                            f"/products/{d.get('shopify_product_id', '')}"
                            if d.get("shopify_product_id") else "/collections/all"
                        ),
                    })

                # count total
                count_res = supabase.table("creator_designs").select("id", count="exact").eq("status", "active").execute()
                total = count_res.count or len(designs)

                self.send_json_response(200, {
                    "success": True,
                    "data": designs,
                    "total": total,
                    "page": page,
                    "per_page": per_page,
                    "has_more": page * per_page < total,
                })
            except Exception as e:
                self.send_json_response(200, {
                    "success": True,
                    "data": DEMO_DESIGNS,
                    "total": len(DEMO_DESIGNS),
                    "page": 1,
                    "per_page": per_page,
                    "has_more": False,
                })
            return

        # ------ GET /api/designs/single ------
        if path == '/api/designs/single':
            design_id = params.get('id', [None])[0]
            if not design_id:
                self.send_json_response(400, {"success": False, "error": "id required"})
                return

            supabase = get_supabase()
            if not supabase:
                match = next((d for d in DEMO_DESIGNS if d['id'] == design_id), DEMO_DESIGNS[0])
                self.send_json_response(200, {"success": True, "data": match})
                return

            try:
                result = (
                    supabase.table("creator_designs")
                    .select("*, creators(username, avatar_url, style_influence_rank, commission_tier, social_links, lifetime_earnings, total_items_sold)")
                    .eq("id", design_id)
                    .single()
                    .execute()
                )
                d = result.data or {}
                creator_info = d.pop("creators", {}) or {}
                rank = creator_info.get('style_influence_rank', 'rookie_designer')
                design = {
                    **d,
                    "image_url": d.get("flux_editorial_image_url") or d.get("flat_image_url", ""),
                    "creator_username": creator_info.get("username", "creator"),
                    "creator_avatar": creator_info.get("avatar_url", ""),
                    "creator_tier": rank,
                    "creator_tier_label": RANK_LABELS.get(rank, {}).get("label", ""),
                    "creator_tier_emoji": RANK_LABELS.get(rank, {}).get("emoji", ""),
                    "creator_social_links": creator_info.get("social_links", {}),
                    "creator_total_sales": creator_info.get("total_items_sold", 0),
                    "shopify_product_url": (
                        f"/products/{d.get('shopify_product_id', '')}"
                        if d.get("shopify_product_id") else "/collections/all"
                    ),
                }
                self.send_json_response(200, {"success": True, "data": design})
            except Exception as e:
                self.send_json_response(200, {"success": True, "data": DEMO_DESIGNS[0]})
            return

        # ------ GET /api/designs/creator ------
        # Designs by a specific creator (for their dashboard)
        if path == '/api/designs/creator':
            user_id = params.get('user_id', [None])[0]
            if not user_id:
                self.send_json_response(400, {"success": False, "error": "user_id required"})
                return

            supabase = get_supabase()
            if not supabase:
                self.send_json_response(200, {"success": True, "data": []})
                return

            try:
                creator_res = supabase.table("creators").select("id").eq("shopify_customer_id", user_id).execute()
                if not creator_res.data:
                    self.send_json_response(200, {"success": True, "data": []})
                    return
                creator_db_id = creator_res.data[0]["id"]
                result = (
                    supabase.table("creator_designs")
                    .select("*")
                    .eq("creator_id", creator_db_id)
                    .order("created_at", desc=True)
                    .execute()
                )
                designs = []
                for d in (result.data or []):
                    designs.append({
                        **d,
                        "image_url": d.get("flux_editorial_image_url") or d.get("flat_image_url", ""),
                        "shopify_product_url": (
                            f"/products/{d.get('shopify_product_id', '')}"
                            if d.get("shopify_product_id") else ""
                        ),
                    })
                self.send_json_response(200, {"success": True, "data": designs})
            except Exception as e:
                self.send_json_response(200, {"success": True, "data": []})
            return

        # ------ GET /api/designs/categories ------
        if path == '/api/designs/categories':
            self.send_json_response(200, {
                "success": True,
                "data": [
                    {"id": "all",        "label": "All Drops",    "emoji": "✨"},
                    {"id": "tee",        "label": "Tees",         "emoji": "👕"},
                    {"id": "hoodie",     "label": "Hoodies",      "emoji": "🧥"},
                    {"id": "jacket",     "label": "Jackets",      "emoji": "🪖"},
                    {"id": "sweatshirt", "label": "Sweatshirts",  "emoji": "🌀"},
                    {"id": "bottoms",    "label": "Bottoms",      "emoji": "👖"},
                    {"id": "accessories","label": "Accessories",  "emoji": "💍"},
                ]
            })
            return

        # Alias: /api/designs → /api/designs/feed (backwards compat)
        if path == '/api/designs':
            supabase = get_supabase()
            if not supabase:
                self.send_json_response(200, {
                    "success": True, "data": DEMO_DESIGNS,
                    "total": len(DEMO_DESIGNS), "page": 1, "per_page": 12, "has_more": False,
                })
                return
            try:
                result = (
                    supabase.table("creator_designs")
                    .select("id, title, description, flux_editorial_image_url, flat_image_url, price, total_sales, total_likes, category, created_at, shopify_product_id, status")
                    .eq("status", "active")
                    .order("created_at", desc=True)
                    .limit(12)
                    .execute()
                )
                self.send_json_response(200, {
                    "success": True, "data": result.data or [],
                    "total": len(result.data or []), "page": 1, "per_page": 12, "has_more": False
                })
            except Exception:
                self.send_json_response(200, {
                    "success": True, "data": DEMO_DESIGNS,
                    "total": len(DEMO_DESIGNS), "page": 1, "per_page": 12, "has_more": False
                })
            return

        self.send_json_response(404, {"error": "Not found"})

    # ===========================================================
    # POST ROUTES
    # ===========================================================
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

        # ------ POST /api/designs/submit ------
        # Creator submits a new design to the feed
        if path == '/api/designs/submit':
            user_id     = body.get('user_id')
            title       = body.get('title', '').strip()
            description = body.get('description', '').strip()
            image_url   = body.get('image_url', '').strip()
            price       = int(body.get('price', 1299))
            category    = body.get('category', 'tee')
            tags        = body.get('tags', [])
            shopify_product_id = body.get('shopify_product_id', '')

            if not user_id or not title or not image_url:
                self.send_json_response(400, {"success": False, "error": "user_id, title, image_url required"})
                return

            supabase = get_supabase()
            if not supabase:
                self.send_json_response(200, {
                    "success": True,
                    "message": "Design submitted! (demo mode)",
                    "data": {"id": str(uuid.uuid4()), "status": "active"}
                })
                return

            try:
                # Resolve creator DB id from shopify customer id
                creator_res = supabase.table("creators").select("id").eq("shopify_customer_id", user_id).execute()
                if not creator_res.data:
                    self.send_json_response(400, {"success": False, "error": "Creator not found. Please complete onboarding first."})
                    return

                creator_db_id = creator_res.data[0]["id"]

                design = {
                    "creator_id": creator_db_id,
                    "title": title,
                    "description": description,
                    "flux_editorial_image_url": image_url,
                    "flat_image_url": image_url,
                    "price": price,
                    "category": category,
                    "tags": tags,
                    "status": "active",
                    "total_sales": 0,
                    "total_likes": 0,
                    "shopify_product_id": shopify_product_id,
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat(),
                }
                result = supabase.table("creator_designs").insert(design).execute()
                inserted = result.data[0] if result.data else {}

                # Update creator active_listings count
                supabase.rpc("increment_active_listings", {"creator_id": creator_db_id}).execute() if False else None
                existing = supabase.table("creators").select("active_listings").eq("id", creator_db_id).execute()
                current = (existing.data[0].get("active_listings", 0) if existing.data else 0)
                supabase.table("creators").update({"active_listings": current + 1}).eq("id", creator_db_id).execute()

                self.send_json_response(200, {
                    "success": True,
                    "message": "Design published to the feed! 🎉",
                    "data": {
                        "id": inserted.get("id"),
                        "status": "active",
                        "image_url": image_url,
                    }
                })
            except Exception as e:
                self.send_json_response(500, {"success": False, "error": str(e)})
            return

        # ------ POST /api/designs/like ------
        if path == '/api/designs/like':
            design_id = body.get('design_id')
            if not design_id:
                self.send_json_response(400, {"success": False, "error": "design_id required"})
                return

            supabase = get_supabase()
            if not supabase:
                self.send_json_response(200, {"success": True, "message": "Liked! (demo mode)", "likes": 999})
                return

            try:
                result = supabase.table("creator_designs").select("total_likes").eq("id", design_id).execute()
                current_likes = (result.data[0].get("total_likes", 0) if result.data else 0)
                new_likes = current_likes + 1
                supabase.table("creator_designs").update({"total_likes": new_likes}).eq("id", design_id).execute()
                self.send_json_response(200, {"success": True, "likes": new_likes})
            except Exception as e:
                self.send_json_response(200, {"success": True, "likes": 0})
            return

        # ------ POST /api/designs/delete ------
        if path == '/api/designs/delete':
            design_id = body.get('design_id')
            user_id   = body.get('user_id')
            if not design_id or not user_id:
                self.send_json_response(400, {"success": False, "error": "design_id and user_id required"})
                return

            supabase = get_supabase()
            if not supabase:
                self.send_json_response(200, {"success": True, "message": "Deleted (demo mode)"})
                return

            try:
                creator_res = supabase.table("creators").select("id").eq("shopify_customer_id", user_id).execute()
                if not creator_res.data:
                    self.send_json_response(403, {"success": False, "error": "Unauthorized"})
                    return
                creator_db_id = creator_res.data[0]["id"]

                # Soft delete — set status to archived
                supabase.table("creator_designs").update({"status": "archived"}).eq("id", design_id).eq("creator_id", creator_db_id).execute()
                self.send_json_response(200, {"success": True, "message": "Design removed from feed"})
            except Exception as e:
                self.send_json_response(500, {"success": False, "error": str(e)})
            return

        self.send_json_response(404, {"error": "Not found"})
