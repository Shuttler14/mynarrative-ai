import requests
try:
    print("Sending request...")
    res = requests.get("https://mynarrative-ai.vercel.app/api/stylist_pipeline", timeout=5)
    print("Status:", res.status_code)
    try:
        print("JSON:", res.json())
    except:
        print("Text:", res.text)
except Exception as e:
    print("Error:", e)
