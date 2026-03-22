import urllib.request
import json
import base64
import time

auth_str = base64.b64encode(b'admin:infinity').decode('utf-8')
headers = {'Authorization': 'Basic ' + auth_str}

try:
    print("Triggering technical scan for growth...")
    req_trigger = urllib.request.Request('http://localhost:8000/api/admin/scan-technical?strategy=growth', method='POST', headers=headers)
    urllib.request.urlopen(req_trigger)
    
    print("Waiting 3 seconds for the scan to save CSV...")
    time.sleep(3)
    
    print("Fetching last scan results...")
    req_scanner = urllib.request.Request('http://localhost:8000/api/market_scanner?type=last_scan', headers=headers)
    response = urllib.request.urlopen(req_scanner)
    results = json.loads(response.read().decode('utf-8'))
    print(f'Total results: {len(results)}')
    if results:
        head = results[0]
        print(f"Sample: {head.get('symbol')} {head.get('symbolname')} AI={head.get('ai_score')} Source={head.get('ソース')}")
except Exception as e:
    print(f"Error: {e}")
