---
name: seo_content_qa_checker
description: Quality assurance checker for SEO content. Validates readability, keyword density, brand voice, technical SEO elements, and overall content quality against brand guidelines.
---

# SEO Content QA Checker

Quality assurance checker for SEO content.

## Overview

This skill:
1. Validates readability (Flesch score, sentence length)
2. Checks keyword density (primary and secondary)
3. Verifies brand voice compliance
4. Validates technical SEO elements (headings, links, images)
5. Checks for plagiarism (optional)
6. Outputs QA report with pass/fail status

## Inputs

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `article_text` | string | ✅ | Full article content |
| `primary_keyword` | string | ✅ | Primary keyword |
| `secondary_keywords` | array | ❌ | Secondary keywords to check |
| `brand_id` | string | ✅ | Brand identifier for voice/rules |
| `target_readability` | string | ❌ | "Flesch 60-70" or custom target |
| `check_plagiarism` | boolean | ❌ | Run plagiarism check (default: false) |

## Outputs

| Output | Format | Description |
|--------|--------|-------------|
| QA Report | Markdown | Detailed pass/fail report |
| QA Summary | JSON | Machine-readable results |
| Issues List | Markdown | Items requiring revision |
| Overall Status | string | "PASS", "MINOR_REVISIONS", "FAIL" |

## QA Categories

### Readability
| Metric | Target | Tolerance |
|--------|--------|-----------|
| Flesch Reading Ease | 60-70 | 50-80 (warn), <50 or >80 (fail) |
| Avg Sentence Length | 15-20 words | 10-25 (warn), <10 or >25 (fail) |
| Avg Paragraph Length | 2-3 sentences | 1-5 (warn), >5 (fail) |
| Passive Voice | <10% | 10-15% (warn), >15% (fail) |

### Keyword Optimisation
| Metric | Target | Tolerance |
|--------|--------|-----------|
| Primary Keyword Density | 1-2% | 0.5-3% (warn), <0.5% or >3% (fail) |
| Keyword in H1 | Yes | Fail if missing |
| Keyword in First 100 Words | Yes | Warn if missing |
| Keyword in Meta | Yes | (Checked separately) |
| Secondary Keyword Coverage | 60%+ | <60% (warn) |

### Brand Voice
| Check | Rule |
|-------|------|
| Hedging Words | No "we believe", "in our opinion", "may/might" |
| Corporate Waffle | No "synergy", "best-in-class", "comprehensive solutions" |
| Exclamation Marks | Maximum 1 per piece |
| US English | Must use UK English (optimise, colour, centre) |
| Paragraph Length | 2-3 sentences max |

### Technical SEO
| Check | Rule |
|-------|------|
| H1 Hierarchy | Exactly 1 H1, logical H2/H3 nesting |
| External Links | At least 2-3 authority external links |
| Internal Links | At least 3 internal links |
| Image Alt Text | All images must have descriptive alt text |
| URL Slug | Matches primary keyword, lowercase, hyphens |
| Word Count | Within 10% of target |

## Process

### Step 1: Readability Analysis

Calculate:
- Flesch Reading Ease
- Average sentence length
- Average paragraph length
- Passive voice percentage

### Step 2: Keyword Analysis

Calculate:
- Primary keyword density
- Secondary keyword presence
- Keyword placement (H1, first 100 words, meta)

### Step 3: Brand Voice Check

Scan for:
- Hedging words list
- Corporate waffle list
- US English spellings
- Exclamation marks count
- Paragraph lengths

### Step 4: Technical SEO Check

Validate:
- Heading hierarchy
- Link counts (internal + external)
- Image alt text presence
- URL slug format

### Step 5: Generate Report

Compile QA report with:
- Overall status
- Category-by-category results
- Issues requiring attention
- Recommendations for fixes

## Example Output

```markdown
# SEO Content QA Report

**Page:** Bad Credit Car Finance
**Date:** 2026-04-08
**Overall Status:** MINOR_REVISIONS ⚠️

---

## Readability
| Metric | Result | Target | Status |
|--------|--------|--------|--------|
| Flesch Reading Ease | 64 | 60-70 | ✅ PASS |
| Avg Sentence Length | 18 words | 15-20 | ✅ PASS |
| Avg Paragraph Length | 2.5 sentences | 2-3 | ✅ PASS |
| Passive Voice | 8% | <10% | ✅ PASS |

---

## Keyword Optimisation
| Metric | Result | Target | Status |
|--------|--------|--------|--------|
| Primary Keyword Density | 1.4% | 1-2% | ✅ PASS |
| Keyword in H1 | Yes | Required | ✅ PASS |
| Keyword in First 100 Words | Yes | Required | ✅ PASS |
| Secondary Keyword Coverage | 75% | 60%+ | ✅ PASS |

---

## Brand Voice
| Check | Result | Status |
|-------|--------|--------|
| Hedging Words | 0 found | ✅ PASS |
| Corporate Waffle | 0 found | ✅ PASS |
| US English | 2 found ("color", "optimize") | ⚠️ FIX |
| Exclamation Marks | 1 | ✅ PASS |
| Paragraph Length | 2.3 avg | ✅ PASS |

---

## Technical SEO
| Check | Result | Status |
|-------|--------|--------|
| H1 Hierarchy | 1 H1, logical H2s | ✅ PASS |
| Internal Links | 4 links | ✅ PASS |
| External Links | 3 links | ✅ PASS |
| Image Alt Text | 2 of 3 present | ⚠️ FIX |
| Word Count | 1,847 words | ✅ PASS |

---

## Issues Requiring Revision

### ⚠️ MUST FIX
1. **US English spellings** — Replace "color" with "colour", "optimize" with "optimise"
2. **Missing Alt Text** — Image 3 ("customer receiving keys") needs alt text

### 📝 RECOMMENDED
1. Consider adding internal link to /car-finance-calculator
2. Add more social proof signals in Benefits section

---

**QA Summary:** 8/10 checks passed, 2 warnings, 0 failures
**Recommendation:** Fix US English and alt text, then ready to publish
```

## Constraints

- Do NOT rewrite content — only report issues
- Do NOT fail on subjective style preferences
- Do NOT count brand voice as FAIL (warn only)
- Maximum 1 exclamation mark per piece
- H1 must contain primary keyword

## Error Handling

- If brand_id not found, skip brand voice checks
- If primary_keyword not found, warn but don't fail
- If article is empty, return error
- If plagiarism check enabled and fails, flag for review