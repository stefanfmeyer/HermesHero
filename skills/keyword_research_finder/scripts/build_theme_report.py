#!/usr/bin/env python3
"""
build_theme_report.py
Build descriptive coverage guidance for each detected keyword theme.
"""
import sys
import json
import re

# Theme guidance templates
THEME_GUIDANCE = {
    'pricing': {
        'name': 'Pricing',
        'reason': 'Most commercial landing pages include pricing information or cost explanations. Searchers evaluating options actively look for this.',
        'coverage': 'Explain pricing structure clearly. Include plan options, what's included at each tier, and any free trial or freemium option.'
    },
    'features': {
        'name': 'Features & Capabilities',
        'reason': 'Competitors consistently describe product features prominently. Searchers want to understand what they can do.',
        'coverage': 'Provide a clear overview of key functionality. Focus on the features most relevant to the primary keyword context.'
    },
    'comparison': {
        'name': 'Comparisons & Alternatives',
        'reason': 'Searchers at evaluation stage look for how options compare. Pages covering comparisons often attract high-intent traffic.',
        'coverage': 'Address common comparison queries. Include any clear differentiators vs alternatives. Be factual and balanced.'
    },
    'benefits': {
        'name': 'Benefits & Value',
        'reason': 'Understanding the outcomes and value proposition is a key step in conversion decisions.',
        'coverage': 'Describe the key outcomes and value delivered. Connect features to real-world benefits for the user.'
    },
    'reviews': {
        'name': 'Reviews & Social Proof',
        'reason': 'Searchers actively seek validation. Pages with reviews and testimonials attract comparison shoppers.',
        'coverage': 'Include testimonials, ratings, or case studies if available and genuine. Address common questions prospects have.'
    },
    'how it works': {
        'name': 'How It Works',
        'reason': 'Searchers need to understand the mechanism or process before committing. Clarity here reduces friction.',
        'coverage': 'Explain the core process or workflow clearly. Keep it concise — focus on what matters to someone evaluating the option.'
    },
    'eligibility': {
        'name': 'Requirements & Eligibility',
        'reason': 'Prospects need to know if something is relevant to them before investing time.',
        'coverage': 'State any requirements, prerequisites, or ideal user criteria clearly near the top of the page.'
    },
    'integrations': {
        'name': 'Integrations & Compatibility',
        'reason': 'Technical and workflow compatibility is a common evaluation criteria, especially in B2B contexts.',
        'coverage': 'List key integrations or compatibility information. Mention any popular tools, platforms, or ecosystems supported.'
    },
    'use cases': {
        'name': 'Use Cases & Applications',
        'reason': 'Searchers want to understand if a solution applies to their specific situation or industry.',
        'coverage': 'Describe the types of users, industries, or situations where the solution is most applicable. Include practical examples.'
    },
    'risks': {
        'name': 'Limitations, Risks & Considerations',
        'reason': 'Thorough evaluation includes understanding drawbacks. Transparent pages build trust.',
        'coverage': 'Be honest about limitations or situations where the product may not be suitable. This builds credibility and helps qualify leads.'
    },
    'support': {
        'name': 'Support & Resources',
        'reason': 'Post-purchase support is a common concern, especially for software and services.',
        'coverage': 'Describe available support channels, documentation, and resources. This reduces hesitation for new buyers.'
    },
    'alternatives': {
        'name': 'Alternatives & Competitors',
        'reason': 'Searchers often search for alternatives. Covering this topic captures high-intent comparison traffic.',
        'coverage': 'Address common alternative queries directly. Explain why the page\'s offering is a strong choice vs alternatives.'
    },
    'getting started': {
        'name': 'Getting Started & Setup',
        'reason': 'The desire to get started quickly is common. Removing activation friction is a conversion factor.',
        'coverage': 'Describe the onboarding or setup process briefly. Emphasise ease and speed if relevant.'
    },
    'free trial': {
        'name': 'Free Trial & Demo Options',
        'reason': 'Searchers actively looking for no-commitment ways to evaluate. This is a strong commercial signal.',
        'coverage': 'Prominently feature any free trial, demo, or freemium option. Include clear calls to action.'
    },
    'mobile': {
        'name': 'Mobile & App Access',
        'reason': 'Mobile accessibility is a common evaluation point for modern software and services.',
        'coverage': 'Note mobile app availability, platforms supported, and any mobile-specific features or limitations.'
    },
    'security': {
        'name': 'Security & Compliance',
        'reason': 'Data security and compliance are increasingly important in purchasing decisions.',
        'coverage': 'Describe relevant security practices, certifications, or compliance standards (SOC2, GDPR, etc.) if applicable.'
    },
    'templates': {
        'name': 'Templates & Ready-Made Resources',
        'reason': 'Ready-made templates lower the barrier to getting started and demonstrate practical value.',
        'coverage': 'Showcase available templates, pre-built resources, or examples of what's included.'
    },
    'updates': {
        'name': 'Updates & New Features',
        'reason': 'Active development signals quality and longevity. Searchers want reassurance they\'re choosing something current.',
        'coverage': 'Mention recent updates, new features, or the development roadmap if appropriate.'
    },
    'team': {
        'name': 'Team Collaboration',
        'reason': 'For tools used by groups, team features are often a key evaluation point.',
        'coverage': 'Describe how teams can collaborate, share, and work together on the platform.'
    },
}

def match_theme_from_keyword(kw, theme):
    """Check if a keyword matches a specific theme."""
    theme_lower = theme.lower()
    kw_lower = kw.lower()
    
    theme_words = theme_lower.split()
    
    # Direct substring match
    if theme_lower in kw_lower:
        return True
    
    # Any significant word from theme appears in keyword
    for word in theme_words:
        if len(word) > 3 and word in kw_lower:
            return True
    
    return False

def select_keywords_for_theme(all_keywords, theme, top_n=6):
    """Select the best keywords from the pool that match a theme."""
    matched = []
    for kw in all_keywords:
        if match_theme_from_keyword(kw, theme):
            matched.append(kw)
        elif any(word in kw.lower() for word in theme.split() if len(word) > 4):
            matched.append(kw)
    
    return matched[:top_n]

def main():
    themes_json_raw = sys.argv[1] if len(sys.argv) > 1 else "[]"
    keywords_raw = sys.argv[2] if len(sys.argv) > 2 else ""
    core_kw = sys.argv[3] if len(sys.argv) > 3 else ""
    page_type = sys.argv[4] if len(sys.argv) > 4 else ""
    
    try:
        themes_data = json.loads(themes_json_raw)
    except:
        themes_data = []
    
    all_keywords = [k.strip() for k in keywords_raw.split('\n') if k.strip()]
    
    report_lines = []
    
    for theme_entry in themes_data:
        theme = theme_entry.get('theme', '')
        signals = theme_entry.get('signals', 0)
        pages = theme_entry.get('pages_covering', 0)
        
        # Skip very weak signals
        if signals < 2 and pages < 2:
            continue
        
        # Get guidance
        guidance = THEME_GUIDANCE.get(theme, None)
        
        if guidance:
            theme_name = guidance['name']
            reason = guidance['reason']
            coverage = guidance['coverage']
        else:
            # Dynamic theme — generate generic guidance
            theme_name = theme.replace('_', ' ').title()
            reason = f"This topic appears across multiple ranking competitors ({pages} pages cover it)."
            coverage = f"Cover this topic area as it appears on competitor pages. Ensure alignment with the overall page theme."
        
        # Select matching keywords
        matched_kw = select_keywords_for_theme(all_keywords, theme)
        
        report_lines.append(f"\n{'─'*50}")
        report_lines.append(f"Theme: {theme_name}")
        report_lines.append(f"{'─'*50}")
        report_lines.append(f"  Example keywords:  {', '.join(matched_kw[:6]) if matched_kw else 'None identified yet'}")
        report_lines.append(f"  Why it matters:    {reason}")
        report_lines.append(f"  Coverage guidance: {coverage}")
    
    # If no themes detected, provide default
    if not report_lines:
        report_lines.append(f"\n{'─'*50}")
        report_lines.append("Theme: Core Topic Overview")
        report_lines.append(f"{'─'*50}")
        report_lines.append(f"  Example keywords:  {core_kw}")
        report_lines.append(f"  Why it matters:     This is the primary topic the page must address.")
        report_lines.append(f"  Coverage guidance: Cover the core topic thoroughly, including what it is, who it's for, and why it matters.")
    
    print('\n'.join(report_lines))

if __name__ == '__main__':
    main()
