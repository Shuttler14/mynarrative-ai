"""
Explainability Module — XAI natural language reasoning generator.
Creates dynamic stylist explanations for why items were chosen.
"""
from __future__ import annotations
import json
import os
import urllib.request
from typing import Optional

from .knowledge_graph import get_knowledge_graph


# ── Reasoning Templates ────────────────────────────────────────────────────

REASONING_TEMPLATES = {
    "color_pairing": [
        "The {color_b} pairs beautifully with your {color_a} using {color_theory} color theory.",
        "We chose {color_b} to complement the {color_a} — a classic {color_theory} combination.",
        "The {color_b} tone creates a harmonious balance with the {color_a} ({color_theory}).",
    ],
    "proportion": [
        "The {fit_b} {cat_b} balances the {fit_a} {cat_a} for a flattering silhouette.",
        "We paired a {fit_b} fit on the {cat_b} to complement the {fit_a} {cat_a}.",
        "This {fit_b} {cat_b} creates the ideal contrast with your {fit_a} {cat_a}.",
    ],
    "occasion_match": [
        "Perfect for {occasion} — the formality level is just right.",
        "This combination works beautifully for a {occasion} setting.",
        "Each piece is appropriately styled for {occasion}.",
    ],
    "material_harmony": [
        "The {material_a} and {material_b} textures complement each other perfectly.",
        "We paired {material_a} with {material_b} for a luxurious tactile experience.",
        "The fabric combination of {material_a} and {material_b} is ideal for {season}.",
    ],
    "budget": [
        "All within your ₹{budget:,.0f} budget — great value without compromising style.",
        "Fits your ₹{budget:,.0f} budget perfectly.",
        "Smart picks that stay within your ₹{budget:,.0f} range.",
    ],
    "style_archetype": [
        "Each piece reflects your {style} aesthetic.",
        "We stayed true to your {style} style with these selections.",
        "These items align with your {style} taste.",
    ],
    "brand_diversity": [
        "Featuring pieces from {brands} for a well-rounded look.",
        "We curated options from {brands} to give you variety.",
    ],
    "body_shape": [
        "The silhouette flatters your {body_shape} body shape.",
        "These proportions are designed to complement your {body_shape} figure.",
    ],
}


def _pick_template(category: str) -> str:
    """Pick a random template from a category."""
    import random
    templates = REASONING_TEMPLATES.get(category, [""])
    return random.choice(templates)


def _classify_color_theory(color_a: str, color_b: str) -> str:
    """Classify the color relationship between two colors."""
    kg = get_knowledge_graph()
    comp = kg.get_complementary_colors(color_a)
    analog = kg.get_analogous_colors(color_a)
    if color_b in comp:
        return "complementary"
    if color_b in analog:
        return "analogous"
    return "harmonious"


def generate_rule_based_reasoning(
    outfit_items: list[dict],
    occasion: str = "casual",
    style: str = "classic",
    budget: dict = None,
    body_shape: str = "",
) -> str:
    """
    Generate a rule-based explanation for the outfit.
    Uses templates and knowledge graph data — no LLM call needed.
    """
    if not outfit_items:
        return "No items to explain."

    kg = get_knowledge_graph()
    parts = []

    # Color reasoning (first two items)
    if len(outfit_items) >= 2:
        item_a = outfit_items[0]
        item_b = outfit_items[1]
        color_a = item_a.get("color", "")
        color_b = item_b.get("color", "")
        if color_a and color_b:
            theory = _classify_color_theory(color_a, color_b)
            template = _pick_template("color_pairing")
            parts.append(template.format(
                color_a=color_a, color_b=color_b, color_theory=theory
            ))

    # Proportion reasoning
    if len(outfit_items) >= 2:
        cat_a = outfit_items[0].get("category", "")
        cat_b = outfit_items[1].get("category", "")
        fit_a = "fitted"
        fit_b = "relaxed"
        if cat_a and cat_b:
            template = _pick_template("proportion")
            parts.append(template.format(
                fit_a=fit_a, fit_b=fit_b, cat_a=cat_a, cat_b=cat_b
            ))

    # Material reasoning
    if len(outfit_items) >= 2:
        mat_a = outfit_items[0].get("material", "")
        mat_b = outfit_items[1].get("material", "")
        if mat_a and mat_b and mat_a != mat_b:
            template = _pick_template("material_harmony")
            parts.append(template.format(
                material_a=mat_a, material_b=mat_b, season="the current season"
            ))

    # Occasion reasoning
    template = _pick_template("occasion_match")
    parts.append(template.format(occasion=occasion.replace("_", " ")))

    # Budget reasoning
    if budget and budget.get("target"):
        template = _pick_template("budget")
        parts.append(template.format(budget=budget["target"]))

    # Style reasoning
    template = _pick_template("style_archetype")
    parts.append(template.format(style=style))

    # Brand diversity
    brands = list(set(item.get("brand", "") for item in outfit_items if item.get("brand")))
    if len(brands) > 1:
        template = _pick_template("brand_diversity")
        parts.append(template.format(brands=" and ".join(brands[:3])))

    # Body shape reasoning
    if body_shape:
        template = _pick_template("body_shape")
        parts.append(template.format(body_shape=body_shape))

    return " ".join(parts)


def generate_llm_reasoning(
    outfit_items: list[dict],
    occasion: str = "casual",
    style: str = "classic",
    budget: dict = None,
    body_shape: str = "",
    user_context: str = "",
) -> str:
    """
    Generate a natural language explanation using GPT-4o-mini.
    Falls back to rule-based if LLM unavailable.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return generate_rule_based_reasoning(outfit_items, occasion, style, budget, body_shape)

    # Build item descriptions
    item_descriptions = []
    for i, item in enumerate(outfit_items, 1):
        desc = f"{i}. {item.get('title', 'Unknown')} — {item.get('category', '')}"
        if item.get("color"):
            desc += f", {item['color']}"
        if item.get("material"):
            desc += f", {item['material']}"
        if item.get("brand"):
            desc += f" by {item['brand']}"
        if item.get("price"):
            desc += f" (₹{float(item['price']):,.0f})"
        item_descriptions.append(desc)

    items_text = "\n".join(item_descriptions)
    budget_text = f"Budget: ₹{budget['target']:,.0f}" if budget and budget.get("target") else "Budget: flexible"

    prompt = f"""You are an expert fashion stylist for My Narrative AI.
Generate a 1-2 sentence explanation for why these items work together as an outfit.
Be specific about color theory, proportions, and occasion appropriateness.
Be concise, warm, and confident — like a personal stylist.

Occasion: {occasion.replace('_', ' ')}
Style: {style}
{budget_text}
{f"Body shape: {body_shape}" if body_shape else ""}
{f"Context: {user_context}" if user_context else ""}

Items:
{items_text}

Output only the explanation, no labels or preamble:"""

    try:
        payload = json.dumps({
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 150,
            "temperature": 0.7,
        }).encode()

        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return generate_rule_based_reasoning(outfit_items, occasion, style, budget, body_shape)


def generate_item_reasoning(product: dict, anchor: dict = None, context: str = "") -> str:
    """Generate a short explanation for a single product recommendation."""
    kg = get_knowledge_graph()
    parts = []

    if anchor:
        anchor_color = anchor.get("color", "")
        product_color = product.get("color", "")
        if anchor_color and product_color:
            theory = _classify_color_theory(anchor_color, product_color)
            parts.append(f"Complements your {anchor.get('category', 'item')} using {theory} color pairing")

    if product.get("material"):
        parts.append(f"Made in {product['material']}")

    if product.get("brand"):
        parts.append(f"by {product['brand']}")

    return " — ".join(parts) if parts else f"Great addition to your outfit"


def generate_outfit_title(outfit_items: list[dict], occasion: str = "") -> str:
    """Generate a catchy title for the outfit."""
    categories = [item.get("category", "") for item in outfit_items if item.get("category")]
    colors = [item.get("color", "") for item in outfit_items if item.get("color")]

    primary_color = max(set(colors), key=colors.count) if colors else ""
    occasion_text = occasion.replace("_", " ").title() if occasion else ""

    if occasion_text:
        return f"{primary_color.title()} {occasion_text} Look" if primary_color else f"{occasion_text} Outfit"
    return f"{primary_color.title()} Ensemble" if primary_color else "Curated Look"
