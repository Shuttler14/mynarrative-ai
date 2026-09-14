"""Health check handler."""
import os
import time

_start_time = time.time()


def handle_health() -> dict:
    """Platform health check."""
    import json
    import requests

    db_ok = False
    ai_ok = False
    db_error = ""

    # Check Supabase — query actual table with both headers
    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_KEY", "")
    if supabase_url and supabase_key:
        try:
            resp = requests.get(
                f"{supabase_url.rstrip('/')}/rest/v1/brands",
                params={"select": "id", "limit": "1"},
                headers={
                    "apikey": supabase_key,
                    "Authorization": f"Bearer {supabase_key}",
                    "Range": "0-0",
                },
                timeout=10,
            )
            db_ok = resp.status_code in (200, 206)
            if not db_ok:
                db_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
        except Exception as e:
            db_error = f"{type(e).__name__}: {str(e)[:200]}"

    # Check OpenAI
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if openai_key:
        ai_ok = True

    return {
        "status": "healthy" if db_ok else "degraded",
        "version": "1.2.0",
        "uptime_seconds": round(time.time() - _start_time),
        "db": "ok" if db_ok else "error",
        "db_error": db_error if not db_ok else "",
        "ai": "ok" if ai_ok else "error",
        "supabase_url_set": bool(supabase_url),
        "supabase_key_set": bool(supabase_key),
    }
