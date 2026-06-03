#!/usr/bin/env python3
"""
monitor_endpoints.py — My Narrative Production Uptime Monitor
==============================================================
Checks all production endpoints and reports status.
Can be run manually or scheduled (cron / GitHub Actions / Windows Task Scheduler).

Usage:
    python scripts/monitor_endpoints.py              # single check
    python scripts/monitor_endpoints.py --watch 60   # check every 60 seconds
    python scripts/monitor_endpoints.py --notify     # send alert on failure (Slack/email)

Exit codes:
    0 = all endpoints healthy
    1 = one or more endpoints failed
"""

import urllib.request
import urllib.error
import json
import sys
import time
import os
from datetime import datetime, timezone

# ─────────────────────────────────────────────────────────────
# PRODUCTION ENDPOINTS TO MONITOR
# ─────────────────────────────────────────────────────────────
PROD_URL = os.environ.get(
    "VERCEL_DEPLOYMENT_URL",
    "https://creator-economy-rl1uvgob6-aryans-projects-af8c9a95.vercel.app"
)

ENDPOINTS = [
    # Critical path — must always be 200
    {"path": "/api/webhook/health",                "name": "Shopify Webhook",         "critical": True},
    {"path": "/api/webhook/design-order/health",   "name": "D2E Order Webhook",       "critical": True},
    {"path": "/api/webhook/design-refund/health",  "name": "D2E Refund Webhook",      "critical": True},
    {"path": "/api/design/publish/health",         "name": "Publish Handler",         "critical": True},
    {"path": "/api/design/pipeline/health",        "name": "AI Pipeline",             "critical": True},
    {"path": "/api/design/feed/health",            "name": "Social Feed",             "critical": True},
    {"path": "/api/creator/earnings/health",       "name": "Earnings API",            "critical": True},
    # Data endpoints — verify they return valid data
    {"path": "/api/design/feed?limit=1",           "name": "Feed Data",               "critical": False, "check_key": "designs"},
    {"path": "/api/creator/earnings?creator_id=monitor-check",
                                                   "name": "Earnings Data",           "critical": False, "check_key": "summary"},
    {"path": "/api/designs",                       "name": "Legacy Feed",             "critical": False},
]

# ─────────────────────────────────────────────────────────────
# ALERT CONFIG (optional — set env vars to enable)
# ─────────────────────────────────────────────────────────────
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
ALERT_EMAIL       = os.environ.get("ALERT_EMAIL", "")


def check_endpoint(ep, base_url=PROD_URL, timeout=20):
    """Check a single endpoint. Returns result dict."""
    url      = f"{base_url}{ep['path']}"
    start    = time.time()
    result   = {
        "name":     ep["name"],
        "path":     ep["path"],
        "url":      url,
        "status":   None,
        "latency":  None,
        "ok":       False,
        "error":    None,
        "response": None,
        "critical": ep.get("critical", True),
        "check_key": ep.get("check_key"),
    }
    try:
        req = urllib.request.Request(url)
        req.add_header("Accept", "application/json")
        req.add_header("User-Agent", "MyNarrative-Monitor/1.0")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            latency = round((time.time() - start) * 1000)
            body    = json.loads(r.read().decode())
            result["status"]   = r.status
            result["latency"]  = latency
            result["response"] = body

            # Basic validation
            if r.status == 200:
                check_key = ep.get("check_key")
                if check_key and check_key not in body:
                    result["ok"]    = False
                    result["error"] = f"Missing key '{check_key}' in response"
                else:
                    result["ok"] = True
            else:
                result["ok"]    = False
                result["error"] = f"Non-200 status: {r.status}"

    except urllib.error.HTTPError as e:
        result["status"]  = e.code
        result["latency"] = round((time.time() - start) * 1000)
        result["error"]   = f"HTTP {e.code}"
    except urllib.error.URLError as e:
        result["latency"] = round((time.time() - start) * 1000)
        result["error"]   = f"Connection error: {str(e.reason)[:50]}"
    except Exception as e:
        result["latency"] = round((time.time() - start) * 1000)
        result["error"]   = str(e)[:80]

    return result


def run_check(base_url=PROD_URL, verbose=True):
    """Run all endpoint checks. Returns (all_ok, results_list)."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    if verbose:
        print(f"\n{'='*65}")
        print(f"  MY NARRATIVE — Endpoint Health Check")
        print(f"  {ts}")
        print(f"  URL: {base_url}")
        print(f"{'='*65}\n")

    results  = []
    failures = []

    for ep in ENDPOINTS:
        r = check_endpoint(ep, base_url)
        results.append(r)

        if verbose:
            icon    = "✅" if r["ok"] else "❌"
            lat     = f"{r['latency']}ms" if r["latency"] else "---"
            status  = r["status"] or "ERR"
            err     = f" — {r['error']}" if r["error"] else ""
            crit    = " [CRITICAL]" if r["critical"] and not r["ok"] else ""
            print(f"  {icon} [{status}] {r['name']} ({lat}){err}{crit}")

        if not r["ok"]:
            failures.append(r)

    all_ok = len(failures) == 0
    critical_failures = [f for f in failures if f["critical"]]

    if verbose:
        print(f"\n{'─'*65}")
        passed = len(results) - len(failures)
        print(f"  Result: {passed}/{len(results)} endpoints healthy")
        if failures:
            print(f"  Failures: {[f['name'] for f in failures]}")
        if critical_failures:
            print(f"  CRITICAL failures: {[f['name'] for f in critical_failures]}")
        print(f"{'='*65}\n")

    return all_ok, results


def send_slack_alert(failures, base_url):
    """Send Slack alert for failures."""
    if not SLACK_WEBHOOK_URL:
        return
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": "🚨 My Narrative API Alert"}},
        {"type": "section", "text": {"type": "mrkdwn",
            "text": f"*{len(failures)} endpoint(s) failing* at `{ts}`\nURL: `{base_url}`"}},
    ]
    for f in failures:
        blocks.append({"type": "section", "text": {"type": "mrkdwn",
            "text": f"❌ *{f['name']}* — `{f['path']}`\nError: {f['error']}"}})

    payload = json.dumps({"blocks": blocks}).encode()
    req = urllib.request.Request(SLACK_WEBHOOK_URL, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10):
            print(f"  Slack alert sent ({len(failures)} failures)")
    except Exception as e:
        print(f"  Slack alert failed: {e}")


def watch_mode(interval_seconds, base_url=PROD_URL):
    """Continuously monitor every N seconds."""
    print(f"Watching {base_url}")
    print(f"Checking every {interval_seconds}s — Ctrl+C to stop\n")
    consecutive_failures = 0
    try:
        while True:
            all_ok, results = run_check(base_url, verbose=True)
            if not all_ok:
                consecutive_failures += 1
                failures = [r for r in results if not r["ok"]]
                if consecutive_failures >= 2 and SLACK_WEBHOOK_URL:
                    send_slack_alert(failures, base_url)
            else:
                consecutive_failures = 0
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")


if __name__ == "__main__":
    args = sys.argv[1:]

    if "--watch" in args:
        idx = args.index("--watch")
        interval = int(args[idx + 1]) if idx + 1 < len(args) else 60
        watch_mode(interval)
    else:
        all_ok, results = run_check(verbose=True)

        if "--json" in args:
            print(json.dumps(results, indent=2))

        if not all_ok:
            failures = [r for r in results if not r["ok"]]
            if "--notify" in args:
                send_slack_alert(failures, PROD_URL)
            sys.exit(1)
        sys.exit(0)
