#!/usr/bin/env python3
"""
Manual keyword research runner for choosemycar.com/bad-credit-car-finance
Uses DataForSEO APIs directly.
"""
import json
import urllib.request
import urllib.error
import sys
import os

BASE_URL = "https://api.dataforseo.com/v3"
CREDS_FILE = os.path.expanduser("~/.openclaw/credentials.json")

# Load credentials
with open(CREDS_FILE) as f:
    creds = json.load(f)["dataforseo"]

login = creds["login"]
password = creds["password"]
import base64
AUTH = "Basic " + base64.b64encode(f"{login}:{password}".encode()).decode()

print(f"Login: {login}")
print(f"Auth prefix: {AUTH[:20]}...")

def post(endpoint, payload):
    url = f"{BASE_URL}/{endpoint}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={
        "Authorization": AUTH,
        "Content-Type": "application/json"
    }, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.reason}", "body": e.read().decode()}
    except Exception as e:
        return {"error": str(e)}

# Step 1: Keyword variations
print("\n=== KEYWORD VARIATIONS ===")
kw_vars = post("keywords_data/google/keyword_variations/live", [{
    "keyword": "bad credit car finance",
    "location_name": "United Kingdom",
    "language_name": "English",
    "include_metadata": True
}])
print(json.dumps(kw_vars)[:3000])

# Step 2: Keyword suggestions (core)
print("\n=== KEYWORD SUGGESTIONS (CORE) ===")
kw_suggest = post("keywords_data/google/keyword_suggestions/live", [{
    "keyword": "bad credit car finance",
    "location_name": "United Kingdom",
    "language_name": "English"
}])
print(json.dumps(kw_suggest)[:3000])

# Step 3: Related keywords
print("\n=== RELATED KEYWORDS ===")
related = post("keywords_data/google/related_results/live", [{
    "keyword": "bad credit car finance",
    "location_name": "United Kingdom",
    "language_name": "English"
}])
print(json.dumps(related)[:3000])

# Step 4: SERP
print("\n=== SERP RESULTS ===")
serp = post("serp/google/organic/live/advanced", [{
    "keyword": "bad credit car finance",
    "location_name": "United Kingdom",
    "language_name": "English",
    "device": "desktop",
    "os": "windows",
    "include_search_features": True,
    "include_answer_box": True,
    "include_people_also_ask": True
}])
print(json.dumps(serp)[:5000])

print("\n=== DONE ===")
