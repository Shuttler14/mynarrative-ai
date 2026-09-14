"""Closet upload handler — upload garment photo, AI analyzes and categorizes."""
import json
import os
import urllib.request
import base64

def _get_supabase_url():
    return os.environ.get("SUPABASE_URL", "")

def _get_supabase_key():
    return os.environ.get("SUPABASE_KEY", "")


def _sb_request(method, path, payload=None):
    supabase_url = _get_supabase_url()
    supabase_key = _get_supabase_key()
    if not supabase_url or not supabase_key:
        return None
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json"
    }
    body = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(f"{supabase_url.rstrip('/')}{path}", data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode() or "null")
    except Exception:
        return None


def _classify_garment_with_gemini(image_url: str) -> dict:
    """Use Gemini Vision to classify a garment image."""
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {"category": "top", "color": "", "pattern": "solid", "material": "", "description": "Clothing item"}

    try:
        import openai
        client = openai.OpenAI(api_key=api_key)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Analyze this garment image. Return JSON: {\"category\": \"top|bottom|dress|outerwear|accessory|footwear\", \"color_primary\": \"hex code\", \"pattern\": \"solid|striped|floral|plaid|abstract\", \"material\": \"cotton|silk|denim|leather|polyester|other\", \"description\": \"brief description\", \"tags\": [\"tag1\", \"tag2\"]}"},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]
            }],
            response_format={"type": "json_object"},
            temperature=0.3
        )

        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"⚠️ [classify_garment] {e}")
        return {"category": "top", "color": "", "pattern": "solid", "material": "", "description": "Clothing item", "tags": []}


def _generate_embedding(text: str) -> list:
    """Generate embedding vector for text."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return []

    try:
        import openai
        client = openai.OpenAI(api_key=api_key)
        emb = client.embeddings.create(model="text-embedding-3-small", input=text)
        return emb.data[0].embedding if emb and emb.data else []
    except Exception:
        return []


def handle_closet_upload(body: dict, user_id: str) -> dict:
    """Upload a garment photo to user's digital closet."""
    if not user_id:
        return {"error": "user_id required"}

    image_url = body.get("image_url", "")
    image_base64 = body.get("image_base64", "")

    if not image_url and not image_base64:
        return {"error": "image_url or image_base64 required"}

    # Use image_url directly, or construct data URL from base64
    if not image_url and image_base64:
        image_url = f"data:image/jpeg;base64,{image_base64}"

    # Classify garment
    classification = _classify_garment_with_gemini(image_url)

    # Generate embedding
    embedding_text = f"{classification.get('category', 'top')} {classification.get('description', '')} {classification.get('color_primary', '')} {classification.get('material', '')}"
    embedding = _generate_embedding(embedding_text)

    # Save to database
    closet_item = {
        "user_id": user_id,
        "image_url": image_url,
        "category": classification.get("category", "top"),
        "color_primary": classification.get("color_primary", ""),
        "pattern": classification.get("pattern", "solid"),
        "material": classification.get("material", ""),
        "description": classification.get("description", ""),
        "metadata": {
            "ai_detected": True,
            "tags": classification.get("tags", [])
        }
    }

    if embedding:
        closet_item["embedding"] = embedding

    result = _sb_request("POST", "/rest/v1/user_closet_items", closet_item)

    if result and len(result) > 0:
        item = result[0]
        # Update user's closet count
        _sb_request("POST", "/rest/v1/rpc/increment_closet_count", {"p_user_id": user_id})

        return {
            "item_id": item["id"],
            "image_url": item["image_url"],
            "category": item["category"],
            "color": item.get("color_primary", ""),
            "pattern": item.get("pattern", ""),
            "material": item.get("material", ""),
            "description": item.get("description", ""),
            "tags": classification.get("tags", [])
        }

    return {"error": "Failed to save closet item"}
