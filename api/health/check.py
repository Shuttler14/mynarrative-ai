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

    # Check Supabase
    supabase_url = os.environ.get("SUPABASE_URL", "")
    if supabase_url:
        try:
            req = urllib.request.Request(f"{supabase_url.rstrip('/')}/rest/v1/", method="GET")
            req.add_header("apikey", os.environ.get("SUPABASE_KEY", ""))
            with urllib.request.urlopen(req, timeout=5) as resp:
                db_ok = resp.status == 200
        except Exception:
            pass

    # Check OpenAI
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if openai_key:
        ai_ok = True  # Just check if key exists

    return {
        "status": "healthy" if db_ok else "degraded",
        "version": "1.0.0",
        "uptime_seconds": round(time.time() - _start_time),
        "db": "ok" if db_ok else "error",
        "ai": "ok" if ai_ok else "error"
    }
