# Technical Debt Registry

> **Last Updated:** 2026-09-22

## Critical (Blocks Production)

| ID | Issue | Impact | Effort | Status |
|---|---|---|---|---|
| TD-001 | Supabase checkout schema NOT deployed | Cart/orders lost on cold start | 1 hour | ✅ COMPLETED (2026-09-22) |
| TD-002 | `RAZORPAY_KEY_ID`/`RAZORPAY_KEY_SECRET` not set | Payment verification fails | 5 min | BLOCKED (need keys) |
| TD-003 | Shopify checkout/order-confirmation pages not created | Checkout flow broken | 15 min | ✅ COMPLETED (2026-09-22) |

## High (Security/Reliability)

| ID | Issue | Impact | Effort | Status |
|---|---|---|---|---|
| TD-004 | API key hardcoded in `brand-dashboard.js` | Anyone can impersonate Zara | 2 hours | TECH DEBT |
| TD-005 | Supabase credentials exposed in `window.ENV` | Credential leak | 1 hour | TECH DEBT |
| TD-006 | Hardcoded service role key in `checkout_api.py:17` | Bypasses RLS | 30 min | TECH DEBT |
| TD-007 | No rate limiting on secondary gateway | DDoS vulnerability | 2 hours | TECH DEBT |
| TD-008 | Wide-open CORS on `api-secondary/` | Origin bypass | 30 min | TECH DEBT |
| TD-009 | In-memory checkout state lost on cold start | Data loss | 2 hours | TECH DEBT |

## Medium (Code Quality)

| ID | Issue | Impact | Effort | Status |
|---|---|---|---|---|
| TD-010 | 8+ duplicate `_sb_request()` implementations | Maintenance nightmare | 4 hours | TECH DEBT |
| TD-011 | Two parallel API gateways (b2b_gateway + api-secondary) | Inconsistent security | 8 hours | TECH DEBT |
| TD-012 | Duplicate creator economy code (2 locations) | Unclear which is active | 4 hours | TECH DEBT |
| TD-013 | No SQL migration versioning | Overlapping table definitions | 4 hours | TECH DEBT |
| TD-014 | Broken import in `cross_ranking.py` | Dead code | 30 min | TECH DEBT |
| TD-015 | `maxDuration: 30` but pipelines can exceed 30s | Timeout errors | 2 hours | TECH DEBT |

## Low (Documentation/Cleanup)

| ID | Issue | Impact | Effort | Status |
|---|---|---|---|---|
| TD-016 | No AGENTS.md for AI agents | Inconsistent agent behavior | 1 hour | COMPLETED |
| TD-017 | No CONTRIBUTING.md | Unclear contribution process | 1 hour | COMPLETED |
| TD-018 | No entity registry | Can't track system dependencies | 2 hours | COMPLETED |
| TD-019 | No architecture decision records | Lost context on decisions | 2 hours | COMPLETED |
| TD-020 | No deployment map | Hard to onboard new devs | 1 hour | COMPLETED |

## Vercel Supabase Table Status

| Table | Status | Notes |
|---|---|---|
| `brands` | EMPTY | Needs seeding |
| `brand_products` | EMPTY | Needs seeding |
| `brand_catalogs` | EMPTY | Needs seeding |
| `host_preferences` | EXISTS | Uses `brand_id` as PK (no `id` column) |
| `brand_dna` | EXISTS | — |
| `product_dna` | EXISTS | — |
| `brand_exclusions` | EXISTS | — |
| `brand_pair_compatibility` | EXISTS | — |
| `sponsored_campaigns` | EXISTS | — |
| `network_events` | EXISTS | — |
| `narrative_cart` | ✅ DEPLOYED | 2026-09-22 |
| `narrative_orders` | ✅ DEPLOYED | 2026-09-22 |
| `narrative_order_items` | ✅ DEPLOYED | 2026-09-22 |
| `narrative_addresses` | ✅ DEPLOYED | 2026-09-22 |

## Resolution Priority

1. ~~**Deploy Supabase checkout schema** (TD-001)~~ — ✅ DONE
2. **Set Razorpay env vars** (TD-002) — Enables payment verification
3. ~~**Create Shopify pages** (TD-003)~~ — ✅ DONE
4. **Move API key to server-side** (TD-004) — Fixes security vulnerability
5. **Consolidate `_sb_request()`** (TD-010) — Reduces maintenance burden
