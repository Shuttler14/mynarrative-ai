import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '_lib'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'creator-economy-api', 'api'))

from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse
import json

ROUTES = [
    ('/api/webhook/shopify', 'dtf_pipeline'),
    ('/api/webhook/shopify/health', 'dtf_pipeline'),
    ('/api/dtf/health', 'dtf_pipeline'),
    ('/api/dtf/process', 'dtf_pipeline'),
    ('/api/webhook/order_paid', 'shopify_webhook'),
    ('/api/webhook/order_fulfilled', 'shopify_webhook'),
    ('/api/webhook/order_refunded', 'shopify_webhook'),
    ('/api/webhook/health', 'shopify_webhook'),
    ('/api/webhook/design-order', 'design_order_webhook'),
    ('/api/webhook/design-order/health', 'design_order_webhook'),
    ('/api/webhook/design-refund', 'design_refund_webhook'),
    ('/api/webhook/design-refund/health', 'design_refund_webhook'),
    ('/api/designs', 'design_feed'),
    ('/api/design/process', 'design_pipeline'),
    ('/api/design/pipeline/health', 'design_pipeline'),
    ('/api/design/publish', 'design_publish'),
    ('/api/design/publish/health', 'design_publish'),
    ('/api/design/feed', 'design_social_feed'),
    ('/api/design/feed/health', 'design_social_feed'),
    ('/api/fulfillment/generate_gang_sheet', 'generate_gang_sheet'),
    ('/api/creator/earnings', 'creator_earnings'),
    ('/api/creator/earnings/summary', 'creator_earnings'),
    ('/api/creator/earnings/health', 'creator_earnings'),
    ('/api/classify_item', 'classify_item'),
    ('/api/cloth_detection', 'cloth_detection'),
    ('/api/fashion_consultant', 'fashion_consultant'),
    ('/api/generate_design', 'generate_design'),
    ('/api/generate_slogans', 'generate_slogans'),
    ('/api/physique_analyze', 'physique_analyze'),
    ('/api/profile_manager', 'profile_manager'),
    ('/api/secure_image', 'secure_image'),
    ('/api/shopify_product', 'shopify_product'),
    ('/api/user_profile', 'user_profile'),
    ('/api/verify_social', 'verify_social'),
]

class handler(BaseHTTPRequestHandler):
    def _resolve(self):
        path = urlparse(self.path).path.rstrip('/')
        for route_path, module_name in ROUTES:
            if path == route_path:
                return module_name
        if path.startswith('/api/creator/'):
            return 'creator_economy'
        return None

    def _dispatch(self, method):
        module_name = self._resolve()
        if module_name is None:
            self.send_response(404)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'no_route'}).encode())
            return
        try:
            mod = __import__(module_name)
            handler_cls = mod.handler
            getattr(handler_cls, method)(self)
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'dispatch_failed', 'detail': str(e)}).encode())

    def do_GET(self):
        self._dispatch('do_GET')

    def do_POST(self):
        self._dispatch('do_POST')

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.send_header('Access-Control-Max-Age', '86400')
        self.end_headers()
