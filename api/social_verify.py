"""
social_verify.py — Nango Webhook Handler + Supabase Upsert
===========================================================
Nango calls this endpoint when OAuth completes successfully.
We fetch the creator's profile via Nango proxy, then write to Supabase.
Supabase Realtime broadcasts the update to the creator's browser instantly.

Route: POST /api/social_verify
Nango Dashboard: set webhook URL to https://mynarrative-ai.vercel.app/api/social_verify
"""

import os
import json
import urllib.request
import urllib.parse
import hmac
import hashlib
from http.server import BaseHTTPRequestHandler

NANGO_SECRET_KEY   = os.environ.get("NANGO_SECRET_KEY", "")
NANGO_WEBHOOK_SECRET = os.environ.get("NANGO_WEBHOOK_SECRET", "")
SUPABASE_URL       = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY       = os.environ.get("SUPABASE_KEY", "")  # service role key
NANGO_API          = "https://api.nango.dev"
PROXYCURL_API_KEY  = os.environ.get("PROXYCURL_API_KEY", "")

# Elite thresholds — any ONE platform qualifying = elite
ELITE_THRESHOLDS = {
    "instagram":  500000,
    "youtube":    300000,
    "twitter-v2": 200000,
    "twitter":    200000,
    "linkedin":   150000,
}

# Commission range — exact rate determined post-review
COMMISSION_RANGE = {"min": 30, "max": 45}


# ── Nango Proxy helpers ───────────────────────────────────────────────────────

def nango_get(connection_id: str, integration: str, endpoint: str) -> dict:
    """Call Nango proxy — it injects the correct auth header automatically."""
    url = f"{NANGO_API}/proxy{endpoint}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization":          f"Bearer {NANGO_SECRET_KEY}",
            "Connection-Id":          connection_id,
            "Provider-Config-Key":    integration,
        },
        method="GET"
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_profile(platform: str, connection_id: str) -> dict:
    """Fetch follower count + profile info via Nango proxy."""

    if platform in ("instagram",):
        data = nango_get(connection_id, "instagram",
                         "/me?fields=id,username,name,profile_picture_url,followers_count")
        return {
            "username":      data.get("username", ""),
            "display_name":  data.get("name", ""),
            "avatar_url":    data.get("profile_picture_url", ""),
            "follower_count": int(data.get("followers_count", 0)),
        }

    elif platform in ("twitter-v2", "twitter"):
        data = nango_get(connection_id, "twitter-v2",
                         "/2/users/me?user.fields=username,name,profile_image_url,public_metrics")
        user = data.get("data", {})
        metrics = user.get("public_metrics", {})
        return {
            "username":      user.get("username", ""),
            "display_name":  user.get("name", ""),
            "avatar_url":    user.get("profile_image_url", ""),
            "follower_count": int(metrics.get("followers_count", 0)),
        }

    elif platform == "youtube":
        data = nango_get(connection_id, "youtube",
                         "/youtube/v3/channels?part=snippet,statistics&mine=true")
        items = data.get("items", [])
        if not items:
            return {"username": "", "display_name": "", "avatar_url": "", "follower_count": 0}
        item = items[0]
        snippet    = item.get("snippet", {})
        statistics = item.get("statistics", {})
        return {
            "username":      item.get("id", ""),
            "display_name":  snippet.get("title", ""),
            "avatar_url":    snippet.get("thumbnails", {}).get("default", {}).get("url", ""),
            "follower_count": int(statistics.get("subscriberCount", 0)),
        }

    elif platform == "linkedin":
        # Try Proxycurl first (no approval wait), fall back to Nango proxy
        if PROXYCURL_API_KEY:
            return fetch_linkedin_proxycurl(connection_id)
        data = nango_get(connection_id, "linkedin",
                         "/v2/me?projection=(id,localizedFirstName,localizedLastName,profilePicture)")
        # LinkedIn basic profile doesn't give followers without Marketing API approval
        # We store 0 and flag for manual review
        return {
            "username":      data.get("id", ""),
            "display_name":  f"{data.get('localizedFirstName','')} {data.get('localizedLastName','')}".strip(),
            "avatar_url":    "",
            "follower_count": 0,
            "needs_manual_review": True,
        }

    return {"username": "", "display_name": "", "avatar_url": "", "follower_count": 0}


def fetch_linkedin_proxycurl(connection_id: str) -> dict:
    """Fetch LinkedIn follower count via Proxycurl (bypasses long API approval)."""
    # We need the LinkedIn profile URL — get it from Nango first
    try:
        data = nango_get(connection_id, "linkedin",
                         "/v2/me?projection=(id,localizedFirstName,localizedLastName,vanityName)")
        vanity = data.get("vanityName") or data.get("id", "")
        profile_url = f"https://www.linkedin.com/in/{vanity}"

        req = urllib.request.Request(
            f"https://nubela.co/proxycurl/api/v2/linkedin?url={urllib.parse.quote(profile_url)}",
            headers={"Authorization": f"Bearer {PROXYCURL_API_KEY}"},
            method="GET"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            pdata = json.loads(resp.read().decode("utf-8"))
            return {
                "username":      vanity,
                "display_name":  pdata.get("full_name", ""),
                "avatar_url":    pdata.get("profile_pic_url", ""),
                "follower_count": int(pdata.get("follower_count") or pdata.get("connections") or 0),
            }
    except Exception:
        return {"username": "", "display_name": "", "avatar_url": "", "follower_count": 0,
                "needs_manual_review": True}


# ── Supabase helpers ──────────────────────────────────────────────────────────

def supabase_upsert(table: str, record: dict, on_conflict: str):
    """Upsert a record into Supabase via REST API."""
    url = f"{SUPABASE_URL}/rest/v1/{table}?on_conflict={on_conflict}"
    payload = json.dumps(record).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "apikey":         SUPABASE_KEY,
            "Authorization":  f"Bearer {SUPABASE_KEY}",
            "Content-Type":   "application/json",
            "Prefer":         "resolution=merge-duplicates,return=representation",
        },
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def sync_avatar(source_url: str, path: str) -> str:
    """Upload avatar to Supabase Storage and return public URL."""
    if not source_url:
        return ""
    try:
        with urllib.request.urlopen(source_url, timeout=10) as img_resp:
            img_data = img_resp.read()
            content_type = img_resp.headers.get("Content-Type", "image/jpeg")

        upload_url = f"{SUPABASE_URL}/storage/v1/object/avatars/{path}"
        req = urllib.request.Request(
            upload_url,
            data=img_data,
            headers={
                "apikey":        SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type":  content_type,
                "x-upsert":      "true",
            },
            method="POST"
        )
        urllib.request.urlopen(req, timeout=15)
        return f"{SUPABASE_URL}/storage/v1/object/public/avatars/{path}"
    except Exception:
        return source_url  # Fall back to original URL if upload fails


def verify_nango_signature(body: bytes, signature: str) -> bool:
    """Verify Nango webhook HMAC signature."""
    if not NANGO_WEBHOOK_SECRET:
        return True  # Skip verification if secret not set (dev mode)
    expected = hmac.new(
        NANGO_WEBHOOK_SECRET.encode("utf-8"),
        body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature.replace("sha256=", ""))


# ── HTTP Handler ──────────────────────────────────────────────────────────────

class handler(BaseHTTPRequestHandler):

    def send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Nango-Signature")

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

    def do_POST(self):
        length   = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length)
        signature = self.headers.get("X-Nango-Signature", "")

        # Verify webhook authenticity
        if not verify_nango_signature(raw_body, signature):
            return self.send_json(401, {"success": False, "error": "Invalid webhook signature"})

        try:
            body = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            return self.send_json(400, {"success": False, "error": "Invalid JSON"})

        # Only handle successful auth events from Nango
        event_type = body.get("type", "")
        if event_type != "auth" or not body.get("success"):
            return self.send_json(200, {"ok": True, "skipped": True, "reason": "Not an auth success event"})

        creator_id    = body.get("endUser", {}).get("id", "")
        platform      = body.get("providerConfigKey", "")  # e.g. "instagram", "twitter-v2"
        connection_id = body.get("connectionId", "")

        if not all([creator_id, platform, connection_id]):
            return self.send_json(400, {
                "success": False,
                "error": "Missing required fields: endUser.id, providerConfigKey, connectionId"
            })

        # Normalize platform name for storage
        platform_key = platform.replace("-v2", "").lower()  # twitter-v2 -> twitter

        try:
            # Fetch profile via Nango proxy
            profile = fetch_profile(platform, connection_id)
            followers = profile.get("follower_count", 0)
            threshold = ELITE_THRESHOLDS.get(platform, ELITE_THRESHOLDS.get(platform_key, 0))
            qualifies = followers >= threshold

            # Sync avatar to Supabase Storage
            avatar_path = f"{creator_id}/{platform_key}.jpg"
            avatar_url  = sync_avatar(profile.get("avatar_url", ""), avatar_path)

            # Build Supabase record
            record = {
                "creator_id":          creator_id,
                "platform":            platform_key,
                "nango_connection_id": connection_id,
                "username":            profile.get("username", ""),
                "display_name":        profile.get("display_name", ""),
                "avatar_url":          avatar_url,
                "follower_count":      followers,
                "verified":            qualifies,
                "qualifies_elite":     qualifies,
                "commission_range":    f"{COMMISSION_RANGE['min']}-{COMMISSION_RANGE['max']}%" if qualifies else None,
                "commission_note":     "Final rate determined post-review based on reach & engagement" if qualifies else None,
                "needs_manual_review": profile.get("needs_manual_review", False),
                "last_synced":         _now_iso(),
            }

            # Upsert to Supabase (triggers Realtime broadcast to frontend)
            if SUPABASE_URL and SUPABASE_KEY:
                supabase_upsert("platform_connections", record, "creator_id,platform")

            return self.send_json(200, {
                "success":         True,
                "creator_id":      creator_id,
                "platform":        platform_key,
                "follower_count":  followers,
                "qualifies_elite": qualifies,
                "commission_range": record.get("commission_range"),
                "threshold":       threshold,
                "profile": {
                    "username":     profile.get("username"),
                    "display_name": profile.get("display_name"),
                    "avatar_url":   avatar_url,
                }
            })

        except Exception as ex:
            # Log the error but return 200 so Nango doesn't retry
            return self.send_json(200, {
                "success": False,
                "error":   str(ex),
                "note":    "Error logged — Nango will not retry on 200"
            })

    def log_message(self, format, *args):
        pass


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
