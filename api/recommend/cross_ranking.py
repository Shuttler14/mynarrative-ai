"""
Cross-Brand Ranking Engine — Two-stage ranking for the Narrative Commerce Network.

Pipeline:
  Network Products → Eligibility → Organic Score → Sponsored Boost → Final Rank

The key principle: Money never buys eligibility. It only buys marginal
exposure inside a pool of already-eligible, already-compatible products.
"""
from __future__ import annotations
import json
import os
import time
from typing import Optional

from .eligibility import get_eligibility_engine
from .brand_dna import get_brand_dna_builder


def _sb_request(method: str, path: str, payload: dict = None) -> Optional[list | dict]:
    """Raw Supabase REST request."""
    import requests as _requests
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY", "")
    if not url or not key:
        return None
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    full_url = f"{url.rstrip('/')}{path}"
    try:
        if method == "GET":
            resp = _requests.get(full_url, headers=headers, timeout=15)
        elif method == "POST":
            resp = _requests.post(full_url, json=payload, headers=headers, timeout=15)
        elif method == "PATCH":
            resp = _requests.patch(full_url, json=payload, headers=headers, timeout=15)
        else:
            resp = _requests.request(method, full_url, json=payload, headers=headers, timeout=15)
        return resp.json() if resp.text else None
    except Exception:
        return None


# ── Scoring Weights ────────────────────────────────────────────────────────

ORGANIC_WEIGHTS = {
    "outfit_compatibility": 0.25,
    "style_aesthetic": 0.15,
    "user_preference": 0.15,
    "price_compatibility": 0.10,
    "occasion_match": 0.10,
    "product_quality": 0.07,
    "brand_positioning": 0.07,
    "popularity_conversion": 0.05,
    "availability_size": 0.04,
    "trend_momentum": 0.02,
}

MAX_SPONSORED_BOOST = 0.15  # 15% max boost from sponsorship


class CrossBrandRanker:
    """
    Two-stage ranking engine for cross-brand recommendations.

    Stage 1: Eligibility (hard gate — no exceptions)
    Stage 2: Organic scoring (multi-factor weighted)
    Stage 3: Sponsored boost (capped, quality-gated)
    """

    def __init__(self):
        self.eligibility = get_eligibility_engine()
        self.dna_builder = get_brand_dna_builder()

    def rank(
        self,
        candidates: list[dict],
        host_brand_id: str,
        user_context: dict,
        outfit_context: dict,
        occasion: str = "casual",
        style: str = "classic",
    ) -> list[dict]:
        """
        Full ranking pipeline for cross-brand products.

        Args:
            candidates: Raw product list from network
            host_brand_id: The brand whose website we're on
            user_context: {gender, size, preferred_colors, age, etc.}
            outfit_context: {items, avg_price, anchor_item, etc.}
            occasion: Target occasion
            style: Target style archetype

        Returns:
            Ranked list of products with scores
        """

        # ── Fetch host configuration ──────────────────────────────────
        host_prefs = self._get_host_preferences(host_brand_id)
        host_dna = self.dna_builder.get_dna(host_brand_id)
        category_rules = self._get_category_rules(host_brand_id)

        # ── Stage 1: Eligibility ──────────────────────────────────────
        eligible = []
        rejected = []
        for product in candidates:
            is_eligible, reason = self.eligibility.check(
                product, host_brand_id, host_prefs, category_rules, user_context
            )
            if is_eligible:
                product["_eligible"] = True
                eligible.append(product)
            else:
                product["_eligible"] = False
                product["_rejection_reason"] = reason
                rejected.append(product)

        if not eligible:
            return []

        # ── Stage 2: Organic Scoring ──────────────────────────────────
        for product in eligible:
            score = self._compute_organic_score(
                product, host_dna, host_prefs, user_context, outfit_context, occasion, style
            )
            product["_organic_score"] = score

        eligible.sort(key=lambda x: x["_organic_score"], reverse=True)

        # ── Stage 3: Sponsored Boost (top candidates only) ────────────
        top_pool = eligible[:20]
        sponsored_campaigns = self._get_active_campaigns(host_brand_id)
        top_pool = self._apply_sponsored_boost(top_pool, sponsored_campaigns)

        # ── Final Sort ────────────────────────────────────────────────
        top_pool.sort(
            key=lambda x: x.get("_final_score", x["_organic_score"]),
            reverse=True,
        )

        # Clean internal fields for output
        for p in top_pool:
            p.pop("_eligible", None)
            p.pop("_rejection_reason", None)

        return top_pool

    # ── Host Configuration Fetchers ────────────────────────────────────────

    def _get_host_preferences(self, brand_id: str) -> dict:
        """Get host brand preferences with defaults."""
        result = _sb_request(
            "GET",
            f"/rest/v1/host_preferences?brand_id=eq.{brand_id}&select=*"
        )
        if result and len(result) > 0:
            return result[0]

        # Try to compute host avg price from their products
        return {
            "network_mode": "curated_network",
            "cross_brand_density": "balanced",
            "allowed_positionings": ["value", "mid", "premium", "luxury"],
            "competitor_policy": "never_show",
            "excluded_brand_ids": [],
            "competitor_brand_ids": [],
            "price_tolerance_pct": 0.50,
            "show_network_badge": True,
        }

    def _get_category_rules(self, brand_id: str) -> dict:
        """Get per-category rules for the host."""
        result = _sb_request(
            "GET",
            f"/rest/v1/host_category_rules?brand_id=eq.{brand_id}&select=*"
        )
        if not result or not isinstance(result, list):
            return {}

        rules = {}
        for row in result:
            cat = row.get("category", "")
            if cat:
                rules[cat] = {
                    "allow_external": row.get("allow_external", True),
                    "preferred_positionings": row.get("preferred_positionings", []),
                    "price_range_min": float(row.get("price_range_min", 0)),
                    "price_range_max": float(row.get("price_range_max", 999999)),
                }
        return rules

    def _get_active_campaigns(self, host_brand_id: str) -> list[dict]:
        """Get active sponsored campaigns targeting this host's site."""
        result = _sb_request(
            "GET",
            f"/rest/v1/sponsored_campaigns?status=eq.active&select=*"
        )
        if not result or not isinstance(result, list):
            return []

        campaigns = []
        for c in result:
            target_brands = c.get("target_brand_ids", [])
            # Campaign targets this host if:
            # 1. target_brand_ids is empty (network-wide), OR
            # 2. host_brand_id is in the target list
            if not target_brands or host_brand_id in target_brands:
                # Check budget remaining
                if float(c.get("spent", 0)) < float(c.get("budget", 0)):
                    campaigns.append(c)

        return campaigns

    # ── Organic Scoring ────────────────────────────────────────────────────

    def _compute_organic_score(
        self,
        product: dict,
        host_dna: dict,
        host_prefs: dict,
        user_context: dict,
        outfit_context: dict,
        occasion: str,
        style: str,
    ) -> float:
        """Weighted multi-factor organic scoring. Returns 0.0 - 1.0."""
        w = ORGANIC_WEIGHTS

        score = 0.0
        score += w["outfit_compatibility"] * self._score_outfit_compat(product, outfit_context)
        score += w["style_aesthetic"] * self._score_style_match(product, host_dna, style)
        score += w["user_preference"] * self._score_user_pref(product, user_context)
        score += w["price_compatibility"] * self._score_price_compat(product, outfit_context, host_dna)
        score += w["occasion_match"] * self._score_occasion(product, occasion)
        score += w["product_quality"] * self._score_quality(product)
        score += w["brand_positioning"] * self._score_positioning(product, host_dna)
        score += w["popularity_conversion"] * self._score_popularity(product)
        score += w["availability_size"] * self._score_availability(product, user_context)
        score += w["trend_momentum"] * self._score_trend(product)

        return round(score, 4)

    def _score_outfit_compat(self, product: dict, outfit_context: dict) -> float:
        """How well does this product complete the current outfit?"""
        existing_items = outfit_context.get("items", [])
        if not existing_items:
            return 0.7  # Neutral if no outfit context

        existing_cats = {i.get("category") for i in existing_items}
        product_cat = product.get("category", "")

        # Outfit role complementarity
        COMPLEMENT_MAP = {
            "top": {"bottom", "footwear", "accessory", "bag"},
            "bottom": {"top", "footwear", "outerwear"},
            "dress": {"footwear", "accessory", "outerwear", "bag"},
            "footwear": {"top", "bottom", "accessory"},
            "outerwear": {"top", "bottom", "dress"},
            "accessory": {"top", "bottom", "dress"},
            "bag": {"top", "bottom", "dress"},
        }

        complements = COMPLEMENT_MAP.get(product_cat, set())
        if existing_cats & complements:
            return 0.9  # Good complement
        if product_cat in existing_cats:
            return 0.25  # Duplicate category — bad
        return 0.55  # Neutral

    def _score_style_match(self, product: dict, host_dna: dict, user_style: str) -> float:
        """Style/aesthetic compatibility."""
        host_styles = host_dna.get("style_profile", {})
        product_styles = product.get("style_tags", [])
        if isinstance(product_styles, str):
            try:
                product_styles = json.loads(product_styles)
            except Exception:
                product_styles = []

        if not host_styles or not product_styles:
            return 0.5

        # Overlap between product styles and host brand styles
        overlap = sum(1 for s in product_styles if s in host_styles)
        if overlap == 0:
            return 0.35

        # Bonus if product also matches user's style
        user_match = 1.0 if user_style in product_styles else 0.0

        base = min(1.0, 0.5 + (overlap * 0.15))
        return (base + user_match * 0.2) / 1.2

    def _score_user_pref(self, product: dict, user_context: dict) -> float:
        """Match against user's preferences."""
        preferred_colors = set(user_context.get("preferred_colors", []))
        product_color = product.get("color", "")

        if preferred_colors and product_color and product_color.lower() in preferred_colors:
            return 0.9

        # Check size availability
        user_size = user_context.get("size", "")
        if user_size:
            sizes = product.get("sizes", [])
            if isinstance(sizes, str):
                try:
                    sizes = json.loads(sizes)
                except Exception:
                    sizes = []
            if user_size in sizes:
                return 0.8

        return 0.5

    def _score_price_compat(self, product: dict, outfit_context: dict, host_dna: dict) -> float:
        """Price compatibility with outfit context and host range."""
        product_price = float(product.get("price", 0))
        if product_price <= 0:
            return 0.5

        # Compare to outfit average price
        outfit_avg = outfit_context.get("avg_price", 0)
        if outfit_avg > 0:
            ratio = product_price / outfit_avg
            if 0.6 <= ratio <= 1.4:
                return 0.95
            elif 0.4 <= ratio <= 1.8:
                return 0.7
            elif 0.25 <= ratio <= 2.5:
                return 0.45
            return 0.2

        # Fallback to host price tier
        host_avg = float(host_dna.get("price_positioning", {}).get("avg", 0))
        if host_avg > 0:
            ratio = product_price / host_avg
            if 0.5 <= ratio <= 1.5:
                return 0.85
            return max(0.2, 0.85 - abs(ratio - 1) * 0.3)

        return 0.5

    def _score_occasion(self, product: dict, occasion: str) -> float:
        """Occasion compatibility."""
        if not occasion:
            return 0.6

        product_occasions = product.get("occasion", [])
        if isinstance(product_occasions, str):
            try:
                product_occasions = json.loads(product_occasions)
            except Exception:
                product_occasions = [product_occasions]

        if occasion in product_occasions:
            return 0.95

        # Check for similar occasions
        SIMILAR = {
            "casual": ["brunch", "streetwear"],
            "business_formal": ["interview", "business_casual"],
            "cocktail": ["date_night", "night_out"],
            "wedding_guest": ["cocktail", "gala"],
        }
        similar = SIMILAR.get(occasion, [])
        if any(o in product_occasions for o in similar):
            return 0.7

        return 0.4

    def _score_quality(self, product: dict) -> float:
        """Product quality score."""
        quality = float(product.get("quality_score", 0.5))
        return max(0.0, min(1.0, quality))

    def _score_positioning(self, product: dict, host_dna: dict) -> float:
        """Brand positioning compatibility."""
        host_tier = host_dna.get("price_positioning", {}).get("tier", "mid")
        product_tier = product.get("brand_positioning", "mid")

        TIERS = ["value", "mid", "premium", "luxury"]
        try:
            host_idx = TIERS.index(host_tier)
            prod_idx = TIERS.index(product_tier)
        except ValueError:
            return 0.5

        diff = abs(host_idx - prod_idx)
        if diff == 0:
            return 0.95
        elif diff == 1:
            return 0.75
        elif diff == 2:
            return 0.45
        return 0.2

    def _score_popularity(self, product: dict) -> float:
        """Brand popularity / historical conversion."""
        pop = float(product.get("brand_popularity", 0.5))
        return max(0.0, min(1.0, pop))

    def _score_availability(self, product: dict, user_context: dict) -> float:
        """Size/stock availability."""
        user_size = user_context.get("size", "")
        if not user_size:
            return 0.8  # No size preference = assume ok

        sizes = product.get("sizes", [])
        if isinstance(sizes, str):
            try:
                sizes = json.loads(sizes)
            except Exception:
                sizes = []

        if not sizes:
            return 0.7  # No size info = assume available

        if user_size in sizes:
            return 1.0
        return 0.3

    def _score_trend(self, product: dict) -> float:
        """Trend momentum (recently popular products score higher)."""
        trend = float(product.get("trend_score", 0.5))
        return max(0.0, min(1.0, trend))

    # ── Sponsored Boost ────────────────────────────────────────────────────

    def _apply_sponsored_boost(
        self,
        candidates: list[dict],
        campaigns: list[dict],
    ) -> list[dict]:
        """
        Apply quality-gated sponsored boost.
        Money never overrides organic ranking — it only adds marginal lift.
        """
        if not campaigns:
            for p in candidates:
                p["_final_score"] = p["_organic_score"]
                p["_sponsored"] = False
            return candidates

        for product in candidates:
            best_boost = 0.0
            matched_campaign = None

            for campaign in campaigns:
                if self._campaign_matches(product, campaign):
                    boost = float(campaign.get("boost_pct", 0.10))
                    if boost > best_boost:
                        best_boost = min(boost, MAX_SPONSORED_BOOST)
                        matched_campaign = campaign

            organic = product["_organic_score"]
            product["_final_score"] = round(organic * (1 + best_boost), 4)
            product["_sponsored"] = best_boost > 0
            product["_boost_amount"] = best_boost
            if matched_campaign:
                product["_campaign_id"] = matched_campaign.get("id", "")

        return candidates

    def _campaign_matches(self, product: dict, campaign: dict) -> bool:
        """Check if a product qualifies for a specific campaign."""
        # Brand match
        if product.get("brand_id") != campaign.get("brand_id"):
            return False

        # Category filter
        target_cats = campaign.get("target_categories", [])
        if target_cats and product.get("category") not in target_cats:
            return False

        # Occasion filter
        target_occasions = campaign.get("target_occasions", [])
        if target_occasions:
            product_occasions = product.get("occasion", [])
            if isinstance(product_occasions, str):
                try:
                    product_occasions = json.loads(product_occasions)
                except Exception:
                    product_occasions = []
            if not any(o in target_occasions for o in product_occasions):
                return False

        # Price filter
        price = float(product.get("price", 0))
        if price < float(campaign.get("target_price_min", 0)):
            return False
        if price > float(campaign.get("target_price_max", 999999)):
            return False

        return True


def get_cross_brand_ranker() -> CrossBrandRanker:
    """Singleton accessor."""
    return CrossBrandRanker()
