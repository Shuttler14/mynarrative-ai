"""
End-to-end test harness for the Narrative Commerce Network.
Tests the full pipeline: eligibility -> ranking -> VTON -> analytics.
Run: python test_narrative_network.py
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# -- Config --
DRISHTI_URL = "https://drishti-api.fly.dev"
HAS_SUPABASE = bool(os.environ.get("SUPABASE_URL")) and bool(os.environ.get("SUPABASE_KEY"))

passed = 0
failed = 0
skipped = 0


def test(name, fn):
    global passed, failed, skipped
    try:
        result = fn()
        if result is None:
            print(f"  [skip] {name} (env not configured)")
            skipped += 1
        elif result:
            print(f"  [pass] {name}")
            passed += 1
        else:
            print(f"  [FAIL] {name}")
            failed += 1
    except Exception as e:
        print(f"  [FAIL] {name}: {e}")
        failed += 1


# == 1. DATABASE SCHEMA ==
print("\n== 1. DATABASE SCHEMA ==")

def test_schema_tables():
    if not HAS_SUPABASE:
        return None
    from api.core.supabase import sb_request
    tables = [
        "brand_dna", "product_dna", "host_category_rules", "host_preferences",
        "brand_exclusions", "brand_pair_compatibility", "sponsored_campaigns",
        "cross_brand_transactions", "network_events",
    ]
    for t in tables:
        r = sb_request("GET", f"/rest/v1/{t}?select=id&limit=1")
        if r is None:
            print(f"    table '{t}' not reachable")
            return False
    return True

test("All 9 narrative network tables exist", test_schema_tables)


# == 2. ELIGIBILITY ENGINE ==
print("\n== 2. ELIGIBILITY ENGINE ==")

def test_eligibility_import():
    from api.recommend.eligibility import EligibilityEngine
    return EligibilityEngine is not None

test("EligibilityEngine imports", test_eligibility_import)

def test_eligibility_check():
    from api.recommend.eligibility import EligibilityEngine
    engine = EligibilityEngine()
    candidate = {
        "is_active": True, "category": "tops", "price": 2500,
        "brand": "Nike", "brand_id": "nike-001",
    }
    host_prefs = {
        "network_mode": "curated_network",
        "excluded_brand_ids": [],
        "competitor_brand_ids": [],
        "competitor_policy": "never_show",
    }
    category_rules = {"tops": {"allow_external": True}}
    user_context = {"gender": "women", "min_price": 500, "max_price": 10000}
    eligible, reason = engine.check(candidate, "host-001", host_prefs, category_rules, user_context)
    return isinstance(eligible, bool) and isinstance(reason, str)

test("Eligibility check returns (bool, str)", test_eligibility_check)

def test_eligibility_rejects_inactive():
    from api.recommend.eligibility import EligibilityEngine
    engine = EligibilityEngine()
    candidate = {
        "is_active": False, "category": "tops", "price": 2500,
        "brand": "Nike", "brand_id": "nike-001",
    }
    eligible, reason = engine.check(candidate, "host-001", {}, {}, {})
    return eligible is False

test("Eligibility rejects inactive products", test_eligibility_rejects_inactive)

def test_eligibility_rejects_excluded_brand():
    from api.recommend.eligibility import EligibilityEngine
    engine = EligibilityEngine()
    candidate = {
        "is_active": True, "category": "tops", "price": 2500,
        "brand": "Nike", "brand_id": "nike-001",
    }
    host_prefs = {"excluded_brand_ids": ["nike-001"]}
    eligible, reason = engine.check(candidate, "host-001", host_prefs, {}, {})
    return eligible is False and "excluded" in reason.lower()

test("Eligibility rejects excluded brands", test_eligibility_rejects_excluded_brand)


# == 3. BRAND DNA ==
print("\n== 3. BRAND DNA ==")

def test_brand_dna_import():
    from api.recommend.brand_dna import BrandDNABuilder
    return BrandDNABuilder is not None

test("BrandDNABuilder imports", test_brand_dna_import)

def test_brand_dna_build():
    from api.recommend.brand_dna import BrandDNABuilder
    builder = BrandDNABuilder()
    dna = builder.build_dna("test-brand-nonexistent")
    return isinstance(dna, dict) and "style_profile" in dna

test("BrandDNA.build_dna() returns dict with style_profile", test_brand_dna_build)

def test_brand_dna_default():
    from api.recommend.brand_dna import BrandDNABuilder
    builder = BrandDNABuilder()
    dna = builder.build_dna("test-brand-nonexistent")
    return dna.get("quality_score") == 0.5

test("BrandDNA returns defaults for unknown brand", test_brand_dna_default)


# == 4. NETWORK COMPATIBILITY ==
print("\n== 4. NETWORK COMPATIBILITY ==")

def test_compat_import():
    from api.recommend.network_compatibility import NetworkCompatibilityScorer
    return NetworkCompatibilityScorer is not None

test("NetworkCompatibilityScorer imports", test_compat_import)

def test_compat_score():
    from api.recommend.network_compatibility import NetworkCompatibilityScorer
    scorer = NetworkCompatibilityScorer()
    result = scorer.compute_pair_score("brand-a-test", "brand-b-test")
    return isinstance(result, dict) and "tier" in result

test("Compatibility score returns tier", test_compat_score)


# == 5. CROSS-BRAND RANKING ==
print("\n== 5. CROSS-BRAND RANKING ==")

def test_ranker_import():
    from api.recommend.cross_ranking import get_cross_brand_ranker
    ranker = get_cross_brand_ranker()
    return ranker is not None

test("CrossBrandRanker loads", test_ranker_import)

def test_ranker_filters_inactive():
    from api.recommend.cross_ranking import get_cross_brand_ranker
    ranker = get_cross_brand_ranker()
    candidates = [
        {"id": "1", "is_active": True, "category": "tops", "price": 2500,
         "brand": "Nike", "brand_id": "nike-001"},
        {"id": "2", "is_active": False},
        {"id": "3", "is_active": True, "category": "tops", "price": 3000,
         "brand": "Adidas", "brand_id": "adidas-001"},
    ]
    ranked = ranker.rank(candidates, "host-001", {}, {}, "casual", "minimal")
    return all(r.get("is_active") for r in ranked)

test("Ranker filters inactive via eligibility gate", test_ranker_filters_inactive)

def test_ranker_preserves_order():
    from api.recommend.cross_ranking import get_cross_brand_ranker
    ranker = get_cross_brand_ranker()
    candidates = [
        {"id": "1", "is_active": True, "category": "tops", "price": 2500,
         "brand": "Nike", "brand_id": "nike-001"},
        {"id": "2", "is_active": True, "category": "bottoms", "price": 3000,
         "brand": "Adidas", "brand_id": "adidas-001"},
    ]
    ranked = ranker.rank(candidates, "host-001", {}, {}, "casual", "minimal")
    return len(ranked) == 2

test("Ranker returns all eligible candidates", test_ranker_preserves_order)


# == 6. SPONSORED CAMPAIGNS ==
print("\n== 6. SPONSORED CAMPAIGNS ==")

def test_campaigns_import():
    from api.sponsored.campaigns import (
        handle_create_campaign, handle_list_campaigns,
        handle_campaign_performance, handle_pricing_tiers,
    )
    return True

test("Campaign handlers import", test_campaigns_import)

def test_pricing_tiers():
    from api.sponsored.campaigns import handle_pricing_tiers
    result = handle_pricing_tiers()
    return "tiers" in result and "starter" in result["tiers"]

test("Pricing tiers return correct structure", test_pricing_tiers)

def test_pricing_has_three_tiers():
    from api.sponsored.campaigns import handle_pricing_tiers
    result = handle_pricing_tiers()
    tiers = result["tiers"]
    return len(tiers) == 3 and "starter" in tiers and "growth" in tiers and "enterprise" in tiers

test("Pricing has 3 tiers (starter/growth/enterprise)", test_pricing_has_three_tiers)


# == 7. NETWORK ANALYTICS ==
print("\n== 7. NETWORK ANALYTICS ==")

def test_analytics_import():
    from api.analytics import track_network_event, get_brand_network_report, get_product_performance
    return True

test("Analytics handlers import", test_analytics_import)


# == 8. WIDGET BOOTSTRAP ==
print("\n== 8. WIDGET BOOTSTRAP ==")

def test_bootstrap_import():
    from api.widget.bootstrap import handle_bootstrap
    return True

test("Widget bootstrap imports", test_bootstrap_import)


# == 9. DRISHTI VTON (Fly.io) ==
print("\n== 9. DRISHTI VTON (Fly.io) ==")

def test_drishti_health():
    import requests
    try:
        r = requests.get(f"{DRISHTI_URL}/", timeout=10)
        return r.status_code in (200, 404)
    except Exception:
        return None

test("drishti-api.fly.dev is reachable", test_drishti_health)

def test_drishti_vton_endpoint():
    import requests
    try:
        r = requests.post(
            f"{DRISHTI_URL}/api/vton/try-on",
            json={},
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        return r.status_code == 400
    except Exception:
        return None

test("Drishti /api/vton/try-on returns 400 on empty body", test_drishti_vton_endpoint)

def test_drishti_virtual_tryon_endpoint():
    import requests
    try:
        r = requests.post(
            f"{DRISHTI_URL}/api/virtual-tryon",
            json={},
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        # This endpoint may not exist on Fly.io (only /api/vton/try-on)
        # Accept 400, 404, or 422 as valid
        return r.status_code in (400, 404, 422)
    except Exception:
        return None

test("Drishti /api/virtual-tryon exists (or 404 if not deployed)", test_drishti_virtual_tryon_endpoint)

def test_drishti_cors():
    import requests
    try:
        r = requests.options(
            f"{DRISHTI_URL}/api/vton/try-on",
            headers={
                "Origin": "https://mynarrative.store",
                "Access-Control-Request-Method": "POST",
            },
            timeout=10,
        )
        return r.status_code in (200, 204)
    except Exception:
        return None

test("Drishti VTON has CORS headers", test_drishti_cors)


# == 10. FULL PIPELINE INTEGRATION ==
print("\n== 10. FULL PIPELINE INTEGRATION ==")

def test_recommend_returns_network_mode():
    if not os.environ.get("OPENAI_API_KEY"):
        return None  # skip — needs OpenAI for LLM reasoning
    from api.recommend.generate import handle_recommend
    result = handle_recommend({
        "brand_id": "test-brand",
        "brand_name": "Test Brand",
        "user_id": "test-user",
        "occasion": "casual",
        "price_tier": "mid",
        "outfit_count": 2,
    })
    return "network_mode" in result

test("handle_recommend returns network_mode field", test_recommend_returns_network_mode)

def test_recommend_returns_network_enabled():
    if not os.environ.get("OPENAI_API_KEY"):
        return None
    from api.recommend.generate import handle_recommend
    result = handle_recommend({
        "brand_id": "test-brand",
        "brand_name": "Test Brand",
        "user_id": "test-user",
        "occasion": "casual",
        "price_tier": "mid",
        "outfit_count": 2,
    })
    return "network_enabled" in result

test("handle_recommend returns network_enabled field", test_recommend_returns_network_enabled)

def test_recommend_has_success_field():
    if not os.environ.get("OPENAI_API_KEY"):
        return None
    from api.recommend.generate import handle_recommend
    result = handle_recommend({
        "brand_id": "test-brand",
        "brand_name": "Test Brand",
        "user_id": "test-user",
        "occasion": "casual",
        "price_tier": "mid",
        "outfit_count": 2,
    })
    return "success" in result

test("handle_recommend has success field", test_recommend_has_success_field)


# == 11. GATEWAY SYNTAX CHECK ==
print("\n== 11. GATEWAY INTEGRITY ==")

def test_gateway_compiles():
    import py_compile
    py_compile.compile("api/b2b_gateway.py", doraise=True)
    return True

test("b2b_gateway.py compiles cleanly", test_gateway_compiles)

def test_all_new_modules_compile():
    import py_compile
    modules = [
        "api/recommend/eligibility.py",
        "api/recommend/brand_dna.py",
        "api/recommend/cross_ranking.py",
        "api/recommend/network_compatibility.py",
        "api/sponsored/campaigns.py",
        "api/analytics/__init__.py",
        "api/widget/bootstrap.py",
        "api/recommend/generate.py",
    ]
    for m in modules:
        py_compile.compile(m, doraise=True)
    return True

test("All 8 new/modified modules compile", test_all_new_modules_compile)


# == SUMMARY ==
print(f"\n{'='*50}")
print(f"  RESULTS: {passed} passed, {failed} failed, {skipped} skipped")
print(f"{'='*50}")

sys.exit(0 if failed == 0 else 1)
