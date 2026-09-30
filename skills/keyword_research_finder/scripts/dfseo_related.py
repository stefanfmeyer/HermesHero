#!/usr/bin/env python3
"""
dfseo_related.py
Fetch related keywords from DataForSEO.
"""
import sys
sys.path.insert(0, sys.path[0])
from dfseo_api_base import dfseo_post

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
        "language_name": "English"
    }
]

result = dfseo_post("keywords_data/google/related_results/live", payload, auth)

related = []
if 'error' not in result:
    tasks = result.get('tasks', [])
    if tasks:
        items = tasks[0].get('result', [{}])[0].get('items', [])
        for item in items[:40]:
            kw = item.get('keyword', '')
            if kw:
                related.append(kw)

print('\n'.join(related))
