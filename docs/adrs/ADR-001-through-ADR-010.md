# Architecture Decision Records

## ADR-001: Dual Backend Architecture (Vercel + Fly.io)

**Date:** 2026-09-22
**Status:** Accepted
**Context:** The system needs both B2B gateway functions (short-lived, high-concurrency) and long-running AI/ML pipelines (VTON, recommendations, price scraping).

**Decision:** Use Vercel for B2B gateway (serverless, 30s max) and Fly.io for Drishti FastAPI (persistent, long-running).

**Consequences:**
- ✅ Vercel handles high-concurrency B2B traffic efficiently
- ✅ Fly.io handles long-running GPU inference and scraping
- ❌ Two separate codebases to maintain
- ❌ Cross-backend communication adds latency
- ❌ Different deployment pipelines

---

## ADR-002: In-Memory Fallback for Checkout

**Date:** 2026-09-22
**Status:** Accepted (Technical Debt)
**Context:** Supabase checkout schema (`supabase_unified_checkout.sql`) has 8 tables defined but NOT deployed. Cart/checkout needs to work immediately.

**Decision:** Use Python dict-based in-memory storage as fallback when Supabase tables don't exist.

**Consequences:**
- ✅ Checkout works immediately without schema deployment
- ✅ Full E2E flow verified (cart → order → commission split)
- ❌ Data lost on Vercel cold starts
- ❌ Not suitable for production use
- ❌ Requires schema deployment to fix

---

## ADR-003: API Key Hardcoded in Client-Side JS

**Date:** 2026-09-22
**Status:** Accepted (Security Debt)
**Context:** Brand dashboard needs to authenticate with the B2B gateway. No OAuth flow exists for brand users.

**Decision:** Hardcode API key in `brand-dashboard.js` for Zara brand.

**Consequences:**
- ✅ Dashboard works immediately
- ❌ API key exposed in client-side code
- ❌ Any user can impersonate Zara
- ❌ No key rotation mechanism

---

## ADR-004: Marketplace-First Recommendations (Drishti)

**Date:** 2026-09-22
**Status:** Accepted
**Context:** Need product recommendations but don't have a comprehensive product catalog.

**Decision:** Use Google Shopping via SerpApi as primary recommendation source, with direct marketplace scrapers as fallback.

**Consequences:**
- ✅ Access to millions of products without catalog management
- ✅ Real-time pricing and availability
- ❌ Dependency on SerpApi (rate limits, cost)
- ❌ Scraping may violate marketplace ToS
- ❌ Inconsistent product data quality

---

## ADR-005: Deterministic Fashion Scoring (No LLM in Hot Path)

**Date:** 2026-09-22
**Status:** Accepted
**Context:** Need fast recommendation scoring that can handle high concurrency.

**Decision:** Use lexicon-based scoring (13 color families, 11 fabrics, 7 fits, 7 patterns, 13 occasions) instead of LLM calls in the hot path.

**Consequences:**
- ✅ Sub-100ms scoring latency
- ✅ Deterministic and reproducible
- ✅ No API costs for scoring
- ❌ Less nuanced than LLM-based scoring
- ❌ Requires manual lexicon maintenance

---

## ADR-006: Three B2B Network Modes

**Date:** 2026-09-22
**Status:** Accepted
**Context:** Different brands have different preferences for how they participate in the network.

**Decision:** Implement three modes: Brand Only (A), Curated Network (B), Open Network (C).

**Consequences:**
- ✅ Flexible participation model
- ✅ Brands control their exposure
- ❌ Complex permission logic
- ❌ Harder to debug recommendation issues

---

## ADR-007: Two-Sided Permission System

**Date:** 2026-09-22
**Status:** Accepted
**Context:** Need to balance advertiser targeting with host brand control.

**Decision:** Advertiser targeting never overrides host permission. Host can exclude any brand/category.

**Consequences:**
- ✅ Host brands maintain control
- ✅ Prevents unwanted product placement
- ❌ Advertisers may not reach desired audiences
- ❌ Complex eligibility checking

---

## ADR-008: Sponsored Boost Cap at 15%

**Date:** 2026-09-22
**Status:** Accepted
**Context:** Need to monetize through sponsored placements without degrading recommendation quality.

**Decision:** Cap sponsored boost at 15% of organic score.

**Consequences:**
- ✅ Revenue from sponsored placements
- ✅ Recommendation quality preserved
- ✅ Organic scores still dominate ranking
- ❌ Advertisers may want higher visibility
- ❌ Need to tune boost weights

---

## ADR-009: Epsilon-Greedy Exploration (18%)

**Date:** 2026-09-22
**Status:** Accepted
**Context:** Need to ensure brand fairness in recommendations and prevent winner-take-all dynamics.

**Decision:** Use 18% epsilon-greedy exploration rate in multi-armed bandit.

**Consequences:**
- ✅ New brands get exposure
- ✅ Prevents ranking staleness
- ❌ 18% of recommendations are suboptimal
- ❌ Exploration items may not convert well

---

## ADR-010: Shopify Theme as Frontend Host

**Date:** 2026-09-22
**Status:** Accepted
**Context:** Need a frontend that integrates seamlessly with the Shopify ecosystem.

**Decision:** Use Shopify theme (Liquid templates + JS/CSS assets) as the frontend host.

**Consequences:**
- ✅ Native Shopify integration
- ✅ CDN-hosted assets
- ✅ Checkout integration available
- ❌ Limited to Shopify's rendering model
- ❌ Liquid templating is restrictive
- ❌ No SSR for dynamic content
