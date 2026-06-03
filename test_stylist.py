import requests
import json

url = "https://mynarrative-ai.vercel.app/api/stylist_pipeline"
# url = "http://localhost:8000/api/stylist_pipeline"

payload = {
    "action": "full_pipeline",
    "user_id": "test_guest_123",
    "occasion": "date_night",
    "vibe_id": "main_character",
    "user_image": "mock_base64_string"
}

try:
    response = requests.post(url, json=payload, timeout=20)
    print("STATUS:", response.status_code)
    try:
        print("JSON:", json.dumps(response.json(), indent=2))
    except:
        print("TEXT:", response.text)
except Exception as e:
    print("ERROR:", e)
