---
name: meta-generator
description: Extracts and generates SEO meta title and meta description from a complete article. Uses the article's H1, headings, and content to identify the primary keyword and generate optimised metadata. Input is the full article text (combined from Stage 3 article + Stage 4 FAQ + Stage 5 internal links). Output as Markdown + Google Doc. Use when you need to generate meta data for a completed article. For generating meta from a keyword alone (without article), use seo-keyword-research skill.
---

# Meta Generator

Extract primary keyword from article and generate optimised SEO meta title and description.

## Inputs

```json
{
  "article_text": "string (required — full article content)",
  "brand_name": "string (optional — defaults to page's meta publisher if not provided)",
  "cta_text": "string (optional — custom CTA ending for meta description, e.g. 'Learn more', 'Get started')"
}
```

### Input Rules

- **article_text is required** — full article content including headings and body
- Extracts primary keyword from H1, title context, and content themes
- Does NOT accept keyword alone — use seo-keyword-research for keyword-based meta generation

## Process

### Step 1 — Extract Primary Keyword

From the article, identify the primary keyword:
1. Check H1 (usually contains primary keyword)
2. Check first paragraph for keyword context
3. Note recurring themes and key phrases
4. Confirm keyword reflects page purpose

### Step 2 — Extract Secondary Keywords

From the article:
1. H2 headings often contain secondary keywords
2. First mention of key topics in each section
3. Note any repeated phrases that signal important topics

### Step 3 — Generate Meta Title

Create a title that:
- Includes primary keyword naturally
- Reads clearly and naturally
- Accurately represents page content
- Matches brand title format

**Length guidance:**
- ✅ Ideal: 50–60 characters
- ⚠️ Maximum: 60 characters
- **Format:** `[title] | [brand name]` — separated by vertical pipe only

### Step 4 — Generate Meta Description

Write a description that:
- Accurately summarises the article
- Aligns with search intent
- Includes primary keyword naturally
- Encourages clicks naturally
- Ends with a CTA

**CTA rules:**
- If `cta_text` provided, use that
- If not provided, use brand-appropriate CTA: "Learn more", "Read more", "Get started"
- CTA should feel natural, not forced

**Length guidance:**
- ✅ Ideal: 140–155 characters
- ⚠️ Maximum: 160 characters

## Output Format

```
Primary keyword identified: [keyword]

Meta Title: [title]
Character count: [N]

Meta Description: [description]
Character count: [N]

Quality Checks:
[N] Primary keyword appears in title
[N] Title within 50–60 characters (max 60)
[N] Title format: [title] | [brand]
[N] Primary keyword appears in description
[N] Description within 140–155 characters (max 160)
[N] Description ends with CTA
[N] Description accurately reflects article
[N] Wording is clear and natural
```

## QA Checks

- [ ] Primary keyword appears naturally in title
- [ ] Title length 50–60 characters (max 60)
- [ ] Title format: `[title] | [brand]` (pipe-separated)
- [ ] Primary keyword appears naturally in description
- [ ] Description length 140–155 characters (max 160)
- [ ] Description ends with a CTA
- [ ] Description accurately reflects the article
- [ ] Wording is clear, natural, non-spam
- [ ] No exaggerated or misleading claims

## Avoid

- Keyword stuffing
- Generic phrases: "best ever", "ultimate guide", "number one"
- Misleading wording that overpromises
- Meta descriptions without CTA
- Descriptions that don't match article content

## Example

**Input:**
```json
{
  "article_text": "# What is Bad Credit Car Finance\n\nBad credit car finance is a specialised...",
  "brand_name": "ExampleBrand",
  "cta_text": "Explore now"
}
```

**Output:**
```
Primary keyword identified: bad credit car finance

Meta Title: What is Bad Credit Car Finance | ExampleBrand
Character count: 47

Meta Description: Learn what bad credit car finance is, how it works, and your eligibility options. Get matched to specialist lenders even with poor credit. Explore now
Character count: 152

Quality Checks:
[✓] Primary keyword appears in title
[✓] Title within 50–60 characters (max 60)
[✓] Title format: What is Bad Credit Car Finance | ExampleBrand
[✓] Primary keyword appears in description
[✓] Description within 140–155 characters (max 160)
[✓] Description ends with CTA
[✓] Description accurately reflects article
[✓] Wording is clear and natural
```