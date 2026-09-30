#!/usr/bin/env python3
"""
dfseo_api_base.py
Shared DataForSEO API utilities.
"""
import json
import urllib.request
import urllib.error

BASE_URL = "https://api.dataforseo.com/v3"

def dfseo_post(endpoint, payload, auth_base64, max_cost=10.0):
    """Make a DataForSEO POST request. Returns parsed JSON or error string."""
    url = f"{BASE_URL}/{endpoint}"
    data = json.dumps(payload).encode('utf-8')
    
    req = urllib.request.Request(url,
        data=data,
        headers={
            'Authorization': f'Basic {auth_base64}',
            'Content-Type': 'application/json'
        },
        method='POST'
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            cost = result.get('cost', 0)
            if cost > max_cost:
                return {"error": f"Cost {cost} exceeds budget {max_cost}"}
            return result
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}

def dfseo_get(endpoint, auth_base64):
    """Make a DataForSEO GET request. Returns parsed JSON or error string."""
    url = f"{BASE_URL}/{endpoint}"
    
    req = urllib.request.Request(url,
        headers={'Authorization': f'Basic {auth_base64}'},
        method='GET'
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        return {"error": str(e)}

def track_spend(cost, tracker_path, max_daily=10.0):
    """Update daily spend tracker."""
    import os
    from datetime import date
    
    today = date.today().isoformat()
    data = {}
    if os.path.exists(tracker_path):
        try:
            data = json.load(open(tracker_path))
        except:
            pass
    
    current = float(data.get(today, 0))
    new_total = round(current + cost, 6)
    data[today] = new_total
    
    with open(tracker_path, 'w') as f:
        json.dump(data, f)
    
    if new_total > max_daily:
        return False  # exceeded
    return True

def location_to_code(location_name, auth_base64):
    """Convert location name to DataForSEO location code."""
    result = dfseo_get("serp/google/locations", auth_base64)
    if 'error' in result:
        return None
    try:
        for loc in result.get('results', []):
            if location_name.lower() in loc.get('name', '').lower():
                return loc.get('location_code')
    except:
        pass
    # Fallback common codes
    fallback = {
        'united kingdom': 2840, 'uk': 2840, 'gb': 2840,
        'united states': 2840, 'us': 2840, 'usa': 2840,
        'germany': 2744, 'de': 2744,
        'france': 2754, 'fr': 2754,
        'australia': 2474, 'au': 2474,
        'canada': 2476, 'ca': 2476,
    }
    return fallback.get(location_name.lower())
