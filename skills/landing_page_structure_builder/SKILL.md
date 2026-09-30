---
name: landing_page_structure_builder
description: Build complete landing page structures from keyword research and SERP analysis. Generates H1/H2/H3 hierarchy, word count allocation, and format guidance for each section. Optimised for conversion-focused landing pages.
---

# Landing Page Structure Builder

Build complete landing page structures from keyword research for conversion-focused pages.

## Overview

This skill:
1. Takes keyword research output and SERP analysis
2. Builds H1/H2/H3 hierarchy optimised for conversion
3. Allocates word count to each section
4. Assigns format types (paragraph, bullets, comparison table, CTA)
5. Outputs complete page structure for content writing

## Inputs

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `keyword_research_output` | JSON | ✅ | Output from keyword_research_finder |
| `serp_analysis_output` | JSON | ❌ | Output from serp_top20_analyser (optional) |
| `brand_id` | string | ✅ | Brand identifier for voice/tone |
| `page_type` | string | ✅ | "service", "product", "location", "comparison" |
| `conversion_goal` | string | ✅ | "lead", "sale", "call", "form" |
| `word_count_range` | string | ❌ | Target word count (e.g., "1500-2500") |

## Outputs

| Output | Format | Destination |
|--------|--------|-------------|
| Page Structure | Markdown | Stage 3 (Content Writer) |
| Page Structure | Google Doc | Review/approval |
| Structure JSON | JSON | Metadata for tracking |

## Process

### Step 1: Parse Keyword Research

Extract from keyword_research_finder output:
- Primary keyword → H1 + URL slug
- Secondary keywords → H2 candidates
- Supporting keywords → H3 candidates
- Keyword themes → Section groupings

### Step 2: Load Brand Context

If `brand_id` provided:
1. Load Brand Guidelines (voice, tone, USP)
2. Load Writing Style Guide (formatting rules)
3. Load Services.md (for service pages)
4. Apply brand voice to section guidance

### Step 3: Build H2 Structure

For landing pages, order:
1. **Hero/Hook** — Value proposition, clear H1
2. **Problem/Pain** — Address pain points early
3. **Solution/Service** — Core offering
4. **Benefits** — Why choose us (bullets/table)
5. **Features/Details** — Deep dive content
6. **Social Proof** — Testimonials, case studies
7. **FAQ** — Address objections
8. **CTA** — Clear next action

### Step 4: Allocate Word Count

Landing page word allocation:
- Hero/Hook: 10-15% (200-300 words)
- Problem/Pain: 15-20% (250-400 words)
- Solution/Service: 20-25% (350-500 words)
- Benefits: 10-15% (200-300 words)
- Features: 15-20% (250-400 words)
- Social Proof: 5-10% (100-200 words)
- FAQ: 10-15% (200-300 words)
- CTA: 5% (100-150 words)

### Step 5: Assign Formats

| Section | Preferred Formats |
|---------|-------------------|
| Hero/Hook | Paragraph, short list |
| Problem/Pain | Paragraph, bullets |
| Solution/Service | Paragraph, table |
| Benefits | Bullets, comparison table |
| Features | Paragraph, table |
| Social Proof | Testimonial cards, case study summary |
| FAQ | Accordion, Q&A list |
| CTA | Button + short paragraph |

## Example Output

```markdown
# Landing Page Structure — Bad Credit Car Finance

**Target URL:** https://choosemycar.com/bad-credit-car-finance
**Page Type:** Service
**Conversion Goal:** Form submission
**Total Word Count:** 2000 words

## H1: Bad Credit Car Finance
**Word Count:** 250 words
**Format:** Paragraph + bullet list
**Keywords:** bad credit car finance, car finance with bad credit

### H2: What is Bad Credit Car Finance?
**Word Count:** 300 words
**Format:** Short definition + paragraph
**Keywords:** bad credit car finance explained

### H2: Can You Get Car Finance with Bad Credit?
**Word Count:** 200 words
**Format:** Paragraph + key points
**Keywords:** car finance with bad credit

### H2: Eligibility Requirements
**Word Count:** 400 words
**Format:** Checklist
**Keywords:** eligibility, requirements, criteria

#### H3: Minimum Income
**Word Count:** 100 words
**Format:** Bullet list

#### H3: Credit Situations Accepted
**Word Count:** 150 words
**Format:** Bullet list

### H2: How to Apply
**Word Count:** 300 words
**Format:** Numbered steps
**Keywords:** apply, application process

### H2: Why Choose Us
**Word Count:** 250 words
**Format:** Comparison table + bullets
**Keywords:** benefits, why choose

### H2: Customer Reviews
**Word Count:** 150 words
**Format:** Testimonial cards
**Keywords:** reviews, testimonials

### H2: Frequently Asked Questions
**Word Count:** 150 words
**Format:** Accordion
**Keywords:** FAQ, questions

### H2: Get Your Free Quote
**Word Count:** 100 words
**Format:** CTA button + paragraph
**Keywords:** quote, apply now

---
**Word Count Summary:** 2000 words
**Conversion Focus:** Form submission above fold, repeated CTAs
```

## Constraints

- Do NOT generate full article content — only structure
- Do NOT include FAQ questions — handled by faq_creator
- Landing pages must have clear CTAs in top 25% of content
- H1 must contain primary keyword
- Word count must not exceed 3000 words for landing pages

## Error Handling

- If brand_id not found, use generic landing page structure
- If serp_analysis not provided, use default structure
- If word_count_range not specified, default to 1500-2500