#!/usr/bin/env python3
"""
dfseo_related_fixed.py
Fetch related keywords using SERP data.
Extracts from ranking URLs' keywords.
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
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}

# Get keywords from sites ranking for this keyword
# First get SERP results
serp_result = api_post("serp/google/organic/live/advanced", [{
    "keyword": keyword,
    "location_code": loc_code,
    "language_code": "en",
}])

related = []
if 'error' not in serp_result:
    tasks = serp_result.get('tasks', [])
    if tasks and tasks[0].get('status_code') == 20000:
        items = tasks[0].get('result', [{}])[0].get('items', [])
        urls = [item.get('url') for item in items[:10] if item.get('url')]
        
        # Now get keywords for each ranking site
        for url in urls[:5]:
            site_result = api_post("keywords_data/google/keywords_for_site/live", [{
                "target": url,
                "location_code": loc_code,
                "language_code": "en",
                "limit": 20
            }])
            if 'error' not in site_result:
                site_tasks = site_result.get('tasks', [])
                if site_tasks and site_tasks[0].get('status_code') == 20000:
                    site_items = site_tasks[0].get('result', [{}])[0].get('items', [])
                    for item in site_items:
                        kw = item.get('keyword', '')
                        if kw and kw.lower() != keyword.lower():
                            related.append(kw)

# Dedupe
related = list(dict.fromkeys(related))[:50]
print('\n'.join(related))