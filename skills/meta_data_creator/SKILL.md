---
name: meta_data_creator
description: Generate SEO-optimised meta titles and descriptions for pages. Creates compelling titles (50-60 chars) and descriptions (150-160 chars) that improve CTR and search visibility.
---

# Meta Data Creator

Generate SEO-optimised meta titles and descriptions.

## Overview

This skill:
1. Takes primary keyword and article/page context
2. Generates meta titles (50-60 characters)
3. Generates meta descriptions (150-160 characters)
4. Optimises for CTR (click-through rate)
5. Includes brand voice elements
6. Outputs implementation-ready meta tags

## Inputs

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `primary_keyword` | string | ✅ | Primary keyword for SEO |
| `page_title` | string | ✅ | H1/title of the page |
| `page_summary` | string | ❌ | Brief page summary or intro |
| `brand_id` | string | ✅ | Brand identifier |
| `page_type` | string | ❌ | "blog", "landing_page", "service" |
| `cta_text` | string | ❌ | Call-to-action for description |

## Outputs

| Output | Format | Description |
|--------|--------|-------------|
| Meta Title | string | 50-60 character title |
| Meta Description | string | 150-160 character description |
| Open Graph Title | string | Social sharing title |
| Open Graph Description | string | Social sharing description |
| Twitter Card Copy | string | Twitter-optimised text |

## Character Limits

| Element | Min | Max | Ideal |
|---------|-----|-----|-------|
| Meta Title | 40 | 60 | 55 |
| Meta Description | 120 | 160 | 155 |
| OG Title | 40 | 60 | 55 |
| OG Description | 60 | 150 | 125 |

## Process

### Step 1: Load Brand Context

If `brand_id` provided:
1. Load brand voice and tone
2. Load formatting rules
3. Apply brand personality to copy

### Step 2: Generate Meta Title

Title formula:
```
[Primary Keyword] | [Benefit] [Brand] — when keyword is brandable
[Primary Keyword] — [Secondary Keyword] [Year] — for informational
[How to/What is/etc.] [Primary Keyword] — for guides
```

Title rules:
- Primary keyword as close to front as possible
- No truncation (watch character count)
- Include brand name only if brandable
- Year included for news/seasonal content

### Step 3: Generate Meta Description

Description formula:
```
[Hook/Solution] + [Key benefit] + [Social proof/Urgency] + [CTA]
```

Description rules:
- Primary keyword in first 80 characters
- Action-oriented (verbs work)
- Create urgency or curiosity
- End with implied CTA
- No duplication of title

### Step 4: Generate Social Meta

Open Graph:
- Title: Can differ from meta title (more brand voice)
- Description: More conversational than meta description

Twitter Card:
- Match OG tags
- Consider character limits for tweets

## Example Output

```markdown
# Meta Data — Bad Credit Car Finance

## Meta Title (55 characters)
Bad Credit Car Finance | Get Approved Today | ChooseMyCar

## Meta Description (152 characters)
Struggling with bad credit? Get car finance approved with lenders who work for you. No credit impact check, FCA authorised, 89% approval rate. Apply now.

## Open Graph
**OG Title:** Bad Credit Car Finance — Get Approved Today
**OG Description:** Stop letting bad credit hold you back. We work with specialist lenders to get you behind the wheel. No credit impact check.

## Twitter Card
**Card Copy:** Bad credit? No problem. Car finance designed for people like you. FCA authorised, 89% approval rate. Get your free quote in 2 minutes.

---

**Word Count:** Title: 55 chars | Description: 152 chars ✓

**Primary keyword density:** "bad credit car finance" appears 2x

**CTR optimisation:** Numbers, urgency ("now"), specificity ("89%")
```

## Constraints

- Do NOT exceed character limits
- Do NOT duplicate title in description
- Do NOT use clickbait or misleading claims
- Do NOT use special characters (emojis, excessive pipes)
- Do NOT keyword stuff
- Primary keyword must appear in first 80 chars of description

## Error Handling

- If brand_id not found, use professional tone
- If cta_text not provided, use generic "Learn more"
- If page_summary not provided, generate from page_title only
- If title exceeds 60 chars, truncate with "..." and adjust