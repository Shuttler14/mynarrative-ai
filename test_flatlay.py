import urllib.request
import json
import time

def test_flatlay_extract():
    url = "http://localhost:8000/api/flatlay/extract"
    payload = {
        "action": "extract",
        "image_url": "https://images.unsplash.com/photo-1617137968427-85924c800a22?w=500&auto=format&fit=crop",
        "category": "upper_body",
        "product_id": "test_prod_888",
        "source_platform": "myntra"
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
    
    print("Testing flat-lay extraction via local gateway...")
    print(f"Original image: {payload['image_url']}")
    
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
    test_flatlay_extract()
