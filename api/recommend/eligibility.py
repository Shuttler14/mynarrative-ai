"""
Eligibility Engine — Brand Safety Layer.
Hard rules that MUST pass before a product enters the ranking pipeline.
No amount of money can bypass these checks.
"""
from __future__ import annotations
from typing import Optional


class EligibilityEngine:
    """
    Pipeline: ALL NETWORK PRODUCTS → Eligible Products
    
    Every product must pass ALL checks to proceed.
    This is the non-negotiable brand safety gate.
    """

    def check(
        self,
        product: dict,
        host_brand_id: str,
        host_prefs: dict,
        category_rules: dict,
        user_context: dict,
    ) -> tuple[bool, str]:
        """
        Run all eligibility checks on a product.
        Returns (is_eligible, rejection_reason).
        """
        checks = [
            self._check_product_active,
            self._check_category_allowed,
            self._check_brand_not_excluded,
            self._check_competitor_policy,
            self._check_price_bounds,
            self._check_gender_compatible,
            self._check_in_stock,
            self._check_vton_ready,
            self._check_positioning_allowed,
            self._check_quality_threshold,
        ]

        for check_fn in checks:
            eligible, reason = check_fn(
                product, host_brand_id, host_prefs, category_rules, user_context
            )
            if not eligible:
                return False, reason

        return True, ""

    def _check_product_active(self, product, _host_id, _prefs, _cat_rules, _ctx):
        if not product.get("is_active", True):
            return False, "Product inactive"
        return True, ""

    def _check_category_allowed(self, product, _host_id, _prefs, cat_rules, _ctx):
        category = product.get("category", "")
        if not category:
            return True, ""
        rule = cat_rules.get(category, {})
        if not rule.get("allow_external", True):
            return False, f"Category '{category}' not open to external brands"
        return True, ""

    def _check_brand_not_excluded(self, product, host_id, prefs, _cat_rules, _ctx):
        product_brand_id = product.get("brand_id", "")
        if not product_brand_id:
            return True, ""
        excluded = set(prefs.get("excluded_brand_ids", []))
        if str(product_brand_id) in excluded:
            return False, "Brand explicitly excluded by host"
        return True, ""

    def _check_competitor_policy(self, product, host_id, prefs, _cat_rules, _ctx):
        product_brand_id = product.get("brand_id", "")
        if not product_brand_id:
            return True, ""
        competitors = set(prefs.get("competitor_brand_ids", []))
        policy = prefs.get("competitor_policy", "never_show")
        if str(product_brand_id) in competitors:
            if policy == "never_show":
                return False, "Direct competitor — blocked by host policy"
            elif policy == "show_if_relevant":
                pass  # Allow but will score lower in ranking
        return True, ""

    def _check_price_bounds(self, product, _host_id, prefs, cat_rules, _ctx):
        product_price = float(product.get("price", 0))
        if product_price <= 0:
            return True, ""  # Free or missing price — allow

        category = product.get("category", "")
        cat_rule = cat_rules.get(category, {})

        # Use category-level rules if available
        cat_min = float(cat_rule.get("price_range_min", 0))
        cat_max = float(cat_rule.get("price_range_max", 999999))

        # Global host price tolerance
        tolerance = float(prefs.get("price_tolerance_pct", 0.50))
        host_avg = float(prefs.get("host_avg_price", 0))

        # Hard boundary: 2x range from category or host avg
        if host_avg > 0:
            hard_min = host_avg * (1 - tolerance * 2)
            hard_max = host_avg * (1 + tolerance * 2)
        else:
            hard_min = cat_min * 0.5 if cat_min > 0 else 0
            hard_max = cat_max * 2 if cat_max < 999999 else 999999

        if product_price < hard_min or product_price > hard_max:
            return False, f"Price ₹{product_price:.0f} outside bounds (₹{hard_min:.0f}-₹{hard_max:.0f})"

        return True, ""

    def _check_gender_compatible(self, product, _host_id, _prefs, _cat_rules, ctx):
        product_gender = product.get("gender", "unisex")
        if product_gender == "unisex":
            return True, ""
        user_gender = ctx.get("gender", "")
        if not user_gender or user_gender == "unisex":
            return True, ""
        if product_gender != user_gender:
            return False, f"Gender mismatch: product is {product_gender}, user is {user_gender}"
        return True, ""

    def _check_in_stock(self, product, _host_id, _prefs, _cat_rules, ctx):
        sizes = product.get("sizes", [])
        if isinstance(sizes, str):
            try:
                import json
                sizes = json.loads(sizes)
            except Exception:
                sizes = []
        if sizes and ctx.get("user_size"):
            if ctx["user_size"] not in sizes:
                return False, f"Size {ctx['user_size']} not available"
        return True, ""

    def _check_vton_ready(self, product, _host_id, _prefs, _cat_rules, _ctx):
        dna = product.get("dna", {})
        if dna.get("vton_ready") is False:
            return False, "Product not VTON-ready"
        return True, ""

    def _check_positioning_allowed(self, product, _host_id, prefs, _cat_rules, _ctx):
        allowed = prefs.get("allowed_positionings", [])
        if not allowed:
            return True, ""  # No restriction
        product_positioning = product.get("brand_positioning", "mid")
        if product_positioning not in allowed:
            return False, f"Positioning '{product_positioning}' not in allowed list"
        return True, ""

    def _check_quality_threshold(self, product, _host_id, _prefs, _cat_rules, _ctx):
        quality = float(product.get("quality_score", 0.5))
        if quality < 0.25:
            return False, f"Quality score {quality:.2f} below minimum threshold"
        return True, ""


def get_eligibility_engine() -> EligibilityEngine:
    """Singleton accessor."""
    return EligibilityEngine()
