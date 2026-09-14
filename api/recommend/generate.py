"""
Recommendation Generator — Full pipeline orchestrator.
Implements the 7-stage recommendation pipeline:
1. Intent Detection → 2. Inventory Filter → 3. Knowledge Graph →
4. Outfit Assembly + Embeddings → 5. Scoring → 6. Exploration → 7. Explainability
"""
from __future__ import annotations
import json
import os
import sys
import urllib.request
from typing import Optional

# Ensure parent directory is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.recommend.intent_detection import build_user_profile
from api.recommend.inventory_filter import (
    filter_brand_products, filter_closet_items, filter_partner_products,
    get_product_price, check_stock,
)
from api.recommend.knowledge_graph import get_knowledge_graph, Category
from api.recommend.embeddings import (
    generate_product_embedding, generate_query_embedding,
    generate_closet_embedding, extract_attributes, build_enriched_description,
)
from api.recommend.outfit_assembly import (
    OutfitBuilder, build_outfit_from_anchor, build_outfit_from_scratch,
)
from api.recommend.scoring import (
    score_products, diversify_results, score_product,
)
from api.recommend.exploration import (
    allocate_brand_slots, record_impression, select_brand_for_exploration,
)
from api.recommend.explainability import (
    generate_llm_reasoning, generate_rule_based_reasoning,
    generate_item_reasoning, generate_outfit_title,
)

try:
    from api.brand_catalog import search_brand_products
except ImportError:
    search_brand_products = None

# ── Supabase Helper ────────────────────────────────────────────────────────

def _get_supabase_url():
    return os.environ.get("SUPABASE_URL", "")

def _get_supabase_key():
    return os.environ.get("SUPABASE_KEY", "")


def _sb_request(method: str, path: str, payload: dict = None) -> Optional[dict | list]:
    """Raw Supabase REST request."""
    supabase_url = _get_supabase_url()
    supabase_key = _get_supabase_key()
    if not supabase_url or not supabase_key:
        return None
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
    }
    body = json.dumps(payload).encode() if payload else None
    url = f"{supabase_url.rstrip('/')}{path}"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode() or "null"
            return json.loads(raw)
    except Exception:
        return None


def _match_brand_products(
    brand_id: str,
    query_embedding: list[float],
    category: str = "",
    price_min: float = 0,
    price_max: float = 999999,
    match_count: int = 20,
) -> list[dict]:
    """Vector similarity search via Supabase RPC."""
    payload = {
        "query_embedding": json.dumps(query_embedding),
        "p_brand_id": brand_id,
        "p_match_count": match_count,
        "p_category": category or None,
        "p_price_min": price_min,
        "p_price_max": price_max,
    }
    result = _sb_request("POST", "/rest/v1/rpc/match_brand_products", payload)
    return result if isinstance(result, list) else []


def _match_closet_items(
    user_id: str,
    query_embedding: list[float],
    category: str = "",
    match_count: int = 10,
) -> list[dict]:
    """Vector similarity search for closet items."""
    payload = {
        "query_embedding": json.dumps(query_embedding),
        "p_user_id": user_id,
        "p_match_count": match_count,
        "p_category": category or None,
    }
    result = _sb_request("POST", "/rest/v1/rpc/match_closet_items", payload)
    return result if isinstance(result, list) else []


# ── Main Pipeline ──────────────────────────────────────────────────────────

def handle_recommend(body: dict) -> dict:
    """
    Main recommendation endpoint handler.
    
    Expected body:
    {
        "brand_id": "uuid",
        "brand_name": "Zara",
        "user_id": "uuid",
        "occasion": "cocktail",
        "price_tier": "premium",
        "price_range_min": 1500,
        "price_range_max": 3500,
        "gender": "women",
        "style": "classic",
        "vibe": "clean girl",
        "skin_tone": 5,
        "body_shape": "hourglass",
        "include_closet": true,
        "outfit_count": 4,
        "currency": "INR",
        "anchor_item": { ... },
        "user_context": "going to a cocktail party",
    }
    """
    try:
        brand_id = body.get("brand_id", "")
        brand_name = body.get("brand_name", "")
        user_id = body.get("user_id", "")
        occasion = body.get("occasion", "")
        price_tier = body.get("price_tier", "premium")
        price_range_min = float(body.get("price_range_min", 0))
        price_range_max = float(body.get("price_range_max", 0))
        gender = body.get("gender", "")
        style = body.get("style", "")
        vibe = body.get("vibe", "")
        skin_tone = int(body.get("skin_tone", 0))
        body_shape = body.get("body_shape", "")
        include_closet = bool(body.get("include_closet", False))
        outfit_count = min(int(body.get("outfit_count", 4)), 8)
        currency = body.get("currency", "INR")
        anchor_item = body.get("anchor_item")
        user_context = body.get("user_context", "")

        if not brand_id and not brand_name:
            return {"error": "brand_id or brand_name required"}

        kg = get_knowledge_graph()

        # ── Stage 1: Intent Detection ──────────────────────────────────────
        closet_items = []
        if user_id and include_closet:
            closet_items = filter_closet_items(user_id, limit=20)

        profile = build_user_profile(
            user_id=user_id,
            occasion=occasion,
            price_tier=price_tier,
            price_range_min=price_range_min,
            price_range_max=price_range_max,
            gender=gender,
            style=style,
            vibe=vibe,
            skin_tone=skin_tone,
            body_shape=body_shape,
            closet_items=closet_items,
            anchor_item=anchor_item,
            currency=currency,
            user_context=user_context,
        )

        occasion_final = profile["occasion"]
        style_final = profile["style_archetype"]
        budget = profile["budget"]
        gender_final = profile["gender"]

        # ── Stage 2: Inventory Filter ──────────────────────────────────────
        products = filter_brand_products(
            brand_id=brand_id,
            brand_name=brand_name,
            gender=gender_final,
            min_price=budget["min"],
            max_price=budget["max"],
            limit=60,
        )

        if not products:
            # Retry without price filter
            products = filter_brand_products(
                brand_id=brand_id,
                brand_name=brand_name,
                gender=gender_final,
                limit=60,
            )

        # ── Stage 3: Knowledge Graph Pre-filter ────────────────────────────
        kg_filtered = []
        for p in products:
            if not check_stock(p):
                continue
            # Quick KG compatibility check
            cat = p.get("category", "")
            if cat and not kg.is_category_allowed(occasion_final, cat):
                continue
            color = p.get("color", "")
            if color and not kg.is_color_allowed(occasion_final, color):
                continue
            kg_filtered.append(p)

        if not kg_filtered:
            kg_filtered = products  # Fallback: use all products

        # ── Stage 4: Embeddings + Outfit Assembly ──────────────────────────
        # Generate embeddings for all candidates
        for p in kg_filtered:
            emb_result = generate_product_embedding(p)
            p["embedding_vector"] = emb_result["embedding"]
            p["_attributes"] = emb_result["attributes"]

        # Generate query embedding
        query_text = f"{occasion_final} {style_final} outfit for {gender_final}"
        query_embedding = generate_query_embedding(
            query_text, occasion=occasion_final, style=style_final,
            price_tier=budget["tier"]
        )

        # Build outfits
        all_outfits = []

        if anchor_item:
            # Anchor-based outfit building
            anchor_emb = generate_product_embedding(anchor_item)
            anchor_item["embedding_vector"] = anchor_emb["embedding"]
            anchor_item["_attributes"] = anchor_emb["attributes"]

            outfit_result = build_outfit_from_anchor(
                anchor=anchor_item,
                occasion=occasion_final,
                style=style_final,
                candidate_products=kg_filtered,
            )

            # For each missing category, search for best matches
            for query in outfit_result["search_queries"]:
                cat = query.get("slot_category", "")
                cat_products = [p for p in kg_filtered if p.get("category") == cat]
                if not cat_products and cat:
                    # Search with vector similarity
                    cat_embedding = generate_query_embedding(
                        f"{cat} for {occasion_final}",
                        occasion=occasion_final, style=style_final
                    )
                    vector_matches = _match_brand_products(
                        brand_id=brand_id,
                        query_embedding=cat_embedding,
                        category=cat,
                        price_min=budget["min"],
                        price_max=budget["max"],
                        match_count=10,
                    )
                    cat_products = vector_matches

                if cat_products:
                    scored = score_products(
                        cat_products,
                        query_embedding=query_embedding,
                        anchor=anchor_item,
                        occasion=occasion_final,
                        style=style_final,
                        budget=budget,
                    )
                    top = scored[:2]
                    for p in top:
                        record_impression(p.get("brand", brand_name))
                    all_outfits.extend(top)

        else:
            # No anchor — build outfits from scratch
            scored_all = score_products(
                kg_filtered,
                query_embedding=query_embedding,
                occasion=occasion_final,
                style=style_final,
                budget=budget,
            )
            diversified = diversify_results(scored_all, top_n=outfit_count * 3)
            all_outfits = diversified

        # ── Stage 5: Scoring (already done above, results are scored) ──────

        # ── Stage 6: Exploration (B2B partner brand injection) ─────────────
        partner_products = []
        if brand_name:
            partner_products = filter_partner_products(
                host_brand=brand_name,
                gender=gender_final,
                min_price=budget["min"],
                max_price=budget["max"],
                limit=15,
            )

        # Inject exploration items from partner brands
        exploration_items = []
        if partner_products:
            for pp in partner_products:
                emb = generate_product_embedding(pp)
                pp["embedding_vector"] = emb["embedding"]
                pp["_attributes"] = emb["attributes"]
                pp["_is_partner"] = True

            scored_partners = score_products(
                partner_products,
                query_embedding=query_embedding,
                anchor=anchor_item,
                occasion=occasion_final,
                style=style_final,
                budget=budget,
            )
            exploration_items = scored_partners[:3]
            for item in exploration_items:
                record_impression(item.get("brand", ""))

        # ── Stage 7: Outfit Assembly + Explainability ──────────────────────
        # Group items into outfits
        outfits = _assemble_final_outfits(
            primary_items=all_outfits[:outfit_count * 2],
            exploration_items=exploration_items,
            outfit_count=outfit_count,
            occasion=occasion_final,
            style=style_final,
            budget=budget,
            body_shape=body_shape,
            user_context=user_context,
            brand_id=brand_id,
        )

        # Generate reasoning for each outfit
        for outfit in outfits:
            items = outfit.get("items", [])
            reasoning = generate_llm_reasoning(
                outfit_items=items,
                occasion=occasion_final,
                style=style_final,
                budget=budget,
                body_shape=body_shape,
                user_context=user_context,
            )
            outfit["reasoning"] = reasoning
            outfit["title"] = generate_outfit_title(items, occasion_final)

            # Score outfit coherence
            outfit["coherence_score"] = kg.score_outfit_coherence(
                items, occasion_final
            )

        # ── Session Persistence ────────────────────────────────────────────
        session_data = {
            "user_id": user_id,
            "brand_id": brand_id,
            "occasion": occasion_final,
            "style": style_final,
            "budget": budget,
            "outfits": outfits,
            "profile": profile,
        }

        session_id = ""
        if user_id:
            session_result = _sb_request("POST", "/rest/v1/recommendation_sessions", {
                "user_id": user_id,
                "brand_id": brand_id,
                "session_data": session_data,
                "outfit_count": len(outfits),
            })
            if session_result and isinstance(session_result, dict):
                session_id = session_result.get("id", "")

        return {
            "success": True,
            "session_id": session_id,
            "outfits": outfits,
            "count": len(outfits),
            "profile": {
                "occasion": occasion_final,
                "style": style_final,
                "budget_tier": budget["tier"],
                "budget_target": budget["target"],
            },
            "partner_items": len(exploration_items),
        }

    except Exception as e:
        return {"error": str(e)}


def _enrich_items_with_purchase_urls(items: list[dict], brand_id: str = "") -> list[dict]:
    """
    Enrich product items with purchase URLs and price comparison data.
    Looks up products in brand catalog and global inventory for multi-source pricing.
    """
    enriched = []
    for item in items:
        product = dict(item)
        product_id = product.get("id", "")
        title = product.get("title", "")
        brand = product.get("brand", "")
        price = float(product.get("price", 0))

        # Build purchase links from available data
        purchase_links = []

        # 1. Direct product URL from brand_products table
        if product.get("product_url"):
            purchase_links.append({
                "platform": brand or "Brand Store",
                "url": product["product_url"],
                "price": price,
                "is_best": True,
                "delivery": "Brand Direct",
                "rating": None,
            })

        # 2. Affiliate URL if available
        if product.get("affiliate_url") and product["affiliate_url"] != product.get("product_url"):
            purchase_links.append({
                "platform": "Affiliate Partner",
                "url": product["affiliate_url"],
                "price": price,
                "is_best": False,
                "delivery": "Marketplace",
                "rating": None,
            })

        # 3. Try to find on multiple marketplaces via brand catalog search
        if title and not purchase_links and search_brand_products:
            try:
                catalog_results = search_brand_products(
                    brand=brand, limit=5, currency="INR"
                )
                for cp in catalog_results:
                    cp_title = cp.get("title", "").lower()
                    if title.lower()[:15] in cp_title or cp_title[:15] in title.lower():
                        cp_price = float(cp.get("price", 0))
                        purchase_links.append({
                            "platform": cp.get("marketplace_source", "Marketplace"),
                            "url": cp.get("product_url", cp.get("image_url", "")),
                            "price": cp_price,
                            "is_best": False,
                            "delivery": "2-5 days",
                            "rating": cp.get("rating"),
                        })
            except Exception:
                pass

        # 4. If still no links, construct a Shopify product URL from brand domain
        if not purchase_links and brand:
            slug = brand.lower().replace(" ", "-")
            purchase_links.append({
                "platform": brand,
                "url": f"https://{slug}.com",
                "price": price,
                "is_best": True,
                "delivery": "Check store",
                "rating": None,
            })

        # Mark the best price option
        if purchase_links:
            best_link = min(purchase_links, key=lambda x: x.get("price", float("inf")))
            for link in purchase_links:
                link["is_best"] = link == best_link

        product["purchase_links"] = purchase_links
        product["best_price"] = min((l["price"] for l in purchase_links), default=price)
        product["best_platform"] = next(
            (l["platform"] for l in purchase_links if l["is_best"]), brand or ""
        )
        enriched.append(product)

    return enriched


def _assemble_final_outfits(
    primary_items: list[dict],
    exploration_items: list[dict],
    outfit_count: int,
    occasion: str,
    style: str,
    budget: dict,
    body_shape: str,
    user_context: str,
    brand_id: str = "",
) -> list[dict]:
    """Assemble final outfits from scored items."""
    kg = get_knowledge_graph()
    outfits = []

    # Group by category
    by_category: dict[str, list[dict]] = {}
    for item in primary_items:
        cat = item.get("category", "unknown")
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(item)

    # Build outfits by picking one from each category
    categories_needed = ["top", "bottom", "footwear"]
    if occasion in ("cocktail", "black_tie", "date_night", "gala", "wedding_guest"):
        categories_needed = ["dress", "footwear"]

    for i in range(outfit_count):
        outfit_items = []
        seen_brands = set()

        for cat in categories_needed:
            candidates = by_category.get(cat, [])
            # Filter out items already used in this outfit
            used_ids = {item.get("id", "") for item in outfit_items}
            available = [c for c in candidates if c.get("id", "") not in used_ids]

            if available:
                # Pick the best one, trying to diversify brands
                picked = None
                for item in available:
                    if item.get("brand", "") not in seen_brands:
                        picked = item
                        break
                if not picked:
                    picked = available[0]

                outfit_items.append(picked)
                seen_brands.add(picked.get("brand", ""))

                # Remove from pool
                by_category[cat] = [c for c in candidates if c.get("id", "") != picked.get("id", "")]

        # Add exploration item if available
        if exploration_items and i < len(exploration_items):
            exp_item = exploration_items[i]
            if exp_item.get("id", "") not in {item.get("id", "") for item in outfit_items}:
                outfit_items.append(exp_item)

        if outfit_items:
            # Clean up internal fields
            clean_items = []
            for item in outfit_items:
                clean = {k: v for k, v in item.items() if not k.startswith("_")}
                clean_items.append(clean)

            # Enrich with purchase URLs
            clean_items = _enrich_items_with_purchase_urls(clean_items, brand_id)

            outfits.append({
                "items": clean_items,
                "total_price": sum(float(item.get("price", 0)) for item in clean_items),
                "item_count": len(clean_items),
            })

    return outfits
