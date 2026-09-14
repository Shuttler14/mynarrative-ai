"""
Exploration Module — Multi-Armed Bandit for B2B brand fairness.
Epsilon-greedy strategy allocates 15-20% of recommendations to lower-impression partner brands.
"""
from __future__ import annotations
import math
import time
from typing import Optional


# In-memory brand impression tracking (resets periodically)
_brand_stats: dict[str, dict] = {}  # brand -> {impressions, clicks, conversions, last_updated}

# Epsilon-greedy parameters
EPSILON = 0.18  # 18% exploration
MIN_IMPRESSIONS = 5  # Minimum impressions before brand is considered "established"
DECAY_FACTOR = 0.95  # Decay old impressions over time


def _get_brand_stats(brand: str) -> dict:
    """Get or initialize stats for a brand."""
    if brand not in _brand_stats:
        _brand_stats[brand] = {
            "impressions": 0,
            "clicks": 0,
            "conversions": 0,
            "last_updated": time.time(),
            "score": 0.5,  # Initial neutral score
        }
    return _brand_stats[brand]


def record_impression(brand: str):
    """Record a recommendation impression for a brand."""
    stats = _get_brand_stats(brand)
    stats["impressions"] += 1
    stats["last_updated"] = time.time()
    _update_brand_score(brand)


def record_click(brand: str):
    """Record a click on a recommended item from this brand."""
    stats = _get_brand_stats(brand)
    stats["clicks"] += 1
    stats["last_updated"] = time.time()
    _update_brand_score(brand)


def record_conversion(brand: str):
    """Record a purchase/conversion from a recommended item."""
    stats = _get_brand_stats(brand)
    stats["conversions"] += 1
    stats["last_updated"] = time.time()
    _update_brand_score(brand)


def _update_brand_score(brand: str):
    """Update the internal score for a brand based on engagement."""
    stats = _get_brand_stats(brand)
    impressions = max(stats["impressions"], 1)
    ctr = stats["clicks"] / impressions
    cvr = stats["conversions"] / max(stats["clicks"], 1)

    # Composite score: weighted combination of CTR and CVR
    # Newer brands get a boost (exploration bonus)
    novelty_bonus = max(0, (MIN_IMPRESSIONS - stats["impressions"]) / MIN_IMPRESSIONS) * 0.3
    stats["score"] = min(1.0, ctr * 2 + cvr * 3 + novelty_bonus)


def get_brand_score(brand: str) -> float:
    """Get the current exploration score for a brand."""
    stats = _get_brand_stats(brand)
    return stats["score"]


def should_explore(exploration_rate: float = EPSILON) -> bool:
    """Decide whether to explore (True) or exploit (False)."""
    import random
    return random.random() < exploration_rate


def select_brand_for_exploration(
    candidate_brands: list[str],
    host_brand: str = "",
) -> Optional[str]:
    """
    Epsilon-greedy brand selection for B2B partner recommendations.
    - With probability (1 - epsilon): select the brand with highest score (exploit)
    - With probability epsilon: select a random brand (explore)
    """
    import random

    # Filter out host brand
    available = [b for b in candidate_brands if b != host_brand]
    if not available:
        return None

    if should_explore():
        # Exploration: pick a random brand, preferring lower-impression ones
        weights = []
        for brand in available:
            stats = _get_brand_stats(brand)
            # Lower impressions = higher weight for exploration
            weight = 1.0 / (1.0 + stats["impressions"] * 0.1)
            weights.append(weight)
        total = sum(weights) or 1
        weights = [w / total for w in weights]
        return random.choices(available, weights=weights, k=1)[0]
    else:
        # Exploitation: pick the brand with highest score
        return max(available, key=lambda b: get_brand_score(b))


def allocate_brand_slots(
    total_items: int,
    candidate_brands: list[str],
    host_brand: str = "",
    exploration_rate: float = EPSILON,
) -> dict[str, int]:
    """
    Allocate recommendation slots across brands.
    Ensures exploration brands get 15-20% of slots.
    Returns: {brand: slot_count}
    """
    import random

    if not candidate_brands:
        return {}

    available = [b for b in candidate_brands if b != host_brand]
    if not available:
        return {}

    exploration_slots = max(1, int(total_items * exploration_rate))
    exploitation_slots = total_items - exploration_slots

    allocations: dict[str, int] = {}

    # Exploitation: distribute among top brands
    if exploitation_slots > 0:
        # Sort by score
        sorted_brands = sorted(available, key=lambda b: get_brand_score(b), reverse=True)
        top_brands = sorted_brands[:min(3, len(sorted_brands))]
        if top_brands:
            per_brand = exploitation_slots // len(top_brands)
            remainder = exploitation_slots % len(top_brands)
            for i, brand in enumerate(top_brands):
                allocations[brand] = per_brand + (1 if i < remainder else 0)

    # Exploration: allocate to lower-impression brands
    if exploration_slots > 0:
        low_impression = [
            b for b in available
            if _get_brand_stats(b)["impressions"] < MIN_IMPRESSIONS
        ]
        if not low_impression:
            low_impression = available  # All brands are established, pick random

        explore_brands = random.sample(
            low_impression,
            min(exploration_slots, len(low_impression))
        )
        for brand in explore_brands:
            allocations[brand] = allocations.get(brand, 0) + 1

    return allocations


def get_brand_impressions_report() -> dict:
    """Get a report of all brand impressions and scores."""
    report = {}
    for brand, stats in _brand_stats.items():
        report[brand] = {
            "impressions": stats["impressions"],
            "clicks": stats["clicks"],
            "conversions": stats["conversions"],
            "ctr": round(stats["clicks"] / max(stats["impressions"], 1), 3),
            "cvr": round(stats["conversions"] / max(stats["clicks"], 1), 3),
            "score": round(stats["score"], 3),
        }
    return report


def reset_old_stats(max_age_hours: int = 168):
    """Reset stats older than max_age_hours (default: 7 days)."""
    cutoff = time.time() - (max_age_hours * 3600)
    to_remove = [b for b, s in _brand_stats.items() if s["last_updated"] < cutoff]
    for brand in to_remove:
        del _brand_stats[brand]
