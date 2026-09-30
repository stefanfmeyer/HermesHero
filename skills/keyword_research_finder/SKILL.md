# Keyword Research Finder

Identify the full keyword opportunity for a landing page — combining existing coverage, competitor themes, DataForSEO expansion, and search intent signals.

## Overview

This skill produces a practical keyword set for building high-quality SEO landing pages. It prioritises **relevance and search intent** over raw keyword volume. The output identifies what topics a page must cover to compete in search results.

**Key feature:** Accepts competing URLs to avoid keyword cannibalisation with existing pages on your site.

## When to Use

- Creating a new landing page
- Rewriting an existing landing page
- Expanding keyword coverage for an existing page
- Consolidating multiple pages into one stronger page
- Improving keyword targeting for commercial search queries

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| `--primary` | No* | Primary keyword (e.g. "CRM software") |
| `--url` | No* | URL of the page to analyse |
| `--country` | Yes | Country code (e.g. "United Kingdom", "United States") |
| `--competing-urls` | **Recommended** | Comma-separated list of URLs that already target similar keywords (to avoid cannibalisation) |
| `--competing-file` | No | Path to file with competing URLs (one per line) |
| `--page-type` | No | Page type hint (e.g. "product", "pricing", "comparison") |
| `--existing` | No | Path to file with existing keyword list (one per line) |
| `--gsc` | No | Path to Search Console CSV export |
| `--modifiers` | No | Comma-separated additional modifiers (optional) |

*At least one of `--primary` or `--url` is required.

## Usage

```bash
# Basic usage with competing URLs (recommended)
keyword_finder --url "https://example.com/crm" --country "United Kingdom" \
  --competing-urls "https://example.com/crm/pricing,https://example.com/crm/features"

# With primary keyword and competing URLs
keyword_finder --primary "CRM software" --country "United Kingdom" \
  --competing-urls "https://example.com/crm/free-trial,https://example.com/crm/enterprise"

# With competing URLs from file
keyword_finder --url "https://example.com/pm-tool" --country "United Kingdom" \
  --competing-file ~/urls/existing_pages.txt

# Full example with all options
keyword_finder \
  --primary "project management software" \
  --url "https://example.com/pm-tool" \
  --country "United Kingdom" \
  --competing-urls "https://example.com/pm-tool/free,https://example.com/pm-tool/enterprise" \
  --existing ~/keywords/existing.txt \
  --page-type "product" \
  --modifiers "enterprise,team,free"
```

## Why Competing URLs Matter

When the skill suggests keywords that are already targeted by other pages on your site, you risk **keyword cannibalisation** — multiple pages competing for the same search terms.

By providing `--competing-urls` or `--competing-file`, the skill will:
1. Analyse each competing URL to extract targeted keywords
2. Filter out suggested keywords that would cannibalise existing pages
3. Flag any remaining overlaps in the output

**Example:** If you're researching `bad-credit-car-finance` and provide:
```
--competing-urls "https://choosemycar.com/bad-credit-car-finance/ccj,https://choosemycar.com/bad-credit-car-finance/iva"
```
The skill will exclude keywords like "car finance with ccj" or "iva car finance" from recommendations.

## Output Format

The skill returns structured output:

```
============================================
KEYWORD RESEARCH FINDER — Landing Page Keyword Opportunity
============================================

PRIMARY KEYWORD IDENTIFIED:
[primary keyword]

SECONDARY KEYWORDS:
[keyword 1]
[keyword 2]
...

SUPPORTING KEYWORD VARIATIONS:
[keyword 1]
[keyword 2]
...

QUESTION-BASED KEYWORDS:
[keyword 1]
[keyword 2]
...

--------------------------------------------
KEYWORD THEMES
--------------------------------------------

[Theme 1]
  Example keywords:   [list]
  Why it matters:     [explanation]
  Coverage guidance:  [what to cover on the page]

[Theme 2]
  ...

--------------------------------------------
POTENTIAL FAQ OPPORTUNITIES
--------------------------------------------
- [question 1]
- [question 2]
...

--------------------------------------------
KEYWORDS TO AVOID TARGETING
--------------------------------------------
- [keyword] — [reason]
...

--------------------------------------------
DATA SOURCES USED
--------------------------------------------
- DataForSEO SERP (top 20 URLs analysed)
- DataForSEO keyword variations
- DataForSEO keyword suggestions
- DataForSEO related keywords
- Existing keyword signals [included/excluded]
```

## Quality Standards

- Keywords are closely aligned with the page topic
- Commercially relevant keywords are prioritised
- Themes reflect real SERP patterns from competitors
- Themes are practical and not overly granular
- Keyword lists are not inflated unnecessarily
- Output supports landing page creation, not blog ideation
