# AGENTS.md — AI Agent Instructions

> **Version:** 1.0.0 | **Last Updated:** 2026-09-22

## Quick Start for AI Agents

1. **Read the entity registry** at `docs/registries/registry.yaml` for system/feature/API IDs
2. **Consult system passports** in `docs/passports/` for detailed specs
3. **Check architecture diagrams** in `docs/diagrams/` for data flows
4. **Read `docs/CHANGE_TRACKING.md`** before making any changes — assign a Change ID
5. **Follow coding conventions** below
6. **Run lint and typecheck** before committing

## Coding Conventions

### Python (Vercel Backend)

```python
# Import style
from api.core.supabase import sb_request  # Use shared helper
# NOT: duplicate _sb_request() implementations

# Error handling
try:
    result = sb_request("GET", "table_name", params={...})
except Exception as e:
    return {"error": str(e)}, 500

# Response format
return {"data": result}, 200  # NOT: {"result": result}
return {"error": "message"}, 400  # NOT: {"message": "error"}
```

### Python (Fly.io Drishti)

```python
# FastAPI style
from fastapi import APIRouter, Depends, HTTPException
router = APIRouter()

@router.get("/endpoint")
async def handler(db: AsyncSession = Depends(get_db)):
    ...
    return {"data": result}
```

### JavaScript (Shopify Theme)

```javascript
// Widget API calls
var API = 'https://drishti-api.fly.dev';  // Fly.io for recommendations
// NOT: var VERCEL_API for recommendations

// Dashboard API calls
fetch('/api/dashboard/overview', {
    headers: { 'X-API-Key': MN_API_KEY }
})
```

## Entity ID Format

All entities use the format `TYPE-NNN`:
- `SYS-NNN` — Systems
- `FEAT-NNN` — Features
- `PRJ-NNN` — Projects
- `INT-NNN` — Integrations
- `API-NNN` — APIs
- `DB-NNN` — Database tables

## Critical Constraints

### DO NOT MODIFY
- `api-secondary/app.py` — Existing VTON model is PERMANENTLY LOCKED
- Fly.io secrets — Use `fly secrets set` for changes
- Supabase service role key — Never expose in logs or errors

### ALWAYS CHECK
- `docs/registries/registry.yaml` before creating new entities
- `docs/passports/` for system-specific constraints
- Existing code patterns before adding new modules

### NEVER
- Hardcode API keys in client-side code (use env vars)
- Create duplicate `_sb_request()` implementations
- Use `else:` blocks before public routes in `b2b_gateway.py`
- Query `host_preferences` with `id` column (it doesn't exist)
- Query `brand_products` with `brand_id` column (use `brand` text field)
- Delete or overwrite rows in `narrative_commission_ledger` (immutable append-only)
- Reuse click_ids (they are permanent, never recycled)
- Modify `api/attribution.py` commission logic without code review (CRITICAL)

## File Locations

| What | Where |
|---|---|
| Vercel backend | `mynarrative-ai - Copy (3)/api/` |
| Fly.io backend | `/Users/shuttler/Desktop/Drishti/api/` |
| Shopify theme | `current - Copy (3)/` |
| Entity registry | `docs/registries/registry.yaml` |
| System passports | `docs/passports/` |
| Architecture docs | `docs/diagrams/` |
| Deployment docs | `docs/deployment/` |
| ADRs | `docs/adrs/` |

## Testing

```bash
# Vercel backend
cd mynarrative-ai\ -\ Copy\ \(3\)/
python -m pytest tests/ -v

# Fly.io backend
cd /Users/shuttler/Desktop/Drishti/
python -m pytest tests/ -v

# Lint
ruff check api/
mypy api/
```

## Environment Variables

See `docs/deployment/INFRASTRUCTURE.md` for complete list.

**Critical (must be set):**
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (Vercel)
- `DATABASE_URL`, `QDRANT_URL`, `REDIS_URL`, `JWT_SECRET` (Fly.io)
- `OPENAI_API_KEY`, `REPLICATE_API_TOKEN` (both)
- `SHOPIFY_ACCESS_TOKEN`, `SHOPIFY_WEBHOOK_SECRET` (both)

**Missing (blocks features):**
- `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET` (Vercel) — Payment verification
