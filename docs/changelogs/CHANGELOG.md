# Changelog

## [1.0.0] — 2026-09-22

### Added
- **B2B Recommendation Engine** — 12-stage pipeline with 7-factor scoring
- **Virtual Try-On Pipeline** — IDM-VTON + CatVTON with face preservation
- **Brand Dashboard** — Full SPA with analytics, products, campaigns, partners, wallet
- **Checkout System** — Cross-brand cart, order splitting, commission calculation
- **Creator Economy** — Registration, tiers, commissions, design publishing, print-on-demand
- **Price Comparison** — 5-platform aggregation (Amazon, Flipkart, Myntra, AJIO, Nykaa)
- **AI Stylist Wizard** — Floating widget with 5-step onboarding + VTON
- **Sponsored Campaigns** — 8-section campaign creation with 15% boost cap
- **Knowledge Graph** — 906-line rules engine for fashion intelligence
- **Fashion Taxonomy** — Men (6 categories) + Women (6 categories) with pairing rules
- **Three B2B Network Modes** — Brand Only, Curated Network, Open Network
- **Two-Sided Permission System** — Host control + advertiser targeting
- **Multi-Currency Support** — INR, USD, GBP, EUR, AED, AUD
- **OTP Authentication** — 6-digit OTP with SHA-256 hash
- **Shopify Product Sync** — Admin REST/GraphQL → Qdrant with embeddings
- **Catalog Sync Microservice** — Dedicated sync service with webhook support
- **Admin System** — Dashboard, user management, analytics, catalog sync
- **Weather-Based Recommendations** — OpenWeatherMap integration
- **Body & Style Analysis** — Replicate + OpenAI vision models
- **Observability Stack** — Sentry + Prometheus + OpenTelemetry + structlog
- **CI/CD** — GitHub Actions for lint, type-check, tests, security scans, load tests

### Fixed
- **AI Stylist Wizard routing** — Now always uses Fly.io for recommendations (was routing photo users to Vercel with empty tables)
- **Vercel b2b_gateway.py syntax errors** — Fixed Python syntax errors blocking all API endpoints
- **checkout_api.py IndexError** — Fixed `query.get('key', [None])[0]` crash on empty lists
- **inventory_filter.py _sb_query crash** — Now returns `[]` when Supabase returns error dict
- **Supabase error detection** — `_sb` table check now detects `PGRST205` and `404` errors

### Known Issues
- Supabase checkout schema NOT deployed (8 tables in SQL file)
- `RAZORPAY_KEY_ID`/`RAZORPAY_KEY_SECRET` not set in Vercel
- API key hardcoded in client-side JS (security debt)
- In-memory checkout state lost on Vercel cold starts
- 8+ duplicate `_sb_request()` implementations across modules
- No rate limiting on secondary gateway
- Wide-open CORS on `api-secondary/`
