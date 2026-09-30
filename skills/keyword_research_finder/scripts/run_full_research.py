#!/usr/bin/env python3
"""
run_full_research.py
End-to-end keyword research for choosemycar.com/bad-credit-car-finance
All DataForSEO calls in one script with cost tracking.
"""
import sys, json, re, urllib.request, urllib.error
from datetime import date

CREDS_FILE = "/Users/walter/.openclaw/credentials.json"
SPEND_TRACKER = "/Users/walter/.openclaw/dataforseo_spend.json"
BASE_URL = "https://api.dataforseo.com/v3"

# Load credentials
creds = json.load(open(CREDS_FILE))['dataforseo']
login, password = creds['login'], creds['password']
import base64
auth_base64 = base64.b64encode(f"{login}:{password}".encode()).decode()

TODAY = date.today().isoformat()

def track_spend(cost):
    data = {}
    if __import__('os').path.exists(SPEND_TRACKER):
        data = json.load(open(SPEND_TRACKER))
    data[TODAY] = round(data.get(TODAY, 0) + cost, 6)
    json.dump(data, open(SPEND_TRACKER, 'w'))

def api_post(endpoint, payload):
    url = f"{BASE_URL}/{endpoint}"
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={
        'Authorization': f'Basic {auth_base64}',
        'Content-Type': 'application/json'
    }, method='POST')
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())
        track_spend(result.get('cost', 0))
        return result

def fetch_url(url):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'en-GB,en;q=0.9',
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode('utf-8', errors='ignore')
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'(?is)<(script|style)[^>]*>.*?</\1>', '', text)
        return re.sub(r'\s+', ' ', text).strip()

def extract_topic(text):
    stopwords = {'the','and','for','are','but','not','you','all','can','had','her','was','one','our','out','day','get','has','him','his','how','its','may','new','now','old','see','two','way','who','boy','did','own','say','she','too','use','your','each','such','into','let','made','just','over','then','them','than','that','this','with','from','they','will','what','when','been','have','more','would','could','their','there','which','here','also','about','after','back','because','before','being','between','both','come','does','even','find','first','from','going','good','great','high','home','keep','last','life','long','look','made','make','many','most','much','must','name','need','next','only','part','place','point','read','right','same','should','small','some','take','tell','thing','think','time','turn','under','very','want','well','work','world','year','down','still','while','online','click','page','learn','create','help','like','love','best','free','top','use','using','used'}
    words = re.findall(r'\b[a-zA-Z][a-zA-Z0-9+\-.]{2,}\b', text.lower())
    filtered = [w for w in words if w not in stopwords and len(w) >= 4]
    bigrams = [' '.join(filtered[i:i+2]) for i in range(len(filtered)-1)]
    from collections import Counter
    combined = Counter(filtered) + Counter(bigrams)
    for phrase, _ in combined.most_common(30):
        phrase_len = len(phrase.split()) if isinstance(phrase, str) else 1
        if phrase_len >= 2 and len(phrase) >= 8:
            return phrase
    return 'bad credit car finance'

MODIFIERS = ['best','top','cheap','cost','price','pricing','review','comparison','compare','alternative','vs','features','benefits','requirements','eligibility','process','near me','online','support','options']

def score_kw(kw, core):
    score = 0
    core_words = set(core.lower().split())
    kw_words = set(kw.lower().split())
    overlap = len(kw_words & core_words)
    if overlap >= 1: score += 2
    if overlap >= 2: score += 3
    commercial = ['price','cost','buy','plan','review','vs','compare','best','top','free','demo','hire purchase','car finance','loan','bad credit','guaranteed','approved']
    if any(c in kw.lower() for c in commercial): score += 2
    if re.match(r'^(what is|how to|how do|why is|tutorial)', kw.lower()): score -= 2
    if len(kw.split()) > 8: score -= 1
    return score

print("="*54)
print("  KEYWORD RESEARCH FINDER")
print("="*54)
print(f"Started: {TODAY}")

# Step 1: Fetch URL and extract topic
print("\n[STEP 1] Fetching URL...")
text = fetch_url("https://choosemycar.com/bad-credit-car-finance")
topic = extract_topic(text)
print(f"Primary topic: {topic}")

# Step 2: SERP
print("\n[STEP 2] SERP organic...")
serp = api_post("serp/google/organic/live/advanced", [{
    "keyword": topic,
    "location_name": "United Kingdom",
    "language_name": "English",
    "include_answer_box": True,
    "include_people_also_ask": True,
}])
tasks = serp.get('tasks', [])
result = tasks[0].get('result', []) if tasks else []
organic_items = result[0].get('items', []) if result else []
serp_urls = []
for item in organic_items[:20]:
    if item.get('url'):
        serp_urls.append(item['url'])
print(f"  Found {len(serp_urls)} ranking URLs")

# Extract PAA — handle different SERP response structures
paa = []
for item in organic_items:
    for p in item.get('items', [])[:5]:
        if isinstance(p, dict) and p.get('question'):
            paa.append(p['question'])
        elif isinstance(p, str) and '?' in p:
            paa.append(p)
print(f"  Found {len(paa)} PAA questions")

# Step 3: Keyword variations
print("\n[STEP 3] Keyword variations...")
vars_result = api_post("keywords_data/google/keyword_variations/live", [{
    "keyword": topic, "location_name": "United Kingdom", "language_name": "English"
}])
var_kws = []
for t in vars_result.get('tasks', []):
    for r in t.get('result', []):
        for i in r.get('items', [])[:40]:
            k = i.get('keyword','')
            if k: var_kws.append(k)
print(f"  {len(var_kws)} keyword variations")

# Step 4: Keyword suggestions
print("\n[STEP 4] Keyword suggestions...")
all_suggest = []
# Core kw
suggest_result = api_post("keywords_data/google/keyword_suggestions/live", [{
    "keyword": topic, "location_name": "United Kingdom", "language_name": "English"
}])
for t in suggest_result.get('tasks', []):
    for r in t.get('result', []):
        for i in r.get('items', [])[:20]:
            k = i.get('keyword','')
            if k: all_suggest.append(k)
# With modifiers
for mod in MODIFIERS[:8]:
    r = api_post("keywords_data/google/keyword_suggestions/live", [{
        "keyword": f"{topic} {mod}", "location_name": "United Kingdom", "language_name": "English"
    }])
    for t in r.get('tasks', []):
        for r2 in t.get('result', []):
            for i in r2.get('items', [])[:8]:
                k = i.get('keyword','')
                if k and k.lower() not in [s.lower() for s in all_suggest]: all_suggest.append(k)
print(f"  {len(all_suggest)} keyword suggestions")

# Step 5: Related
print("\n[STEP 5] Related keywords...")
rel_result = api_post("keywords_data/google/related_results/live", [{
    "keyword": topic, "location_name": "United Kingdom", "language_name": "English"
}])
rel_kws = []
for t in rel_result.get('tasks', []):
    for r in t.get('result', []):
        for i in r.get('items', [])[:30]:
            k = i.get('keyword','')
            if k: rel_kws.append(k)
print(f"  {len(rel_kws)} related keywords")

# Step 6: Combine + score
print("\n[STEP 6] Scoring and filtering...")
all_kws = list(set(var_kws + all_suggest + rel_kws))
scored = [(score_kw(k, topic), k) for k in all_kws]
scored.sort(reverse=True)
top_kws = [k for s, k in scored if s > 0]
secondary = [k for k in top_kws if any(c in k.lower() for c in ['price','cost','plan','buy','review','vs','compare','best','hire purchase','guaranteed','approved'])][:12]
supporting = [k for k in top_kws if k not in secondary and any(c in k.lower() for c in ['bad credit','car finance','loan','mortgage','vehicle','quote','broker','dealer'])][:15]
print(f"  {len(top_kws)} keywords after filtering")

# Step 7: Detect themes from SERP URLs
print("\n[STEP 7] Detecting themes from competitor pages...")
theme_map = {
    'pricing': ['price','cost','pricing','apr','rate','rates','monthly','payment','deposit','representative'],
    'features': ['features','feature','capabilities','options','choose','selection','vehicle','cars'],
    'eligibility': ['eligibility','eligible','criteria','requirements','qualify','accepted','approved','accepted'],
    'how it works': ['how it works','apply','application','process','steps','get started','online'],
    'finance types': ['hire purchase','hp','conditional sale','cs','personal contract','pcp','lease','finance'],
    'bad credit': ['bad credit','poor credit','adverse credit','credit history','credit score'],
    'guarantees': ['guaranteed','assurance','no obligation','free','no fee'],
    'testimonials': ['review','reviews','testimonial','customer','rating','trustpilot','experience'],
}
found_themes = {}
for u in serp_urls[:8]:
    try:
        ct = fetch_url(u)
        ct_lower = ct.lower()
        for theme, patterns in theme_map.items():
            if any(p in ct_lower for p in patterns):
                found_themes[theme] = found_themes.get(theme, 0) + 1
    except:
        pass

top_themes = sorted(found_themes.items(), key=lambda x: -x[1])[:6]
print(f"  {len(top_themes)} themes detected")

# Step 8: Build report
print("\n" + "="*54)
print("  KEYWORD RESEARCH FINDER — Landing Page Keyword Opportunity")
print("="*54)

print(f"\nPRIMARY KEYWORD IDENTIFIED:\n  {topic}\n")
print("SECONDARY KEYWORDS (commercial intent):")
for k in secondary: print(f"  • {k}")
print()

print("SUPPORTING KEYWORD VARIATIONS:")
for k in supporting[:12]: print(f"  • {k}")
print()

print("QUESTION-BASED KEYWORDS:")
for q in paa[:10]: print(f"  • {q}")
print()

print("━"*54)
print("KEYWORD THEMES")
print("━"*54)
theme_guidance = {
    'pricing': ("Pricing & Rates", "Most ranking pages include APR, monthly payment examples, and representative rates.", "Show representative APR, example monthly payments, deposit requirements."),
    'features': ("Vehicle Selection & Options", "Competitors emphasise the range of vehicles and finance options available.", "Highlight vehicle types, brands, and finance plans available."),
    'eligibility': ("Approval Criteria", "Searchers with bad credit want to know if they'll qualify before applying.", "State clear eligibility criteria — credit history, income requirements."),
    'how it works': ("Application Process", "Quick, frictionless process is a key differentiator.", "Show simple 3-step process — apply online, get a decision, choose your car."),
    'finance types': ("Finance Plan Types", "Hire Purchase and Conditional Sale are the core products for this audience.", "Clearly explain HP and CS — differences, ownership, flexibility."),
    'bad credit': ("Bad Credit Explanation", "Core topic — page must address what bad credit means and how the service helps.", "Explain how bad credit car finance works and why traditional lenders say no."),
    'guarantees': ("No-Obligation Assurance", "Reducing perceived risk for hesitant applicants.", "Prominently feature no-obligation quotes and guaranteed approval options."),
    'testimonials': ("Social Proof", "Trustpilot ratings and customer reviews appear prominently on competitors.", "Include recent reviews, Trustpilot score, and specific success stories."),
}
for theme, count in top_themes:
    if theme in theme_guidance:
        name, reason, coverage = theme_guidance[theme]
        kw_list = [k for k in top_kws if any(p in k.lower() for p in theme.split())]
        print(f"\n  Theme: {name}")
        print(f"  Keywords: {', '.join(kw_list[:5]) if kw_list else '(from SERP patterns)'}")
        print(f"  Why it matters: {reason}")
        print(f"  Coverage: {coverage}")

print()
print("━"*54)
print("POTENTIAL FAQ OPPORTUNITIES")
print("━"*54)
print("  From PAA and keyword data:")
for q in paa[:8]: print(f"  → {q}")

print()
print("━"*54)
print("DATA SOURCES USED")
print("━"*54)
print(f"  DataForSEO SERP — {len(serp_urls)} URLs")
print(f"  Keyword variations — {len(var_kws)}")
print(f"  Keyword suggestions — {len(all_suggest)} (incl. {len(MODIFIERS[:8])} modifiers)")
print(f"  Related keywords — {len(rel_kws)}")
print(f"  Competitor pages analysed — {min(8, len(serp_urls))}")
print(f"  Final filtered set — {len(top_kws)} keywords")
print("="*54)
