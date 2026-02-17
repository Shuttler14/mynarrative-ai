from http.server import BaseHTTPRequestHandler
import json
import os
import replicate

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

        try:
            # 1. Auth Check
            token = os.environ.get("REPLICATE_API_TOKEN")
            if not token:
                raise ValueError("Server Config Error: Missing Replicate Token")
            
            client = replicate.Client(api_token=token)
            
            # 2. Parse Request
            content_length = int(self.headers['Content-Length'])
            body = json.loads(self.rfile.read(content_length))
            mode = body.get('mode', 'flux') # Default to Flux if not specified

            output_url = ""

            # ---------------------------------------------------------
            # MODE A: VIRTUAL TRY-ON (Product Page - IDM-VTON)
            # Cost: ~$0.02 - $0.05
            # ---------------------------------------------------------
            if mode == 'vton':
                human_img = body.get('user_image')     # Base64 or URL
                garm_img = body.get('garment_image')   # URL from Shopify CDN
                category = body.get('category', 'upper_body') 
                
                # Using IDM-VTON model
                output = client.run(
                    "cuuupid/idm-vton:c871bb9b046607e580c22118d58d01d4ce893999830f6e61e6d262172740922e",
                    input={
                        "human_img": human_img,
                        "garm_img": garm_img,
                        "garment_des": body.get('description', "clothing item"),
                        "category": category,
                        "crop": False,
                        "seed": 42,
                        "steps": 30
                    }
                )
                output_url = output # IDM-VTON returns a string URL

            # ---------------------------------------------------------
            # MODE B: FANTASY VISUALIZATION (Consultant - FLUX)
            # Cost: ~$0.003
            # ---------------------------------------------------------
            elif mode == 'flux':
                # Constructing the prompt from inputs
                prompt = body.get('prompt')
                # Fallback construction if raw prompt isn't sent
                if not prompt:
                    gender = body.get('gender', 'man')
                    skin = body.get('skin', 'medium')
                    outfit = body.get('outfit', 'stylish streetwear')
                    context = body.get('context', 'studio lighting')
                    prompt = f"A photorealistic full-body shot of an Indian {gender} with {skin} skin tone, wearing {outfit}. Background is {context}. Cinematic lighting, 4k, texture rich, fashion photography."

                output = client.run(
                    "black-forest-labs/flux-schnell",
                    input={
                        "prompt": prompt,
                        "aspect_ratio": "3:4",
                        "num_inference_steps": 4 # Speed optimized
                    }
                )
                output_url = output[0] # Flux returns a list

            # 3. Response
            self.wfile.write(json.dumps({"success": True, "image": output_url}).encode('utf-8'))

        except Exception as e:
            # Production Logging would go here
            self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
