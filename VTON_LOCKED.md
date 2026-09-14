# VTON SYSTEM — FROZEN (Do Not Modify)

## MILESTONE: v2.1.0-vton-locked (Sep 15, 2026)

The VTON (Virtual Try-On) system is **PERMANENTLY LOCKED**.
No further changes to VTON code paths. Future work is recommendation engine only.

## Architecture (Locked)

### VTON Model: `prunaai/p-image-try-on` on Replicate
- **Speed**: ~5.8 seconds per try-on
- **Input**: person image (data URI) + garment image (data URI)
- **Output**: result image URL (Replicate CDN)
- **Model version**: `0e122964dd5d7fce695da14e9206f8dd48c0c5595ecb7e3cf1a4078701fb2665`

### Fallback: `cuuupid/idm-vton` on Replicate
- Used for category-specific try-on (dresses, lower_body)
- Category must be one of: `upper_body`, `lower_body`, `dresses`
- `force_dc=True` only for dresses

### Key Patterns (Proven from Jul 26, 2026)
1. **Data URI download** — Downloads images as base64 data URIs before sending to Replicate (fixes Google Shopping 404s, CDN blocking, expiring R2 URLs)
2. **Garment extraction** — Auto-extracts clean flat-lay from marketplace product photos via `rembg` + post-processing before VTON
3. **Image proxy** — Downloads inaccessible Google Shopping thumbnails and converts to data URIs
4. **429 retry** — Exponential backoff (10s, 20s, 30s) on Replicate rate limits
5. **Category validation** — IDM-VTON category validated against `upper_body/lower_body/dresses`

### Deployment
- **Fly.io**: `https://drishti-api-v2.fly.dev` (region: sin, 512MB RAM, shared CPU)
- **Vercel**: `https://drishti-api-blond.vercel.app` (Vercel Hobby, 60s timeout)
- **Widget**: Calls Fly.io for VTON, proxies other endpoints to Vercel

### Files (DO NOT MODIFY)
- `api-secondary/app.py` — Fly.io Flask app (VTON + weather + body analysis + reco proxy)
- `api-secondary/Dockerfile` — Docker config
- `api-secondary/fly.toml` — Fly.io config
- `api-secondary/requirements.txt` — Python deps

### Environment Variables (Fly.io)
- `REPLICATE_API_TOKEN` — Replicate API token (set via `flyctl secrets set`)
- `OPENAI_API_KEY` — OpenAI API key (for body analysis)
- `TEST_API_KEY` — API key for Vercel proxy

## What Changed (Future Work)

**ONLY recommendation engine improvements** — both B2B and B2C:
- Make recommendations more precise
- Better occasion/style matching
- Improved price tier filtering
- Brand catalog expansion
- Cross-brand syndicate features
- Creator economy features
