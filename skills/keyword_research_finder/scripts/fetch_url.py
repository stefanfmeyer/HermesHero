#!/usr/bin/env python3
"""
fetch_url.py
Fetches a URL and extracts clean text using Python's urllib.
More reliable than curl in restricted environments.
"""
import sys
import re
import urllib.request

if len(sys.argv) < 2:
    print("", file=sys.stderr)
    sys.exit(1)

url = sys.argv[1]

req = urllib.request.Request(url,
    headers={
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-GB,en;q=0.9',
    }
)

try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode('utf-8', errors='ignore')
        # Strip tags
        text = re.sub(r'<[^>]+>', ' ', html)
        # Remove script/style blocks
        text = re.sub(r'(?is)<(script|style)[^>]*>.*?</\1>', '', text)
        # Clean whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        print(text[:4000])
except Exception as e:
    print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)
