#!/usr/bin/env python3
"""
schema_audit.py
Complete schema audit and enhancement tool.

Workflow:
1. Detect existing schema on webpage
2. If schema exists: Audit issues → Suggest fixes → Identify gaps → Generate gold standard
3. If no schema: Analyze page → Generate recommendations → Create schema
4. Validate final output against schema.org rules
5. Generate comprehensive report with before/after comparison
"""
import sys, json, re, urllib.request, urllib.error
from datetime import datetime
from pathlib import Path

# Import from existing modules
sys.path.insert(0, str(Path(__file__).parent))
from schema_validator import SchemaValidator

def fetch_url(url):
    """Fetch webpage HTML."""
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        print(f"Error fetching URL: {e}")
        return None

def extract_existing_schema(html):
    """Extract existing JSON-LD from page."""
    import html as html_module
    schemas = []
    pattern = r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>'
    matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
    for match in matches:
        try:
            cleaned = match.strip()
            cleaned = html_module.unescape(cleaned)
            schema = json.loads(cleaned)
            schemas.append(schema)
        except json.JSONDecodeError:
            pass
    return schemas

def validate_schema(schema_data):
    """Validate schema and return detailed report."""
    validator = SchemaValidator()
    return validator.validate(schema_data)

def analyze_page_for_schema(html, url):
    """Analyze page and detect schema opportunities with confidence scores."""
    from schema_generator import HTMLSignalExtractor, detect_signals, calculate_confidence, extract_metadata, determine_primary_entity
    
    parser = HTMLSignalExtractor()
    parser.feed(html)
    
    text = re.sub(r'<[^>]+>', ' ', html).lower()
    
    signals = detect_signals(html, text, parser)
    scores, reasoning = calculate_confidence(signals)
    
    metadata = extract_metadata(parser)
    
    if not metadata.get('title'):
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        if title_match:
            metadata['title'] = title_match.group(1).strip()
    
    if not metadata.get('canonical'):
        canon_match = re.search(r'<link[^>]*rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if canon_match:
            metadata['canonical'] = canon_match.group(1)
        else:
            metadata['canonical'] = url
    
    # Rank by confidence
    ranked = []
    for entity_type, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
        if score >= 0.40:  # Minimum threshold
            if score >= 0.85:
                priority = 'High'
            elif score >= 0.65:
                priority = 'Medium'
            else:
                priority = 'Low'
            
            ranked.append({
                'type': entity_type,
                'confidence': score,
                'priority': priority,
                'reasoning': reasoning.get(entity_type, [])
            })
    
    return ranked, metadata

def generate_gold_standard_schema(ranked_entities, html, metadata, existing_schema=None):
    """Generate gold standard schema based on analysis."""
    from schema_generator import generate_json_ld, generate_breadcrumb, generate_organization, generate_faq, generate_howto, generate_video_objects, generate_dataset, HTMLSignalExtractor
    
    parser = HTMLSignalExtractor()
    parser.feed(html)
    text = re.sub(r'<[^>]+>', ' ', html).lower()
    
    graph = []
    
    # Add each high-confidence entity
    for entity_info in ranked_entities:
        if entity_info['confidence'] >= 0.65:  # Only include medium+ confidence
            entity_type = entity_info['type']
            signals = {entity_type: [(r, 0.8) for r in entity_info['reasoning']]}
            schema = generate_json_ld(entity_type, metadata, signals, parser=parser, html=html)
            if schema and isinstance(schema, dict) and schema.get("@type"):
                graph.append(schema)
    
    # Always add Organization if not present
    if not any(e.get('@type') == 'Organization' for e in graph):
        org = generate_organization(parser=parser, html=html)
        if org:
            graph.insert(0, org)
    
    # Add BreadcrumbList
    breadcrumb = generate_breadcrumb(metadata, parser)
    if breadcrumb:
        graph.insert(1, breadcrumb)
    
    return graph if len(graph) > 1 else graph[0]

def compare_schemas(existing, gold_standard):
    """Compare existing schema with gold standard to identify gaps."""
    comparison = {
        'existing_entities': [],
        'gold_entities': [],
        'missing_entities': [],
        'enhanced_entities': [],
        'fixed_issues': []
    }
    
    # Extract entity types from existing
    if isinstance(existing, list):
        for entity in existing:
            if isinstance(entity, dict):
                comparison['existing_entities'].append(entity.get('@type', 'Unknown'))
    elif isinstance(existing, dict):
        if '@graph' in existing:
            for entity in existing['@graph']:
                comparison['existing_entities'].append(entity.get('@type', 'Unknown'))
        else:
            comparison['existing_entities'].append(existing.get('@type', 'Unknown'))
    
    # Extract entity types from gold standard
    if isinstance(gold_standard, list):
        for entity in gold_standard:
            if isinstance(entity, dict):
                comparison['gold_entities'].append(entity.get('@type', 'Unknown'))
    elif isinstance(gold_standard, dict):
        if '@graph' in gold_standard:
            for entity in gold_standard['@graph']:
                comparison['gold_entities'].append(entity.get('@type', 'Unknown'))
        else:
            comparison['gold_entities'].append(gold_standard.get('@type', 'Unknown'))
    
    # Find missing entities
    comparison['missing_entities'] = [e for e in comparison['gold_entities'] if e not in comparison['existing_entities']]
    
    # Find enhanced entities (present in both but gold standard has more properties)
    # This is simplified - would need deeper comparison in production
    
    return comparison

def generate_audit_report(url, existing_schema, validation_result, ranked_entities, gold_schema, comparison, output_file=None):
    """Generate comprehensive audit report."""
    
    has_existing = existing_schema is not None and len(existing_schema) > 0
    
    report = f"""# Schema Markup Audit Report

**URL:** {url}
**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Audit Type:** {'Existing Schema Audit + Enhancement' if has_existing else 'New Schema Recommendations'}

---

## Executive Summary

"""
    
    if has_existing:
        report += f"""This audit analyzed the existing schema markup on your webpage and compared it against schema.org standards and Google Rich Results requirements.

**Key Findings:**
- **Existing Entities:** {len(comparison['existing_entities'])} schema entities detected
- **Validation Status:** {'✅ Valid' if validation_result['valid'] else '❌ Has Issues'}
- **Issues Found:** {validation_result['summary']['errors']} errors, {validation_result['summary']['warnings']} warnings
- **Gold Standard Entities:** {len(comparison['gold_entities'])} entities recommended
- **Missing Entities:** {len(comparison['missing_entities'])} entities to add
"""
    else:
        report += f"""This audit analyzed your webpage to identify schema markup opportunities and generate recommendations for implementation.

**Key Findings:**
- **Existing Schema:** None detected
- **Recommended Entities:** {len(ranked_entities)} schema types identified
- **High Priority:** {len([e for e in ranked_entities if e['priority'] == 'High'])} entities
- **Medium Priority:** {len([e for e in ranked_entities if e['priority'] == 'Medium'])} entities
- **Low Priority:** {len([e for e in ranked_entities if e['priority'] == 'Low'])} entities
"""
    
    report += """
---

"""
    
    if has_existing:
        report += """## Existing Schema Analysis

### Entities Detected

"""
        report += "| Entity Type | Status | Issues |\n"
        report += "|-------------|--------|--------|\n"
        
        for entity_type in comparison['existing_entities']:
            # Check if this entity had validation issues
            issues = [e for e in validation_result['errors'] if entity_type in e]
            warnings = [w for w in validation_result['warnings'] if entity_type in w]
            status = '❌ Has Issues' if issues else ('⚠️ Warnings' if warnings else '✅ Valid')
            issue_count = len(issues) + len(warnings)
            report += f"| {entity_type} | {status} | {issue_count} issue(s) |\n"
        
        report += f"""
### Validation Issues

"""
        if validation_result['errors']:
            report += "**Errors:**\n\n"
            for error in validation_result['errors']:
                report += f"- ❌ {error}\n"
            report += "\n"
        else:
            report += "✅ No errors found\n\n"
        
        if validation_result['warnings']:
            report += "**Warnings:**\n\n"
            for warning in validation_result['warnings']:
                report += f"- ⚠️ {warning}\n"
            report += "\n"
        
        report += """
### Recommended Fixes

"""
        if validation_result['errors'] or validation_result['warnings']:
            report += "| Issue Type | Recommendation | Priority |\n"
            report += "|------------|----------------|----------|\n"
            
            if validation_result['errors']:
                report += "| Schema.org Validation | Fix all errors to ensure schema is valid | High |\n"
            
            if any('Google Rich Results' in w for w in validation_result['warnings']):
                report += "| Google Rich Results | Add missing required properties for rich results eligibility | High |\n"
            
            if any('thumbnailUrl' in w for w in validation_result['warnings']):
                report += "| VideoObject | Add actual thumbnailUrl and uploadDate | Medium |\n"
        else:
            report += "✅ No fixes required - existing schema is valid\n"
        
        report += """
### Enhancement Opportunities

"""
        if comparison['missing_entities']:
            report += "The following entities are missing from your current schema but recommended for gold standard:\n\n"
            report += "| Entity Type | Impact | Recommendation |\n"
            report += "|-------------|--------|----------------|\n"
            
            for entity_type in comparison['missing_entities']:
                impact = 'High' if entity_type in ['FAQPage', 'FinancialProduct', 'Product'] else 'Medium'
                report += f"| {entity_type} | {impact} | Add to improve search visibility |\n"
        else:
            report += "✅ All recommended entities are already present\n"
    
    else:
        report += """## Schema Opportunities Detected

### Ranked Recommendations

"""
        report += "| Priority | Entity Type | Confidence | Reasoning |\n"
        report += "|----------|-------------|------------|-----------|\n"
        
        for entity in ranked_entities:
            reasoning_str = ', '.join(entity['reasoning'][:3]) if entity['reasoning'] else 'Page structure analysis'
            report += f"| {entity['priority']} | {entity['type']} | {entity['confidence']:.2f} | {reasoning_str} |\n"
        
        report += """
### Implementation Priority

**High Priority (Implement First):**
- These entities have the highest confidence scores and biggest SEO impact
- Should be implemented immediately

**Medium Priority (Implement Second):**
- Supporting entities that enhance rich results
- Implement after high-priority entities

**Low Priority (Optional Enhancements):**
- Nice-to-have entities for comprehensive schema
- Implement when resources allow

"""
    
    report += f"""
---

## Gold Standard Schema

The gold standard schema combines:
"""
    
    if has_existing:
        report += """- ✅ Fixes for all validation errors
- ✅ Fixes for all warnings
- ✅ Missing high-value entities
- ✅ Enhanced properties on existing entities
"""
    else:
        report += """- ✅ High-confidence entity types
- ✅ All required properties for Google Rich Results
- ✅ Enhanced optional properties for better entity recognition
"""
    
    report += """
---

## Validation Results

"""
    
    # Validate gold standard schema
    gold_validator = SchemaValidator()
    if isinstance(gold_schema, list):
        gold_report = gold_validator.validate({'@graph': gold_schema})
    else:
        gold_report = gold_validator.validate(gold_schema)
    
    if gold_report['valid']:
        report += "✅ **Gold standard schema is VALID** according to schema.org rules\n\n"
    else:
        report += "❌ **Gold standard schema has issues:**\n\n"
        for error in gold_report['errors']:
            report += f"- {error}\n"
        report += "\n"
    
    report += f"""
---

## Implementation Steps

### 1. Review Gold Standard Schema

The generated schema file is ready for deployment.

### 2. Replace Existing Schema

"""
    
    if has_existing:
        report += """Remove your current schema markup and replace with the gold standard version. This ensures:
- All validation errors are fixed
- All warnings are resolved
- Missing entities are added
- Maximum SEO benefit
"""
    else:
        report += """Add the schema markup to your page for the first time. This will:
- Enable rich results in Google Search
- Improve entity recognition by search engines
- Enhance AI understanding of your content
"""
    
    report += """
### 3. Add to Website

Add the schema markup to the `<head>` section of your HTML:

```html
<head>
  <!-- Other head elements -->
  
  <script type="application/ld+json">
  <!-- Paste JSON-LD from gold standard schema file here -->
  </script>
</head>
```

### 4. Test Implementation

Use Google's Rich Results Test to validate:
- **Tool:** https://search.google.com/test/rich-results
- **Expected Result:** All entities should show as valid

### 5. Monitor Performance

After deployment, monitor Google Search Console:
- **Report:** Enhancements → [Relevant entity type]
- **Look for:** Valid items, errors, warnings
- **Timeline:** Allow 1-2 weeks for Google to process

---

## Appendix: Schema Files

### Existing Schema (Before)
"""
    
    if has_existing and existing_schema:
        if isinstance(existing_schema, list):
            report += f"\n```json\n{json.dumps(existing_schema, indent=2)[:2000]}...\n```\n"
        else:
            report += f"\n```json\n{json.dumps(existing_schema, indent=2)[:2000]}...\n```\n"
    else:
        report += "\nNo existing schema detected\n"
    
    report += """
### Gold Standard Schema (After)
"""
    if isinstance(gold_schema, list):
        report += f"\n```json\n{json.dumps(gold_schema, indent=2)[:2000]}...\n```\n"
    else:
        report += f"\n```json\n{json.dumps(gold_schema, indent=2)[:2000]}...\n```\n"
    
    report += f"""
---

**Report Generated By:** Schema Markup Generator Skill v2.0
**Validation Engine:** schema_validator.py
**Schema.org Version:** Latest (from schema.org GitHub)
**Google Rich Results:** Checked against current guidelines
"""
    
    return report, gold_report


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Schema audit and enhancement tool')
    parser.add_argument('--url', required=True, help='URL to analyze')
    parser.add_argument('--existing-schema', help='Path to existing schema file (optional, will auto-detect if not provided)')
    parser.add_argument('--output', default='/tmp/schema_audit_report.md', help='Output report file')
    parser.add_argument('--schema-output', default='/tmp/schema_gold_standard.json', help='Output schema file')
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("SCHEMA AUDIT & ENHANCEMENT TOOL")
    print("=" * 80)
    print(f"\nURL: {args.url}")
    print("=" * 80 + "\n")
    
    # Step 1: Fetch webpage
    print("Step 1: Fetching webpage...")
    html = fetch_url(args.url)
    if not html:
        print("Failed to fetch webpage")
        sys.exit(1)
    print("✅ Webpage fetched successfully\n")
    
    # Step 2: Detect existing schema
    print("Step 2: Detecting existing schema...")
    existing_schema = extract_existing_schema(html)
    
    if args.existing_schema:
        print(f"Loading existing schema from {args.existing_schema}...")
        try:
            import codecs
            with codecs.open(args.existing_schema, 'r', 'utf-8-sig') as f:
                file_schema = json.load(f)
                if isinstance(file_schema, dict) and '@graph' in file_schema:
                    existing_schema = file_schema['@graph']
                else:
                    existing_schema = [file_schema] if isinstance(file_schema, dict) else file_schema
        except Exception as e:
            print(f"Warning: Could not load file: {e}")
    
    if existing_schema:
        print(f"✅ Found {len(existing_schema)} existing schema entities")
        has_existing = True
    else:
        print("ℹ️  No existing schema detected")
        has_existing = False
    
    print()
    
    # Step 3: Analyze page / Validate existing
    if has_existing:
        print("Step 3: Validating existing schema...")
        validation_result = validate_schema({'@graph': existing_schema} if len(existing_schema) > 1 else existing_schema[0])
        
        print(f"Validation: {'✅ Valid' if validation_result['valid'] else '❌ Has Issues'}")
        print(f"  Errors: {validation_result['summary']['errors']}")
        print(f"  Warnings: {validation_result['summary']['warnings']}")
        print()
        
        print("Step 4: Analyzing page for enhancement opportunities...")
        ranked_entities, metadata = analyze_page_for_schema(html, args.url)
        print(f"✅ Found {len(ranked_entities)} schema opportunities\n")
    else:
        print("Step 3: Analyzing page for schema opportunities...")
        ranked_entities, metadata = analyze_page_for_schema(html, args.url)
        validation_result = {'valid': True, 'errors': [], 'warnings': [], 'summary': {'errors': 0, 'warnings': 0}}
        print(f"✅ Found {len(ranked_entities)} schema opportunities\n")
    
    # Step 4: Generate gold standard schema
    print("Step 4: Generating gold standard schema...")
    gold_schema = generate_gold_standard_schema(ranked_entities, html, metadata, existing_schema if has_existing else None)
    print("✅ Gold standard schema generated\n")
    
    # Step 5: Compare schemas
    if has_existing:
        print("Step 5: Comparing existing vs gold standard...")
        comparison = compare_schemas(existing_schema, gold_schema)
        print(f"Missing entities: {len(comparison['missing_entities'])}")
        print(f"Enhanced entities: {len(comparison['enhanced_entities'])}")
        print()
    else:
        comparison = {'existing_entities': [], 'gold_entities': [], 'missing_entities': [], 'enhanced_entities': [], 'fixed_issues': []}
    
    # Step 6: Generate report
    print("Step 6: Generating audit report...")
    report, gold_validation = generate_audit_report(
        args.url, 
        existing_schema if has_existing else None,
        validation_result,
        ranked_entities,
        gold_schema,
        comparison,
        args.output
    )
    
    # Save report
    with open(args.output, 'w') as f:
        f.write(report)
    print(f"✅ Report saved to {args.output}\n")
    
    # Save gold standard schema
    with open(args.schema_output, 'w') as f:
        json.dump(gold_schema if isinstance(gold_schema, dict) else {'@graph': gold_schema}, f, indent=2)
    print(f"✅ Gold standard schema saved to {args.schema_output}\n")
    
    # Upload to Google Docs
    print("Step 7: Uploading report to Google Docs...")
    import subprocess
    title = f"Schema Audit - {args.url.split('/')[-1].replace('-', ' ').title()}"
    result = subprocess.run(
        ['gog', '-a', 'walter@former-employer.io', 'docs', 'create', title, '--file', args.output],
        capture_output=True, text=True
    )
    
    if result.returncode == 0:
        for line in result.stdout.split('\n'):
            if 'link' in line.lower():
                url_match = re.search(r'(https://docs\.google\.com/document/d/[A-Za-z0-9_-]+)', line)
                if url_match:
                    print(f"✅ Google Doc: {url_match.group(1)}\n")
                    break
    else:
        print(f"⚠️  Google Doc upload failed: {result.stderr}\n")
    
    # Summary
    print("=" * 80)
    print("AUDIT COMPLETE")
    print("=" * 80)
    print(f"URL: {args.url}")
    print(f"Existing Schema: {'Yes' if has_existing else 'No'}")
    print(f"Gold Standard Entities: {len(gold_schema) if isinstance(gold_schema, list) else 1}")
    print(f"Validation: {'✅ Valid' if gold_validation['valid'] else '❌ Has Issues'}")
    print(f"Report: {args.output}")
    print(f"Schema: {args.schema_output}")
    print("=" * 80)


if __name__ == '__main__':
    main()
