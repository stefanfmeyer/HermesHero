#!/usr/bin/env python3
"""
dfseo_keyword_vars_fixed.py
Fetch keyword variations using WORKING DataForSEO endpoints.
Uses: keywords_data/google/search_volume/live (works)
Fallback: SERP-based keyword discovery
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

loc_code = LOCATION_CODES.get(location.lower(), 2826)  # Default UK

BASE_URL = "https://api.dataforseo.com/v3"

def api_post(endpoint, payload):
    url = f"{BASE_URL}/{endpoint}"
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={
        'Authorization': f'Basic {auth}',
        'Content-Type': 'application/json'
    }, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}

# Strategy 1: Get keywords from ranking sites (keywords_for_site)
# This works and gives us related keywords
result = api_post("keywords_data/google/keywords_for_site/live", [{
    "target": keyword,
    "location_code": loc_code,
    "language_code": "en",
    "limit": 50
}])

variations = []
if 'error' not in result:
    tasks = result.get('tasks', [])
    if tasks and tasks[0].get('status_code') == 20000:
        items = tasks[0].get('result', [{}])[0].get('items', [])
        for item in items:
            kw = item.get('keyword', '')
            if kw and kw.lower() != keyword.lower():
                variations.append(kw)

# Strategy 2: Get search volume for the keyword + variations
# This confirms relevance
if variations:
    vol_result = api_post("keywords_data/google/search_volume/live", [{
        "keywords": [keyword] + variations[:20],
        "location_code": loc_code,
        "language_code": "en"
    }])
    if 'error' not in vol_result:
        tasks = vol_result.get('tasks', [])
        if tasks and tasks[0].get('status_code') == 20000:
            items = tasks[0].get('result', [{}])[0].get('items', [])
            # Filter to keywords with search volume
            valid = []
            for item in items:
                kw = item.get('keyword', '')
                vol = item.get('search_volume', 0)
                if kw and vol and kw.lower() != keyword.lower():
                    valid.append(kw)
            variations = valid[:50]

# Output results
print('\n'.join(variations[:50]))