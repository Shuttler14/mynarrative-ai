"""Temporary seed endpoint — remove after testing."""
from http.server import BaseHTTPRequestHandler
import json, os, sys, uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api.core.supabase import sb_request

BRAND_A = "7fcf3029-86e6-43ab-a256-9518d32458f8"

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            cl = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(cl)) if cl > 0 else {}
            action = body.get("action", "seed")
            if action == "seed":
                r = self._seed()
            elif action == "status":
                r = self._status()
            else:
                self.send_response(400)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(r, default=str).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def _seed(self):
        res = {}
        brand_b_id = str(uuid.uuid4())
        sb_request("POST", "/rest/v1/brands", {"id": brand_b_id, "name": "H&M", "slug": "hm", "status": "active"})
        res["supplier_brand"] = brand_b_id

        products = [
            {"title": "Oversized Blazer", "category": "outerwear", "price": 3999, "color": "black", "gender": "women",
             "image_url": "https://images.unsplash.com/photo-1591047139829-d91aecb6caea?w=512"},
            {"title": "Tailored Trousers", "category": "bottoms", "price": 2499, "color": "navy", "gender": "women",
             "image_url": "https://images.unsplash.com/photo-1594938298603-c8148c4dae35?w=512"},
            {"title": "Silk Camisole", "category": "tops", "price": 1999, "color": "cream", "gender": "women",
             "image_url": "https://images.unsplash.com/photo-1564257631407-4deb1f99d992?w=512"},
            {"title": "Pleated Midi Skirt", "category": "bottoms", "price": 2999, "color": "emerald", "gender": "women",
             "image_url": "https://images.unsplash.com/photo-1583496661160-fb5886a0aaaa?w=512"},
            {"title": "Leather Tote Bag", "category": "accessories", "price": 4999, "color": "tan", "gender": "women",
             "image_url": "https://images.unsplash.com/photo-1548036328-c9fa89d128fa?w=512"},
        ]
        for p in products:
            sb_request("POST", "/rest/v1/brand_catalogs", {"id": str(uuid.uuid4()), "brand_id": brand_b_id, "is_active": True, **p})
        res["products"] = len(products)

        existing = sb_request("GET", f"/rest/v1/host_preferences?brand_id=eq.{BRAND_A}&select=id")
        if isinstance(existing, list) and len(existing) > 0:
            sb_request("PATCH", f"/rest/v1/host_preferences?brand_id=eq.{BRAND_A}", {"network_mode": "curated_network", "max_cross_brand_ratio": 0.3})
        else:
            sb_request("POST", "/rest/v1/host_preferences", {"brand_id": BRAND_A, "network_mode": "curated_network", "max_cross_brand_ratio": 0.3})
        res["host_mode"] = "curated_network"

        for cat in ["tops", "bottoms", "outerwear", "accessories"]:
            sb_request("POST", "/rest/v1/host_category_rules", {"brand_id": BRAND_A, "category": cat, "allow_external": True, "max_external_products": 5})
        res["rules"] = 4
        return res

    def _status(self):
        brands = sb_request("GET", "/rest/v1/brands?select=id,name&limit=10")
        prefs = sb_request("GET", f"/rest/v1/host_preferences?brand_id=eq.{BRAND_A}&select=network_mode")
        catalogs = sb_request("GET", "/rest/v1/brand_catalogs?select=id,brand_id,title,category&limit=20")
        rules = sb_request("GET", f"/rest/v1/host_category_rules?brand_id=eq.{BRAND_A}&select=category")
        return {
            "brands": brands or [],
            "host_prefs": prefs or [],
            "catalog_count": len(catalogs) if isinstance(catalogs, list) else 0,
            "catalogs": catalogs or [],
            "rules": rules or [],
        }

    def log_message(self, format, *args):
        pass
