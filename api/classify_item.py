"""
Image Classification API using GPT-4o-mini
Classifies uploaded wardrobe items with category, color, style, etc.
"""
from http.server import BaseHTTPRequestHandler
import json
import os
import base64
from openai import OpenAI

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        try:
            # Parse request
            content_length = int(self.headers['Content-Length'])
            body = json.loads(self.rfile.read(content_length).decode('utf-8'))
            
            image_data = body.get('image')  # Base64 encoded image
            
            if not image_data:
                raise ValueError("No image provided")

            # Initialize OpenAI
            client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
            
            # Call GPT-4o-mini Vision API
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """You are a fashion expert AI that classifies clothing and accessories.
                        Analyze the image and return ONLY a valid JSON object with these fields:
                        {
                            "category": "one of: shirt, t-shirt, hoodie, jacket, pants, jeans, shorts, skirt, dress, shoes, sneakers, boots, hat, bag, accessory, jewelry, other",
                            "subcategory": "more specific type (e.g., 'denim jacket', 'running shoes')",
                            "color": "primary color",
                            "secondaryColor": "secondary color if any, otherwise null",
                            "pattern": "solid, striped, floral, graphic, logo, etc.",
                            "material": "cotton, denim, leather, synthetic, etc.",
                            "style": "casual, formal, streetwear, athletic, etc.",
                            "season": "summer, winter, spring, fall, all-season",
                            "brand": "if visible, otherwise null",
                            "confidence": 0.0-1.0
                        }
                        Return ONLY the JSON, no other text."""
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image_data
                                }
                            }
                        ]
                    }
                ],
                max_tokens=300
            )
            
            # Parse GPT response
            classification = json.loads(response.choices[0].message.content)
            
            # Success response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": True,
                "classification": classification
            }).encode('utf-8'))

        except json.JSONDecodeError as e:
            # GPT returned non-JSON, try to extract or fallback
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": True,
                "classification": {
                    "category": "clothing",
                    "subcategory": "unknown",
                    "color": "unknown",
                    "secondaryColor": None,
                    "pattern": "unknown",
                    "material": "unknown",
                    "style": "casual",
                    "season": "all-season",
                    "brand": None,
                    "confidence": 0.5
                },
                "note": "GPT returned non-JSON, using fallback"
            }).encode('utf-8'))

        except Exception as e:
            # Error Response
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": False, 
                "error": str(e)
            }).encode('utf-8'))
