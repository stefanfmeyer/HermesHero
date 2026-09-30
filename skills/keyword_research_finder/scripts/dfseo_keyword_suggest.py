#!/usr/bin/env python3
"""
dfseo_keyword_suggest.py
Fetch keyword suggestions with modifiers from DataForSEO.
"""
import sys
import json
sys.path.insert(0, sys.path[0])
from dfseo_api_base import dfseo_post

if len(sys.argv) < 5:
    print("")
    sys.exit(0)

keyword = sys.argv[1]
location = sys.argv[2]
modifiers = sys.argv[3].split(',')
auth = sys.argv[4]

all_suggestions = []

# Core keyword suggestions
payload = [
    {
        "keyword": keyword,
        "location_name": location,
        "language_name": "English"
    }
]

result = dfseo_post("keywords_data/google/keyword_suggestions/live", payload, auth)

if 'error' not in result:
    tasks = result.get('tasks', [])
    if tasks:
        for task in tasks:
            items = task.get('result', [{}])[0].get('items', [])
            for item in items[:30]:
                kw = item.get('keyword', '')
                if kw:
                    all_suggestions.append(kw)

# Now combine core keyword with each modifier
for mod in modifiers[:10]:
    mod = mod.strip()
    if not mod:
        continue
    
    modified_kw = f"{keyword} {mod}"
    payload = [[{"keyword": modified_kw, "location_name": location, "language_name": "English"}]]
    result = dfseo_post("keywords_data/google/keyword_suggestions/live", payload, auth)
    
    if 'error' not in result:
        tasks = result.get('tasks', [])
        if tasks:
            for task in tasks:
                items = task.get('result', [{}])[0].get('items', [])
                for item in items[:10]:
                    kw = item.get('keyword', '')
                    if kw and kw.lower() not in [s.lower() for s in all_suggestions]:
                        all_suggestions.append(kw)

print('\n'.join(all_suggestions[:150]))
