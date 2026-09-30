#!/usr/bin/env python3
"""
dfseo_keyword_ideas.py
Fetch keyword ideas using DataForSEO Labs endpoint.
Uses: dataforseo_labs/google/keyword_ideas/live
Returns related keywords (may not have volume data).
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
    'united states': 2840,
    'us': 2840,
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
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}

# Use keyword_ideas endpoint
result = api_post("dataforseo_labs/google/keyword_ideas/live", [{
    "keywords": [keyword],
    "location_code": loc_code,
    "language_code": "en",
    "limit": 50
}])

ideas = []
if 'error' not in result:
    tasks = result.get('tasks', [])
    if tasks and tasks[0].get('status_code') == 20000:
        res = tasks[0].get('result', [])
        if res:
            items = res[0].get('items', [])
            for item in items:
                kw = item.get('keyword', '')
                if kw and kw.lower() != keyword.lower():
                    ideas.append(kw)

# Output keyword ideas
print('\n'.join(ideas[:50]))