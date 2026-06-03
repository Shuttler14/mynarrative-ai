from http.server import BaseHTTPRequestHandler
import json
import os
import time
import urllib.request
import urllib.error

try:
    import replicate
    REPLICATE_AVAILABLE = True
except ImportError:
    REPLICATE_AVAILABLE = False

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Try importing compositor for full_outfit mode
try:
    from api.vton_compositor import composite_outfit, prepare_garment_layers
    COMPOSITOR_AVAILABLE = True
except ImportError:
    try:
        from vton_compositor import composite_outfit, prepare_garment_layers
        COMPOSITOR_AVAILABLE = True
    except ImportError:
        COMPOSITOR_AVAILABLE = False
        print("⚠️ vton_compositor not available — full_outfit will use inline sequential fallback")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
VERSION = "2.0.0"
QUALITY_STEPS = {
    "preview": 20,
    "final": 40,
}
FLUX_QUALITY_STEPS = {
    "preview": 4,
    "final": 8,
}
DEFAULT_QUALITY = "preview"

# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def _generate_garment_description(garment_image_url):
    """Use GPT-4o-mini to auto-describe a garment image for better VTON results.
    
    Sends the garment image to GPT-4o-mini vision and asks for a concise,
    structured description covering type, color, pattern, fabric, and style.
    Returns a plain-text description string or a sensible fallback.
    """
    if not OPENAI_AVAILABLE:
        print("ℹ️ OpenAI not available — skipping auto garment description")
        return "clothing item"

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ℹ️ OPENAI_API_KEY not set — skipping auto garment description")
        return "clothing item"

    try:
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a fashion garment descriptor for a virtual try-on system. "
                        "Describe clothing items concisely and accurately."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Describe this clothing item in 1 sentence for a virtual try-on system. "
                                "Include: type, color, pattern, fabric, style."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": garment_image_url, "detail": "low"},
                        },
                    ],
                },
            ],
            max_tokens=80,
            temperature=0.3,
        )
        description = response.choices[0].message.content.strip()
        print(f"🏷️ Auto-generated garment description: {description}")
        return description
    except Exception as e:
        print(f"⚠️ Garment description generation failed: {e}")
        return "clothing item"


def _retry_replicate(func, *args, max_retries=1, delay=2, **kwargs):
    """Retry wrapper for Replicate API calls.

    Retries on HTTP 500/503 server errors up to *max_retries* times with a
    *delay* (seconds) between attempts.  All other errors are raised
    immediately.

    Returns the result of ``func(*args, **kwargs)`` on success.
    """
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_error = e
            error_msg = str(e).lower()
            is_retryable = any(code in error_msg for code in ("500", "503", "server error", "service unavailable"))
            if is_retryable and attempt < max_retries:
                print(f"🔄 Replicate call failed (attempt {attempt + 1}/{max_retries + 1}), retrying in {delay}s… Error: {e}")
                time.sleep(delay)
            else:
                raise last_error


def _save_look_to_supabase(user_id, result_image_url, garments, occasion=None, vibe_id=None):
    """Persist the generated look to the user_looks table via Supabase REST API.
    
    This is a fire-and-forget helper — failures are logged but do not
    propagate to the caller so the user still receives their try-on result.
    """
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
    if not supabase_url or not supabase_key:
        print("⚠️ Supabase credentials not configured — skipping look save")
        return None

    payload = json.dumps({
        "user_id": user_id,
        "image_url": result_image_url,
        "garments": garments,
        "occasion": occasion,
        "vibe_id": vibe_id,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{supabase_url}/rest/v1/user_looks",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Prefer": "return=representation",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            saved = json.loads(resp.read().decode())
            print(f"💾 Look saved for user {user_id}: {saved}")
            return saved
    except Exception as e:
        print(f"⚠️ Failed to save look: {e}")
        return None


class handler(BaseHTTPRequestHandler):

    def _error(self, status, message):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({"success": False, "error": message}).encode('utf-8'))

    def _success(self, data):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def do_OPTIONS(self):
        # Handle CORS preflight request
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Max-Age', '86400')
        self.end_headers()

    # ------------------------------------------------------------------
    # GET — Health check
    # ------------------------------------------------------------------
    def do_GET(self):
        """Health-check endpoint returning service status and capabilities."""
        self._success({
            "service": "virtual_try_on",
            "modes": ["vton", "flux", "full_outfit"],
            "replicate_available": REPLICATE_AVAILABLE,
            "openai_available": OPENAI_AVAILABLE,
            "compositor_available": COMPOSITOR_AVAILABLE,
            "version": VERSION,
        })

    # ------------------------------------------------------------------
    # POST — Main handler
    # ------------------------------------------------------------------
    def do_POST(self):
        try:
            # 1. Auth Check
            if not REPLICATE_AVAILABLE:
                self._error(500, "Server Config Error: replicate package not installed. Run: pip install replicate")
                return

            token = os.environ.get("REPLICATE_API_TOKEN") or os.getenv("REPLICATE_API_TOKEN")
            if not token:
                self._error(500, "REPLICATE_API_TOKEN is not set in Vercel environment variables. Please add it at: Vercel Dashboard → Your Project → Settings → Environment Variables → Add REPLICATE_API_TOKEN")
                return

            client = replicate.Client(api_token=token)
            
            # 2. Parse Request
            content_length = int(self.headers['Content-Length'])
            body = json.loads(self.rfile.read(content_length))
            mode = body.get('mode', 'flux') # Default to Flux if not specified
            quality = body.get('quality', DEFAULT_QUALITY)

            output_url = ""

            # ---------------------------------------------------------
            # MODE A: VIRTUAL TRY-ON (Product Page - IDM-VTON)
            # Cost: ~$0.02 - $0.05
            # ---------------------------------------------------------
            if mode == 'vton':
                human_img = body.get('user_image')     # Base64 or URL
                garm_img = body.get('garment_image')   # URL from Shopify CDN
                category = body.get('category', 'upper_body') 

                if not human_img:
                    self._error(400, "Missing 'user_image': provide a base64-encoded photo or a public URL of the person.")
                    return
                if not garm_img:
                    self._error(400, "Missing 'garment_image': provide the public URL of the garment flat-lay image.")
                    return

                # Auto-generate garment description if not provided
                description = body.get('description', '').strip()
                if not description:
                    description = _generate_garment_description(garm_img)

                num_steps = QUALITY_STEPS.get(quality, QUALITY_STEPS[DEFAULT_QUALITY])
                print(f"👕 VTON mode | quality={quality} | steps={num_steps} | category={category}")
                
                # --- AUTO-FETCH LOGIC (FIX FOR MODEL VERSION ERROR) ---
                try:
                    model = client.models.get("cuuupid/idm-vton")
                    latest_version = model.latest_version
                    version_id = latest_version.id
                    print(f"✅ Using IDM-VTON Version: {version_id}")
                except Exception as e:
                    # Fallback to known working hash if auto-fetch fails
                    print(f"⚠️ Auto-fetch failed, using fallback. Error: {e}")
                    version_id = "c871bb9b046607b680449ecbae55fd8c6d945e0a1948644bf2361b3d021d3ff4"

                # Run Prediction (with retry)
                output = _retry_replicate(
                    client.run,
                    f"cuuupid/idm-vton:{version_id}",
                    input={
                        "human_img": human_img,
                        "garm_img": garm_img,
                        "garment_des": description,
                        "category": category,
                        "crop": False,
                        "seed": 42,
                        "steps": num_steps,
                        "force_dc": False,
                        "mask_only": False
                    },
                )
                
                # IDM-VTON returns a FileOutput object
                output_url = str(output) if hasattr(output, '__str__') else output

            # ---------------------------------------------------------
            # MODE B: FANTASY VISUALIZATION (Consultant - FLUX)
            # Cost: ~$0.003
            # ---------------------------------------------------------
            elif mode == 'flux':
                # Constructing the prompt from inputs
                prompt = body.get('prompt')
                # Fallback construction if raw prompt isn't sent
                if not prompt:
                    gender = body.get('gender', 'man')
                    skin = body.get('skin', 'medium')
                    outfit = body.get('outfit', 'stylish streetwear')
                    context = body.get('context', 'studio lighting')
                    prompt = f"A photorealistic full-body shot of an Indian {gender} with {skin} skin tone, wearing {outfit}. Background is {context}. Cinematic lighting, 4k, texture rich, fashion photography."

                flux_steps = FLUX_QUALITY_STEPS.get(quality, FLUX_QUALITY_STEPS[DEFAULT_QUALITY])
                print(f"🎨 Flux mode | quality={quality} | steps={flux_steps}")

                # 1. GENERATE BASE IMAGE WITH FLUX (with retry)
                output = _retry_replicate(
                    client.run,
                    "black-forest-labs/flux-schnell",
                    input={
                        "prompt": prompt,
                        "aspect_ratio": "3:4",
                        "num_inference_steps": flux_steps
                    },
                )
                generated_image_url = output[0] # Flux returns a list

                # 2. OPTIONAL: FACE SWAP
                user_face = body.get('user_image')
                if user_face:
                    print("🔄 Running face swap with latest model version…")
                    # Auto-fetch latest faceswap version
                    try:
                        fs_model = client.models.get("lucataco/faceswap")
                        fs_version_id = fs_model.latest_version.id
                        print(f"✅ Using faceswap version: {fs_version_id}")
                    except Exception as e:
                        print(f"⚠️ Faceswap auto-fetch failed, using fallback. Error: {e}")
                        fs_version_id = "9a4298548422074c3f57258c5d544497314ae4112df80d116f0d2109bd068e9c"

                    swap_output = _retry_replicate(
                        client.run,
                        f"lucataco/faceswap:{fs_version_id}",
                        input={
                            "target_image": generated_image_url,
                            "swap_image": user_face
                        },
                    )
                    output_url = str(swap_output)
                else:
                    output_url = generated_image_url

            # ---------------------------------------------------------
            # MODE C: FULL OUTFIT (Multi-Garment Try-On)
            # Delegates to vton_compositor or runs sequential inline
            # Cost: ~$0.02-$0.05 per garment layer
            # ---------------------------------------------------------
            elif mode == 'full_outfit':
                user_id = body.get('user_id')
                face_image = body.get('face_image')
                body_image = body.get('body_image')
                garments = body.get('garments', [])
                save_look = body.get('save_look', False)
                occasion = body.get('occasion')
                vibe_id = body.get('vibe_id')

                if not body_image:
                    self._error(400, "Missing 'body_image': provide a full-body photo (base64 or URL) as the canvas for garment layering.")
                    return
                if not garments or not isinstance(garments, list):
                    self._error(400, "Missing or invalid 'garments': provide a list of garment objects with at least 'flat_lay_url' and 'category'.")
                    return

                num_steps = QUALITY_STEPS.get(quality, QUALITY_STEPS[DEFAULT_QUALITY])
                print(f"👗 Full Outfit mode | {len(garments)} garments | quality={quality} | steps={num_steps}")

                # --- Try compositor first, fall back to inline sequential ---
                if COMPOSITOR_AVAILABLE:
                    print("🧩 Using vton_compositor for multi-garment compositing…")
                    try:
                        layers = prepare_garment_layers(garments)
                        result = composite_outfit(
                            client=client,
                            body_image=body_image,
                            face_image=face_image,
                            layers=layers,
                            quality=quality,
                        )
                        output_url = result.get("image", "")
                    except Exception as e:
                        print(f"⚠️ Compositor failed, falling back to inline sequential: {e}")
                        output_url = self._run_sequential_vton(client, body_image, garments, num_steps)
                else:
                    # Inline sequential fallback
                    output_url = self._run_sequential_vton(client, body_image, garments, num_steps)

                # Optional face swap onto the composited result
                if face_image and output_url:
                    print("🔄 Applying face swap to composited outfit…")
                    try:
                        fs_model = client.models.get("lucataco/faceswap")
                        fs_version_id = fs_model.latest_version.id
                    except Exception:
                        fs_version_id = "9a4298548422074c3f57258c5d544497314ae4112df80d116f0d2109bd068e9c"
                    try:
                        swap_out = _retry_replicate(
                            client.run,
                            f"lucataco/faceswap:{fs_version_id}",
                            input={
                                "target_image": output_url,
                                "swap_image": face_image,
                            },
                        )
                        output_url = str(swap_out)
                        print("✅ Face swap applied successfully")
                    except Exception as e:
                        print(f"⚠️ Face swap failed (continuing without): {e}")

                # Persist look if requested
                if save_look and user_id and output_url:
                    garment_summary = [
                        {"url": g.get("flat_lay_url"), "category": g.get("category")}
                        for g in garments
                    ]
                    _save_look_to_supabase(user_id, output_url, garment_summary, occasion, vibe_id)

            # ---------------------------------------------------------
            # Unknown mode
            # ---------------------------------------------------------
            else:
                self._error(400, f"Unknown mode '{mode}'. Supported modes: vton, flux, full_outfit")
                return

            # 3. Success Response
            self._success({"success": True, "image": output_url})

        except Exception as e:
            error_msg = str(e)
            # Check for Replicate-specific errors by message content
            if '402' in error_msg or 'payment' in error_msg.lower() or 'credit' in error_msg.lower():
                error_msg = '💳 Replicate credits exhausted. Add credits at replicate.com/account/billing'
            elif '422' in error_msg or 'version' in error_msg.lower():
                error_msg = '⚠️ AI model version error. Please try again — the system will auto-fetch the latest version. If this persists, contact support.'
            elif '401' in error_msg or 'unauthorized' in error_msg.lower() or 'token' in error_msg.lower():
                error_msg = '🔑 Invalid REPLICATE_API_TOKEN. Please check your Vercel environment variables.'
            elif '429' in error_msg or 'rate' in error_msg.lower():
                error_msg = '⏳ Rate limit reached. Please wait a moment and try again.'
            elif '500' in error_msg or '503' in error_msg:
                error_msg = '🔧 Replicate server error. The AI service is temporarily unavailable — please retry in a few seconds.'
            self._error(500, error_msg)

    # ------------------------------------------------------------------
    # Internal: sequential VTON for full_outfit inline fallback
    # ------------------------------------------------------------------
    def _run_sequential_vton(self, client, body_image, garments, num_steps):
        """Run IDM-VTON sequentially for each garment, piping the output
        of one pass as the input for the next.

        Returns the final composited image URL.
        """
        print(f"🔗 Running sequential VTON for {len(garments)} garment(s)…")

        # Fetch IDM-VTON version once
        try:
            model = client.models.get("cuuupid/idm-vton")
            version_id = model.latest_version.id
            print(f"✅ Using IDM-VTON Version: {version_id}")
        except Exception as e:
            print(f"⚠️ Auto-fetch failed, using fallback. Error: {e}")
            version_id = "c871bb9b046607b680449ecbae55fd8c6d945e0a1948644bf2361b3d021d3ff4"

        current_image = body_image

        for idx, garment in enumerate(garments):
            flat_lay_url = garment.get("flat_lay_url")
            category = garment.get("category", "upper_body")
            description = garment.get("description", "").strip()

            if not flat_lay_url:
                print(f"⚠️ Garment #{idx + 1} missing 'flat_lay_url' — skipping")
                continue

            # Auto-describe if needed
            if not description:
                description = _generate_garment_description(flat_lay_url)

            print(f"  👕 Garment {idx + 1}/{len(garments)}: {category} — \"{description[:60]}\"")

            output = _retry_replicate(
                client.run,
                f"cuuupid/idm-vton:{version_id}",
                input={
                    "human_img": current_image,
                    "garm_img": flat_lay_url,
                    "garment_des": description,
                    "category": category,
                    "crop": False,
                    "seed": 42,
                    "steps": num_steps,
                    "force_dc": False,
                    "mask_only": False,
                },
            )
            current_image = str(output) if hasattr(output, '__str__') else output
            print(f"  ✅ Garment {idx + 1} applied → {current_image[:80]}…")

        return current_image