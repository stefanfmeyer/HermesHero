# Confidence Scoring Logic

Confidence scores determine whether schema types should be implemented automatically, with confirmation, or not at all.

## Score Calculation

Each schema type receives a score between 0 and 1 based on:

1. **Signal strength** — How strong each detected signal is
2. **Signal consistency** — Multiple signals pointing to same type
3. **Data completeness** — How many required properties can be extracted
4. **Ambiguity penalties** — Conflicting signals reduce score

## Base Signal Scores

### Product Schema

| Signal | Score | Notes |
|--------|-------|-------|
| Price detected | +0.35 | Currency symbols or explicit price text |
| SKU detected | +0.25 | Product ID, Model number |
| Add to cart button | +0.20 | E-commerce intent |
| Specifications table | +0.15 | Product details present |
| Reviews detected | +0.10 | Rating/review section |
| Availability text | +0.10 | In stock, ships in, etc. |
| Variant selectors | +0.08 | Size, color, options |

**Maximum:** 1.0 (capped)

### Article Schema

| Signal | Score | Notes |
|--------|-------|-------|
| Publication date | +0.30 | Published, posted, updated |
| Author byline | +0.25 | Written by, author name |
| Reading time | +0.15 | X min read |
| Table of contents | +0.15 | On this page, jump to |
| Blog layout | +0.10 | Blog/article terminology |

**Maximum:** 1.0 (capped)

### Service Schema

| Signal | Score | Notes |
|--------|-------|-------|
| Conversion CTA | +0.30 | Get quote, contact us, book now |
| Lead form | +0.25 | Form element present |
| Benefits section | +0.20 | Why choose, advantages |
| No pricing | +0.15 | Absence of price signals |

**Maximum:** 1.0 (capped)

### FAQPage Schema

| Signal | Score | Notes |
|--------|-------|-------|
| Accordion elements | +0.25 | Collapse, toggle, expand |
| Q&A structure | +0.30 | dt/dd, itemscope question/answer |
| Question headings | +0.25 | ? or how/what/why starters |

**Maximum:** 1.0 (capped)

### Organization Schema

| Signal | Score | Notes |
|--------|-------|-------|
| Logo detected | +0.30 | img with logo/brand in alt/src |
| Company name | +0.25 | Copyright notice |
| Contact info | +0.20 | Contact, phone, email |
| Social profiles | +0.15 | Social media links |

**Maximum:** 1.0 (capped)

### FinancialProduct Schema

| Signal | Score | Notes |
|--------|-------|-------|
| APR reference | +0.35 | X% APR |
| Loan calculator | +0.30 | Payment/finance calculator |
| Eligibility criteria | +0.20 | Qualify, requirements |
| Finance terms | +0.25 | HP, PCP, conditional sale |

**Maximum:** 1.0 (capped)

### SoftwareApplication Schema

| Signal | Score | Notes |
|--------|-------|-------|
| Features list | +0.20 | Features, capabilities |
| Pricing tiers | +0.25 | Basic, pro, enterprise |
| Platform refs | +0.15 | Windows, Mac, iOS, Android |
| Download CTA | +0.20 | Download, install, free trial |

**Maximum:** 1.0 (capped)

### CollectionPage / ItemList Schema

| Signal | Score | Notes |
|--------|-------|-------|
| Product grid | +0.30 | Product-grid, item-grid class |
| Filters | +0.25 | Filter, sort, refine |
| Pagination | +0.20 | Page X, next page, load more |
| Product cards | +0.25 | Product-card, listing class |

**Maximum:** 1.0 (capped)

### BreadcrumbList Schema

| Signal | Score | Notes |
|--------|-------|-------|
| Nav hierarchy | +0.30 | Breadcrumb, home > |
| Breadcrumb markup | +0.40 | Explicit breadcrumb element |

**Maximum:** 1.0 (capped)

### VideoObject Schema

| Signal | Score | Notes |
|--------|-------|-------|
| Video embed | +0.40 | video tag, YouTube/Vimeo iframe |
| Gallery present | +0.25 | May contain video |

**Maximum:** 1.0 (capped)

## Confidence Thresholds

| Score Range | Action |
|-------------|--------|
| 0.85 – 1.0 | **Safe** — Implement automatically |
| 0.65 – 0.84 | **Moderate** — Implement, optionally request confirmation |
| 0.40 – 0.64 | **Low** — Request confirmation before implementation |
| < 0.40 | **Very Low** — Do not implement unless user confirms |

## Diminishing Returns

To prevent score inflation:
- First 3 signals: full value
- Signals 4-6: 50% value
- Signals 7+: 25% value

Formula: `adjusted_score = sum(signal_scores[:3]) + sum(s * 0.5 for s in signal_scores[3:6]) + sum(s * 0.25 for s in signal_scores[6:])`

## Ambiguity Penalties

When two schema types have similar scores:
- If top_score - second_score < 0.1 AND top_score < 0.85: flag as ambiguous
- Apply 0.8 multiplier to both scores
- Request user confirmation if validation enabled

## Data Completeness Bonus

If required properties for a schema type can be fully extracted:
- Add +0.1 bonus (capped at 1.0)

Required properties by type:
- **Product:** name, (offers or description)
- **Article:** headline, (author or datePublished)
- **Service:** name, (provider or description)
- **FAQPage:** mainEntity with at least one Question/Answer
- **Organization:** name
- **BreadcrumbList:** itemListElement with at least 2 items

## Minimum Signal Count Penalty

If fewer than 2 signals detected for a schema type:
- Apply 0.7 multiplier to score

This prevents false positives from single weak signals.
