# Codebase Audit Report

> **Date:** 2026-09-22 | **Version:** 1.0.0

## Executive Summary

The My Narrative Commerce Network is a **B2B fashion recommendation and advertising network** spanning 3 repositories, 7 deployment targets, 97+ architectural entities, and 40+ database tables. The system is functional but has significant technical debt in security, code duplication, and deployment gaps.

## Repository Inventory

| Repository | Files | Lines | Purpose |
|---|---|---|---|
| mynarrative-ai (Vercel) | 80+ | 15,000+ | B2B gateway, recommendations, checkout, dashboard |
| drishti (Fly.io) | 100+ | 25,000+ | VTON, price comparison, user auth, catalog |
| imageless_test (Shopify) | 150+ | 60,000+ | Theme, dashboard SPA, AI stylist wizard |
| **Total** | **330+** | **100,000+** | — |

## Architecture Summary

```
Customer Browser
    ├── Shopify Theme (mynarrative.store)
    │   ├── Brand Dashboard SPA
    │   └── AI Stylist Wizard
    │
    ├── Vercel Backend (drishti-api-blond.vercel.app)
    │   ├── B2B Gateway (35 endpoints)
    │   ├── Recommendation Engine (12 stages)
    │   ├── Checkout System (in-memory fallback)
    │   └── Dashboard API
    │
    ├── Fly.io Backend (drishti-api.fly.dev)
    │   ├── VTON Pipeline (Replicate + face preservation)
    │   ├── Price Comparison (5 platforms)
    │   ├── User Auth (OTP + JWT)
    │   ├── Catalog Sync (Shopify → Qdrant)
    │   └── Admin System
    │
    ├── Fly.io Qdrant (vector DB)
    ├── Modal GPU (CatVTON)
    └── Supabase (PostgreSQL)
```

## Entity Inventory

| Type | Count | Examples |
|---|---|---|
| Systems | 20 | SYS-001 (Recommendation Engine), SYS-002 (VTON Pipeline) |
| Features | 32 | FEAT-001 (Cross-Brand Ranking), FEAT-006 (Single Garment VTON) |
| Projects | 8 | PRJ-001 (Vercel Backend), PRJ-002 (Fly.io Backend) |
| Integrations | 22 | INT-001 (OpenAI), INT-002 (Replicate), INT-004 (Supabase) |
| APIs | 9 | API-001 (B2B Gateway), API-005 (Drishti FastAPI) |
| Database Tables | 40 | DB-001 (Brands), DB-004 (Brand Products), DB-039 (VTON Jobs) |
| **Total** | **131** | — |

## API Surface

| Gateway | Endpoints | Auth | Status |
|---|---|---|---|
| B2B Gateway (Vercel) | 35 | API key | ✅ Working |
| Syndicate Gateway | 9 | API key | ✅ Working |
| Secondary Gateway | 11 | None | ⚠️ Legacy |
| Creator Economy API | 15 | Various | ✅ Working |
| Drishti FastAPI | 45 | JWT + admin | ✅ Working |
| VTOE GPU Server | 4 | None (internal) | ✅ Working |
| Modal VTON | 1 | None (internal) | ✅ Working |
| Admin Analytics | 4 | Prometheus | ✅ Working |
| Shopify Sync | 3 | ADMIN_SECRET | ✅ Working |
| **Total** | **127** | — | — |

## Database Inventory

| Database | Tables | Status |
|---|---|---|
| Supabase (Vercel) | 28 | ⚠️ Most empty or missing |
| Supabase (Fly.io) | 10 | ✅ Populated |
| Qdrant | 1 | ✅ Populated |
| **Total** | **39** | — |

## External Service Dependencies

| Service | Used By | Status |
|---|---|---|
| OpenAI | Recommendation, Analysis | ✅ Configured |
| Replicate | VTON, Garment Extraction | ✅ Configured |
| Supabase | Database | ✅ Configured |
| Cloudflare R2 | Image Storage | ✅ Configured |
| Shopify | Product Sync | ✅ Configured |
| SerpApi | Price Comparison | ✅ Configured |
| Stripe | Payments | ✅ Configured |
| Razorpay | Payments (India) | ❌ NOT SET |
| AWS Rekognition | Content Moderation | ✅ Configured |
| AWS S3 | Image Storage | ✅ Configured |
| Qdrant | Vector Search | ✅ Configured |
| Redis | Rate Limiting | ✅ Configured |
| Modal | GPU Workers | ✅ Configured |
| OpenWeatherMap | Weather Data | ✅ Configured |
| Sentry | Error Tracking | ✅ Configured |

## Security Assessment

### Critical Issues
1. **API key hardcoded in client-side JS** (`brand-dashboard.js`)
2. **Supabase credentials exposed in `window.ENV`**
3. **Service role key in source code** (`checkout_api.py:17`)
4. **No rate limiting on secondary gateway**
5. **Wide-open CORS on `api-secondary/`**

### Positive Findings
- ✅ Bot detection on B2B gateway (blocks curl)
- ✅ HMAC verification on Shopify webhooks
- ✅ JWT authentication on user endpoints
- ✅ API key authentication on B2B endpoints
- ✅ Sentry for error tracking

## Performance Characteristics

| Metric | Value | Notes |
|---|---|---|
| B2B Gateway timeout | 30s | Vercel max |
| Fly.io health check | 30s interval | Always-on (1 machine) |
| VTON polling timeout | 120s | Replicate prediction |
| Modal GPU timeout | 600s | CatVTON worker |
| Exploration rate | 18% | Epsilon-greedy |
| Sponsored boost cap | 15% | Max ranking boost |
| Embedding dimension | 1536 | OpenAI text-embedding-3-small |
| Qdrant embedding | 384 | BAAI/bge-small-en-v1.5 |

## Recommendations

### Immediate (This Week)
1. Deploy Supabase checkout schema (TD-001)
2. Set Razorpay env vars (TD-002)
3. Create Shopify checkout pages (TD-003)

### Short-Term (This Month)
4. Move API key to server-side auth (TD-004)
5. Consolidate duplicate `_sb_request()` implementations (TD-010)
6. Add rate limiting to secondary gateway (TD-007)
7. Fix CORS on `api-secondary/` (TD-008)

### Long-Term (This Quarter)
8. Consolidate duplicate creator economy code (TD-012)
9. Implement SQL migration versioning (TD-013)
10. Add comprehensive test coverage
11. Implement OAuth for brand dashboard authentication

## Documentation Created

| Document | Location | Purpose |
|---|---|---|
| README | `docs/README.md` | Project overview and quick start |
| Entity Registry | `docs/registries/registry.yaml` | Machine-readable entity inventory |
| System Passports | `docs/passports/` | 6 detailed system specs |
| Architecture Diagrams | `docs/diagrams/data-flows.md` | 6 Mermaid flow diagrams |
| Deployment Map | `docs/deployment/INFRASTRUCTURE.md` | Infrastructure and env vars |
| ADRs | `docs/adrs/ADR-001-through-ADR-010.md` | 10 architecture decisions |
| Changelog | `docs/changelogs/CHANGELOG.md` | Version history |
| Technical Debt | `docs/TECHNICAL_DEBT.md` | 20 tracked debt items |
| AGENTS.md | `AGENTS.md` | AI agent instructions |
| CONTRIBUTING.md | `CONTRIBUTING.md` | Contribution guidelines |
| CODEOWNERS | `CODEOWNERS` | Code ownership |
