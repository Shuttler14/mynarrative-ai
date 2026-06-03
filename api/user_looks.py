"""
================================================================================
  MY NARRATIVE AI — USER LOOKS LIBRARY
  api/user_looks.py
================================================================================

  PURPOSE:
  Vercel Serverless Function for saving, retrieving, and sharing
  virtual try-on results in the user's personal looks library.

  ENDPOINTS:
    POST /api/user_looks  — save_look, get_looks, get_look, toggle_favorite,
                            delete_look, get_stats
    GET  /api/user_looks   — get_looks (paginated), get_look (by share token)

  REQUIRED ENVIRONMENT VARIABLES:
  ─────────────────────────────────
  SUPABASE_URL       → Supabase project REST URL
  SUPABASE_KEY       → Supabase anon/service key
  APP_BASE_URL       → Frontend origin for shareable links (optional)

================================================================================
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import time
import uuid
import base64
import urllib.parse
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

APP_BASE_URL = os.environ.get("APP_BASE_URL", "https://mynarrative.in").rstrip("/")

# Supabase Storage bucket for user look result images
LOOKS_BUCKET = "user-looks"

# Pagination defaults
DEFAULT_PAGE = 1
DEFAULT_LIMIT = 20
MAX_LIMIT = 100


# ---------------------------------------------------------------------------
# SUPABASE REST HELPERS (mirrors stylist_pipeline.py pattern)
# ---------------------------------------------------------------------------

def _sb_headers() -> Tuple[str, str, dict]:
    """Return (supabase_url, supabase_key, headers) for REST API calls."""
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_KEY", "").strip()
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    return url, key, headers


def _sb_configured() -> bool:
    """Check if Supabase credentials are present."""
    url, key, _ = _sb_headers()
    return bool(url and key)


def _sb_request(method: str, path: str, payload: Any = None,
                extra_headers: Optional[dict] = None) -> Tuple[Any, Optional[str]]:
    """
    Execute a Supabase REST API request.

    Returns:
        (data, None) on success
        (None, error_string) on failure
    """
    url, key, headers = _sb_headers()
    if not url or not key:
        return None, "supabase_not_configured"

    if extra_headers:
        headers.update(extra_headers)

    full_url = f"{url.rstrip('/')}{path}"
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(full_url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8") or "null"
            return json.loads(raw), None
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8")
        except Exception:
            detail = str(e)
        return None, f"http_{e.code}:{detail[:300]}"
    except Exception as e:
        return None, str(e)


def _sb_upload_image(bucket: str, file_path: str,
                     image_bytes: bytes, content_type: str = "image/jpeg") -> Tuple[str, Optional[str]]:
    """
    Upload an image to Supabase Storage via the REST API.

    Returns:
        (public_url, None) on success
        ("", error_string) on failure
    """
    url, key, _ = _sb_headers()
    if not url or not key:
        return "", "supabase_not_configured"

    upload_url = f"{url.rstrip('/')}/storage/v1/object/{bucket}/{file_path}"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": content_type,
        "x-upsert": "true",
    }

    req = urllib.request.Request(upload_url, data=image_bytes, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp.read()  # Consume response
        public_url = f"{url.rstrip('/')}/storage/v1/object/public/{bucket}/{file_path}"
        return public_url, None
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8")
        except Exception:
            detail = str(e)
        return "", f"storage_upload_http_{e.code}:{detail[:300]}"
    except Exception as e:
        return "", f"storage_upload_error:{e}"


def _download_image(image_url: str, timeout: int = 15) -> bytes:
    """Download image bytes from a URL."""
    if not image_url or not isinstance(image_url, str):
        return b""
    req = urllib.request.Request(
        image_url,
        headers={"User-Agent": "MN-UserLooks/1.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception as e:
        print(f"⚠️ [download_image] Failed to download {image_url[:80]}: {e}")
        return b""


# ---------------------------------------------------------------------------
# LOOK ACTION HANDLERS
# ---------------------------------------------------------------------------

def _action_save_look(body: dict) -> Tuple[dict, int]:
    """
    Save a try-on result to the user's looks library.

    1. Downloads the result image from the provided URL
    2. Uploads it to Supabase Storage under user-looks/{user_id}/{look_id}.jpg
    3. Creates a record in the user_looks table
    4. Returns the look_id + shareable URL
    """
    user_id = (body.get("user_id") or "").strip()
    if not user_id:
        return {"success": False, "error": "user_id is required"}, 400

    result_image_url = (body.get("result_image_url") or "").strip()
    if not result_image_url:
        return {"success": False, "error": "result_image_url is required"}, 400

    garments = body.get("garments") or []
    occasion = (body.get("occasion") or "").strip()
    vibe_id = (body.get("vibe_id") or "").strip()
    recommendation_context = body.get("recommendation_context") or {}
    is_favorite = bool(body.get("is_favorite", False))

    look_id = str(uuid.uuid4())
    print(f"📸 [save_look] user={user_id} look_id={look_id}")

    # --- Step 1: Download the result image ---
    image_bytes = b""
    storage_url = result_image_url  # Fallback to original URL

    if result_image_url.startswith("data:image"):
        # Handle base64 data URI
        try:
            header, b64data = result_image_url.split(",", 1)
            image_bytes = base64.b64decode(b64data)
            print(f"📦 [save_look] Decoded base64 image: {len(image_bytes)} bytes")
        except Exception as e:
            print(f"⚠️ [save_look] Base64 decode failed: {e}")
    else:
        image_bytes = _download_image(result_image_url)
        if image_bytes:
            print(f"📥 [save_look] Downloaded image: {len(image_bytes)} bytes")
        else:
            print(f"⚠️ [save_look] Could not download image, storing URL reference only")

    # --- Step 2: Upload to Supabase Storage ---
    if image_bytes:
        file_path = f"{user_id}/{look_id}.jpg"
        uploaded_url, upload_err = _sb_upload_image(
            LOOKS_BUCKET, file_path, image_bytes, "image/jpeg"
        )
        if upload_err:
            print(f"⚠️ [save_look] Storage upload failed: {upload_err}")
            # Fall back to original URL — still save the record
        else:
            storage_url = uploaded_url
            print(f"☁️ [save_look] Uploaded to storage: {storage_url[:80]}")
    else:
        print(f"ℹ️ [save_look] No image bytes to upload, using original URL")

    # --- Step 3: Insert record into user_looks table ---
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    record = {
        "id": look_id,
        "user_id": user_id,
        "result_image_url": storage_url,
        "garments": json.dumps(garments) if isinstance(garments, list) else garments,
        "occasion": occasion,
        "vibe_id": vibe_id,
        "recommendation_context": json.dumps(recommendation_context) if isinstance(recommendation_context, dict) else recommendation_context,
        "is_favorite": is_favorite,
        "is_deleted": False,
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    extra = {"Prefer": "return=representation"}
    data, err = _sb_request("POST", "/rest/v1/user_looks", record, extra_headers=extra)
    if err:
        print(f"❌ [save_look] DB insert failed: {err}")
        return {"success": False, "error": f"Failed to save look: {err}"}, 500

    # Extract share_token from the returned record
    share_token = ""
    if isinstance(data, list) and data:
        share_token = data[0].get("share_token", "")
    elif isinstance(data, dict):
        share_token = data.get("share_token", "")

    share_url = f"/looks/share/{share_token}" if share_token else ""

    print(f"✅ [save_look] Saved successfully — look_id={look_id}, share_token={share_token}")

    return {
        "success": True,
        "look_id": look_id,
        "share_url": share_url,
        "share_token": share_token,
        "image_url": storage_url,
        "created_at": now_iso,
    }, 200


def _action_get_looks(body: dict) -> Tuple[dict, int]:
    """
    Retrieve paginated looks for a user, sorted by created_at DESC.
    Supports filtering by occasion and favorites.
    """
    user_id = (body.get("user_id") or "").strip()
    if not user_id:
        return {"success": False, "error": "user_id is required"}, 400

    page = max(1, int(body.get("page", DEFAULT_PAGE) or DEFAULT_PAGE))
    limit = min(MAX_LIMIT, max(1, int(body.get("limit", DEFAULT_LIMIT) or DEFAULT_LIMIT)))
    offset = (page - 1) * limit

    filter_occasion = (body.get("filter_occasion") or "").strip()
    filter_favorite = body.get("filter_favorite", None)

    print(f"📋 [get_looks] user={user_id} page={page} limit={limit}")

    # Build query path
    query = (
        f"/rest/v1/user_looks"
        f"?select=id,user_id,result_image_url,garments,occasion,vibe_id,"
        f"is_favorite,share_token,created_at,updated_at"
        f"&user_id=eq.{urllib.parse.quote(user_id)}"
        f"&is_deleted=eq.false"
        f"&order=created_at.desc"
        f"&offset={offset}"
        f"&limit={limit}"
    )

    if filter_occasion:
        query += f"&occasion=eq.{urllib.parse.quote(filter_occasion)}"
    if filter_favorite is True or filter_favorite == "true":
        query += "&is_favorite=eq.true"

    # Request with count header for pagination metadata
    extra = {"Prefer": "count=exact"}
    data, err = _sb_request("GET", query, extra_headers=extra)
    if err:
        print(f"❌ [get_looks] Query failed: {err}")
        return {"success": False, "error": f"Failed to retrieve looks: {err}"}, 500

    looks = data if isinstance(data, list) else []

    # Parse JSONB garments field if it comes back as string
    for look in looks:
        if isinstance(look.get("garments"), str):
            try:
                look["garments"] = json.loads(look["garments"])
            except (json.JSONDecodeError, TypeError):
                look["garments"] = []
        # Add share_url
        share_token = look.get("share_token", "")
        look["share_url"] = f"/looks/share/{share_token}" if share_token else ""

    print(f"✅ [get_looks] Returned {len(looks)} looks for user={user_id}")

    return {
        "success": True,
        "looks": looks,
        "page": page,
        "limit": limit,
        "count": len(looks),
    }, 200


def _action_get_look(body: dict) -> Tuple[dict, int]:
    """
    Get a single look by look_id or share_token.
    Public endpoint — does NOT require user_id (for shareable links).
    """
    look_id = (body.get("look_id") or "").strip()
    share_token = (body.get("share_token") or "").strip()

    if not look_id and not share_token:
        return {"success": False, "error": "look_id or share_token is required"}, 400

    # Build query — search by look_id or share_token
    query = (
        "/rest/v1/user_looks"
        "?select=id,user_id,result_image_url,garments,occasion,vibe_id,"
        "recommendation_context,is_favorite,share_token,created_at,updated_at"
        "&is_deleted=eq.false"
        "&limit=1"
    )

    if look_id:
        query += f"&id=eq.{urllib.parse.quote(look_id)}"
        print(f"🔍 [get_look] Fetching look by id={look_id}")
    else:
        query += f"&share_token=eq.{urllib.parse.quote(share_token)}"
        print(f"🔍 [get_look] Fetching look by share_token={share_token}")

    data, err = _sb_request("GET", query)
    if err:
        print(f"❌ [get_look] Query failed: {err}")
        return {"success": False, "error": f"Failed to retrieve look: {err}"}, 500

    if not data or (isinstance(data, list) and len(data) == 0):
        return {"success": False, "error": "Look not found"}, 404

    look = data[0] if isinstance(data, list) else data

    # Parse JSONB fields
    for field in ("garments", "recommendation_context"):
        if isinstance(look.get(field), str):
            try:
                look[field] = json.loads(look[field])
            except (json.JSONDecodeError, TypeError):
                look[field] = [] if field == "garments" else {}

    # Add share_url
    st = look.get("share_token", "")
    look["share_url"] = f"/looks/share/{st}" if st else ""

    print(f"✅ [get_look] Found look id={look.get('id')}")

    return {
        "success": True,
        "look": look,
    }, 200


def _action_toggle_favorite(body: dict) -> Tuple[dict, int]:
    """Toggle the is_favorite flag on a look."""
    user_id = (body.get("user_id") or "").strip()
    look_id = (body.get("look_id") or "").strip()

    if not user_id or not look_id:
        return {"success": False, "error": "user_id and look_id are required"}, 400

    print(f"⭐ [toggle_favorite] user={user_id} look_id={look_id}")

    # Step 1: Fetch current favorite status
    fetch_query = (
        f"/rest/v1/user_looks"
        f"?select=id,is_favorite"
        f"&id=eq.{urllib.parse.quote(look_id)}"
        f"&user_id=eq.{urllib.parse.quote(user_id)}"
        f"&is_deleted=eq.false"
        f"&limit=1"
    )
    data, err = _sb_request("GET", fetch_query)
    if err:
        return {"success": False, "error": f"Failed to fetch look: {err}"}, 500

    if not data or (isinstance(data, list) and len(data) == 0):
        return {"success": False, "error": "Look not found or access denied"}, 404

    current = data[0] if isinstance(data, list) else data
    new_status = not bool(current.get("is_favorite", False))

    # Step 2: Update
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    update_query = (
        f"/rest/v1/user_looks"
        f"?id=eq.{urllib.parse.quote(look_id)}"
        f"&user_id=eq.{urllib.parse.quote(user_id)}"
    )
    update_payload = {
        "is_favorite": new_status,
        "updated_at": now_iso,
    }
    extra = {"Prefer": "return=representation"}
    updated, update_err = _sb_request("PATCH", update_query, update_payload, extra_headers=extra)
    if update_err:
        return {"success": False, "error": f"Failed to update: {update_err}"}, 500

    print(f"✅ [toggle_favorite] look_id={look_id} → is_favorite={new_status}")

    return {
        "success": True,
        "look_id": look_id,
        "is_favorite": new_status,
        "updated_at": now_iso,
    }, 200


def _action_delete_look(body: dict) -> Tuple[dict, int]:
    """Soft-delete a look by setting is_deleted = true."""
    user_id = (body.get("user_id") or "").strip()
    look_id = (body.get("look_id") or "").strip()

    if not user_id or not look_id:
        return {"success": False, "error": "user_id and look_id are required"}, 400

    print(f"🗑️ [delete_look] user={user_id} look_id={look_id}")

    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    update_query = (
        f"/rest/v1/user_looks"
        f"?id=eq.{urllib.parse.quote(look_id)}"
        f"&user_id=eq.{urllib.parse.quote(user_id)}"
        f"&is_deleted=eq.false"
    )
    update_payload = {
        "is_deleted": True,
        "updated_at": now_iso,
    }
    extra = {"Prefer": "return=representation"}
    data, err = _sb_request("PATCH", update_query, update_payload, extra_headers=extra)
    if err:
        return {"success": False, "error": f"Failed to delete look: {err}"}, 500

    if not data or (isinstance(data, list) and len(data) == 0):
        return {"success": False, "error": "Look not found or already deleted"}, 404

    print(f"✅ [delete_look] Soft-deleted look_id={look_id}")

    return {
        "success": True,
        "look_id": look_id,
        "deleted": True,
        "updated_at": now_iso,
    }, 200


def _action_get_stats(body: dict) -> Tuple[dict, int]:
    """
    Get aggregate stats for a user's looks library.

    Returns: total_looks, favorite_looks, looks_by_occasion (breakdown),
             looks_this_month, most_tried_brand, most_tried_category.
    """
    user_id = (body.get("user_id") or "").strip()
    if not user_id:
        return {"success": False, "error": "user_id is required"}, 400

    print(f"📊 [get_stats] user={user_id}")

    # Fetch all non-deleted looks for this user (lightweight fields only)
    query = (
        f"/rest/v1/user_looks"
        f"?select=id,garments,occasion,is_favorite,created_at"
        f"&user_id=eq.{urllib.parse.quote(user_id)}"
        f"&is_deleted=eq.false"
        f"&order=created_at.desc"
        f"&limit=500"
    )
    data, err = _sb_request("GET", query)
    if err:
        return {"success": False, "error": f"Failed to fetch stats: {err}"}, 500

    looks = data if isinstance(data, list) else []

    # --- Compute stats ---
    total_looks = len(looks)
    favorite_looks = 0
    looks_by_occasion: Dict[str, int] = {}
    looks_this_month = 0
    brand_counts: Dict[str, int] = {}
    category_counts: Dict[str, int] = {}

    # Current month boundary (UTC)
    now = time.gmtime()
    month_start = time.strftime("%Y-%m-01T00:00:00Z", now)

    for look in looks:
        # Favorites count
        if look.get("is_favorite"):
            favorite_looks += 1

        # Occasion breakdown
        occ = (look.get("occasion") or "other").strip() or "other"
        looks_by_occasion[occ] = looks_by_occasion.get(occ, 0) + 1

        # This month count
        created = look.get("created_at", "")
        if isinstance(created, str) and created >= month_start:
            looks_this_month += 1

        # Brand & category counts from garments
        garments = look.get("garments", [])
        if isinstance(garments, str):
            try:
                garments = json.loads(garments)
            except (json.JSONDecodeError, TypeError):
                garments = []

        for g in (garments or []):
            if not isinstance(g, dict):
                continue
            brand = (g.get("brand") or "").strip()
            if brand:
                brand_counts[brand] = brand_counts.get(brand, 0) + 1
            cat = (g.get("category") or "").strip()
            if cat:
                category_counts[cat] = category_counts.get(cat, 0) + 1

    # Top brand and category
    most_tried_brand = max(brand_counts, key=brand_counts.get) if brand_counts else ""
    most_tried_category = max(category_counts, key=category_counts.get) if category_counts else ""

    print(f"✅ [get_stats] total={total_looks}, favorites={favorite_looks}, "
          f"this_month={looks_this_month}, top_brand={most_tried_brand}")

    return {
        "success": True,
        "user_id": user_id,
        "total_looks": total_looks,
        "favorite_looks": favorite_looks,
        "looks_by_occasion": looks_by_occasion,
        "looks_this_month": looks_this_month,
        "most_tried_brand": most_tried_brand,
        "most_tried_category": most_tried_category,
        "brand_counts": brand_counts,
        "category_counts": category_counts,
    }, 200


# ---------------------------------------------------------------------------
# ACTION ROUTER
# ---------------------------------------------------------------------------

ACTION_MAP = {
    "save_look": _action_save_look,
    "get_looks": _action_get_looks,
    "get_look": _action_get_look,
    "toggle_favorite": _action_toggle_favorite,
    "delete_look": _action_delete_look,
    "get_stats": _action_get_stats,
}


# ---------------------------------------------------------------------------
# VERCEL SERVERLESS HANDLER
# ---------------------------------------------------------------------------

class handler(BaseHTTPRequestHandler):
    """
    Vercel Serverless Function handler for the User Looks Library API.

    POST /api/user_looks — All actions via JSON body { "action": "..." }
    GET  /api/user_looks  — get_looks / get_look via query parameters
    """

    def _cors_headers(self):
        """Set CORS headers for cross-origin requests."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Max-Age", "86400")

    def _respond(self, status: int, data: dict):
        """Send a JSON response with CORS headers."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self._cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode("utf-8"))

    def _error(self, status: int, message: str):
        """Shorthand for error responses."""
        self._respond(status, {"success": False, "error": message})

    def _success(self, data: dict):
        """Shorthand for success responses."""
        self._respond(200, data)

    # --- OPTIONS (CORS preflight) ---
    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(200)
        self._cors_headers()
        self.end_headers()

    # --- GET ---
    def do_GET(self):
        """
        Handle GET requests with query parameters.
        Supports:
          ?action=get_looks&user_id=xxx[&page=1&limit=20&filter_occasion=...]
          ?action=get_look&look_id=xxx
          ?action=get_look&share_token=xxx
        """
        try:
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)

            action = (params.get("action", [None])[0] or "").strip()

            if not action:
                # Health check / metadata endpoint
                self._success({
                    "service": "My Narrative AI — User Looks Library",
                    "version": "1.0.0",
                    "status": "operational",
                    "actions": list(ACTION_MAP.keys()),
                    "supabase_configured": _sb_configured(),
                })
                return

            if not _sb_configured():
                self._error(503, "Supabase is not configured. Set SUPABASE_URL and SUPABASE_KEY.")
                return

            # Build a body-like dict from query params
            body = {}
            for key, vals in params.items():
                body[key] = vals[0] if vals else ""

            # Coerce types
            if "page" in body:
                try:
                    body["page"] = int(body["page"])
                except (ValueError, TypeError):
                    body["page"] = DEFAULT_PAGE
            if "limit" in body:
                try:
                    body["limit"] = int(body["limit"])
                except (ValueError, TypeError):
                    body["limit"] = DEFAULT_LIMIT
            if "filter_favorite" in body:
                body["filter_favorite"] = body["filter_favorite"].lower() in ("true", "1", "yes")

            # Only allow read actions via GET
            if action not in ("get_looks", "get_look", "get_stats"):
                self._error(405, f"Action '{action}' is not allowed via GET. Use POST instead.")
                return

            handler_fn = ACTION_MAP.get(action)
            if not handler_fn:
                self._error(400, f"Unknown action: '{action}'. Valid: {', '.join(ACTION_MAP.keys())}")
                return

            result, status = handler_fn(body)
            self._respond(status, result)

        except Exception as e:
            print(f"❌ [do_GET] Unhandled error: {e}")
            self._error(500, f"Internal server error: {str(e)}")

    # --- POST ---
    def do_POST(self):
        """
        Handle POST requests. All actions are dispatched via the 'action' field
        in the JSON body.
        """
        try:
            # Check Supabase configuration
            if not _sb_configured():
                self._error(503, "Supabase is not configured. Set SUPABASE_URL and SUPABASE_KEY in Vercel environment variables.")
                return

            # Parse request body
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length <= 0:
                self._error(400, "Empty request body. Please provide valid JSON.")
                return

            # Vercel Hobby plan limit: ~4.5 MB
            MAX_BODY_SIZE = 4.5 * 1024 * 1024
            if content_length > MAX_BODY_SIZE:
                self._error(413, "Payload too large. Maximum size is 4.5 MB.")
                return

            raw_body = self.rfile.read(content_length)
            try:
                body = json.loads(raw_body)
            except json.JSONDecodeError:
                self._error(400, "Invalid JSON in request body.")
                return

            if not isinstance(body, dict):
                self._error(400, "Request body must be a JSON object.")
                return

            # Route to action handler
            action = (body.get("action") or "").strip()
            if not action:
                self._error(400, "Missing 'action' field. Valid actions: " + ", ".join(ACTION_MAP.keys()))
                return

            handler_fn = ACTION_MAP.get(action)
            if not handler_fn:
                self._error(400, f"Unknown action: '{action}'. Valid: {', '.join(ACTION_MAP.keys())}")
                return

            print(f"\n{'━' * 50}")
            print(f"📦 [user_looks] action={action}")
            print(f"{'━' * 50}")

            result, status = handler_fn(body)
            self._respond(status, result)

        except Exception as e:
            print(f"❌ [do_POST] Unhandled error: {e}")
            self._error(500, f"Internal server error: {str(e)}")
