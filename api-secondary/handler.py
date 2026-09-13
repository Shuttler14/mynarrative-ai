from http.server import BaseHTTPRequestHandler
import sys
import os
import json

sys.path.insert(0, os.path.dirname(__file__))

ROUTES = {
    "/api/classify": "classify_item",
    "/api/cloth-detect": "cloth_detection",
    "/api/fashion": "fashion_consultant",
    "/api/physique": "physique_analyze",
    "/api/profile": "profile_manager",
    "/api/secure-image": "secure_image",
    "/api/shopify-product": "shopify_product",
    "/api/stylist": "stylist_pipeline",
    "/api/user": "user_profile",
    "/api/verify-social": "verify_social",
    "/api/virtual-tryon": "virtual_try_on",
}


class handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _resolve_module(self):
        path = self.path.split("?")[0]
        for prefix, module in sorted(ROUTES.items(), key=lambda x: -len(x[0])):
            if path.startswith(prefix):
                return module
        return None

    def _delegate(self, method):
        module_name = self._resolve_module()
        if not module_name:
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Not found", "path": self.path}).encode())
            return
        try:
            mod = __import__(module_name)
            sub_cls = mod.handler
            sub_inst = sub_cls(self.request, self.client_address, self.server)
            sub_inst.path = self.path
            sub_inst.command = self.command
            getattr(sub_inst, f"do_{method}")()
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e), "traceback": tb[-500:]}).encode())

    def do_GET(self):
        self._delegate("GET")

    def do_POST(self):
        self._delegate("POST")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
