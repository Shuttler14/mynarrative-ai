"""
social_connect.py — OAuth Connect Session Initiator
=====================================================
Generates a Nango connect session token for a given platform + creator.
The frontend calls this, gets a connectURL, then opens Nango's hosted OAuth popup.

Route: GET /api/social_connect?platform=instagram&creator_id=<uuid>
"""

import os
import json
import urllib.request
import urllib.parse
from http.server import BaseHTTPRequestHandler

NANGO_SECRET_KEY = os.environ.get("NANGO_SECRET_KEY", "")
NANGO_API = "https://api.nango.dev"

# Nango integration keys — must match what you register in app.nango.dev
NANGO_INTEGRATIONS = {
    "instagram": "instagram",
    "youtube":   "youtube",
    "twitter":   "twitter-v2",
    "linkedin":  "linkedin",
}

# Elite follower thresholds per platform
ELITE_THRESHOLDS = {
    "instagram": 500000,
    "youtube":   300000,
    "twitter":   200000,
    "linkedin":  150000,
}


def get_nango_connect_token(creator_id: str, platform: str) -> dict:
    """Call Nango API to create a connect session token."""
    integration = NANGO_INTEGRATIONS.get(platform)
    if not integration:
        raise ValueError(f"Unsupported platform: {platform}")

    payload = json.dumps({
        "end_user": {
            "id": creator_id,
            "display_name": f"Creator {creator_id[:8]}"
        },
        "allowed_integrations": [integration],
        "expires_in_mins": 30
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{NANGO_API}/connect/sessions",
        data=payload,
        headers={
            "Authorization": f"Bearer {NANGO_SECRET_KEY}",
            "Content-Type": "application/json",
        },
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return data


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

        platform   = params.get("platform", [""])[0].lower().strip()
        creator_id = params.get("creator_id", [""])[0].strip()

        # Validate inputs
        if not platform or platform not in NANGO_INTEGRATIONS:
            return self.send_json(400, {
                "success": False,
                "error": f"Invalid platform. Supported: {', '.join(NANGO_INTEGRATIONS.keys())}"
            })

        if not creator_id:
            return self.send_json(400, {
                "success": False,
                "error": "creator_id is required"
            })

        # If Nango key not configured — return a mock URL for development
        if not NANGO_SECRET_KEY:
            return self.send_json(200, {
                "success": True,
                "connectURL": f"https://app.nango.dev/oauth/connect?integration={NANGO_INTEGRATIONS[platform]}&creator_id={creator_id}",
                "platform": platform,
                "threshold": ELITE_THRESHOLDS.get(platform, 0),
                "mock": True,
                "message": "NANGO_SECRET_KEY not configured. Using mock URL."
            })

        try:
            result = get_nango_connect_token(creator_id, platform)
            connect_url = result.get("data", {}).get("connect_session_token") or result.get("connectURL", "")

            return self.send_json(200, {
                "success": True,
                "connectURL": connect_url,
                "platform": platform,
                "integration": NANGO_INTEGRATIONS[platform],
                "threshold": ELITE_THRESHOLDS.get(platform, 0),
                "threshold_label": _threshold_label(platform),
            })

        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8")
            return self.send_json(502, {
                "success": False,
                "error": "Nango API error",
                "detail": body
            })

        except Exception as ex:
            return self.send_json(500, {
                "success": False,
                "error": str(ex)
            })

    def log_message(self, format, *args):
        pass  # Suppress default HTTP logging


def _threshold_label(platform: str) -> str:
    labels = {
        "instagram": "500K+ followers",
        "youtube":   "300K+ subscribers",
        "twitter":   "200K+ followers",
        "linkedin":  "150K+ followers",
    }
    return labels.get(platform, "")
