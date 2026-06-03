"""
verify_social.py — Elite Creator Verification Gateway
======================================================
Receives an HMAC-signed verification_token from the social-verifier service
(which itself produced it after a successful OAuth dance or server-side
YouTube Data API call). Validates the HMAC with a shared secret so the
browser cannot forge follower counts. If the creator clears the Elite
threshold (>= 10 000 followers) the corresponding Supabase `creators` row
is upgraded to commission_tier='elite', is_elite=true.

Endpoint:
  POST /api/verify_social
  Body: { "creator_id": "<shopify customer id>",
          "verification_token": "<base64>.<hmacSig>" }

Responses:
  200 upgraded:       { success:true, status:"upgraded",   followers, message }
  200 keep_growing:   { success:true, status:"keep_growing", followers, message }
  200 already_elite:  { success:true, status:"already_elite", followers, message }
  400 Error:          { success:false, error:"Account is private or invalid." }
"""

from http.server import BaseHTTPRequestHandler
import base64
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ELITE_THRESHOLD   = 10_000
STANDARD_COMMISSION_PCT = 5
ELITE_COMMISSION_PCT    = 40
MAX_TOKEN_AGE_MS  = 10 * 60 * 1000  # 10 minutes
SUPPORTED_PLATFORMS = {'youtube', 'twitter', 'instagram', 'linkedin'}


# ─── Supabase helpers ─────────────────────────────────────────────────────────
def _sb_headers():
    url = os.environ.get('SUPABASE_URL', '')
    key = os.environ.get('SUPABASE_KEY', '') or os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
    return url, key, {
        'apikey':        key,
        'Authorization': f'Bearer {key}',
        'Content-Type':  'application/json',
        'Accept':        'application/json',
        'Prefer':        'return=representation',
    }


def sb_get(table, select='*', filters=None, limit=None):
    url, key, headers = _sb_headers()
    if not url or not key:
        return [], 'supabase_not_configured'
    params = {'select': select}
    if filters:
        params.update(filters)
    if limit:
        params['limit'] = str(limit)
    full_url = f"{url.rstrip('/')}/rest/v1/{table}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(full_url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
            return (data if isinstance(data, list) else []), None
    except urllib.error.HTTPError as e:
        return [], f'HTTP {e.code}: {e.read().decode()[:200]}'
    except Exception as e:
        return [], str(e)


def sb_patch(table, data, filter_col, filter_val):
    url, key, headers = _sb_headers()
    if not url or not key:
        return None, 'supabase_not_configured'
    params   = {filter_col: f'eq.{filter_val}'}
    full_url = f"{url.rstrip('/')}/rest/v1/{table}?{urllib.parse.urlencode(params)}"
    body     = json.dumps(data).encode()
    req      = urllib.request.Request(full_url, data=body, headers=headers, method='PATCH')
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode()), None
    except urllib.error.HTTPError as e:
        return None, f'HTTP {e.code}: {e.read().decode()[:200]}'
    except Exception as e:
        return None, str(e)


# ─── HMAC verification of the signed payload from social-verifier ────────────
def _b64url_decode(s: str) -> bytes:
    s = s + '=' * (-len(s) % 4)
    return base64.urlsafe_b64decode(s.encode())


def verify_token(token: str):
    """Returns (payload_dict, None) on success, (None, error_message) on failure."""
    secret = os.environ.get('SOCIAL_VERIFIER_SECRET', '')
    if not secret:
        return None, 'server_missing_verifier_secret'
    if not token or '.' not in token:
        return None, 'malformed_token'
    body_b64, sig_b64 = token.split('.', 1)
    expected = hmac.new(
        secret.encode(),
        body_b64.encode(),
        hashlib.sha256,
    ).digest()
    expected_b64 = base64.urlsafe_b64encode(expected).rstrip(b'=').decode()
    if not hmac.compare_digest(sig_b64, expected_b64):
        return None, 'bad_signature'
    try:
        payload = json.loads(_b64url_decode(body_b64).decode())
    except Exception:
        return None, 'malformed_payload'
    iat = payload.get('iat')
    if not isinstance(iat, (int, float)) or (time.time() * 1000) - iat > MAX_TOKEN_AGE_MS:
        return None, 'token_expired'
    platform = payload.get('platform')
    if platform not in SUPPORTED_PLATFORMS:
        return None, 'unsupported_platform'
    return payload, None


# ─── Response helpers ─────────────────────────────────────────────────────────
def _send(handler: BaseHTTPRequestHandler, status: int, body: dict):
    data = json.dumps(body).encode()
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json')
    handler.send_header('Content-Length', str(len(data)))
    handler.send_header('Access-Control-Allow-Origin', '*')
    handler.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
    handler.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
    handler.end_headers()
    handler.wfile.write(data)


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        _send(self, 204, {})

    def do_GET(self):
        _send(self, 200, {
            'ok': True,
            'endpoint': '/api/verify_social',
            'elite_threshold': ELITE_THRESHOLD,
        })

    def do_POST(self):
        # ---- parse body --------------------------------------------------------
        try:
            length = int(self.headers.get('Content-Length') or 0)
            raw    = self.rfile.read(length) if length else b'{}'
            body   = json.loads(raw or b'{}')
        except Exception as e:
            return _send(self, 400, {'success': False, 'error': f'bad_request: {e}'})

        creator_id = str(body.get('creator_id') or '').strip()
        token      = str(body.get('verification_token') or '').strip()

        if not creator_id:
            return _send(self, 400, {'success': False, 'error': 'creator_id is required.'})
        if not token:
            return _send(self, 400, {'success': False, 'error': 'verification_token is required.'})

        # ---- verify HMAC -------------------------------------------------------
        payload, err = verify_token(token)
        if err:
            return _send(self, 400, {'success': False, 'error': 'Account is private or invalid.',
                                     'detail': err})

        # Defense-in-depth: the token must have been issued for THIS creator.
        token_creator = str(payload.get('creator_id') or '').strip()
        if token_creator and token_creator != creator_id:
            return _send(self, 403, {'success': False, 'error': 'creator_id_mismatch'})

        platform  = str(payload.get('platform') or '').lower()
        username  = str(payload.get('username') or '')
        followers = int(payload.get('followers') or 0)
        photo     = payload.get('profile_photo') or ''

        # ---- locate the creator row -------------------------------------------
        rows, err_get = sb_get(
            'creators',
            select='id,shopify_customer_id,commission_tier,is_elite,verified_follower_count',
            filters={'shopify_customer_id': f'eq.{creator_id}'},
            limit=1,
        )
        if err_get:
            return _send(self, 502, {'success': False, 'error': 'supabase_lookup_failed',
                                     'detail': err_get})
        if not rows:
            return _send(self, 404, {'success': False, 'error': 'creator_not_found'})

        creator  = rows[0]
        now_iso  = datetime.now(timezone.utc).isoformat()

        # ---- below Elite threshold: keep_growing -----------------------------
        if followers < ELITE_THRESHOLD:
            # Store the latest verified handle + count so the UI can show progress.
            sb_patch(
                'creators',
                {
                    'social_platform_verified': platform,
                    'verified_follower_count':  followers,
                    'elite_verified_handle':    username,
                    'updated_at':               now_iso,
                },
                'shopify_customer_id',
                creator_id,
            )
            remaining = ELITE_THRESHOLD - followers
            return _send(self, 200, {
                'success':   True,
                'status':    'keep_growing',
                'platform':  platform,
                'username':  username,
                'followers': followers,
                'remaining': remaining,
                'threshold': ELITE_THRESHOLD,
                'message':   (f'You have {followers:,} followers on {platform}. '
                              f'Reach {ELITE_THRESHOLD:,} to unlock Elite status!'),
            })

        # ---- Elite! upgrade the creator --------------------------------------
        updated, err_up = sb_patch(
            'creators',
            {
                'is_elite':                 True,
                'commission_tier':          'elite',
                'social_platform_verified': platform,
                'verified_follower_count':  followers,
                'elite_verified_handle':    username,
                'elite_verified_at':        now_iso,
                'updated_at':               now_iso,
            },
            'shopify_customer_id',
            creator_id,
        )
        if err_up:
            return _send(self, 502, {'success': False, 'error': 'supabase_update_failed',
                                     'detail': err_up})

        was_already = bool(creator.get('is_elite'))
        return _send(self, 200, {
            'success':        True,
            'status':         'already_elite' if was_already else 'upgraded',
            'platform':       platform,
            'username':       username,
            'profile_photo':  photo,
            'followers':      followers,
            'commission_tier': 'elite',
            'commission_pct': ELITE_COMMISSION_PCT,
            'message':        ('You are already an Elite Creator — stats refreshed.'
                               if was_already else 'Welcome to the Elite Tier!'),
        })
