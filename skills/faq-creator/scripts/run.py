#!/usr/bin/env python3
"""
faq_creator.py — Generate FAQ section from article + PAA data
Run: python3 run.py --article "path/to/article.md" --primary "seo tips" --brand "ExampleBrand"
"""
import sys
import json
import argparse
import urllib.request
import urllib.error
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

def load_brand_context(brand_id, author_persona=None):
    """Load brand guidelines from Google Drive."""
    # For now, return placeholder - in real implementation, fetch from gog
    return {
        "voice": "Direct, confident, plain English",
        "tone": "Expert but approachable",
        "style": "UK English, sentence case headings"
    }

def extract_article_topics(article_text):
    """Extract topics covered in the article."""
    topics = []
    
    # Extract H2s and H3s
    for match in re.finditer(r'^#{2,3}\s+(.+)$', article_text, re.MULTILINE):
        heading = match.group(1).lower().strip()
        topics.append(heading)
    
    # Extract first sentences from paragraphs
    paragraphs = article_text.split('\n\n')
    for para in paragraphs[:10]:  # First 10 paragraphs
        clean = re.sub(r'#+', '', para).strip()
        if clean and len(clean) > 20:
            first_sent = clean.split('.')[0].lower()
            if len(first_sent) > 15:
                topics.append(first_sent)
    
    return topics

def get_paa_questions(primary_keyword):
    """Fetch PAA questions from DataForSEO SERP."""
    print(f"\n[1] Fetching PAA questions for: {primary_keyword}")
    
    result = api_post("serp/google/organic/live/advanced", [{
        "keyword": primary_keyword,
        "location_name": "United Kingdom",
        "language_name": "English",
        "max_crawl_pages": 10
    }])
    
    paa = []
    if 'tasks' in result:
        for task in result.get('tasks', []):
            for r in task.get('result', []):
                for item in r.get('items', [])[:30]:
                    if item.get('type') == 'people_also_ask':
                        question = item.get('rich_snippet', {}).get('top', {}).get('description', '')
                        if not question:
                            question = item.get('snippet', '')
                        if question and len(question) > 10:
                            # Clean the question
                            question = question.strip()
                            if question.endswith('?'):
                                question = question[:-1]
                            paa.append(question)
    
    print(f"    Found {len(paa)} PAA questions")
    return paa

def should_include_question(question, article_topics, keywords_to_avoid):
    """Check if question should be included."""
    q_lower = question.lower()
    
    # Check keywords to avoid
    for kw in keywords_to_avoid:
        if kw.lower() in q_lower:
            return False, "matches keyword to avoid"
    
    # Check if topic already covered
    for topic in article_topics:
        topic_words = topic.split()[:3]  # First 3 words
        if all(word in q_lower for word in topic_words if len(word) > 3):
            return False, f"topic already covered: {topic[:30]}"
    
    return True, "passed"

def generate_faq_answers(questions, brand_context, author_persona=None):
    """Generate FAQ answers in brand voice."""
    print(f"\n[2] Generating FAQ answers in brand voice...")
    
    answers = []
    for i, q in enumerate(questions, 1):
        # Generate a brief answer
        answer = f"[Answer for: {q} — generated in {brand_context.get('voice', 'brand')} voice]"
        answers.append({
            "question": q,
            "answer": answer  # In real implementation, use LLM or template
        })
        print(f"    Q{i}: {q[:50]}...")
    
    return answers

def build_faq_markdown(faqs):
    """Build FAQ markdown section."""
    md = "### Frequently Asked Questions\n\n"
    for faq in faqs:
        md += f"**{faq['question']}?**\n"
        md += f"{faq['answer']}\n\n"
    return md

def build_faq_schema(faqs):
    """Build FAQPage JSON-LD schema."""
    entities = []
    for faq in faqs:
        entities.append({
            "@type": "Question",
            "name": faq['question'] + "?",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": faq['answer']
            }
        })
    
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": entities
    }

def main():
    parser = argparse.ArgumentParser(description='FAQ Creator')
    parser.add_argument('--article', required=True, help='Path to article markdown file')
    parser.add_argument('--primary', required=True, help='Primary keyword')
    parser.add_argument('--brand', required=True, help='Brand ID for Google Drive')
    parser.add_argument('--author', help='Author persona (optional)')
    parser.add_argument('--avoid', nargs='*', help='Keywords to avoid')
    parser.add_argument('--output', help='Output file prefix')
    args = parser.parse_args()
    
    print(f"\n{'='*60}")
    print(f"  FAQ CREATOR")
    print(f"{'='*60}")
    print(f"\n  Article: {args.article}")
    print(f"  Primary keyword: {args.primary}")
    print(f"  Brand: {args.brand}")
    print(f"  Author: {args.author or 'brand-default'}")
    
    # Load article
    print(f"\n[0] Loading article...")
    with open(args.article, 'r') as f:
        article_text = f.read()
    print(f"    Article loaded: {len(article_text)} chars")
    
    # Extract topics
    print(f"\n[0b] Extracting article topics...")
    topics = extract_article_topics(article_text)
    print(f"    Found {len(topics)} topics")
    
    # Load brand context
    print(f"\n[0c] Loading brand context...")
    brand = load_brand_context(args.brand, args.author)
    print(f"    Voice: {brand.get('voice')}")
    
    # Get PAA questions
    keywords_to_avoid = args.avoid or []
    paa = get_paa_questions(args.primary)
    
    # Filter questions
    print(f"\n[3] Filtering questions...")
    filtered = []
    for q in paa:
        include, reason = should_include_question(q, topics, keywords_to_avoid)
        if include:
            filtered.append(q)
            print(f"    ✓ {q[:50]}...")
        else:
            print(f"    ✗ {q[:40]}... ({reason})")
    
    # Limit to 5-6
    filtered = filtered[:6]
    print(f"\n    {len(filtered)} questions after filtering")
    
    # Generate answers
    faqs = generate_faq_answers(filtered, brand, args.author)
    
    # Build outputs
    print(f"\n[4] Building outputs...")
    md = build_faq_markdown(faqs)
    schema = build_faq_schema(faqs)
    
    print(f"\n{'='*60}")
    print(f"  FAQ SECTION")
    print(f"{'='*60}")
    print(md)
    
    # Save
    if args.output:
        with open(f"{args.output}-faq.md", 'w') as f:
            f.write(md)
        with open(f"{args.output}-faq-schema.json", 'w') as f:
            json.dump(schema, f, indent=2)
        print(f"\n[Saved] {args.output}-faq.md")
        print(f"[Saved] {args.output}-faq-schema.json")
    
    return {"markdown": md, "schema": schema}

if __name__ == '__main__':
    main()