#!/usr/bin/env python3
"""
dfseo_autocomplete.py
Fetch keyword suggestions from Google Autocomplete via DataForSEO.
Uses: serp/google/autocomplete/live/advanced
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
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}

# Use autocomplete endpoint
result = api_post("serp/google/autocomplete/live/advanced", [{
    "keyword": keyword,
    "location_code": loc_code,
    "language_code": "en"
}])

suggestions = []
if 'error' not in result:
    tasks = result.get('tasks', [])
    if tasks and tasks[0].get('status_code') == 20000:
        # Result structure: result[0].items[]
        res = tasks[0].get('result', [])
        if res:
            items = res[0].get('items', []) if isinstance(res[0], dict) else res
            for item in items:
                if isinstance(item, dict):
                    suggestion = item.get('suggestion', item.get('keyword', ''))
                else:
                    suggestion = str(item)
                if suggestion and suggestion.lower() != keyword.lower():
                    suggestions.append(suggestion)

# Output suggestions
print('\n'.join(suggestions[:50]))