"""Health check handler."""
import os
import time

_start_time = time.time()


def handle_health() -> dict:
    """Platform health check."""
    import urllib.request
    import json

    db_ok = False
    ai_ok = False
    db_error = ""

    # Check Supabase — query actual table with both headers
    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_KEY", "")
    if supabase_url and supabase_key:
        try:
            req = urllib.request.Request(
                f"{supabase_url.rstrip('/')}/rest/v1/brands?select=id&limit=1",
                method="GET",
            )
            req.add_header("apikey", supabase_key)
            req.add_header("Authorization", f"Bearer {supabase_key}")
            req.add_header("Range", "0-0")
            with urllib.request.urlopen(req, timeout=10) as resp:
                db_ok = resp.status in (200, 206)
        except Exception as e:
            db_error = str(e)[:200]

    # Check OpenAI
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if openai_key:
        ai_ok = True  # Just check if key exists

    return {
        "status": "healthy" if db_ok else "degraded",
        "version": "1.0.0",
        "uptime_seconds": round(time.time() - _start_time),
        "db": "ok" if db_ok else "error",
        "db_error": db_error if not db_ok else "",
        "ai": "ok" if ai_ok else "error",
        "supabase_url_set": bool(supabase_url),
        "supabase_key_set": bool(supabase_key),
    }
