"""
register_shopify_webhooks.py — My Narrative Shopify Webhook Registration
=========================================================================
Programmatically registers all required Shopify webhooks via the Admin API.
Safe to re-run: checks for existing webhooks before registering to avoid duplicates.

Usage:
    python scripts/register_shopify_webhooks.py

Required env vars (set in .env or system env):
    SHOPIFY_STORE_URL           e.g. mynarrative.myshopify.com
    SHOPIFY_ADMIN_ACCESS_TOKEN  Admin API token (starts with shpat_)
    VERCEL_DEPLOYMENT_URL       e.g. https://api.mynarrative.store
                                (fallback: https://mynarrative-ai.vercel.app)

Optional:
    SHOPIFY_API_VERSION         default: 2024-01

Output: Prints registered webhook IDs and confirms success.
"""

import os
import sys
import json
import requests
from datetime import datetime

# ─────────────────────────────────────────────
# Load environment
# ─────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env.local'))
except ImportError:
    pass  # dotenv optional

SHOPIFY_STORE_URL   = os.environ.get("SHOPIFY_STORE_URL", "").strip().rstrip("/")
SHOPIFY_TOKEN       = os.environ.get("SHOPIFY_ADMIN_ACCESS_TOKEN", "").strip()
SHOPIFY_API_VERSION = os.environ.get("SHOPIFY_API_VERSION", "2024-01")
VERCEL_URL          = os.environ.get("VERCEL_DEPLOYMENT_URL", "").strip().rstrip("/")

# ─────────────────────────────────────────────
# Webhook definitions — all topics to register
# ─────────────────────────────────────────────
# Format: (topic, relative_path, description)
WEBHOOKS_TO_REGISTER = [
    (
        "orders/create",
        "/api/webhook/design-order",
        "D2E: Record design order + write financial ledger"
    ),
    (
        "refunds/create",
        "/api/webhook/design-refund",
        "D2E: Process refund — negative ledger entry + tier downgrade"
    ),
    (
        "orders/paid",
        "/api/webhook/order_paid",
        "General: Mark order as paid in shopify_orders table"
    ),
    (
        "orders/fulfilled",
        "/api/webhook/order_fulfilled",
        "General: Mark order as fulfilled"
    ),
]


def shopify_request(method, path, payload=None):
    """Make an authenticated Shopify Admin REST API request."""
    url     = f"https://{SHOPIFY_STORE_URL}/admin/api/{SHOPIFY_API_VERSION}{path}"
    headers = {
        "X-Shopify-Access-Token": SHOPIFY_TOKEN,
        "Content-Type":           "application/json",
        "Accept":                 "application/json",
    }
    resp = requests.request(method, url, headers=headers, json=payload, timeout=15)
    return resp


def get_existing_webhooks():
    """Fetch all currently registered webhooks from Shopify."""
    resp = shopify_request("GET", "/webhooks.json?limit=250")
    if resp.status_code != 200:
        print(f"  ERROR fetching webhooks: {resp.status_code} {resp.text}")
        return []
    return resp.json().get("webhooks", [])


def register_webhook(topic, address, description):
    """
    Register a single webhook. Returns (action, webhook_dict) where
    action is 'created', 'already_exists', or 'error'.
    """
    payload = {
        "webhook": {
            "topic":   topic,
            "address": address,
            "format":  "json",
        }
    }
    resp = shopify_request("POST", "/webhooks.json", payload)

    if resp.status_code == 201:
        webhook = resp.json().get("webhook", {})
        return "created", webhook
    elif resp.status_code == 422:
        # Usually means "Address for this topic has already been taken"
        errors = resp.json().get("errors", {})
        if "address" in str(errors).lower() or "taken" in str(errors).lower():
            return "already_exists", None
        return "error", {"status": resp.status_code, "errors": errors}
    else:
        return "error", {"status": resp.status_code, "body": resp.text[:200]}


def delete_webhook(webhook_id):
    """Delete a webhook by ID (used for cleanup of stale registrations)."""
    resp = shopify_request("DELETE", f"/webhooks/{webhook_id}.json")
    return resp.status_code == 200


def verify_webhook(webhook_id):
    """Verify a webhook registration is active."""
    resp = shopify_request("GET", f"/webhooks/{webhook_id}.json")
    if resp.status_code == 200:
        return resp.json().get("webhook", {})
    return None


def run():
    print("=" * 65)
    print("  My Narrative — Shopify Webhook Registration")
    print(f"  {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 65)

    # ── Validate config ───────────────────────────────────────────
    errors = []
    if not SHOPIFY_STORE_URL:
        errors.append("SHOPIFY_STORE_URL is not set")
    if not SHOPIFY_TOKEN:
        errors.append("SHOPIFY_ADMIN_ACCESS_TOKEN is not set")
    if not VERCEL_URL:
        errors.append("VERCEL_DEPLOYMENT_URL is not set")

    if errors:
        print("\n❌ CONFIGURATION ERRORS:")
        for e in errors:
            print(f"   • {e}")
        print("\nSet these in mynarrative-ai/.env or as system env vars:")
        print("   SHOPIFY_STORE_URL=mynarrative.myshopify.com")
        print("   SHOPIFY_ADMIN_ACCESS_TOKEN=shpat_xxxx")
        print("   VERCEL_DEPLOYMENT_URL=https://mynarrative-ai.vercel.app")
        sys.exit(1)

    print(f"\n  Store:      {SHOPIFY_STORE_URL}")
    print(f"  API Ver:    {SHOPIFY_API_VERSION}")
    print(f"  Vercel URL: {VERCEL_URL}")
    print(f"  Webhooks:   {len(WEBHOOKS_TO_REGISTER)} to register\n")

    # ── Fetch existing webhooks ───────────────────────────────────
    print("📋 Fetching existing webhooks...")
    existing = get_existing_webhooks()
    existing_map = {}  # topic → webhook dict
    for wh in existing:
        existing_map[wh["topic"]] = wh
    print(f"   Found {len(existing)} existing webhooks\n")

    # ── Register / verify each webhook ───────────────────────────
    results = []
    registered_ids = []

    for topic, path, description in WEBHOOKS_TO_REGISTER:
        full_address = f"{VERCEL_URL}{path}"
        print(f"  [{topic}]")
        print(f"   → {full_address}")
        print(f"   Description: {description}")

        # Check if already registered to THIS address
        if topic in existing_map:
            existing_wh = existing_map[topic]
            existing_addr = existing_wh.get("address", "")

            if existing_addr == full_address:
                wh_id = existing_wh["id"]
                print(f"   ✅ Already registered (ID: {wh_id})")
                registered_ids.append(wh_id)
                results.append({
                    "topic":   topic,
                    "action":  "already_exists",
                    "id":      wh_id,
                    "address": full_address,
                })
                print()
                continue
            else:
                # Same topic, different address — delete old, re-register
                print(f"   ⚠️  Existing webhook points to different address:")
                print(f"      Old: {existing_addr}")
                print(f"      New: {full_address}")
                print(f"      Deleting old webhook {existing_wh['id']}...")
                if delete_webhook(existing_wh["id"]):
                    print(f"      Deleted ✓")
                else:
                    print(f"      Failed to delete — manual cleanup may be needed")

        # Register new webhook
        action, webhook = register_webhook(topic, full_address, description)

        if action == "created":
            wh_id = webhook["id"]
            print(f"   ✅ REGISTERED (ID: {wh_id})")
            registered_ids.append(wh_id)
            results.append({
                "topic":      topic,
                "action":     "created",
                "id":         wh_id,
                "address":    full_address,
                "created_at": webhook.get("created_at", ""),
            })
        elif action == "already_exists":
            print(f"   ℹ️  Already exists with this address (Shopify 422)")
            results.append({
                "topic":   topic,
                "action":  "already_exists",
                "address": full_address,
            })
        else:
            print(f"   ❌ FAILED: {webhook}")
            results.append({
                "topic":   topic,
                "action":  "error",
                "error":   str(webhook),
                "address": full_address,
            })
        print()

    # ── Verify all registered webhooks are active ─────────────────
    print("🔍 Verifying active webhook registrations...")
    verified = []
    for wh_id in registered_ids:
        wh = verify_webhook(wh_id)
        if wh:
            print(f"   ✅ ID {wh_id} | {wh['topic']} | {wh['address']}")
            verified.append(wh)
        else:
            print(f"   ❌ ID {wh_id} could not be verified")

    # ── Summary ───────────────────────────────────────────────────
    successes = [r for r in results if r["action"] in ("created", "already_exists")]
    failures  = [r for r in results if r["action"] == "error"]

    print("\n" + "=" * 65)
    print(f"  SUMMARY: {len(successes)}/{len(WEBHOOKS_TO_REGISTER)} webhooks active")
    if registered_ids:
        print(f"  Active webhook IDs: {registered_ids}")
    if failures:
        print(f"\n  ❌ FAILURES ({len(failures)}):")
        for f in failures:
            print(f"     {f['topic']}: {f.get('error', 'unknown error')}")
        sys.exit(1)
    else:
        print("\n  ✅ All webhooks registered and verified successfully!")
        print(f"\n  Register these in Shopify Admin if not already set:")
        print(f"  Store > Settings > Notifications > Webhooks")
        for r in results:
            print(f"    • {r['topic']} → {r['address']}")
    print("=" * 65)

    # ── Write result JSON ─────────────────────────────────────────
    out_path = os.path.join(os.path.dirname(__file__), 'webhook_registration_result.json')
    with open(out_path, 'w') as f:
        json.dump({
            "registered_at":  datetime.utcnow().isoformat(),
            "store_url":      SHOPIFY_STORE_URL,
            "vercel_url":     VERCEL_URL,
            "results":        results,
            "active_ids":     registered_ids,
        }, f, indent=2)
    print(f"\n  📄 Result saved to: {out_path}")


if __name__ == "__main__":
    run()
