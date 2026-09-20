"""
Network Compatibility Scorer — Computes brand-to-brand compatibility.
Determines which brands can appear together and assigns tier ratings.
Updated weekly from transaction + interaction data.
"""
from __future__ import annotations
import json
import os
from typing import Optional


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


def _age_range_overlap(min1: float, max1: float, min2: float, max2: float) -> float:
    """Compute overlap ratio between two age ranges."""
    overlap_start = max(min1, min2)
    overlap_end = min(max1, max2)
    if overlap_start >= overlap_end:
        return 0.3
    overlap = overlap_end - overlap_start
    total = max(max1, max2) - min(min1, min2)
    if total <= 0:
        return 0.5
    return min(1.0, overlap / total)


def _color_palette_similarity(palette_a: list, palette_b: list) -> float:
    """How similar are two brand color palettes."""
    if not palette_a or not palette_b:
        return 0.5
    set_a = set(c.lower() for c in palette_a)
    set_b = set(c.lower() for c in palette_b)
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    if union == 0:
        return 0.5
    return intersection / union


class NetworkCompatibilityScorer:
    """
    Computes compatibility between brand pairs.
    
    Uses five dimensions:
    1. Style compatibility — do their aesthetics align?
    2. Price compatibility — are they in similar price ranges?
    3. Audience compatibility — do they target the same customers?
    4. Category complement — do they fill different outfit roles?
    5. Occasion compatibility — do they serve the same occasions?
    """

    def compute_pair_score(self, brand_a_id: str, brand_b_id: str) -> dict:
        """
        Compute full compatibility between two brands.
        Returns scores, tier, and recommendation text.
        """
        dna_a = self._get_brand_dna(brand_a_id)
        dna_b = self._get_brand_dna(brand_b_id)

        scores = {
            "style_compatibility": self._style_match(dna_a, dna_b),
            "price_compatibility": self._price_match(dna_a, dna_b),
            "audience_compatibility": self._audience_match(dna_a, dna_b),
            "category_complement": self._category_complement(dna_a, dna_b),
            "occasion_compatibility": self._occasion_match(dna_a, dna_b),
        }

        total = sum(scores.values()) / len(scores)

        tier = self._assign_tier(total)
        recommendation = self._get_recommendation_text(tier)

        result = {
            "brand_a_id": brand_a_id,
            "brand_b_id": brand_b_id,
            "scores": scores,
            "total_score": round(total, 3),
            "tier": tier,
            "recommendation": recommendation,
        }

        # Persist
        self._save_pair_score(result)

        return result

    def get_pair_score(self, brand_a_id: str, brand_b_id: str) -> Optional[dict]:
        """Get cached pair score, recompute if stale (>7 days)."""
        result = _sb_request(
            "GET",
            f"/rest/v1/brand_pair_compatibility?"
            f"brand_a_id=eq.{brand_a_id}&brand_b_id=eq.{brand_b_id}&select=*"
        )
        # Also check reverse direction
        if not result or not isinstance(result, list) or len(result) == 0:
            result = _sb_request(
                "GET",
                f"/rest/v1/brand_pair_compatibility?"
                f"brand_a_id=eq.{brand_b_id}&brand_b_id=eq.{brand_a_id}&select=*"
            )

        if result and isinstance(result, list) and len(result) > 0:
            row = result[0]
            from datetime import datetime, timedelta
            last = row.get("last_updated", "")
            if last:
                try:
                    last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
                    if datetime.now(last_dt.tzinfo) - last_dt < timedelta(days=7):
                        return row
                except Exception:
                    pass

        return self.compute_pair_score(brand_a_id, brand_b_id)

    def get_all_compatible_brands(
        self,
        brand_id: str,
        min_tier: str = "compatible",
    ) -> list[dict]:
        """Get all brands compatible with the given brand, sorted by score."""
        TIER_ORDER = {"strong_match": 4, "compatible": 3, "weak": 2, "incompatible": 1}
        min_score = TIER_ORDER.get(min_tier, 3)

        # Check both directions
        result_a = _sb_request(
            "GET",
            f"/rest/v1/brand_pair_compatibility?"
            f"brand_a_id=eq.{brand_id}&select=*&order=total_score.desc"
        )
        result_b = _sb_request(
            "GET",
            f"/rest/v1/brand_pair_compatibility?"
            f"brand_b_id=eq.{brand_id}&select=*&order=total_score.desc"
        )

        pairs = []
        seen = set()

        for result in [result_a, result_b]:
            if not result or not isinstance(result, list):
                continue
            for row in result:
                partner = row.get("brand_b_id") if row.get("brand_a_id") == brand_id else row.get("brand_a_id")
                if partner in seen:
                    continue
                seen.add(partner)
                tier = row.get("tier", "weak")
                if TIER_ORDER.get(tier, 0) >= min_score:
                    pairs.append({
                        "brand_id": partner,
                        "total_score": row.get("total_score", 0),
                        "tier": tier,
                        "scores": {
                            "style": row.get("style_compatibility", 0),
                            "price": row.get("price_compatibility", 0),
                            "audience": row.get("audience_compatibility", 0),
                            "category": row.get("category_complement", 0),
                            "occasion": row.get("occasion_compatibility", 0),
                        },
                    })

        pairs.sort(key=lambda x: x["total_score"], reverse=True)
        return pairs

    # ── Scoring Functions ──────────────────────────────────────────────────

    def _style_match(self, a: dict, b: dict) -> float:
        """Style profile similarity."""
        styles_a = a.get("style_profile", {})
        styles_b = b.get("style_profile", {})
        if not styles_a or not styles_b:
            return 0.5

        # Find common style keys
        common = set(styles_a.keys()) & set(styles_b.keys())
        if not common:
            return 0.3

        # Average similarity across common styles
        similarities = []
        for style in common:
            val_a = float(styles_a[style])
            val_b = float(styles_b[style])
            # Similarity = 1 - normalized difference
            sim = 1.0 - abs(val_a - val_b)
            similarities.append(sim)

        return sum(similarities) / len(similarities) if similarities else 0.5

    def _price_match(self, a: dict, b: dict) -> float:
        """Price positioning similarity."""
        tier_a = a.get("price_positioning", {}).get("tier", "mid")
        tier_b = b.get("price_positioning", {}).get("tier", "mid")

        TIERS = ["value", "mid", "premium", "luxury"]
        try:
            idx_a = TIERS.index(tier_a)
            idx_b = TIERS.index(tier_b)
        except ValueError:
            return 0.5

        diff = abs(idx_a - idx_b)
        if diff == 0:
            return 0.95
        elif diff == 1:
            return 0.7
        elif diff == 2:
            return 0.4
        return 0.2

    def _audience_match(self, a: dict, b: dict) -> float:
        """Target audience overlap."""
        demo_a = a.get("target_demographics", {})
        demo_b = b.get("target_demographics", {})

        age_overlap = _age_range_overlap(
            float(demo_a.get("age_min", 18)),
            float(demo_a.get("age_max", 65)),
            float(demo_b.get("age_min", 18)),
            float(demo_b.get("age_max", 65)),
        )

        gender_a = demo_a.get("gender", "unisex")
        gender_b = demo_b.get("gender", "unisex")
        gender_match = 1.0 if gender_a == gender_b or "unisex" in (gender_a, gender_b) else 0.4

        return (age_overlap * 0.6 + gender_match * 0.4)

    def _category_complement(self, a: dict, b: dict) -> float:
        """
        How complementary are the categories.
        High score = they sell different things (good for outfit building).
        Low score = they sell the same things (competitive).
        """
        cats_a = set(a.get("category_strength", {}).keys())
        cats_b = set(b.get("category_strength", {}).keys())

        if not cats_a or not cats_b:
            return 0.5

        if cats_a.isdisjoint(cats_b):
            return 0.95  # Perfect complement — no overlap

        overlap = len(cats_a & cats_b)
        total = len(cats_a | cats_b)

        return max(0.25, 1.0 - (overlap / total))

    def _occasion_match(self, a: dict, b: dict) -> float:
        """Occasion profile similarity."""
        # Simplified — would use actual occasion distributions
        return 0.65

    # ── Tier Assignment ────────────────────────────────────────────────────

    def _assign_tier(self, total_score: float) -> str:
        if total_score >= 0.8:
            return "strong_match"
        elif total_score >= 0.6:
            return "compatible"
        elif total_score >= 0.4:
            return "weak"
        return "incompatible"

    def _get_recommendation_text(self, tier: str) -> str:
        TEXTS = {
            "strong_match": "Strong compatibility with your brand positioning",
            "compatible": "Compatible partner for cross-recommendations",
            "weak": "Limited compatibility — consider carefully",
            "incompatible": "Not recommended for cross-recommendation",
        }
        return TEXTS.get(tier, "")

    # ── Data Helpers ───────────────────────────────────────────────────────

    def _get_brand_dna(self, brand_id: str) -> dict:
        """Fetch Brand DNA from database."""
        result = _sb_request(
            "GET",
            f"/rest/v1/brand_dna?brand_id=eq.{brand_id}&select=style_profile,price_positioning,target_demographics,category_strength,color_palette,formality_range"
        )
        if result and len(result) > 0:
            return result[0]
        return {}

    def _save_pair_score(self, data: dict):
        """Persist pair compatibility score."""
        existing = _sb_request(
            "GET",
            f"/rest/v1/brand_pair_compatibility?"
            f"brand_a_id=eq.{data['brand_a_id']}&brand_b_id=eq.{data['brand_b_id']}&select=id"
        )

        payload = {
            "brand_a_id": data["brand_a_id"],
            "brand_b_id": data["brand_b_id"],
            "style_compatibility": data["scores"]["style_compatibility"],
            "price_compatibility": data["scores"]["price_compatibility"],
            "audience_compatibility": data["scores"]["audience_compatibility"],
            "category_complement": data["scores"]["category_complement"],
            "occasion_compatibility": data["scores"]["occasion_compatibility"],
            "total_score": data["total_score"],
            "tier": data["tier"],
        }

        if existing and len(existing) > 0:
            _sb_request(
                "PATCH",
                f"/rest/v1/brand_pair_compatibility?"
                f"brand_a_id=eq.{data['brand_a_id']}&brand_b_id=eq.{data['brand_b_id']}",
                payload,
            )
        else:
            _sb_request("POST", "/rest/v1/brand_pair_compatibility", payload)


def get_network_compatibility_scorer() -> NetworkCompatibilityScorer:
    """Singleton accessor."""
    return NetworkCompatibilityScorer()
