#!/usr/bin/env python3
"""
dfseo_keyword_suggest_fixed.py
Fetch keyword suggestions using SERP data (works).
Extracts from "related searches" and "people also search for".
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
modifiers = sys.argv[3] if len(sys.argv) > 3 else ""
auth = sys.argv[4]

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
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}

# Use SERP to find related keywords
result = api_post("serp/google/organic/live/advanced", [{
    "keyword": keyword,
    "location_code": loc_code,
    "language_code": "en",
    "include_related_results": True,
}])

suggestions = []
if 'error' not in result:
    tasks = result.get('tasks', [])
    if tasks and tasks[0].get('status_code') == 20000:
        items = tasks[0].get('result', [{}])[0].get('items', [])
        for item in items:
            # Extract from "related searches"
            related = item.get('related_search', [])
            for r in related[:10]:
                kw = r.get('keyword', r.get('query', ''))
                if kw and kw.lower() != keyword.lower():
                    suggestions.append(kw)
            # Extract from "people also search"
            pasp = item.get('people_also_search', [])
            for p in pasp[:10]:
                kw = p.get('keyword', p.get('query', ''))
                if kw and kw.lower() != keyword.lower():
                    suggestions.append(kw)

# Dedupe
suggestions = list(dict.fromkeys(suggestions))[:50]
print('\n'.join(suggestions))