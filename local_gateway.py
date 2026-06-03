#!/usr/bin/env python3
"""
local_gateway.py — Local API Gateway for Testing Vercel Python Functions
========================================================================
Parses vercel.json rewrites and emulates Vercel routing locally by importing
the handlers from the api/ folder and running a single Unified HTTP Server.
"""

import sys
import os
import json
import urllib.parse
import importlib.util
from http.server import HTTPServer, BaseHTTPRequestHandler

# Load environment variables
def load_env(path=".env.local"):
    if not os.path.exists(path):
        print(f"Env file {path} not found.")
        return
    print(f"Loading env from {path}...")
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                os.environ[k] = v
                # Print key name for verification (no value to be safe)
                print(f"  Env loaded: {k}")

# Define a routing table based on vercel.json
ROUTING_MAP = {
    "/api/tryon/compose": "api/vton_compositor.py",
    "/api/tryon/single": "api/virtual_try_on.py",
    "/api/tryon/full": "api/virtual_try_on.py",
    "/api/flatlay/extract": "api/flatlay_extractor.py",
    "/api/flatlay/classify": "api/flatlay_extractor.py",
    "/api/marketplace/search": "api/marketplace_scraper.py",
    "/api/marketplace/ingest": "api/marketplace_scraper.py",
    "/api/recommend": "api/recommendation_engine.py",
    "/api/looks": "api/user_looks.py",
}

# Add dynamic route prefixes for recommendation engine and looks
# e.g., /api/recommend/some_action -> api/recommendation_engine.py
# e.g., /api/looks/some_action -> api/user_looks.py

# Import modules dynamically
MODULE_CACHE = {}

def get_handler_class(filepath):
    if filepath in MODULE_CACHE:
        return MODULE_CACHE[filepath]
    
    module_name = filepath.replace("/", ".").replace(".py", "")
    print(f"Loading handler from {filepath} (module: {module_name})...")
    spec = importlib.util.spec_from_file_location(module_name, filepath)
    if spec is None or spec.loader is None:
        raise ValueError(f"Could not load spec for {filepath}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "handler"):
        raise AttributeError(f"Module {module_name} has no class 'handler'")
    MODULE_CACHE[filepath] = module.handler
    return module.handler

class LocalGatewayHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Forward logs to stdout with a prefix
        sys.stdout.write("GATEWAY LOG: %s\n" % (format % args))

    def _resolve_route(self, path):
        parsed = urllib.parse.urlparse(path)
        route_path = parsed.path
        
        # Exact match
        if route_path in ROUTING_MAP:
            return ROUTING_MAP[route_path]
            
        # Match with prefix
        for pattern, filepath in ROUTING_MAP.items():
            if route_path.startswith(pattern + "/"):
                return filepath
                
        # Legacy/direct matching for /api/<filename>
        direct_path = route_path.strip("/")
        if direct_path.startswith("api/"):
            py_file = direct_path + ".py"
            if os.path.exists(py_file):
                return py_file
        
        return None

    def handle_request(self, method):
        filepath = self._resolve_route(self.path)
        if not filepath:
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Route {self.path} not found in gateway routing"}).encode("utf-8"))
            return
            
        try:
            handler_class = get_handler_class(filepath)
            # Instantiate the Vercel handler. It inherits from BaseHTTPRequestHandler.
            # We override the methods so it executes within our context.
            
            # Save our own wfile, rfile, headers, path, command, request, client_address, server
            # and pass them to a new instance of the handler class.
            
            # Since HTTPServer expects a handler to be constructed, we can construct the target handler 
            # with our client request connection socket. But since we are already inside a handler,
            # we can copy the connection attributes.
            
            # A simpler way: instantiate the target handler class and copy the request context.
            target_instance = handler_class.__new__(handler_class)
            
            # Copy all attributes in __dict__
            for k, v in self.__dict__.items():
                setattr(target_instance, k, v)
            
            # Ensure critical HTTP handler attributes are copied
            target_instance.request = self.request
            target_instance.client_address = self.client_address
            target_instance.server = self.server
            target_instance.rfile = self.rfile
            target_instance.wfile = self.wfile
            target_instance.headers = self.headers
            target_instance.path = self.path
            target_instance.command = self.command
            target_instance.close_connection = self.close_connection
            target_instance.connection = getattr(self, "connection", None)
            target_instance.requestline = getattr(self, "requestline", "")
            
            # Initialize target instance if it expects initialization
            # BaseHTTPRequestHandler __init__ calls handle() which calls handle_one_request() etc.
            # We don't want to call __init__ because it will block/try to read/write.
            # Instead we just call the corresponding HTTP method: do_GET, do_POST, do_OPTIONS, etc.
            method_name = f"do_{method}"
            if hasattr(target_instance, method_name):
                method_fn = getattr(target_instance, method_name)
                print(f"🚀 Gateway routing {method} {self.path} -> {filepath}")
                method_fn()
            else:
                self.send_response(405)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"Method {method} not supported by handler"}).encode("utf-8"))
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Gateway invocation error: {str(e)}", "trace": traceback.format_exc()}).encode("utf-8"))

    def do_GET(self):
        self.handle_request("GET")

    def do_POST(self):
        self.handle_request("POST")

    def do_OPTIONS(self):
        self.handle_request("OPTIONS")

    def do_PUT(self):
        self.handle_request("PUT")

    def do_DELETE(self):
        self.handle_request("DELETE")

def run(port=8000):
    load_env()
    server_address = ('', port)
    httpd = HTTPServer(server_address, LocalGatewayHandler)
    print(f"\n========================================================")
    print(f"  MY NARRATIVE LOCAL GATEWAY ACTIVE ON PORT {port}")
    print(f"  Routes:")
    for path, script in ROUTING_MAP.items():
        print(f"    {path} -> {script}")
    print(f"========================================================\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping gateway...")
        httpd.server_close()

if __name__ == "__main__":
    port = 8000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
    run(port)
