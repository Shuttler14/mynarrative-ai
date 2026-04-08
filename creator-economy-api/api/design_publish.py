"""
design_publish.py — My Narrative Design-to-Earn Pipeline
=========================================================

ARCHITECTURAL DECISION (CRITICAL — DO NOT REVERT):
----------------------------------------------------
We use exactly 2 global parent Shopify products (1 T-Shirt, 1 Hoodie).
All creators share these same parent products and their 5 color variants.

RACE CONDITION AVOIDED:
  ❌ OLD (BROKEN): Update Shopify Product Metafield with unique_product_id
     → Creator B's publish overwrites Creator A's metafield on the SAME product
     → Print provider reads wrong design for Creator A's orders

  ✅ CORRECT (THIS FILE): Publish = Supabase database record update ONLY.
     The unique_product_id travels with ORDERS via Cart Line-Item Properties:
       _design_uuid: <S3_UUID>
     Print provider reads from order.line_items[].properties, NOT from product metafields.

Endpoints:
  POST /api/design/publish        — Mark a design as published in Supabase
  GET  /api/design/publish/health — Health check
"""

from http.server import BaseHTTPRequestHandler
import json
import os
from urllib.parse import urlparse
import urllib.request
import urllib.parse
import urllib.error

# =====================================================
# SHOPIFY VARIANT IDs — used by the FRONTEND cart only
# These are returned so the frontend knows which
# Shopify variant GID to add to cart for each color.
# The parent products are NEVER mutated.
# =====================================================
TSHIRT_COLOR_VARIANT_MAP = {
    "white":   os.environ.get("TSHIRT_VARIANT_WHITE",   "gid://shopify/ProductVariant/TSHIRT_WHITE_ID"),
    "black":   os.environ.get("TSHIRT_VARIANT_BLACK",   "gid://shopify/ProductVariant/TSHIRT_BLACK_ID"),
    "navy":    os.environ.get("TSHIRT_VARIANT_NAVY",    "gid://shopify/ProductVariant/TSHIRT_NAVY_ID"),
    "sage":    os.environ.get("TSHIRT_VARIANT_SAGE",    "gid://shopify/ProductVariant/TSHIRT_SAGE_ID"),
    "coral":   os.environ.get("TSHIRT_VARIANT_CORAL",   "gid://shopify/ProductVariant/TSHIRT_CORAL_ID"),
}

HOODIE_COLOR_VARIANT_MAP = {
    "white":    os.environ.get("HOODIE_VARIANT_WHITE",    "gid://shopify/ProductVariant/HOODIE_WHITE_ID"),
    "black":    os.environ.get("HOODIE_VARIANT_BLACK",    "gid://shopify/ProductVariant/HOODIE_BLACK_ID"),
    "navy":     os.environ.get("HOODIE_VARIANT_NAVY",     "gid://shopify/ProductVariant/HOODIE_NAVY_ID"),
    "burgundy": os.environ.get("HOODIE_VARIANT_BURGUNDY", "gid://shopify/ProductVariant/HOODIE_BURGUNDY_ID"),
    "forest":   os.environ.get("HOODIE_VARIANT_FOREST",   "gid://shopify/ProductVariant/HOODIE_FOREST_ID"),
}

# Numeric Shopify variant IDs (integer form needed by Storefront Cart API)
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

# =====================================================
# PRICE BOUNDS (in paise — 1 INR = 100 paise)
# =====================================================
PRICE_BOUNDS = {
    "tshirt": {"min": 64900, "max": 99900},
    "hoodie": {"min": 119900, "max": 189900},
}


# ============================================================
# URLLIB-BASED SUPABASE CLIENT HELPERS
# ============================================================
def _sb_headers():
    """Return (url, key, headers) for Supabase REST API."""
    url = os.environ.get('SUPABASE_URL', '')
    key = os.environ.get('SUPABASE_KEY', '')
    return url, key, {
        'apikey': key,
        'Authorization': f'Bearer {key}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Prefer': 'return=representation',
    }


def sb_configured():
    """Check if Supabase is configured."""
    url, key, _ = _sb_headers()
    return bool(url and key)


def sb_get(table, select='*', filters=None, order=None, limit=None):
    """
    GET request to Supabase REST API.
    
    Args:
        table: Table name
        select: Comma-separated columns (default '*')
        filters: Dict of {column: f'eq.{value}'} for filtering
        order: Order clause (e.g., 'id.desc')
        limit: Row limit as string
    
    Returns:
        (data_list, error_str) tuple. data_list is [] if error.
    """
    url, key, headers = _sb_headers()
    if not url or not key:
        return [], 'not_configured'
    
    params = {'select': select}
    if filters:
        params.update(filters)
    if order:
        params['order'] = order
    if limit:
        params['limit'] = str(limit)
    
    full_url = f"{url.rstrip('/')}/rest/v1/{table}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(full_url, headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
            return (data if isinstance(data, list) else []), None
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()[:100]
        return [], f'HTTP {e.code}: {error_body}'
    except Exception as e:
        return [], str(e)


def sb_patch(table, data, filter_col, filter_val, filter_col2=None, filter_val2=None):
    """
    PATCH request to Supabase REST API (update).
    
    Args:
        table: Table name
        data: Dict with fields to update
        filter_col: Column name for first filter
        filter_val: Value for first filter
        filter_col2: Optional second filter column
        filter_val2: Optional second filter value
    
    Returns:
        (response_obj, error_str) tuple. response_obj is None if error.
    """
    url, key, headers = _sb_headers()
    if not url or not key:
        return None, 'not_configured'
    
    params = {filter_col: f'eq.{filter_val}'}
    if filter_col2 and filter_val2:
        params[filter_col2] = f'eq.{filter_val2}'
    
    full_url = f"{url.rstrip('/')}/rest/v1/{table}?{urllib.parse.urlencode(params)}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(full_url, data=body, headers=headers, method='PATCH')
    
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            resp = json.loads(r.read().decode())
            return resp, None
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()[:100]
        return None, f'HTTP {e.code}: {error_body}'
    except Exception as e:
        return None, str(e)


def build_variant_map(product_type, selected_colors):
    """
    Return a dict mapping color -> {variant_id_gid, variant_id_numeric}
    for use by the frontend cart logic.
    These are the STATIC global variant IDs — they never change.
    """
    color_map = TSHIRT_COLOR_VARIANT_MAP if product_type == "tshirt" else HOODIE_COLOR_VARIANT_MAP
    numeric_map = TSHIRT_NUMERIC_VARIANT_MAP if product_type == "tshirt" else HOODIE_NUMERIC_VARIANT_MAP
    result = {}
    for color in selected_colors:
        c = color.lower().strip()
        if c in color_map:
            result[c] = {
                "variant_gid": color_map[c],
                "variant_numeric": numeric_map.get(c, ""),
            }
    return result


class handler(BaseHTTPRequestHandler):

    def send_json_response(self, status_code, data):
        """Send a JSON response with CORS headers."""
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
        if parsed.path == "/api/design/publish/health":
            self.send_json_response(200, {
                "status": "ok",
                "message": "Design Publish Handler v2.0 — Supabase-only, no Shopify product mutation",
                "architecture": (
                    "Publish records the design in Supabase (status=published). "
                    "The unique_product_id travels with orders via Shopify Cart Line-Item Properties "
                    "(_design_uuid). Print provider reads from order line-item properties, not product metafields."
                ),
                "endpoints": [
                    "POST /api/design/publish       — publish design (Supabase update only)",
                    "GET  /api/design/publish/health — health check",
                ]
            })
            return
        self.send_json_response(404, {"error": "Not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_length)

        try:
            body = json.loads(body_bytes.decode("utf-8"))
        except Exception:
            self.send_json_response(400, {"error": "Invalid JSON body"})
            return

        if parsed.path == "/api/design/publish":
            self._handle_publish(body)
            return

        self.send_json_response(404, {"error": "Not found"})

    def _handle_publish(self, body):
        """
        Publish a creator design.

        What this does:
          1. Validate input + price bounds
          2. Fetch design from Supabase — ensure status == 'ready'
          3. Update Supabase: status = 'published', store listing metadata
          4. Return variant IDs + unique_product_id to the frontend
             so it can build the correct cart payload with _design_uuid property

        What this does NOT do (intentionally):
          ❌ Does NOT call Shopify Admin API
          ❌ Does NOT update any Shopify Product Metafield
          ❌ Does NOT create new Shopify products or variants
          The 2 parent products remain completely untouched.
        """
        # ------------------------------------------------------------------
        # 1. VALIDATE INPUT
        # ------------------------------------------------------------------
        required = ["design_id", "creator_id", "title", "product_type",
                    "selected_colors", "price_paise"]
        for field in required:
            if field not in body:
                self.send_json_response(400, {"error": f"Missing required field: {field}"})
                return

        design_id      = str(body.get("design_id", "")).strip()
        creator_id     = str(body.get("creator_id", "")).strip()
        title          = str(body.get("title", "")).strip()[:60]
        description    = str(body.get("description", "")).strip()[:300]
        product_type   = str(body.get("product_type", "")).lower().strip()
        selected_colors = body.get("selected_colors", [])
        price_paise    = body.get("price_paise")
        mockup_urls    = body.get("mockup_urls", {})

        if not design_id or not creator_id or not title:
            self.send_json_response(400, {"error": "design_id, creator_id, and title must not be empty"})
            return

        if product_type not in ("tshirt", "hoodie"):
            self.send_json_response(400, {"error": "product_type must be 'tshirt' or 'hoodie'"})
            return

        if not isinstance(selected_colors, list) or len(selected_colors) == 0:
            self.send_json_response(400, {"error": "selected_colors must be a non-empty list"})
            return

        # Validate colors are valid for chosen product type
        valid_colors = set(
            TSHIRT_COLOR_VARIANT_MAP.keys() if product_type == "tshirt"
            else HOODIE_COLOR_VARIANT_MAP.keys()
        )
        invalid = [c for c in selected_colors if c.lower().strip() not in valid_colors]
        if invalid:
            self.send_json_response(400, {
                "error": f"Invalid color(s) for {product_type}: {invalid}",
                "valid_colors": sorted(valid_colors)
            })
            return

        try:
            price_paise = int(price_paise)
        except (ValueError, TypeError):
            self.send_json_response(400, {"error": "price_paise must be an integer"})
            return

        bounds = PRICE_BOUNDS[product_type]
        if not (bounds["min"] <= price_paise <= bounds["max"]):
            self.send_json_response(400, {
                "error": (
                    f"price_paise {price_paise} is out of bounds for {product_type}. "
                    f"Must be between {bounds['min']} (₹{bounds['min']//100}) "
                    f"and {bounds['max']} (₹{bounds['max']//100})"
                )
            })
            return

        # ------------------------------------------------------------------
        # 2. FETCH DESIGN FROM SUPABASE
        # ------------------------------------------------------------------
        if not sb_configured():
            # Demo mode — return mock success so frontend can be tested
            variant_map = build_variant_map(product_type, selected_colors)
            demo_uuid = f"demo-uuid-{design_id[:8]}"
            self.send_json_response(200, {
                "status": "published",
                "demo_mode": True,
                "design_id": design_id,
                "unique_product_id": demo_uuid,
                "product_type": product_type,
                "selected_colors": selected_colors,
                "price_rupees": price_paise / 100,
                "variant_map": variant_map,
                "cart_instructions": {
                    "note": (
                        "When adding to cart, use the variant_id for the chosen color "
                        "and include _design_uuid as a line-item property."
                    ),
                    "example_cart_payload": {
                        "items": [{
                            "id": variant_map.get(selected_colors[0], {}).get("variant_numeric", "VARIANT_ID"),
                            "quantity": 1,
                            "properties": {
                                "_design_uuid": demo_uuid,
                                "_design_title": title,
                                "_creator_id": creator_id,
                                "_product_type": product_type,
                                "_color": selected_colors[0],
                            }
                        }]
                    }
                }
            })
            return

        try:
            design_data, err = sb_get('creator_designs', '*', filters={'id': f'eq.{design_id}'})
            if err or not design_data:
                self.send_json_response(404, {"error": f"Design {design_id} not found"})
                return

            design = design_data[0]
            unique_product_id = design.get("unique_product_id")
            status = design.get("status")

            if status not in ("ready", "published"):
                self.send_json_response(409, {
                    "error": f"Design status is '{status}'. Must be 'ready' to publish.",
                    "hint": "Ensure the pipeline (POST /api/design/process) has completed successfully."
                })
                return

            if not unique_product_id:
                self.send_json_response(400, {
                    "error": "Design is missing unique_product_id. Re-run the pipeline."
                })
                return

        except Exception as e:
            self.send_json_response(500, {"error": f"Supabase query failed: {str(e)}"})
            return

        # ------------------------------------------------------------------
        # 3. UPDATE SUPABASE — status = 'published', store listing metadata
        #    NO Shopify API call. The 2 parent products are not touched.
        # ------------------------------------------------------------------
        try:
            _, err = sb_patch('creator_designs', {
                "status":          "published",
                "title":           title,
                "description":     description,
                "product_type":    product_type,
                "selected_colors": selected_colors,
                "price_paise":     price_paise,
                "mockup_urls":     mockup_urls,
            }, 'id', design_id)
            if err:
                self.send_json_response(500, {"error": f"Failed to update design in Supabase: {err}"})
                return
        except Exception as e:
            self.send_json_response(500, {"error": f"Failed to update design in Supabase: {str(e)}"})
            return

        # ------------------------------------------------------------------
        # 4. RETURN VARIANT MAP + unique_product_id TO FRONTEND
        #    Frontend uses this to build the Shopify cart payload with
        #    _design_uuid as a line-item property.
        # ------------------------------------------------------------------
        variant_map = build_variant_map(product_type, selected_colors)
        price_rupees = price_paise / 100

        self.send_json_response(200, {
            "status": "published",
            "design_id": design_id,
            "unique_product_id": unique_product_id,
            "product_type": product_type,
            "selected_colors": selected_colors,
            "price_rupees": price_rupees,
            "title": title,
            "mockup_urls": mockup_urls,
            "variant_map": variant_map,
            # ---------------------------------------------------------------
            # HOW THE PRINT PROVIDER GETS THE DESIGN:
            # When a customer clicks "Buy", the frontend must call:
            #   POST /cart/add.js
            #   { items: [{ id: <variant_numeric_id>, quantity: 1,
            #               properties: {
            #                 _design_uuid: <unique_product_id>,
            #                 _design_title: <title>,
            #                 _creator_id: <creator_id>,
            #                 _product_type: <tshirt|hoodie>,
            #                 _color: <color>
            #               }}]}
            # Shopify then embeds these properties in the order's line_items.
            # The webhook (design_order_webhook.py) reads them on orders/create.
            # ---------------------------------------------------------------
            "cart_instructions": {
                "note": (
                    "Add to cart using the numeric variant_id for the chosen color. "
                    "Always include _design_uuid as a line-item property. "
                    "The print provider reads _design_uuid from the order, NOT from the product metafield."
                ),
                "endpoint": "POST /cart/add.js (Shopify Storefront)",
                "example_payload": {
                    "items": [{
                        "id": "{{variant_numeric_id}}",
                        "quantity": 1,
                        "properties": {
                            "_design_uuid":   unique_product_id,
                            "_design_title":  title,
                            "_creator_id":    creator_id,
                            "_product_type":  product_type,
                            "_color":         "{{selected_color}}",
                        }
                    }]
                }
            }
        })
