import urllib.request
import json
import time

def test_recommendation():
    url = "http://localhost:8000/api/recommend"
    payload = {
        "action": "recommend_outfit",
        "user_id": "test_user_777",
        "gender": "men",
        "event": "wedding_sangeet",
        "location": "Mumbai",
        "budget_min": 2000,
        "budget_max": 8000,
        "body_profile": {
            "skin_tone": "Honey",
            "body_type": "average",
            "height_cm": 175
        },
        "style_preferences": ["classic", "indo-western"],
        "auto_tryon": False
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
    
    print("Testing outfit recommendation engine via local gateway...")
    print(f"Gender: {payload['gender']} | Event: {payload['event']} | Location: {payload['location']}")
    
    start_time = time.time()
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
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
    test_recommendation()
