# System Passport: Price Comparison Aggregator

> **ID:** SYS-006 | **Status:** Active | **Maturity:** Production

## Overview

Cross-platform price comparison engine covering Amazon, Flipkart, Myntra, AJIO, and Nykaa. Uses SerpApi (Google Shopping) as primary source with direct marketplace scrapers as fallback.

## Architecture

### Data Sources

| Source | Method | Priority | Notes |
|---|---|---|---|
| Google Shopping (SerpApi) | API | Primary | Covers all 5 platforms in one call |
| Amazon.in | HTML scraping | Fallback | ASIN extraction |
| Flipkart.com | JSON + HTML | Fallback | `__INITIAL_STATE__` |
| Myntra.com | HTML | Fallback | `window.__myx` |
| AJIO.com | HTML | Fallback | Script tag parsing |
| NykaaFashion.com | HTML | Fallback | `__NEXT_DATA__` |

### Pipeline

```
Product Request → SerpApi Search → Parse Results
                                      ↓
                        Sufficient? → Yes → Rank + Return
                                      ↓ No
                        Direct Scrapers → Amazon + Flipkart + Myntra + AJIO + Nykaa
                                      ↓
                        Merge Results → Apply Card Offers → Rank + Return
```

### Card Offer Database

| Bank | Cards | Platforms |
|---|---|---|
| HDFC | Credit, Debit | Amazon, Myntra, Flipkart, AJIO, Nykaa |
| ICICI | Credit, Debit | Amazon, Myntra, Flipkart |
| SBI | Credit, Debit | Amazon, Myntra, Flipkart |
| Axis | Credit, Debit | Amazon, Flipkart |
| Kotak | Credit | Amazon |
| AMEX | Credit | Amazon |
| AU | Credit | Amazon |
| OneCard | Credit | Amazon |
| Flipkart.Axis | Credit | Flipkart |

## API Endpoints

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/api/pricing/compare/{source}/{source_id}` | GET | None | Compare prices |
| `/api/pricing/compare-by-url` | GET | None | Compare by URL |
| `/api/pricing/alerts` | POST | JWT | Create price alert |
| `/api/pricing/alerts` | GET | JWT | List alerts |
| `/api/pricing/alerts/{id}` | DELETE | JWT | Deactivate alert |

## Dependencies

- **External:** SerpApi, Amazon, Flipkart, Myntra, AJIO, Nykaa
- **Database:** Supabase (`price_alerts`, `offers`)
- **Systems:** None

## Known Issues

1. **Scraping may violate marketplace ToS**
2. **Rate limiting** — Marketplaces may block rapid requests
3. **Inconsistent HTML structures** — Scrapers break when sites update
4. **No caching** — Each request hits live sites

## Files

| File | Purpose |
|---|---|
| `api/services/price_scraper.py` | Main scraper logic |
| `api/services/card_offers.py` | Card offer database |
| `api/services/price_intelligence.py` | Budget resolution |
| `api/routers/pricing.py` | FastAPI router |
