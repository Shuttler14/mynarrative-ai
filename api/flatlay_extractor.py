"""
Flat-Lay Extractor API — Vercel Serverless Function
=====================================================
AI-powered pipeline that converts model / lifestyle product photos into
clean flat-lay (garment-only) images suitable for IDM-VTON virtual try-on.

Pipeline:
  1. Image Classification  (GPT-4o-mini vision)  ~$0.001
  2. Garment Description   (GPT-4o-mini vision)  ~$0.001
  3. Flat-Lay Generation   (FLUX-schnell)         ~$0.003
  4. Caching               (Supabase Storage + DB)

Endpoints:
  POST /api/flatlay_extractor   — extract | classify | batch_extract
  GET  /api/flatlay_extractor   — health check
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import time
import hashlib
import urllib.request
import urllib.error
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import replicate
    REPLICATE_AVAILABLE = True
except ImportError:
    REPLICATE_AVAILABLE = False
    print("⚠️ replicate package not available — flat-lay generation disabled")

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("⚠️ openai package not available — classification/description disabled")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
VERSION = "1.0.0"
FLATLAY_BUCKET = "flatlay-cache"
FLATLAY_TABLE = "flatlay_cache"

# Classifications that don't need further processing — image is already usable
PASSTHROUGH_CLASSIFICATIONS = {"flat_lay", "mannequin", "product_only"}

# Classifications that require the full generate pipeline
GENERATE_CLASSIFICATIONS = {"on_model", "lifestyle", "group"}

VALID_CATEGORIES = {"upper_body", "lower_body", "dresses", "outerwear"}

# Cost estimates (USD)
COST_CLASSIFY = 0.001
COST_DESCRIBE = 0.001
COST_GENERATE = 0.003


# ---------------------------------------------------------------------------
# Supabase helpers (direct HTTP REST API via urllib.request)
# ---------------------------------------------------------------------------

def _sb_headers():
    """Return (url, key, headers_dict) for Supabase REST API calls."""
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_KEY", "").strip() or os.environ.get("SUPABASE_KEY", "").strip()
    return url, key, {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def _image_url_hash(image_url: str) -> str:
    """Produce a stable SHA-256 hex digest (first 16 chars) for cache keying."""
    return hashlib.sha256(image_url.encode("utf-8")).hexdigest()[:16]


def _check_flatlay_cache(image_url=None, product_id=None):
    """Query the flatlay_cache table for an existing cached result.

    Looks up by product_id first (fastest), then falls back to image_url hash.
    Returns the cached row dict if found, or None.
    """
    sb_url, sb_key, headers = _sb_headers()
    if not sb_url or not sb_key:
        print("⚠️ Supabase not configured — skipping cache check")
        return None

    filters = []
    if product_id:
        filters.append(f"product_id=eq.{urllib.parse.quote(str(product_id))}")
    if image_url:
        url_hash = _image_url_hash(image_url)
        filters.append(f"image_url_hash=eq.{url_hash}")

    for filt in filters:
        try:
            req_url = f"{sb_url}/rest/v1/{FLATLAY_TABLE}?{filt}&limit=1"
            req = urllib.request.Request(req_url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=8) as resp:
                rows = json.loads(resp.read().decode())
                if rows and isinstance(rows, list) and len(rows) > 0:
                    print(f"✅ Cache HIT — key: {filt}")
                    return rows[0]
        except Exception as e:
            print(f"⚠️ Cache lookup failed ({filt}): {e}")

    print("🔍 Cache MISS")
    return None


def _save_to_flatlay_cache(image_url, flat_lay_url, classification, category,
                           product_id=None, source_platform=None,
                           garment_description=None):
    """Persist flat-lay result metadata to the flatlay_cache table.

    Fire-and-forget — errors are logged but not propagated.
    """
    sb_url, sb_key, headers = _sb_headers()
    if not sb_url or not sb_key:
        print("⚠️ Supabase not configured — skipping cache save")
        return None

    headers["Prefer"] = "return=representation"
    payload = json.dumps({
        "image_url": image_url,
        "image_url_hash": _image_url_hash(image_url),
        "flat_lay_url": flat_lay_url,
        "classification": classification,
        "category": category,
        "product_id": product_id,
        "source_platform": source_platform,
        "garment_description": garment_description,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            f"{sb_url}/rest/v1/{FLATLAY_TABLE}",
            data=payload,
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            saved = json.loads(resp.read().decode())
            print(f"💾 Cache saved: {saved[0].get('id') if isinstance(saved, list) and saved else 'ok'}")
            return saved
    except Exception as e:
        print(f"⚠️ Cache save failed: {e}")
        return None


def _upload_to_supabase_storage(image_data_bytes, path, content_type="image/png"):
    """Upload an image (raw bytes) to Supabase Storage bucket.

    Downloads the image from a URL first if image_data_bytes is a URL string.
    Returns the public URL on success, None on failure.
    """
    sb_url, sb_key, _ = _sb_headers()
    if not sb_url or not sb_key:
        print("⚠️ Supabase not configured — skipping storage upload")
        return None

    # If we got a URL instead of bytes, download it first
    if isinstance(image_data_bytes, str) and image_data_bytes.startswith("http"):
        try:
            req = urllib.request.Request(image_data_bytes, headers={"User-Agent": "MyNarrative/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                image_data_bytes = resp.read()
        except Exception as e:
            print(f"⚠️ Failed to download image for storage upload: {e}")
            return None

    try:
        upload_url = f"{sb_url}/storage/v1/object/{FLATLAY_BUCKET}/{path}"
        req = urllib.request.Request(
            upload_url,
            data=image_data_bytes,
            headers={
                "apikey": sb_key,
                "Authorization": f"Bearer {sb_key}",
                "Content-Type": content_type,
                "x-upsert": "true",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp.read()  # consume response

        public_url = f"{sb_url}/storage/v1/object/public/{FLATLAY_BUCKET}/{path}"
        print(f"📤 Uploaded to storage: {public_url}")
        return public_url
    except Exception as e:
        print(f"⚠️ Storage upload failed: {e}")
        return None


# ---------------------------------------------------------------------------
# GPT-4o-mini Vision: Image Classification
# ---------------------------------------------------------------------------

CLASSIFY_PROMPT = """You are an expert fashion image classifier for an e-commerce virtual try-on system.

Analyze this product/fashion image and classify it into ONE of these categories:

- flat_lay: Garment laid flat on a surface or hanging, no person/mannequin visible
- mannequin: Garment displayed on a mannequin or dress form
- on_model: Single person wearing the garment (model shot / lookbook)
- lifestyle: Person wearing clothes in a lifestyle/outdoor/editorial context
- product_only: Close-up product shot (just the fabric, detail, or packaged item)
- group: Multiple people or multiple garments in one shot

Also determine:
- garment_visible: Is a clear, identifiable clothing item visible? (true/false)
- confidence: Your confidence in the classification (0.0 to 1.0)

Return ONLY a valid JSON object, no markdown, no explanation:
{"classification": "...", "garment_visible": true, "confidence": 0.95}"""


def _classify_image(image_url):
    """Use GPT-4o-mini vision to classify a fashion product image.

    Returns dict with keys: classification, garment_visible, confidence.
    Cost: ~$0.001 per call.
    """
    if not OPENAI_AVAILABLE:
        print("⚠️ OpenAI not available — defaulting classification to 'on_model'")
        return {"classification": "on_model", "garment_visible": True, "confidence": 0.5}

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("⚠️ OPENAI_API_KEY not set — defaulting classification to 'on_model'")
        return {"classification": "on_model", "garment_visible": True, "confidence": 0.5}

    try:
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise fashion image classifier. Return only valid JSON.",
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": CLASSIFY_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": image_url, "detail": "low"},
                        },
                    ],
                },
            ],
            max_tokens=100,
            temperature=0.1,
        )
        raw = response.choices[0].message.content.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        result = json.loads(raw)
        print(f"🔍 Classification: {result.get('classification')} (confidence: {result.get('confidence')})")
        return result
    except Exception as e:
        print(f"⚠️ Classification failed: {e}")
        return {"classification": "on_model", "garment_visible": True, "confidence": 0.3}


# ---------------------------------------------------------------------------
# GPT-4o-mini Vision: Garment Description
# ---------------------------------------------------------------------------

DESCRIBE_PROMPT = """You are a fashion product copywriter for an e-commerce platform.

Describe the main clothing garment visible in this image in rich detail.
Focus on these attributes:
- Type of garment (e.g., shirt, kurta, dress, jeans, jacket)
- Primary and secondary colors
- Pattern (solid, striped, floral, printed, embroidered, etc.)
- Apparent fabric/material (cotton, silk, denim, chiffon, etc.)
- Style (casual, formal, ethnic, streetwear, party, etc.)
- Fit (slim, regular, oversized, flared, A-line, etc.)
- Notable details (buttons, pockets, collar type, embellishments, etc.)

Return ONLY a single paragraph description (2-3 sentences). No JSON, no bullet points.
Example: "A navy blue slim-fit cotton shirt with a classic spread collar and white button-down front. Features subtle vertical pinstripes, chest pocket, and rolled-up sleeve tabs. Smart casual style suitable for office or evening wear." """


def _describe_garment(image_url):
    """Use GPT-4o-mini vision to generate a rich text description of the garment.

    Only called for on_model / lifestyle images that need flat-lay generation.
    Returns a plain text description string.
    Cost: ~$0.001 per call.
    """
    if not OPENAI_AVAILABLE:
        print("⚠️ OpenAI not available — using generic garment description")
        return "a clothing garment"

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("⚠️ OPENAI_API_KEY not set — using generic garment description")
        return "a clothing garment"

    try:
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a fashion garment descriptor. Describe clothing items "
                        "concisely and accurately for product photography recreation."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": DESCRIBE_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": image_url, "detail": "low"},
                        },
                    ],
                },
            ],
            max_tokens=200,
            temperature=0.3,
        )
        description = response.choices[0].message.content.strip()
        print(f"🏷️ Garment description: {description[:80]}…")
        return description
    except Exception as e:
        print(f"⚠️ Garment description failed: {e}")
        return "a clothing garment"


# ---------------------------------------------------------------------------
# FLUX-schnell: Flat-Lay Generation
# ---------------------------------------------------------------------------

def _generate_flatlay(garment_description, category="upper_body"):
    """Use Replicate FLUX-schnell to generate a clean flat-lay product image.

    Takes the garment description and produces a professional e-commerce
    style flat-lay photograph on a clean white background.
    Returns the generated image URL.
    Cost: ~$0.003 per call.
    """
    if not REPLICATE_AVAILABLE:
        print("⚠️ Replicate not available — cannot generate flat-lay")
        return None

    token = os.environ.get("REPLICATE_API_TOKEN")
    if not token:
        print("⚠️ REPLICATE_API_TOKEN not set — cannot generate flat-lay")
        return None

    # Build the generation prompt
    prompt = (
        f"Professional product photography flat lay of {garment_description}. "
        "Clean white background, no wrinkles, centered, soft studio lighting, "
        "fashion e-commerce style, top-down view. "
        "No person, no mannequin, just the clothing item laid flat."
    )

    print(f"🎨 Generating flat-lay with FLUX-schnell…")
    print(f"   Prompt: {prompt[:100]}…")

    try:
        client = replicate.Client(api_token=token)
        output = client.run(
            "black-forest-labs/flux-schnell",
            input={
                "prompt": prompt,
                "aspect_ratio": "3:4",
                "num_inference_steps": 4,
            },
        )
        # FLUX returns a list of FileOutput objects
        if isinstance(output, list) and len(output) > 0:
            result_url = str(output[0])
        else:
            result_url = str(output)
        print(f"✅ Flat-lay generated: {result_url[:80]}…")
        return result_url
    except Exception as e:
        print(f"❌ Flat-lay generation failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Core pipeline: extract flat-lay from any product image
# ---------------------------------------------------------------------------

def _run_extract_pipeline(image_url, category="upper_body", product_id=None,
                          source_platform=None):
    """Full extraction pipeline: classify → describe → generate → cache.

    Returns a result dict with all metadata about the extraction.
    """
    start_time = time.time()
    steps = []
    cost = 0.0

    # ------------------------------------------------------------------
    # Step 0: Check cache FIRST (avoid redundant API calls)
    # ------------------------------------------------------------------
    cached = _check_flatlay_cache(image_url=image_url, product_id=product_id)
    if cached:
        elapsed_ms = int((time.time() - start_time) * 1000)
        return {
            "success": True,
            "original_url": image_url,
            "classification": cached.get("classification", "unknown"),
            "flat_lay_url": cached.get("flat_lay_url"),
            "garment_description": cached.get("garment_description"),
            "was_cached": True,
            "processing_steps": ["cache_hit"],
            "processing_time_ms": elapsed_ms,
            "cost_estimate_usd": 0.0,
        }

    # ------------------------------------------------------------------
    # Step 1: Classify the image (~$0.001)
    # ------------------------------------------------------------------
    classification_result = _classify_image(image_url)
    classification = classification_result.get("classification", "on_model")
    garment_visible = classification_result.get("garment_visible", True)
    confidence = classification_result.get("confidence", 0.5)
    steps.append("classify")
    cost += COST_CLASSIFY

    # If garment is not visible, return early
    if not garment_visible:
        elapsed_ms = int((time.time() - start_time) * 1000)
        return {
            "success": False,
            "original_url": image_url,
            "classification": classification,
            "flat_lay_url": None,
            "garment_description": None,
            "was_cached": False,
            "processing_steps": steps,
            "processing_time_ms": elapsed_ms,
            "cost_estimate_usd": cost,
            "error": "No garment visible in image",
        }

    # ------------------------------------------------------------------
    # Step 1b: If already flat-lay/mannequin/product_only → passthrough
    # ------------------------------------------------------------------
    if classification in PASSTHROUGH_CLASSIFICATIONS:
        print(f"🖼️ Image is already '{classification}' — using original image directly")
        flat_lay_url = image_url
        garment_description = None

        # Cache the passthrough result too
        _save_to_flatlay_cache(
            image_url=image_url,
            flat_lay_url=flat_lay_url,
            classification=classification,
            category=category,
            product_id=product_id,
            source_platform=source_platform,
            garment_description=None,
        )
        steps.append("passthrough")

        elapsed_ms = int((time.time() - start_time) * 1000)
        return {
            "success": True,
            "original_url": image_url,
            "classification": classification,
            "classification_confidence": confidence,
            "flat_lay_url": flat_lay_url,
            "garment_description": garment_description,
            "was_cached": False,
            "processing_steps": steps,
            "processing_time_ms": elapsed_ms,
            "cost_estimate_usd": cost,
        }

    # ------------------------------------------------------------------
    # Step 2: Describe the garment (~$0.001)
    # Only for on_model / lifestyle / group images
    # ------------------------------------------------------------------
    print(f"🖼️ Image is '{classification}' — starting describe + generate pipeline")
    garment_description = _describe_garment(image_url)
    steps.append("describe")
    cost += COST_DESCRIBE

    # ------------------------------------------------------------------
    # Step 3: Generate flat-lay image (~$0.003)
    # ------------------------------------------------------------------
    flat_lay_url = _generate_flatlay(garment_description, category)
    steps.append("generate")
    cost += COST_GENERATE

    if not flat_lay_url:
        elapsed_ms = int((time.time() - start_time) * 1000)
        return {
            "success": False,
            "original_url": image_url,
            "classification": classification,
            "classification_confidence": confidence,
            "flat_lay_url": None,
            "garment_description": garment_description,
            "was_cached": False,
            "processing_steps": steps,
            "processing_time_ms": elapsed_ms,
            "cost_estimate_usd": cost,
            "error": "Flat-lay generation failed",
        }

    # ------------------------------------------------------------------
    # Step 4: Cache result (Storage + DB)
    # ------------------------------------------------------------------
    # Build storage path: {source_platform}/{product_id_or_hash}.png
    file_key = product_id if product_id else _image_url_hash(image_url)
    platform = source_platform or "unknown"
    storage_path = f"{platform}/{file_key}.png"

    # Upload generated flat-lay to Supabase Storage
    stored_url = _upload_to_supabase_storage(flat_lay_url, storage_path)
    final_flat_lay_url = stored_url if stored_url else flat_lay_url

    # Save metadata to DB
    _save_to_flatlay_cache(
        image_url=image_url,
        flat_lay_url=final_flat_lay_url,
        classification=classification,
        category=category,
        product_id=product_id,
        source_platform=source_platform,
        garment_description=garment_description,
    )
    steps.append("cache")

    elapsed_ms = int((time.time() - start_time) * 1000)
    return {
        "success": True,
        "original_url": image_url,
        "classification": classification,
        "classification_confidence": confidence,
        "flat_lay_url": final_flat_lay_url,
        "garment_description": garment_description,
        "was_cached": False,
        "processing_steps": steps,
        "processing_time_ms": elapsed_ms,
        "cost_estimate_usd": round(cost, 4),
    }


# ---------------------------------------------------------------------------
# Batch extraction with threading
# ---------------------------------------------------------------------------

def _run_batch_extract(images, max_concurrent=3):
    """Process multiple images in parallel using ThreadPoolExecutor.

    Args:
        images: list of dicts with image_url, category, product_id, source_platform
        max_concurrent: max parallel threads (default 3, capped at 5)

    Returns:
        dict with results list and summary stats.
    """
    max_concurrent = min(max(1, max_concurrent), 5)  # Clamp 1–5
    start_time = time.time()

    results = []
    total_cost = 0.0
    success_count = 0
    cached_count = 0

    print(f"📦 Batch extract: {len(images)} images, max_concurrent={max_concurrent}")

    def _process_single(img_spec):
        return _run_extract_pipeline(
            image_url=img_spec.get("image_url", ""),
            category=img_spec.get("category", "upper_body"),
            product_id=img_spec.get("product_id"),
            source_platform=img_spec.get("source_platform"),
        )

    with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
        future_to_idx = {
            executor.submit(_process_single, img): idx
            for idx, img in enumerate(images)
        }
        # Pre-fill results list with None placeholders
        results = [None] * len(images)

        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                result = future.result()
                results[idx] = result
                if result.get("success"):
                    success_count += 1
                if result.get("was_cached"):
                    cached_count += 1
                total_cost += result.get("cost_estimate_usd", 0.0)
            except Exception as e:
                print(f"❌ Batch item #{idx} failed: {e}")
                results[idx] = {
                    "success": False,
                    "error": str(e),
                    "original_url": images[idx].get("image_url", ""),
                }

    elapsed_ms = int((time.time() - start_time) * 1000)

    return {
        "success": True,
        "total_images": len(images),
        "successful": success_count,
        "cached": cached_count,
        "failed": len(images) - success_count,
        "total_cost_estimate_usd": round(total_cost, 4),
        "total_processing_time_ms": elapsed_ms,
        "results": results,
    }


# ---------------------------------------------------------------------------
# Vercel Serverless Handler
# ---------------------------------------------------------------------------

class handler(BaseHTTPRequestHandler):
    """Flat-Lay Extractor API handler.

    POST actions:
        extract        — Full pipeline: classify → describe → generate → cache
        classify       — Classification only (~$0.001)
        batch_extract  — Process multiple images in parallel

    GET:
        Health check returning service status and capabilities.
    """

    # -- Response helpers --------------------------------------------------

    def _error(self, status, message):
        """Send a JSON error response with CORS headers."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({
            "success": False,
            "error": message,
        }).encode("utf-8"))

    def _success(self, data):
        """Send a JSON success response with CORS headers."""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    # -- CORS preflight ----------------------------------------------------

    def do_OPTIONS(self):
        """Handle CORS preflight request."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    # -- GET: Health check -------------------------------------------------

    def do_GET(self):
        """Health-check endpoint returning service status and capabilities."""
        self._success({
            "service": "flatlay_extractor",
            "version": VERSION,
            "replicate_available": REPLICATE_AVAILABLE,
            "openai_available": OPENAI_AVAILABLE,
            "actions": ["extract", "classify", "batch_extract"],
            "supported_categories": list(VALID_CATEGORIES),
            "supported_platforms": ["myntra", "flipkart", "ajio", "amazon"],
            "cost_estimates_usd": {
                "classify_only": COST_CLASSIFY,
                "full_extract": COST_CLASSIFY + COST_DESCRIBE + COST_GENERATE,
            },
        })

    # -- POST: Main handler ------------------------------------------------

    def do_POST(self):
        """Route POST requests to the appropriate action handler."""
        try:
            # Parse request body
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                self._error(400, "Empty request body")
                return
            body = json.loads(self.rfile.read(content_length))

            action = body.get("action", "extract")

            # ----- ACTION: classify -----
            if action == "classify":
                self._handle_classify(body)

            # ----- ACTION: extract -----
            elif action == "extract":
                self._handle_extract(body)

            # ----- ACTION: batch_extract -----
            elif action == "batch_extract":
                self._handle_batch_extract(body)

            else:
                self._error(400, f"Unknown action '{action}'. Supported: extract, classify, batch_extract")

        except json.JSONDecodeError as e:
            self._error(400, f"Invalid JSON in request body: {e}")
        except Exception as e:
            print(f"❌ Unhandled error: {e}")
            self._error(500, f"Internal server error: {str(e)}")

    # -- Action: classify --------------------------------------------------

    def _handle_classify(self, body):
        """Classify an image without extraction (~$0.001).

        Input:  {"action": "classify", "image_url": "..."}
        Output: {"success": true, "classification": "on_model", ...}
        """
        image_url = body.get("image_url", "").strip()
        if not image_url:
            self._error(400, "Missing 'image_url': provide a public URL of the product image")
            return

        start_time = time.time()
        result = _classify_image(image_url)
        elapsed_ms = int((time.time() - start_time) * 1000)

        self._success({
            "success": True,
            "image_url": image_url,
            "classification": result.get("classification"),
            "garment_visible": result.get("garment_visible"),
            "confidence": result.get("confidence"),
            "processing_time_ms": elapsed_ms,
            "cost_estimate_usd": COST_CLASSIFY,
        })

    # -- Action: extract ---------------------------------------------------

    def _handle_extract(self, body):
        """Full extraction pipeline: classify → describe → generate → cache.

        Input:
            {
                "action": "extract",
                "image_url": "URL of the product image",
                "category": "upper_body|lower_body|dresses|outerwear",
                "product_id": "optional",
                "source_platform": "optional — myntra|flipkart|ajio|amazon"
            }
        """
        image_url = body.get("image_url", "").strip()
        if not image_url:
            self._error(400, "Missing 'image_url': provide a public URL of the product image")
            return

        category = body.get("category", "upper_body")
        if category not in VALID_CATEGORIES:
            print(f"⚠️ Unknown category '{category}' — defaulting to 'upper_body'")
            category = "upper_body"

        product_id = body.get("product_id")
        source_platform = body.get("source_platform")

        # Validate dependencies
        if not OPENAI_AVAILABLE:
            self._error(500, "Server config error: openai package not installed")
            return
        if not os.environ.get("OPENAI_API_KEY"):
            self._error(500, "OPENAI_API_KEY is not set in environment variables")
            return

        print(f"🖼️ Extract request | category={category} | product_id={product_id} | platform={source_platform}")

        result = _run_extract_pipeline(
            image_url=image_url,
            category=category,
            product_id=product_id,
            source_platform=source_platform,
        )

        if result.get("success"):
            self._success(result)
        else:
            # Still return 200 with success=false so the client gets details
            self._success(result)

    # -- Action: batch_extract ---------------------------------------------

    def _handle_batch_extract(self, body):
        """Process multiple images in parallel using threading.

        Input:
            {
                "action": "batch_extract",
                "images": [
                    {"image_url": "...", "category": "...", "product_id": "..."},
                    ...
                ],
                "max_concurrent": 3
            }
        """
        images = body.get("images", [])
        if not images or not isinstance(images, list):
            self._error(400, "Missing or invalid 'images': provide a list of image objects")
            return

        if len(images) > 20:
            self._error(400, f"Too many images ({len(images)}). Maximum is 20 per batch request")
            return

        # Validate each image has an image_url
        for idx, img in enumerate(images):
            if not img.get("image_url", "").strip():
                self._error(400, f"Image #{idx + 1} is missing 'image_url'")
                return

        max_concurrent = body.get("max_concurrent", 3)
        try:
            max_concurrent = int(max_concurrent)
        except (TypeError, ValueError):
            max_concurrent = 3

        # Validate dependencies
        if not OPENAI_AVAILABLE:
            self._error(500, "Server config error: openai package not installed")
            return
        if not os.environ.get("OPENAI_API_KEY"):
            self._error(500, "OPENAI_API_KEY is not set in environment variables")
            return

        print(f"📦 Batch request: {len(images)} images, max_concurrent={max_concurrent}")

        result = _run_batch_extract(images, max_concurrent)
        self._success(result)

    # -- Suppress default logging ------------------------------------------

    def log_message(self, format, *args):
        """Suppress default BaseHTTPRequestHandler logging."""
        pass
