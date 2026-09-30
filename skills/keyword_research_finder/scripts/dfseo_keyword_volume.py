#!/usr/bin/env python3
"""
dfseo_keyword_volume.py
Fetch keyword search volume using CORRECT DataForSEO endpoint:
keywords_data/google_ads/search_volume/live
"""
import sys
import json
import urllib.request
import urllib.error

if len(sys.argv) < 4:
    print("")
    sys.exit(0)

keyword = sys.argv[1]
location = sys.argv[2]
auth = sys.argv[3]

# Location name to code mapping
LOCATION_CODES = {
    'united kingdom': 2826,
    'uk': 2826,
    'gb': 2826,
    'great britain': 2826,
    'united states': 2840,
    'us': 2840,
    'usa': 2840,
}

loc_code = LOCATION_CODES.get(location.lower(), 2826)

BASE_URL = "https://api.dataforseo.com/v3"

def api_post(endpoint, payload):
    url = f"{BASE_URL}/{endpoint}"
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={
        'Authorization': f'Basic {auth}',
        'Content-Type': 'application/json'
    }, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}

# Use the CORRECT endpoint: google_ads/search_volume/live
result = api_post("keywords_data/google_ads/search_volume/live", [{
    "keywords": [keyword],
    "location_code": loc_code,
    "language_code": "en"
}])

keywords_with_volume = []
if 'error' not in result:
    tasks = result.get('tasks', [])
    if tasks and tasks[0].get('status_code') == 20000:
        # Result is a list of keyword results directly
        results = tasks[0].get('result', [])
        for kw_result in results:
            kw = kw_result.get('keyword', '')
            vol = kw_result.get('search_volume') or 0
            cpc = kw_result.get('cpc') or 0
            comp = kw_result.get('competition', '') or ''
            # Include even if volume is null (for autocomplete suggestions)
            if kw:
                keywords_with_volume.append(f"{kw}|{vol}|{cpc}|{comp}")

# Output: keyword|volume|cpc|competition
print('\n'.join(keywords_with_volume))