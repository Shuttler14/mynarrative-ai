"""
Outfit Assembly — Anchor item analysis & category gap detection.
Determines what's missing from an outfit and retrieves complementary items.
"""
from __future__ import annotations
from typing import Optional

from .knowledge_graph import get_knowledge_graph, Category, PROPORTION_RULES, LENGTH_RULES


# Default outfit templates by occasion
OUTFIT_TEMPLATES = {
    "casual": {
        "required": [Category.TOP, Category.BOTTOM, Category.FOOTWEAR],
        "optional": [Category.ACCESSORY, Category.BAG],
        "max_items": 5,
    },
    "business_formal": {
        "required": [Category.TOP, Category.BOTTOM, Category.FOOTWEAR],
        "optional": [Category.OUTERWEAR, Category.ACCESSORY],
        "max_items": 6,
    },
    "business_casual": {
        "required": [Category.TOP, Category.BOTTOM, Category.FOOTWEAR],
        "optional": [Category.OUTERWEAR, Category.ACCESSORY],
        "max_items": 5,
    },
    "cocktail": {
        "required": [Category.DRESS],
        "optional": [Category.FOOTWEAR, Category.BAG, Category.JEWELRY],
        "max_items": 5,
    },
    "black_tie": {
        "required": [Category.DRESS],
        "optional": [Category.FOOTWEAR, Category.BAG, Category.JEWELRY, Category.OUTERWEAR],
        "max_items": 5,
    },
    "beach": {
        "required": [Category.TOP, Category.BOTTOM],
        "optional": [Category.FOOTWEAR, Category.ACCESSORY, Category.BAG],
        "max_items": 4,
    },
    "date_night": {
        "required": [Category.DRESS],
        "optional": [Category.FOOTWEAR, Category.BAG, Category.JEWELRY, Category.OUTERWEAR],
        "max_items": 6,
    },
    "streetwear": {
        "required": [Category.TOP, Category.BOTTOM, Category.FOOTWEAR],
        "optional": [Category.OUTERWEAR, Category.ACCESSORY, Category.BAG],
        "max_items": 6,
    },
    "wedding_guest": {
        "required": [Category.DRESS],
        "optional": [Category.FOOTWEAR, Category.BAG, Category.JEWELRY, Category.OUTERWEAR],
        "max_items": 6,
    },
    "brunch": {
        "required": [Category.TOP, Category.BOTTOM, Category.FOOTWEAR],
        "optional": [Category.ACCESSORY, Category.BAG],
        "max_items": 5,
    },
    "workout": {
        "required": [Category.TOP, Category.BOTTOM, Category.FOOTWEAR],
        "optional": [Category.ACCESSORY],
        "max_items": 4,
    },
    "festival": {
        "required": [Category.TOP, Category.BOTTOM, Category.FOOTWEAR],
        "optional": [Category.ACCESSORY, Category.BAG, Category.JEWELRY],
        "max_items": 6,
    },
    "minimalist": {
        "required": [Category.TOP, Category.BOTTOM, Category.FOOTWEAR],
        "optional": [Category.ACCESSORY],
        "max_items": 4,
    },
    "gala": {
        "required": [Category.DRESS],
        "optional": [Category.FOOTWEAR, Category.BAG, Category.JEWELRY],
        "max_items": 5,
    },
    "night_out": {
        "required": [Category.DRESS],
        "optional": [Category.FOOTWEAR, Category.BAG, Category.JEWELRY, Category.OUTERWEAR],
        "max_items": 6,
    },
}

# Category-specific fit recommendations
FIT_RULES = {
    "top": {
        "slim": {"complement_bottom": ["relaxed", "wide", "straight"], "avoid_bottom": ["skinny"]},
        "fitted": {"complement_bottom": ["relaxed", "straight"], "avoid_bottom": []},
        "oversized": {"complement_bottom": ["fitted", "slim", "skinny"], "avoid_bottom": ["oversized"]},
        "relaxed": {"complement_bottom": ["fitted", "slim"], "avoid_bottom": ["relaxed"]},
    },
    "bottom": {
        "slim": {"complement_top": ["relaxed", "oversized"], "avoid_top": ["slim"]},
        "skinny": {"complement_top": ["oversized", "relaxed", "long"], "avoid_top": ["slim", "crop"]},
        "straight": {"complement_top": ["fitted", "relaxed"], "avoid_top": []},
        "wide": {"complement_top": ["fitted", "slim", "crop"], "avoid_top": ["wide", "oversized"]},
        "relaxed": {"complement_top": ["fitted", "slim"], "avoid_top": ["relaxed"]},
    },
}

# Length pairing rules
LENGTH_PAIRINGS = {
    "crop_top": ["high_waist", "maxi", "wide"],
    "regular_top": ["any"],
    "long_top": ["slim", "fitted"],
    "mini_bottom": ["regular", "long"],
    "maxi_bottom": ["crop", "fitted"],
    "wide_bottom": ["fitted", "crop"],
}


class OutfitSlot:
    """Represents a slot in an outfit that needs to be filled."""

    def __init__(self, category: Category, priority: int = 1, required: bool = True):
        self.category = category
        self.priority = priority
        self.required = required
        self.filled_by: Optional[dict] = None
        self.complement_constraints: dict = {}

    def fill(self, product: dict):
        self.filled_by = product

    @property
    def is_filled(self) -> bool:
        return self.filled_by is not None

    def __repr__(self):
        item = self.filled_by.get("title", "empty") if self.filled_by else "empty"
        return f"Slot({self.category.value}: {item})"


class OutfitBuilder:
    """Builds a complete outfit from an anchor item or from scratch."""

    def __init__(self, occasion: str = "casual", style: str = "classic"):
        self.kg = get_knowledge_graph()
        self.occasion = occasion
        self.style = style
        self.template = OUTFIT_TEMPLATES.get(occasion, OUTFIT_TEMPLATES["casual"])
        self.slots: list[OutfitSlot] = []
        self._build_slots()

    def _build_slots(self):
        """Initialize outfit slots based on occasion template."""
        for cat in self.template["required"]:
            self.slots.append(OutfitSlot(category=cat, priority=1, required=True))
        for cat in self.template.get("optional", []):
            self.slots.append(OutfitSlot(category=cat, priority=2, required=False))

    def set_anchor(self, anchor: dict) -> dict:
        """
        Set an anchor item and determine what's missing.
        Returns: {anchor_slot, missing_slots, proportion_hints}
        """
        anchor_category = anchor.get("category", "").lower()
        anchor_fit = anchor.get("metadata", {}).get("fit", "regular")
        anchor_color = anchor.get("color", "")
        anchor_material = anchor.get("material", "")

        # Find the slot for this category
        anchor_slot = None
        for slot in self.slots:
            if slot.category.value == anchor_category:
                anchor_slot = slot
                break

        # If anchor doesn't fit any slot, add it as a new slot
        if not anchor_slot:
            try:
                cat = Category(anchor_category)
                anchor_slot = OutfitSlot(category=cat, priority=1, required=True)
                self.slots.insert(0, anchor_slot)
            except ValueError:
                pass

        if anchor_slot:
            anchor_slot.fill(anchor)

        # Get proportion advice
        proportion_hints = self.kg.get_proportion_advice(anchor_fit, anchor_category)

        # Get compatible categories
        compatible = self.kg.get_compatible_categories(anchor_category)

        # Get complementary colors
        comp_colors = self.kg.get_complementary_colors(anchor_color) if anchor_color else set()

        # Determine missing slots
        missing = [s for s in self.slots if not s.is_filled and s.category in compatible]

        # Set constraints on missing slots based on anchor
        for slot in missing:
            fit_key = f"{anchor_fit}_{slot.category.value}"
            if fit_key in FIT_RULES:
                fit_rule = FIT_RULES[fit_key]
                slot.complement_constraints["preferred_fit"] = fit_rule.get(f"complement_{slot.category.value}", [])
                slot.complement_constraints["avoid_fit"] = fit_rule.get(f"avoid_{slot.category.value}", [])
            if comp_colors:
                slot.complement_constraints["preferred_colors"] = list(comp_colors)[:3]
            if anchor_material:
                slot.complement_constraints["compatible_materials"] = list(
                    self.kg.MATERIAL_COMPATIBILITY.get(anchor_material, {}).get("pairs_with", set())
                )

        return {
            "anchor": anchor,
            "anchor_slot": anchor_slot,
            "missing_slots": missing,
            "proportion_hints": proportion_hints,
            "compatible_categories": [c.value for c in compatible],
            "complementary_colors": list(comp_colors)[:5],
        }

    def get_search_queries_for_slot(self, slot: OutfitSlot) -> dict:
        """Generate search parameters for finding products to fill a slot."""
        queries = {
            "category": slot.category.value,
            "preferred_colors": slot.complement_constraints.get("preferred_colors", []),
            "preferred_fit": slot.complement_constraints.get("preferred_fit", []),
            "avoid_fit": slot.complement_constraints.get("avoid_fit", []),
            "compatible_materials": slot.complement_constraints.get("compatible_materials", []),
        }
        return queries

    def assemble_outfit(self, products: list[dict]) -> list[dict]:
        """
        Given a list of products, assign them to slots.
        Returns: ordered list of products in the outfit.
        """
        unfilled = [s for s in self.slots if not s.is_filled]
        available = list(products)

        for slot in unfilled:
            best_product = None
            best_score = -1

            for product in available:
                score = self._score_product_for_slot(product, slot)
                if score > best_score:
                    best_score = score
                    best_product = product

            if best_product:
                slot.fill(best_product)
                available.remove(best_product)

        # Return filled slots in order
        return [slot.filled_by for slot in self.slots if slot.is_filled and slot.filled_by]

    def _score_product_for_slot(self, product: dict, slot: OutfitSlot) -> float:
        """Score how well a product fills a specific outfit slot."""
        score = 0.0

        # Category match (essential)
        if product.get("category", "").lower() == slot.category.value:
            score += 0.4
        else:
            return 0.0  # Wrong category = instant reject

        # Color preference
        product_color = product.get("color", "").lower()
        preferred_colors = slot.complement_constraints.get("preferred_colors", [])
        if preferred_colors and product_color in preferred_colors:
            score += 0.25
        elif product_color:
            # Use knowledge graph to score color pair with anchor
            anchor = None
            for s in self.slots:
                if s.is_filled:
                    anchor = s.filled_by
                    break
            if anchor:
                anchor_color = anchor.get("color", "black")
                color_score = self.kg.score_color_pair(anchor_color, product_color)
                score += color_score * 0.25

        # Fit preference
        product_fit = product.get("metadata", {}).get("fit", "regular") if isinstance(product.get("metadata"), dict) else "regular"
        preferred_fit = slot.complement_constraints.get("preferred_fit", [])
        avoid_fit = slot.complement_constraints.get("avoid_fit", [])
        if preferred_fit and product_fit in preferred_fit:
            score += 0.15
        elif avoid_fit and product_fit in avoid_fit:
            score -= 0.1

        # Material compatibility
        product_material = product.get("material", "").lower()
        compatible_materials = slot.complement_constraints.get("compatible_materials", [])
        if compatible_materials and product_material in compatible_materials:
            score += 0.1

        # Style match
        style_profile = self.kg.get_style_profile(self.style)
        if style_profile:
            if product_color in style_profile.get("colors", set()):
                score += 0.1
            try:
                from .knowledge_graph import Pattern
                product_pattern = product.get("tags", [])
                if isinstance(product_pattern, list):
                    for tag in product_pattern:
                        if tag.lower() in [p.value for p in style_profile.get("patterns", [])]:
                            score += 0.05
                            break
            except Exception:
                pass

        return max(0.0, min(1.0, score))

    def get_outfit_summary(self) -> dict:
        """Get a summary of the assembled outfit."""
        filled = [s for s in self.slots if s.is_filled]
        return {
            "occasion": self.occasion,
            "style": self.style,
            "total_items": len(filled),
            "categories": [s.category.value for s in filled],
            "items": [s.filled_by for s in filled if s.filled_by],
            "slots_remaining": len([s for s in self.slots if not s.is_filled]),
        }


def build_outfit_from_anchor(
    anchor: dict,
    occasion: str = "casual",
    style: str = "classic",
    candidate_products: list[dict] = None,
) -> dict:
    """
    High-level function: build a complete outfit from an anchor item.
    Returns: {outfit_items, missing_categories, search_queries, proportion_hints}
    """
    builder = OutfitBuilder(occasion=occasion, style=style)
    analysis = builder.set_anchor(anchor)

    outfit_items = [anchor]
    missing_queries = []

    if candidate_products:
        outfit_items = builder.assemble_outfit(candidate_products)

    for slot in analysis["missing_slots"]:
        query = builder.get_search_queries_for_slot(slot)
        query["slot_category"] = slot.category.value
        query["priority"] = slot.priority
        missing_queries.append(query)

    return {
        "outfit_items": outfit_items,
        "missing_categories": [s.category.value for s in analysis["missing_slots"]],
        "search_queries": missing_queries,
        "proportion_hints": analysis["proportion_hints"],
        "complementary_colors": analysis["complementary_colors"],
        "outfit_summary": builder.get_outfit_summary(),
    }


def build_outfit_from_scratch(
    occasion: str = "casual",
    style: str = "classic",
    candidate_products: list[dict] = None,
) -> dict:
    """
    Build an outfit from scratch (no anchor item).
    Returns: {outfit_items, search_queries}
    """
    builder = OutfitBuilder(occasion=occasion, style=style)

    missing_queries = []
    for slot in builder.slots:
        query = {
            "category": slot.category.value,
            "priority": slot.priority,
            "slot_category": slot.category.value,
        }
        missing_queries.append(query)

    outfit_items = []
    if candidate_products:
        outfit_items = builder.assemble_outfit(candidate_products)

    return {
        "outfit_items": outfit_items,
        "missing_categories": [s.category.value for s in builder.slots],
        "search_queries": missing_queries,
        "outfit_summary": builder.get_outfit_summary(),
    }
