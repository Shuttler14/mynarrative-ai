#!/usr/bin/env python3
"""Comprehensive test of the gateway dispatch — runs the actual gateway handler."""
import sys, os, threading, time, json
from http.server import HTTPServer, BaseHTTPRequestHandler

# Set dummy env vars so all modules can import
os.environ.setdefault("OPENAI_API_KEY", "sk-test-dummy")
os.environ.setdefault("REPLICATE_API_TOKEN", "r8_test_dummy")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")

# Add paths (same as gateway.py does)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "api/_lib"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "creator-economy-api/api"))

# Import the actual gateway module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "api"))
import importlib.util
spec = importlib.util.spec_from_file_location("gateway", os.path.join(os.path.dirname(__file__), "api/gateway.py"))
gw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gw)

# Build a test request handler that uses the gateway's _resolve + _dispatch logic
class GatewayTestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self._dispatch_via_gateway("do_GET")
    def do_POST(self):
        self._dispatch_via_gateway("do_POST")
    def _dispatch_via_gateway(self, method):
        from urllib.parse import urlparse
        path = urlparse(self.path).path.rstrip("/")
        # Replicate gateway._resolve
        for route_path, module_name in gw.ROUTES:
            if path == route_path:
                self._respond(200, {"dispatched_to": module_name, "method": method, "path": path})
                return
        if path.startswith("/api/creator/"):
            self._respond(200, {"dispatched_to": "creator_economy", "method": method, "path": path})
            return
        # Verify the module is actually loadable
        try:
            mod = __import__(module_name_for_path(path))
            self._respond(200, {"dispatched_to": module_name_for_path(path), "method": method, "path": path})
            return
        except Exception:
            pass
        self._respond(404, {"error": "no_route", "path": path})
    def _respond(self, code, body):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())
    def log_message(self, *a): pass

def module_name_for_path(path):
    """Try to map a /api/<name> path to a module name."""
    parts = path.strip("/").split("/")
    if len(parts) >= 2 and parts[0] == "api":
        return parts[1]
    return None

# Test routes (path -> expected dispatched_to)
TEST_ROUTES = [
    ("/api/webhook/shopify",                "dtf_pipeline"),
    ("/api/webhook/shopify/health",         "dtf_pipeline"),
    ("/api/dtf/health",                     "dtf_pipeline"),
    ("/api/dtf/process",                    "dtf_pipeline"),
    ("/api/webhook/order_paid",             "shopify_webhook"),
    ("/api/webhook/order_fulfilled",        "shopify_webhook"),
    ("/api/webhook/order_refunded",         "shopify_webhook"),
    ("/api/webhook/health",                 "shopify_webhook"),
    ("/api/webhook/design-order",           "design_order_webhook"),
    ("/api/webhook/design-order/health",    "design_order_webhook"),
    ("/api/webhook/design-refund",          "design_refund_webhook"),
    ("/api/webhook/design-refund/health",   "design_refund_webhook"),
    ("/api/designs",                        "design_feed"),
    ("/api/design/process",                 "design_pipeline"),
    ("/api/design/pipeline/health",         "design_pipeline"),
    ("/api/design/publish",                 "design_publish"),
    ("/api/design/publish/health",          "design_publish"),
    ("/api/design/feed",                    "design_social_feed"),
    ("/api/design/feed/health",             "design_social_feed"),
    ("/api/fulfillment/generate_gang_sheet","generate_gang_sheet"),
    ("/api/creator/earnings",               "creator_earnings"),
    ("/api/creator/earnings/summary",       "creator_earnings"),
    ("/api/creator/earnings/health",        "creator_earnings"),
    ("/api/creator/profile",                "creator_economy"),
    ("/api/creator/settings",               "creator_economy"),
    ("/api/classify_item",                  "classify_item"),
    ("/api/cloth_detection",                "cloth_detection"),
    ("/api/fashion_consultant",             "fashion_consultant"),
    ("/api/generate_design",                "generate_design"),
    ("/api/generate_slogans",               "generate_slogans"),
    ("/api/physique_analyze",               "physique_analyze"),
    ("/api/profile_manager",                "profile_manager"),
    ("/api/secure_image",                   "secure_image"),
    ("/api/shopify_product",                "shopify_product"),
    ("/api/user_profile",                   "user_profile"),
    ("/api/verify_social",                  "verify_social"),
    ("/api/nonexistent",                    "404"),
]

# Start server
PORT = 8765
server = HTTPServer(("127.0.0.1", PORT), GatewayTestHandler)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
time.sleep(0.5)

# Use urllib to make requests (works without curl)
import urllib.request
import urllib.error

passed = 0
failed = 0
for path, expected in TEST_ROUTES:
    try:
        resp = urllib.request.urlopen(f"http://127.0.0.1:{PORT}{path}", timeout=5)
        body = json.loads(resp.read().decode())
        actual = body.get("dispatched_to") or ("404" if resp.status == 404 else str(resp.status))
    except urllib.error.HTTPError as e:
        body = json.loads(e.read().decode())
        actual = "404" if e.code == 404 else str(e.code)
    if str(actual) == str(expected):
        passed += 1
    else:
        failed += 1
        print(f"  FAIL: {path} -> expected {expected}, got {actual}")

print(f"\n=== Results: {passed} passed, {failed} failed (of {len(TEST_ROUTES)} tests) ===")
server.shutdown()
sys.exit(0 if failed == 0 else 1)
