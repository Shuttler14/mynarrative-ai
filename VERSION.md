# My Narrative — Version History & Deployment Tracker

## Tagging Convention

Every push/deploy MUST follow this pattern:

```
v{MAJOR}.{MINOR}.{PATCH}-{stage}
```

### Version Numbers
- **MAJOR** — Breaking changes, new architecture, database migrations
- **MINOR** — New features, new endpoints, new integrations
- **PATCH** — Bug fixes, config changes, dependency updates

### Stage Tags (appended after version)
- `-dev` — Local development, not deployed
- `-staging` — Deployed to staging/preview
- `-prod` — Deployed to production
- `-rollback` — Reverted to previous version

### Examples
```
v2.1.0-prod     — Feature release, production deploy
v2.1.1-prod     — Bug fix, production deploy
v2.2.0-dev      — New feature, local only
v2.2.0-staging  — New feature, preview deploy
v2.2.0-prod     — New feature, production deploy
v2.2.1-prod     — Hotfix for v2.2.0
```

### Commit Message Convention
```
{type}: {description}

type:
  feat     — New feature
  fix      — Bug fix
  security — Security hardening
  docs     — Documentation only
  refactor — Code restructure (no behavior change)
  perf     — Performance improvement
  test     — Adding tests
  chore    — Build, config, dependency updates
  MILESTONE — Major milestone (use sparingly)

Examples:
  feat: add cross-brand syndicate pricing engine
  fix: VTON category validation for dresses
  security: sanitize error responses in API gateway
  MILESTONE: Lock VTON system — prunaai/p-image-try-on proven working
```

---

## Deployment Log

### v2.1.0-prod — VTON LOCKED (Sep 15, 2026)
**MILESTONE: VTON system permanently frozen.**

| Component | Version | URL | Status |
|---|---|---|---|
| Fly.io API | v2.1.0 | `https://drishti-api.fly.dev` | Running |
| Vercel API | v2.1.0 | `https://drishti-api-blond.vercel.app` | Ready |
| Shopify Theme | v2.1.0 | `https://mynarrative.store` | Live |
| Widget | v2.1.0 | Floating widget on store | Live |

**Commits:**
- API: `b048cf7` docs: VTON_LOCKED.md
- API: `650621f` MILESTONE: Lock VTON system
- API: `5a1cd05` fix: migrate urllib→requests, lazy env vars
- Theme: `e1426f8` MILESTONE: Lock VTON
- Theme: `239fc4c` Fix VTON: 3 frontend bugs

**Tags:**
- API: `v2.1.0-vton-locked`
- Theme: `v2.1.0-vton-locked`, `v4.0-vton-working`, `v4.1-vton-ux-polish`

**What's locked:**
- VTON model: `prunaai/p-image-try-on` (5.8s)
- Fallback: `cuuupid/idm-vton` (category-specific)
- Patterns: data URI download, garment extraction, image proxy, 429 retry
- See `VTON_LOCKED.md` for full details

---

### v2.0.0-prod — B2B + Security (Sep 14, 2026)
**B2B Cross-Brand Syndicate platform with hardened security.**

| Component | Version | URL | Status |
|---|---|---|---|
| Fly.io API | v2.0.0 | `https://drishti-api.fly.dev` | Superseded |
| Vercel API | v2.0.0 | `https://drishti-api-blond.vercel.app` | Superseded |

**Commits:**
- `b447023` feat: B2B Cross-Brand Syndicate platform
- `4f35274` security: fix module-level env vars, health check auth, RLS
- `d44b2b8` feat: World-class recommendation engine — 7-stage pipeline

---

### v1.0.0-prod — Initial Deployment (Sep 8, 2026)
**First working production deployment.**

| Component | Version | URL | Status |
|---|---|---|---|
| Vercel API | v1.0.0 | `https://drishti-api-blond.vercel.app` | Superseded |

**Commits:**
- `a6bd611` initial deployment

---

## Future Releases

When working on recommendation engine improvements, follow this pattern:

1. Create a feature branch (optional for solo dev)
2. Commit with proper type prefix
3. Deploy to preview: `vercel --yes` (no `--prod`)
4. Test on preview URL
5. Deploy to production: `vercel --prod --yes`
6. Tag: `git tag -a v{X}.{Y}.{Z}-prod -m "description"`
7. Push: `git push origin main --tags`
8. Update this VERSION.md with the new entry

### Recommended Next Versions
- `v2.2.0` — Recommendation engine improvements (B2B/B2C)
- `v2.3.0` — Brand catalog expansion
- `v2.4.0` — Cross-brand syndicate refinements
- `v3.0.0` — Major: new architecture or database migration
