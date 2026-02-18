from http.server import BaseHTTPRequestHandler
import json
import os
import base64
import uuid
from supabase import create_client, Client

# Initialize Supabase
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key) if url and key else None

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        try:
            # Check if Supabase is configured
            if not supabase:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": False,
                    "error": "Supabase not configured. Please set SUPABASE_URL and SUPABASE_KEY in Vercel environment variables."
                }).encode('utf-8'))
                return

            # Parse request body
            content_length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(content_length).decode('utf-8'))
            
            action = body.get('action')  # 'save_twin' or 'add_item' or 'get_twin' or 'get_closet'
            user_id = body.get('user_id')  # Shopify Customer ID
            image_data = body.get('image')  # Base64 string

            if not user_id:
                raise ValueError("user_id is required")

            response = {}

            if action == 'save_twin':
                # Save Digital Twin (Master Photo)
                if not image_data:
                    raise ValueError("image data is required")

                # Convert base64 to bytes if needed
                if image_data.startswith('data:image'):
                    # Remove data:image/...;base64, prefix
                    image_data = image_data.split(',')[1]
                
                image_bytes = base64.b64decode(image_data)
                
                # Upload to Supabase Storage bucket 'digital-twins'
                file_path = f"{user_id}/master_photo.png"
                
                # Upload with upsert (replace if exists)
                upload_result = supabase.storage.from_("digital-twins").upload(
                    file_path, 
                    image_bytes,
                    {"content-type": "image/png", "upsert": "true"}
                )
                
                # Get Public URL
                public_url = supabase.storage.from_("digital-twins").get_public_url(file_path)
                
                # Update User Profile DB
                supabase.table("profiles").upsert({
                    "id": user_id, 
                    "twin_photo_url": public_url,
                    "updated_at": "now()"
                }).execute()
                
                response = {"success": True, "url": public_url}

            elif action == 'get_twin':
                # Retrieve Digital Twin URL
                result = supabase.table("profiles").select("twin_photo_url").eq("id", user_id).execute()
                
                if result.data and len(result.data) > 0:
                    response = {"success": True, "url": result.data[0].get("twin_photo_url")}
                else:
                    response = {"success": False, "url": None}

            elif action == 'add_item':
                # Add item to Digital Closet
                if not image_data:
                    raise ValueError("image data is required")

                # Convert base64 to bytes
                if image_data.startswith('data:image'):
                    image_data = image_data.split(',')[1]
                
                image_bytes = base64.b64decode(image_data)
                
                # Generate unique filename
                item_id = str(uuid.uuid4())
                file_name = f"{user_id}/{item_id}.png"
                
                # Upload to Supabase Storage 'closet'
                supabase.storage.from_("closet").upload(
                    file_name,
                    image_bytes,
                    {"content-type": "image/png"}
                )
                
                # Get Public URL
                image_url = supabase.storage.from_("closet").get_public_url(file_name)
                
                # --- GPT-4o CLASSIFICATION ---
                category = 'general'
                color = 'unknown'
                tags = []
                
                try:
                    from openai import OpenAI
                    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
                    
                    print(f"🤖 Analyzing image with GPT-4o...")
                    completion = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": "Analyze this clothing item. Return a JSON object with keys: 'category' (e.g. Tops, Bottoms, Footwear, Accessories), 'color' (dominant color name), and 'tags' (array of 3-5 descriptive keywords like style, material, pattern)."},
                                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}
                                ]
                            }
                        ],
                        response_format={"type": "json_object"},
                        max_tokens=300
                    )
                    
                    analysis = json.loads(completion.choices[0].message.content)
                    category = analysis.get('category', 'general')
                    color = analysis.get('color', 'unknown')
                    tags = analysis.get('tags', [])
                    print(f"✅ GPT-4o Analysis: {analysis}")
                    
                except Exception as gpt_error:
                    print(f"⚠️ GPT-4o Analysis Failed: {gpt_error}")
                    # Fallback to manual input if provided, or defaults
                    category = body.get('category', 'general')
                    color = body.get('color', 'unknown')
                    tags = body.get('tags', [])

                # Save Metadata to DB
                item_data = {
                    "id": item_id,
                    "user_id": user_id,
                    "image_url": image_url,
                    "category": category,
                    "color": color,
                    "tags": tags,
                    "created_at": "now()"
                }
                supabase.table("closet_items").insert(item_data).execute()
                
                response = {"success": True, "item": item_data}

            elif action == 'get_closet':
                # Retrieve all closet items for user
                result = supabase.table("closet_items").select("*").eq("user_id", user_id).execute()
                
                response = {"success": True, "items": result.data or []}

            elif action == 'delete_item':
                # Delete item from closet
                item_id = body.get('item_id')
                if not item_id:
                    raise ValueError("item_id is required")
                
                # Get item to find image path
                item = supabase.table("closet_items").select("*").eq("id", item_id).eq("user_id", user_id).execute()
                
                if item.data and len(item.data) > 0:
                    # Delete from storage
                    file_path = f"{user_id}/{item_id}.png"
                    supabase.storage.from_("closet").remove([file_path])
                    
                    # Delete from DB
                    supabase.table("closet_items").delete().eq("id", item_id).execute()
                    
                    response = {"success": True}
                else:
                    response = {"success": False, "error": "Item not found"}

            else:
                raise ValueError(f"Unknown action: {action}")

            # Send success response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode('utf-8'))

        except Exception as e:
            # Enhanced error handling
            error_msg = str(e)
            print(f"Error in profile_manager: {error_msg}")
            
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": False,
                "error": error_msg
            }).encode('utf-8'))
