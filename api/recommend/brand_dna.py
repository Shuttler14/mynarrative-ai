"""
Brand DNA Builder — Computes and maintains brand profiles.
Analyzes product catalog, transaction history, and network interactions
to create a continuously updated brand fingerprint.
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


# ── Style Keywords for Classification ───────────────────────────────────────

_STYLE_KEYWORDS = {
    "classic": ["classic", "timeless", "refined", "polished", "elegant", "tailored"],
    "minimalist": ["minimalist", "clean", "simple", "essential", "understated"],
    "streetwear": ["streetwear", "urban", "oversized", "boxy", "hype", "capsule"],
    "bohemian": ["bohemian", "boho", "free-spirited", "eclectic", "flowy"],
    "romantic": ["romantic", "feminine", "soft", "delicate", "floral"],
    "edgy": ["edgy", "bold", "rebellious", "striking", "avant-garde"],
    "preppy": ["preppy", "polished", "prep", "crisp", "ivy"],
    "athleisure": ["athleisure", "athletic", "sporty", "performance", "activewear"],
    "contemporary": ["contemporary", "modern", "current", "trendy"],
    "traditional": ["traditional", "ethnic", "heritage", "artisan"],
}


class BrandDNABuilder:
    """
    Builds and maintains Brand DNA from:
    1. Product catalog analysis (primary signal)
    2. Transaction/conversion history (secondary signal)
    3. Network interaction data (tertiary signal)
    """

    def build_dna(self, brand_id: str) -> dict:
        """Compute complete Brand DNA for a brand."""
        products = self._fetch_brand_products(brand_id)
        if not products:
            return self._default_dna()

        dna = {
            "style_profile": self._compute_style_profile(products),
            "price_positioning": self._compute_price_positioning(products),
            "target_demographics": self._compute_demographics(products),
            "category_strength": self._compute_category_strength(products),
            "color_palette": self._compute_color_palette(products),
            "formality_range": self._compute_formality_range(products),
            "quality_score": self._compute_quality_score(brand_id),
            "brand_popularity": self._compute_popularity(brand_id),
        }

        # Persist to database
        self._save_dna(brand_id, dna)

        return dna

    def get_dna(self, brand_id: str) -> dict:
        """Get cached Brand DNA, recompute if stale (>24h)."""
        result = _sb_request(
            "GET",
            f"/rest/v1/brand_dna?brand_id=eq.{brand_id}&select=*"
        )
        if result and len(result) > 0:
            row = result[0]
            # Check staleness
            from datetime import datetime, timedelta
            last = row.get("last_computed_at", "")
            if last:
                try:
                    last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
                    if datetime.now(last_dt.tzinfo) - last_dt < timedelta(hours=24):
                        return {
                            "style_profile": row.get("style_profile", {}),
                            "price_positioning": row.get("price_positioning", {}),
                            "target_demographics": row.get("target_demographics", {}),
                            "category_strength": row.get("category_strength", {}),
                            "color_palette": row.get("color_palette", []),
                            "formality_range": row.get("formality_range", {}),
                            "quality_score": row.get("quality_score", 0.5),
                            "brand_popularity": row.get("brand_popularity", 0.5),
                        }
                except Exception:
                    pass

        # Recompute
        return self.build_dna(brand_id)

    def _fetch_brand_products(self, brand_id: str) -> list[dict]:
        """Fetch all active products for a brand."""
        catalogs = _sb_request(
            "GET",
            f"/rest/v1/brand_catalogs?brand_id=eq.{brand_id}&select=id"
        )
        if not catalogs:
            return []

        catalog_ids = [c["id"] for c in catalogs]
        if not catalog_ids:
            return []

        cid = catalog_ids[0]
        products = _sb_request(
            "GET",
            f"/rest/v1/brand_products?catalog_id=eq.{cid}&is_active=eq.true&select=*&limit=500"
        )
        return products if isinstance(products, list) else []

    def _compute_style_profile(self, products: list[dict]) -> dict:
        """Analyze style distribution across catalog."""
        style_counts = {}
        for p in products:
            text = " ".join([
                p.get("title", ""),
                p.get("description", ""),
                " ".join(p.get("tags", []) if isinstance(p.get("tags"), list) else []),
                p.get("subcategory", ""),
            ]).lower()

            for style, keywords in _STYLE_KEYWORDS.items():
                if any(kw in text for kw in keywords):
                    style_counts[style] = style_counts.get(style, 0) + 1

        total = max(sum(style_counts.values()), 1)
        profile = {k: round(v / total, 3) for k, v in style_counts.items()}

        # Ensure minimum representation
        if not profile:
            profile = {"contemporary": 0.5, "classic": 0.5}

        return profile

    def _compute_price_positioning(self, products: list[dict]) -> dict:
        """Compute price distribution and tier."""
        prices = []
        for p in products:
            try:
                price = float(p.get("price", 0))
                if price > 0:
                    prices.append(price)
            except (ValueError, TypeError):
                continue

        if not prices:
            return {"min": 0, "max": 0, "avg": 0, "tier": "mid", "p25": 0, "p75": 0}

        prices_sorted = sorted(prices)
        avg = sum(prices) / len(prices)
        n = len(prices)

        if avg < 1500:
            tier = "value"
        elif avg < 3500:
            tier = "mid"
        elif avg < 8000:
            tier = "premium"
        else:
            tier = "luxury"

        return {
            "min": round(prices_sorted[0], 2),
            "max": round(prices_sorted[-1], 2),
            "avg": round(avg, 2),
            "tier": tier,
            "p25": round(prices_sorted[n // 4], 2),
            "p75": round(prices_sorted[3 * n // 4], 2),
            "median": round(prices_sorted[n // 2], 2),
        }

    def _compute_demographics(self, products: list[dict]) -> dict:
        """Infer target demographics from catalog."""
        genders = {}
        for p in products:
            g = p.get("gender", "unisex")
            genders[g] = genders.get(g, 0) + 1

        dominant_gender = max(genders, key=genders.get) if genders else "unisex"

        # Default age range — would be refined with transaction data
        return {
            "age_min": 22,
            "age_max": 35,
            "gender": dominant_gender,
        }

    def _compute_category_strength(self, products: list[dict]) -> dict:
        """How strong is this brand in each category."""
        cats = {}
        for p in products:
            cat = p.get("category", "unknown")
            cats[cat] = cats.get(cat, 0) + 1
        total = max(len(products), 1)
        return {k: round(v / total, 3) for k, v in cats.items()}

    def _compute_color_palette(self, products: list[dict]) -> list[str]:
        """Dominant colors in brand's catalog."""
        colors = {}
        for p in products:
            c = p.get("color", "")
            if c:
                colors[c.lower()] = colors.get(c.lower(), 0) + 1
        sorted_colors = sorted(colors.items(), key=lambda x: x[1], reverse=True)
        return [c for c, _ in sorted_colors[:7]]

    def _compute_formality_range(self, products: list[dict]) -> dict:
        """Formality distribution."""
        forms = []
        for p in products:
            f = p.get("formality")
            if f is not None:
                try:
                    forms.append(int(f))
                except (ValueError, TypeError):
                    pass
        if not forms:
            return {"min": 2, "max": 5, "avg": 3}
        return {
            "min": min(forms),
            "max": max(forms),
            "avg": round(sum(forms) / len(forms), 1),
        }

    def _compute_quality_score(self, brand_id: str) -> float:
        """
        Quality score from:
        - Return rate (lower = better)
        - Average reviews
        - Conversion rate
        """
        # Placeholder — would aggregate from transaction data
        # Start with 0.5 (neutral) and improve over time
        result = _sb_request(
            "GET",
            f"/rest/v1/brand_dna?brand_id=eq.{brand_id}&select=quality_score"
        )
        if result and len(result) > 0:
            return float(result[0].get("quality_score", 0.5))
        return 0.5

    def _compute_popularity(self, brand_id: str) -> float:
        """
        Brand popularity from network-wide data:
        - Total impressions across all host sites
        - Total conversions
        - CTR
        """
        # Count cross-brand transactions
        tx = _sb_request(
            "GET",
            f"/rest/v1/cross_brand_transactions?supplier_brand_id=eq.{brand_id}&select=id"
        )
        tx_count = len(tx) if isinstance(tx, list) else 0

        # Normalize: 0-100 transactions → 0.0-1.0
        return min(1.0, tx_count / 100)

    def _save_dna(self, brand_id: str, dna: dict):
        """Persist Brand DNA to database."""
        existing = _sb_request(
            "GET",
            f"/rest/v1/brand_dna?brand_id=eq.{brand_id}&select=brand_id"
        )
        payload = {
            "brand_id": brand_id,
            "style_profile": dna["style_profile"],
            "price_positioning": dna["price_positioning"],
            "target_demographics": dna["target_demographics"],
            "category_strength": dna["category_strength"],
            "color_palette": dna["color_palette"],
            "formality_range": dna["formality_range"],
            "quality_score": dna["quality_score"],
            "brand_popularity": dna["brand_popularity"],
        }

        if existing and len(existing) > 0:
            _sb_request("PATCH", f"/rest/v1/brand_dna?brand_id=eq.{brand_id}", payload)
        else:
            _sb_request("POST", "/rest/v1/brand_dna", payload)

    def _default_dna(self) -> dict:
        return {
            "style_profile": {"contemporary": 0.5, "classic": 0.5},
            "price_positioning": {"min": 0, "max": 0, "avg": 0, "tier": "mid", "p25": 0, "p75": 0},
            "target_demographics": {"age_min": 18, "age_max": 65, "gender": "unisex"},
            "category_strength": {},
            "color_palette": [],
            "formality_range": {"min": 2, "max": 5, "avg": 3},
            "quality_score": 0.5,
            "brand_popularity": 0.5,
        }


def get_brand_dna_builder() -> BrandDNABuilder:
    """Singleton accessor."""
    return BrandDNABuilder()
