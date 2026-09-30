---
name: schema-markup-generator
description: Analyze webpages and generate implementation-ready JSON-LD schema markup with built-in validation. Use when needing structured data for SEO rich results, entity clarity for search engines and AI systems, or schema validation/merging. Works autonomously across any industry by detecting HTML signals, scoring confidence, validating against schema.org rules, and prompting only when ambiguity exists.
---

# Schema Markup Generator

Analyzes webpages to identify schema opportunities, classify page types, extract entity properties, validate against schema.org standards, and generate valid JSON-LD markup. Operates autonomously using HTML signals, requesting clarification only when confidence is low.

**Key Features:**
- ✅ Autonomous HTML analysis with confidence scoring
- ✅ Schema.org validation (required properties, types, enums)
- ✅ Google Rich Results compliance checks
- ✅ FAQ extraction from accordion/Bootstrap structures
- ✅ VideoObject detection (including lazy-loaded iframes)
- ✅ APR/interestRate extraction for financial products
- ✅ Organization name extraction from page metadata
- ✅ Merge/validation against existing schema files

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| `--url` | Yes* | URL of page to analyze |
| `--html` | Yes* | Raw HTML content (alternative to URL) |
| `--sitewide-entities` | No | JSON file with brand-level entities (organization_name, logo, social_profiles, etc.) |
| `--schema-preferences` | No | JSON file with preferences (prioritise_ecommerce, avoid_faq, google_only, etc.) |
| `--existing-schema` | No | Path to existing JSON-LD to validate/merge |
| `--allow-validation` | No | true/false — prompt user on low-confidence decisions (default: false) |
| `--confidence-threshold` | No | Minimum score for auto-include (default: 0.65) |

*At least one of `--url` or `--html` required.

## Usage

```bash
# Basic usage
schema_generator --url "https://example.com/product-page"

# With sitewide entities
schema_generator --url "https://example.com/service" \
  --sitewide-entities ~/entities/brand.json

# With preferences and validation
schema_generator --url "https://example.com/landing" \
  --schema-preferences ~/prefs/seo.json \
  --allow-validation true

# From raw HTML
schema_generator --html "$(cat page.html)" \
  --existing-schema ~/schema/current.json
```

## Outputs

1. **Schema Opportunity Summary** — Detected types with confidence scores and reasoning
2. **Sanity Check Prompts** — Only when confidence < threshold or ambiguity exists
3. **JSON-LD Schema** — Valid, implementation-ready structured data
4. **Schema Validation** — schema.org compliance check with errors/warnings/suggestions
5. **Implementation Notes** — Placement guidance, merge/replace decisions, missing fields

## Validation

The skill includes built-in validation against schema.org rules and Google Rich Results requirements:

**Validation Checks:**
- Required properties present for each type
- Property types correct (URL, Email, Date, Number, Text)
- Enumerated values valid (e.g., loanType, availability)
- Nested types correct (e.g., Question → Answer)
- Google Rich Results minimum requirements (e.g., FAQPage needs ≥1 Q&A)
- Google Rich Results required properties (e.g., VideoObject needs thumbnailUrl)

**Validation Output:**
```
SCHEMA VALIDATION
------------------------------------------------------------
✅ Schema is valid according to schema.org rules

⚠️  0 warning(s)

💡 TIP: Add thumbnailUrl to VideoObject (if missing)
```

**Validation Files:**
- `scripts/schema_validator.py` — Validation engine
- `schemaorg/schema.ttl` — Schema.org RDF definitions
- `schemaorg/schema.jsonld` — JSON-LD context

## Core Principles

- **Accuracy over volume** — One strong primary entity beats multiple weak ones
- **No hallucination** — Never fabricate missing data or use placeholder values
- **Maximize automation** — Extract signals directly from HTML wherever possible
- **Minimal prompts** — Request clarification only when confidence is low
- **No duplication** — Avoid conflicting or duplicate entities
- **Entity clarity** — Improve understanding for both search engines and AI systems

## Confidence Thresholds

| Score | Action |
|-------|--------|
| 0.85–1.0 | Safe to implement automatically |
| 0.65–0.84 | Implement, optionally request confirmation |
| 0.40–0.64 | Request confirmation before implementation |
| < 0.40 | Do not implement unless user confirms |

## Supported Schema Types

**Core:** Article, BlogPosting, NewsArticle, Product, Offer, Service, CollectionPage, ItemList, BreadcrumbList, FAQPage, Organization, Person, Review, AggregateRating, VideoObject, ImageObject, LocalBusiness, WebPage, SoftwareApplication, WebApplication, FinancialProduct, LoanOrCredit

**Advanced (when confidence allows):** HowTo, Speakable, Dataset, Event, JobPosting, Course, DiscussionForumPosting, MedicalEntity, MerchantReturnPolicy, ShippingDetails, ProductGroup, hasVariant

## Entity Hierarchy Rules

**Correct patterns:**
- Product contains Offer
- Article contains Author
- CollectionPage contains ItemList
- Service contains Organization as provider
- LoanOrCredit nested under Product when finance applies
- BreadcrumbList linked to primary entity
- FAQPage linked via mainEntity

**Avoid:**
- Multiple conflicting primary entities
- Duplicate Organization schema blocks
- Empty properties or placeholder values

## Scripts

- `scripts/schema_generator.py` — Main analysis and generation script with integrated validation
- `scripts/schema_validator.py` — Standalone validation engine (schema.org + Google Rich Results)

## Schema.org Data

- `schemaorg/schema.ttl` — RDF/Turtle definitions from schema.org GitHub
- `schemaorg/schema.jsonld` — JSON-LD context for validation

## Extraction Capabilities

**FAQ Extraction:**
- Bootstrap accordion structures (card-header/card-body)
- Lazy-loaded content with data-src attributes
- HTML entity decoding
- Full answer text extraction (including links)

**Video Detection:**
- YouTube/Vimeo iframes (src and data-src attributes)
- Auto-generates thumbnailUrl from video ID
- Adds uploadDate (extracted or current date)
- Google Rich Results compliant output

**Financial Data:**
- APR/interestRate extraction (handles HTML tags)
- Representative APR detection
- Loan type classification (PersonalLoan, BusinessLoan, etc.)

**Organization Detection:**
- Copyright notices
- Logo alt text
- Meta tags (author, og:site_name)
- Page title patterns

## References

- `references/schema-types.md` — Detailed schema type mappings and signals
- `references/confidence-scoring.md` — Scoring logic and thresholds
- `references/entity-hierarchy.md` — Hierarchy rules and patterns
- `references/validation-rules.md` — Validation checks and Google requirements
