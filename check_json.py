import urllib.request
import base64

def _raise_err(x):
    raise ValueError(f"Invalid constant {x}")

auth_str = base64.b64encode(b'admin:infinity').decode('utf-8')
headers = {'Authorization': 'Basic ' + auth_str}

try:
    print("Fetching last scan results...")
    req_scanner = urllib.request.Request('http://localhost:8000/api/market_scanner?type=last_scan', headers=headers)
    response = urllib.request.urlopen(req_scanner)
    text = response.read().decode('utf-8')
    print("Raw text snippet:")
    print(text[:300]) # Print first 300 chars
    
    if 'NaN' in text:
        print("WARNING: 'NaN' found in JSON response! This will break JS JSON.parse().")
        idx = text.find('NaN')
        print(f"Context around NaN: {text[max(0, idx-20):idx+20]}")
    else:
        print("No NaN found. Parsing test:")
        import json
        json.loads(text, parse_constant=lambda x: _raise_err(x))
        print("Successfully parsed strictly.")
except Exception as e:
    print(f"Error: {e}")
