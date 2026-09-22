# System Passport: Virtual Try-On Pipeline

> **ID:** SYS-002 | **Status:** Active | **Maturity:** Production

## Overview

VTON pipeline using Replicate API with face preservation. Supports single garment and full-look (up to 4 garments) try-on. Includes garment extraction from marketplace photos.

## Architecture

### Pipeline Stages

```
Marketplace Photo → Garment Extraction → Clean Garment Image
                                                ↓
Person Photo → Person Detection → Pose Estimation
                                                ↓
                              VTON (IDM-VTON / CatVTON)
                                                ↓
                              Face Preservation (InsightFace + CodeFormer)
                                                ↓
                              Quality Verification (ArcFace)
                                                ↓
                              Result Image → Cloudflare R2
```

### Engine Options

| Engine | Model | Use Case |
|---|---|---|
| IDM-VTON | `yisol/IDM-VTON` | Primary (Replicate) |
| CatVTON | `zhengchong/CatVTON` | Fallback (Modal GPU) |
| CatVTON-MaskFree | `zhengchong/CatVTON-MaskFree` | Modal serverless |

### Garment Extraction Pipeline

1. Download marketplace image
2. Replicate rembg (background removal)
3. PIL post-processing (morphological cleanup, bounding box crop)
4. White background compositing
5. Upload to Cloudflare R2

### Face Preservation Pipeline

1. YOLO face detection
2. ArcFace face verification
3. InsightFace face swap
4. CodeFormer face restoration
5. Quality scoring (face similarity, garment similarity, pose match)

## API Endpoints

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/api/vton/try-on` | POST | Optional JWT | Create VTON job |
| `/api/vton/widget/try-on` | POST | Optional JWT | Shopify widget endpoint |
| `/api/vton/upload-person` | POST | Optional JWT | Upload person image to R2 |
| `/api/vton/extract-garment` | POST | None | Extract garment from marketplace photo |
| `/api/vton/extract-garment-upload` | POST | None | Extract from uploaded file |
| `/api/vton/job/{job_id}` | GET | None | Get job status |
| `/api/vton/engines` | GET | None | List available engines |
| `/api/vton/batch-try-on` | POST | Optional JWT | Batch VTON (up to 6 garments) |
| `/api/vton/history` | JWT | User's VTON history |

## Dependencies

- **External:** Replicate (IDM-VTON, rembg, face-bounds, CodeFormer), Cloudflare R2
- **Local:** InsightFace (buffalo_l), YOLO (yolov8n.pt), CodeFormer
- **Database:** Supabase (`vton_jobs`, `garment_assets`)
- **Systems:** None (standalone)

## Configuration

| Parameter | Value | Notes |
|---|---|---|
| Max polling time | 120s | Replicate prediction timeout |
| Max batch size | 6 | For batch-try-on |
| Max full-look garments | 4 | For multi-garment try-on |
| Storage | Cloudflare R2 | S3-compatible |
| GPU (Modal) | T4 | For CatVTON |

## Known Issues

1. **CDN access issues** — Images downloaded as base64 data URIs to avoid CDN blocks
2. **No retry on Modal** — Only Replicate has retry logic for 429 errors

## Files

| File | Purpose |
|---|---|
| `api/services/vton_replicate.py` | Replicate VTON service |
| `api/routers/vton.py` | FastAPI router |
| `api/services/garment_extract.py` | Garment extraction |
| `vtoe/` | Full GPU pipeline (5 stages) |
| `modal_vton/app.py` | Modal CatVTON worker |
