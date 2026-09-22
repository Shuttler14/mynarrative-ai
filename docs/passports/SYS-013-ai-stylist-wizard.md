# System Passport: AI Stylist Wizard

> **ID:** SYS-013 | **Status:** Active | **Maturity:** Production

## Overview

Floating widget for customer-facing outfit recommendations and virtual try-on. Implements a 5-step onboarding flow and generates outfit recommendations using the Fly.io backend.

## Architecture

### Frontend Components

| File | Purpose |
|---|---|
| `assets/MN-stylist-wizard-v4.js` | Main widget logic |
| `assets/MN-stylist-wizard-v4.css` | Widget styles |

### Backend Dependencies

| Endpoint | Backend | Purpose |
|---|---|---|
| `/api/reco/outfits` | Fly.io | Product recommendations (global inventory) |
| `/api/vton/try-on` | Fly.io | Virtual try-on |
| `/api/vton/upload-person` | Fly.io | Photo upload for VTON |

### Onboarding Flow (5 Steps)

1. **Gender Selection** — Men / Women / Other
2. **Budget Selection** — Value / Mid-Range / Premium / Luxury
3. **Occasion Selection** — Casual / Formal / Party / Wedding / etc.
4. **Style Preferences** — Minimalist / Streetwear / Boho / Classic / etc.
5. **Photo Upload** — Optional (for VTON later)

### Widget Modes

| Mode | Description |
|---|---|
| Mini Mode | Collapsed floating button |
| Full Mode | Expanded wizard with onboarding + recommendations |
| VTON Mode | Virtual try-on display |

## API Flow

```
Customer opens widget
  → 5-step onboarding (collects preferences)
  → POST /api/reco/outfits (Fly.io) with preferences
  → Display outfit recommendations with prices
  → Customer clicks "Try On"
    → POST /api/vton/upload-person (if no photo yet)
    → POST /api/vton/try-on (Fly.io)
    → Display VTON result
  → Customer clicks "Add to Cart"
    → POST /api/checkout/cart (Vercel)
    → Cart updated
```

## Configuration

| Variable | Value | Notes |
|---|---|---|
| `API` | `https://drishti-api.fly.dev` | Fly.io backend |
| `VERCEL_API` | `https://drishti-api-blond.vercel.app` | Vercel backend (unused now) |
| `MN_API_KEY` | From `window.ENV` | For checkout |

## Dependencies

- **Backend:** Fly.io (recommendations + VTON)
- **Backend:** Vercel (checkout/cart)
- **Database:** Supabase (via Fly.io global inventory)

## Known Issues

1. **Previously routed photo users to Vercel `/api/recommend`** — Now fixed to always use Fly.io inventory
2. **No error handling for failed VTON** — Widget doesn't gracefully handle Replicate failures
3. **No loading states for long VTON operations** — Can take 30-60s

## Files

| File | Purpose |
|---|---|
| `assets/MN-stylist-wizard-v4.js` | Widget logic |
| `assets/MN-stylist-wizard-v4.css` | Widget styles |
