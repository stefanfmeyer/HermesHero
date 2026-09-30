---
name: section_expander
description: Expand section headings into full content blocks. Takes H2/H3 structure and generates paragraph content, maintaining brand voice and keyword density.
---

# Section Expander

Expand section headings into full content blocks.

## Overview

This skill:
1. Takes H2/H3 structure from content brief
2. Generates paragraph content for each section
3. Maintains brand voice and tone
4. Optimises keyword density (1-2%)
5. Outputs content blocks for assembly

## Inputs

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `section_heading` | string | ✅ | H2 or H3 heading |
| `subtopics` | array | ✅ | H3/H4 subtopics to cover |
| `word_count` | integer | ✅ | Target word count for section |
| `primary_keyword` | string | ✅ | Primary keyword for density |
| `secondary_keywords` | array | ❌ | Secondary keywords to include |
| `brand_id` | string | ✅ | Brand identifier for voice/tone |
| `format` | string | ✅ | "paragraph", "bullets", "table", "steps" |

## Outputs

| Output | Format | Description |
|--------|--------|-------------|
| Section Content | Markdown | Full content for section |
| Keyword Density | JSON | Primary/secondary keyword counts |

## Process

### Step 1: Load Brand Context

Load brand voice, tone, and writing style.

### Step 2: Generate Content

Based on format type:

**Paragraph:** 3-5 sentences, 15-20 words per sentence, active voice

**Bullets:** 5-8 bullet points, concise, actionable

**Table:** 2-4 columns, 3-6 rows, comparison focus

**Steps:** Numbered steps, 50-80 words each

### Step 3: Keyword Integration

- Primary keyword: 1-2% density
- Secondary keywords: 0.5-1% density
- Natural placement (not forced)
- Avoid keyword stuffing

### Step 4: Quality Check

- Flesch Reading Ease: 60-70
- Active voice: >90%
- Paragraph length: 2-3 sentences
- No hedging words

## Example Usage

```bash
section_expander --heading "Eligibility Requirements" --subtopics "['Minimum income', 'Credit situations', 'Deposit requirements']" --word_count 400 --primary_keyword "car finance eligibility" --brand_id "neon-gorilla" --format "checklist"
```

## Example Output

```markdown
## Eligibility Requirements

Understanding car finance eligibility helps you prepare before applying. Most lenders have straightforward criteria — here's what you need:

### Minimum Income Requirements

- **Minimum monthly income:** £1,000 (varies by lender)
- **Proof of income:** Payslips or bank statements
- **Employment status:** Full-time, part-time, or self-employed accepted

### Credit Situations Accepted

We work with lenders who accept:

- **Bad credit:** CCJs, defaults, missed payments
- **No credit history:** First-time buyers welcome
- **IVAs and bankruptcies:** Discharged cases considered
- **Thin credit files:** Limited credit history OK

### Deposit Requirements

- **Minimum deposit:** £0 (some lenders offer 100% finance)
- **Recommended deposit:** 10-20% for better rates
- **Part exchange:** Use your current car as deposit

**Keyword Density:** Primary: 1.2%, Secondary: 0.8%
```

## Constraints

- Do NOT generate headings — only expand existing structure
- Do NOT write FAQs — handled by faq_creator
- Do NOT exceed word count by more than 10%
- Do NOT use hedging language ("we believe", "in our opinion")
- Maximum keyword density: 2% for primary

## Error Handling

- If brand_id not found, use generic professional tone
- If format not specified, default to paragraph
- If word_count not achieved, expand with supporting details