#!/usr/bin/env python3
"""
extract_topic.py
Infers the primary topic/keyword from a page's text content.
Uses frequency analysis and phrase detection.
"""
import sys
import re
from collections import Counter

def extract_key_phrases(text, min_len=3, max_len=6, top_n=8):
    """Extract important noun phrases and key terms."""
    # Remove punctuation, keep alphanumeric
    words = re.findall(r'\b[a-zA-Z][a-zA-Z0-9+\-.]{2,}\b', text.lower())
    
    # Stopwords
    stopwords = {
        'the','and','for','are','but','not','you','all','can','had','her','was','one','our',
        'out','day','get','has','him','his','how','its','may','new','now','old','see','two',
        'way','who','boy','did','own','say','she','too','use','your','each','such','into',
        'let','made','just','over','then','them','than','that','this','with','from','they',
        'will','what','when','been','have','more','would','could','their','there','which',
        'here','also','about','after','back','because','before','being','between','both',
        'come','does','even','find','first','from','going','good','great','high','home',
        'keep','last','life','long','look','made','make','many','most','much','must',
        'name','need','next','only','part','place','point','read','right','same','should',
        'small','some','take','tell','thing','think','time','turn','under','very','want',
        'well','work','world','year','down','still','while','online','click','page','read',
        'learn','create','help','like','love','best','free','top','use','using','used'
    }
    
    # Filter stopwords and short words
    filtered = [w for w in words if w not in stopwords and len(w) >= min_len]
    
    # Count single words
    word_counts = Counter(filtered)
    
    # Extract bigrams and trigrams
    bigrams = [' '.join(filtered[i:i+2]) for i in range(len(filtered)-1) if filtered[i] not in stopwords]
    trigrams = [' '.join(filtered[i:i+3]) for i in range(len(filtered)-2)]
    
    phrase_counts = Counter(bigrams + trigrams)
    
    # Combine and rank
    combined = Counter()
    for phrase, count in word_counts.most_common(30):
        combined[phrase] = count * 2  # Weight single words
    for phrase, count in phrase_counts.most_common(30):
        combined[phrase] = combined.get(phrase, 0) + count
    
    # Filter to phrases likely to be keyword-worthy
    keywords = []
    for phrase, score in combined.most_common(top_n * 2):
        # Skip if phrase is mostly stopwords
        phrase_words = phrase.split()
        significant = sum(1 for w in phrase_words if w not in stopwords)
        if significant >= len(phrase_words) / 2 and len(phrase) >= 4:
            keywords.append(phrase)
    
    return keywords[:top_n]

def main():
    content = sys.stdin.read()[:3000]  # limit
    if not content.strip():
        print("unknown")
        return
    
    phrases = extract_key_phrases(content)
    
    # Pick the most likely primary keyword
    if phrases:
        # Prefer longer, more specific phrases as primary
        primary = phrases[0]
        print(primary)
    else:
        print("unknown")

if __name__ == '__main__':
    main()
