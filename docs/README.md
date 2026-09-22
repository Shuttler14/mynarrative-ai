# My Narrative Commerce Network — Documentation

> **Version:** 1.0.0 | **Last Updated:** 2026-09-22

## What Is This?

My Narrative is a **B2B fashion recommendation and advertising network**. It connects fashion brands through an AI-powered recommendation engine, virtual try-on technology, and a unified checkout system.

**In plain English:** A fashion brand (like Zara) installs our widget. When a customer browses Zara's site, our AI recommends complementary products from partner brands (like H&M), lets the customer virtually try them on, and handles the entire checkout — all within Zara's website.

## Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CUSTOMER BROWSER                             │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │  Shopify Theme   │  │  AI Stylist      │  │  Brand Dashboard │  │
│  │  (mynarrative.   │  │  Wizard (v4)     │  │  (SPA)           │  │
│  │   store)         │  │                  │  │                  │  │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘  │
└───────────┼──────────────────────┼──────────────────────┼────────────┘
            │                      │                      │
            ▼                      ▼                      ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      API GATEWAY LAYER                               │
│                                                                      │
│  ┌─────────────────────┐    ┌─────────────────────────────────────┐  │
│  │  Vercel (B2B GW)    │    │  Fly.io (Drishti FastAPI)           │  │
│  │  b2b_gateway.py     │    │  api/main.py                        │  │
│  │                     │    │                                     │  │
│  │  /api/recommend     │    │  /api/reco/outfits                  │  │
│  │  /api/checkout      │    │  /api/vton/try-on                   │  │
│  │  /api/dashboard/*   │    │  /api/catalog/*                     │  │
│  │  /api/sponsored/*   │    │  /api/pricing/compare               │  │
│  │  /api/brand/*       │    │  /api/user/*                        │  │
│  │  /api/design/*      │    │  /api/analysis/*                    │  │
│  │  /api/closet/*      │    │  /api/admin/*                       │  │
│  │  /api/subscription/*│    │  /api/weather/*                     │  │
│  └────────┬────────────┘    └──────────┬──────────────────────────┘  │
└───────────┼─────────────────────────────┼────────────────────────────┘
            │                             │
            ▼                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     AI/ML PIPELINE LAYER                             │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  Recommendation Engine (12 stages)                            │  │
│  │  intent → filter → knowledge_graph → embeddings → scoring →   │  │
│  │  exploration → explainability → eligibility → cross_ranking   │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  VTON Pipeline                                                │  │
│  │  garment_extract → IDM-VTON → face_preservation → quality     │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  Price Comparison Pipeline                                    │  │
│  │  SerpApi → Direct Scrapers → Card Offers → Budget Intel       │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
            │                             │
            ▼                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     DATA & STORAGE LAYER                             │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  Supabase    │  │  Qdrant      │  │  Cloudflare  │              │
│  │  PostgreSQL  │  │  Vector DB   │  │  R2 Storage  │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐                                 │
│  │  Redis       │  │  Shopify     │                                 │
│  │  (Rate Limit)│  │  Admin API   │                                 │
│  └──────────────┘  └──────────────┘                                 │
└──────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     EXTERNAL SERVICES                                │
│                                                                      │
│  OpenAI  │  Replicate  │  SerpApi  │  Stripe  │  Razorpay          │
│  AWS     │  Modal       │  Shopify  │  Sentry  │  OpenWeatherMap    │
└──────────────────────────────────────────────────────────────────────┘
```

## Repositories

| Repository | Description | URL |
|---|---|---|
| **mynarrative-ai** | Vercel backend (B2B gateway, recommendations, checkout, dashboard) | [GitHub](https://github.com/Shuttler14/mynarrative-ai) |
| **drishti** | Fly.io FastAPI backend (VTON, price comparison, user auth, catalog) | Local: `/Users/shuttler/Desktop/Drishti/` |
| **imageless_test** | Shopify theme (mynarrative.store) | [GitHub](https://github.com/Shuttler14/imageless_test) |

## Deployment Targets

| Target | Provider | URL | Status |
|---|---|---|---|
| B2B Gateway | Vercel | `drishti-api-blond.vercel.app` | ✅ Active |
| Main API | Fly.io | `drishti-api.fly.dev` | ✅ Active |
| Qdrant | Fly.io | (internal) | ✅ Active |
| Frontend | Shopify | `mynarrative.store` | ✅ Active |
| VTON GPU | Modal | `vton.mynarrative.in` | ✅ Active |
| Database | Supabase | `fmganuxtqbquubtvvqdo.supabase.co` | ✅ Active |

## Key Documentation

| Document | Location | Purpose |
|---|---|---|
| **Entity Registry** | `docs/registries/registry.yaml` | Machine-readable registry of all 97 entities |
| **System Passports** | `docs/passports/` | Detailed specs for each system |
| **Architecture Diagrams** | `docs/diagrams/` | Mermaid diagrams for data flows |
| **Deployment Map** | `docs/deployment/` | Infrastructure and deployment details |
| **ADRs** | `docs/adrs/` | Architecture Decision Records |
| **Changelog** | `docs/changelogs/CHANGELOG.md` | Version history |

## Quick Start

### For AI Agents
1. Read `AGENTS.md` for coding conventions and constraints
2. Check `docs/registries/registry.yaml` for entity IDs
3. Consult system passports in `docs/passports/` for detailed specs
4. Run `make lint` and `make typecheck` before committing

### For Developers
1. Clone the relevant repository
2. Copy `.env.example` to `.env` and fill in credentials
3. Install dependencies: `pip install -r requirements.txt`
4. Run tests: `pytest tests/`

### For DevOps
1. Check `docs/deployment/` for infrastructure details
2. Review `docs/deployment/INFRASTRUCTURE.md` for all deployment targets
3. Check environment variables in each system passport

## Business Model

| Metric | Value |
|---|---|
| Platform commission | 10% |
| Host affiliate commission | 7% |
| Free shipping threshold | ₹999 |
| GST | 18% |
| Sponsored boost cap | 15% |
| Exploration rate | 18% (epsilon-greedy) |

## Currency Support

INR (base), USD, GBP, EUR, AED, AUD

## Support

- Issues: [GitHub Issues](https://github.com/Shuttler14/mynarrative-ai/issues)
- Dashboard: `mynarrative.store/pages/brand-dashboard`
