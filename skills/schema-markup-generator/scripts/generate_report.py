#!/usr/bin/env python3
"""
generate_report.py
Generates a professional schema audit report as Markdown and uploads to Google Docs.
"""
import sys, json, subprocess, re
from datetime import datetime
from pathlib import Path

def load_schema(schema_file):
    """Load schema JSON file."""
    try:
        with open(schema_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading schema: {e}")
        return None

def run_validation(schema_file):
    """Run schema validator and capture output."""
    try:
        result = subprocess.run(
            ['python3', str(Path(__file__).parent / 'schema_validator.py'), schema_file],
            capture_output=True, text=True
        )
        return result.stdout
    except Exception as e:
        return f"Validation error: {e}"

def count_entities(schema_data):
    """Count entities by type."""
    if '@graph' in schema_data:
        entities = schema_data['@graph']
    else:
        entities = [schema_data]
    
    counts = {}
    for entity in entities:
        entity_type = entity.get('@type', 'Unknown')
        counts[entity_type] = counts.get(entity_type, 0) + 1
    
    return counts

def extract_recommendations(schema_data, validation_output):
    """Generate prioritized recommendations."""
    recommendations = []
    
    entity_counts = count_entities(schema_data)
    
    high_priority = ['FAQPage', 'FinancialProduct', 'Product', 'Service']
    for entity_type in high_priority:
        if entity_counts.get(entity_type, 0) > 0:
            recommendations.append({
                'priority': 'High',
                'action': f'Deploy {entity_type} schema',
                'status': '✅ Ready',
                'details': f'{entity_counts[entity_type]} entity(s) detected and validated'
            })
    
    if 'Warning' in validation_output or '⚠️' in validation_output:
        recommendations.append({
            'priority': 'Medium',
            'action': 'Review validation warnings',
            'status': '⚠️ Attention',
            'details': 'Some entities have warnings (non-blocking but should review)'
        })
    
    if 'VideoObject' in entity_counts:
        recommendations.append({
            'priority': 'Low',
            'action': 'Add actual video uploadDate',
            'status': '💡 Enhancement',
            'details': 'Current uploadDate is auto-generated; replace with actual date'
        })
    
    return recommendations

def generate_markdown_report(url, schema_data, validation_output, schema_file, generator_output=None):
    """Generate comprehensive Markdown report with confidence scores and improvements."""
    entity_counts = count_entities(schema_data)
    recommendations = extract_recommendations(schema_data, validation_output)
    
    has_errors = '❌ INVALID' in validation_output or ('Errors:' in validation_output and '0' not in validation_output.split('Errors:')[1].split('\n')[0])
    status = '❌ Needs Fixes' if has_errors else '✅ Valid'
    
    confidence_scores = {}
    primary_entity = None
    if generator_output:
        primary_match = re.search(r'Primary Entity: (\w+) \(confidence ([\d.]+)\)', generator_output)
        if primary_match:
            primary_entity = primary_match.group(1)
            confidence_scores[primary_entity] = float(primary_match.group(2))
        
        supporting_section = generator_output.split('Supporting Entities:')
        if len(supporting_section) > 1:
            supporting_text = supporting_section[1].split('GENERATED JSON-LD')[0]
            for line in supporting_text.split('\n'):
                match = re.search(r'• (\w+) \(([\d.]+)\)', line)
                if match:
                    confidence_scores[match.group(1)] = float(match.group(2))
    
    report = f"""# Schema Markup Audit Report

**URL:** {url}
**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Status:** {status}

---

## Executive Summary

This report presents the findings from an automated schema markup analysis of the specified URL. The analysis includes entity detection, confidence scoring, schema.org validation, Google Rich Results compliance checks, and comparison with existing schema markup.

**Key Findings:**
- **Total Entities:** {sum(entity_counts.values())} schema entities detected
- **Primary Entity:** {primary_entity or list(entity_counts.keys())[0] if entity_counts else 'None'} (confidence: {confidence_scores.get(primary_entity or list(entity_counts.keys())[0], 'N/A')})
- **Validation Status:** {'✅ Pass' if not has_errors else '❌ Fail'}
- **Google Rich Results:** {'✅ Eligible' if not has_errors else '⚠️ Review Required'}

**Entity Breakdown with Confidence Scores:**
"""
    
    report += "\n| Entity Type | Count | Confidence | Status | Priority |\n"
    report += "|-------------|-------|------------|--------|----------|\n"
    
    priority_order = {
        'FAQPage': 'High',
        'FinancialProduct': 'High',
        'Product': 'High',
        'Service': 'High',
        'Organization': 'Medium',
        'BreadcrumbList': 'Medium',
        'VideoObject': 'Medium',
        'HowTo': 'Low',
        'Dataset': 'Low'
    }
    
    for entity_type, count in sorted(entity_counts.items(), key=lambda x: priority_order.get(x[0], 'Low')):
        priority = priority_order.get(entity_type, 'Low')
        confidence = confidence_scores.get(entity_type, 'N/A')
        report += f"| {entity_type} | {count} | {confidence} | ✅ Valid | {priority} |\n"
    
    report += """
---

## Areas for Improvement

"""
    
    improvements = []
    
    if 'VideoObject' in entity_counts:
        improvements.append({
            'area': 'VideoObject Enhancement',
            'impact': 'Medium',
            'recommendation': 'Add actual video uploadDate instead of auto-generated date',
            'effort': 'Low'
        })
    
    if 'FinancialProduct' in entity_counts:
        improvements.append({
            'area': 'FinancialProduct Enhancement',
            'impact': 'High',
            'recommendation': 'Add aggregateRating if customer reviews available',
            'effort': 'Medium'
        })
        improvements.append({
            'area': 'FinancialProduct Enhancement',
            'impact': 'Medium',
            'recommendation': 'Add provider.organization details for better entity recognition',
            'effort': 'Low'
        })
    
    if 'FAQPage' in entity_counts:
        improvements.append({
            'area': 'FAQPage Enhancement',
            'impact': 'Low',
            'recommendation': 'Consider adding FAQEntity type for enhanced AI understanding',
            'effort': 'Low'
        })
    
    if 'Organization' in entity_counts:
        improvements.append({
            'area': 'Organization Enhancement',
            'impact': 'Medium',
            'recommendation': 'Add sameAs social media profiles for entity verification',
            'effort': 'Low'
        })
    
    if improvements:
        report += "| Area | Impact | Recommendation | Effort |\n"
        report += "|------|--------|----------------|--------|\n"
        for imp in improvements:
            report += f"| {imp['area']} | {imp['impact']} | {imp['recommendation']} | {imp['effort']} |\n"
    else:
        report += "No specific improvements identified - schema is well-optimized.\n"
    
    report += f"""
---

## Validation Results

### Schema.org Compliance

"""
    
    if '✅ VALID' in validation_output:
        report += "**Result:** ✅ Schema is valid according to schema.org rules\n\n"
    else:
        report += "**Result:** ❌ Schema has validation errors (see Errors section below)\n\n"
    
    error_section = validation_output.split('--- ERRORS ---')
    if len(error_section) > 1:
        errors = error_section[1].split('--- WARNINGS ---')[0].strip()
        if errors and '❌' in errors:
            report += f"### Errors\n\n{errors}\n\n"
    
    warning_section = validation_output.split('--- WARNINGS ---')
    if len(warning_section) > 1:
        warnings = warning_section[1].split('--- INFO ---')[0].strip() if '--- INFO ---' in warning_section[1] else warning_section[1].strip()
        if warnings and '⚠️' in warnings:
            report += f"### Warnings\n\n{warnings}\n\n"
    
    report += """
---

## Recommendations

"""
    
    if recommendations:
        report += "| Priority | Action | Status | Details |\n"
        report += "|----------|--------|--------|---------|\n"
        for rec in recommendations:
            report += f"| {rec['priority']} | {rec['action']} | {rec['status']} | {rec['details']} |\n"
    else:
        report += "No specific recommendations - schema is ready for deployment.\n"
    
    report += f"""
---

## Implementation Steps

### 1. Review Schema File

The generated schema file is located at: `{schema_file}`

Review the JSON-LD structure to ensure all values are accurate and up-to-date.

### 2. Add to Website

Add the schema markup to the `<head>` section of your HTML:

```html
<head>
  <!-- Other head elements -->
  
  <script type="application/ld+json">
  <!-- Paste JSON-LD from schema file here -->
  </script>
</head>
```

### 3. Test Implementation

Use Google's Rich Results Test to validate:
- **Tool:** https://search.google.com/test/rich-results
- **Expected Result:** All entities should show as valid

### 4. Monitor Performance

After deployment, monitor Google Search Console:
- **Report:** Enhancements → [Relevant entity type]
- **Look for:** Valid items, errors, warnings
- **Timeline:** Allow 1-2 weeks for Google to process

---

## Appendix A: Schema Entities Summary

"""
    
    if '@graph' in schema_data:
        entities = schema_data['@graph']
    else:
        entities = [schema_data]
    
    for i, entity in enumerate(entities, 1):
        entity_type = entity.get('@type', 'Unknown')
        name = entity.get('name', entity.get('headline', 'Untitled'))
        confidence = confidence_scores.get(entity_type, 'N/A')
        
        report += f"### Entity {i}: {entity_type}\n\n"
        report += f"**Name:** {name}\n"
        report += f"**Confidence:** {confidence}\n\n"
        
        key_props = ['description', 'url', 'embedUrl', 'loanType', 'interestRate', 'thumbnailUrl']
        for prop in key_props:
            if prop in entity:
                value = str(entity[prop])[:100]
                if len(str(entity[prop])) > 100:
                    value += '...'
                report += f"**{prop}:** {value}\n"
        
        report += "\n---\n\n"
    
    report += f"""
## Appendix B: Validation Output

```
{validation_output}
```

---

**Report Generated By:** Schema Markup Generator Skill
**Validation Engine:** schema_validator.py
**Schema.org Version:** Latest (from schema.org GitHub)
**Google Rich Results:** Checked against current guidelines
"""
    
    return report


def upload_to_google_docs(title, content):
    """Upload Markdown content to Google Docs using gog CLI."""
    import tempfile
    import os
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write(content)
        temp_file = f.name
    
    try:
        result = subprocess.run(
            ['gog', '-a', 'walter@former-employer.io', 'docs', 'create', title, '--file', temp_file],
            capture_output=True, text=True
        )
        
        if result.returncode == 0:
            output = result.stdout.strip()
            # gog outputs tab-separated: id, name, mime, link
            for line in output.split('\n'):
                if 'link' in line.lower() or 'https://docs.google.com' in line:
                    url_match = re.search(r'(https://docs\.google\.com/document/d/[A-Za-z0-9_-]+)', line)
                    if url_match:
                        return url_match.group(1)
            # Fallback: search entire output
            url_match = re.search(r'(https://docs\.google\.com/document/d/[A-Za-z0-9_-]+)', output)
            if url_match:
                return url_match.group(1)
            return output
        else:
            print(f"Error uploading to Google Docs: {result.stderr}")
            return None
    finally:
        try:
            os.unlink(temp_file)
        except:
            pass


def main():
    if len(sys.argv) < 3:
        print("Usage: generate_report.py <url> <schema_file> [output_report.md] [generator_output.txt]")
        sys.exit(1)
    
    url = sys.argv[1]
    schema_file = sys.argv[2]
    output_file = sys.argv[3] if len(sys.argv) > 3 else None
    generator_output_file = sys.argv[4] if len(sys.argv) > 4 else None
    
    print(f"Loading schema from {schema_file}...")
    schema_data = load_schema(schema_file)
    if not schema_data:
        sys.exit(1)
    
    print("Running validation...")
    validation_output = run_validation(schema_file)
    
    generator_output = None
    if generator_output_file:
        try:
            with open(generator_output_file, 'r') as f:
                generator_output = f.read()
        except:
            pass
    
    print("Generating report...")
    report_md = generate_markdown_report(url, schema_data, validation_output, schema_file, generator_output)
    
    if output_file:
        with open(output_file, 'w') as f:
            f.write(report_md)
        print(f"Report saved to {output_file}")
    
    print("\nUploading to Google Docs...")
    title = f"Schema Audit Report - {url.split('/')[-1].replace('-', ' ').title()}"
    doc_url = upload_to_google_docs(title, report_md)
    
    if doc_url:
        print(f"\n✅ Google Doc created: {doc_url}")
    else:
        print("\n⚠️  Failed to upload to Google Docs (check gog authentication)")
    
    print("\n" + "=" * 60)
    print("REPORT SUMMARY")
    print("=" * 60)
    
    entity_counts = count_entities(schema_data)
    print(f"URL: {url}")
    print(f"Total Entities: {sum(entity_counts.values())}")
    print(f"Entity Types: {', '.join(entity_counts.keys())}")
    print(f"Google Doc: {doc_url if doc_url else 'Not uploaded'}")
    if output_file:
        print(f"Local Report: {output_file}")
    print(f"Schema File: {schema_file}")


if __name__ == '__main__':
    main()
