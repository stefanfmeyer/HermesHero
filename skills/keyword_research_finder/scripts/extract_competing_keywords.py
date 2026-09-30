#!/usr/bin/env python3
"""
Extract keywords from competing URLs to avoid keyword cannibalisation.
Fetches each URL and extracts primary keywords/topics being targeted.
"""
import sys
import re
import json
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

def fetch_page(url):
    """Fetch page content with basic error handling."""
    try:
        req = Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; KeywordResearchBot/1.0)'
        })
        with urlopen(req, timeout=15) as resp:
            return resp.read().decode('utf-8', errors='ignore')
    except (URLError, HTTPError, Exception) as e:
        return ""

def extract_title(content):
    """Extract page title."""
    match = re.search(r'<title[^>]*>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
    if match:
        title = match.group(1).strip()
        # Remove common suffixes like " | Brand" or " - Brand"
        title = re.split(r'\s*[\|–-]\s*(?=[^|–-]*$)', title)[0].strip()
        return title
    return ""

def extract_h1(content):
    """Extract H1 heading."""
    match = re.search(r'<h1[^>]*>(.*?)</h1>', content, re.IGNORECASE | re.DOTALL)
    if match:
        return re.sub(r'<[^>]+>', '', match.group(1)).strip()
    return ""

def extract_meta_keywords(content):
    """Extract meta keywords tag."""
    match = re.search(r'<meta[^>]+name=["\']keywords["\'][^>]+content=["\']([^"\']+)["\']', content, re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']keywords["\']', content, re.IGNORECASE)
    if match:
        return match.group(1)
    return ""

def extract_meta_description(content):
    """Extract meta description."""
    match = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']', content, re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']', content, re.IGNORECASE)
    if match:
        return match.group(1)
    return ""

def extract_slug_keywords(url):
    """Extract keywords from URL slug."""
    from urllib.parse import urlparse
    path = urlparse(url).path
    slug = path.strip('/').replace('-', ' ').replace('/', ' ')
    return slug

def extract_keywords_from_url(url):
    """Extract all potential keywords from a URL."""
    content = fetch_page(url)
    
    keywords = []
    
    # Extract from URL slug
    slug_kw = extract_slug_keywords(url)
    if slug_kw:
        keywords.append(slug_kw)
    
    if content:
        # Title
        title = extract_title(content)
        if title:
            keywords.append(title)
        
        # H1
        h1 = extract_h1(content)
        if h1:
            keywords.append(h1)
        
        # Meta keywords
        meta_kw = extract_meta_keywords(content)
        if meta_kw:
            keywords.extend([k.strip() for k in meta_kw.split(',')])
        
        # Meta description (extract key phrases)
        meta_desc = extract_meta_description(content)
        if meta_desc:
            keywords.append(meta_desc)
    
    # Clean and normalize
    cleaned = []
    for kw in keywords:
        kw = kw.lower().strip()
        kw = re.sub(r'[^\w\s]', ' ', kw)
        kw = ' '.join(kw.split())
        if kw and len(kw) > 2:
            cleaned.append(kw)
    
    return list(set(cleaned))

def main(urls_file):
    """Main entry point."""
    with open(urls_file, 'r') as f:
        urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    all_keywords = []
    
    for url in urls:
        print(f"Analysing: {url}")
        kws = extract_keywords_from_url(url)
        all_keywords.extend(kws)
        print(f"  Found {len(kws)} keyword signals")
    
    # Deduplicate
    unique = list(set(all_keywords))
    
    # Output as JSON
    print("\n=== COMPETING KEYWORDS ===")
    print(json.dumps(unique, indent=2))
    
    return unique

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: extract_competing_keywords.py <urls_file>")
        sys.exit(1)
    
    main(sys.argv[1])