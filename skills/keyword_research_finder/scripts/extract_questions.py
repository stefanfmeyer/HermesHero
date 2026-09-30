#!/usr/bin/env python3
"""
extract_questions.py
Extract question-based keywords from SERP data and keyword suggestions.
Deduplicate and filter for commercially relevant questions.
"""
import sys
import json
import re

def extract_from_serp(serp_raw):
    """Extract PAA and question keywords from SERP response."""
    questions = []
    try:
        data = json.loads(serp_raw) if serp_raw.startswith('{') else {}
        tasks = data.get('tasks', [])
        for task in tasks:
            result = task.get('result', [])
            if result and len(result) > 0:
                items = result[0].get('items', [])
                for item in items:
                    # People Also Ask
                    for paa in item.get('items', [])[:10]:
                        question = paa.get('question', '')
                        if question and len(question.split()) <= 15:
                            questions.append(question)
    except:
        pass
    return questions

def extract_from_suggestions(suggestions_raw):
    """Extract question-format keywords from suggestions."""
    questions = []
    for line in suggestions_raw.split('\n'):
        line = line.strip()
        if not line:
            continue
        # Starts with what, how, why, is, can, does, should, will, does
        if re.match(r'^(what|how|why|is|can|does|should|will|do|which|when|where|who)\b', line.lower()):
            questions.append(line)
    return questions

def score_question(q, core_kw):
    """Score question for FAQ usefulness."""
    score = 0
    q_lower = q.lower()
    
    # Questions that suggest purchase consideration
    if any(w in q_lower for w in ['cost','price','free','trial','demo','buy','plan']):
        score += 2
    # Questions that address concerns
    if any(w in q_lower for w in ['safe','secure','reliable',' legit','good','better','worth']):
        score += 2
    # Comparison questions
    if ' vs ' in q_lower or ' versus ' in q_lower:
        score += 1
    # How/what questions that explain the product
    if any(w in q_lower for w in ['work','use','help','do','does']):
        score += 1
    
    # Penalise very long questions
    if len(q.split()) > 12:
        score -= 1
    
    return score

def main():
    serp_raw = sys.argv[1] if len(sys.argv) > 1 else ""
    suggestions_raw = sys.argv[2] if len(sys.argv) > 2 else ""
    
    all_q = []
    all_q.extend(extract_from_serp(serp_raw))
    all_q.extend(extract_from_suggestions(suggestions_raw))
    
    # Deduplicate
    seen = set()
    unique = []
    for q in all_q:
        q_clean = q.strip()
        if q_clean and q_clean.lower() not in seen and len(q_clean) > 10:
            seen.add(q_clean.lower())
            unique.append(q_clean)
    
    # Score and rank
    scored = [(score_question(q, ""), q) for q in unique]
    scored.sort(reverse=True)
    
    top_q = [q for _, q in scored[:20]]
    
    print('\n'.join(top_q))

if __name__ == '__main__':
    main()
