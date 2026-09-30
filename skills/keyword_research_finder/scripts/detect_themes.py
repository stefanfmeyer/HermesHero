#!/usr/bin/env python3
"""
detect_themes.py
Analyse competitor ranking pages to detect keyword themes.
Takes a list of URLs (one per line) and analyses their content
to find recurring topic patterns.
"""
import sys
import json
import urllib.request
import urllib.error
import re
from collections import Counter

STOPWORDS = {
    'the','and','for','are','but','not','you','all','can','had','her','was','one','our',
    'out','day','get','has','him','his','how','its','may','new','now','old','see','two',
    'way','who','did','own','say','she','too','use','your','each','such','into','let',
    'made','just','over','then','them','than','that','this','with','from','they','will',
    'what','when','been','have','more','would','could','their','there','which','here',
    'also','about','after','back','because','before','being','between','both','come',
    'does','even','find','first','going','good','great','high','home','keep','last',
    'life','long','look','make','many','most','much','must','name','need','next','only',
    'part','place','point','read','right','same','should','small','some','take','tell',
    'thing','think','time','turn','under','very','want','well','work','world','year',
    'down','still','while','online','click','page','learn','create','help','like',
    'love','free','top','using','used','yourself',' yourselves','download','sign',
    'contact','read','article','guide','resources','information','types','related'
}

# Common theme indicators — these are expanded dynamically per page
# This is the starter set that triggers theme detection
THEME_SEED_PATTERNS = {
    'pricing': ['price','cost','pricing','plans','pricing plans','cost of','monthly','annual','subscription','fee','charge','rate','packages','tier'],
    'features': ['features','feature','capabilities','functionality','tools','what it does','can do','lets you','helps you','function','built-in','integrated'],
    'comparison': ['compare','comparison','vs ','vs.','alternative','versus','compared','differ','other solutions','competitors','rival','instead of','notion vs','alternatives to'],
    'benefits': ['benefits','benefit','advantage','why','why use','reasons','value','outcomes','results','impact','gains','improves','saves'],
    'reviews': ['review','reviews','rating','testimonials','feedback','customers say','user review','what users','real users'],
    'how it works': ['how it works','how to','how does','process','steps','workflow','getting started','setup','implementation','getting started'],
    'eligibility': ['requirements','eligibility','who is for','who should','prerequisites','needed','necessary',' qualifications','candidates'],
    'integrations': ['integrations','integrates','connects','compatibility','works with','add-ons','extensions','plugins','api'],
    'use cases': ['use cases','use case','when to','scenarios','examples','how to use','applications','industries','who uses'],
    'risks': ['risks','risk','limitations','disadvantages','cons','drawbacks','problems','issues','concerns','not suitable','may not be'],
    'support': ['support','help','customer service','assistance','help center','contact','resources','documentation','faq','knowledge'],
    'alternatives': ['alternatives','alternative','competitors','vs ','instead','notion alternative','best notion alternative','replace'],
    'getting started': ['get started','setup','installation','quick start','onboarding','setup','how to sign up','sign up','register','create account'],
    'free trial': ['free trial','trial','free','demo','try','no credit card','start free','begin'],
    'mobile': ['mobile','app','ios','android','smartphone','iphone','ipad','on the go'],
    'security': ['security','secure','safe','encrypted','privacy','data protection','gdpr','compliance','soc2'],
    'templates': ['templates','premade','ready-made','examples','sample','library'],
    'updates': ['updates','new','latest','what\'s new','changelog','recent','2024','2025'],
    'team': ['team','teams','collaboration','collaborate','share','multiplayer','groups','organizations'],
}

def get_page_text(url, timeout=8):
    """Fetch a URL and extract readable text."""
    try:
        req = urllib.request.Request(url,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; KeywordResearchBot/1.0)'}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            text = re.sub(r'<[^>]+>', ' ', html)
            text = re.sub(r'\s+', ' ', text).strip()
            return text[:4000]
    except:
        return ""

def find_themes_in_text(text, seed_patterns):
    """Detect which theme categories appear in text."""
    text_lower = text.lower()
    found = {}
    for theme, patterns in seed_patterns.items():
        for pat in patterns:
            if pat in text_lower:
                found[theme] = found.get(theme, 0) + 1
    return found

def expand_theme_patterns(text, seed_themes):
    """Look for additional patterns in page content not in seed list."""
    text_lower = text.lower()
    # Find all H2/H3 headings
    headings = re.findall(r'<h[23][^>]*>([^<]+)<', text_lower) or []
    subtopics = re.findall(r'\b([a-z]{4,20}\s+(?:features?|benefits?|options?|solutions?|tools?|services?|platform|software|app|system))\b', text_lower)
    return headings + subtopics

def main():
    urls_raw = sys.argv[1] if len(sys.argv) > 1 else ""
    core_keyword = sys.argv[2] if len(sys.argv) > 2 else ""
    auth = sys.argv[3] if len(sys.argv) > 3 else ""
    
    urls = [u.strip() for u in urls_raw.split('\n') if u.strip()][:10]
    
    all_theme_counts = Counter()
    all_headings = []
    page_theme_map = {}
    
    for url in urls:
        text = get_page_text(url)
        if not text:
            continue
        
        # Detect which themes are present
        themes = find_themes_in_text(text, THEME_SEED_PATTERNS)
        page_theme_map[url] = themes
        
        for theme, count in themes.items():
            all_theme_counts[theme] += count
        
        # Collect headings for dynamic theme discovery
        headings = re.findall(r'<h[23][^>]*>([^<]+)<', text)
        all_headings.extend(headings)
    
    # Also look at headings to discover emergent themes
    heading_themes = Counter()
    for h in all_headings:
        h_clean = re.sub(r'[^a-z0-9\s]', '', h.lower())
        for theme, patterns in THEME_SEED_PATTERNS.items():
            if any(p in h_clean for p in patterns):
                heading_themes[theme] += 3  # weight headings higher
    
    # Merge counts
    for theme, count in heading_themes.items():
        all_theme_counts[theme] += count
    
    # Pick top themes (at least 2, at most 8)
    top_themes = [t for t, _ in all_theme_counts.most_common(8)]
    if not top_themes:
        # Default themes when nothing detected
        top_themes = ['features', 'pricing', 'how it works', 'comparison']
    
    # Build theme objects
    result = []
    for theme in top_themes:
        result.append({
            "theme": theme,
            "signals": all_theme_counts.get(theme, 0),
            "pages_covering": sum(1 for t in page_theme_map.values() if theme in t)
        })
    
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
