import os as _os
import tempfile as _tempfile
_TMP = '/tmp'
_os.environ['MPLCONFIGDIR']        = _TMP
_os.environ['XDG_CACHE_HOME']      = _TMP
_os.environ['TRANSFORMERS_CACHE']  = _TMP
_os.environ['HF_HOME']             = _TMP
_os.environ['TORCH_HOME']          = _TMP
_os.environ['NUMBA_CACHE_DIR']     = _TMP
_os.environ['FONTCONFIG_PATH']     = _TMP
_os.environ['FONTCONFIG_FILE']     = _os.path.join(_TMP, 'fonts.conf')
_os.environ['PILLOW_BLOCK_OPEN']   = '0'
for _d in ['/tmp/matplotlib', '/tmp/fontconfig']:
    try:
        _os.makedirs(_d, exist_ok=True)
    except Exception:
        pass

from http.server import BaseHTTPRequestHandler
import json
import os
import uuid
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from currency_utils import detect_currency_from_headers, convert_price_rupees, format_price

TSHIRT_NUMERIC_VARIANT_MAP = {
    "white":   os.environ.get("TSHIRT_NUMERIC_VARIANT_WHITE",   ""),
    "black":   os.environ.get("TSHIRT_NUMERIC_VARIANT_BLACK",   ""),
    "navy":    os.environ.get("TSHIRT_NUMERIC_VARIANT_NAVY",    ""),
    "sage":    os.environ.get("TSHIRT_NUMERIC_VARIANT_SAGE",    ""),
    "coral":   os.environ.get("TSHIRT_NUMERIC_VARIANT_CORAL",   ""),
}

HOODIE_NUMERIC_VARIANT_MAP = {
    "white":    os.environ.get("HOODIE_NUMERIC_VARIANT_WHITE",    ""),
    "black":    os.environ.get("HOODIE_NUMERIC_VARIANT_BLACK",    ""),
    "navy":     os.environ.get("HOODIE_NUMERIC_VARIANT_NAVY",     ""),
    "burgundy": os.environ.get("HOODIE_NUMERIC_VARIANT_BURGUNDY", ""),
    "forest":   os.environ.get("HOODIE_NUMERIC_VARIANT_FOREST",   ""),
}


def enrich_design_with_variant_map(design, currency="INR"):
    product_type = design.get("product_type", "tshirt")
    selected_colors = design.get("selected_colors") or []
    numeric_map = (
        TSHIRT_NUMERIC_VARIANT_MAP if product_type == "tshirt"
        else HOODIE_NUMERIC_VARIANT_MAP
    )
    variant_map = {}
    for color in selected_colors:
        c = color.lower().strip()
        if c in numeric_map:
            variant_map[c] = {
                "variant_numeric": numeric_map[c],
                "mockup_url": (design.get("mockup_urls") or {}).get(
                    f"{product_type}_{c}", ""
                ),
            }
    design["variant_map"] = variant_map
    design["price_rupees"] = (design.get("price_paise") or 0) / 100
    design["price_formatted"] = format_price(convert_price_rupees(design["price_rupees"], currency), currency)
    design["currency"] = currency
    return design


DEMO_DESIGNS_SOCIAL = [
    {
        "id": "demo-001",
        "unique_product_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "title": "Midnight Bloom",
        "description": "Dark floral oversized tee — where nature meets streetwear.",
        "creator_id": "creator-001",
        "creator_username": "aria_styles",
        "creator_avatar": "https://api.dicebear.com/7.x/avataaars/svg?seed=aria",
        "creator_tier": "trendsetter",
        "product_type": "tshirt",
        "selected_colors": ["white", "black", "navy"],
        "price_paise": 129900,
        "mockup_urls": {
            "tshirt_white": "https://images.unsplash.com/photo-1523381210434-271e8be1f52b?w=600&q=80",
            "tshirt_black": "https://images.unsplash.com/photo-1556821840-3a63f15732ce?w=600&q=80",
            "tshirt_navy":  "https://images.unsplash.com/photo-1586790170083-2f9ceadc732d?w=600&q=80",
        },
        "total_likes": 1420,
        "total_sales": 248,
        "status": "published",
        "created_at": "2026-03-20T10:00:00Z",
    },
    {
        "id": "demo-002",
        "unique_product_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
        "title": "Urban Cipher",
        "description": "Bold geometric graphic hoodie. Code your own aesthetic.",
        "creator_id": "creator-002",
        "creator_username": "zayan.creates",
        "creator_avatar": "https://api.dicebear.com/7.x/avataaars/svg?seed=zayan",
        "creator_tier": "emerging_talent",
        "product_type": "hoodie",
        "selected_colors": ["black", "burgundy"],
        "price_paise": 189900,
        "mockup_urls": {
            "hoodie_black":    "https://images.unsplash.com/photo-1551698618-1dfe5d97d256?w=600&q=80",
            "hoodie_burgundy": "https://images.unsplash.com/photo-1527719327859-c6ce80353573?w=600&q=80",
        },
        "total_likes": 980,
        "total_sales": 134,
        "status": "published",
        "created_at": "2026-03-18T14:00:00Z",
    },
    {
        "id": "demo-003",
        "unique_product_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
        "title": "Chaos Theory",
        "description": "Abstract splatter art on premium drop-shoulder tee.",
        "creator_id": "creator-003",
        "creator_username": "meera.ink",
        "creator_avatar": "https://api.dicebear.com/7.x/avataaars/svg?seed=meera",
        "creator_tier": "platform_icon",
        "product_type": "tshirt",
        "selected_colors": ["white", "sage", "coral"],
        "price_paise": 149900,
        "mockup_urls": {
            "tshirt_white": "https://images.unsplash.com/photo-1586790170083-2f9ceadc732d?w=600&q=80",
            "tshirt_sage":  "https://images.unsplash.com/photo-1523381210434-271e8be1f52b?w=600&q=80",
            "tshirt_coral": "https://images.unsplash.com/photo-1556821840-3a63f15732ce?w=600&q=80",
        },
        "total_likes": 3200,
        "total_sales": 512,
        "status": "published",
        "created_at": "2026-03-15T09:00:00Z",
    },
]

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
        currency = detect_currency_from_headers(self.headers)

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
                # Accept both legacy ('active') and new ('published') statuses in the public feed
                # so older rows remain visible while design_publish.py writes status='published'.
                query = (
                    supabase.table("creator_designs")
                    .select(
                        "id, title, description, flux_editorial_image_url, flat_image_url, "
                        "price, total_sales, total_likes, category, tags, created_at, "
                        "shopify_product_id, shopify_product_url, status, "
                        "creators(username, narrative_name, avatar_url, style_influence_rank, commission_tier)"
                    )
                    .in_("status", ["active", "published"])
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
                        "creator_narrative_name": creator_info.get("narrative_name", ""),
                        "creator_avatar": creator_info.get("avatar_url", ""),
                        "creator_tier": rank,
                        "creator_tier_label": RANK_LABELS.get(rank, {}).get("label", ""),
                        "creator_tier_emoji": RANK_LABELS.get(rank, {}).get("emoji", ""),
                        "shopify_product_url": (
                            d.get("shopify_product_url")
                            or (f"/products/{d.get('shopify_product_id', '')}"
                                if d.get("shopify_product_id") else "/collections/all")
                        ),
                    })

                # count total
                count_res = (
                    supabase.table("creator_designs")
                    .select("id", count="exact")
                    .in_("status", ["active", "published"])
                    .execute()
                )
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
                    self.send_json_response(200, {"success": True, "data": [], "designs": []})
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
                            d.get("shopify_product_url")
                            or (f"/products/{d.get('shopify_product_id', '')}"
                                if d.get("shopify_product_id") else "")
                        ),
                    })
                # Return under BOTH `data` and `designs` so old and new consumers work.
                self.send_json_response(200, {"success": True, "data": designs, "designs": designs})
            except Exception as e:
                self.send_json_response(200, {"success": True, "data": [], "designs": []})
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

        # ------ GET /api/design/feed/health ------
        if path == '/api/design/feed/health':
            self.send_json_response(200, {
                "status": "ok",
                "message": "Design Social Feed v1.0",
                "endpoints": [
                    "GET /api/design/feed             — list published designs",
                    "GET /api/design/feed?id=<uuid>   — single design",
                    "GET /api/design/feed/health       — health check",
                ]
            })
            return

        # ------ GET /api/design/feed ------
        if path == '/api/design/feed':
            design_id = params.get("id", [None])[0]
            if design_id:
                self._handle_feed_single(design_id, currency)
            else:
                self._handle_feed_list(params, currency)
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
                    .select("id, title, description, flux_editorial_image_url, flat_image_url, price, total_sales, total_likes, category, created_at, shopify_product_id, shopify_product_url, status")
                    .in_("status", ["active", "published"])
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
        # Creator submits a new design to the feed. Accepts two payload shapes:
        #   (a) AI studio:   { user_id, title, image_url, price, category, tags, shopify_product_id }
        #   (b) Upload flow: { user_id, title, design_file_url, flat_image_url, source, placement,
        #                     color, status }  ← status defaults to 'draft'
        # Drafts are NOT shown in the public feed; they appear only on the creator dashboard
        # until the creator hits /api/design/publish.
        if path == '/api/designs/submit':
            user_id     = body.get('user_id')
            title       = (body.get('title') or 'Untitled').strip()
            description = (body.get('description') or '').strip()
            # Accept image_url, design_file_url, or flat_image_url
            image_url   = (
                body.get('image_url')
                or body.get('design_file_url')
                or body.get('flat_image_url')
                or ''
            ).strip()
            try:
                price = int(body.get('price', 1299))
            except (TypeError, ValueError):
                price = 1299
            category    = body.get('category', 'tee')
            tags        = body.get('tags', []) or []
            shopify_product_id = body.get('shopify_product_id', '')
            source      = body.get('source', 'creator_upload')
            placement   = body.get('placement', 'front')
            color       = body.get('color', '')
            # Accept any of: 'draft', 'ready', 'active', 'published'; normalize.
            req_status = (body.get('status') or 'draft').lower().strip()
            if req_status not in ('draft', 'ready', 'active', 'published'):
                req_status = 'draft'

            if not user_id or not image_url:
                self.send_json_response(400, {"success": False, "error": "user_id and an image url (image_url / design_file_url / flat_image_url) are required"})
                return

            supabase = get_supabase()
            if not supabase:
                demo_id = str(uuid.uuid4())
                self.send_json_response(200, {
                    "success": True,
                    "message": "Design submitted (demo mode)",
                    "design_id": demo_id,
                    "id": demo_id,
                    "status": req_status,
                    "data": {"id": demo_id, "status": req_status, "image_url": image_url}
                })
                return

            try:
                # Resolve creator DB id from shopify customer id; auto-create a minimal
                # creator row if missing so upload flow doesn't dead-end when user hasn't
                # finished onboarding yet.
                creator_res = supabase.table("creators").select("id, active_listings").eq("shopify_customer_id", user_id).execute()
                if not creator_res.data:
                    ins = supabase.table("creators").insert({
                        "shopify_customer_id": user_id,
                        "username": f"creator_{str(user_id)[-6:]}",
                        "balance": 0,
                        "lifetime_earnings": 0,
                        "total_items_sold": 0,
                        "active_listings": 0,
                        "commission_tier": "standard",
                        "commission_rate": 15,
                        "style_influence_rank": "rookie_designer",
                        "onboarding_completed": False,
                        "created_at": datetime.utcnow().isoformat(),
                    }).execute()
                    creator_db_id = ins.data[0]["id"] if ins.data else None
                    current_active = 0
                    if not creator_db_id:
                        self.send_json_response(500, {"success": False, "error": "Could not create creator record"})
                        return
                else:
                    creator_db_id = creator_res.data[0]["id"]
                    current_active = creator_res.data[0].get("active_listings", 0) or 0

                design = {
                    "creator_id": creator_db_id,
                    "title": title,
                    "description": description,
                    "flux_editorial_image_url": image_url,
                    "flat_image_url": image_url,
                    "price": price,
                    "category": category,
                    "tags": tags,
                    "status": req_status,
                    "source": source,
                    "placement": placement,
                    "color": color,
                    "total_sales": 0,
                    "total_likes": 0,
                    "shopify_product_id": shopify_product_id,
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat(),
                }
                result = supabase.table("creator_designs").insert(design).execute()
                inserted = result.data[0] if result.data else {}
                design_id = inserted.get("id")

                # Only bump active_listings when it's actually public
                if req_status in ('active', 'published') and design_id:
                    supabase.table("creators").update({"active_listings": current_active + 1}).eq("id", creator_db_id).execute()

                self.send_json_response(200, {
                    "success": True,
                    "message": "Design saved",
                    "design_id": design_id,
                    "id": design_id,
                    "status": req_status,
                    "data": {"id": design_id, "status": req_status, "image_url": image_url}
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

    def _handle_feed_single(self, design_id, currency="INR"):
        supabase = get_supabase()
        if not supabase:
            for d in DEMO_DESIGNS_SOCIAL:
                if d["id"] == design_id or d["unique_product_id"] == design_id:
                    return self.send_json_response(200, {
                        "success": True, "demo_mode": True,
                        "design": enrich_design_with_variant_map(dict(d), currency)
                    })
            self.send_json_response(404, {"error": "Design not found (demo mode)"})
            return
        try:
            resp = supabase.table("creator_designs").select(
                "id, unique_product_id, title, description, creator_id, "
                "product_type, selected_colors, price_paise, mockup_urls, "
                "total_likes, total_sales, status, created_at"
            ).eq("id", design_id).eq("status", "published").execute()
            if not resp.data:
                return self.send_json_response(404, {"error": "Design not found"})
            design = enrich_design_with_variant_map(resp.data[0], currency)
            self.send_json_response(200, {"success": True, "design": design})
        except Exception:
            for d in DEMO_DESIGNS_SOCIAL:
                if d["id"] == design_id or d["unique_product_id"] == design_id:
                    return self.send_json_response(200, {
                        "success": True, "demo_mode": True,
                        "design": enrich_design_with_variant_map(dict(d), currency)
                    })
            self.send_json_response(404, {"error": "Design not found (demo mode)"})

    def _handle_feed_list(self, params, currency="INR"):
        page     = max(1, int(params.get("page", ["1"])[0]))
        limit    = min(50, max(1, int(params.get("limit", ["12"])[0])))
        sort_by  = params.get("sort", ["latest"])[0]
        product  = params.get("product", ["all"])[0]
        creator  = params.get("creator", [None])[0]
        offset   = (page - 1) * limit

        try:
            supabase = get_supabase()
            if not supabase:
                raise ValueError("supabase_not_configured")
            query = supabase.table("creator_designs").select(
                "id, unique_product_id, title, description, creator_id, "
                "product_type, selected_colors, price_paise, mockup_urls, "
                "total_likes, total_sales, status, created_at",
                count="exact"
            ).eq("status", "published")
            if product != "all":
                query = query.eq("product_type", product)
            if creator:
                query = query.eq("creator_id", creator)
            if sort_by == "popular":
                query = query.order("total_likes", desc=True)
            elif sort_by == "trending":
                query = query.order("total_sales", desc=True)
            else:
                query = query.order("created_at", desc=True)
            query = query.range(offset, offset + limit - 1)
            resp = query.execute()
            designs = [enrich_design_with_variant_map(d, currency) for d in (resp.data or [])]
            total = resp.count or 0
            self.send_json_response(200, {
                "success": True,
                "designs": designs,
                "pagination": {
                    "page": page, "limit": limit,
                    "total": total, "has_more": offset + limit < total,
                }
            })
        except Exception:
            demos = [enrich_design_with_variant_map(dict(d), currency) for d in DEMO_DESIGNS_SOCIAL]
            if product != "all":
                demos = [d for d in demos if d.get("product_type") == product]
            self.send_json_response(200, {
                "success": True,
                "demo_mode": True,
                "designs": demos[offset:offset + limit],
                "pagination": {
                    "page": page, "limit": limit,
                    "total": len(demos), "has_more": offset + limit < len(demos),
                }
            })
