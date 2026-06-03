"""
================================================================================
  MY NARRATIVE AI — MULTI-GARMENT VIRTUAL TRY-ON COMPOSITOR
  api/vton_compositor.py
================================================================================

  PURPOSE:
  Vercel Serverless Function that orchestrates multi-garment virtual try-on
  by chaining sequential IDM-VTON predictions on Replicate, then optionally
  face-swapping the user's face onto the final composite.

  ACTIONS:
    compose_outfit  — Full multi-garment pipeline with optional face swap
    single_tryon    — Lightweight single-garment try-on (no face swap)
    health          — Service health check

  COST GUIDE (Replicate):
    Preview (20 steps):  ~₹0.80–₹1.60  per garment
    Final   (40 steps):  ~₹2.50–₹4.00  per garment
    Face Swap:           ~₹0.40         per call

  REQUIRED ENVIRONMENT VARIABLES (set in Vercel Dashboard):
  ──────────────────────────────────────────────────────────
  REPLICATE_API_TOKEN     → Replicate API token
  SUPABASE_URL            → Supabase project URL    (optional, for caching)
  SUPABASE_KEY            → Supabase anon/service key (optional, for caching)

================================================================================
"""

from http.server import BaseHTTPRequestHandler
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

try:
    import replicate
    REPLICATE_AVAILABLE = True
except ImportError:
    REPLICATE_AVAILABLE = False


# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

IDM_VTON_MODEL = "cuuupid/idm-vton"
IDM_VTON_FALLBACK_VERSION = "c871bb9b046607b680449ecbae55fd8c6d945e0a1948644bf2361b3d021d3ff4"
FACESWAP_MODEL = "lucataco/faceswap:9a4298548422074c3f57258c5d544497314ae4112df80d116f0d2109bd068e9c"

QUALITY_STEPS = {
    "preview": 20,
    "final": 40,
}

# Garment processing order — dresses first (full body), then upper, then lower
CATEGORY_ORDER = {
    "dresses": 0,
    "upper_body": 1,
    "lower_body": 2,
}

VALID_CATEGORIES = {"upper_body", "lower_body", "dresses"}

# Retry config for transient errors
MAX_RETRIES = 1
RETRY_DELAY_SECONDS = 2
RETRYABLE_STATUS_CODES = {500, 503}


# ---------------------------------------------------------------------------
# SUPABASE HELPERS (direct HTTP REST API — no SDK)
# ---------------------------------------------------------------------------

def _sb_config():
    """Return (url, key) tuple for Supabase. Empty strings if not configured."""
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_KEY", "").strip()
    return url, key


def _sb_headers(key: str) -> dict:
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def sb_configured() -> bool:
    url, key = _sb_config()
    return bool(url and key)


def _sb_request(method: str, path: str, payload=None, timeout: int = 15):
    """Generic Supabase REST API request. Returns (data, error_string)."""
    url, key = _sb_config()
    if not url or not key:
        return None, "supabase_not_configured"
    full_url = f"{url.rstrip('/')}{path}"
    headers = _sb_headers(key)
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(full_url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
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


# ---------------------------------------------------------------------------
# CACHE HELPERS
# ---------------------------------------------------------------------------

def _build_cache_key(body_image: str, garments: list, quality: str) -> str:
    """
    Build a deterministic SHA-256 cache key from:
      - body_image URL (or first 100 chars of base64)
      - sorted garment flat_lay_urls
      - quality level
    """
    # Normalize body image identifier
    if body_image.startswith("http"):
        body_id = body_image
    else:
        body_id = body_image[:100]

    # Sort garment URLs for determinism
    garment_urls = sorted(g.get("flat_lay_url", "") for g in garments)
    raw = f"{body_id}|{'|'.join(garment_urls)}|{quality}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def cache_lookup(cache_key: str):
    """
    Check vton_cache table for a matching cache_key.
    Returns (cached_url, None) or (None, error).
    """
    if not sb_configured():
        return None, "supabase_not_configured"

    path = f"/rest/v1/vton_cache?cache_key=eq.{urllib.parse.quote(cache_key)}&select=result_url&limit=1"
    data, err = _sb_request("GET", path)
    if err:
        print(f"⚠️ [cache_lookup] Error: {err}")
        return None, err
    if isinstance(data, list) and len(data) > 0:
        result_url = data[0].get("result_url", "")
        if result_url:
            print(f"✅ [cache_lookup] Cache HIT for {cache_key[:16]}...")
            return result_url, None
    return None, None


def cache_store(cache_key: str, result_url: str, metadata: dict):
    """
    Upload result image URL and metadata to vton_cache table.
    Also uploads to Supabase Storage vton-results bucket.
    """
    if not sb_configured():
        return

    # 1. Try uploading the image to Supabase Storage
    storage_url = _upload_to_storage(result_url, cache_key)
    final_url = storage_url if storage_url else result_url

    # 2. Insert cache record
    row = {
        "cache_key": cache_key,
        "result_url": final_url,
        "original_replicate_url": result_url,
        "quality": metadata.get("quality", "preview"),
        "garments_applied": metadata.get("garments_applied", 0),
        "face_swapped": metadata.get("face_swapped", False),
        "processing_time_ms": metadata.get("processing_time_ms", 0),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    _, _, headers_dict = _sb_config()[0], _sb_config()[1], _sb_headers(_sb_config()[1])
    url_base = _sb_config()[0].rstrip("/")
    key = _sb_config()[1]
    headers = _sb_headers(key)
    headers["Prefer"] = "return=representation"

    try:
        req = urllib.request.Request(
            f"{url_base}/rest/v1/vton_cache",
            data=json.dumps(row).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()
        print(f"💾 [cache_store] Cached result for {cache_key[:16]}...")
    except Exception as e:
        print(f"⚠️ [cache_store] Failed to cache: {e}")


def _upload_to_storage(image_url: str, cache_key: str) -> str:
    """
    Download image from Replicate URL and upload to Supabase Storage
    bucket 'vton-results'. Returns public URL or empty string on failure.
    """
    if not sb_configured() or not image_url:
        return ""

    try:
        # Download image from Replicate
        dl_req = urllib.request.Request(
            image_url,
            headers={"User-Agent": "MN-VTON-Compositor/1.0"},
            method="GET",
        )
        with urllib.request.urlopen(dl_req, timeout=30) as resp:
            image_bytes = resp.read()
            content_type = resp.headers.get("Content-Type", "image/png")

        # Determine extension
        ext = "png"
        if "jpeg" in content_type or "jpg" in content_type:
            ext = "jpg"
        elif "webp" in content_type:
            ext = "webp"

        filename = f"{cache_key[:32]}.{ext}"
        sb_url, sb_key = _sb_config()
        upload_url = f"{sb_url.rstrip('/')}/storage/v1/object/vton-results/{filename}"

        headers = {
            "apikey": sb_key,
            "Authorization": f"Bearer {sb_key}",
            "Content-Type": content_type,
            "x-upsert": "true",
        }
        up_req = urllib.request.Request(upload_url, data=image_bytes, headers=headers, method="POST")
        with urllib.request.urlopen(up_req, timeout=30) as resp:
            resp.read()

        public_url = f"{sb_url.rstrip('/')}/storage/v1/object/public/vton-results/{filename}"
        print(f"📤 [storage] Uploaded to {filename}")
        return public_url

    except Exception as e:
        print(f"⚠️ [storage] Upload failed: {e}")
        return ""


# ---------------------------------------------------------------------------
# REPLICATE HELPERS
# ---------------------------------------------------------------------------

def _get_replicate_client():
    """Initialize and return a Replicate client. Returns (client, error)."""
    if not REPLICATE_AVAILABLE:
        return None, "replicate package not installed. Run: pip install replicate"

    token = os.environ.get("REPLICATE_API_TOKEN", "").strip()
    if not token:
        return None, (
            "REPLICATE_API_TOKEN is not set in Vercel environment variables. "
            "Please add it at: Vercel Dashboard → Your Project → Settings → "
            "Environment Variables → Add REPLICATE_API_TOKEN"
        )

    return replicate.Client(api_token=token), None


def _get_idm_vton_version(client) -> str:
    """Auto-fetch latest IDM-VTON version with fallback to hardcoded hash."""
    try:
        model = client.models.get(IDM_VTON_MODEL)
        latest = model.latest_version
        version_id = latest.id
        print(f"✅ [idm-vton] Using version: {version_id}")
        return version_id
    except Exception as e:
        print(f"⚠️ [idm-vton] Auto-fetch failed, using fallback. Error: {e}")
        return IDM_VTON_FALLBACK_VERSION


def _run_vton_with_retry(client, version_id: str, inputs: dict) -> str:
    """
    Run IDM-VTON prediction with retry logic for transient errors.
    Returns the output image URL string.
    Raises on permanent failure.
    """
    last_error = None
    for attempt in range(1 + MAX_RETRIES):
        try:
            output = client.run(
                f"{IDM_VTON_MODEL}:{version_id}",
                input=inputs,
            )
            # IDM-VTON returns a FileOutput object
            return str(output) if hasattr(output, '__str__') else output
        except Exception as e:
            last_error = e
            error_msg = str(e)

            # Check if retryable (transient server errors)
            is_retryable = any(str(code) in error_msg for code in RETRYABLE_STATUS_CODES)

            if is_retryable and attempt < MAX_RETRIES:
                print(f"🔄 [idm-vton] Retry {attempt + 1}/{MAX_RETRIES} after {RETRY_DELAY_SECONDS}s — {error_msg[:120]}")
                time.sleep(RETRY_DELAY_SECONDS)
                continue

            # Non-retryable or exhausted retries
            raise last_error


def _run_faceswap(client, target_image: str, swap_image: str) -> str:
    """
    Run face swap using lucataco/faceswap.
    Returns the output URL or empty string on failure.
    """
    try:
        print("🔄 [faceswap] Running face personalization...")
        output = client.run(
            FACESWAP_MODEL,
            input={
                "target_image": target_image,
                "swap_image": swap_image,
            },
        )
        result = str(output)
        print(f"✅ [faceswap] Face swap complete")
        return result
    except Exception as e:
        print(f"⚠️ [faceswap] Face swap failed (returning VTON result without face): {e}")
        return ""


def _classify_replicate_error(error_msg: str) -> str:
    """Classify a Replicate error into a user-friendly message."""
    lowered = error_msg.lower()
    if "402" in error_msg or "payment" in lowered or "credit" in lowered:
        return "💳 Replicate credits exhausted. Add credits at replicate.com/account/billing"
    elif "401" in error_msg or "unauthorized" in lowered or "token" in lowered:
        return "🔑 Invalid REPLICATE_API_TOKEN. Please check your Vercel environment variables."
    elif "422" in error_msg or "version" in lowered:
        return "⚠️ AI model version error. Please contact support."
    return error_msg


# ---------------------------------------------------------------------------
# COMPOSE OUTFIT — Full multi-garment pipeline
# ---------------------------------------------------------------------------

def _compose_outfit(client, body: dict) -> dict:
    """
    Full multi-garment virtual try-on pipeline:
      1. Validate inputs
      2. Check cache
      3. Sort garments by processing order
      4. Sequential IDM-VTON per garment
      5. Face swap (optional)
      6. Cache result
      7. Return composite
    """
    t_start = time.time()

    # ── Validate inputs ──────────────────────────────────────────────
    user_id = body.get("user_id", "anonymous")
    face_image = body.get("face_image", "")
    body_image = body.get("body_image", "")
    garments = body.get("garments", [])
    quality = body.get("quality", "preview")

    if not face_image:
        return {"success": False, "error": "face_image is required (base64 or URL)"}
    if not body_image:
        return {"success": False, "error": "body_image is required (base64 or URL)"}
    if not garments or not isinstance(garments, list):
        return {"success": False, "error": "At least 1 garment is required in the garments array"}
    if quality not in QUALITY_STEPS:
        quality = "preview"

    steps = QUALITY_STEPS[quality]

    # Validate each garment
    for i, g in enumerate(garments):
        if not isinstance(g, dict):
            return {"success": False, "error": f"garments[{i}] must be a JSON object"}
        if not g.get("flat_lay_url"):
            return {"success": False, "error": f"garments[{i}].flat_lay_url is required"}
        cat = g.get("category", "upper_body")
        if cat not in VALID_CATEGORIES:
            return {"success": False, "error": f"garments[{i}].category must be one of: {', '.join(VALID_CATEGORIES)}"}

    print(f"👗 [compose_outfit] user={user_id} garments={len(garments)} quality={quality} steps={steps}")

    # ── Check cache ──────────────────────────────────────────────────
    cache_key = _build_cache_key(body_image, garments, quality)

    if sb_configured():
        cached_url, cache_err = cache_lookup(cache_key)
        if cached_url:
            return {
                "success": True,
                "result_image": cached_url,
                "face_swapped": True,
                "garments_applied": len(garments),
                "garments_failed": 0,
                "quality": quality,
                "processing_time_ms": int((time.time() - t_start) * 1000),
                "per_garment": [
                    {"category": g.get("category", "upper_body"), "status": "cached", "time_ms": 0}
                    for g in garments
                ],
                "cached": True,
                "cache_key": cache_key,
            }

    # ── Sort garments by processing order ────────────────────────────
    sorted_garments = sorted(
        garments,
        key=lambda g: CATEGORY_ORDER.get(g.get("category", "upper_body"), 99),
    )

    # ── Auto-fetch IDM-VTON version ──────────────────────────────────
    version_id = _get_idm_vton_version(client)

    # ── Sequential IDM-VTON per garment ──────────────────────────────
    current_image = body_image
    per_garment = []
    garments_applied = 0
    garments_failed = 0

    for idx, garment in enumerate(sorted_garments):
        g_start = time.time()
        category = garment.get("category", "upper_body")
        flat_lay_url = garment["flat_lay_url"]
        description = garment.get("description", "clothing item")
        product_id = garment.get("product_id", "")

        print(f"  👕 [{idx + 1}/{len(sorted_garments)}] Applying {category} — {description[:50]}")

        vton_inputs = {
            "human_img": current_image,
            "garm_img": flat_lay_url,
            "garment_des": description,
            "category": category,
            "crop": False,
            "seed": 42,
            "steps": steps,
            "force_dc": False,
            "mask_only": False,
        }

        try:
            result_url = _run_vton_with_retry(client, version_id, vton_inputs)
            if not result_url:
                raise ValueError("IDM-VTON returned empty output")

            current_image = result_url
            garments_applied += 1
            g_time = int((time.time() - g_start) * 1000)
            per_garment.append({
                "category": category,
                "product_id": product_id,
                "status": "success",
                "time_ms": g_time,
            })
            print(f"  ✅ [{idx + 1}] {category} applied in {g_time}ms")

        except Exception as e:
            garments_failed += 1
            g_time = int((time.time() - g_start) * 1000)
            error_msg = _classify_replicate_error(str(e))

            per_garment.append({
                "category": category,
                "product_id": product_id,
                "status": "failed",
                "error": error_msg,
                "time_ms": g_time,
            })
            print(f"  ❌ [{idx + 1}] {category} FAILED in {g_time}ms — {error_msg[:100]}")

            # If Replicate credits exhausted, abort immediately
            if "402" in str(e) or "credit" in str(e).lower():
                return {
                    "success": False,
                    "error": error_msg,
                    "garments_applied": garments_applied,
                    "garments_failed": garments_failed,
                    "per_garment": per_garment,
                    "processing_time_ms": int((time.time() - t_start) * 1000),
                }

            # Otherwise skip this garment and continue
            continue

    # If no garments were applied successfully, return error
    if garments_applied == 0:
        return {
            "success": False,
            "error": "All garment try-ons failed. Please check your inputs and try again.",
            "garments_applied": 0,
            "garments_failed": garments_failed,
            "per_garment": per_garment,
            "processing_time_ms": int((time.time() - t_start) * 1000),
        }

    # ── Face Swap ────────────────────────────────────────────────────
    face_swapped = False
    face_result = _run_faceswap(client, target_image=current_image, swap_image=face_image)
    if face_result:
        current_image = face_result
        face_swapped = True

    total_time = int((time.time() - t_start) * 1000)
    print(f"🎉 [compose_outfit] Complete! {garments_applied}/{len(garments)} garments, "
          f"face_swap={face_swapped}, {total_time}ms total")

    # ── Cache result ─────────────────────────────────────────────────
    if sb_configured():
        try:
            cache_store(cache_key, current_image, {
                "quality": quality,
                "garments_applied": garments_applied,
                "face_swapped": face_swapped,
                "processing_time_ms": total_time,
            })
        except Exception as e:
            print(f"⚠️ [cache_store] Non-critical cache failure: {e}")

    return {
        "success": True,
        "result_image": current_image,
        "face_swapped": face_swapped,
        "garments_applied": garments_applied,
        "garments_failed": garments_failed,
        "quality": quality,
        "processing_time_ms": total_time,
        "per_garment": per_garment,
        "cached": False,
        "cache_key": cache_key,
    }


# ---------------------------------------------------------------------------
# SINGLE TRY-ON — Lightweight single-garment (no face swap)
# ---------------------------------------------------------------------------

def _single_tryon(client, body: dict) -> dict:
    """
    Quick single-garment virtual try-on. No face swap, no caching.
    Fast and cheap — ideal for product page previews.
    """
    t_start = time.time()

    body_image = body.get("body_image", "")
    garment_image = body.get("garment_image", "")
    category = body.get("category", "upper_body")
    description = body.get("description", "clothing item")
    quality = body.get("quality", "preview")

    if not body_image:
        return {"success": False, "error": "body_image is required (base64 or URL)"}
    if not garment_image:
        return {"success": False, "error": "garment_image is required (URL)"}
    if category not in VALID_CATEGORIES:
        category = "upper_body"
    if quality not in QUALITY_STEPS:
        quality = "preview"

    steps = QUALITY_STEPS[quality]
    print(f"👕 [single_tryon] category={category} quality={quality} steps={steps}")

    # Auto-fetch IDM-VTON version
    version_id = _get_idm_vton_version(client)

    vton_inputs = {
        "human_img": body_image,
        "garm_img": garment_image,
        "garment_des": description,
        "category": category,
        "crop": False,
        "seed": 42,
        "steps": steps,
        "force_dc": False,
        "mask_only": False,
    }

    try:
        result_url = _run_vton_with_retry(client, version_id, vton_inputs)
        if not result_url:
            raise ValueError("IDM-VTON returned empty output")
    except Exception as e:
        error_msg = _classify_replicate_error(str(e))
        return {"success": False, "error": error_msg}

    total_time = int((time.time() - t_start) * 1000)
    print(f"✅ [single_tryon] Complete in {total_time}ms")

    return {
        "success": True,
        "result_image": result_url,
        "category": category,
        "quality": quality,
        "processing_time_ms": total_time,
    }


# ---------------------------------------------------------------------------
# HEALTH CHECK
# ---------------------------------------------------------------------------

def _health_check() -> dict:
    """Service health check — validate configuration and model availability."""
    checks = {
        "replicate_package": REPLICATE_AVAILABLE,
        "replicate_token": bool(os.environ.get("REPLICATE_API_TOKEN", "").strip()),
        "supabase_configured": sb_configured(),
    }

    # Test Replicate model access if token available
    model_status = "unknown"
    if checks["replicate_package"] and checks["replicate_token"]:
        try:
            client = replicate.Client(api_token=os.environ.get("REPLICATE_API_TOKEN", "").strip())
            model = client.models.get(IDM_VTON_MODEL)
            version_id = model.latest_version.id
            model_status = f"available (v:{version_id[:12]}...)"
        except Exception as e:
            model_status = f"error: {str(e)[:80]}"

    checks["idm_vton_model"] = model_status

    all_ok = (
        checks["replicate_package"]
        and checks["replicate_token"]
        and model_status.startswith("available")
    )

    return {
        "success": True,
        "status": "healthy" if all_ok else "degraded",
        "service": "vton_compositor",
        "version": "1.0.0",
        "checks": checks,
        "supported_actions": ["compose_outfit", "single_tryon", "health"],
        "quality_modes": {
            "preview": {"steps": 20, "cost_inr": "₹0.80–₹1.60/garment"},
            "final": {"steps": 40, "cost_inr": "₹2.50–₹4.00/garment"},
        },
    }


# ---------------------------------------------------------------------------
# VERCEL SERVERLESS HANDLER
# ---------------------------------------------------------------------------

class handler(BaseHTTPRequestHandler):

    def _error(self, status, message):
        """Send a JSON error response with CORS headers."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({
            "success": False,
            "error": message,
        }).encode('utf-8'))

    def _success(self, data):
        """Send a JSON success response with CORS headers."""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def do_OPTIONS(self):
        """Handle CORS preflight request."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Max-Age', '86400')
        self.end_headers()

    def do_GET(self):
        """Handle GET requests — health check only."""
        try:
            result = _health_check()
            self._success(result)
        except Exception as e:
            self._error(500, f"Health check failed: {str(e)}")

    def do_POST(self):
        """
        Handle POST requests — route by action field:
          compose_outfit  — Multi-garment VTON pipeline
          single_tryon    — Single garment quick try-on
          health          — Service health check (also available via GET)
        """
        try:
            # ── Initialize Replicate client ──────────────────────────
            client, client_err = _get_replicate_client()
            if client_err:
                self._error(500, f"Server Config Error: {client_err}")
                return

            # ── Parse request body ───────────────────────────────────
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._error(400, "Empty request body")
                return

            body = json.loads(self.rfile.read(content_length).decode('utf-8'))
            action = body.get("action", "").strip().lower()

            # ── Route by action ──────────────────────────────────────
            if action == "compose_outfit":
                print(f"🎨 [vton_compositor] Action: compose_outfit")
                result = _compose_outfit(client, body)

            elif action == "single_tryon":
                print(f"👕 [vton_compositor] Action: single_tryon")
                result = _single_tryon(client, body)

            elif action == "health":
                print(f"🏥 [vton_compositor] Action: health")
                result = _health_check()

            else:
                self._error(400, (
                    f"Unknown action: '{action}'. "
                    "Supported actions: compose_outfit, single_tryon, health"
                ))
                return

            # ── Send response ────────────────────────────────────────
            if result.get("success"):
                self._success(result)
            else:
                status = 402 if "credit" in result.get("error", "").lower() else 500
                self._error(status, result.get("error", "Unknown error"))

        except json.JSONDecodeError as e:
            self._error(400, f"Invalid JSON in request body: {e}")
        except Exception as e:
            error_msg = _classify_replicate_error(str(e))
            print(f"💥 [vton_compositor] Unhandled error: {error_msg}")
            self._error(500, error_msg)

    def log_message(self, format, *args):
        """Suppress default BaseHTTPRequestHandler logging."""
        pass
