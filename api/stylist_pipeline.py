"""
================================================================================
  MY NARRATIVE AI STYLIST — BACKEND PIPELINE
  api/stylist_pipeline.py
================================================================================

  PURPOSE:
  Vercel Serverless Function that orchestrates the full AI Stylist pipeline:
    Step 1 (receive):  occasion + vibe_id from frontend
    Step 2 (parallel):  extract_biometrics() + segment_wardrobe() — run concurrently
    Step 3 (sequential): build_flux_prompt() → generate_flux_image() → face_swap()
    Step 4 (lookup):    get_affiliate_recommendation() — mock upsell data
    Step 5 (return):    aggregated response to frontend

  ANTI-HALLUCINATION GUARDRAILS:
  ✅ All CV/ML tasks are clean WRAPPER FUNCTIONS calling external APIs.
  ✅ No PyTorch, TensorFlow, or OpenCV code is written here.
  ✅ FLUX and Face Swap are sequenced, never merged into one call.
  ✅ Affiliate data uses mock JSON, not a real web scraper.

  REQUIRED ENVIRONMENT VARIABLES (set in Vercel Dashboard):
  ─────────────────────────────────────────────────────────
  REPLICATE_API_TOKEN     → Replicate.com API token (for FLUX + Face Swap)
  VISION_API_KEY          → API key for the Vision Model (DeepFashion2-style segmentation)
  VISION_API_URL          → Endpoint URL for the Vision Model API
  BIOMETRICS_API_KEY      → API key for face / skin-tone / body-type detection
  BIOMETRICS_API_URL      → Endpoint URL for the Biometrics API
  SUPABASE_URL            → Supabase project URL (for pgvector Ghost Closet)
  SUPABASE_KEY            → Supabase anon/service key

================================================================================
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import uuid
import time
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed

# ---------------------------------------------------------------------------
# OPTIONAL IMPORTS — graceful degradation if not installed
# ---------------------------------------------------------------------------
try:
    import replicate
    REPLICATE_AVAILABLE = True
except ImportError:
    REPLICATE_AVAILABLE = False

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

try:
    import requests as http_requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


# ---------------------------------------------------------------------------
# CONFIGURATION & CONSTANTS
# ---------------------------------------------------------------------------

# Monk Skin Tone (MST) Scale — 10 tones from light to dark
# Reference: https://skintone.google/
MST_LABELS = {
    1: "Very Light",
    2: "Light",
    3: "Light-Medium",
    4: "Medium-Light",
    5: "Medium",
    6: "Medium-Tan",
    7: "Tan",
    8: "Dark-Tan",
    9: "Dark",
    10: "Very Dark",
}

# Color theory mapping: MST → complementary fashion tones
# This is the "Why This Works" tooltip data
MST_COLOR_THEORY = {
    1: {"best_colors": ["Navy", "Emerald", "Burgundy", "Charcoal"], "avoid": ["Pale Yellow", "Beige"], "undertone_note": "Cool jewel tones create striking contrast."},
    2: {"best_colors": ["Forest Green", "Plum", "Cobalt Blue", "Rust"], "avoid": ["Neon Yellow"], "undertone_note": "Rich earth tones and deep jewels balance lighter skin."},
    3: {"best_colors": ["Teal", "Coral", "Olive", "Mustard"], "avoid": ["Washed-out Pastels"], "undertone_note": "Warm mid-tones with subtle saturation work best."},
    4: {"best_colors": ["Burnt Orange", "Royal Blue", "Sage Green", "Maroon"], "avoid": ["Khaki"], "undertone_note": "Warm undertones pair beautifully with earth-inspired shades."},
    5: {"best_colors": ["Hot Pink", "Turquoise", "Gold", "Wine Red"], "avoid": ["Muddy Brown"], "undertone_note": "Medium tones can carry both warm and cool palettes."},
    6: {"best_colors": ["Tangerine", "Electric Blue", "Lavender", "Cream"], "avoid": ["Dark Brown"], "undertone_note": "High-contrast brights create editorial impact."},
    7: {"best_colors": ["White", "Bright Yellow", "Fuchsia", "Sky Blue"], "avoid": ["Dark Navy"], "undertone_note": "Vibrant, saturated colors pop against warm tan skin."},
    8: {"best_colors": ["Ivory", "Gold", "Coral Red", "Emerald"], "avoid": ["Charcoal Grey"], "undertone_note": "Warm metallics and bright jewel tones celebrate deep warmth."},
    9: {"best_colors": ["White", "Canary Yellow", "Hot Pink", "Cobalt"], "avoid": ["Dark Olive"], "undertone_note": "High-saturation pure colors create maximum visual impact."},
    10: {"best_colors": ["Pure White", "Bright Orange", "Electric Green", "Gold"], "avoid": ["Dark Brown", "Black"], "undertone_note": "Bold, luminous colors create stunning contrast."},
}

# Vibe presets — these map vibe_id to FLUX prompt modifiers
VIBE_PRESETS = {
    "caffeine_survivor": {
        "label": "Surviving on Caffeine ☕",
        "flux_modifier": "oversized cozy hoodie, distressed denim, messy-chic hair, coffee shop aesthetic",
        "style_persona": "effortlessly unbothered",
    },
    "sarcastic_rizzler": {
        "label": "The Sarcastic Rizzler 😏",
        "flux_modifier": "sharp tailored blazer, statement sneakers, confident pose, editorial lighting",
        "style_persona": "sharp-witted trendsetter",
    },
    "main_character": {
        "label": "Main Character Energy ✨",
        "flux_modifier": "dramatic flowing outfit, cinematic backlighting, street style, golden hour",
        "style_persona": "the protagonist of every scene",
    },
    "quiet_luxury": {
        "label": "Quiet Luxury 🤫",
        "flux_modifier": "minimal neutral tones, cashmere texture, understated elegance, clean silhouette",
        "style_persona": "old-money minimalist",
    },
}

# Occasion presets — map occasion to FLUX prompt context
OCCASION_PRESETS = {
    "date_night": {
        "label": "Date Night 🌙",
        "flux_context": "romantic evening setting, warm ambient lighting, upscale restaurant vibes",
        "style_direction": "elevated casual to semi-formal",
    },
    "office": {
        "label": "Office 💼",
        "flux_context": "modern corporate office, clean backdrop, professional lighting",
        "style_direction": "smart casual to business formal",
    },
    "sangeet": {
        "label": "Sangeet 💃",
        "flux_context": "vibrant Indian wedding sangeet celebration, colorful lighting, festive atmosphere",
        "style_direction": "festive ethnic with modern fusion",
    },
    "airport_look": {
        "label": "Airport Look ✈️",
        "flux_context": "luxury airport terminal, travel aesthetic, natural daylight",
        "style_direction": "comfortable yet polished travel wear",
    },
}


# ============================================================================
#  SECTION 1: EXTERNAL API WRAPPER FUNCTIONS
#  ──────────────────────────────────────────
#  These are CLEAN WRAPPERS. They call external APIs and return structured data.
#  They do NOT contain any ML model code. Replace endpoints with your actual APIs.
# ============================================================================

def extract_biometrics(image_base64: str) -> dict:
    """
    ┌──────────────────────────────────────────────────────────────────────┐
    │  WRAPPER: Biometric Extraction                                     │
    │  ──────────────────────────────────────────────────────────────────  │
    │  Calls an external API to detect:                                  │
    │    • Face bounding box (x, y, width, height)                       │
    │    • Monk Skin Tone (MST) scale value (1-10)                       │
    │    • Body type estimation (slim, athletic, average, plus)          │
    │    • Gender presentation (for FLUX prompt accuracy)                │
    │                                                                    │
    │  REQUIRES: BIOMETRICS_API_KEY, BIOMETRICS_API_URL                  │
    │  REPLACE: The mock response below with real API call               │
    └──────────────────────────────────────────────────────────────────────┘
    """
    api_key = os.environ.get("BIOMETRICS_API_KEY")
    api_url = os.environ.get("BIOMETRICS_API_URL")

    if api_key and api_url and REQUESTS_AVAILABLE:
        # ─── REAL API CALL (uncomment when API is ready) ───
        # response = http_requests.post(
        #     api_url,
        #     headers={
        #         "Authorization": f"Bearer {api_key}",
        #         "Content-Type": "application/json",
        #     },
        #     json={"image": image_base64},
        #     timeout=30,
        # )
        # response.raise_for_status()
        # return response.json()
        pass

    # ─── MOCK RESPONSE (used until real API is connected) ───
    print("⚠️  [extract_biometrics] Using MOCK data — connect BIOMETRICS_API_URL for production")
    return {
        "face_detected": True,
        "face_bbox": {"x": 120, "y": 80, "width": 200, "height": 250},
        "monk_skin_tone": 5,           # MST scale 1-10
        "mst_label": MST_LABELS[5],    # "Medium"
        "body_type": "athletic",       # slim | athletic | average | plus
        "gender_presentation": "man",  # man | woman | non-binary
        "confidence": 0.92,
        "face_image_base64": image_base64[:100] + "...",  # Cropped face placeholder
    }


def segment_wardrobe(image_base64: str) -> dict:
    """
    ┌──────────────────────────────────────────────────────────────────────┐
    │  WRAPPER: Wardrobe Segmentation (DeepFashion2-style)               │
    │  ──────────────────────────────────────────────────────────────────  │
    │  Calls a Vision API to detect, classify, and crop individual       │
    │  clothing items from the full-body photo.                          │
    │                                                                    │
    │  Returns items: top, bottom, footwear, accessories                 │
    │  Each item includes: category, color, pattern, cropped_image       │
    │                                                                    │
    │  REQUIRES: VISION_API_KEY, VISION_API_URL                          │
    │  REPLACE: The mock response below with real API call               │
    └──────────────────────────────────────────────────────────────────────┘
    """
    api_key = os.environ.get("VISION_API_KEY")
    api_url = os.environ.get("VISION_API_URL")

    if api_key and api_url and REQUESTS_AVAILABLE:
        # ─── REAL API CALL (uncomment when API is ready) ───
        # response = http_requests.post(
        #     api_url,
        #     headers={
        #         "Authorization": f"Bearer {api_key}",
        #         "Content-Type": "application/json",
        #     },
        #     json={
        #         "image": image_base64,
        #         "tasks": ["segmentation", "classification", "color_extraction"],
        #     },
        #     timeout=45,
        # )
        # response.raise_for_status()
        # return response.json()
        pass

    # ─── MOCK RESPONSE (used until real API is connected) ───
    print("⚠️  [segment_wardrobe] Using MOCK data — connect VISION_API_URL for production")
    return {
        "items_detected": 4,
        "items": [
            {
                "id": str(uuid.uuid4()),
                "slot": "top",
                "category": "Topwear",
                "sub_category": "Oversized Hoodie",
                "color": "Charcoal Grey",
                "pattern": "solid",
                "style": "Western",
                "confidence": 0.95,
                "cropped_image_base64": "mock_cropped_top_base64...",
                "description": "Dark grey oversized cotton hoodie with kangaroo pocket",
            },
            {
                "id": str(uuid.uuid4()),
                "slot": "bottom",
                "category": "Bottomwear",
                "sub_category": "Slim Jeans",
                "color": "Indigo Blue",
                "pattern": "solid",
                "style": "Western",
                "confidence": 0.93,
                "cropped_image_base64": "mock_cropped_bottom_base64...",
                "description": "Dark wash indigo slim-fit denim jeans",
            },
            {
                "id": str(uuid.uuid4()),
                "slot": "footwear",
                "category": "Footwear",
                "sub_category": "Running Shoes",
                "color": "Black",
                "pattern": "solid",
                "style": "Western",
                "confidence": 0.88,
                "cropped_image_base64": "mock_cropped_shoes_base64...",
                "description": "Black mesh running shoes with white sole",
            },
            {
                "id": str(uuid.uuid4()),
                "slot": "accessory",
                "category": "Accessory",
                "sub_category": "Watch",
                "color": "Silver",
                "pattern": "solid",
                "style": "Western",
                "confidence": 0.78,
                "cropped_image_base64": "mock_cropped_accessory_base64...",
                "description": "Silver minimalist analog watch with mesh band",
            },
        ],
    }


def save_to_ghost_closet(user_id: str, wardrobe_items: list) -> dict:
    """
    ┌──────────────────────────────────────────────────────────────────────┐
    │  WRAPPER: Save to Ghost Closet (pgvector in Supabase)              │
    │  ──────────────────────────────────────────────────────────────────  │
    │  Saves extracted wardrobe items as vector embeddings in the        │
    │  Supabase PostgreSQL database with pgvector extension.              │
    │                                                                    │
    │  Each item gets:                                                    │
    │    • A text embedding (from item description)                       │
    │    • Metadata (category, color, pattern, style)                     │
    │    • A cropped image URL (stored in Supabase Storage)               │
    │                                                                    │
    │  This builds the user's "Digital Closet" / "Style Graph" over      │
    │  time, enabling personalized recommendations.                       │
    │                                                                    │
    │  REQUIRES: SUPABASE_URL, SUPABASE_KEY                              │
    └──────────────────────────────────────────────────────────────────────┘
    """
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")

    saved_items = []

    if supabase_url and supabase_key and SUPABASE_AVAILABLE:
        try:
            supabase: Client = create_client(supabase_url, supabase_key)

            for item in wardrobe_items:
                record = {
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "image_url": item.get("cropped_image_base64", ""),  # Would be a real URL in production
                    "category": item.get("category", "Unknown"),
                    "color": item.get("color", "Unknown"),
                    "tags": [
                        item.get("sub_category", ""),
                        item.get("pattern", ""),
                        item.get("style", ""),
                    ],
                    # In production, you would also store:
                    # "embedding": generate_embedding(item["description"]),
                    # This would be a 768-dim or 1536-dim vector from an embedding model
                }
                # Upsert to Supabase
                result = supabase.table("closet_items").insert(record).execute()
                saved_items.append(record["id"])

            print(f"✅ [save_to_ghost_closet] Saved {len(saved_items)} items for user {user_id}")
        except Exception as e:
            print(f"⚠️  [save_to_ghost_closet] Supabase error: {e}")
            # Fall through to mock response
    else:
        print("⚠️  [save_to_ghost_closet] Using MOCK save — connect Supabase for production")
        for item in wardrobe_items:
            saved_items.append(str(uuid.uuid4()))

    return {
        "success": True,
        "user_id": user_id,
        "items_saved": len(saved_items),
        "item_ids": saved_items,
    }


# ============================================================================
#  SECTION 2: FLUX IMAGE GENERATION + FACE SWAP PIPELINE
#  ──────────────────────────────────────────────────────
#  CRITICAL SEQUENCING:
#    Step A → Build the FLUX prompt from user data
#    Step B → FLUX generates the editorial body + clothes image
#    Step C → Face Swap applies the user's actual face onto the FLUX output
#  These MUST be sequential. FLUX and Face Swap are never called together.
# ============================================================================

def build_flux_prompt(biometrics: dict, wardrobe: dict, occasion: str, vibe_id: str) -> str:
    """
    Constructs a detailed FLUX image generation prompt by combining:
    - Biometric data (skin tone, body type, gender)
    - Wardrobe items from the user's photo
    - Occasion context
    - Vibe personality modifier

    Returns a single natural-language prompt string for FLUX.
    """
    # Get MST label for skin tone accuracy
    mst_value = biometrics.get("monk_skin_tone", 5)
    mst_label = MST_LABELS.get(mst_value, "Medium")
    gender = biometrics.get("gender_presentation", "person")
    body_type = biometrics.get("body_type", "average")

    # Get vibe style modifier
    vibe = VIBE_PRESETS.get(vibe_id, VIBE_PRESETS["caffeine_survivor"])
    vibe_modifier = vibe["flux_modifier"]

    # Get occasion context
    occ = OCCASION_PRESETS.get(occasion, OCCASION_PRESETS["date_night"])
    occasion_context = occ["flux_context"]

    # Extract the user's existing clothing for style coherence
    user_items = wardrobe.get("items", [])
    existing_pieces = []
    for item in user_items:
        if item.get("slot") in ("top", "bottom"):
            existing_pieces.append(f"{item['color']} {item['sub_category']}")

    existing_clothing_str = ", ".join(existing_pieces) if existing_pieces else "stylish contemporary outfit"

    # ─── CONSTRUCT THE PROMPT ───
    prompt = (
        f"High-end fashion editorial photograph of an Indian {gender} with "
        f"{mst_label.lower()} ({mst_label}) skin tone and {body_type} build. "
        f"Wearing: {vibe_modifier}, styled with {existing_clothing_str}. "
        f"Setting: {occasion_context}. "
        f"Shot on Hasselblad, cinematic color grading, 4K resolution, "
        f"texture-rich fabrics, natural skin texture, fashion magazine quality. "
        f"Full body shot, head to toe visible, facing camera."
    )

    print(f"🎨 [build_flux_prompt] Generated prompt ({len(prompt)} chars)")
    return prompt


def generate_flux_image(prompt: str) -> str:
    """
    ┌──────────────────────────────────────────────────────────────────────┐
    │  STEP 3B: FLUX Image Generation                                     │
    │  ──────────────────────────────────────────────────────────────────  │
    │  Calls FLUX (via Replicate) to generate a photorealistic editorial │
    │  fashion image from the constructed prompt.                         │
    │                                                                    │
    │  IMPORTANT: This generates ONLY the body and clothes.              │
    │  The face will be swapped in Step 3C.                               │
    │                                                                    │
    │  REQUIRES: REPLICATE_API_TOKEN                                     │
    │  MODEL: black-forest-labs/flux-schnell (fast) or flux-dev (quality)│
    └──────────────────────────────────────────────────────────────────────┘
    """
    token = os.environ.get("REPLICATE_API_TOKEN")

    if token and REPLICATE_AVAILABLE:
        try:
            client = replicate.Client(api_token=token)
            print("🖼️  [generate_flux_image] Calling FLUX API...")

            output = client.run(
                "black-forest-labs/flux-schnell",
                input={
                    "prompt": prompt,
                    "aspect_ratio": "3:4",         # Portrait orientation for fashion
                    "num_inference_steps": 4,       # Speed optimized for schnell
                    "output_format": "webp",
                    "output_quality": 90,
                },
            )
            # FLUX returns a list of FileOutput objects
            image_url = str(output[0]) if output else None

            if image_url:
                print(f"✅ [generate_flux_image] Image generated: {image_url[:80]}...")
                return image_url
            else:
                raise Exception("FLUX returned empty output")

        except Exception as e:
            print(f"❌ [generate_flux_image] FLUX API error: {e}")
            raise

    # ─── MOCK FALLBACK ───
    print("⚠️  [generate_flux_image] Using MOCK image — connect REPLICATE_API_TOKEN for production")
    return "https://placehold.co/768x1024/1a1a2e/e94560?text=FLUX+Generated+Image"


def apply_face_swap(flux_image_url: str, user_face_image: str) -> str:
    """
    ┌──────────────────────────────────────────────────────────────────────┐
    │  STEP 3C: Face Swap (Identity Transfer)                             │
    │  ──────────────────────────────────────────────────────────────────  │
    │  Takes the FLUX-generated editorial image and swaps the generic    │
    │  face with the user's actual face from their uploaded photo.        │
    │                                                                    │
    │  CRITICAL: This runs AFTER generate_flux_image(), never in         │
    │  parallel. FLUX generates the body → Face Swap applies identity.   │
    │                                                                    │
    │  REQUIRES: REPLICATE_API_TOKEN                                     │
    │  MODEL: lucataco/faceswap (InsightFace-based)                      │
    └──────────────────────────────────────────────────────────────────────┘
    """
    token = os.environ.get("REPLICATE_API_TOKEN")

    if token and REPLICATE_AVAILABLE:
        try:
            client = replicate.Client(api_token=token)
            print("🔄 [apply_face_swap] Calling Face Swap API...")

            swap_output = client.run(
                "lucataco/faceswap:9a4298548422074c3f57258c5d544497314ae4112df80d116f0d2109bd068e9c",
                input={
                    "target_image": flux_image_url,   # FLUX output (body + clothes)
                    "swap_image": user_face_image,     # User's original photo (face source)
                },
            )

            result_url = str(swap_output) if swap_output else None

            if result_url:
                print(f"✅ [apply_face_swap] Face swap complete: {result_url[:80]}...")
                return result_url
            else:
                raise Exception("Face Swap returned empty output")

        except Exception as e:
            print(f"❌ [apply_face_swap] Face Swap error: {e}")
            # Return FLUX image without face swap as graceful fallback
            print("⚠️  Falling back to FLUX image without face swap")
            return flux_image_url

    # ─── MOCK FALLBACK ───
    print("⚠️  [apply_face_swap] Using MOCK face swap — connect REPLICATE_API_TOKEN for production")
    return "https://placehold.co/768x1024/16213e/0f3460?text=Face+Swapped+Image"


# ============================================================================
#  SECTION 3: AFFILIATE / MONETIZATION (The "Switzerland" Upsell)
#  ──────────────────────────────────────────────────────────────
#  ANTI-HALLUCINATION GUARDRAIL:
#  This returns MOCK hardcoded data. We are NOT building a web scraper for
#  Myntra or any affiliate platform. Replace with real affiliate API later.
# ============================================================================

def get_affiliate_recommendation(item_type: str, style_vibe: str) -> dict:
    """
    ┌──────────────────────────────────────────────────────────────────────┐
    │  MOCK: Affiliate Recommendation Engine                              │
    │  ──────────────────────────────────────────────────────────────────  │
    │  Returns a hardcoded product recommendation with affiliate link,   │
    │  price, and bank offer for the "gap item" — i.e., a clothing item │
    │  the user doesn't own but the AI recommends.                        │
    │                                                                    │
    │  In production, this would call:                                    │
    │   • Myntra Affiliate API                                            │
    │   • Amazon Associates API                                           │
    │   • Ajio Partner API                                                 │
    │  to return real products with real affiliate tracking links.         │
    └──────────────────────────────────────────────────────────────────────┘
    """
    # Mock product database keyed by item_type
    mock_products = {
        "sneakers": {
            "product_name": "White Chunky Platform Sneakers",
            "brand": "HRX by Hrithik Roshan",
            "price": 2799,
            "original_price": 3999,
            "discount_pct": 30,
            "currency": "INR",
            "affiliate_url": "https://www.myntra.com/sneakers/hrx/white-chunky?aff=mynarrative",
            "image_url": "https://assets.myntassets.com/w_412,q_60,dpr_2,fl_progressive/assets/images/sneakers_mock.jpg",
            "bank_offer": "Use HDFC Credit Card to save ₹500 instantly",
            "platform": "Myntra",
        },
        "blazer": {
            "product_name": "Slim Fit Structured Blazer — Navy",
            "brand": "Allen Solly",
            "price": 4499,
            "original_price": 6999,
            "discount_pct": 36,
            "currency": "INR",
            "affiliate_url": "https://www.myntra.com/blazers/allen-solly/navy?aff=mynarrative",
            "image_url": "https://assets.myntassets.com/w_412,q_60,dpr_2,fl_progressive/assets/images/blazer_mock.jpg",
            "bank_offer": "Use Axis Bank card to get 10% cashback (up to ₹300)",
            "platform": "Myntra",
        },
        "ethnic_kurta": {
            "product_name": "Silk Blend Nehru Collar Kurta — Ivory",
            "brand": "Manyavar",
            "price": 3299,
            "original_price": 4999,
            "discount_pct": 34,
            "currency": "INR",
            "affiliate_url": "https://www.myntra.com/kurtas/manyavar/silk-ivory?aff=mynarrative",
            "image_url": "https://assets.myntassets.com/w_412,q_60,dpr_2,fl_progressive/assets/images/kurta_mock.jpg",
            "bank_offer": "Use HDFC Credit Card to save ₹500 instantly",
            "platform": "Myntra",
        },
        "watch": {
            "product_name": "Fossil Minimalist Chronograph — Rose Gold",
            "brand": "Fossil",
            "price": 8995,
            "original_price": 12995,
            "discount_pct": 31,
            "currency": "INR",
            "affiliate_url": "https://www.myntra.com/watches/fossil/rose-gold?aff=mynarrative",
            "image_url": "https://assets.myntassets.com/w_412,q_60,dpr_2,fl_progressive/assets/images/watch_mock.jpg",
            "bank_offer": "No-cost EMI available on all cards",
            "platform": "Myntra",
        },
        "sunglasses": {
            "product_name": "Ray-Ban Aviator Classic — Gold",
            "brand": "Ray-Ban",
            "price": 6490,
            "original_price": 8990,
            "discount_pct": 28,
            "currency": "INR",
            "affiliate_url": "https://www.myntra.com/sunglasses/ray-ban/aviator?aff=mynarrative",
            "image_url": "https://assets.myntassets.com/w_412,q_60,dpr_2,fl_progressive/assets/images/sunglasses_mock.jpg",
            "bank_offer": "Use ICICI card for extra 5% off",
            "platform": "Myntra",
        },
    }

    # Default to sneakers if item_type not found
    product = mock_products.get(item_type.lower(), mock_products["sneakers"])

    # Add vibe-context to the recommendation
    product["style_context"] = f"Recommended to complete your '{style_vibe}' look"
    product["gap_reason"] = f"This {item_type} was featured in your AI-generated editorial but isn't in your closet yet."

    return product


def identify_gap_items(wardrobe_items: list, generated_outfit_items: list) -> list:
    """
    Compares the user's existing wardrobe with the items shown in the
    AI-generated outfit. Returns items the user is MISSING (gap items).

    These gap items become affiliate upsell opportunities.
    """
    # Extract user's item categories (slots they already own)
    owned_slots = {item.get("slot", "").lower() for item in wardrobe_items}

    # Mock: items that were "generated" in the FLUX image but user doesn't own
    # In production, this would use a Vision API to detect items in the FLUX output
    generated_items = [
        {"slot": "sneakers", "item_type": "sneakers", "description": "White Chunky Sneakers", "is_owned": False},
        {"slot": "sunglasses", "item_type": "sunglasses", "description": "Aviator Sunglasses", "is_owned": False},
    ]

    # Mark items that user already has
    for item in generated_items:
        if item["slot"] in owned_slots:
            item["is_owned"] = True

    # Return only gap items (not owned)
    gap_items = [item for item in generated_items if not item["is_owned"]]
    return gap_items


# ============================================================================
#  SECTION 4: GAMIFICATION DATA (Mascot Cards + Style Graph)
# ============================================================================

def get_gamification_state(user_id: str) -> dict:
    """
    Returns the gamification state for the user:
    - Mascot cards collected
    - Style graph progress
    - Rewards unlocked

    In production, this would query the database. Currently returns mock data.
    """
    return {
        "mascot_quest": {
            "cards_collected": 1,
            "cards_total": 5,
            "current_card": {
                "name": "The Street Style Phantom",
                "rarity": "Common",
                "unlock_method": "Complete your first AI editorial",
            },
            "next_card": {
                "name": "The Boardroom Shapeshifter",
                "rarity": "Rare",
                "unlock_method": "Checkout any recommended item",
            },
            "checkout_cta": "Checkout to unlock your next physical Mascot Card! 🎴",
        },
        "style_graph": {
            "photos_uploaded": 1,
            "photos_required": 4,       # Need 4 total (3 more after first)
            "progress_pct": 25,
            "reward_unlocked": False,
            "reward_description": "Upload 3 more OOTD photos to train your AI and unlock 5% Store Credit 🎁",
            "credit_amount": "5%",
            "credit_type": "Store Credit",
        },
    }


# ============================================================================
#  SECTION 5: MAIN REQUEST HANDLER (Vercel Serverless Function)
# ============================================================================

class handler(BaseHTTPRequestHandler):
    """
    Vercel Serverless Function entry point.

    POST /api/stylist_pipeline
    ──────────────────────────
    Handles the full AI Stylist pipeline orchestration.

    Request Body:
    {
        "action": "full_pipeline" | "get_vibes" | "get_occasions" | "get_gamification",
        "user_id": "shopify_customer_id",
        "occasion": "date_night" | "office" | "sangeet" | "airport_look",
        "vibe_id": "caffeine_survivor" | "sarcastic_rizzler" | "main_character" | "quiet_luxury",
        "user_image": "base64_encoded_image_string"
    }
    """

    def _cors_headers(self):
        """Set CORS headers for cross-origin requests."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS, GET")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Max-Age", "86400")

    def _respond(self, status: int, data: dict):
        """Send a JSON response with CORS headers."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self._cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode("utf-8"))

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(200)
        self._cors_headers()
        self.end_headers()

    def do_GET(self):
        """Health check and metadata endpoint."""
        self._respond(200, {
            "service": "My Narrative AI Stylist Pipeline",
            "version": "2.0.0",
            "status": "operational",
            "available_vibes": list(VIBE_PRESETS.keys()),
            "available_occasions": list(OCCASION_PRESETS.keys()),
        })

    def do_POST(self):
        """
        ┌──────────────────────────────────────────────────────────────────┐
        │  MAIN PIPELINE ORCHESTRATOR                                     │
        │                                                                  │
        │  Flow:                                                           │
        │  1. Parse request (occasion, vibe, user image)                  │
        │  2. PARALLEL: extract_biometrics() + segment_wardrobe()         │
        │  3. SEQUENTIAL: build_flux_prompt() → generate_flux() → swap()  │
        │  4. PARALLEL: save_to_ghost_closet() + get_affiliates()         │
        │  5. Return complete response to frontend                        │
        └──────────────────────────────────────────────────────────────────┘
        """
        try:
            # ─── PARSE REQUEST ───
            content_length = int(self.headers.get("Content-Length", 0))
            
            # Check for oversized payload (Vercel Hobby plan limit: 4.5 MB)
            MAX_BODY_SIZE = 4.5 * 1024 * 1024  # 4.5 MB in bytes
            if content_length > MAX_BODY_SIZE:
                self._respond(413, {
                    "success": False,
                    "error": "Payload too large. Image size exceeds Vercel Hobby plan limit (4.5 MB). Please use a smaller image.",
                })
                return
            
            body = b''
            if content_length > 0:
                body = self.rfile.read(content_length)
            
            if not body:
                self._respond(400, {
                    "success": False,
                    "error": "Empty request body. Please provide valid JSON data.",
                })
                return
            
            try:
                body = json.loads(body)
            except json.JSONDecodeError:
                self._respond(400, {"success": False, "error": "Invalid JSON in request body"})
                return

            action = body.get("action", "full_pipeline")

            # ─────────────────────────────────────────────────────────
            # ACTION: Return available vibes for Step 1B
            # ─────────────────────────────────────────────────────────
            if action == "get_vibes":
                vibes = []
                for vid, vdata in VIBE_PRESETS.items():
                    vibes.append({"id": vid, "label": vdata["label"], "persona": vdata["style_persona"]})
                self._respond(200, {"success": True, "vibes": vibes})
                return

            # ─────────────────────────────────────────────────────────
            # ACTION: Return available occasions for Step 1A
            # ─────────────────────────────────────────────────────────
            if action == "get_occasions":
                occasions = []
                for oid, odata in OCCASION_PRESETS.items():
                    occasions.append({"id": oid, "label": odata["label"], "direction": odata["style_direction"]})
                self._respond(200, {"success": True, "occasions": occasions})
                return

            # ─────────────────────────────────────────────────────────
            # ACTION: Return gamification state for Step 5
            # ─────────────────────────────────────────────────────────
            if action == "get_gamification":
                user_id = body.get("user_id", "anonymous")
                gamification = get_gamification_state(user_id)
                self._respond(200, {"success": True, "gamification": gamification})
                return

            # ─────────────────────────────────────────────────────────
            # ACTION: FULL PIPELINE (Steps 2 → 3 → 4 → 5)
            # ─────────────────────────────────────────────────────────
            if action == "full_pipeline":
                pipeline_start = time.time()

                # Validate required fields
                user_id = body.get("user_id")
                occasion = body.get("occasion")
                vibe_id = body.get("vibe_id")
                user_image = body.get("user_image")  # Base64 encoded

                if not all([user_id, occasion, vibe_id, user_image]):
                    self._respond(400, {
                        "success": False,
                        "error": "Missing required fields: user_id, occasion, vibe_id, user_image",
                        "required": ["user_id", "occasion", "vibe_id", "user_image"],
                    })
                    return

                # ═══════════════════════════════════════════════════════
                # STEP 2: PARALLEL — Biometrics + Wardrobe Segmentation
                # ═══════════════════════════════════════════════════════
                print("━" * 60)
                print("🚀 STEP 2: Running parallel extraction pipeline...")
                print("━" * 60)

                biometrics_result = None
                wardrobe_result = None

                with ThreadPoolExecutor(max_workers=2) as executor:
                    # Submit both tasks in parallel
                    biometrics_future = executor.submit(extract_biometrics, user_image)
                    wardrobe_future = executor.submit(segment_wardrobe, user_image)

                    # Collect results
                    biometrics_result = biometrics_future.result(timeout=60)
                    wardrobe_result = wardrobe_future.result(timeout=60)

                print(f"✅ Biometrics: MST={biometrics_result.get('monk_skin_tone')}, "
                      f"Body={biometrics_result.get('body_type')}")
                print(f"✅ Wardrobe: {wardrobe_result.get('items_detected')} items detected")

                # ═══════════════════════════════════════════════════════
                # STEP 3A: Build the FLUX prompt
                # ═══════════════════════════════════════════════════════
                print("\n🎨 STEP 3A: Building FLUX prompt...")
                flux_prompt = build_flux_prompt(
                    biometrics=biometrics_result,
                    wardrobe=wardrobe_result,
                    occasion=occasion,
                    vibe_id=vibe_id,
                )

                # ═══════════════════════════════════════════════════════
                # STEP 3B: Generate FLUX image (SEQUENTIAL — must finish
                #          before face swap can begin)
                # ═══════════════════════════════════════════════════════
                print("\n🖼️  STEP 3B: Generating FLUX editorial image...")
                flux_image_url = generate_flux_image(flux_prompt)

                # ═══════════════════════════════════════════════════════
                # STEP 3C: Apply Face Swap (SEQUENTIAL — uses FLUX output)
                # ═══════════════════════════════════════════════════════
                print("\n🔄 STEP 3C: Applying face swap...")
                final_image_url = apply_face_swap(
                    flux_image_url=flux_image_url,
                    user_face_image=user_image,  # Original uploaded photo
                )

                # ═══════════════════════════════════════════════════════
                # STEP 4: Save to Ghost Closet + Get Affiliate Upsells
                # (These can run in parallel with each other)
                # ═══════════════════════════════════════════════════════
                print("\n💾 STEP 4: Saving to Ghost Closet + generating affiliate recommendations...")

                # Save wardrobe items to vector DB
                closet_result = save_to_ghost_closet(
                    user_id=user_id,
                    wardrobe_items=wardrobe_result.get("items", []),
                )

                # Identify gap items (what user needs to buy)
                gap_items = identify_gap_items(
                    wardrobe_items=wardrobe_result.get("items", []),
                    generated_outfit_items=[],  # Would come from FLUX output analysis
                )

                # Get affiliate recommendations for each gap item
                affiliate_recommendations = []
                for gap in gap_items:
                    rec = get_affiliate_recommendation(
                        item_type=gap["item_type"],
                        style_vibe=VIBE_PRESETS.get(vibe_id, {}).get("label", ""),
                    )
                    rec["gap_item"] = gap
                    affiliate_recommendations.append(rec)

                # ═══════════════════════════════════════════════════════
                # STEP 5: Gamification state
                # ═══════════════════════════════════════════════════════
                print("\n🎮 STEP 5: Fetching gamification state...")
                gamification = get_gamification_state(user_id)

                # ─── Get color theory data for the tooltip ───
                mst_value = biometrics_result.get("monk_skin_tone", 5)
                color_theory = MST_COLOR_THEORY.get(mst_value, MST_COLOR_THEORY[5])

                # ═══════════════════════════════════════════════════════
                # ASSEMBLE FINAL RESPONSE
                # ═══════════════════════════════════════════════════════
                pipeline_duration = round(time.time() - pipeline_start, 2)
                print(f"\n{'━' * 60}")
                print(f"✅ PIPELINE COMPLETE in {pipeline_duration}s")
                print(f"{'━' * 60}")

                response = {
                    "success": True,
                    "pipeline_duration_seconds": pipeline_duration,

                    # Step 2 results: Biometric + Wardrobe data
                    "biometrics": {
                        "monk_skin_tone": mst_value,
                        "mst_label": MST_LABELS.get(mst_value, "Medium"),
                        "body_type": biometrics_result.get("body_type"),
                        "gender_presentation": biometrics_result.get("gender_presentation"),
                    },
                    "wardrobe": {
                        "items_detected": wardrobe_result.get("items_detected", 0),
                        "items": wardrobe_result.get("items", []),
                    },
                    "ghost_closet": closet_result,

                    # Step 3 results: Generated editorial image
                    "editorial": {
                        "flux_prompt": flux_prompt,
                        "flux_image_url": flux_image_url,
                        "final_image_url": final_image_url,  # After face swap
                        "occasion": OCCASION_PRESETS.get(occasion, {}),
                        "vibe": VIBE_PRESETS.get(vibe_id, {}),
                    },

                    # Step 4 results: Color theory + Affiliate upsells
                    "color_theory": {
                        "mst_value": mst_value,
                        "best_colors": color_theory["best_colors"],
                        "avoid_colors": color_theory["avoid"],
                        "undertone_note": color_theory["undertone_note"],
                        "tooltip_text": (
                            f"Based on your Monk Skin Tone ({MST_LABELS.get(mst_value)}), "
                            f"{color_theory['undertone_note']} "
                            f"Best colors: {', '.join(color_theory['best_colors'])}."
                        ),
                    },
                    "affiliate_upsells": affiliate_recommendations,
                    "outfit_completion_pct": max(0, 100 - (len(gap_items) * 10)),

                    # Step 5 results: Gamification
                    "gamification": gamification,
                }

                self._respond(200, response)
                return

            # Unknown action
            self._respond(400, {
                "success": False,
                "error": f"Unknown action: '{action}'. Valid: full_pipeline, get_vibes, get_occasions, get_gamification",
            })

        except json.JSONDecodeError:
            self._respond(400, {"success": False, "error": "Invalid JSON in request body"})
        except Exception as e:
            print(f"❌ Pipeline error: {e}")
            error_msg = str(e)

            # Friendly error messages for known issues
            if "402" in error_msg or "credit" in error_msg.lower():
                error_msg = "💳 AI service credits exhausted. Please add credits at replicate.com/account/billing"
            elif "401" in error_msg or "unauthorized" in error_msg.lower():
                error_msg = "🔑 Invalid API token. Check your Vercel environment variables."
            elif "timeout" in error_msg.lower():
                error_msg = "⏱️ Pipeline timed out. The AI models are taking too long. Please try again."

            self._respond(500, {"success": False, "error": error_msg})
