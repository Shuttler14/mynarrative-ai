# System Passport: B2B Recommendation Engine

> **ID:** SYS-001 | **Status:** Active | **Maturity:** Production

## Overview

AI-powered cross-brand fashion recommendation engine with a 12-stage pipeline. Processes customer context (budget, occasion, style, body type) and generates ranked outfit recommendations across multiple brands.

## Architecture

### Pipeline Stages

| Stage | Module | Purpose | Input | Output |
|---|---|---|---|---|
| 1 | `intent_detection.py` | Budget/occasion/style inference | User query | Structured intent |
| 2 | `inventory_filter.py` | Hard pre-filter (stock, size, gender, price) | Products + intent | Filtered products |
| 3 | `knowledge_graph.py` | 906-line rules engine | Filtered products | Rule scores |
| 4a | `outfit_assembly.py` | Anchor analysis + category gap detection | Products | Outfit slots |
| 4b | `embeddings.py` | Dual-pipeline: OpenAI text + Fashion-CLIP image | Products | Vector scores |
| 5 | `scoring.py` | Gated non-linear multi-factor scoring | All scores | Final rank |
| 6 | `exploration.py` | Multi-armed bandit (18% epsilon-greedy) | Ranked list | Diversified list |
| 7 | `explainability.py` | Rule-based + LLM reasoning | Ranked list | Explanations |
| — | `eligibility.py` | Brand safety hard gate (10 checks) | Products | Eligible only |
| — | `network_compatibility.py` | Brand-to-brand compatibility (5 dimensions) | Brand pairs | Compatibility |
| — | `cross_ranking.py` | Two-stage: organic + sponsored boost (max 15%) | Scores | Final ranking |
| — | `generate.py` | Full orchestrator (705 lines) | All stages | Final response |

### Scoring Weights

| Factor | Weight | Description |
|---|---|---|
| kg_compatibility | 0.25 | Knowledge graph compatibility score |
| vector_similarity | 0.20 | Embedding similarity score |
| style_cohesion | 0.15 | Style coherence across outfit |
| color_harmony | 0.10 | Color theory matching |
| attribute_match | 0.10 | Product attribute alignment |
| quality_rating | 0.10 | Product quality signals |
| price_fit | 0.10 | Budget alignment |

### B2B Network Modes

| Mode | Name | Description |
|---|---|---|
| A | Brand Only | Host sells own products only |
| B | Curated Network | Default — host picks partner brands |
| C | Open Network | Anyone can sell through host's widget |

## API Endpoints

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/api/recommend` | POST | API key | Generate recommendations |
| `/api/recommend/cross-brand` | POST | API key | Cross-brand recommendations |

## Dependencies

- **Database:** Supabase (`brand_products`, `brand_dna`, `host_preferences`, `brand_exclusions`, `brand_pair_compatibility`)
- **External:** OpenAI (text-embedding-3-small)
- **Systems:** None (foundational)

## Configuration

| Parameter | Value | Notes |
|---|---|---|
| Max products per brand | Configurable | Per host preferences |
| Exploration rate | 18% | Epsilon-greedy |
| Sponsored boost cap | 15% | Maximum boost for paid placements |
| Embedding model | text-embedding-3-small | 1536-dim |
| Knowledge graph rules | 906 | Color, occasion, body, patterns, materials |

## Known Issues

1. **In-memory exploration state** — lost on Vercel cold starts
2. **8+ duplicate `_sb_request()` implementations** — maintenance burden
3. **Broken import** in `cross_ranking.py` — `from api.brand_dna import get_brand_dna_builder` (likely dead code)

## Files

| File | Lines | Purpose |
|---|---|---|
| `api/recommend/generate.py` | 705 | Orchestrator |
| `api/recommend/knowledge_graph.py` | 906 | Rules engine |
| `api/recommend/scoring.py` | ~200 | Multi-factor scoring |
| `api/recommend/intent_detection.py` | ~150 | Intent parsing |
| `api/recommend/inventory_filter.py` | ~100 | Hard filtering |
| `api/recommend/embeddings.py` | ~200 | Vector scoring |
| `api/recommend/exploration.py` | ~100 | Bandit exploration |
| `api/recommend/explainability.py` | ~150 | Explanation gen |
| `api/recommend/eligibility.py` | ~150 | Brand safety |
| `api/recommend/network_compatibility.py` | ~200 | Brand compatibility |
| `api/recommend/cross_ranking.py` | ~200 | Organic + sponsored |
| `api/recommend/outfit_assembly.py` | ~150 | Outfit slot detection |
