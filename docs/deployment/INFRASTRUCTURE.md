# Infrastructure & Deployment Map

> **Last Updated:** 2026-09-22

## Deployment Targets

### 1. Vercel (Serverless Functions)

| Property | Value |
|---|---|
| Provider | Vercel |
| Runtime | Python 3.11 |
| Max Duration | 30s |
| Projects | B2B Gateway, Proxy, Creator Economy |
| Deploy URL | `drishti-api-blond.vercel.app` |

**Environment Variables (Required):**
```
SUPABASE_URL=https://fmganuxtqbquubtvvqdo.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
OPENAI_API_KEY=sk-...
REPLICATE_API_TOKEN=r8_...
SHOPIFY_ACCESS_TOKEN=shpat_...
SHOPIFY_STORE_URL=https://jjdk0v-0c.myshopify.com
SHOPIFY_WEBHOOK_SECRET=...
STRIPE_SECRET_KEY=sk_...
RAZORPAY_KEY_ID=rzp_... (NOT SET)
RAZORPAY_KEY_SECRET=... (NOT SET)
```

**Routes (vercel.json):**
```json
{
  "functions": {
    "api/b2b_gateway.py": { "maxDuration": 30 }
  },
  "rewrites": [
    { "source": "/api/(.*)", "destination": "/api/b2b_gateway" }
  ]
}
```

### 2. Fly.io (Main API — Drishti)

| Property | Value |
|---|---|
| Provider | Fly.io |
| App Name | `drishti-api` |
| Region | `ams` (Amsterdam) |
| Memory | 1024 MB |
| CPU | shared x1 |
| Min Machines | 1 (always on) |
| Auto-stop | off |
| Health Check | `GET /health` every 30s |
| Concurrency | 80 soft / 100 hard |

**Dockerfile:**
```dockerfile
FROM python:3.12-slim
RUN apt-get install -y gcc libpq-dev curl
COPY libs/py-observability /libs/py-observability
RUN pip install /libs/py-observability
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
RUN alembic upgrade head
CMD ["uvicorn", "api.main:app"]
```

**Environment Variables (from `fly secrets list`):**
```
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=redis://...
QDRANT_URL=http://...
JWT_SECRET=...
SHOPIFY_ACCESS_TOKEN=shpat_...
SHOPIFY_WEBHOOK_SECRET=...
OPENAI_API_KEY=sk-...
REPLICATE_API_TOKEN=r8_...
CORS_ORIGINS=...
OPENWEATHERMAP_API_KEY=...
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
S3_BUCKET=...
SHOPIFY_STORE_URL=https://mynarrative.store
```

### 3. Fly.io (Qdrant Vector DB)

| Property | Value |
|---|---|
| App Name | `drishti-qdrant-moonlit-morning-7709` |
| Image | `qdrant/qdrant:v1.12.0` |
| Region | `ams` |
| Memory | 512 MB |
| Volume | `drishti_qdrant_data` → `/qdrant/storage` |
| Min Machines | 0 (auto-stop) |
| Port | 6333 |

### 4. Shopify (Theme Hosting)

| Property | Value |
|---|---|
| Store | `mynarrative.store` |
| Shopify Domain | `jjdk0v-0c.myshopify.com` |
| Theme ID | `140709101760` |
| Access Token | `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` |

**Asset CDN URLs:**
```
https://mynarrative.store/cdn/shop/t/3/assets/brand-dashboard.css
https://mynarrative.store/cdn/shop/t/3/assets/brand-dashboard.js
https://mynarrative.store/cdn/shop/t/3/assets/MN-stylist-wizard-v4.js
```

### 5. Modal (GPU Worker)

| Property | Value |
|---|---|
| Provider | Modal |
| GPU | T4 |
| Image | NVIDIA CUDA 12.1.1 + Python 3.11 |
| Model | CatVTON-MaskFree (mix-48k-1024) |
| Scaledown | 180s window |
| Timeout | 600s |
| Endpoint | `/v1/try-on` |

### 6. Supabase (Database)

| Property | Value |
|---|---|
| URL | `https://fmganuxtqbquubtvvqdo.supabase.co` |
| Type | PostgreSQL + REST API |
| Auth | Service Role Key (bypasses RLS) |

**Tables (Vercel Supabase):**
- Most tables EMPTY or missing (especially `brand_products`, `brand_catalogs`, `brands`)
- `host_preferences` uses `brand_id` as primary key (no `id` column)
- `brand_products` uses `brand` text field (NOT `brand_id`)

**Tables (Drishti Supabase):**
- 10 tables via SQLAlchemy + Alembic
- Managed by Fly.io backend

### 7. Docker (Microservices)

| Service | Purpose | Location |
|---|---|---|
| shopify-sync-svc | Shopify → Qdrant sync | `services/shopify-sync-svc/` |
| admin-svc | Admin analytics + Grafana | `services/admin-svc/` |

## Network Topology

```
                    ┌─────────────┐
                    │   Customer   │
                    │   Browser    │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ Shopify  │ │ Vercel   │ │ Fly.io   │
        │ Theme    │ │ (B2B GW) │ │ (Drishti)│
        └──────────┘ └────┬─────┘ └────┬─────┘
                          │            │
                   ┌──────┴──────┐     │
                   │             │     │
                   ▼             ▼     ▼
             ┌──────────┐ ┌──────────┐ ┌──────────┐
             │ Supabase │ │ Qdrant   │ │ Modal    │
             │ (Postgres)│ │ (Vector) │ │ (GPU)    │
             └──────────┘ └──────────┘ └──────────┘
```

## Environment Variables Summary

| Variable | Vercel | Fly.io | Purpose |
|---|---|---|---|
| `SUPABASE_URL` | ✅ | — | Database URL |
| `SUPABASE_SERVICE_ROLE_KEY` | ✅ | — | Database admin key |
| `DATABASE_URL` | — | ✅ | PostgreSQL connection |
| `QDRANT_URL` | — | ✅ | Vector DB |
| `REDIS_URL` | — | ✅ | Rate limiting |
| `JWT_SECRET` | — | ✅ | Auth signing |
| `OPENAI_API_KEY` | ✅ | ✅ | AI services |
| `REPLICATE_API_TOKEN` | ✅ | ✅ | GPU inference |
| `SHOPIFY_ACCESS_TOKEN` | ✅ | ✅ | Shopify API |
| `SHOPIFY_WEBHOOK_SECRET` | ✅ | ✅ | Webhook verification |
| `SHOPIFY_STORE_URL` | ✅ | ✅ | Store URL |
| `STRIPE_SECRET_KEY` | ✅ | — | Payments |
| `RAZORPAY_KEY_ID` | ❌ NOT SET | — | Payments (India) |
| `RAZORPAY_KEY_SECRET` | ❌ NOT SET | — | Payments (India) |
| `SERPAPI_KEY` | — | ✅ | Google Shopping |
| `OPENWEATHERMAP_API_KEY` | — | ✅ | Weather data |
| `AWS_*` | ✅ | ✅ | Cloud storage |
| `R2_*` | — | ✅ | Cloudflare R2 |
| `ADMIN_SECRET` | — | ✅ | Admin auth |
| `SMTP_*` | — | ✅ | Email delivery |

## CI/CD

| Workflow | Trigger | Purpose |
|---|---|---|
| `ci.yml` | PR/push to main | Lint (ruff) + type-check (mypy) + tests |
| `ci-images.yml` | — | Docker image builds |
| `ci-terraform.yml` | — | Infrastructure as code |
| `zap-baseline.yml` | — | OWASP ZAP security scan |
| `loadtest.yml` | — | k6 load tests |
