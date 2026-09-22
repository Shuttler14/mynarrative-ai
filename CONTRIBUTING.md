# Contributing to My Narrative Commerce Network

> **Version:** 1.0.0 | **Last Updated:** 2026-09-22

## Development Setup

### Prerequisites
- Python 3.11+
- Node.js 18+ (for Shopify theme development)
- Git
- Access to Supabase, Vercel, Fly.io, Shopify

### Repository Setup

```bash
# Clone repositories
git clone https://github.com/Shuttler14/mynarrative-ai.git
git clone https://github.com/Shuttler14/imageless_test.git

# Vercel backend
cd mynarrative-ai
cp .env.example .env  # Fill in credentials
pip install -r requirements.txt

# Fly.io backend
cd /path/to/Drishti
cp .env.example .env  # Fill in credentials
pip install -r requirements.txt
```

## Coding Standards

### Python
- Follow PEP 8
- Use type hints where possible
- Keep functions under 50 lines
- Use shared helpers (`api.core.supabase.sb_request`) instead of duplicating
- Write docstrings for public functions

### JavaScript
- Use `var` for widget code (Shopify theme compatibility)
- Use `const`/`let` for dashboard code (modern browsers)
- Keep functions under 100 lines
- Document API calls with comments

### SQL
- Use snake_case for table/column names
- Always include `created_at` timestamp
- Use UUIDs for primary keys
- Add indexes for frequently queried columns

## Commit Messages

Use conventional commits:
```
feat: add new feature
fix: bug fix
docs: documentation update
refactor: code refactoring
test: add tests
chore: maintenance tasks
```

## Pull Request Process

1. Create a feature branch from `main`
2. Make your changes
3. Run lint and typecheck:
   ```bash
   ruff check api/
   mypy api/
   ```
4. Run tests:
   ```bash
   pytest tests/ -v
   ```
5. Update documentation if needed
6. Submit PR with clear description

## Testing

### Unit Tests
```bash
# Vercel backend
pytest tests/ -v

# Fly.io backend
cd /path/to/Drishti
pytest tests/ -v
```

### Integration Tests
```bash
# Run full E2E test suite
python test_narrative_network.py
```

### Load Tests
```bash
# k6 load tests (Drishti)
cd /path/to/Drishti/loadtest/
k6 run tryon.js
k6 run mixed_smoke.js
```

## Code Review Checklist

- [ ] No hardcoded API keys or secrets
- [ ] No duplicate `_sb_request()` implementations
- [ ] Public routes before auth `else:` blocks in `b2b_gateway.py`
- [ ] Correct column names (no `brand_id` on `brand_products`, no `id` on `host_preferences`)
- [ ] Error handling for all external API calls
- [ ] Documentation updated
- [ ] Tests added/updated
- [ ] Lint and typecheck pass

## Architecture Decisions

All architecture decisions are documented in `docs/adrs/`. Before making significant changes:
1. Check existing ADRs for context
2. Create a new ADR if the change is significant
3. Get approval before implementing

## Entity Registry

When adding new systems, features, or integrations:
1. Check `docs/registries/registry.yaml` for existing IDs
2. Assign the next available ID in the category
3. Update the registry with new entries
4. Create a system passport if it's a new system
