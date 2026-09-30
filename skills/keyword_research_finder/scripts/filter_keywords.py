#!/usr/bin/env python3
"""
filter_keywords.py
Filter keyword list for relevance and intent alignment.
Removes keywords unrelated to core topic, purely informational
queries (when commercial intent), and low-relevance variations.
"""
import sys
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
    'love','free','top','using','used'
}

# Patterns that indicate purely informational intent (commercial pages)
INFO_ONLY_PATTERNS = [
    r'^what is\b', r'^how to\b', r'^how do\b', r'^how does\b',
    r'^why is\b', r'^why do\b', r'^when is\b',
    r'^who is\b', r'^who was\b', r'^where is\b',
    r'^tutorial\b', r'^guide to\b', r'^steps to\b',
    r'^history of\b', r'^biography\b', r'^definition of\b',
]

# Patterns that indicate blog/editorial, not landing page
BLOG_PATTERNS = [
    r'^my ', r'^i ', r'^we ', r'^our ',
    r' experience\b', r' journey\b', r' story\b',
    r'^best [a-z]+ in ', r'^top [a-z]+ for ',
    r' ideas\b', r' tips\b', r' tricks\b',
    r' in 2024\b', r' in 2025\b',
    r'^ list of\b', r' examples\b',
]

def keyword_token_overlap(kw, core_kw, min_overlap=1):
    """Check if keyword shares significant terms with core keyword."""
    kw_words = set(re.findall(r'[a-z]+', kw.lower()))
    core_words = set(re.findall(r'[a-z]+', core_kw.lower()))
    significant_kw = kw_words - STOPWORDS
    significant_core = core_words - STOPWORDS
    overlap = len(significant_kw & significant_core)
    return overlap >= min_overlap

def is_commercial_intent(kw):
    """Detect commercial transaction/comparison intent."""
    commercial = [
        'buy','price','cost','pricing','plan','plans','pricing',
        'review','reviews','vs ','versus','compare','comparison',
        'best','top','alternative','alternative to','代替',
        'discount','deal','offer','free trial','demo',
        'subscription','purchase','license','software','tool',
        'platform','service','solution','app','download',
    ]
    kw_lower = kw.lower()
    return any(c in kw_lower for c in commercial)

def is_informational_only(kw, page_type):
    """Check if keyword is purely informational (not appropriate for commercial page)."""
    if page_type and page_type.lower() in ('info', 'blog', 'guide'):
        return False  # informational pages can use these
    
    for pat in INFO_ONLY_PATTERNS:
        if re.match(pat, kw.lower()):
            return True
    for pat in BLOG_PATTERNS:
        if re.search(pat, kw.lower()):
            return True
    return False

def is_cannibalising(kw, competing_keywords):
    """Check if keyword overlaps significantly with competing page keywords."""
    if not competing_keywords:
        return False
    kw_lower = kw.lower()
    kw_words = set(re.findall(r'[a-z]+', kw_lower)) - STOPWORDS
    
    for comp in competing_keywords:
        comp_lower = comp.lower()
        comp_words = set(re.findall(r'[a-z]+', comp_lower)) - STOPWORDS
        
        # Check for significant overlap (3+ shared meaningful words)
        overlap = kw_words & comp_words
        if len(overlap) >= 3:
            return True
        
        # Check if kw is a substring of competing keyword (or vice versa)
        if kw_lower in comp_lower or comp_lower in kw_lower:
            # But only if it's substantial (not just "car finance")
            if len(kw_words) > 2:
                return True
        
        # Check for key phrase match
        kw_phrase = ' '.join(sorted(kw_words))
        comp_phrase = ' '.join(sorted(comp_words))
        if kw_phrase == comp_phrase:
            return True
    
    return False

def score_keyword(kw, core_kw, existing_keywords, page_type, competing_keywords=None):
    """Score a keyword for relevance. Higher = more relevant."""
    score = 0
    kw_lower = kw.lower()
    
    # First check: filter out cannibalising keywords
    if competing_keywords and is_cannibalising(kw, competing_keywords):
        return -10  # Strong penalty to exclude
    
    # Overlap with core keyword
    if keyword_token_overlap(kw, core_kw, min_overlap=1):
        score += 2
    if keyword_token_overlap(kw, core_kw, min_overlap=2):
        score += 3
    
    # Commercial intent bonus
    if is_commercial_intent(kw):
        score += 2
    
    # If it's in existing keywords, it's relevant
    if existing_keywords:
        for ex in existing_keywords:
            if ex.lower() in kw_lower or kw_lower in ex.lower():
                score += 2
                break
    
    # Penalise purely informational
    if is_informational_only(kw, page_type):
        score -= 2
    
    # Penalise overly long keywords (likely long-tail irrelevant)
    if len(kw.split()) > 7:
        score -= 1
    
    # Length bonus for medium-long (specific commercial)
    if 2 <= len(kw.split()) <= 5:
        score += 1
    
    return score

def main():
    keywords_raw = sys.argv[1] if len(sys.argv) > 1 else ""
    core_kw = sys.argv[2] if len(sys.argv) > 2 else ""
    existing_raw = sys.argv[3] if len(sys.argv) > 3 else ""
    page_type = sys.argv[4] if len(sys.argv) > 4 else ""
    competing_raw = sys.argv[5] if len(sys.argv) > 5 else ""
    
    keywords = [k.strip() for k in keywords_raw.split('\n') if k.strip()]
    existing = [e.strip() for e in existing_raw.split('|') if e.strip()]
    competing = [c.strip() for c in competing_raw.split('\n') if c.strip()]
    
    scored = []
    excluded = []
    for kw in keywords:
        score = score_keyword(kw, core_kw, existing, page_type, competing)
        if score < -5:  # Cannibalising keywords
            excluded.append(kw)
        else:
            scored.append((score, kw))
    
    # Sort by score descending, keep positive scores
    scored.sort(reverse=True)
    
    # Top keywords (cap at 80)
    top_kw = [kw for score, kw in scored if score > 0][:80]
    
    print('\n'.join(top_kw))

if __name__ == '__main__':
    main()
