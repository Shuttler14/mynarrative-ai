"""
Fashion Knowledge Graph — Pure Python rules engine.
Zero external dependencies. 500+ rules covering color theory, occasion,
category pairing, material compatibility, body proportions, and style archetypes.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ── Enums ──────────────────────────────────────────────────────────────────

class Category(Enum):
    TOP = "top"
    BOTTOM = "bottom"
    FOOTWEAR = "footwear"
    DRESS = "dress"
    OUTERWEAR = "outerwear"
    ACCESSORY = "accessory"
    BAG = "bag"
    JEWELRY = "jewelry"
    FULL_BODY = "full_body"


class Occasion(Enum):
    CASUAL = "casual"
    BUSINESS_FORMAL = "business_formal"
    BUSINESS_CASUAL = "business_casual"
    COCKTAIL = "cocktail"
    BLACK_TIE = "black_tie"
    BEACH = "beach"
    DATE_NIGHT = "date_night"
    BRUNCH = "brunch"
    WORKOUT = "workout"
    STREETWEAR = "streetwear"
    FESTIVAL = "festival"
    INTERVIEW = "interview"
    WEDDING_GUEST = "wedding_guest"
    GALA = "gala"
    SUNDAY_FUNDAY = "sunday_funday"
    OUTDOOR_ADVENTURE = "outdoor_adventure"
    NIGHT_OUT = "night_out"
    MUSIC_FESTIVAL = "music_festival"
    ETHNIC_FUSION = "ethnic_fusion"
    MINIMALIST = "minimalist"


class StyleArchetype(Enum):
    CLASSIC = "classic"
    MINIMALIST = "minimalist"
    BOHEMIAN = "bohemian"
    STREETWEAR = "streetwear"
    ROMANTIC = "romantic"
    EDGY = "edgy"
    PREPPY = "preppy"
    ATHLEISURE = "athleisure"
    AVANT_GARDE = "avant_garde"
    RELAXED = "relaxed"


class Formality(Enum):
    ULTRA_CASUAL = 1
    CASUAL = 2
    SMART_CASUAL = 3
    BUSINESS_CASUAL = 4
    BUSINESS = 5
    FORMAL = 6
    BLACK_TIE = 7


class Season(Enum):
    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"
    WINTER = "winter"
    ALL_SEASON = "all_season"


class BodyShape(Enum):
    APPLE = "apple"
    PEAR = "pear"
    HOURGLASS = "hourglass"
    RECTANGLE = "rectangle"
    INVERTED_TRIANGLE = "inverted_triangle"


class Pattern(Enum):
    SOLID = "solid"
    STRIPED = "striped"
    PLAID = "plaid"
    FLORAL = "floral"
    GEOMETRIC = "geometric"
    POLKA_DOT = "polka_dot"
    ANIMAL = "animal"
    ABSTRACT = "abstract"
    CHECK = "check"
    CAMO = "camo"


# ── Color Theory ───────────────────────────────────────────────────────────

# RGB color definitions for fashion colors
COLOR_RGB = {
    "black": (0, 0, 0), "white": (255, 255, 255), "red": (220, 20, 60),
    "blue": (65, 105, 225), "navy": (0, 0, 128), "green": (34, 139, 34),
    "olive": (128, 128, 0), "emerald": (80, 200, 120), "teal": (0, 128, 128),
    "purple": (128, 0, 128), "lavender": (230, 230, 250), "pink": (255, 192, 203),
    "hot_pink": (255, 105, 180), "coral": (255, 127, 80), "peach": (255, 218, 185),
    "orange": (255, 165, 0), "burnt_orange": (191, 87, 0), "yellow": (255, 255, 0),
    "mustard": (255, 219, 88), "gold": (255, 215, 0), "beige": (245, 245, 220),
    "cream": (255, 253, 208), "tan": (210, 180, 140), "brown": (139, 69, 19),
    "camel": (193, 154, 107), "burgundy": (128, 0, 32), "maroon": (128, 0, 0),
    "mauve": (224, 176, 255), "rust": (183, 65, 14), "terracotta": (204, 78, 92),
    "sage": (188, 184, 138), "mint": (152, 255, 152), "aqua": (0, 255, 255),
    "royal_blue": (65, 105, 225), "sky_blue": (135, 206, 235), "powder_blue": (176, 224, 230),
    "charcoal": (54, 69, 79), "grey": (128, 128, 128), "silver": (192, 192, 192),
    "stone": (155, 147, 132), "khaki": (195, 177, 123), "ivory": (255, 255, 240),
    "off_white": (250, 249, 246), "chocolate": (123, 63, 0), "wine": (114, 47, 55),
    "forest_green": (34, 100, 34), "lime": (50, 205, 50), "neon_green": (57, 255, 20),
    "hot_red": (255, 0, 0), "crimson": (220, 20, 60), "blush": (222, 93, 131),
}

# Color relationships — which colors complement each other
COMPLEMENTARY_COLORS = {
    "red": ["green", "olive", "sage"],
    "blue": ["orange", "coral", "peach"],
    "navy": ["gold", "mustard", "cream"],
    "green": ["red", "burgundy", "coral"],
    "purple": ["yellow", "gold", "mustard"],
    "pink": ["green", "olive", "teal"],
    "orange": ["blue", "navy", "teal"],
    "yellow": ["purple", "lavender", "navy"],
    "black": ["white", "red", "gold", "ivory"],
    "white": ["black", "navy", "red"],
    "beige": ["navy", "blue", "burgundy"],
    "brown": ["blue", "teal", "cream"],
    "burgundy": ["gold", "cream", "sage"],
    "teal": ["coral", "peach", "rust"],
    "olive": ["cream", "burgundy", "blush"],
    "camel": ["navy", "black", "white"],
    "grey": ["pink", "lavender", "yellow"],
    "charcoal": ["white", "red", "gold"],
    "emerald": ["blush", "peach", "gold"],
    "rust": ["navy", "teal", "cream"],
}

ANALOGOUS_COLORS = {
    "red": ["orange", "coral", "burgundy", "maroon", "rust"],
    "blue": ["teal", "navy", "sky_blue", "powder_blue", "royal_blue"],
    "green": ["olive", "sage", "emerald", "lime", "forest_green"],
    "purple": ["lavender", "mauve", "pink", "hot_pink"],
    "orange": ["coral", "peach", "burnt_orange", "rust", "terracotta"],
    "yellow": ["gold", "mustard", "cream", "peach"],
    "pink": ["coral", "peach", "blush", "hot_pink", "lavender"],
    "brown": ["tan", "camel", "chocolate", "rust", "terracotta"],
}

# Skin tone → best colors (Monk Skin Tone scale 1-10)
SKIN_TONE_COLORS = {
    1: {"best": ["red", "emerald", "royal_blue", "hot_pink", "coral"],
        "avoid": ["beige", "tan", "brown", "orange"]},
    2: {"best": ["red", "blue", "green", "purple", "pink"],
        "avoid": ["orange", "yellow", "beige"]},
    3: {"best": ["blue", "green", "pink", "coral", "burgundy"],
        "avoid": ["orange", "mustard"]},
    4: {"best": ["blue", "green", "coral", "burgundy", "emerald"],
        "avoid": ["neon_green", "orange"]},
    5: {"best": ["blue", "green", "yellow", "coral", "teal"],
        "avoid": ["pink", "lavender"]},
    6: {"best": ["yellow", "orange", "coral", "teal", "olive"],
        "avoid": ["lavender", "pink"]},
    7: {"best": ["orange", "yellow", "olive", "terracotta", "gold"],
        "avoid": ["pink", "lavender", "pastels"]},
    8: {"best": ["orange", "gold", "olive", "terracotta", "burgundy"],
        "avoid": ["pastels", "lavender", "mauve"]},
    9: {"best": ["burgundy", "gold", "olive", "terracotta", "rust"],
        "avoid": ["pastels", "neon", "bright_pink"]},
    10: {"best": ["burgundy", "gold", "emerald", "white", "red"],
         "avoid": ["pastels", "beige", "brown"]},
}

# 60-30-10 rule palette
PALETTE_60_30_10 = {
    "dominant_colors": ["black", "white", "navy", "beige", "grey", "cream", "charcoal", "brown", "tan"],
    "secondary_colors": ["blue", "grey", "camel", "stone", "olive", "sage", "forest_green", "burgundy"],
    "accent_colors": ["red", "coral", "gold", "hot_pink", "emerald", "yellow", "orange", "teal"],
}


# ── Occasion Rules ─────────────────────────────────────────────────────────

@dataclass
class OccasionRule:
    occasion: Occasion
    allowed_categories: set[Category]
    min_formality: Formality
    max_formality: Formality
    allowed_patterns: set[Pattern]
    restricted_colors: set[str]
    preferred_materials: set[str]
    max_items: int = 6
    description: str = ""


OCCASION_RULES: dict[Occasion, OccasionRule] = {
    Occasion.CASUAL: OccasionRule(
        occasion=Occasion.CASUAL,
        allowed_categories={Category.TOP, Category.BOTTOM, Category.FOOTWEAR, Category.ACCESSORY, Category.BAG},
        min_formality=Formality.ULTRA_CASUAL, max_formality=Formality.CASUAL,
        allowed_patterns={Pattern.SOLID, Pattern.STRIPED, Pattern.FLORAL, Pattern.CHECK, Pattern.GEOMETRIC, Pattern.POLKA_DOT, Pattern.ABSTRACT},
        restricted_colors=set(),
        preferred_materials={"cotton", "denim", "linen", "jersey", "fleece"},
        max_items=5, description="Relaxed everyday wear"),
    Occasion.BUSINESS_FORMAL: OccasionRule(
        occasion=Occasion.BUSINESS_FORMAL,
        allowed_categories={Category.TOP, Category.BOTTOM, Category.FOOTWEAR, Category.OUTERWEAR, Category.ACCESSORY},
        min_formality=Formality.BUSINESS, max_formality=Formality.FORMAL,
        allowed_patterns={Pattern.SOLID, Pattern.STRIPED, Pattern.PLAID},
        restricted_colors={"neon_green", "hot_pink", "orange", "yellow", "lime"},
        preferred_materials={"wool", "silk", "cotton", "linen", "cashmere"},
        max_items=6, description="Corporate professional"),
    Occasion.BUSINESS_CASUAL: OccasionRule(
        occasion=Occasion.BUSINESS_CASUAL,
        allowed_categories={Category.TOP, Category.BOTTOM, Category.FOOTWEAR, Category.OUTERWEAR, Category.ACCESSORY},
        min_formality=Formality.SMART_CASUAL, max_formality=Formality.BUSINESS_CASUAL,
        allowed_patterns={Pattern.SOLID, Pattern.STRIPED, Pattern.CHECK, Pattern.PLAID},
        restricted_colors={"neon_green", "hot_pink"},
        preferred_materials={"cotton", "chino", "wool", "linen", "denim"},
        max_items=5, description="Smart but not stuffy"),
    Occasion.COCKTAIL: OccasionRule(
        occasion=Occasion.COCKTAIL,
        allowed_categories={Category.DRESS, Category.TOP, Category.BOTTOM, Category.FOOTWEAR, Category.BAG, Category.JEWELRY},
        min_formality=Formality.FORMAL, max_formality=Formality.FORMAL,
        allowed_patterns={Pattern.SOLID, Pattern.STRIPED, Pattern.GEOMETRIC},
        restricted_colors={"denim_blue", "khaki", "camo"},
        preferred_materials={"silk", "satin", "chiffon", "velvet", "lace"},
        max_items=6, description="Elegant evening wear"),
    Occasion.BLACK_TIE: OccasionRule(
        occasion=Occasion.BLACK_TIE,
        allowed_categories={Category.DRESS, Category.OUTERWEAR, Category.FOOTWEAR, Category.BAG, Category.JEWELRY},
        min_formality=Formality.BLACK_TIE, max_formality=Formality.BLACK_TIE,
        allowed_patterns={Pattern.SOLID},
        restricted_colors={"neon_green", "hot_pink", "orange", "yellow", "lime", "camo"},
        preferred_materials={"silk", "satin", "velvet", "taffeta", "organza"},
        max_items=5, description="Black tie formal"),
    Occasion.BEACH: OccasionRule(
        occasion=Occasion.BEACH,
        allowed_categories={Category.TOP, Category.BOTTOM, Category.FOOTWEAR, Category.ACCESSORY, Category.BAG},
        min_formality=Formality.ULTRA_CASUAL, max_formality=Formality.CASUAL,
        allowed_patterns={Pattern.SOLID, Pattern.FLORAL, Pattern.GEOMETRIC, Pattern.STRIPED},
        restricted_colors={"black", "charcoal", "navy"},
        preferred_materials={"linen", "cotton", "chiffon", "rayon"},
        max_items=4, description="Beach and resort wear"),
    Occasion.DATE_NIGHT: OccasionRule(
        occasion=Occasion.DATE_NIGHT,
        allowed_categories={Category.DRESS, Category.TOP, Category.BOTTOM, Category.FOOTWEAR, Category.BAG, Category.JEWELRY, Category.OUTERWEAR},
        min_formality=Formality.SMART_CASUAL, max_formality=Formality.FORMAL,
        allowed_patterns={Pattern.SOLID, Pattern.STRIPED, Pattern.GEOMETRIC},
        restricted_colors=set(),
        preferred_materials={"silk", "satin", "cotton", "denim", "leather"},
        max_items=6, description="Date night elegant"),
    Occasion.BRUNCH: OccasionRule(
        occasion=Occasion.BRUNCH,
        allowed_categories={Category.TOP, Category.BOTTOM, Category.FOOTWEAR, Category.ACCESSORY, Category.BAG},
        min_formality=Formality.CASUAL, max_formality=Formality.SMART_CASUAL,
        allowed_patterns={Pattern.SOLID, Pattern.FLORAL, Pattern.STRIPED, Pattern.CHECK},
        restricted_colors=set(),
        preferred_materials={"cotton", "linen", "denim", "chambray"},
        max_items=5, description="Weekend brunch"),
    Occasion.STREETWEAR: OccasionRule(
        occasion=Occasion.STREETWEAR,
        allowed_categories={Category.TOP, Category.BOTTOM, Category.FOOTWEAR, Category.OUTERWEAR, Category.ACCESSORY, Category.BAG},
        min_formality=Formality.ULTRA_CASUAL, max_formality=Formality.CASUAL,
        allowed_patterns={Pattern.SOLID, Pattern.GEOMETRIC, Pattern.ABSTRACT, Pattern.CAMO, Pattern.CHECK},
        restricted_colors=set(),
        preferred_materials={"cotton", "denim", "nylon", "leather", "fleece"},
        max_items=6, description="Urban streetwear"),
    Occasion.WEDDING_GUEST: OccasionRule(
        occasion=Occasion.WEDDING_GUEST,
        allowed_categories={Category.DRESS, Category.TOP, Category.BOTTOM, Category.FOOTWEAR, Category.BAG, Category.JEWELRY, Category.OUTERWEAR},
        min_formality=Formality.FORMAL, max_formality=Formality.FORMAL,
        allowed_patterns={Pattern.SOLID, Pattern.FLORAL, Pattern.GEOMETRIC},
        restricted_colors={"white", "ivory", "cream", "off_white"},
        preferred_materials={"silk", "satin", "chiffon", "crepe", "lace"},
        max_items=6, description="Wedding guest attire"),
    Occasion.FESTIVAL: OccasionRule(
        occasion=Occasion.FESTIVAL,
        allowed_categories={Category.TOP, Category.BOTTOM, Category.FOOTWEAR, Category.ACCESSORY, Category.BAG, Category.JEWELRY},
        min_formality=Formality.ULTRA_CASUAL, max_formality=Formality.CASUAL,
        allowed_patterns={Pattern.FLORAL, Pattern.GEOMETRIC, Pattern.ABSTRACT, Pattern.ANIMAL, Pattern.POLKA_DOT},
        restricted_colors=set(),
        preferred_materials={"cotton", "chiffon", "silk", "denim"},
        max_items=6, description="Festival fashion"),
    Occasion.INTERVIEW: OccasionRule(
        occasion=Occasion.INTERVIEW,
        allowed_categories={Category.TOP, Category.BOTTOM, Category.FOOTWEAR, Category.OUTERWEAR, Category.ACCESSORY},
        min_formality=Formality.BUSINESS_CASUAL, max_formality=Formality.BUSINESS,
        allowed_patterns={Pattern.SOLID, Pattern.STRIPED},
        restricted_colors={"neon_green", "hot_pink", "orange", "yellow"},
        preferred_materials={"wool", "cotton", "linen", "silk"},
        max_items=5, description="Professional interview"),
    Occasion.GALA: OccasionRule(
        occasion=Occasion.GALA,
        allowed_categories={Category.DRESS, Category.OUTERWEAR, Category.FOOTWEAR, Category.BAG, Category.JEWELRY},
        min_formality=Formality.BLACK_TIE, max_formality=Formality.BLACK_TIE,
        allowed_patterns={Pattern.SOLID, Pattern.GEOMETRIC},
        restricted_colors={"khaki", "camo", "denim_blue"},
        preferred_materials={"silk", "satin", "velvet", "taffeta", "sequin"},
        max_items=5, description="Gala formal"),
    Occasion.OUTDOOR_ADVENTURE: OccasionRule(
        occasion=Occasion.OUTDOOR_ADVENTURE,
        allowed_categories={Category.TOP, Category.BOTTOM, Category.FOOTWEAR, Category.OUTERWEAR, Category.ACCESSORY},
        min_formality=Formality.ULTRA_CASUAL, max_formality=Formality.CASUAL,
        allowed_patterns={Pattern.SOLID, Pattern.CAMO},
        restricted_colors={"hot_pink", "neon_green"},
        preferred_materials={"nylon", "polyester", "fleece", "denim"},
        max_items=5, description="Outdoor activities"),
    Occasion.NIGHT_OUT: OccasionRule(
        occasion=Occasion.NIGHT_OUT,
        allowed_categories={Category.DRESS, Category.TOP, Category.BOTTOM, Category.FOOTWEAR, Category.BAG, Category.JEWELRY, Category.OUTERWEAR},
        min_formality=Formality.SMART_CASUAL, max_formality=Formality.FORMAL,
        allowed_patterns={Pattern.SOLID, Pattern.STRIPED, Pattern.GEOMETRIC},
        restricted_colors=set(),
        preferred_materials={"silk", "satin", "leather", "denim", "velvet"},
        max_items=6, description="Night out"),
    Occasion.MINIMALIST: OccasionRule(
        occasion=Occasion.MINIMALIST,
        allowed_categories={Category.TOP, Category.BOTTOM, Category.FOOTWEAR, Category.OUTERWEAR, Category.ACCESSORY},
        min_formality=Formality.CASUAL, max_formality=Formality.BUSINESS_CASUAL,
        allowed_patterns={Pattern.SOLID},
        restricted_colors={"neon_green", "hot_pink", "orange", "camo", "animal"},
        preferred_materials={"cotton", "wool", "linen", "silk", "cashmere"},
        max_items=4, description="Clean minimalist look"),
}


# ── Category Pairing Rules ─────────────────────────────────────────────────

# What categories can pair with what
CATEGORY_PAIRS = {
    Category.TOP: {Category.BOTTOM, Category.FOOTWEAR, Category.OUTERWEAR, Category.ACCESSORY, Category.BAG},
    Category.BOTTOM: {Category.TOP, Category.FOOTWEAR, Category.OUTERWEAR, Category.ACCESSORY, Category.BAG},
    Category.DRESS: {Category.FOOTWEAR, Category.OUTERWEAR, Category.BAG, Category.JEWELRY},
    Category.OUTERWEAR: {Category.TOP, Category.BOTTOM, Category.DRESS, Category.FOOTWEAR, Category.ACCESSORY},
    Category.FOOTWEAR: {Category.TOP, Category.BOTTOM, Category.DRESS, Category.OUTERWEAR},
    Category.ACCESSORY: {Category.TOP, Category.BOTTOM, Category.DRESS, Category.OUTERWEAR},
    Category.BAG: {Category.TOP, Category.BOTTOM, Category.DRESS, Category.OUTERWEAR},
    Category.JEWELRY: {Category.DRESS, Category.TOP, Category.OUTERWEAR},
    Category.FULL_BODY: {Category.FOOTWEAR, Category.OUTERWEAR, Category.BAG, Category.JEWELRY},
}

# Proportion rules: (anchor_category, recommended_fit_for_complement)
PROPORTION_RULES = {
    "slim_slim": {"top": "slim", "bottom": "relaxed", "verdict": "balanced"},
    "slim_relaxed": {"top": "slim", "bottom": "relaxed", "verdict": "ideal"},
    "oversized_fitted": {"top": "oversized", "bottom": "fitted", "verdict": "ideal"},
    "oversized_relaxed": {"top": "oversized", "bottom": "slim", "verdict": "balanced"},
    "fitted_oversized": {"top": "fitted", "bottom": "oversized", "verdict": "ideal"},
    "fitted_fitted": {"top": "fitted", "bottom": "slim", "verdict": "can_work"},
}

# Length balancing
LENGTH_RULES = {
    "mini_top": "maxi_or_wide_bottom",
    "cropped_top": "high_waist_bottom",
    "regular_top": "any_bottom",
    "long_top": "slim_bottom",
    "maxi_top": "slim_or_cropped_bottom",
}


# ── Material Compatibility ─────────────────────────────────────────────────

MATERIAL_COMPATIBILITY = {
    "cotton": {"pairs_with": ["denim", "leather", "wool", "linen", "chambray"],
               "seasons": {Season.SPRING, Season.SUMMER, Season.AUTUMN}, "weight": "light-medium"},
    "linen": {"pairs_with": ["cotton", "silk", "leather", "straw"],
              "seasons": {Season.SUMMER}, "weight": "light"},
    "silk": {"pairs_with": ["wool", "cotton", "leather", "velvet", "cashmere"],
             "seasons": {Season.SPRING, Season.SUMMER, Season.AUTUMN}, "weight": "light"},
    "satin": {"pairs_with": ["velvet", "wool", "leather", "cashmere"],
              "seasons": {Season.SPRING, Season.AUTUMN, Season.WINTER}, "weight": "light-medium"},
    "wool": {"pairs_with": ["silk", "cotton", "leather", "cashmere", "denim"],
             "seasons": {Season.AUTUMN, Season.WINTER}, "weight": "medium-heavy"},
    "cashmere": {"pairs_with": ["silk", "wool", "cotton", "leather"],
                 "seasons": {Season.AUTUMN, Season.WINTER}, "weight": "light-medium"},
    "denim": {"pairs_with": ["cotton", "leather", "silk", "wool", "sneakers"],
              "seasons": {Season.SPRING, Season.SUMMER, Season.AUTUMN}, "weight": "medium"},
    "leather": {"pairs_with": ["silk", "cotton", "wool", "denim", "cashmere"],
                "seasons": {Season.AUTUMN, Season.WINTER}, "weight": "medium-heavy"},
    "velvet": {"pairs_with": ["silk", "satin", "wool", "cashmere"],
               "seasons": {Season.AUTUMN, Season.WINTER}, "weight": "heavy"},
    "chiffon": {"pairs_with": ["silk", "satin", "cotton"],
                "seasons": {Season.SPRING, Season.SUMMER}, "weight": "light"},
    "nylon": {"pairs_with": ["cotton", "polyester", "leather"],
              "seasons": {Season.SPRING, Season.AUTUMN}, "weight": "light"},
    "polyester": {"pairs_with": ["cotton", "nylon", "leather"],
                  "seasons": {Season.SPRING, Season.SUMMER, Season.AUTUMN}, "weight": "light"},
    "fleece": {"pairs_with": ["denim", "cotton", "nylon"],
               "seasons": {Season.AUTUMN, Season.WINTER}, "weight": "medium"},
    "chambray": {"pairs_with": ["cotton", "leather", "denim"],
                 "seasons": {Season.SPRING, Season.SUMMER}, "weight": "light"},
    "crepe": {"pairs_with": ["silk", "satin", "wool"],
              "seasons": {Season.SPRING, Season.AUTUMN}, "weight": "light-medium"},
    "sequin": {"pairs_with": ["silk", "satin", "velvet"],
               "seasons": {Season.WINTER}, "weight": "medium"},
    "rayon": {"pairs_with": ["cotton", "silk", "linen"],
              "seasons": {Season.SPRING, Season.SUMMER}, "weight": "light"},
}

# Pattern mixing rules — which patterns can coexist
PATTERN_MIXING_RULES = {
    Pattern.SOLID: {Pattern.STRIPED, Pattern.FLORAL, Pattern.GEOMETRIC, Pattern.PLAID, Pattern.POLKA_DOT, Pattern.CHECK, Pattern.ANIMAL, Pattern.ABSTRACT, Pattern.CAMO},
    Pattern.STRIPED: {Pattern.SOLID, Pattern.PLAID, Pattern.CHECK},
    Pattern.FLORAL: {Pattern.SOLID},
    Pattern.GEOMETRIC: {Pattern.SOLID, Pattern.STRIPED},
    Pattern.PLAID: {Pattern.SOLID, Pattern.STRIPED},
    Pattern.POLKA_DOT: {Pattern.SOLID, Pattern.STRIPED},
    Pattern.ANIMAL: {Pattern.SOLID},
    Pattern.ABSTRACT: {Pattern.SOLID},
    Pattern.CHECK: {Pattern.SOLID, Pattern.STRIPED},
    Pattern.CAMO: {Pattern.SOLID},
}


# ── Body Shape Guidelines ─────────────────────────────────────────────────

BODY_SHAPE_RULES: dict[BodyShape, dict] = {
    BodyShape.APPLE: {
        "goal": "Draw attention away from midsection, elongate torso",
        "best_tops": ["V-neck", "wrap_top", "empire_waist", "tunic"],
        "best_bottoms": ["straight_leg", "bootcut", "wide_leg", "high_waist"],
        "best_dresses": ["empire_waist", "A_line", "wrap_dress"],
        "best_outerwear": ["structured_blazer", "long_cardigan", "trench"],
        "avoid": ["crop_top", "tight_waistband", "belted_waist", "clingy_fabric"],
        "proportion_rule": "elongate_top_or_balanced",
    },
    BodyShape.PEAR: {
        "goal": "Balance narrower shoulders with wider hips",
        "best_tops": ["boat_neck", "off_shoulder", "structured_shoulder", "puff_sleeve"],
        "best_bottoms": ["straight_leg", "bootcut", "dark_wash_jeans", "A_line_skirt"],
        "best_dresses": ["A_line", "fit_and_flare", "off_shoulder"],
        "best_outerwear": ["structured_blazer", "cape", "bolero"],
        "avoid": ["skinny_jeans", "pencil_skirt", "cargo_pants"],
        "proportion_rule": "broaden_shoulders",
    },
    BodyShape.HOURGLASS: {
        "goal": "Highlight defined waist, maintain balance",
        "best_tops": ["wrap_top", "fitted_tee", "V-neck", "peplum"],
        "best_bottoms": ["high_waist", "straight_leg", "pencil_skirt"],
        "best_dresses": ["wrap_dress", "fit_and_flare", "bodycon"],
        "best_outerwear": ["belted_coat", "fitted_blazer", "peplum_jacket"],
        "avoid": ["oversized_top", "boxy_silhouette", "drop_waist"],
        "proportion_rule": "define_waist",
    },
    BodyShape.RECTANGLE: {
        "goal": "Create curves, define waist",
        "best_tops": ["peplum", "ruffle", "wrap_top", "puff_sleeve"],
        "best_bottoms": ["pleated", "wide_leg", "cargo", "paperbag_waist"],
        "best_dresses": ["fit_and_flare", "wrap_dress", "ruffle_detail"],
        "best_outerwear": ["belted_coat", "peplum_blazer", "cropped_jacket"],
        "avoid": ["straight_silhouette", "boxy_fit", "drop_waist"],
        "proportion_rule": "create_curves",
    },
    BodyShape.INVERTED_TRIANGLE: {
        "goal": "Balance broad shoulders with hip volume",
        "best_tops": ["V-neck", "scoop_neck", "raglan_sleeve", "dark_top"],
        "best_bottoms": ["wide_leg", "flared", "pleated", "light_color_bottom"],
        "best_dresses": ["A_line", "fit_and_flare", "full_skirt"],
        "best_outerwear": ["long_cardigan", "unstructured", "hip_length"],
        "avoid": ["shoulder_pads", "boat_neck", "halter", "puff_sleeve"],
        "proportion_rule": "balance_shoulders_with_hips",
    },
}


# ── Style Archetype Profiles ──────────────────────────────────────────────

STYLE_PROFILES: dict[StyleArchetype, dict] = {
    StyleArchetype.CLASSIC: {
        "colors": {"navy", "black", "white", "beige", "camel", "burgundy", "grey"},
        "patterns": {Pattern.SOLID, Pattern.STRIPED, Pattern.PLAID},
        "materials": {"wool", "silk", "cotton", "cashmere", "leather"},
        "silhouettes": {"tailored", "structured", "fitted"},
        "keywords": ["timeless", "refined", "polished", "elegant"],
    },
    StyleArchetype.MINIMALIST: {
        "colors": {"black", "white", "grey", "beige", "cream", "navy"},
        "patterns": {Pattern.SOLID},
        "materials": {"cotton", "wool", "linen", "silk", "cashmere"},
        "silhouettes": {"clean", "simple", "uncluttered"},
        "keywords": ["clean", "essential", "understated", "modern"],
    },
    StyleArchetype.BOHEMIAN: {
        "colors": {"rust", "terracotta", "olive", "mustard", "burgundy", "cream", "sage"},
        "patterns": {Pattern.FLORAL, Pattern.GEOMETRIC, Pattern.ABSTRACT},
        "materials": {"chiffon", "silk", "cotton", "suede", "satin"},
        "silhouettes": {"flowy", "layered", "relaxed"},
        "keywords": ["free-spirited", "eclectic", "artistic", "romantic"],
    },
    StyleArchetype.STREETWEAR: {
        "colors": {"black", "white", "grey", "navy", "olive", "red"},
        "patterns": {Pattern.SOLID, Pattern.GEOMETRIC, Pattern.ABSTRACT, Pattern.CAMO},
        "materials": {"cotton", "denim", "nylon", "leather", "fleece"},
        "silhouettes": {"oversized", "relaxed", "boxy"},
        "keywords": ["urban", "edgy", "casual", "bold"],
    },
    StyleArchetype.ROMANTIC: {
        "colors": {"pink", "blush", "lavender", "cream", "mauve", "wine"},
        "patterns": {Pattern.FLORAL, Pattern.POLKA_DOT, Pattern.SOLID},
        "materials": {"silk", "satin", "lace", "chiffon", "velvet"},
        "silhouettes": {"fitted", "flowy", "feminine"},
        "keywords": ["feminine", "soft", "elegant", "delicate"],
    },
    StyleArchetype.EDGY: {
        "colors": {"black", "red", "burgundy", "charcoal", "white"},
        "patterns": {Pattern.SOLID, Pattern.ANIMAL, Pattern.GEOMETRIC},
        "materials": {"leather", "denim", "vinyl", "silk"},
        "silhouettes": {"structured", "asymmetric", "sharp"},
        "keywords": ["bold", "rebellious", "striking", "modern"],
    },
    StyleArchetype.PREPPY: {
        "colors": {"navy", "red", "white", "khaki", "forest_green", "burgundy"},
        "patterns": {Pattern.PLAID, Pattern.STRIPED, Pattern.CHECK, Pattern.SOLID},
        "materials": {"cotton", "chino", "wool", "denim", "leather"},
        "silhouettes": {"tailored", "crisp", "structured"},
        "keywords": ["polished", "preppy", "classic", "clean"],
    },
    StyleArchetype.ATHLEISURE: {
        "colors": {"black", "grey", "navy", "white", "olive"},
        "patterns": {Pattern.SOLID, Pattern.GEOMETRIC},
        "materials": {"nylon", "polyester", "cotton", "fleece", "spandex"},
        "silhouettes": {"relaxed", "functional", "comfortable"},
        "keywords": ["active", "comfortable", "functional", "modern"],
    },
    StyleArchetype.AVANT_GARDE: {
        "colors": {"black", "white", "red", "neon_green", "hot_pink"},
        "patterns": {Pattern.GEOMETRIC, Pattern.ABSTRACT},
        "materials": {"silk", "vinyl", "leather", "neoprene"},
        "silhouettes": {"asymmetric", "unconventional", "dramatic"},
        "keywords": ["experimental", "artistic", "innovative", "bold"],
    },
    StyleArchetype.RELAXED: {
        "colors": {"beige", "cream", "olive", "grey", "brown", "sage"},
        "patterns": {Pattern.SOLID, Pattern.CHECK, Pattern.STRIPED},
        "materials": {"cotton", "linen", "denim", "jersey"},
        "silhouettes": {"loose", "comfortable", "unstructured"},
        "keywords": ["easy", "comfortable", "laid-back", "effortless"],
    },
}


# ── Knowledge Graph Class ──────────────────────────────────────────────────

class KnowledgeGraph:
    """Singleton fashion knowledge graph with 500+ rules."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._color_cache: dict[str, set[str]] = {}
        self._build_color_cache()

    def _build_color_cache(self):
        """Pre-compute color compatibility sets."""
        for color, complements in COMPLEMENTARY_COLORS.items():
            self._color_cache[color] = set(complements)
        for color, analogs in ANALOGOUS_COLORS.items():
            if color in self._color_cache:
                self._color_cache[color] |= set(analogs)
            else:
                self._color_cache[color] = set(analogs)

    # ── Color Methods ──────────────────────────────────────────────────────

    def get_complementary_colors(self, color: str) -> set[str]:
        """Get colors that complement the given color."""
        return COMPLEMENTARY_COLORS.get(color.lower(), set())

    def get_analogous_colors(self, color: str) -> set[str]:
        """Get colors analogous to the given color."""
        return ANALOGOUS_COLORS.get(color.lower(), set())

    def get_harmonious_palette(self, color: str) -> dict[str, set[str]]:
        """Get a full harmonious palette for a color."""
        c = color.lower()
        return {
            "complementary": COMPLEMENTARY_COLORS.get(c, set()),
            "analogous": ANALOGOUS_COLORS.get(c, set()),
            "all_harmonious": self._color_cache.get(c, set()),
        }

    def score_color_pair(self, color_a: str, color_b: str) -> float:
        """Score how well two colors go together (0.0 - 1.0)."""
        a, b = color_a.lower(), color_b.lower()
        if a == b:
            return 0.7  # Same color is fine but not exciting
        if b in COMPLEMENTARY_COLORS.get(a, set()):
            return 1.0  # Perfect complement
        if b in ANALOGOUS_COLORS.get(a, set()):
            return 0.85  # Analogous harmony
        # Check through cache for indirect harmony
        if b in self._color_cache.get(a, set()):
            return 0.75
        # Neutral colors go with everything
        neutrals = {"black", "white", "grey", "charcoal", "beige", "cream", "navy"}
        if a in neutrals or b in neutrals:
            return 0.8
        return 0.3  # Unknown or clashing

    def score_palette_cohesion(self, colors: list[str]) -> float:
        """Score how cohesive a palette of multiple colors is."""
        if len(colors) <= 1:
            return 1.0
        pairs = []
        for i in range(len(colors)):
            for j in range(i + 1, len(colors)):
                pairs.append(self.score_color_pair(colors[i], colors[j]))
        return sum(pairs) / len(pairs) if pairs else 0.5

    def get_best_colors_for_skin_tone(self, skin_tone: int) -> dict[str, list[str]]:
        """Get recommended/avoid colors for a Monk Skin Tone level (1-10)."""
        tone = max(1, min(10, skin_tone))
        return SKIN_TONE_COLORS.get(tone, {"best": [], "avoid": []})

    def generate_60_30_10_palette(self, anchor_color: str) -> dict[str, str]:
        """Generate a 60-30-10 palette anchored by a given color."""
        c = anchor_color.lower()
        complements = list(COMPLEMENTARY_COLORS.get(c, ["grey"]))[:1]
        accent = complements[0] if complements else "gold"
        return {"dominant": c, "secondary": accent, "accent": accent}

    # ── Occasion Methods ───────────────────────────────────────────────────

    def get_occasion_rule(self, occasion: str) -> Optional[OccasionRule]:
        """Get the rule set for a specific occasion."""
        try:
            return OCCASION_RULES[Occasion(occasion.lower())]
        except (ValueError, KeyError):
            return None

    def is_category_allowed(self, occasion: str, category: str) -> bool:
        """Check if a category is allowed for an occasion."""
        rule = self.get_occasion_rule(occasion)
        if not rule:
            return True  # Unknown occasion = allow everything
        try:
            return Category(category.lower()) in rule.allowed_categories
        except ValueError:
            return False

    def is_pattern_allowed(self, occasion: str, pattern: str) -> bool:
        """Check if a pattern is allowed for an occasion."""
        rule = self.get_occasion_rule(occasion)
        if not rule:
            return True
        try:
            return Pattern(pattern.lower()) in rule.allowed_patterns
        except ValueError:
            return True

    def is_color_allowed(self, occasion: str, color: str) -> bool:
        """Check if a color is allowed for an occasion."""
        rule = self.get_occasion_rule(occasion)
        if not rule:
            return True
        return color.lower() not in rule.restricted_colors

    def get_formality_for_occasion(self, occasion: str) -> tuple[int, int]:
        """Get (min, max) formality levels for an occasion."""
        rule = self.get_occasion_rule(occasion)
        if not rule:
            return (1, 7)
        return (rule.min_formality.value, rule.max_formality.value)

    # ── Category Pairing Methods ───────────────────────────────────────────

    def get_compatible_categories(self, category: str) -> set[Category]:
        """Get categories that can pair with the given category."""
        try:
            return CATEGORY_PAIRS.get(Category(category.lower()), set())
        except ValueError:
            return set()

    def are_categories_compatible(self, cat_a: str, cat_b: str) -> bool:
        """Check if two categories can be worn together."""
        compat = self.get_compatible_categories(cat_a)
        try:
            return Category(cat_b.lower()) in compat
        except ValueError:
            return False

    # ── Material Methods ───────────────────────────────────────────────────

    def are_materials_compatible(self, mat_a: str, mat_b: str) -> bool:
        """Check if two materials can be paired."""
        a, b = mat_a.lower(), mat_b.lower()
        info_a = MATERIAL_COMPATIBILITY.get(a)
        if info_a:
            return b in info_a["pairs_with"]
        info_b = MATERIAL_COMPATIBILITY.get(b)
        if info_b:
            return a in info_b["pairs_with"]
        return True  # Unknown materials are allowed

    def get_season_materials(self, season: str) -> set[str]:
        """Get materials appropriate for a season."""
        try:
            s = Season(season.lower())
        except ValueError:
            return set()
        result = set()
        for mat, info in MATERIAL_COMPATIBILITY.items():
            if s in info["seasons"]:
                result.add(mat)
        return result

    # ── Pattern Methods ────────────────────────────────────────────────────

    def are_patterns_compatible(self, pat_a: str, pat_b: str) -> bool:
        """Check if two patterns can be mixed."""
        try:
            a, b = Pattern(pat_a.lower()), Pattern(pat_b.lower())
        except ValueError:
            return True
        return b in PATTERN_MIXING_RULES.get(a, set())

    # ── Body Shape Methods ─────────────────────────────────────────────────

    def get_body_shape_rules(self, body_shape: str) -> Optional[dict]:
        """Get styling rules for a body shape."""
        try:
            return BODY_SHAPE_RULES[BodyShape(body_shape.lower())]
        except (ValueError, KeyError):
            return None

    def score_item_for_body_shape(self, body_shape: str, item_description: str) -> float:
        """Score how well an item suits a body shape (0.0 - 1.0)."""
        rules = self.get_body_shape_rules(body_shape)
        if not rules:
            return 0.5
        desc = item_description.lower()
        # Check best items
        for key in ["best_tops", "best_bottoms", "best_dresses", "best_outerwear"]:
            for keyword in rules.get(key, []):
                if keyword.replace("_", " ") in desc or keyword in desc:
                    return 0.95
        # Check avoid items
        for keyword in rules.get("avoid", []):
            if keyword.replace("_", " ") in desc or keyword in desc:
                return 0.2
        return 0.5  # Neutral

    # ── Style Archetype Methods ────────────────────────────────────────────

    def get_style_profile(self, archetype: str) -> Optional[dict]:
        """Get the profile for a style archetype."""
        try:
            return STYLE_PROFILES[StyleArchetype(archetype.lower())]
        except (ValueError, KeyError):
            return None

    def score_style_match(self, archetype: str, item_attributes: dict) -> float:
        """Score how well an item matches a style archetype (0.0 - 1.0)."""
        profile = self.get_style_profile(archetype)
        if not profile:
            return 0.5
        score = 0.5
        # Check color match
        item_color = item_attributes.get("color", "").lower()
        if item_color in profile["colors"]:
            score += 0.15
        # Check pattern match
        item_pattern = item_attributes.get("pattern", "").lower()
        try:
            if Pattern(item_pattern) in profile["patterns"]:
                score += 0.15
        except ValueError:
            pass
        # Check material match
        item_material = item_attributes.get("material", "").lower()
        if item_material in profile["materials"]:
            score += 0.1
        # Check silhouette
        item_silhouette = item_attributes.get("silhouette", "").lower()
        if item_silhouette in profile["silhouettes"]:
            score += 0.1
        return min(1.0, score)

    def detect_style_archetype(self, closet_items: list[dict]) -> str:
        """Detect a user's dominant style archetype from their closet."""
        archetype_scores: dict[str, float] = {}
        for archetype in STYLE_PROFILES:
            total = 0.0
            for item in closet_items:
                total += self.score_style_match(archetype.value, item)
            archetype_scores[archetype.value] = total / max(len(closet_items), 1)
        if not archetype_scores:
            return "classic"
        return max(archetype_scores, key=archetype_scores.get)

    # ── Proportion Methods ─────────────────────────────────────────────────

    def get_proportion_advice(self, anchor_fit: str, anchor_category: str) -> dict:
        """Get proportion advice for complementing an anchor item."""
        if anchor_category in ("top", "outerwear"):
            if anchor_fit in ("slim", "fitted"):
                return {"recommended_bottom_fit": "relaxed", "rule": "slim_top_relaxed_bottom"}
            elif anchor_fit in ("oversized", "boxy"):
                return {"recommended_bottom_fit": "fitted", "rule": "oversized_top_fitted_bottom"}
        elif anchor_category == "bottom":
            if anchor_fit in ("slim", "skinny"):
                return {"recommended_top_fit": "relaxed", "rule": "slim_bottom_relaxed_top"}
            elif anchor_fit in ("wide", "relaxed", "flared"):
                return {"recommended_top_fit": "fitted", "rule": "wide_bottom_fitted_top"}
        return {"recommended_top_fit": "balanced", "rule": "default"}

    # ── Full Outfit Scoring ────────────────────────────────────────────────

    def score_outfit_coherence(self, items: list[dict], occasion: str = "casual") -> dict:
        """Score the overall coherence of an outfit."""
        if not items:
            return {"total": 0.0, "color": 0.0, "category": 0.0, "material": 0.0, "pattern": 0.0}

        # Color cohesion
        colors = [i.get("color", "black") for i in items if i.get("color")]
        color_score = self.score_palette_cohesion(colors) if colors else 0.5

        # Category compatibility
        categories = [i.get("category", "") for i in items]
        cat_pairs = 0
        cat_total = 0
        for i in range(len(categories)):
            for j in range(i + 1, len(categories)):
                cat_total += 1
                if self.are_categories_compatible(categories[i], categories[j]):
                    cat_pairs += 1
        cat_score = cat_pairs / max(cat_total, 1)

        # Material compatibility
        materials = [i.get("material", "") for i in items if i.get("material")]
        mat_pairs = 0
        mat_total = 0
        for i in range(len(materials)):
            for j in range(i + 1, len(materials)):
                mat_total += 1
                if self.are_materials_compatible(materials[i], materials[j]):
                    mat_pairs += 1
        mat_score = mat_pairs / max(mat_total, 1)

        # Pattern mixing
        patterns = [i.get("pattern", "solid") for i in items if i.get("pattern")]
        pat_pairs = 0
        pat_total = 0
        for i in range(len(patterns)):
            for j in range(i + 1, len(patterns)):
                pat_total += 1
                if self.are_patterns_compatible(patterns[i], patterns[j]):
                    pat_pairs += 1
        pat_score = pat_pairs / max(pat_total, 1)

        # Occasion appropriateness
        occ_score = 1.0
        rule = self.get_occasion_rule(occasion)
        if rule:
            for item in items:
                cat = item.get("category", "")
                if cat and not self.is_category_allowed(occasion, cat):
                    occ_score *= 0.3
                mat = item.get("material", "")
                if mat and mat not in rule.preferred_materials and rule.preferred_materials:
                    occ_score *= 0.8

        total = (color_score * 0.3 + cat_score * 0.25 + mat_score * 0.15 +
                 pat_score * 0.1 + occ_score * 0.2)

        return {
            "total": round(total, 3),
            "color": round(color_score, 3),
            "category": round(cat_score, 3),
            "material": round(mat_score, 3),
            "pattern": round(pat_score, 3),
            "occasion": round(occ_score, 3),
        }


# ── Module-level singleton accessor ────────────────────────────────────────

_graph = None

def get_knowledge_graph() -> KnowledgeGraph:
    """Get the singleton KnowledgeGraph instance."""
    global _graph
    if _graph is None:
        _graph = KnowledgeGraph()
    return _graph
