---
name: internal_link_mapper
description: Map internal links from new content to existing content. Identifies linking opportunities, prevents cannibalisation, and maintains link equity. Outputs link recommendations with anchor text.
---

# Internal Link Mapper

Map internal links from new content to existing site content.

## Overview

This skill:
1. Analyzes new content for keyword themes
2. Searches existing site content for related pages
3. Identifies linking opportunities (3-5 per page)
4. Prevents keyword cannibalisation
5. Suggests optimal anchor text
6. Outputs link recommendations with rationale

## Inputs

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `article_text` | string | ✅ | Full article content |
| `primary_keyword` | string | ✅ | Primary keyword for context |
| `keyword_themes` | array | ✅ | Keyword themes from research |
| `site_url` | string | ✅ | Base URL for internal links |
| `existing_content` | JSON | ❌ | List of existing pages with URLs + keywords |
| `max_links` | integer | ❌ | Maximum links to suggest (default: 5) |

## Outputs

| Output | Format | Description |
|--------|--------|-------------|
| Link Recommendations | Markdown | Suggested links with anchor text |
| Link Recommendations | JSON | Machine-readable link map |
| Cannibalisation Warnings | Markdown | Pages to avoid linking to |

## Process

### Step 1: Extract Article Themes

Parse article to identify:
- H2 headings (topic areas)
- Key phrases (potential anchors)
- Keyword mentions (linking opportunities)

### Step 2: Load Existing Content

If `existing_content` provided:
- Map existing pages by primary keyword
- Identify topical clusters
- Flag potential cannibalisation

If not provided:
- Use site_url + sitemap to discover pages
- Extract keywords from page titles

### Step 3: Match Themes to Existing Pages

For each keyword theme:
1. Search existing content for matches
2. Score relevance (0-1)
3. Filter by relevance threshold (0.6+)
4. Rank by link equity

### Step 4: Prevent Cannibalisation

Flag pages to avoid:
- Pages targeting same primary keyword
- Pages with overlapping keyword themes
- Pages that would confuse search intent

### Step 5: Generate Recommendations

For each link:
- Source anchor text (from article)
- Target URL (existing page)
- Link rationale (why this link)
- Estimated link equity

## Example Usage

```bash
internal_link_mapper --article-text "article.md" --primary-keyword "bad credit car finance" --keyword-themes "['eligibility', 'apply', 'rates']" --site-url "https://choosemycar.com" --max-links 5
```

## Example Output

```markdown
# Internal Link Recommendations

## Primary Links (High Relevance)

### 1. "car finance eligibility"
- **Anchor Text:** "eligibility requirements" (H3 section)
- **Target URL:** https://choosemycar.com/eligibility/car-finance
- **Rationale:** Related topic, high authority page
- **Link Equity:** High (PA 45, 23 internal links pointing to it)

### 2. "car finance calculator"
- **Anchor Text:** "calculate your payments"
- **Target URL:** https://choosemycar.com/calculator
- **Rationale:** Topical relevance, user journey next step
- **Link Equity:** Medium (PA 32, good traffic)

### 3. "guarantor car finance"
- **Anchor Text:** "guarantor options"
- **Target URL:** https://choosemycar.com/guarantor-car-finance
- **Rationale:** Related product page, supports user journey
- **Link Equity:** Medium (PA 28)

## Secondary Links (Contextual)

### 4. "car finance with CCJ"
- **Anchor Text:** "CCJs and defaults"
- **Target URL:** https://choosemycar.com/car-finance-ccj
- **Rationale:** Addresses specific credit situation mentioned
- **Link Equity:** Medium (PA 25)

### 5. "car finance guide"
- **Anchor Text:** "learn more about car finance"
- **Target URL:** https://choosemycar.com/guide
- **Rationale:** Educational resource, supports E-E-A-T
- **Link Equity:** Low (PA 18)

## Cannibalisation Warnings

⚠️ **Do NOT link to:**
- https://choosemycar.com/bad-credit-car-finance (same primary keyword)
- https://choosemycar.com/poor-credit-car-finance (overlapping intent)

These pages target the same keyword and would create keyword cannibalisation.
```

## Constraints

- Maximum 5 internal links per 1000 words
- Do NOT link to pages targeting same keyword
- Do NOT use generic anchor text ("click here", "learn more")
- Do NOT link to low-quality pages
- Prefer deep links over homepage links

## Error Handling

- If existing_content not provided, use sitemap discovery
- If no matches found, return empty recommendations
- If cannibalisation risk high, warn user