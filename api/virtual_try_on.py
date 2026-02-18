from http.server import BaseHTTPRequestHandler
import json
import os
import replicate

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        # Handle CORS preflight request
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Max-Age', '86400')
        self.end_headers()

    def do_POST(self):
        try:
            # 1. Auth Check
            token = os.environ.get("REPLICATE_API_TOKEN") or os.getenv("REPLICATE_API_TOKEN")
            if not token:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": False, 
                    "error": "Server Config Error: Missing REPLICATE_API_TOKEN environment variable"
                }).encode('utf-8'))
                return
            
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
                
                print("👕 Fetching latest IDM-VTON version...")
                
                # --- AUTO-FETCH LOGIC (FIX FOR MODEL VERSION ERROR) ---
                try:
                    model = client.models.get("cuuupid/idm-vton")
                    latest_version = model.latest_version
                    version_id = latest_version.id
                    print(f"✅ Using IDM-VTON Version: {version_id}")
                except Exception as e:
                    # Fallback to known working hash if auto-fetch fails
                    print(f"⚠️ Auto-fetch failed, using fallback. Error: {e}")
                    version_id = "c871bb9b046607b680449ecbae55fd8c6d945e0a1948644bf2361b3d021d3ff4"

                # Run Prediction
                output = client.run(
                    f"cuuupid/idm-vton:{version_id}",
                    input={
                        "human_img": human_img,
                        "garm_img": garm_img,
                        "garment_des": body.get('description', "clothing item"),
                        "category": category,
                        "crop": False,
                        "seed": 42,
                        "steps": 30,
                        "force_dc": False,
                        "mask_only": False
                    }
                )
                
                # IDM-VTON returns a FileOutput object
                output_url = str(output) if hasattr(output, '__str__') else output

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

                # 1. GENERATE BASE IMAGE WITH FLUX
                output = client.run(
                    "black-forest-labs/flux-schnell",
                    input={
                        "prompt": prompt,
                        "aspect_ratio": "3:4",
                        "num_inference_steps": 4 # Speed optimized
                    }
                )
                generated_image_url = output[0] # Flux returns a list

                # 2. OPTIONAL: FACE SWAP
                user_face = body.get('user_image')
                if user_face:
                    # Run Face Swap (chained prediction)
                    # Using lucataco/faceswap (based on InsightFace)
                    swap_output = client.run(
                        "lucataco/faceswap:9a4298548422074c3f57258c5d544497314ae4112df80d116f0d2109bd068e9c",
                        input={
                            "target_image": generated_image_url,
                            "swap_image": user_face
                        }
                    )
                    output_url = str(swap_output)
                else:
                    output_url = generated_image_url

            # 3. Success Response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "image": output_url}).encode('utf-8'))

        except replicate.exceptions.ReplicateError as e:
            # Replicate-specific error handling
            error_msg = str(e)
            status_code = 500
            
            # Check for specific error types
            if hasattr(e, 'status'):
                if e.status == 402:
                    error_msg = '💳 REPLICATE CREDITS EXHAUSTED\n\nPlease add credits at:\nhttps://replicate.com/account/billing\n\nAfter purchasing, wait 2-3 minutes before trying again.'
                elif e.status == 422:
                    error_msg = '⚠️ MODEL VERSION ERROR\n\nThe AI model version is invalid or you don\'t have permission.\nPlease contact support.'
            
            self.send_response(status_code)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"success": False, "error": error_msg}).encode('utf-8'))
            
        except Exception as e:
            # Generic error handling
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))