import urllib.request
import json
import time

def test_tryon_single():
    url = "http://localhost:8000/api/tryon/single"
    payload = {
        "mode": "vton",
        "user_image": "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=500&auto=format&fit=crop",
        "garment_image": "https://images.unsplash.com/photo-1583743814966-8936f5b7be1a?w=500&auto=format&fit=crop",
        "category": "upper_body",
        "description": "classic black t-shirt",
        "quality": "preview"
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )
    
    print("Testing single tryon on Replicate via local gateway...")
    print(f"User image: {payload['user_image']}")
    print(f"Garment image: {payload['garment_image']}")
    
    start_time = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode())
            print(f"Status Code: {resp.status}")
            print(json.dumps(data, indent=2))
            elapsed = time.time() - start_time
            print(f"Completed in {elapsed:.2f} seconds.")
    except Exception as e:
        print(f"Failed: {e}")
        if hasattr(e, 'read'):
            print(e.read().decode())

if __name__ == "__main__":
    test_tryon_single()
