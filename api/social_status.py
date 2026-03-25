"""
social_status.py — Platform Connection Status
==============================================
Returns the current verification status of all connected platforms for a creator.
Frontend polls / subscribes to this to show real-time verified badges.

Route: GET /api/social_status?creator_id=<uuid>
"""

import os
import json
import urllib.request
import urllib.parse
from http.server import BaseHTTPRequestHandler

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

ELITE_THRESHOLDS = {
    "instagram": 500000,
    "youtube":   300000,
    "twitter":   200000,
    "linkedin":  150000,
}

PLATFORM_LABELS = {
    "instagram": {"name": "Instagram", "threshold_label": "500K+ followers"},
    "youtube":   {"name": "YouTube",   "threshold_label": "300K+ subscribers"},
    "twitter":   {"name": "X / Twitter","threshold_label": "200K+ followers"},
    "linkedin":  {"name": "LinkedIn",  "threshold_label": "150K+ followers"},
}


def supabase_select(table: str, filters: dict) -> list:
    """Select rows from Supabase via REST API."""
    query = "&".join([f"{k}=eq.{urllib.parse.quote(str(v))}" for k, v in filters.items()])
    url = f"{SUPABASE_URL}/rest/v1/{table}?{query}&select=*"
    req = urllib.request.Request(
        url,
        headers={
            "apikey":        SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type":  "application/json",
        },
        method="GET"
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


class handler(BaseHTTPRequestHandler):

    def send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def send_json(self, code: int, body: dict):
        self.send_response(code)
        self.send_cors_headers()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        creator_id = params.get("creator_id", [""])[0].strip()

        if not creator_id:
            return self.send_json(400, {
                "success": False,
                "error": "creator_id is required"
            })

        # If Supabase not configured — return empty state
        if not SUPABASE_URL or not SUPABASE_KEY:
            return self.send_json(200, {
                "success": True,
                "creator_id": creator_id,
                "platforms": [],
                "any_qualified": False,
                "mock": True,
                "message": "Supabase not configured. No platform connections stored yet."
            })

        try:
            rows = supabase_select("platform_connections", {"creator_id": creator_id})
        except Exception as ex:
            return self.send_json(502, {
                "success": False,
                "error": f"Supabase error: {str(ex)}"
            })

        platforms = []
        any_qualified = False

        for row in rows:
            platform    = row.get("platform", "")
            followers   = row.get("follower_count", 0)
            verified    = row.get("verified", False)
            qualifies   = row.get("qualifies_elite", False) or (
                followers >= ELITE_THRESHOLDS.get(platform, 0)
            )

            if qualifies:
                any_qualified = True

            meta = PLATFORM_LABELS.get(platform, {"name": platform.title(), "threshold_label": ""})

            platforms.append({
                "platform":         platform,
                "name":             meta["name"],
                "threshold_label":  meta["threshold_label"],
                "threshold":        ELITE_THRESHOLDS.get(platform, 0),
                "username":         row.get("username", ""),
                "display_name":     row.get("display_name", ""),
                "avatar_url":       row.get("avatar_url", ""),
                "follower_count":   followers,
                "verified":         verified,
                "qualifies_elite":  qualifies,
                "commission_range": row.get("commission_range", "30-45%") if qualifies else None,
                "commission_note":  row.get("commission_note"),
                "needs_manual_review": row.get("needs_manual_review", False),
                "last_synced":      row.get("last_synced"),
            })

        # Summary for frontend
        qualified_platforms = [p for p in platforms if p["qualifies_elite"]]
        connected_platforms = [p["platform"] for p in platforms]

        return self.send_json(200, {
            "success":              True,
            "creator_id":           creator_id,
            "platforms":            platforms,
            "any_qualified":        any_qualified,
            "qualified_platforms":  [p["platform"] for p in qualified_platforms],
            "connected_platforms":  connected_platforms,
            "elite_status":         "qualified" if any_qualified else (
                                    "pending" if connected_platforms else "not_started"
                                    ),
            "commission_range":     "30-45%" if any_qualified else None,
            "commission_note":      "Final commission determined post-review" if any_qualified else None,
        })

    def log_message(self, format, *args):
        pass
