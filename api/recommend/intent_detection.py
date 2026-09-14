"""
Intent Detection — Budget, occasion, and style archetype inference.
Reads user context to build an implicit preference profile.
"""
from __future__ import annotations
from typing import Optional

# Price tier definitions (INR)
PRICE_TIERS = {
    "value": {"min": 0, "max": 1500, "label": "Value", "tolerance": 0.15},
    "premium": {"min": 1500, "max": 3500, "label": "Premium", "tolerance": 0.15},
    "luxury": {"min": 3500, "max": 999999, "label": "Luxury", "tolerance": 0.20},
}

# Currency conversion (approximate)
CURRENCY_RATES = {
    "INR": 1.0,
    "USD": 83.5,
    "GBP": 105.0,
    "EUR": 90.0,
    "AED": 22.7,
    "AUD": 54.0,
}


def infer_budget(
    price_tier: str = "",
    price_range_min: float = 0,
    price_range_max: float = 0,
    closet_items: list[dict] = None,
    anchor_price: float = 0,
    currency: str = "INR",
) -> dict:
    """
    Infer user's budget with tolerance band.
    Returns: {min, max, target, tolerance, tier}
    """
    tier = PRICE_TIERS.get(price_tier.lower(), PRICE_TIERS["premium"])

    # If explicit price range given, use it
    if price_range_min > 0 and price_range_max > 0:
        # Convert to INR if needed
        rate = CURRENCY_RATES.get(currency, 1.0)
        min_inr = price_range_min * rate
        max_inr = price_range_max * rate
        target = (min_inr + max_inr) / 2
        return {
            "min": min_inr * (1 - tier["tolerance"]),
            "max": max_inr * (1 + tier["tolerance"]),
            "target": target,
            "tolerance": tier["tolerance"],
            "tier": tier["label"],
        }

    # Infer from closet items
    if closet_items:
        prices = []
        for item in closet_items:
            price = float(item.get("price", 0) or item.get("metadata", {}).get("price", 0))
            if price > 0:
                prices.append(price)
        if prices:
            avg_price = sum(prices) / len(prices)
            # Adjust tier based on actual closet prices
            if avg_price > 3500:
                tier = PRICE_TIERS["luxury"]
            elif avg_price > 1500:
                tier = PRICE_TIERS["premium"]
            else:
                tier = PRICE_TIERS["value"]
            target = avg_price
            return {
                "min": target * (1 - tier["tolerance"]),
                "max": target * (1 + tier["tolerance"]),
                "target": target,
                "tolerance": tier["tolerance"],
                "tier": tier["label"],
                "source": "closet_inference",
            }

    # Infer from anchor item price
    if anchor_price > 0:
        if anchor_price > 5000:
            tier = PRICE_TIERS["luxury"]
        elif anchor_price > 2000:
            tier = PRICE_TIERS["premium"]
        else:
            tier = PRICE_TIERS["value"]
        target = anchor_price
        return {
            "min": target * (1 - tier["tolerance"]),
            "max": target * (1 + tier["tolerance"]),
            "target": target,
            "tolerance": tier["tolerance"],
            "tier": tier["label"],
            "source": "anchor_inference",
        }

    # Default to tier-based
    target = (tier["min"] + tier["max"]) / 2
    return {
        "min": tier["min"],
        "max": tier["max"],
        "target": target,
        "tolerance": tier["tolerance"],
        "tier": tier["label"],
    }


def infer_occasion(
    occasion: str = "",
    time_of_day: str = "",
    season: str = "",
    user_context: str = "",
) -> str:
    """
    Infer the occasion from available context.
    Returns normalized occasion string.
    """
    # Direct occasion takes precedence
    if occasion:
        return occasion.lower().strip()

    # Infer from time of day
    time_occasion_map = {
        "morning": "brunch",
        "afternoon": "casual",
        "evening": "date_night",
        "night": "night_out",
    }
    if time_of_day and time_of_day.lower() in time_occasion_map:
        return time_occasion_map[time_of_day.lower()]

    # Infer from context keywords
    if user_context:
        ctx = user_context.lower()
        if any(w in ctx for w in ["interview", "meeting", "office", "work"]):
            return "business_formal"
        if any(w in ctx for w in ["wedding", "reception"]):
            return "wedding_guest"
        if any(w in ctx for w in ["date", "romantic", "dinner"]):
            return "date_night"
        if any(w in ctx for w in ["gym", "workout", "run", "yoga"]):
            return "workout"
        if any(w in ctx for w in ["beach", "pool", "resort", "vacation"]):
            return "beach"
        if any(w in ctx for w in ["party", "night", "club", "bar"]):
            return "night_out"
        if any(w in ctx for w in ["brunch", "lunch", "cafe"]):
            return "brunch"
        if any(w in ctx for w in ["formal", "gala", "ceremony"]):
            return "black_tie"
        if any(w in ctx for w in ["festival", "concert", "music"]):
            return "festival"

    return "casual"  # Default


def infer_style_archetype(
    closet_items: list[dict] = None,
    user_style: str = "",
    vibe: str = "",
) -> str:
    """
    Infer the user's dominant style archetype.
    """
    # Direct style preference
    if user_style:
        style_map = {
            "classic": "classic", "minimalist": "minimalist", "bohemian": "bohemian",
            "boho": "bohemian", "streetwear": "streetwear", "urban": "streetwear",
            "romantic": "romantic", "edgy": "edgy", "preppy": "preppy",
            "athleisure": "athleisure", "athletic": "athleisure",
            "avant-garde": "avant_garde", "relaxed": "relaxed",
        }
        return style_map.get(user_style.lower(), "classic")

    # Vibe to style mapping
    if vibe:
        vibe_map = {
            "clean girl": "minimalist", "old money": "classic", "dark academia": "classic",
            "cottagecore": "bohemian", "y2k": "edgy", "coastal cowgirl": "bohemian",
            "mob wife": "edgy", "quiet luxury": "minimalist", "eclectic": "bohemian",
            "street chic": "streetwear", "romantic": "romantic",
        }
        if vibe.lower() in vibe_map:
            return vibe_map[vibe.lower()]

    # Detect from closet items
    if closet_items:
        from .knowledge_graph import get_knowledge_graph
        kg = get_knowledge_graph()
        return kg.detect_style_archetype(closet_items)

    return "classic"  # Default


def build_user_profile(
    user_id: str = "",
    occasion: str = "",
    price_tier: str = "",
    price_range_min: float = 0,
    price_range_max: float = 0,
    gender: str = "",
    style: str = "",
    vibe: str = "",
    skin_tone: int = 0,
    body_shape: str = "",
    closet_items: list[dict] = None,
    anchor_item: dict = None,
    currency: str = "INR",
    user_context: str = "",
) -> dict:
    """
    Build a complete user intent profile from all available context.
    This is the single source of truth for the recommendation pipeline.
    """
    # Budget inference
    budget = infer_budget(
        price_tier=price_tier,
        price_range_min=price_range_min,
        price_range_max=price_range_max,
        closet_items=closet_items,
        anchor_price=float(anchor_item.get("price", 0)) if anchor_item else 0,
        currency=currency,
    )

    # Occasion inference
    occasion_inferred = infer_occasion(occasion=occasion, user_context=user_context)

    # Style inference
    style_archetype = infer_style_archetype(
        closet_items=closet_items, user_style=style, vibe=vibe
    )

    # Skin tone
    skin_tone_best = []
    if skin_tone:
        from .knowledge_graph import get_knowledge_graph
        kg = get_knowledge_graph()
        tone_info = kg.get_best_colors_for_skin_tone(skin_tone)
        skin_tone_best = tone_info.get("best", [])

    # Gender normalization
    gender_norm = gender.lower() if gender else "unisex"
    if gender_norm not in ("men", "women", "unisex"):
        gender_norm = "unisex"

    # Detect style from closet if not specified
    if not style and closet_items:
        from .knowledge_graph import get_knowledge_graph
        kg = get_knowledge_graph()
        style_archetype = kg.detect_style_archetype(closet_items)

    return {
        "user_id": user_id,
        "budget": budget,
        "occasion": occasion_inferred,
        "style_archetype": style_archetype,
        "gender": gender_norm,
        "skin_tone": skin_tone,
        "skin_tone_best_colors": skin_tone_best,
        "body_shape": body_shape,
        "vibe": vibe,
        "currency": currency,
    }
