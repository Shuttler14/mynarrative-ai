"""
generate_design.py
===================================================================
OpenAI-powered t-shirt design generator for the AI Studio.

Pipeline per request:
  1.  Receive { slogan, style, color, source_input? }
  2.  Build a print-ready prompt (transparent-isolated subject, high
      contrast, limited palette, lockup composition).
  3.  Call OpenAI Images API (gpt-image-1) — returns base64 PNG.
  4.  Upload the bytes to Supabase Storage (bucket: creator_assets).
  5.  Return a stable public URL so the frontend can render it and
      later submit it as a draft design.

Env vars required:
  OPENAI_API_KEY
  SUPABASE_URL
  SUPABASE_SERVICE_KEY   (preferred; falls back to SUPABASE_KEY)

Deploy target: creator-economy-api (Vercel)
Route: /api/generate_design  (also aliased below via vercel.json:
       /api/ai/design-image  → /api/generate_design)
===================================================================
"""
from http.server import BaseHTTPRequestHandler
import os
import json
import base64
import uuid
import time
import urllib.request
import urllib.error

from openai import OpenAI

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or ""
)

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


def _build_prompt(slogan: str, style: str, color: str, source_input: str) -> str:
    """
    Build a print-ready t-shirt design prompt.
    The output MUST be:
      - Isolated subject on a plain background (easy to knock out)
      - High contrast, limited palette (so DTG / screen print is clean)
      - Typography legible at 12-inch print size
    """
    slogan_clean = (slogan or "").strip().replace('"', '').replace("'", "")[:120]
    style_clean = (style or "minimalist typography").strip()[:200]
    color_clean = (color or "black").strip().lower()[:40]

    # Map brand-ish colors to palette guidance
    palette_hint = {
        "white":    "pure white garment; design in rich black with one accent",
        "black":    "jet-black garment; design in bright white with one accent",
        "beige":    "warm sand-beige garment; design in espresso brown with cream accents",
        "lavender": "soft lavender garment; design in deep plum with mint accent",
        "brown":    "dark-chocolate garment; design in off-white with ochre accent",
    }.get(color_clean, f"{color_clean} garment; design in a single high-contrast ink")

    prompt = (
        "Design a single print-ready artwork for the chest of a premium "
        "t-shirt / hoodie. The artwork must be ISOLATED on a flat, plain, "
        "empty background so it can be cleanly printed.\n\n"
        f"Slogan to render on the shirt (EXACT wording, no substitutions): \"{slogan_clean}\"\n"
        f"Art direction: {style_clean}.\n"
        f"Palette: {palette_hint}.\n\n"
        "HARD CONSTRAINTS:\n"
        "- NO human model, NO mockup, NO shirt, NO body. Just the artwork itself.\n"
        "- Centered lockup composition, suitable for a ~12 inch chest print.\n"
        "- Typography must be legible, crisp, and pixel-perfect at 1024×1024.\n"
        "- Limit the palette to 2–3 flat colors. No photorealism. No gradients longer than 20%.\n"
        "- No watermarks, borders, signatures, frames, or extra text beyond the slogan.\n"
        "- No logos of real brands, no celebrities, no copyrighted characters.\n"
        f"Emotional cue from the wearer (subtext only, do not spell it out): {source_input[:160] if source_input else 'personal identity'}."
    )
    return prompt


def _supabase_upload_png(png_bytes: bytes, filename_hint: str) -> str:
    """Upload PNG bytes to the creator_assets bucket and return the public URL."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("supabase_not_configured")

    safe = uuid.uuid4().hex
    fname = f"ai-designs/{int(time.time())}-{safe}.png"
    url = f"{SUPABASE_URL}/storage/v1/object/creator_assets/{fname}"

    req = urllib.request.Request(
        url,
        data=png_bytes,
        method="POST",
        headers={
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "apikey": SUPABASE_KEY,
            "Content-Type": "image/png",
            "x-upsert": "true",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status >= 300:
                body = resp.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"supabase_upload_failed:{resp.status}:{body}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
        raise RuntimeError(f"supabase_upload_failed:{e.code}:{body}")

    return f"{SUPABASE_URL}/storage/v1/object/public/creator_assets/{fname}"


class handler(BaseHTTPRequestHandler):
    def _send(self, status: int, payload: dict):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def do_OPTIONS(self):
        self._send(200, {"ok": True})

    def do_GET(self):
        # Lightweight health check
        self._send(200, {
            "success": True,
            "service": "generate_design",
            "openai_configured": bool(OPENAI_API_KEY),
            "supabase_configured": bool(SUPABASE_URL and SUPABASE_KEY),
        })

    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(content_length) if content_length else b"{}"
            body = json.loads(raw or b"{}")
        except Exception as e:
            return self._send(400, {"success": False, "error": f"bad_json:{e}"})

        slogan       = body.get("slogan") or body.get("quote") or ""
        style        = body.get("style") or "minimalist typography"
        color        = body.get("color") or "black"
        source_input = body.get("source_input") or body.get("user_input") or ""
        # Allow overriding size/quality for debugging, but clamp.
        size    = body.get("size", "1024x1024")
        if size not in ("1024x1024", "1024x1536", "1536x1024"):
            size = "1024x1024"
        quality = body.get("quality", "medium")
        if quality not in ("low", "medium", "high"):
            quality = "medium"

        if not slogan:
            return self._send(400, {"success": False, "error": "missing_slogan"})
        if client is None:
            return self._send(500, {"success": False, "error": "openai_not_configured"})

        prompt = _build_prompt(slogan, style, color, source_input)

        # 1. Generate the image. Try gpt-image-1 first (best quality, supports
        #    transparent backgrounds). If the OpenAI org isn't verified for it,
        #    or it returns any error, transparently fall back to dall-e-3.
        png_bytes = None
        used_model = None
        primary_error = None

        # --- Attempt A: gpt-image-1 (b64_json) --------------------------------
        try:
            result = client.images.generate(
                model="gpt-image-1",
                prompt=prompt,
                size=size,
                quality=quality,
                n=1,
                background="transparent",
            )
            if result and getattr(result, "data", None):
                b64 = getattr(result.data[0], "b64_json", None)
                if b64:
                    png_bytes = base64.b64decode(b64)
                    used_model = "gpt-image-1"
                else:
                    # Some SDKs return `url` even for gpt-image-1 in rare cases.
                    img_url = getattr(result.data[0], "url", None)
                    if img_url:
                        with urllib.request.urlopen(img_url, timeout=20) as r:
                            png_bytes = r.read()
                        used_model = "gpt-image-1"
        except Exception as e:
            primary_error = str(e)

        # --- Attempt B: dall-e-3 (URL) ----------------------------------------
        if png_bytes is None:
            try:
                # dall-e-3 supports 1024x1024, 1024x1792, 1792x1024 and quality hd/standard.
                dalle_size = size if size in ("1024x1024", "1024x1792", "1792x1024") else "1024x1024"
                dalle_quality = "hd" if quality == "high" else "standard"
                result = client.images.generate(
                    model="dall-e-3",
                    prompt=prompt,
                    size=dalle_size,
                    quality=dalle_quality,
                    n=1,
                )
                img_url = getattr(result.data[0], "url", None) if result and result.data else None
                if not img_url:
                    return self._send(502, {
                        "success": False,
                        "error": "openai_no_image_data",
                        "primary_error": primary_error,
                    })
                with urllib.request.urlopen(img_url, timeout=25) as r:
                    png_bytes = r.read()
                used_model = "dall-e-3"
            except Exception as e:
                return self._send(502, {
                    "success": False,
                    "error": f"openai_failed:{e}",
                    "primary_error": primary_error,
                })

        # 2. Upload to Supabase for a stable public URL.
        try:
            public_url = _supabase_upload_png(png_bytes, filename_hint=slogan)
        except Exception as e:
            # Fallback: return as data URL so the UI still shows something.
            data_url = "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")
            return self._send(200, {
                "success": True,
                "image_url": data_url,
                "storage": "data_url",
                "warning": f"supabase_upload_failed:{e}",
                "model": used_model,
                "style": style,
                "slogan": slogan,
            })

        return self._send(200, {
            "success": True,
            "image_url": public_url,
            "storage": "supabase",
            "model": used_model,
            "style": style,
            "slogan": slogan,
        })
