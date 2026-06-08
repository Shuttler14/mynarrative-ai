"""
user_profile.py — User Profile Sync Handler
==========================================
Handles user profile synchronization with Supabase
"""

from http.server import BaseHTTPRequestHandler
import json
import os
from urllib.parse import urlparse, parse_qs

SUPABASE_AVAILABLE = False
supabase_client = None


def get_supabase():
    global supabase_client, SUPABASE_AVAILABLE
    if supabase_client is not None:
        return supabase_client
    
    try:
        from supabase import create_client
        supabase_url = os.environ.get("SUPABASE_URL", "")
        supabase_key = os.environ.get("SUPABASE_KEY", "")
        
        if supabase_url and supabase_key and supabase_url != "https://your-project-id.supabase.co":
            supabase_client = create_client(supabase_url, supabase_key)
            SUPABASE_AVAILABLE = True
    except Exception as e:
        print(f"Supabase init error: {e}")
        supabase_client = None
    
    return supabase_client


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def send_json_response(self, status, data):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        
        user_id = params.get('user_id', [None])[0]
        
        if not user_id:
            self.send_json_response(400, {"success": False, "error": "user_id is required"})
            return
        
        supabase = get_supabase()
        if not supabase:
            self.send_json_response(200, {
                "success": True,
                "message": "Demo mode - no data",
                "data": None
            })
            return
        
        try:
            result = supabase.table("profiles").select("*").eq("id", user_id).execute()
            if result.data:
                self.send_json_response(200, {"success": True, "data": result.data[0]})
            else:
                self.send_json_response(200, {"success": True, "data": None})
        except Exception as e:
            self.send_json_response(200, {"success": True, "data": None, "error": str(e)})

    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(content_length).decode('utf-8'))
        except:
            self.send_json_response(400, {"success": False, "error": "Invalid JSON"})
            return
        
        user_id = body.get('user_id')
        profile = body.get('profile', {})
        hidden_data = body.get('hidden_data', {})
        bank_cards = body.get('bank_cards', [])
        completion_pct = body.get('completion_pct', 0)
        ghost_mode = body.get('ghost_mode', False)
        
        if not user_id:
            self.send_json_response(400, {"success": False, "error": "user_id is required"})
            return
        
        supabase = get_supabase()
        if not supabase:
            self.send_json_response(200, {
                "success": True,
                "message": "Demo mode - profile not synced"
            })
            return
        
        try:
            data = {
                "id": user_id,
                "profile": profile,
                "hidden_data": hidden_data,
                "bank_cards": bank_cards,
                "completion_pct": completion_pct,
                "ghost_mode": ghost_mode,
                "updated_at": "now()"
            }
            
            result = supabase.table("profiles").upsert(data).execute()
            
            self.send_json_response(200, {
                "success": True,
                "message": "Profile synced successfully"
            })
        except Exception as e:
            self.send_json_response(200, {
                "success": True,
                "message": "Profile sync failed",
                "error": str(e)
            })
