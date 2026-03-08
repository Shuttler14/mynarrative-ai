import requests

url = "https://mynarrative-ai.vercel.app/api/stylist_pipeline"

# Test OPTIONS (CORS preflight)
print("Testing OPTIONS request...")
response = requests.options(url, headers={
    "Origin": "https://jjdk0v-0c.myshopify.com",
    "Access-Control-Request-Method": "POST",
    "Access-Control-Request-Headers": "Content-Type"
})
print("OPTIONS Status Code:", response.status_code)
print("OPTIONS Headers:")
for key, value in response.headers.items():
    if key.lower().startswith("access-control"):
        print(f"  {key}: {value}")

print("\n-------------------\n")

# Test POST
print("Testing POST request...")
response = requests.post(url, json={
    "action": "get_vibes"
}, headers={
    "Origin": "https://jjdk0v-0c.myshopify.com",
    "Content-Type": "application/json"
})
print("POST Status Code:", response.status_code)
print("POST Response JSON:", response.json() if response.status_code == 200 else response.text)
print("POST Headers:")
for key, value in response.headers.items():
    if key.lower().startswith("access-control"):
        print(f"  {key}: {value}")
