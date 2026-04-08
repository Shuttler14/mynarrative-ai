"""
design_social_feed.py — My Narrative Published Designs Feed
============================================================

Serves the public social feed of published creator designs.
Data source: Supabase `creator_designs` table (status = 'published').

This endpoint powers the storefront feed cards. Each card includes
the mockup image, creator info, pricing, and — critically — the
variant_map so the frontend can build a correct Shopify cart payload
with _design_uuid as a line-item property.

Endpoints:
  GET  /api/design/feed              — list published designs (paginated)
  GET  /api/design/feed?id=<uuid>    — single design detail
  GET  /api/design/feed/health       — health check
"""

# ─────────────────────────────────────────────────────────────────
# STEP 0 (MUST BE FIRST): Redirect all library caches to /tmp.
# Vercel's Lambda filesystem is read-only everywhere except /tmp.
# Any library that tries to write a cache on import will raise
# [Errno 16] Device or resource busy and crash before handler runs.
# ─────────────────────────────────────────────────────────────────
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
# Ensure /tmp subdirs exist
for _d in ['/tmp/matplotlib', '/tmp/fontconfig']:
    try:
        _os.makedirs(_d, exist_ok=True)
    except Exception:
        pass

from http.server import BaseHTTPRequestHandler
import json
import os
import sys
from urllib.parse import urlparse, parse_qs

# Variant maps — same as design_publish.py (source of truth is env vars)
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


DEMO_DESIGNS = [
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


def get_supabase():
    try:
        from supabase import create_client
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_KEY", "")
        if url and key:
            return create_client(url, key)
    except Exception as e:
        print(f"Supabase init error: {e}")
    return None


def safe_requests_get(url, **kwargs):
    """requests.get wrapper — falls back gracefully if requests not available."""
    try:
        import requests
        return requests.get(url, **kwargs)
    except Exception:
        return None


def enrich_design_with_variant_map(design):
    """
    Attach variant_map to a design record so the frontend can build
    the correct Shopify cart payload without any extra API calls.
    """
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
    return design


class handler(BaseHTTPRequestHandler):

    def send_json_response(self, status_code, data):
        self.send_response(status_code)
        self.send_header("Content-type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        path = parsed.path

        if path == "/api/design/feed/health":
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

        if path == "/api/design/feed":
            design_id = params.get("id", [None])[0]
            if design_id:
                self._handle_get_single(design_id)
            else:
                self._handle_list(params)
            return

        self.send_json_response(404, {"error": "Not found"})

    def _handle_get_single(self, design_id):
        """Return a single published design by its UUID."""
        try:
            supabase = get_supabase()
            if not supabase:
                raise ValueError("supabase_not_configured")
            resp = supabase.table("creator_designs").select(
                "id, unique_product_id, title, description, creator_id, "
                "product_type, selected_colors, price_paise, mockup_urls, "
                "total_likes, total_sales, status, created_at"
            ).eq("id", design_id).eq("status", "published").execute()
            if not resp.data:
                return self.send_json_response(404, {"error": "Design not found"})
            design = enrich_design_with_variant_map(resp.data[0])
            self.send_json_response(200, {"success": True, "design": design})
        except Exception:
            # Demo mode fallback
            for d in DEMO_DESIGNS:
                if d["id"] == design_id or d["unique_product_id"] == design_id:
                    return self.send_json_response(200, {
                        "success": True, "demo_mode": True,
                        "design": enrich_design_with_variant_map(dict(d))
                    })
            self.send_json_response(404, {"error": "Design not found (demo mode)"})

    def _handle_list(self, params):
        """
        Return paginated list of published designs.

        Query params:
          page      (int, default 1)
          limit     (int, default 12, max 50)
          sort      (latest|popular|trending, default latest)
          product   (tshirt|hoodie|all, default all)
          creator   (creator_id to filter by one creator)
        """
        page     = max(1, int(params.get("page", ["1"])[0]))
        limit    = min(50, max(1, int(params.get("limit", ["12"])[0])))
        sort_by  = params.get("sort", ["latest"])[0]
        product  = params.get("product", ["all"])[0]
        creator  = params.get("creator", [None])[0]
        offset   = (page - 1) * limit

        # Always try Supabase but fall back to demo on ANY error (incl. [Errno 16])
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
            resp  = query.execute()
            designs = [enrich_design_with_variant_map(d) for d in (resp.data or [])]
            total   = resp.count or 0

            self.send_json_response(200, {
                "success": True,
                "designs": designs,
                "pagination": {
                    "page": page, "limit": limit,
                    "total": total, "has_more": offset + limit < total,
                }
            })
        except Exception:
            # Demo mode fallback — covers no-Supabase, [Errno 16], cold-start issues
            demos = [enrich_design_with_variant_map(dict(d)) for d in DEMO_DESIGNS]
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
