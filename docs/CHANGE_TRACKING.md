# Change Tracking System

> **Version:** 1.0.0 | **Last Updated:** 2026-09-22

## Overview

Every change to the codebase must be labeled with a **Change ID** following this system. This enables:
- Quick identification of what broke and why
- Easy revert to previous versions
- Clear ownership and accountability
- Audit trail for compliance

## Change ID Format

```
[TYPE]-[SCOPE]-[SEQUENCE]-[DATE]
```

### Components

| Component | Format | Description |
|---|---|---|
| TYPE | 3-letter code | Type of change |
| SCOPE | 2-4 letter code | Area affected |
| SEQ | 3-digit number | Sequential number within scope |
| DATE | YYMMDD | Date of change |

### TYPE Codes

| Code | Type | Description | Revert Risk |
|---|---|---|---|
| `ADD` | Addition | New file, feature, or endpoint | Low |
| `MOD` | Modification | Edit existing code | Medium |
| `FIX` | Bug Fix | Fix broken behavior | Medium |
| `REF` | Refactor | Restructure without behavior change | High |
| `DEL` | Deletion | Remove file or feature | High |
| `CFG` | Configuration | Env vars, config files | Low |
| `DBM` | Database Migration | Schema changes | High |
| `SEC` | Security | Auth, permissions, secrets | Critical |
| `DEP` | Deployment | Infrastructure changes | Critical |
| `DOC` | Documentation | Docs only | None |

### SCOPE Codes

| Code | Scope | Repository |
|---|---|---|
| `B2B` | B2B Gateway | mynarrative-ai (Vercel) |
| `REC` | Recommendation Engine | mynarrative-ai |
| `CHK` | Checkout System | mynarrative-ai |
| `DAS` | Brand Dashboard | mynarrative-ai + Shopify |
| `CRE` | Creator Economy | mynarrative-ai |
| `VEN` | Vercel Config | mynarrative-ai |
| `DRS` | Drishti API | drishti (Fly.io) |
| `VTO` | Virtual Try-On | drishti |
| `PRC` | Price Comparison | drishti |
| `USR` | User Auth | drishti |
| `CAT` | Catalog Sync | drishti |
| `FLY` | Fly.io Config | drishti |
| `SHO` | Shopify Theme | imageless_test |
| `WIZ` | AI Stylist Wizard | imageless_test |
| `DB` | Database | Supabase |
| `ALL` | Cross-cutting | Multiple repos |

## Change Log

### 2026-09-22

| Change ID | Description | Files | Revert |
|---|---|---|---|
| `ADD-ALL-001-260922` | Create entity registry (138 entities) | `docs/registries/registry.yaml` | Delete file |
| `ADD-ALL-002-260922` | Create project README | `docs/README.md` | Delete file |
| `ADD-ALL-003-260922` | Create system passports (7 systems) | `docs/passports/SYS-*.md` | Delete directory |
| `ADD-ALL-004-260922` | Create architecture diagrams | `docs/diagrams/data-flows.md` | Delete file |
| `ADD-ALL-005-260922` | Create deployment map | `docs/deployment/INFRASTRUCTURE.md` | Delete file |
| `ADD-ALL-006-260922` | Create ADRs (10 decisions) | `docs/adrs/ADR-*.md` | Delete file |
| `ADD-ALL-007-260922` | Create changelog | `docs/changelogs/CHANGELOG.md` | Delete file |
| `ADD-ALL-008-260922` | Create technical debt registry | `docs/TECHNICAL_DEBT.md` | Delete file |
| `ADD-ALL-009-260922` | Create audit report | `docs/AUDIT_REPORT.md` | Delete file |
| `ADD-ALL-010-260922` | Create AGENTS.md | `AGENTS.md` | Delete file |
| `ADD-ALL-011-260922` | Create CONTRIBUTING.md | `CONTRIBUTING.md` | Delete file |
| `ADD-ALL-012-260922` | Create CODEOWNERS | `CODEOWNERS` | Delete file |
| `MOD-ALL-013-260922` | Mark TD-001, TD-003 completed | `docs/TECHNICAL_DEBT.md` | Revert edit |
| `DBM-DB-001-260922` | Deploy checkout schema to Supabase | `supabase_unified_checkout.sql` | DROP TABLE (see below) |
| `ADD-SHO-001-260922` | Create Shopify checkout page | `templates/page.checkout.liquid` | Delete Shopify page |
| `ADD-SHO-002-260922` | Create Shopify order confirmation page | `templates/page.order-confirmation.liquid` | Delete Shopify page |
| `MOD-CHK-002-260922` | Rewrite checkout with Shopify Checkout redirect + host affiliate commission | `api/checkout_api.py` | Revert to previous version |
| `MOD-CHK-004-260922` | SQL migration: add Shopify fields + tracking | `supabase_checkout_migration.sql` | ALTER TABLE DROP COLUMN |
| `MOD-CHK-005-260922` | Wire webhook + order status routes in gateway | `api/b2b_gateway.py` | Revert to previous version |
| `ADD-ALL-014-260922` | Create change tracking system | `docs/CHANGE_TRACKING.md` | Delete file |

## Revert Procedures

### Code Changes (ADD/MOD/FIX/REF)

```bash
# Find the change
git log --oneline --all | grep "CHANGE-ID"

# Revert specific commit
git revert <commit-hash>

# Or revert to file before change
git checkout <commit-hash>^ -- <file-path>
```

### Database Migrations (DBM)

**IMPORTANT:** Database reverts are destructive. Always backup first.

```sql
-- Backup before any migration
CREATE TABLE narrative_cart_backup AS SELECT * FROM narrative_cart;
CREATE TABLE narrative_orders_backup AS SELECT * FROM narrative_orders;
CREATE TABLE narrative_order_items_backup AS SELECT * FROM narrative_order_items;
CREATE TABLE narrative_addresses_backup SELECT * FROM narrative_addresses;

-- Revert: Drop tables (ONLY if you need to rollback)
DROP TABLE IF EXISTS narrative_order_items CASCADE;
DROP TABLE IF EXISTS narrative_orders CASCADE;
DROP TABLE IF EXISTS narrative_cart CASCADE;
DROP TABLE IF EXISTS narrative_addresses CASCADE;

-- Restore from backup (if needed)
-- CREATE TABLE narrative_cart AS SELECT * FROM narrative_cart_backup;
-- ... etc
```

### Shopify Changes (SHO)

```bash
# Via Shopify CLI
shopify page delete checkout
shopify page delete order-confirmation

# Or via Admin: Online Store > Pages > Delete page
```

### Deployment Changes (DEP)

```bash
# Vercel
vercel rollback

# Fly.io
fly releases list
fly rollback <release-id>

# Supabase
# Manual: Dashboard > SQL Editor > run revert SQL
```

### Configuration Changes (CFG)

```bash
# Vercel env vars
vercel env rm <VAR_NAME>
vercel env add <VAR_NAME> <value>

# Fly.io secrets
fly secrets unset <VAR_NAME>
fly secrets set <VAR_NAME>=<value>
```

## Change Template

When making a change, copy this template into your commit message:

```
[CHANGE-ID]: Brief description

Type: ADD|MOD|FIX|REF|DEL|CFG|DBM|SEC|DEP|DOC
Scope: B2B|REC|CHK|DAS|CRE|VEN|DRS|VTO|PRC|USR|CAT|FLY|SHO|WIZ|DB|ALL
Risk: LOW|MEDIUM|HIGH|CRITICAL
Revert: How to revert this change
Files: List of affected files
Tests: How to verify the change works
Rollback Steps: Step-by-step revert procedure
```

## Risk Levels

| Level | Description | Approval Required |
|---|---|---|
| LOW | Documentation, comments, non-functional | Any developer |
| MEDIUM | Code changes, feature additions | Code review |
| HIGH | Refactoring, schema changes, auth changes | Lead developer |
| CRITICAL | Security, production deployments, data migrations | Team lead + backup plan |

## Pre-Change Checklist

Before making any change:

- [ ] Assign Change ID from this document
- [ ] Check if change is in DO NOT MODIFY list (AGENTS.md)
- [ ] Identify affected files
- [ ] Plan revert procedure
- [ ] Write test plan
- [ ] Get approval based on risk level
- [ ] Create backup if HIGH/CRITICAL
- [ ] Update this Change Log after completion

## Change Log

### ADD-CHK-010-260922 — Attribution & Commission SQL Schema
- **Date:** 2026-09-22
- **Type:** ADD (Database Migration)
- **Scope:** CHK (Checkout System)
- **Risk:** CRITICAL
- **Files:** `supabase_attribution_system.sql`
- **Description:** Complete SQL schema for attribution and commission tracking. 9 tables: narrative_product_registry, narrative_clicks, narrative_attribution_events, narrative_commission_ledger, narrative_merchant_orders, narrative_reconciliation_log, narrative_pixel_events, narrative_settlements, narrative_abandoned_checkouts. 3 RPC functions.
- **Revert:** `DROP TABLE IF EXISTS narrative_product_registry, narrative_clicks, narrative_attribution_events, narrative_commission_ledger, narrative_merchant_orders, narrative_reconciliation_log, narrative_pixel_events, narrative_settlements, narrative_abandoned_checkouts CASCADE;`

### ADD-CHK-011-260922 — Attribution Engine
- **Date:** 2026-09-22
- **Type:** ADD (New Module)
- **Scope:** CHK (Checkout System)
- **Risk:** CRITICAL
- **Files:** `api/attribution.py`
- **Description:** Core attribution engine with Product Registry, Click Tracking, Attribution Engine (last-eligible-click + 30-day window), Commission Ledger (immutable, line-item), Commission Lifecycle (PENDING → CONFIRMED → PAYABLE → PAID), Reconciliation, Refund processing.
- **Revert:** Delete `api/attribution.py`, drop SQL tables

### ADD-CHK-012-260922 — Tracking & Merchant Pixel
- **Date:** 2026-09-22
- **Type:** ADD (New Module)
- **Scope:** CHK (Checkout System)
- **Risk:** HIGH
- **Files:** `api/tracking.py`
- **Description:** Tracking redirect endpoint (go.mynarrative.store/c/{click_id}), click recording from widget, merchant pixel receiver (Shopify Web Pixel events), product registration batch endpoint.
- **Revert:** Delete `api/tracking.py`

### ADD-CHK-013-260922 — Shopify Web Pixel
- **Date:** 2026-09-22
- **Type:** ADD (New File)
- **Scope:** CHK (Checkout System)
- **Risk:** HIGH
- **Files:** `api/merchant_pixel.js`
- **Description:** Shopify Web Pixel extension for merchant stores. Captures product_viewed, product_added_to_cart, checkout_started, checkout_completed events. Re-links to MN click_id via UTM params or localStorage.
- **Revert:** Delete `api/merchant_pixel.js`

### ADD-CHK-014-260922 — 6-Hour Reconciliation Cron
- **Date:** 2026-09-22
- **Type:** ADD (New File)
- **Scope:** CHK (Checkout System)
- **Risk:** HIGH
- **Files:** `api/cron_reconciliation.py`
- **Description:** 6-hour reconciliation cron job. Advances PENDING → CONFIRMED, CONFIRMED → PAYABLE, checks for discrepancies.
- **Revert:** Delete `api/cron_reconciliation.py`, remove cron from vercel.json

### MOD-CHK-015-260922 — Gateway Routes for Attribution
- **Date:** 2026-09-22
- **Type:** MOD (Modification)
- **Scope:** CHK (Checkout System)
- **Risk:** HIGH
- **Files:** `api/b2b_gateway.py`, `vercel.json`
- **Description:** Added tracking, attribution, and commission routes to b2b_gateway.py. Added cron job and rewrites to vercel.json.
- **Revert:** Revert b2b_gateway.py and vercel.json to previous version
