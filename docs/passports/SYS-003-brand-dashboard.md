# System Passport: Brand Dashboard

> **ID:** SYS-003 | **Status:** Active | **Maturity:** Production

## Overview

B2B brand dashboard implemented as a Shopify-hosted SPA. Provides analytics, product management, campaign creation, network partner views, and wallet management. Loads from Shopify CDN with API calls to Vercel backend.

## Architecture

- **Frontend:** Single-page app (`brand-dashboard.js` ~2350 lines + `brand-dashboard.css`)
- **Template:** `page.brand-dashboard.liquid`
- **Backend:** `api/dashboard/__init__.py` (handlers) + `api/b2b_gateway.py` (routing)
- **CDN:** Assets served from `mynarrative.store/cdn/shop/t/3/assets/`

## Dashboard Sections

| Section | API Endpoint | Description |
|---|---|---|
| Overview | `/api/dashboard/overview` | Products, orders, revenue, conversion, VTON saves |
| Products | `/api/dashboard/products` | Product list with status, inventory |
| Analytics | `/api/dashboard/analytics` | Detailed metrics, trends |
| Campaigns | `/api/sponsored/campaigns` | Create/manage sponsored campaigns |
| Network Settings | `/api/dashboard/network-settings` | Tab A: My Website, Tab B: Product Distribution |
| Partners | `/api/dashboard/partners` | Network partner cards + performance table |
| Wallet | `/api/dashboard/wallet` | Balance, transactions |
| Settings | (various) | Brand configuration |

## Campaign Creation (8 Sections)

1. **Campaign** — Name, dates, objective
2. **Products** — Select products to promote
3. **Categories** — Taxonomy targeting (Men: 6 categories, Women: 6 categories)
4. **Distribution** — Where ads appear
5. **Pairing** — Which host brands to appear with
6. **Audience** — Target demographics
7. **Budget** — Daily/total budget, bid strategy
8. **Exclusions** — Brands/categories to exclude

## Dependencies

- **Backend:** Vercel B2B Gateway (`/api/dashboard/*`)
- **Database:** Supabase (`brands`, `brand_products`, `network_events`, `brand_pair_compatibility`)
- **CDN:** Shopify theme assets
- **Auth:** API key in `X-API-Key` header (hardcoded in JS for Zara brand)

## Known Issues

1. **API key hardcoded in client-side JS** — `mn_test_62e9df6e8017487a482b82568de935e02166dce90b3942a4`
2. **Supabase credentials exposed in `window.ENV`**
3. **No rate limiting on dashboard endpoints**

## Files

| File | Purpose |
|---|---|
| `assets/brand-dashboard.js` | SPA logic (~2350 lines) |
| `assets/brand-dashboard.css` | Dark glass theme |
| `templates/page.brand-dashboard.liquid` | Shopify template |
| `api/dashboard/__init__.py` | Backend handlers |
