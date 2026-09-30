#!/usr/bin/env python3
"""
dfseo_keyword_vars.py
Fetch keyword variations from DataForSEO.
"""
import sys
import json
sys.path.insert(0, sys.path[0])
from dfseo_api_base import dfseo_post, track_spend

if len(sys.argv) < 4:
    print("")
    sys.exit(0)

keyword = sys.argv[1]
location = sys.argv[2]
auth = sys.argv[3]

payload = [
    {
        "keyword": keyword,
        "location_name": location,
        "language_name": "English",
        "include_metadata": True
    }
]

result = dfseo_post("keywords_data/google/keyword_variations/live", payload, auth)

if 'error' in result:
    print("")
else:
    tasks = result.get('tasks', [])
    if tasks:
        items = tasks[0].get('result', [{}])[0].get('items', [])
        variations = []
        for item in items[:50]:
            kw = item.get('keyword', '')
            if kw and kw.lower() != keyword.lower():
                variations.append(kw)
        print('\n'.join(variations))
    else:
        print("")
