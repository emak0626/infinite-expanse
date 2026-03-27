import requests
from requests.auth import HTTPBasicAuth
import json

def test_local_trade_api():
    url = "http://localhost:8000/api/analysis/local_trade/7203"
    auth = HTTPBasicAuth("admin", "infinity")
    
    print(f"Testing {url}...")
    try:
        response = requests.get(url, auth=auth)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print("Response Received:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_local_trade_api()
