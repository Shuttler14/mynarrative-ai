"""
creator_earnings.py — My Narrative Creator Earnings API
=========================================================
Uses Python stdlib urllib (NO httpx, NO supabase-py, NO httpcore)
to avoid [Errno 16] Device or resource busy on Vercel's filesystem.

Endpoints:
  GET /api/creator/earnings?creator_id=<shopify_customer_id>
  GET /api/creator/earnings/summary?creator_id=<id>
  GET /api/creator/earnings/health
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.request
import urllib.parse
from datetime import datetime, timedelta

# ─────────────────────────────────────────────────────────────
# TIER CONFIG
# ─────────────────────────────────────────────────────────────
def compute_tier_progress(total_sold):
    tiers = [(0, "Bronze", 50), (50, "Silver", 200), (200, "Gold", 1000), (1000, "Diamond", None)]
    for floor, name, ceiling in tiers:
        if ceiling is None or total_sold < ceiling:
            if ceiling is None:
                return {"current_tier": "Diamond", "next_tier": None,
                        "sales_to_next_tier": 0, "progress_pct": 100}
            idx = tiers.index((floor, name, ceiling))
            return {
                "current_tier":       name,
                "next_tier":          tiers[idx + 1][1],
                "sales_to_next_tier": ceiling - total_sold,
                "progress_pct":       int(((total_sold - floor) / (ceiling - floor)) * 100),
            }
    return {"current_tier": "Diamond", "next_tier": None,
            "sales_to_next_tier": 0, "progress_pct": 100}


# ─────────────────────────────────────────────────────────────
# SUPABASE REST API via urllib (no httpx dependency)
# ─────────────────────────────────────────────────────────────
def supabase_get(table, select, filters=None, order=None, limit=None):
    """
    Query Supabase REST API using stdlib urllib.
    Returns (list_of_rows, error_string_or_None).
    """
    url_base = os.environ.get("SUPABASE_URL", "")
    api_key  = os.environ.get("SUPABASE_KEY", "")
    if not url_base or not api_key:
        return [], "not_configured"

    params = {"select": select}
    if filters:
        params.update(filters)  # e.g. {"shopify_customer_id": "eq.shopify-001"}
    if order:
        params["order"] = order
    if limit:
        params["limit"] = str(limit)

    query_string = urllib.parse.urlencode(params)
    url = f"{url_base.rstrip('/')}/rest/v1/{table}?{query_string}"

    req = urllib.request.Request(url)
    req.add_header("apikey", api_key)
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    req.add_header("Prefer", "return=representation")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            if isinstance(data, list):
                return data, None
            return [], f"unexpected_response: {str(data)[:100]}"
    except urllib.error.HTTPError as e:
        return [], f"HTTP {e.code}: {e.read().decode()[:100]}"
    except Exception as e:
        return [], str(e)


# ─────────────────────────────────────────────────────────────
# DEMO DATA
# ─────────────────────────────────────────────────────────────
def build_demo_response(creator_id):
    now = datetime.utcnow()
    transactions = [
        {"id": "tx-001", "event_type": "sale",   "amount_paise": 29900,  "amount_rupees": 299.0,
         "product_type": "tshirt", "color": "white",    "quantity": 1,
         "note": "Sale: Midnight Bloom | tshirt/white x1",
         "created_at": (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")},
        {"id": "tx-002", "event_type": "sale",   "amount_paise": 59900,  "amount_rupees": 599.0,
         "product_type": "hoodie", "color": "black",    "quantity": 1,
         "note": "Sale: Urban Cipher | hoodie/black x1",
         "created_at": (now - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")},
        {"id": "tx-003", "event_type": "refund", "amount_paise": -29900, "amount_rupees": -299.0,
         "product_type": "tshirt", "color": "navy",     "quantity": 1,
         "note": "Refund: Midnight Bloom | Order #1001",
         "created_at": (now - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")},
        {"id": "tx-004", "event_type": "sale",   "amount_paise": 49900,  "amount_rupees": 499.0,
         "product_type": "tshirt", "color": "black",    "quantity": 2,
         "note": "Sale: Chaos Theory | tshirt/black x2",
         "created_at": (now - timedelta(days=4)).strftime("%Y-%m-%dT%H:%M:%SZ")},
        {"id": "tx-005", "event_type": "sale",   "amount_paise": 59900,  "amount_rupees": 599.0,
         "product_type": "hoodie", "color": "burgundy", "quantity": 1,
         "note": "Sale: Neon Grid | hoodie/burgundy x1",
         "created_at": (now - timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ")},
    ]
    total_sold  = 50
    total_earn  = sum(t["amount_paise"] for t in transactions if t["amount_paise"] > 0)
    tier_prog   = compute_tier_progress(total_sold)
    return {
        "success": True, "demo_mode": True, "creator_id": creator_id,
        "summary": {
            "total_earnings_paise":  total_earn,
            "total_earnings_rupees": total_earn / 100,
            "total_designs_sold":    total_sold,
            "creator_tier":          tier_prog["current_tier"],
            "tier_progress":         tier_prog,
        },
        "recent_transactions": transactions,
    }


def build_demo_summary(creator_id):
    d = build_demo_response(creator_id)
    return {"success": True, "demo_mode": True, "creator_id": creator_id, "summary": d["summary"]}


# ─────────────────────────────────────────────────────────────
# HTTP HANDLER
# ─────────────────────────────────────────────────────────────
class handler(BaseHTTPRequestHandler):

    def send_json(self, status, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        parsed     = urlparse(self.path)
        params     = parse_qs(parsed.query)
        path       = parsed.path
        creator_id = params.get("creator_id", [""])[0].strip()

        if "/health" in path:
            configured = bool(os.environ.get("SUPABASE_URL"))
            return self.send_json(200, {
                "status":  "ok",
                "message": "Creator Earnings API v2.0 (urllib, no httpx)",
                "mode":    "live" if configured else "demo",
                "endpoints": [
                    "GET /api/creator/earnings?creator_id=<id>",
                    "GET /api/creator/earnings/summary?creator_id=<id>",
                    "GET /api/creator/earnings/health",
                ]
            })

        if not creator_id:
            return self.send_json(400, {"error": "creator_id query param is required"})

        if "/summary" in path:
            return self._summary(creator_id)

        return self._earnings(creator_id)

    def _earnings(self, creator_id):
        # Fetch creator
        rows, err = supabase_get(
            "creators",
            "id,total_earnings_paise,total_designs_sold,creator_tier",
            filters={"shopify_customer_id": f"eq.{creator_id}"},
            limit=1
        )
        if err or not rows:
            return self.send_json(200, build_demo_response(creator_id))

        c          = rows[0]
        creator_db = c.get("id", "")
        total_sold = int(c.get("total_designs_sold") or 0)
        total_earn = int(c.get("total_earnings_paise") or 0)
        tier       = str(c.get("creator_tier") or "Bronze")

        # Fetch ledger
        txrows, _ = supabase_get(
            "financial_ledger",
            "id,event_type,amount_paise,product_type,color,quantity,note,created_at",
            filters={"creator_id": f"eq.{creator_db}"},
            order="created_at.desc",
            limit=10
        )
        transactions = [
            {
                "id":            str(tx.get("id", "")),
                "event_type":    str(tx.get("event_type", "")),
                "amount_paise":  int(tx.get("amount_paise") or 0),
                "amount_rupees": int(tx.get("amount_paise") or 0) / 100,
                "product_type":  str(tx.get("product_type", "")),
                "color":         str(tx.get("color", "")),
                "quantity":      int(tx.get("quantity") or 1),
                "note":          str(tx.get("note", "")),
                "created_at":    str(tx.get("created_at", "")),
            }
            for tx in txrows
        ]

        self.send_json(200, {
            "success": True, "creator_id": creator_id,
            "summary": {
                "total_earnings_paise":  total_earn,
                "total_earnings_rupees": total_earn / 100,
                "total_designs_sold":    total_sold,
                "creator_tier":          tier,
                "tier_progress":         compute_tier_progress(total_sold),
            },
            "recent_transactions": transactions,
        })

    def _summary(self, creator_id):
        rows, err = supabase_get(
            "creators",
            "total_earnings_paise,total_designs_sold,creator_tier",
            filters={"shopify_customer_id": f"eq.{creator_id}"},
            limit=1
        )
        if err or not rows:
            return self.send_json(200, build_demo_summary(creator_id))

        c          = rows[0]
        total_sold = int(c.get("total_designs_sold") or 0)
        total_earn = int(c.get("total_earnings_paise") or 0)
        self.send_json(200, {
            "success": True, "creator_id": creator_id,
            "summary": {
                "total_earnings_paise":  total_earn,
                "total_earnings_rupees": total_earn / 100,
                "total_designs_sold":    total_sold,
                "creator_tier":          str(c.get("creator_tier") or "Bronze"),
                "tier_progress":         compute_tier_progress(total_sold),
            }
        })
