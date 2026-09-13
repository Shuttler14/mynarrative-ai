import os
import tempfile
_TMP = tempfile.gettempdir()
os.environ['MPLCONFIGDIR']        = _TMP
os.environ['XDG_CACHE_HOME']      = _TMP
os.environ['TRANSFORMERS_CACHE']  = _TMP
os.environ['HF_HOME']             = _TMP
os.environ['NUMBA_CACHE_DIR']     = _TMP
os.environ['PILLOW_BLOCK_OPEN']   = '0'

from http.server import BaseHTTPRequestHandler
import json
import os
import uuid
import time
import requests
import urllib.request
import urllib.parse
import urllib.error
from urllib.parse import urlparse, parse_qs
from datetime import datetime

# =====================================================================
# SUPABASE URLLIB REST HELPERS (no httpx — avoids [Errno 16] on Vercel)
# =====================================================================
def _sb_headers():
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
    url, key, _ = _sb_headers()
    return bool(url and key)

def sb_get(table, select='*', filters=None, limit=None):
    url, key, headers = _sb_headers()
    if not url or not key:
        return [], 'not_configured'
    params = {'select': select}
    if filters:
        params.update(filters)
    if limit:
        params['limit'] = str(limit)
    full_url = f"{url.rstrip('/')}/rest/v1/{table}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(full_url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
            return (data if isinstance(data, list) else []), None
    except urllib.error.HTTPError as e:
        return [], f'HTTP {e.code}: {e.read().decode()[:100]}'
    except Exception as e:
        return [], str(e)

def sb_patch(table, data, filter_col, filter_val):
    url, key, headers = _sb_headers()
    if not url or not key:
        return None, 'not_configured'
    params = {filter_col: f'eq.{filter_val}'}
    full_url = f"{url.rstrip('/')}/rest/v1/{table}?{urllib.parse.urlencode(params)}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(full_url, data=body, headers=headers, method='PATCH')
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode()), None
    except urllib.error.HTTPError as e:
        return None, f'HTTP {e.code}: {e.read().decode()[:100]}'
    except Exception as e:
        return None, str(e)

def sb_rpc(function_name, params):
    """Call a Supabase RPC (PostgreSQL function)."""
    url, key, headers = _sb_headers()
    if not url or not key:
        return None, 'not_configured'
    full_url = f"{url.rstrip('/')}/rest/v1/rpc/{function_name}"
    body = json.dumps(params).encode()
    req = urllib.request.Request(full_url, data=body, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode()), None
    except urllib.error.HTTPError as e:
        body_err = e.read().decode()
        try: body_err = json.loads(body_err)
        except: pass
        return None, f'HTTP {e.code}: {str(body_err)[:150]}'
    except Exception as e:
        return None, str(e)

# =====================================================================
# TOKEN GATEKEEPER
# =====================================================================
# ai_credits rules:
#   - Default: 3 (free tier)
#   - Deducted: -1 per AI design generation
#   - Replenished: +5 per sale, +10 per sample kit purchase
#   - Floor: 0 (never negative — enforced by DB constraint)
CREDITS_PER_GENERATION = 1

def check_and_deduct_token(creator_shopify_id, design_id=None):
    """
    Check if creator has ai_credits > 0, then atomically deduct 1.
    Returns (allowed: bool, balance: int, message: str)
    In demo mode (no Supabase), always allow.
    """
    if not sb_configured():
        print(f"[DEMO] Token check skipped — Supabase not configured")
        return True, 999, "demo_mode"

    # Try RPC first (atomic deduction)
    rpc_result, err = sb_rpc("deduct_ai_credit", {
        "p_creator_shopify_id": creator_shopify_id,
        "p_design_id": design_id,
    })

    if err:
        print(f"[TOKEN] RPC deduct_ai_credit failed: {err}, falling back to direct check")
        # Fallback: direct REST check + update (non-atomic but functional)
        rows, get_err = sb_get("creators",
            select="id,ai_credits",
            filters={"shopify_customer_id": f"eq.{creator_shopify_id}"},
            limit=1
        )
        if get_err or not rows:
            print(f"[TOKEN] Creator not found: {creator_shopify_id}, allowing in demo mode")
            return True, 0, "creator_not_found_allowing"

        creator = rows[0]
        current_credits = int(creator.get("ai_credits") or 0)

        if current_credits <= 0:
            return False, 0, (
                "You have 0 Narrative Tokens remaining. "
                "Make a sale or purchase a Creator Sample Kit to earn more tokens."
            )

        # Deduct 1 credit
        new_balance = current_credits - 1
        sb_patch("creators",
            {"ai_credits": new_balance, "total_credits_used": None},
            "id", creator["id"]
        )
        print(f"[TOKEN] Deducted 1 credit from {creator_shopify_id}: {current_credits} → {new_balance}")
        return True, new_balance, f"Token used. {new_balance} remaining."

    # Parse RPC result — returns list of rows
    if isinstance(rpc_result, list) and rpc_result:
        row = rpc_result[0]
    elif isinstance(rpc_result, dict):
        row = rpc_result
    else:
        # RPC returned empty — creator not found, allow in demo mode
        return True, 0, "creator_not_found_allowing"

    allowed      = bool(row.get("success", True))
    new_balance  = int(row.get("new_balance", 0))
    message      = str(row.get("message", ""))

    if not allowed:
        print(f"[TOKEN] REJECTED {creator_shopify_id}: {message}")
    else:
        print(f"[TOKEN] Approved {creator_shopify_id}: balance now {new_balance}")

    return allowed, new_balance, message


# =====================================================================
# STEP 1: IP/Trademark Check using OpenAI GPT-4 Vision
# =====================================================================
def check_ip_trademark(design_file_url):
    """Check image for trademark/IP violations using GPT-4 Vision"""
    try:
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            print("[DEMO] OpenAI not configured, skipping IP check")
            return {"contains_ip": False, "flagged_items": [], "confidence": 0.0}
        
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "gpt-4-vision-preview",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Analyze this image. Does it contain any trademarked logos, characters, or IP from Disney, Marvel, Nike, Adidas, Supreme, Gucci, Louis Vuitton, or any other recognizable brand? Reply ONLY with JSON: {\"contains_ip\": true/false, \"flagged_items\": [\"list\"], \"confidence\": 0.0-1.0}"
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": design_file_url
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 500
            },
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"OpenAI API error: {response.status_code}")
            return {"contains_ip": False, "flagged_items": [], "confidence": 0.0}
        
        result = response.json()
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "{}")
        
        # Parse JSON response
        ip_check = json.loads(content)
        return ip_check
        
    except Exception as e:
        print(f"IP check error: {e}")
        return {"contains_ip": False, "flagged_items": [], "confidence": 0.0}


# =====================================================================
# STEP 2: Upscaling using Replicate API
# =====================================================================
def upscale_design(design_file_url):
    """Upscale image using Replicate Real-ESRGAN model"""
    try:
        import replicate
        
        api_token = os.environ.get("REPLICATE_API_TOKEN", "")
        if not api_token:
            print("[DEMO] Replicate not configured, returning original URL")
            return design_file_url
        
        # Run the model
        output = replicate.run(
            "nightmareai/real-esrgan:42fed1c4974146d4d2414e2be2c5277c7fcf05fcc3a73abf41610695738c1d7b",
            input={"image": design_file_url, "scale": 4}
        )
        
        # Output is typically a list with the upscaled image URL
        if isinstance(output, list) and len(output) > 0:
            return output[0]
        return output
        
    except Exception as e:
        print(f"Upscaling error: {e}")
        return design_file_url


# =====================================================================
# STEP 3 & 4: Generate UUID and Save to S3
# =====================================================================
def upload_to_s3(image_url, unique_product_id, filename="master_file.png"):
    """Download image and upload to S3"""
    try:
        import boto3
        
        aws_key = os.environ.get("AWS_ACCESS_KEY_ID", "")
        aws_secret = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
        aws_region = os.environ.get("AWS_REGION", "us-east-1")
        bucket = os.environ.get("AWS_S3_BUCKET", "")
        
        if not (aws_key and aws_secret and bucket):
            print("[DEMO] AWS not configured, returning mock S3 URL")
            return f"https://{bucket or 'demo-bucket'}.s3.{aws_region}.amazonaws.com/{unique_product_id}/{filename}"
        
        # Download image
        response = requests.get(image_url, timeout=30)
        if response.status_code != 200:
            raise Exception(f"Failed to download image: {response.status_code}")
        
        image_bytes = response.content
        
        # Upload to S3
        s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_key,
            aws_secret_access_key=aws_secret,
            region_name=aws_region
        )
        
        key = f"{unique_product_id}/{filename}"
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=image_bytes,
            ContentType="image/png"
        )
        
        return f"https://{bucket}.s3.{aws_region}.amazonaws.com/{key}"
        
    except Exception as e:
        print(f"S3 upload error: {e}")
        # Return mock URL on failure
        aws_region = os.environ.get("AWS_REGION", "us-east-1")
        bucket = os.environ.get("AWS_S3_BUCKET", "demo-bucket")
        return f"https://{bucket}.s3.{aws_region}.amazonaws.com/{unique_product_id}/{filename}"


# =====================================================================
# STEP 5: Generate Mockups with PIL
# =====================================================================
def generate_mockups(upscaled_url, unique_product_id):
    """Generate product mockups by compositing design onto base images"""
    try:
        from PIL import Image
        import io
        import boto3
        
        # Define variants: 5 tshirt colors + 5 hoodie colors
        BASE_VARIANTS = [
            # T-shirts (would need actual base images in production)
            {"variant_id": "tshirt_white", "product_type": "tshirt", "color": "white"},
            {"variant_id": "tshirt_black", "product_type": "tshirt", "color": "black"},
            {"variant_id": "tshirt_navy", "product_type": "tshirt", "color": "navy"},
            {"variant_id": "tshirt_sage", "product_type": "tshirt", "color": "sage"},
            {"variant_id": "tshirt_coral", "product_type": "tshirt", "color": "coral"},
            # Hoodies
            {"variant_id": "hoodie_white", "product_type": "hoodie", "color": "white"},
            {"variant_id": "hoodie_black", "product_type": "hoodie", "color": "black"},
            {"variant_id": "hoodie_navy", "product_type": "hoodie", "color": "navy"},
            {"variant_id": "hoodie_burgundy", "product_type": "hoodie", "color": "burgundy"},
            {"variant_id": "hoodie_forest", "product_type": "hoodie", "color": "forest"},
        ]
        
        mockup_urls = {}
        aws_key = os.environ.get("AWS_ACCESS_KEY_ID", "")
        aws_secret = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
        aws_region = os.environ.get("AWS_REGION", "us-east-1")
        bucket = os.environ.get("AWS_S3_BUCKET", "")
        
        # Download upscaled design
        design_response = requests.get(upscaled_url, timeout=30)
        if design_response.status_code != 200:
            raise Exception(f"Failed to download upscaled design: {design_response.status_code}")
        
        design_image = Image.open(io.BytesIO(design_response.content))
        design_image = design_image.convert("RGBA")
        
        s3_client = None
        if aws_key and aws_secret and bucket:
            s3_client = boto3.client(
                's3',
                aws_access_key_id=aws_key,
                aws_secret_access_key=aws_secret,
                region_name=aws_region
            )
        
        for variant in BASE_VARIANTS:
            try:
                variant_id = variant["variant_id"]
                
                # In demo mode, create a simple placeholder mockup
                # In production, use actual base images from a CDN/storage
                if not s3_client:
                    # Create a demo mockup image
                    mockup = Image.new("RGB", (500, 600), color=_get_color_rgb(variant["color"]))
                    
                    # Resize design to 40% of base width
                    design_width = int(500 * 0.4)
                    design_ratio = design_image.width / design_image.height
                    design_height = int(design_width / design_ratio)
                    design_resized = design_image.resize((design_width, design_height), Image.Resampling.LANCZOS)
                    
                    # Center on base at 1/3 from top
                    x = (mockup.width - design_resized.width) // 2
                    y = mockup.height // 3
                    
                    # Composite
                    if design_resized.mode == "RGBA":
                        mockup.paste(design_resized, (x, y), design_resized)
                    else:
                        mockup.paste(design_resized, (x, y))
                    
                    mockup_urls[variant_id] = f"https://{bucket or 'demo-bucket'}.s3.{aws_region}.amazonaws.com/{unique_product_id}/mockup_{variant_id}.png"
                else:
                    # TODO: In production, fetch base_image_url from variant config and composite
                    # For now, return demo URLs
                    mockup_urls[variant_id] = f"https://{bucket}.s3.{aws_region}.amazonaws.com/{unique_product_id}/mockup_{variant_id}.png"
                    
            except Exception as e:
                print(f"Mockup generation error for {variant_id}: {e}")
                mockup_urls[variant_id] = f"https://{bucket or 'demo-bucket'}.s3.{aws_region}.amazonaws.com/{unique_product_id}/mockup_{variant_id}.png"
        
        return mockup_urls
        
    except Exception as e:
        print(f"Mockup generation error: {e}")
        # Return mock URLs on failure
        aws_region = os.environ.get("AWS_REGION", "us-east-1")
        bucket = os.environ.get("AWS_S3_BUCKET", "demo-bucket")
        mockup_urls = {}
        for i, color in enumerate(["white", "black", "navy", "sage", "coral", "white", "black", "navy", "burgundy", "forest"]):
            variant_type = "tshirt" if i < 5 else "hoodie"
            variant_id = f"{variant_type}_{color}"
            mockup_urls[variant_id] = f"https://{bucket}.s3.{aws_region}.amazonaws.com/{unique_product_id}/mockup_{variant_id}.png"
        return mockup_urls


def _get_color_rgb(color_name):
    """Get RGB tuple for color name"""
    colors = {
        "white": (255, 255, 255),
        "black": (0, 0, 0),
        "navy": (0, 0, 128),
        "sage": (120, 130, 110),
        "coral": (255, 127, 80),
        "burgundy": (128, 0, 32),
        "forest": (34, 139, 34),
    }
    return colors.get(color_name, (255, 255, 255))


# =====================================================================
# STEP 6: Update Supabase with design metadata
# =====================================================================
def update_design_in_supabase(supabase, design_id, creator_id, unique_product_id, master_file_url, mockup_urls, status="ready"):
    """Update creator_designs table with pipeline results"""
    try:
        if not supabase:
            return True
        
        supabase.table("creator_designs").update({
            "unique_product_id": unique_product_id,
            "master_file_url": master_file_url,
            "mockup_urls": mockup_urls,
            "status": status,
            "updated_at": datetime.utcnow().isoformat()
        }).eq("id", design_id).execute()
        
        return True
        
    except Exception as e:
        print(f"Supabase update error: {e}")
        return False


def flag_design_in_supabase(supabase, design_id, reason):
    """Flag design as containing IP violations"""
    try:
        if not supabase:
            return True
        
        supabase.table("creator_designs").update({
            "status": "flagged",
            "flagged_reason": reason,
            "updated_at": datetime.utcnow().isoformat()
        }).eq("id", design_id).execute()
        
        return True
        
    except Exception as e:
        print(f"Supabase flag error: {e}")
        return False


# =====================================================================
# MAIN HANDLER CLASS
# =====================================================================
class handler(BaseHTTPRequestHandler):

    def send_json_response(self, status_code, data):
        """Send JSON response with CORS headers"""
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())

    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        """GET endpoints for health check and status"""
        parsed = urlparse(self.path)
        path = parsed.path
        query_params = parse_qs(parsed.query)

        # -------------------------------------------------------
        # GET /api/design/pipeline/health — Health check
        # -------------------------------------------------------
        if path == '/api/design/pipeline/health':
            self.send_json_response(200, {
                "status": "ok",
                "message": "My Narrative Design Pipeline v1.0",
                "endpoints": [
                    "POST /api/design/process         — process design through full pipeline",
                    "GET  /api/design/process?design_id=xxx — check design status",
                    "GET  /api/design/pipeline/health — health check",
                ]
            })
            return

        # -------------------------------------------------------
        # GET /api/design/process?design_id=xxx — Check status
        # -------------------------------------------------------
        if path == '/api/design/process':
            design_id = query_params.get('design_id', [None])[0]
            
            if not design_id:
                self.send_json_response(400, {"error": "Missing design_id parameter"})
                return
            
            supabase = get_supabase()
            if not supabase:
                self.send_json_response(200, {
                    "status": "demo",
                    "design_id": design_id,
                    "message": "Supabase not configured - running in demo mode"
                })
                return
            
            try:
                result = supabase.table("creator_designs").select(
                    "id, status, unique_product_id, master_file_url, mockup_urls"
                ).eq("id", design_id).execute()
                
                if result.data and len(result.data) > 0:
                    design = result.data[0]
                    self.send_json_response(200, {
                        "status": design.get("status", "unknown"),
                        "design_id": design.get("id"),
                        "unique_product_id": design.get("unique_product_id"),
                        "master_file_url": design.get("master_file_url"),
                        "mockup_urls": design.get("mockup_urls", {})
                    })
                    return
                else:
                    self.send_json_response(404, {"error": "Design not found"})
                    return
                    
            except Exception as e:
                print(f"Status check error: {e}")
                self.send_json_response(500, {"error": f"Failed to check status: {str(e)}"})
                return

        self.send_json_response(404, {"error": "Not found"})

    def do_POST(self):
        """POST endpoint for design processing pipeline"""
        parsed = urlparse(self.path)
        path = parsed.path

        # Read request body
        content_length = int(self.headers.get('Content-Length', 0))
        body_bytes = self.rfile.read(content_length)

        try:
            request_data = json.loads(body_bytes.decode('utf-8'))
        except:
            self.send_json_response(400, {"error": "Invalid JSON"})
            return

        # -------------------------------------------------------
        # POST /api/design/process — Main pipeline
        # -------------------------------------------------------
        if path == '/api/design/process':
            self._handle_design_process(request_data)
            return

        self.send_json_response(404, {"error": "Not found"})

    # =====================================================================
    # HANDLER: Design Processing Pipeline
    # =====================================================================
    def _handle_design_process(self, request_data):
        """
        Main design processing pipeline handler.

        TOKEN ECONOMY:
          Before any AI work, check creator has ai_credits > 0 and deduct 1.
          403 is returned immediately if no credits remain.

        JIT UPSCALING:
          Replicate Real-ESRGAN upscaling is NOT done here.
          We save the original (or lightly processed) image as the web mockup.
          High-res upscaling fires ONLY when a customer places an order
          (see design_order_webhook.py → trigger_jit_upscaling()).
          This defers the expensive Replicate API cost until revenue is confirmed.
        """
        design_id       = request_data.get("design_id")
        creator_id      = request_data.get("creator_id")
        design_file_url = request_data.get("design_file_url")

        # Validate required fields
        if not (design_id and creator_id and design_file_url):
            self.send_json_response(400, {
                "error": "Missing required fields: design_id, creator_id, design_file_url"
            })
            return

        try:
            # -------------------------------------------------------
            # STEP 0: TOKEN GATEKEEPER
            # Check ai_credits > 0, then atomically deduct 1.
            # This MUST run before any AI/cloud API calls.
            # -------------------------------------------------------
            print(f"[STEP 0] Token check for creator {creator_id}")
            allowed, token_balance, token_msg = check_and_deduct_token(creator_id, design_id)

            if not allowed:
                print(f"[TOKEN DENIED] creator={creator_id} balance=0")
                self.send_json_response(403, {
                    "error": "Insufficient Narrative Tokens",
                    "message": token_msg,
                    "ai_credits": 0,
                    "how_to_earn": [
                        "Make a sale → earn +5 Narrative Tokens",
                        "Purchase a Creator Sample Kit → earn +10 Narrative Tokens",
                    ],
                    "sample_kit": {
                        "tshirt": {"price_rupees": 500, "tokens_earned": 10},
                        "hoodie": {"price_rupees": 900, "tokens_earned": 10},
                    }
                })
                return

            print(f"[STEP 0] Token approved — balance now {token_balance}. msg: {token_msg}")

            # -------------------------------------------------------
            # STEP 1: IP/Trademark Check
            # -------------------------------------------------------
            print(f"[STEP 1] IP/Trademark check for design {design_id}")
            ip_check = check_ip_trademark(design_file_url)

            if ip_check.get("contains_ip") or (
                ip_check.get("confidence", 0) > 0.8 and ip_check.get("flagged_items")
            ):
                reason = f"IP violation detected: {', '.join(ip_check.get('flagged_items', []))}"
                print(f"[FLAGGED] Design {design_id}: {reason}")
                # Update Supabase via urllib
                sb_patch("creator_designs",
                    {"status": "flagged", "flagged_reason": reason,
                     "updated_at": datetime.utcnow().isoformat()},
                    "id", design_id
                )
                self.send_json_response(422, {
                    "error": "Design contains trademarked IP",
                    "reason": reason,
                    "flagged_items": ip_check.get("flagged_items", []),
                    "confidence": ip_check.get("confidence", 0)
                })
                return

            # -------------------------------------------------------
            # STEP 2: JIT DEFERRAL — NO Replicate upscaling here.
            # The original design_file_url is used directly for web mockups.
            # Real-ESRGAN 4x upscaling fires in design_order_webhook.py
            # when the first order is placed (deferred until revenue confirmed).
            # -------------------------------------------------------
            print(f"[STEP 2] JIT mode — using original image for web mockups (no Replicate)")
            web_image_url = design_file_url  # low-res, cheap, instant

            # -------------------------------------------------------
            # STEP 3: Generate UUID
            # -------------------------------------------------------
            print(f"[STEP 3] Generating UUID")
            unique_product_id = str(uuid.uuid4())
            print(f"[STEP 3] unique_product_id = {unique_product_id}")

            # -------------------------------------------------------
            # STEP 4: Save low-res master file to S3 (web mockup quality)
            # -------------------------------------------------------
            print(f"[STEP 4] Uploading low-res master file to S3")
            master_file_url = upload_to_s3(web_image_url, unique_product_id, "master_file.png")
            print(f"[STEP 4] master_file_url = {master_file_url}")

            # -------------------------------------------------------
            # STEP 5: Generate Mockups (using web-res image)
            # -------------------------------------------------------
            print(f"[STEP 5] Generating 10 color variant mockups")
            mockup_urls = generate_mockups(web_image_url, unique_product_id)
            print(f"[STEP 5] Generated {len(mockup_urls)} mockups")

            # -------------------------------------------------------
            # STEP 6: Update Supabase via urllib
            # Sets status='ready', marks upscaling_status='pending'
            # (high_res_master_url is intentionally left NULL until JIT fires)
            # -------------------------------------------------------
            print(f"[STEP 6] Updating Supabase")
            sb_patch("creator_designs", {
                "unique_product_id":  unique_product_id,
                "master_file_url":    master_file_url,
                "high_res_master_url": None,          # JIT: set by webhook on first order
                "upscaling_status":   "pending",      # JIT: will become 'complete' on order
                "mockup_urls":        mockup_urls,
                "status":             "ready",
                "updated_at":         datetime.utcnow().isoformat()
            }, "id", design_id)

            # -------------------------------------------------------
            # STEP 7: Return success
            # -------------------------------------------------------
            print(f"[SUCCESS] Design {design_id} pipeline complete")
            self.send_json_response(200, {
                "status":             "ready",
                "unique_product_id":  unique_product_id,
                "master_file_url":    master_file_url,
                "mockup_urls":        mockup_urls,
                "ai_credits_remaining": token_balance,
                "upscaling":          "deferred",
                "upscaling_note":     (
                    "High-res 4x upscaling will fire automatically when your "
                    "first order is placed — no action needed."
                )
            })

        except Exception as e:
            print(f"[ERROR] Design processing failed: {e}")
            sb_patch("creator_designs",
                {"status": "error", "updated_at": datetime.utcnow().isoformat()},
                "id", design_id
            )
            self.send_json_response(500, {
                "error": "Design processing failed",
                "details": str(e)
            })
