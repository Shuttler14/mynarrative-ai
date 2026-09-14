"""
Scoring Engine — Gated non-linear scoring pipeline.
Implements the gated pricing function and multi-factor similarity scoring.
"""
from __future__ import annotations
import math
from typing import Optional

from .knowledge_graph import get_knowledge_graph
from .embeddings import compute_similarity, compute_attribute_similarity, extract_attributes


# ── Sigmoid Price Gate ─────────────────────────────────────────────────────

def price_gate_sigmoid(
    price: float,
    anchor_price: float,
    tolerance: float = 0.15,
    steepness: float = 10.0,
) -> float:
    """
    Non-linear sigmoid gating function for price.
    
    - Items at or below anchor: score = 1.0 (no penalty for cheaper)
    - Items within tolerance above anchor: gentle penalty
    - Items beyond tolerance: steep exponential penalty
    
    P(price) = 1.0 if price <= anchor
             = 1 / (1 + e^(k * ((price - anchor) / anchor - tolerance))) otherwise
    """
    if price <= anchor_price:
        return 1.0  # Cheaper or same = full score
    
    overshoot = (price - anchor_price) / max(anchor_price, 1)
    exponent = steepness * (overshoot - tolerance)
    # Clamp to prevent overflow
    exponent = max(-500, min(500, exponent))
    return 1.0 / (1.0 + math.exp(exponent))


def price_gate_asymmetric(
    price: float,
    target_min: float,
    target_max: float,
    tolerance: float = 0.15,
) -> float:
    """
    Asymmetric price gate for budget ranges.
    Items below min: penalty if too cheap (might not match quality expectation)
    Items within range: full score
    Items above max: steep penalty
    """
    if price <= 0:
        return 0.0

    # Below minimum (but not drastically)
    if price < target_min:
        ratio = price / max(target_min, 1)
        if ratio >= 0.5:
            return 0.7 + 0.3 * ratio  # Gentle penalty
        return 0.3 + 0.4 * ratio  # Moderate penalty

    # Within range
    if target_min <= price <= target_max:
        return 1.0

    # Above maximum
    overshoot = (price - target_max) / max(target_max, 1)
    if overshoot <= tolerance:
        return 0.85  # Within tolerance band
    elif overshoot <= 0.3:
        return 0.5
    elif overshoot <= 0.5:
        return 0.2
    return 0.05  # Way over budget


# ── Multi-Factor Scoring ──────────────────────────────────────────────────

# Default weights
DEFAULT_WEIGHTS = {
    "kg_compatibility": 0.30,   # Knowledge Graph hard rules
    "vector_similarity": 0.25,  # Semantic vector similarity
    "style_cohesion": 0.15,     # Style archetype match
    "color_harmony": 0.10,      # Color theory score
    "attribute_match": 0.10,    # Structured attribute similarity
    "price_fit": 0.10,          # Price gate score (applied as multiplier)
}


def score_kg_compatibility(product: dict, occasion: str, style: str) -> float:
    """Score product against Knowledge Graph rules."""
    kg = get_knowledge_graph()
    score = 0.5

    # Category allowed for occasion?
    category = product.get("category", "")
    if category:
        if kg.is_category_allowed(occasion, category):
            score += 0.2
        else:
            score -= 0.3

    # Color allowed for occasion?
    color = product.get("color", "")
    if color:
        if kg.is_color_allowed(occasion, color):
            score += 0.1
        else:
            score -= 0.2

    # Pattern allowed?
    tags = product.get("tags", [])
    if isinstance(tags, list):
        for tag in tags:
            if isinstance(tag, str) and not kg.is_pattern_allowed(occasion, tag):
                score -= 0.1

    # Material preferred for occasion?
    material = product.get("material", "")
    if material:
        rule = kg.get_occasion_rule(occasion)
        if rule and rule.preferred_materials:
            if material in rule.preferred_materials:
                score += 0.1
            else:
                score -= 0.05

    # Style match
    attrs = extract_attributes(product)
    style_score = kg.score_style_match(style, attrs)
    score += style_score * 0.1

    return max(0.0, min(1.0, score))


def score_color_harmony(product: dict, anchor: Optional[dict] = None, palette: list[str] = None) -> float:
    """Score color harmony of a product with an outfit context."""
    kg = get_knowledge_graph()
    product_color = product.get("color", "")

    if not product_color:
        return 0.5

    if anchor:
        anchor_color = anchor.get("color", "")
        if anchor_color:
            return kg.score_color_pair(anchor_color, product_color)

    if palette:
        return kg.score_palette_cohesion([product_color] + palette)

    # No context — use general color versatility
    versatile_colors = {"black", "white", "navy", "beige", "grey", "cream", "camel"}
    if product_color in versatile_colors:
        return 0.8
    return 0.6


def score_style_cohesion(product: dict, style_archetype: str) -> float:
    """Score how well a product fits the user's style archetype."""
    kg = get_knowledge_graph()
    attrs = extract_attributes(product)
    return kg.score_style_match(style_archetype, attrs)


def score_vector_similarity(
    product_embedding: list[float],
    query_embedding: list[float],
) -> float:
    """Score vector similarity between product and query."""
    if not product_embedding or not query_embedding:
        return 0.5
    return compute_similarity(product_embedding, query_embedding)


def score_attribute_match(product: dict, query_attributes: dict) -> float:
    """Score structured attribute similarity."""
    product_attrs = extract_attributes(product)
    return compute_attribute_similarity(product_attrs, query_attributes)


# ── Main Scoring Pipeline ─────────────────────────────────────────────────

def score_product(
    product: dict,
    query_embedding: list[float] = None,
    query_attributes: dict = None,
    anchor: dict = None,
    occasion: str = "casual",
    style: str = "classic",
    budget: dict = None,
    palette_colors: list[str] = None,
    weights: dict = None,
) -> dict:
    """
    Score a single product through the full gated pipeline.
    Returns: {final_score, components, price_gate}
    """
    w = weights or DEFAULT_WEIGHTS

    # Individual component scores
    kg_score = score_kg_compatibility(product, occasion, style)
    vec_score = score_vector_similarity(query_embedding, product.get("embedding_vector", []))
    style_score = score_style_cohesion(product, style)
    color_score = score_color_harmony(product, anchor, palette_colors)
    attr_score = score_attribute_match(product, query_attributes) if query_attributes else 0.5

    # Weighted sum (before price gate)
    weighted_sum = (
        w["kg_compatibility"] * kg_score +
        w["vector_similarity"] * vec_score +
        w["style_cohesion"] * style_score +
        w["color_harmony"] * color_score +
        w["attribute_match"] * attr_score
    )

    # Price gate (sigmoid multiplier)
    price = float(product.get("price", 0))
    price_gate = 1.0
    if budget and price > 0:
        target = budget.get("target", 0)
        tolerance = budget.get("tolerance", 0.15)
        price_gate = price_gate_sigmoid(price, target, tolerance)

    # Final score = price_gate * weighted_sum
    final_score = price_gate * weighted_sum

    return {
        "final_score": round(final_score, 4),
        "price_gate": round(price_gate, 4),
        "components": {
            "kg_compatibility": round(kg_score, 3),
            "vector_similarity": round(vec_score, 3),
            "style_cohesion": round(style_score, 3),
            "color_harmony": round(color_score, 3),
            "attribute_match": round(attr_score, 3),
        },
        "weights": w,
    }


def score_products(
    products: list[dict],
    query_embedding: list[float] = None,
    query_attributes: dict = None,
    anchor: dict = None,
    occasion: str = "casual",
    style: str = "classic",
    budget: dict = None,
    palette_colors: list[str] = None,
    weights: dict = None,
) -> list[dict]:
    """
    Score and rank a list of products.
    Returns: products with scores, sorted by final_score descending.
    """
    scored = []
    for product in products:
        result = score_product(
            product=product,
            query_embedding=query_embedding,
            query_attributes=query_attributes,
            anchor=anchor,
            occasion=occasion,
            style=style,
            budget=budget,
            palette_colors=palette_colors,
            weights=weights,
        )
        product_copy = dict(product)
        product_copy["_score"] = result
        scored.append(product_copy)

    # Sort by final score descending
    scored.sort(key=lambda x: x["_score"]["final_score"], reverse=True)
    return scored


def diversify_results(
    scored_products: list[dict],
    max_per_category: int = 2,
    max_per_color: int = 2,
    top_n: int = 10,
) -> list[dict]:
    """
    Re-rank to ensure diversity in categories and colors.
    Avoids recommending all tops or all same color.
    """
    category_counts: dict[str, int] = {}
    color_counts: dict[str, int] = {}
    diversified = []

    for product in scored_products:
        if len(diversified) >= top_n:
            break

        cat = product.get("category", "unknown")
        color = product.get("color", "unknown")

        cat_count = category_counts.get(cat, 0)
        color_count = color_counts.get(color, 0)

        if cat_count >= max_per_category:
            continue
        if color_count >= max_per_color:
            continue

        diversified.append(product)
        category_counts[cat] = cat_count + 1
        color_counts[color] = color_count + 1

    return diversified
