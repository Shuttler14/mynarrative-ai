from http.server import BaseHTTPRequestHandler
import json
import os
import base64
import uuid
import hashlib
from datetime import datetime
import logging

# Set up simple logging (Vercel captures stdout)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("physique_analyze")

# Try to import OpenAI (required for vision analysis)
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI package not available.")

# ═════════════════════════════════════════════════════════════════════════════
# PROMPT DEFINITION
# ═════════════════════════════════════════════════════════════════════════════

PHYSIQUE_ANALYSIS_PROMPT = """You are an expert fashion stylist, color analyst, and body measurement specialist with 20+ years of experience. Analyze this photo of a person and extract detailed physical attributes for fashion design and outfit recommendation.

Analyze the following aspects in detail:

## 1. SKIN TONE ANALYSIS
- MST Scale (1-10): Use Monk Skin Tone scale where 1=Porcelain, 6=Warm Tan, 10=Ebony
- Undertone: cool, warm, neutral, olive, golden, rose
- Surface tone: light, medium, dark
- Skin clarity: clear, slight texture, textured

## 2. BODY METRICS
- Body type: ectomorph, mesomorph, endomorph, rectangle, triangle_pear, inverted_triangle, hourglass, oval_apple, diamond, athletic, petite, tall, plus_size
- Fitness level: very_lean, athletic, fit, average, curvy, plus_size, bodybuilder
- Estimated height: (estimated cm if possible)
- Body composition: lean, average, curvy, muscular
- Posture: excellent, good, slight_kyphosis, rounded_shoulders, anterior_tilt
- Proportions:
  - Shoulder width: narrow, average, broad
  - Neck length: short, average, long

## 3. FACIAL ANALYSIS
- Face shape: oval, round, square, rectangle, heart, diamond, triangle, inverted_triangle, oblong
- Eye color: dark_brown, light_brown, hazel, amber, green, blue, grey

## 4. HAIR ANALYSIS
- Hair color: black, dark_brown, medium_brown, light_brown, chestnut, auburn, red, strawberry_blonde, blonde, platinum_blonde, grey, white, dyed, unknown
- Hair texture: straight, wavy, curly, coily, kinky
- Hair style: short_crop, buzz_cut, pixie, bob, lob, shoulder_length, long_straight, long_wavy, long_curly, fade, unknown

## 5. OVERALL APPEARANCE
- Gender: male, female, non_binary, unknown
- Age range: 13-19, 20-29, 30-39, 40-49, 50-59, 60+, unknown
- Seasonal color analysis: spring, summer, autumn, winter (if detectable)
- Style archetype: preppy, bohemian, minimalist, classic, trendy, etc.

Return your analysis as a JSON object with this exact structure:

```json
{
  "skin": {
    "mst_scale": 6,
    "undertone": "warm",
    "surface_tone": "medium",
    "clarity": "clear",
    "notes": ""
  },
  "body": {
    "type": "rectangle",
    "fitness_level": "fit",
    "estimated_height_cm": 175,
    "body_composition": "average",
    "muscle_definition": "moderate",
    "posture": "good",
    "shoulder_width": "average",
    "neck_length": "average",
    "torso_length": "average",
    "leg_proportion": "average"
  },
  "face": {
    "shape": "oval",
    "eye_color": "dark_brown",
    "eyebrow_thickness": "medium",
    "jawline_definition": "moderate",
    "distinguishing_features": []
  },
  "hair": {
    "color": "black",
    "texture": "straight",
    "style": "short_crop",
    "length": "short",
    "volume": "average"
  },
  "appearance": {
    "gender": "male",
    "age_range": "20-29",
    "apparent_age": 25,
    "seasonal_color": "winter",
    "style_archetype": "minimalist",
    "grooming_level": "polished"
  },
  "photo_quality": {
    "quality": "good",
    "full_body_visible": true,
    "face_visible": true
  },
  "confidence_scores": {
    "skin_analysis": 0.85,
    "body_metrics": 0.75,
    "facial_analysis": 0.90,
    "hair_analysis": 0.80,
    "appearance": 0.85,
    "overall": 0.83
  }
}
```

Be as precise as possible. Only include values you can confidently determine from the image.
"""

# ═════════════════════════════════════════════════════════════════════════════
# ENGINE LOGIC
# ═════════════════════════════════════════════════════════════════════════════

MST_LABEL_MAP = {
    1: "Porcelain", 2: "Fair", 3: "Light Beige", 4: "Medium Beige",
    5: "Olive", 6: "Warm Tan", 7: "Brown", 8: "Dark Brown",
    9: "Very Dark", 10: "Ebony"
}

def analyze_photo_with_gpt(base64_image: str) -> dict:
    """Run GPT-4o-mini vision analysis on the image encoded as base64."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not OPENAI_AVAILABLE or not api_key:
        raise RuntimeError("OpenAI package not installed or OPENAI_API_KEY environment variable missing.")

    client = OpenAI(api_key=api_key)
    logger.info("Calling GPT-4o-mini vision API...")

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert fashion stylist and body analysis specialist. Always respond with valid JSON only. No markdown, no code fences, no extra text."
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": PHYSIQUE_ANALYSIS_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}",
                                "detail": "low"
                            }
                        }
                    ]
                }
            ],
            max_tokens=4000,
            temperature=0.3
        )

        content = response.choices[0].message.content
        logger.info(f"GPT-4o-mini responded ({len(content)} chars)")
        result = json.loads(content)
        return result

    except Exception as e:
        logger.error(f"GPT-4o-mini API call failed: {e}")
        raise RuntimeError(f"OpenAI API error: {e}")

def format_response(raw_result: dict, photo_id: str, user_id: str) -> dict:
    """Format the raw GPT JSON into the expected frontend structure."""
    
    # Safe extractors with fallbacks
    def safe_int(val, min_v, max_v, default):
        try:
            v = int(val)
            return max(min_v, min(max_v, v))
        except (ValueError, TypeError):
            return default

    # Destructure sections safely
    skin_data = raw_result.get("skin", {})
    body_data = raw_result.get("body", {})
    face_data = raw_result.get("face", {})
    hair_data = raw_result.get("hair", {})
    app_data = raw_result.get("appearance", {})
    conf_data = raw_result.get("confidence_scores", {})
    qual_data = raw_result.get("photo_quality", {})

    mst_scale = safe_int(skin_data.get("mst_scale", 5), 1, 10, 5)

    return {
        "analysis_id": photo_id,
        "user_id": user_id,
        "photo_id": photo_id,
        "status": "complete",
        "timestamp": datetime.utcnow().isoformat(),
        "analysis_source": "gpt-4o-mini",
        
        "skin_tone": {
            "mst_scale": mst_scale,
            "mst_label": MST_LABEL_MAP.get(mst_scale, "Olive"),
            "undertone": skin_data.get("undertone", "neutral"),
            "surface_tone": skin_data.get("surface_tone", "medium"),
            "clarity": skin_data.get("clarity", "clear")
        },
        
        "body_metrics": {
            "body_type": body_data.get("type", "rectangle"),
            "fitness_level": body_data.get("fitness_level", "average"),
            "estimated_height_cm": body_data.get("estimated_height_cm"),
            "estimated_weight_kg": body_data.get("estimated_weight_kg"),
            "muscle_definition": body_data.get("muscle_definition", "minimal"),
            "body_composition": body_data.get("body_composition", "average"),
            "posture": body_data.get("posture", "good"),
            "proportions": {
                "shoulder_width": body_data.get("shoulder_width", "average"),
                "neck_length": body_data.get("neck_length", "average"),
                "torso_length": body_data.get("torso_length", "average"),
                "leg_proportion": body_data.get("leg_proportion", "average")
            }
        },
        
        "facial_analysis": {
            "face_shape": face_data.get("shape", "oval"),
            "eye_color": face_data.get("eye_color", "unknown"),
            "eye_shape": face_data.get("eye_shape", "almond"),
            "eyebrow_thickness": face_data.get("eyebrow_thickness", "medium"),
            "jawline_definition": face_data.get("jawline_definition", "moderate"),
            "distinguishing_features": face_data.get("distinguishing_features", [])
        },
        
        "hair_analysis": {
            "hair_color": hair_data.get("color", "unknown"),
            "hair_texture": hair_data.get("texture", "straight"),
            "hair_style": hair_data.get("style", "unknown"),
            "hair_length": hair_data.get("length", "unknown"),
            "hair_volume": hair_data.get("volume", "average")
        },
        
        "overall_appearance": {
            "gender": app_data.get("gender", "unknown"),
            "age_range": app_data.get("age_range", "unknown"),
            "apparent_age": app_data.get("apparent_age"),
            "style_archetype": app_data.get("style_archetype"),
            "seasonal_color": app_data.get("seasonal_color"),
            "grooming_level": app_data.get("grooming_level", "average")
        },
        
        "confidence_scores": {
            "skin_analysis": float(conf_data.get("skin_analysis", 0.75)),
            "body_metrics": float(conf_data.get("body_metrics", 0.75)),
            "facial_analysis": float(conf_data.get("facial_analysis", 0.75)),
            "hair_analysis": float(conf_data.get("hair_analysis", 0.75)),
            "appearance": float(conf_data.get("appearance", 0.75))
        },
        
        "overall_confidence": float(conf_data.get("overall", 0.75)),
        
        "photo_quality": qual_data.get("quality", "good"),
        "face_visible": bool(qual_data.get("face_visible", True)),
        "full_body_visible": bool(qual_data.get("full_body_visible", True))
    }

# ═════════════════════════════════════════════════════════════════════════════
# VERCEL REQUEST HANDLER
# ═════════════════════════════════════════════════════════════════════════════

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def do_POST(self):
        """Handle analysis request"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                raise ValueError("Empty request body")

            body = json.loads(self.rfile.read(content_length).decode('utf-8'))
            image_b64 = body.get('image_base64')
            user_id = body.get('user_id', f"anon_{uuid.uuid4().hex[:8]}")

            if not image_b64:
                raise ValueError("image_base64 field is required")

            # Clean base64 header if present
            if image_b64.startswith('data:image'):
                image_b64 = image_b64.split(',', 1)[1] if ',' in image_b64 else image_b64

            photo_id = hashlib.md5(f"{datetime.utcnow().isoformat()}_{user_id}".encode()).hexdigest()[:16]

            # 1. Run GPT Analysis
            raw_analysis = analyze_photo_with_gpt(image_b64)

            # 2. Format response to match Shopify frontend expectations
            response_payload = format_response(raw_analysis, photo_id, user_id)

            # 3. Send Success Response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(response_payload).encode('utf-8'))

        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Error in physique_analyze: {error_msg}")
            
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": False,
                "error": error_msg
            }).encode('utf-8'))
