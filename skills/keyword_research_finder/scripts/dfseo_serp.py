#!/usr/bin/env python3
"""
dfseo_serp.py
Fetch top 20 ranking URLs and PAA questions from DataForSEO SERP.
"""
import sys
import json
sys.path.insert(0, sys.path[0])
from dfseo_api_base import dfseo_post

if len(sys.argv) < 4:
    print("{}")
    sys.exit(0)

keyword = sys.argv[1]
location = sys.argv[2]
auth = sys.argv[3]

payload = [
    {
        "keyword": keyword,
        "location_name": location,
        "language_name": "English",
        "device": "desktop",
        "os": "windows",
        "include_search_features": True,
        "include_answer_box": True,
        "include_people_also_ask": True
    }
]

result = dfseo_post("serp/google/organic/live/advanced", payload, auth)
print(json.dumps(result))
