#!/usr/bin/env python3
"""
build_report.py
Assemble the final structured keyword research report.
"""
import sys
import json
import re

def parse_keywords(raw, max_items=25):
    """Parse keyword pipe string or newline string into a list."""
    if '|' in raw:
        keywords = [k.strip() for k in raw.split('|') if k.strip()]
    else:
        keywords = [k.strip() for k in raw.split('\n') if k.strip()]
    return keywords[:max_items]

def main():
    core_kw = sys.argv[1] if len(sys.argv) > 1 else ""
    filtered_kw_raw = sys.argv[2] if len(sys.argv) > 2 else ""
    themes_json_raw = sys.argv[3] if len(sys.argv) > 3 else "[]"
    theme_report = sys.argv[4] if len(sys.argv) > 4 else ""
    faq_raw = sys.argv[5] if len(sys.argv) > 5 else ""
    existing_raw = sys.argv[6] if len(sys.argv) > 6 else ""
    kw_total = sys.argv[7] if len(sys.argv) > 7 else "0"
    filtered_count = sys.argv[8] if len(sys.argv) > 8 else "0"
    serp_count = sys.argv[9] if len(sys.argv) > 9 else "0"
    
    existing_keywords = parse_keywords(existing_raw, 20) if existing_raw else []
    filtered_keywords = parse_keywords(filtered_kw_raw, 30)
    
    # Split into commercial (secondary) and supporting
    secondary = [k for k in filtered_keywords if any(w in k.lower() for w in ['price','cost','plan','buy','review','vs','compare','best','top','free','demo'])][:12]
    supporting = [k for k in filtered_keywords if k not in secondary][:15]
    
    try:
        themes_data = json.loads(themes_json_raw)
    except:
        themes_data = []
    
    theme_names = [t.get('theme','') for t in themes_data]
    
    # Keywords to avoid
    avoid = []
    for kw in (filtered_kw_raw.split('\n'))[:100]:
        kw_lower = kw.lower().strip()
        if not kw_lower:
            continue
        # Blog-style
        if re.match(r'^(my|i |we |our )', kw_lower):
            avoid.append(f"{kw} — personal/anecdotal angle, not suitable for commercial landing page")
        # Very long informational
        if len(kw.split()) > 10 and not any(w in kw_lower for w in ['price','cost','plan','buy']):
            avoid.append(f"{kw} — overly long query, likely informational intent")
    
    avoid = avoid[:8]
    
    # Format existing keywords
    existing_section = ""
    if existing_keywords:
        existing_section = (
            f"\n  Retained from existing: {', '.join(existing_keywords[:10])}"
            + (f" and {len(existing_keywords)-10} more" if len(existing_keywords) > 10 else "")
        )
    
    print("=" * 54)
    print("  KEYWORD RESEARCH FINDER — Landing Page Keyword Opportunity")
    print("=" * 54)
    print()
    
    print("PRIMARY KEYWORD IDENTIFIED:")
    print(f"  {core_kw}")
    print()
    
    print("SECONDARY KEYWORDS (commercial intent):")
    if secondary:
        for kw in secondary:
            print(f"  • {kw}")
    else:
        print("  (none identified — consider reviewing commercial modifiers)")
    print()
    
    print("SUPPORTING KEYWORD VARIATIONS:")
    if supporting:
        for kw in supporting:
            print(f"  • {kw}")
    else:
        print("  (none meet relevance threshold)")
    print()
    
    print("QUESTION-BASED KEYWORDS:")
    faq_list = faq_raw.split('\n')[:15]
    if faq_list and faq_list[0]:
        for kw in faq_list:
            if kw.strip():
                print(f"  • {kw.strip()}")
    else:
        print("  (none identified in PAA or keyword suggestions)")
    print()
    
    print("━" * 54)
    print("KEYWORD THEMES")
    print("━" * 54)
    
    if theme_report.strip():
        print(theme_report)
    else:
        print(f"\n  No clear competitor themes detected from SERP data.")
        print(f"  Recommend covering: Core topic overview, Key features/benefits,")
        print(f"  Pricing (if applicable), and a primary call to action.")
    print()
    
    print("━" * 54)
    print("POTENTIAL FAQ OPPORTUNITIES")
    print("━" * 54)
    if faq_list and faq_list[0]:
        print("  The following questions appear in PAA or keyword data.")
        print("  Suitable for FAQ section or 'Common questions' coverage:")
        print()
        for q in faq_list[:10]:
            if q.strip():
                print(f"  → {q.strip()}")
    else:
        print("  No specific FAQ opportunities identified.")
    print()
    
    print("━" * 54)
    print("KEYWORDS TO AVOID TARGETING")
    print("━" * 54)
    if avoid:
        for entry in avoid:
            print(f"  ✗ {entry}")
    else:
        print("  No problematic keywords detected in the expanded set.")
    print()
    
    print("━" * 54)
    print("DATA SOURCES USED")
    print("━" * 54)
    print(f"  DataForSEO SERP — top {serp_count} ranking URLs analysed")
    print(f"  DataForSEO keyword variations — {kw_total} keywords retrieved")
    print(f"  DataForSEO keyword suggestions — expanded with modifiers")
    print(f"  DataForSEO related keywords — semantic expansion")
    if existing_keywords:
        print(f"  Existing keyword signals — {len(existing_keywords)} retained")
    print(f"  Relevance filtered: {kw_total} → {filtered_count} keywords kept")
    print()
    print("━" * 54)
    print("NEXT STEPS")
    print("━" * 54)
    print("  1. Review keyword themes against page structure")
    print("  2. Map each theme to a page section or heading")
    print("  3. Use secondary keywords in subheadings and body copy")
    print("  4. Add FAQ schema using the questions identified above")
    print("  5. Avoid keywords listed under 'avoid targeting'")
    print("=" * 54)

if __name__ == '__main__':
    main()
