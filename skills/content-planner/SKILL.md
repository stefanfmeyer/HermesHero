---
name: content-planner
description: Transforms keyword clusters from keyword-research-finder into complete SEO page outlines (H1/H2/H3/H4) with format guidance and word count allocation. Generates target URL from domain + primary keyword. Outputs brief as Markdown + Google Doc for handoff to CCE engine (Stage 3). Use when you need to create content structure for SEO pages, organize keyword clusters into logical heading hierarchy, or generate EEAT-aligned outlines for blog posts or landing pages. Accepts keyword_research_output, content_type, word_count_range, brand_id, and serp_analysis_enabled flag. NOTE: FAQs are handled by separate faq_creator skill — do NOT include FAQ questions in the brief.
---

# Content Planner

Transform keyword clusters into structured SEO page outlines.

## Inputs

- **keyword_research_output**: Structured output from keyword_research_finder containing:
  - Domain (for target URL generation)
  - Content type (blog or landing_page)
  - Primary keyword
  - Secondary keywords
  - Supporting keyword variations
  - Keyword themes
  - Keywords to avoid

- **brand_id**: Brand identifier to load context from Google Drive knowledge base. Required for accessing brand guidelines and style guides.

- **author_persona** (optional): Author persona to use for the content. If not provided, defaults to brand voice only.
  - Available personas (from Google Drive):
    - `sean-oconnor` — Sean O'Connor (CMO)
    - `ben-fildes` — Ben Fildes (Founder)
    - `senior-strategist` — Your Name (Senior Strategist)

- **word_count_range**: Target word count as:
  - Single value: `2000` (exact target)
  - Range: `1500-2500` (flexible range)
  - Minimum: `1500+` (minimum threshold)

- **serp_analysis_enabled**: `true` or `false` (optional, default: false)

## Brand Knowledge Base

The skill loads context from Google Drive based on `brand_id`:

```
/brand-knowledge/{brand_id}/
├── Brand Guidelines.md         (always loaded)
├── Writing Style Guide.md     (always loaded)
├── Services.md               (context)
├── Competitor Positioning.md  (context)
└── user-personas/
    ├── sean-oconnor/
    │   └── Persona - Sean O'Connor.md
    ├── ben-fildes/
    │   └── Persona - Ben Fildes.md
    └── senior-strategist/
        └── Persona - Your Name.md
```

**Author Persona Loading:**
- If `author_persona` is provided → Load that specific persona file
- If `author_persona` is not provided → Use Brand Guidelines + Writing Style Guide only (no specific author voice)
```
Google Drive: /brand-knowledge/{brand_id}/
├── Brand Guidelines.md         (voice, tone, USP, values)
├── Writing Style Guide.md     (grammar, formatting rules)
├── Services.md               (service details, pricing)
├── Competitor Positioning.md  (differentiation, messaging)
└── user-personas/
    ├── sean-oconnor/
    │   └── Persona - Sean O'Connor.md
    ├── ben-fildes/
    │   └── Persona - Ben Fildes.md
    └── senior-strategist/
        └── Persona - Your Name.md
```

**Brand context includes:**
- Brand voice/tone (e.g., "authoritative but approachable")
- Writing style (e.g., UK English, sentence case headings)
- USP or differentiator (e.g., "specialises in bad credit approvals")
- Audience context (e.g., "UK consumers with poor credit history")
- Author persona (if multiple authors with different styles)

## Outputs

**Page outline** containing:
- Generated target URL (from domain + primary keyword)
- H1 (main title)
- H2 sections (major topics) with word allocation
- H3 subsections (supporting topics) with word allocation
- H4 where useful (detailed breakdowns) with word allocation
- Format guidance for each section
- Total word count summary

**NOTE:** FAQs are NOT included in the brief — handled by separate `faq_creator` skill.

## Process

### Step 0: Parse Keyword Research Output

Extract from keyword_research_finder output:
- Domain → Used to construct target URL
- Content type → blog or landing_page
- Primary keyword → Main H1 + URL slug
- Secondary keywords → H2 candidates
- Supporting keyword variations → H3 candidates
- Keyword themes → Section groupings
- Keywords to avoid → Exclude from outline entirely

### Step 0.5: Load Brand Context (if brand_id provided)

If `brand_id` is provided:
1. Access Google Drive folder: `/brand-knowledge/{brand_id}/`
2. Load `Brand Guidelines.md` for voice, tone, USP
3. Load `Writing Style Guide.md` for formatting rules
4. Load `Services.md` for service context
5. Load `Competitor Positioning.md` for differentiation messaging
6. Load relevant author persona from `user-personas/{author}/`

Generate target URL:
```
Domain: choosemycar.com
Primary keyword: bad credit car finance
→ Target URL: https://choosemycar.com/bad-credit-car-finance
```

URL slug rules:
- Lowercase
- Spaces → hyphens
- Remove special characters
- Keep it concise (match primary keyword)

### Step 1: Map Keyword Themes to H2 Sections

Each keyword theme maps to one H2 section.

Example mapping:
```
Keyword theme: "Eligibility criteria"
→ H2: "Eligibility requirements"
```

### Step 2: Determine Section Order

Order based on user expectations:
1. Definition/overview early
2. Eligibility early for financial/application topics
3. Process steps mid-page
4. Supporting detail later

### Step 3: Expand with Keyword Variations

Use supporting keyword variations for H3 subsections.

Example:
```
Keyword variation: "car finance with iva"
→ H3: "Can you get car finance with an IVA"
```

### Step 4: Allocate Word Count

Distribute word count proportionally across sections:

**Allocation rules:**
- Introduction/H1 context: 10-15% of total
- Each H2 section: Proportional to complexity (number of H3s + importance)
- H3 sections inherit from parent H2 allocation
- Leave 5-10% buffer for natural expansion

**Word count calculation:**
1. Count total H2 sections
2. Weight each H2 by: `(number of H3s + 1) * theme_importance`
3. Distribute words proportionally
4. Round to nearest 50 for readability

**Example allocation for 2000 words:**
```
H1 context: 200 words (10%)
H2: What is bad credit car finance: 200 words (2 H3s = 10%)
H2: Eligibility requirements: 500 words (4 H3s = 25%)
H2: How the application works: 400 words (3 H3s = 20%)
H2: Interest rates: 300 words (2 H3s = 15%)
H2: Next steps: 200 words (10%)
Buffer: 200 words (10%)
```

### Step 5: Assign Format to Each Section

**Allowed formats:**

| Format | When to use |
|--------|-------------|
| paragraph | Explaining concepts, defining terms |
| bullet list | Requirements, benefits, features |
| numbered steps | Processes, instructions, application journeys |
| table | Comparing options, pricing, features |
| checklist | Eligibility criteria, preparation steps |
| short definition block | Introducing key concepts |
| comparison table | Contrasting alternatives |

**EEAT alignment**: Formats should support clarity, scannability, structure, and trust.

## SERP Structure Pattern Detection

If `serp_analysis_enabled = true`, analyze top 20 ranking pages to refine outline structure.

### SERP Analysis Process

1. **Search** using primary keyword and top secondary variations
2. **Extract** H1/H2/H3 headings from top 20 organic results (ignore ads, forums, nav, footer)
3. **Normalise** similar headings into themes (e.g., "What is X", "Understanding X" → "definition section")
4. **Calculate frequency** of structural themes across pages
5. **Identify patterns** appearing on 40%+ of pages (strong = 60%+)
6. **Compare** SERP patterns with keyword themes
7. **Refine** section order based on common patterns
8. **Add** frequently occurring sections missing from keyword themes (if 40%+ frequency)

### Pattern Weighting

- **Prioritise**: Patterns on 40%+ of pages
- **Strong patterns**: 60%+ frequency
- **Ignore**: Patterns below 30% (unless keyword themes strongly support)

### SERP Influence Rules

- SERP analysis **refines** structure, does not override keyword themes
- Keyword themes remain primary source of section topics
- Do not copy single competitor structure
- Build blended structure from overall SERP expectations

## Output Format

```
============================================
CONTENT BRIEF — [Page Title]
============================================
Target URL: [URL]
Content type: [blog/landing_page]

H1: [Main Title]
Total word count: [X words]

H2: [Section Title]
Word allocation: [X words]
Format: [format type]

H3: [Subsection Title]
Word allocation: [X words]
Format: [format type]

H2: [Section Title]
Word allocation: [X words]
Format: [format type]
...

--------------------------------------------
WORD COUNT SUMMARY
--------------------------------------------
Total: [X words]
H1 context: [X words]
Sections: [X words]
Buffer: [X words]

--------------------------------------------
BRAND CONTEXT APPLIED
--------------------------------------------
Author: [author_persona from input, or "brand-default" if not specified]
Author voice: [from persona file if specified, or "brand voice only" if not]
Brand voice: [from Brand Guidelines]
Writing style: [from Writing Style Guide]

--------------------------------------------
KEYWORD COVERAGE
--------------------------------------------
Primary keyword: [keyword] ✓
Secondary keywords: [X of Y] ✓
Keyword themes: [X themes covered]
```

## Constraints

- Do NOT generate full article content
- Do NOT generate FAQ questions (use separate faq_creator skill)
- Do NOT generate schema
- Do NOT generate internal linking suggestions
- Avoid generic headings ("Overview", "Introduction")
- Prefer descriptive headings aligned to keyword themes
- Avoid duplicate sections with identical intent
- Do not force all keyword variations into headings
- SERP analysis refines but does not override keyword themes

## Example Output

```
============================================
CONTENT BRIEF — Bad Credit Car Finance
============================================
Target URL: https://choosemycar.com/bad-credit-car-finance
Content type: landing_page

H1: Bad Credit Car Finance
Total word count: 2000 words

H2: What is bad credit car finance
Word allocation: 200 words
Format: short definition block + paragraph

H2: Can you get car finance with bad credit
Word allocation: 200 words
Format: paragraph

H2: Eligibility requirements
Word allocation: 500 words
Format: checklist

H3: Minimum income requirements
Word allocation: 100 words
Format: bullet list

H3: Credit situations accepted
Word allocation: 150 words
Format: bullet list

H3: Deposit requirements
Word allocation: 100 words
Format: paragraph

H3: Age and residency requirements
Word allocation: 50 words
Format: bullet list

H2: How the application process works
Word allocation: 400 words
Format: numbered steps

H3: Check eligibility
Word allocation: 100 words
Format: step

H3: Submit application
Word allocation: 100 words
Format: step

H3: Receive decision
Word allocation: 100 words
Format: step

H3: Complete purchase
Word allocation: 100 words
Format: step

H2: Guarantor vs no guarantor options
Word allocation: 300 words
Format: comparison table

H2: Interest rates explained
Word allocation: 300 words
Format: paragraph + table

H2: Next steps
Word allocation: 200 words
Format: paragraph + CTA

--------------------------------------------
WORD COUNT SUMMARY
--------------------------------------------
Total: 2000 words
H1 context: 200 words
Sections: 1600 words
Buffer: 200 words

--------------------------------------------
BRAND CONTEXT APPLIED
--------------------------------------------
Voice: Authoritative but approachable
Writing style: UK English, sentence case headings
USP: Specialist in bad credit approvals
Audience: UK consumers with poor credit history
Author: Sean O'Connor

--------------------------------------------
KEYWORD COVERAGE
--------------------------------------------
Primary keyword: bad credit car finance ✓
Secondary keywords: 8 of 12 ✓
Keyword themes: 6 themes covered
```