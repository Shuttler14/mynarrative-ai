import urllib.request
import json
import sys

def test_search():
    url = "http://localhost:8000/api/marketplace/search"
    payload = {
        "action": "search_products",
        "query": "kurta",
        "platform": "amazon",
        "limit": 2
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
    
    print("Testing Amazon search scraping via local gateway...")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            print(f"Status Code: {resp.status}")
            print(json.dumps(data, indent=2))
    except Exception as e:
        print(f"Failed: {e}")
        if hasattr(e, 'read'):
            print(e.read().decode())

if __name__ == "__main__":
    test_search()
