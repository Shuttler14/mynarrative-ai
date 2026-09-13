"""Recommendation handler — generate outfit recommendations."""
import json
import os
import urllib.request

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")


def _sb_request(method, path, payload=None):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    body = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(f"{SUPABASE_URL.rstrip('/')}{path}", data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode() or "null")
    except Exception:
        return None


def _get_text_embedding(text: str) -> list:
    """Generate text embedding using OpenAI."""
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


def _match_brand_products(brand_id: str, query_embedding: list, category: str = "", price_min: float = 0, price_max: float = 999999, limit: int = 6) -> list:
    """Search brand products by embedding similarity."""
    if not query_embedding:
        return []

    payload = {
        "p_brand_id": brand_id,
        "query_embedding": query_embedding,
        "query_category": category or None,
        "query_price_min": price_min if price_min > 0 else None,
        "query_price_max": price_max if price_max < 999999 else None,
        "match_count": min(limit, 20)
    }
    result = _sb_request("POST", "/rest/v1/rpc/match_brand_products", payload)
    return result if isinstance(result, list) else []


def _match_closet_items(user_id: str, query_embedding: list, category: str = "", limit: int = 4) -> list:
    """Search user's closet items by embedding similarity."""
    if not query_embedding or not user_id:
        return []

    payload = {
        "p_user_id": user_id,
        "query_embedding": query_embedding,
        "query_category": category or None,
        "match_count": min(limit, 10)
    }
    result = _sb_request("POST", "/rest/v1/rpc/match_closet_items", payload)
    return result if isinstance(result, list) else []


def _generate_outfit_reasoning(items: list, occasion: str) -> str:
    """Use Gemini to generate reasoning for why items pair well."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return f"Perfect for {occasion}."

    try:
        import openai
        client = openai.OpenAI(api_key=api_key)

        items_desc = "\n".join([f"- {item.get('title', '')} ({item.get('category', '')})" for item in items])

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": f"You are a fashion stylist. Given these items for a {occasion} outfit, write 1-2 sentences explaining why they work together:\n{items_desc}"
            }],
            temperature=0.7,
            max_tokens=100
        )

        return response.choices[0].message.content.strip()
    except Exception:
        return f"Perfect for {occasion}."


def handle_recommend(body: dict) -> dict:
    """Generate outfit recommendations for a user on a brand's site.
    Includes partner brand products via syndicate when brand doesn't cover all categories."""
    brand_id = body.get("brand_id", "")
    user_id = body.get("user_id", "")
    occasion = body.get("occasion", "casual")
    price_tier = body.get("price_tier", "mid")
    include_closet = body.get("include_closet", False)
    outfit_count = min(int(body.get("outfit_count", 3)), 4)

    if not brand_id:
        return {"error": "brand_id required"}

    # Price tier to range mapping
    price_ranges = {
        "value": (0, 1500),
        "budget": (0, 1500),
        "mid": (1500, 3500),
        "premium": (1500, 3500),
        "luxury": (3500, 999999),
        "high": (3500, 999999)
    }
    price_min, price_max = price_ranges.get(price_tier, (0, 999999))

    # Generate query embedding
    query_text = f"{occasion} outfit {price_tier} budget"
    query_embedding = _get_text_embedding(query_text)

    # Search brand products
    brand_products = _match_brand_products(brand_id, query_embedding, price_min=price_min, price_max=price_max, limit=outfit_count * 2)

    # Search partner brand products via syndicate
    partner_products = []
    try:
        from api.syndicate import find_partner_products
        partner_products = find_partner_products(brand_id, occasion=occasion, price_tier=price_tier, limit=outfit_count)
    except Exception as e:
        print(f"⚠️ [syndicate] {e}")

    # Combine brand + partner products
    all_products = brand_products + partner_products

    # Search user's closet if requested
    closet_items = []
    if include_closet and user_id:
        closet_items = _match_closet_items(user_id, query_embedding, limit=outfit_count)

    # Generate outfits (mix brand + partner + closet items)
    outfits = []
    for i in range(outfit_count):
        outfit_items = []

        # Add main brand product (if available)
        if brand_products:
            product_idx = i % len(brand_products)
            product = brand_products[product_idx]
            outfit_items.append({
                "source": "brand_catalog",
                "item_ref_id": str(product.get("id", "")),
                "title": product.get("title", ""),
                "image_url": product.get("image_url", ""),
                "price": float(product.get("price", 0)),
                "reason": "",
                "is_gap_item": False,
                "affiliate_url": "",
                "brand_id": brand_id
            })

        # Add partner product (complementary item)
        if partner_products and i < len(partner_products):
            partner = partner_products[i]
            outfit_items.append({
                "source": "partner_brand",
                "item_ref_id": str(partner.get("id", "")),
                "title": partner.get("title", ""),
                "image_url": partner.get("image_url", ""),
                "price": float(partner.get("price", 0)),
                "reason": f"Pairs perfectly with your {outfit_items[0].get('title', 'outfit')}",
                "is_gap_item": True,
                "affiliate_url": "",
                "brand_id": partner.get("brand_id", ""),
                "host_commission_rate": partner.get("host_commission_rate", 0.07)
            })

        # Add closet items if available
        if closet_items and i < len(closet_items):
            closet_item = closet_items[i]
            outfit_items.append({
                "source": "closet",
                "item_ref_id": str(closet_item.get("id", "")),
                "title": closet_item.get("description", "Your item"),
                "image_url": closet_item.get("image_url", ""),
                "price": 0,
                "reason": "From your closet",
                "is_gap_item": False,
                "affiliate_url": ""
            })

        # Generate reasoning
        reasoning = _generate_outfit_reasoning(outfit_items, occasion)

        # Update reasons
        for item in outfit_items:
            if not item["reason"]:
                item["reason"] = reasoning

        total_price = sum(item.get("price", 0) for item in outfit_items if not item.get("is_gap_item"))

        outfits.append({
            "items": outfit_items,
            "reasoning": reasoning,
            "total_price": total_price,
            "occasion_match_score": 0.85 + (i * 0.03),
            "style_cohesion_score": 0.80 + (i * 0.02),
            "has_partner_items": any(item.get("source") == "partner_brand" for item in outfit_items)
        })

    # Save session
    session = _sb_request("POST", "/rest/v1/recommendation_sessions", {
        "user_id": user_id,
        "brand_id": brand_id,
        "occasion": occasion,
        "price_tier": price_tier,
        "include_closet": include_closet,
        "results": outfits,
        "status": "completed"
    })

    session_id = session[0]["id"] if session and len(session) > 0 else None

    return {
        "session_id": session_id,
        "outfits": outfits,
        "closet_items_used": len(closet_items),
        "brand_products_used": len(brand_products),
        "partner_products_used": len(partner_products)
    }
