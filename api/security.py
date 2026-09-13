"""
Security Middleware — Rate Limiting, Input Validation, Request Signing, Error Sanitization.
All API gateways MUST use these functions for security.
"""
import hashlib
import hmac
import json
import os
import re
import time
from functools import wraps
from typing import Any, Dict, Optional, Tuple

# ═══════════════════════════════════════════════════════════════════════════
# RATE LIMITING (in-memory, per-serverless-instance)
# ═══════════════════════════════════════════════════════════════════════════

_rate_limit_store: Dict[str, list] = {}

RATE_LIMITS = {
    "default":       {"requests": 60,  "window": 60},
    "auth":          {"requests": 10,  "window": 60},
    "recommend":     {"requests": 20,  "window": 60},
    "upload":        {"requests": 10,  "window": 300},
    "webhook":       {"requests": 100, "window": 60},
    "bootstrap":     {"requests": 30,  "window": 60},
    "brand_search":  {"requests": 30,  "window": 60},
}


def check_rate_limit(key: str, tier: str = "default") -> Tuple[bool, dict]:
    """
    Check if a request is within rate limits.
    Returns (allowed, info_dict).
    """
    now = time.time()
    config = RATE_LIMITS.get(tier, RATE_LIMITS["default"])
    window = config["window"]
    max_requests = config["requests"]

    if key not in _rate_limit_store:
        _rate_limit_store[key] = []

    # Clean old entries
    _rate_limit_store[key] = [t for t in _rate_limit_store[key] if now - t < window]

    current = len(_rate_limit_store[key])
    remaining = max(0, max_requests - current)

    if current >= max_requests:
        retry_after = int(window - (now - _rate_limit_store[key][0]))
        return False, {
            "error": "rate_limit_exceeded",
            "retry_after": max(1, retry_after),
            "limit": max_requests,
            "remaining": 0,
            "window": window,
        }

    _rate_limit_store[key].append(now)
    return True, {
        "limit": max_requests,
        "remaining": remaining - 1,
        "window": window,
    }


def get_client_ip(headers) -> str:
    """Extract client IP from headers (Vercel/Cloudflare)."""
    return (
        headers.get("x-forwarded-for", "").split(",")[0].strip()
        or headers.get("x-real-ip", "")
        or headers.get("cf-connecting-ip", "")
        or "unknown"
    )


# ═══════════════════════════════════════════════════════════════════════════
# INPUT VALIDATION & SANITIZATION
# ═══════════════════════════════════════════════════════════════════════════

# Maximum request body size (500KB)
MAX_BODY_SIZE = 512000

# Blocked patterns for injection attacks
_INJECTION_PATTERNS = [
    re.compile(r'(\b(UNION|SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|EXEC|EXECUTE)\b)', re.IGNORECASE),
    re.compile(r'(--|;|\/\*|\*\/|xp_)', re.IGNORECASE),
    re.compile(r'(\b(OR|AND)\b\s+\d+\s*=\s*\d+)', re.IGNORECASE),
    re.compile(r'<script[^>]*>', re.IGNORECASE),
    re.compile(r'javascript:', re.IGNORECASE),
    re.compile(r'on\w+\s*=', re.IGNORECASE),
    re.compile(r'(\.\.\/|\.\.\\)', re.IGNORECASE),
]

# Allowed characters for API keys
_API_KEY_PATTERN = re.compile(r'^mn_(live|test)_[a-f0-9]{48}$')

# UUID pattern
_UUID_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)


def validate_body_size(content_length: int) -> bool:
    """Check if request body is within size limits."""
    return 0 <= content_length <= MAX_BODY_SIZE


def sanitize_string(value: str, max_length: int = 500) -> str:
    """Sanitize a string input — strip, truncate, remove control chars."""
    if not isinstance(value, str):
        return ""
    # Remove control characters (keep newlines)
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', value)
    return cleaned.strip()[:max_length]


def check_injection(value: str) -> bool:
    """Check if a string contains SQL/XSS injection patterns. Returns True if suspicious."""
    if not isinstance(value, str):
        return False
    return any(p.search(value) for p in _INJECTION_PATTERNS)


def validate_api_key_format(key: str) -> bool:
    """Validate API key format without hitting the database."""
    return bool(key and _API_KEY_PATTERN.match(key))


def validate_uuid(value: str) -> bool:
    """Validate UUID format."""
    return bool(value and _UUID_PATTERN.match(value))


def sanitize_body(body: dict, allowed_fields: set = None, max_fields: int = 20) -> dict:
    """
    Sanitize request body:
    - Remove unexpected fields
    - Truncate strings
    - Check for injection patterns
    - Limit field count
    """
    if not isinstance(body, dict):
        return {}

    sanitized = {}
    field_count = 0

    for key, value in body.items():
        if field_count >= max_fields:
            break

        # Skip internal fields
        if key.startswith("_"):
            continue

        # If allowed_fields is set, only accept those
        if allowed_fields and key not in allowed_fields:
            continue

        if isinstance(value, str):
            value = sanitize_string(value)
            if check_injection(value):
                continue  # Drop suspicious values silently
            sanitized[key] = value
        elif isinstance(value, (int, float)):
            # Clamp numeric values
            sanitized[key] = max(-999999999, min(999999999, value))
        elif isinstance(value, bool):
            sanitized[key] = value
        elif isinstance(value, list):
            # Only allow lists of strings, max 20 items
            sanitized[key] = [sanitize_string(str(v)) for v in value[:20]]
        elif isinstance(value, dict):
            # Only allow 1 level deep
            sub = {}
            for sk, sv in value.items():
                if len(sub) >= 10:
                    break
                if isinstance(sv, str):
                    sub[sk] = sanitize_string(sv, 200)
                elif isinstance(sv, (int, float, bool)):
                    sub[sk] = sv
            sanitized[key] = sub
        field_count += 1

    return sanitized


# ═══════════════════════════════════════════════════════════════════════════
# REQUEST SIGNING (HMAC-SHA256)
# ═══════════════════════════════════════════════════════════════════════════

SIGNING_SECRET = os.environ.get("REQUEST_SIGNING_SECRET", "")


def sign_request(payload: str, timestamp: str) -> str:
    """Create HMAC-SHA256 signature for a request payload."""
    if not SIGNING_SECRET:
        return ""
    message = f"{timestamp}.{payload}"
    return hmac.new(
        SIGNING_SECRET.encode(), message.encode(), hashlib.sha256
    ).hexdigest()


def verify_request_signature(payload: str, timestamp: str, signature: str, max_age: int = 300) -> bool:
    """
    Verify HMAC-SHA256 request signature.
    max_age: maximum age of request in seconds (default 5 min).
    """
    if not SIGNING_SECRET or not signature:
        return False

    # Check timestamp freshness
    try:
        ts = float(timestamp)
        if abs(time.time() - ts) > max_age:
            return False
    except (ValueError, TypeError):
        return False

    expected = sign_request(payload, timestamp)
    return hmac.compare_digest(expected, signature)


# ═══════════════════════════════════════════════════════════════════════════
# WEBHOOK SIGNATURE VERIFICATION
# ═══════════════════════════════════════════════════════════════════════════

def verify_razorpay_signature(body: bytes, signature: str, secret: str = "") -> bool:
    """Verify Razorpay webhook signature (HMAC SHA256)."""
    secret = secret or os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def verify_stripe_signature(body: bytes, sig_header: str, secret: str = "") -> bool:
    """Verify Stripe webhook signature (v1)."""
    secret = secret or os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    if not secret or not sig_header:
        return False

    try:
        elements = dict(item.split("=", 1) for item in sig_header.split(","))
        timestamp = elements.get("t", "")
        expected_sig = elements.get("v1", "")

        signed_payload = f"{timestamp}.{body.decode('utf-8')}"
        expected = hmac.new(secret.encode(), signed_payload.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, expected_sig)
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════════════════
# ERROR SANITIZATION
# ═══════════════════════════════════════════════════════════════════════════

# Patterns to strip from error messages
_ERROR_PATTERNS = [
    (re.compile(r'SUPABASE_URL[^\s]*', re.IGNORECASE), '[REDACTED]'),
    (re.compile(r'SUPABASE_KEY[^\s]*', re.IGNORECASE), '[REDACTED]'),
    (re.compile(r'OPENAI_API_KEY[^\s]*', re.IGNORECASE), '[REDACTED]'),
    (re.compile(r'REPLICATE_API_TOKEN[^\s]*', re.IGNORECASE), '[REDACTED]'),
    (re.compile(r'sk_live_\w+', re.IGNORECASE), '[REDACTED_KEY]'),
    (re.compile(r'sk_test_\w+', re.IGNORECASE), '[REDACTED_KEY]'),
    (re.compile(r'Bearer\s+\w+', re.IGNORECASE), 'Bearer [REDACTED]'),
    (re.compile(r'password[=:]\s*\S+', re.IGNORECASE), 'password=[REDACTED]'),
    (re.compile(r'File "(/[^"]+")', re.IGNORECASE), 'File "[internal]"'),
]


def sanitize_error(error: Exception) -> str:
    """Sanitize an error message — remove sensitive info, stack traces, file paths."""
    msg = str(error)

    # Apply redaction patterns
    for pattern, replacement in _ERROR_PATTERNS:
        msg = pattern.sub(replacement, msg)

    # Truncate long messages
    if len(msg) > 200:
        msg = msg[:200] + "..."

    # Map known internal errors to safe messages
    safe_messages = {
        "connection refused": "Service temporarily unavailable",
        "timeout": "Request timed out, please try again",
        "dns": "Service temporarily unavailable",
        "ENOTFOUND": "Service temporarily unavailable",
    }

    msg_lower = msg.lower()
    for pattern, safe_msg in safe_messages.items():
        if pattern in msg_lower:
            return safe_msg

    return msg


def safe_error_response(error: Exception, status: int = 500) -> dict:
    """Create a safe error response that never leaks internals."""
    return {
        "success": False,
        "error": sanitize_error(error),
        "status": status,
    }


# ═══════════════════════════════════════════════════════════════════════════
# SECURITY HEADERS
# ═══════════════════════════════════════════════════════════════════════════

def security_headers() -> dict:
    """Return security headers for API responses."""
    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
        "Cache-Control": "no-store, no-cache, must-revalidate, private",
        "Pragma": "no-cache",
    }


def cors_headers(origin: str = "", allow_all: bool = False) -> dict:
    """Return CORS headers. Prefer allow_all=False with explicit origins."""
    allowed_origins = os.environ.get("CORS_ORIGINS", "https://mynarrative.store,https://www.mynarrative.store").split(",")

    if allow_all:
        allowed = "*"
    elif origin in allowed_origins:
        allowed = origin
    else:
        allowed = allowed_origins[0] if allowed_origins else "https://mynarrative.store"

    return {
        "Access-Control-Allow-Origin": allowed,
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, X-API-Key, X-Session-Token, X-User-ID, X-Request-Signature, X-Timestamp",
        "Access-Control-Max-Age": "86400",
        "Access-Control-Allow-Credentials": "true",
    }


# ═══════════════════════════════════════════════════════════════════════════
# BOT / SCRAPING DETECTION
# ═══════════════════════════════════════════════════════════════════════════

BOT_PATTERNS = [
    re.compile(r'bot|crawler|spider|scraper|curl|wget|python-requests|postman|httpclient', re.IGNORECASE),
]


def is_bot_request(user_agent: str) -> bool:
    """Detect non-browser user agents (bots, scrapers)."""
    if not user_agent:
        return True  # No user agent = suspicious
    return any(p.search(user_agent) for p in BOT_PATTERNS)


# ═══════════════════════════════════════════════════════════════════════════
# COMBINED SECURITY CHECK
# ═══════════════════════════════════════════════════════════════════════════

def security_check(handler, body: dict, tier: str = "default") -> Tuple[bool, dict, dict]:
    """
    Run all security checks on an incoming request.
    Returns (passed, rate_limit_info, sanitized_body).
    """
    ip = get_client_ip(handler.headers)
    ua = handler.headers.get("User-Agent", "")

    # 1. Bot detection
    if is_bot_request(ua):
        return False, {"error": "forbidden", "status": 403}, {}

    # 2. Rate limiting
    rate_key = f"{tier}:{ip}"
    allowed, rate_info = check_rate_limit(rate_key, tier)
    if not allowed:
        return False, rate_info, {}

    # 3. Body size check
    content_length = int(handler.headers.get("Content-Length", 0))
    if not validate_body_size(content_length):
        return False, {"error": "payload_too_large", "status": 413}, {}

    # 4. Input sanitization
    sanitized = sanitize_body(body)

    return True, rate_info, sanitized
