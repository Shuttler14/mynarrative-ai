# System Passport: Checkout System

> **ID:** SYS-004 | **Status:** Active | **Maturity:** Beta

## Overview

Unified cross-brand shopping cart with order creation, commission calculation, and multi-brand order splitting. Currently uses in-memory fallback because Supabase schema is not deployed.

## Architecture

### Components

| Component | File | Purpose |
|---|---|---|
| Gateway | `api/b2b_gateway.py` | Routes `/api/checkout/*` |
| API | `api/checkout_api.py` | Cart CRUD, order creation, commissions |
| Schema | `supabase_unified_checkout.sql` | 8 tables (NOT DEPLOYED) |
| Frontend | `templates/page.checkout.liquid` | Checkout page |
| Confirmation | `templates/page.order-confirmation.liquid` | Order confirmation |

### In-Memory Fallback

When Supabase tables don't exist, the system falls back to Python dicts:
- `_carts` — Cart items keyed by session_id
- `_addresses` — User addresses keyed by user_id
- `_orders` — Orders keyed by order_id

**Warning:** Data lost on Vercel cold starts.

## API Endpoints

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/api/checkout/cart` | GET | Session | Get cart |
| `/api/checkout/cart` | POST | Session | Add to cart |
| `/api/checkout/cart` | DELETE | Session | Remove from cart |
| `/api/checkout/order/create` | POST | Session | Create order (splits by brand) |
| `/api/checkout/order/{id}` | GET | Session | Get order details |
| `/api/checkout/orders` | GET | Session | List user orders |
| `/api/checkout/address` | GET | User | Get addresses |
| `/api/checkout/address` | POST | User | Add address |

### Commission Calculation

| Commission Type | Rate | Recipient |
|---|---|---|
| Platform commission | 10% | My Narrative |
| Host affiliate commission | 7% | Host brand |
| Supplier CPA | 10% | Supplier |

### Order Splitting

When an order contains products from multiple brands, it automatically splits into brand sub-orders:
- Each brand gets its own sub-order
- Commission calculated per sub-order
- Fulfillment handled independently per brand

## Dependencies

- **Database:** Supabase (`narrative_cart`, `narrative_orders`, `narrative_order_items`, `narrative_addresses`) — NOT DEPLOYED
- **External:** Razorpay (payment verification — env vars not set)
- **Systems:** None

## Known Issues

1. **Schema NOT deployed** — 8 tables exist in SQL file but not in Supabase
2. **In-memory fallback** — Data lost on cold starts
3. **`RAZORPAY_KEY_ID`/`RAZORPAY_KEY_SECRET` not set** in Vercel
4. **Shopify pages not created** — `checkout` and `order-confirmation` pages exist as templates but not linked

## Business Rules

| Rule | Value |
|---|---|
| Base currency | INR |
| Supported currencies | INR, USD, GBP, EUR, AED, AUD |
| Free shipping threshold | ₹999 |
| GST | 18% |
| Platform commission | 10% |
| Host affiliate commission | 7% |

## Files

| File | Purpose |
|---|---|
| `api/checkout_api.py` | Cart, orders, commissions, addresses |
| `supabase_unified_checkout.sql` | 8-table schema |
| `templates/page.checkout.liquid` | Checkout page |
| `templates/page.order-confirmation.liquid` | Order confirmation |
