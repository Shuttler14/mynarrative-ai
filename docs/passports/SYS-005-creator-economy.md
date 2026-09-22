# System Passport: Creator Economy Platform

> **ID:** SYS-005 | **Status:** Active | **Maturity:** Production

## Overview

Full creator economy platform with registration, tier progression, commission tracking, design publishing, and print-on-demand fulfillment.

## Architecture

### Creator Tiers

| Tier | Requirement | Benefits |
|---|---|---|
| Bronze | Registration | Base commission |
| Silver | 50 designs sold | Higher commission |
| Gold | 200 designs sold | Priority support |
| Diamond | 1000 designs sold | Premium features |

### Creator Rank System

| Rank | Lifetime Earnings |
|---|---|
| Rookie Designer | <₹50,000 |
| Emerging Talent | ₹50,000 - ₹2,00,000 |
| Trendsetter | ₹2,00,000 - ₹5,00,000 |
| Style Architect | ₹5,00,000 - ₹10,00,000 |
| Platform Icon | >₹10,00,000 |

### Design Publishing Pipeline

```
Creator Uploads Design → AI Generation (FLUX) → Slogan Generation
                                                    ↓
                                              Gang Sheet Generation
                                                    ↓
                                              Shopify Product Creation
                                                    ↓
                                              Design Feed Publication
```

### Print-on-Demand

| Product | Production Cost |
|---|---|
| T-Shirt | ₹500 |
| Hoodie | ₹900 |

## API Endpoints

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/api/design/feed` | GET | None | Browse designs |
| `/api/design/publish` | POST | User | Publish design |
| `/api/design/order-webhook` | POST | None | Order fulfillment |
| `/api/creator/register` | POST | None | Register as creator |
| `/api/creator/earnings` | GET | JWT | View earnings |
| `/api/creator/tiers` | GET | JWT | Tier info |

## Dependencies

- **External:** Replicate (FLUX), Shopify Admin API, AWS Rekognition, AWS S3
- **Database:** Supabase (`creators`, `creator_designs`, `creator_payouts`, `creator_commissions`)
- **Systems:** None

## Known Issues

1. **Duplicate code** — `api/creator_economy.py` AND `creator-economy-api/` have parallel implementations
2. **Supabase Python SDK** — Uses different auth path than other modules (REST)
3. **No KYC verification** — Creator verification not implemented

## Files

| File | Purpose |
|---|---|
| `api/creator_economy.py` | Main creator economy handler |
| `creator-economy-api/` | Standalone API (17 files) |
| `supabase_schema.sql` | Database schema |
