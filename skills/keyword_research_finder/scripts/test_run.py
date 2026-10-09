#!/usr/bin/env python3
"""
Keyword Research Finder
Uses SERP API (working) + intelligent keyword extraction from titles/snippets
"""
import sys
import json
import argparse
import urllib.request
import base64
import re

BASE_URL = "https://api.dataforseo.com/v3"

def get_auth():
    with open('~/.openclaw/credentials.json') as f:
        creds = json.load(f)
    dfseo = creds.get('dataforseo', {})
    login = dfseo.get('login', 'YOUR_DATAFORSEO_LOGIN')
    password = dfseo.get('password', '')
    return base64.b64encode(f"{login}:{password}".encode()).decode()

def api_post(endpoint, payload):
    url = f"{BASE_URL}/{endpoint}"
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={
        'Authorization': f'Basic {get_auth()}',
        'Content-Type': 'application/json'
    }, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            cost = result.get('cost', 0)
            if cost > 0:
                print(f"    API cost: ${cost:.4f}")
            return result
    except Exception as e:
        print(f"    API Error: {e}")
        return {}

def clean_kw(kw):
    """Clean keyword string."""
    kw = re.sub(r'<[^>]+>', '', kw)
    kw = re.sub(r'\s+', ' ', kw)
    kw = kw.strip('.,;:!?()[]{}"\'-')
    return kw.strip().lower()

def extract_keywords_from_text(text):
    """Extract clean keywords from a text string."""
    keywords = []
    
    # Split by common delimiters
    parts = re.split(r'[,;|&]\s*', text)
    
    for part in parts:
        # Clean it
        kw = clean_kw(part)
        # Remove very short or very long
        if len(kw) > 5 and len(kw) < 80:
            # Remove if starts with verb (how, what, why, etc - FAQ territory)
            skip_starts = ['how to', 'how do', 'how does', 'how can', 'what is', 'what are', 
                          'why do', 'why does', 'when to', 'when should', 'where to find',
                          'who should', 'can i', 'should i', 'is it', 'are there']
            if any(kw.startswith(s) for s in skip_starts):
                continue
            keywords.append(kw)
    
    return keywords

def score_kw(kw, primary, primary_words):
    """Score keyword relevance 0-25."""
    score = 0
    kw_lower = kw.lower()
    prim_lower = primary.lower()
    
    # Exact match = highest
    if prim_lower == kw_lower:
        return 25
    if prim_lower in kw_lower:
        score += 15
    if any(p in kw_lower.split()[:2] for p in primary_words if len(p) > 3):
        score += 8
    
    # Good modifiers boost score
    good = ['tips', 'guide', 'best', 'top', 'checklist', 'strategies', 'mistakes', 
            'beginners', 'beginner', '2025', '2026', 'steps', 'small business', 
            'website', 'google', 'search', 'optimization', 'ranking', 'tools']
    for word in good:
        if word in kw_lower:
            score += 3
    
    # Questions get penalized (they go to FAQ)
    questions = ['how to', 'how do', 'how does', 'how can', 'what is', 'what are', 
                 'why do', 'why does', 'when to', 'when should', 'where to find',
                 'who should', 'can i', 'should i', 'is it', 'are there']
    if any(kw_lower.startswith(q) for q in questions):
        score -= 8
    
    return max(score, 0)

def main():
    parser = argparse.ArgumentParser(description='Keyword Research Finder')
    parser.add_argument('--primary', required=True)
    parser.add_argument('--country', default='United Kingdom')
    parser.add_argument('--page-type', default='blog')
    parser.add_argument('--output', help='Output file prefix')
    args = parser.parse_args()
    
    topic = args.primary
    country = args.country
    primary_words = topic.split()
    
    print(f"\n{'='*60}")
    print(f"  KEYWORD RESEARCH FINDER")
    print(f"{'='*60}")
    print(f"\n  Primary: {topic}")
    print(f"  Country: {country}")
    print(f"  Type: {args.page_type}")
    
    all_keywords = []
    competitor_urls = []
    
    # Step 1: SERP - get titles and snippets
    print(f"\n[1] SERP Analysis...")
    serp_result = api_post("serp/google/organic/live/advanced", [{
        "keyword": topic,
        "location_name": country,
        "language_name": "English",
        "max_crawl_pages": 10
    }])
    
    if 'tasks' in serp_result:
        for t in serp_result.get('tasks', []):
            for r in t.get('result', []):
                for item in r.get('items', [])[:20]:
                    # Get URL
                    url = item.get('url', '')
                    if url:
                        competitor_urls.append(url)
                    
                    # Extract from title
                    title = item.get('title', '')
                    if title:
                        kws = extract_keywords_from_text(title)
                        all_keywords.extend(kws)
                    
                    # Extract from snippet
                    snippet = item.get('snippet', '')
                    if snippet:
                        kws = extract_keywords_from_text(snippet)
                        all_keywords.extend(kws)
    
    print(f"    Found {len(competitor_urls)} competitor URLs")
    print(f"    Extracted {len(all_keywords)} keywords from titles/snippets")
    
    # Dedupe
    all_keywords = list(set(all_keywords))
    print(f"    After dedup: {len(all_keywords)}")
    
    # Step 2: Score and categorize
    print(f"\n[2] Scoring keywords...")
    scored = [(score_kw(k, topic, primary_words), k) for k in all_keywords]
    scored.sort(reverse=True)
    
    # Get top keywords avoiding duplicates
    seen = set()
    primary_kws = []
    secondary_kws = []
    supporting_kws = []
    
    for score, kw in scored:
        if kw in seen:
            continue
        seen.add(kw)
        
        if score >= 10 and len(primary_kws) < 10:
            primary_kws.append(kw)
        elif score >= 5 and len(secondary_kws) < 12:
            secondary_kws.append(kw)
        elif score >= 2 and len(supporting_kws) < 15:
            supporting_kws.append(kw)
    
    # Theme detection
    themes = []
    kw_text = ' '.join(all_keywords).lower()
    theme_map = {
        'beginners': ['beginner', 'beginners'],
        'small_business': ['small business'],
        'checklist': ['checklist'],
        'mistakes': ['mistakes', 'errors'],
        'strategies': ['strategy', 'strategies'],
        'local_seo': ['local seo', 'local'],
        'technical': ['technical'],
        'on_page': ['on page', 'on-page'],
        'ecommerce': ['ecommerce', 'e-commerce'],
        'wordpress': ['wordpress'],
        'ai_seo': ['ai seo', ' artificial'],
        'mobile': ['mobile'],
        'ranking': ['ranking', 'rank'],
        'content': ['content'],
        'links': ['backlink', 'backlinks', 'link building'],
        'tools': ['tools', 'software'],
    }
    for theme, patterns in theme_map.items():
        if any(p in kw_text for p in patterns):
            themes.append(theme.replace('_', ' '))
    
    # Results
    print(f"\n{'='*60}")
    print(f"  RESULTS")
    print(f"{'='*60}")
    
    print(f"\n[PRIMARY KEYWORDS]")
    for k in primary_kws:
        print(f"  • {k}")
    
    print(f"\n[SECONDARY KEYWORDS]")
    for k in secondary_kws:
        print(f"  • {k}")
    
    print(f"\n[SUPPORTING KEYWORDS]")
    for k in supporting_kws[:12]:
        print(f"  • {k}")
    
    print(f"\n[KEYWORD THEMES]")
    print(f"  {', '.join(themes) if themes else 'None'}")
    
    print(f"\n[COMPETITOR URLs]")
    for u in competitor_urls[:5]:
        print(f"  • {u[:60]}...")
    
    # Build output
    output = {
        "domain": "former-employer.co.uk",
        "content_type": args.page_type,
        "primary_keyword": topic,
        "secondary_keywords": primary_kws,
        "supporting_keywords": secondary_kws + supporting_kws[:8],
        "question_keywords": [],  # Removed - handled by FAQ skill
        "keyword_themes": themes,
        "keywords_to_avoid": [],
        "competitor_urls": competitor_urls[:5],
        "keyword_count": {
            "total": len(all_keywords),
            "primary": len(primary_kws),
            "secondary": len(secondary_kws),
            "supporting": len(supporting_kws)
        }
    }
    
    # Save
    if args.output:
        with open(f"{args.output}.json", 'w') as f:
            json.dump(output, f, indent=2)
        
        md = f"""# Keyword Research: {topic}

Domain: former-employer.co.uk
Content type: {args.page_type}
Date: 2026-04-08

## Primary Keyword
{topic}

## Secondary Keywords ({len(primary_kws)})
{chr(10).join(['- ' + k for k in primary_kws])}

## Supporting Keywords ({len(supporting_kws[:12])})
{chr(10).join(['- ' + k for k in supporting_kws[:12]])}

## Keyword Themes
{', '.join(themes) if themes else 'None'}

## Competitor URLs
{chr(10).join(['- ' + u for u in competitor_urls[:5]])}
"""
        with open(f"{args.output}.md", 'w') as f:
            f.write(md)
        
        print(f"\n[Saved] {args.output}.json")
        print(f"[Saved] {args.output}.md")
    
    return output

if __name__ == '__main__':
    main()