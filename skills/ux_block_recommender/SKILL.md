---
name: ux_block_recommender
description: Recommend UX/UI blocks for landing pages based on content type, conversion goal, and SERP analysis. Suggests CTAs, trust signals, social proof placement, and interactive elements.
---

# UX Block Recommender

Recommend UX/UI blocks for landing pages to improve conversion and engagement.

## Overview

This skill:
1. Analyzes content structure from landing page builder
2. Recommends UX blocks for each section
3. Suggests CTA placement and types
4. Identifies trust signal opportunities
5. Recommends social proof placement
6. Outputs implementation-ready UX recommendations

## Inputs

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `page_structure` | JSON | ✅ | Output from landing_page_structure_builder |
| `conversion_goal` | string | ✅ | "lead", "sale", "call", "form" |
| `brand_id` | string | ✅ | Brand identifier for style/CTA text |
| `page_type` | string | ✅ | "service", "product", "location", "comparison" |
| `serp_features` | JSON | ❌ | SERP features from serp_top20_analyser |

## Outputs

| Output | Format | Description |
|--------|--------|-------------|
| UX Recommendations | Markdown | Block recommendations by section |
| UX Blocks JSON | JSON | Implementation-ready block definitions |
| CTA Strategy | Markdown | CTA placement and text strategy |

## UX Block Types

### Trust Signals
- Trust badges (security, certifications)
- Statistics (customers served, success rate)
- Partner logos
- Awards/accreditations

### Social Proof
- Testimonial carousel
- Review summary (stars, count)
- Case study cards
- User-generated content

### CTAs
- Primary CTA (above fold, high contrast)
- Secondary CTA (mid-page, softer)
- Exit-intent CTA
- Sticky CTA (mobile)

### Interactive Elements
- Calculator/estimator
- Comparison table
- FAQ accordion
- Timeline/process steps

### Visual Breaks
- Image carousel
- Video embed
- Infographic
- Quote callout

## Process

### Step 1: Analyze Page Structure

Parse page structure to identify:
- Section types (problem, solution, benefits, FAQ)
- Content density (word count per section)
- Current formats (paragraph, bullets, table)

### Step 2: Load Brand Context

If `brand_id` provided:
1. Load brand CTA preferences
2. Load trust signal requirements
3. Load social proof assets available
4. Load brand style guidelines

### Step 3: Map UX Blocks to Sections

| Section | Recommended UX Blocks |
|---------|----------------------|
| Hero/Hook | Trust badges, primary CTA |
| Problem/Pain | Statistics, pain point icons |
| Solution/Service | Feature icons, video embed |
| Benefits | Comparison table, benefit icons |
| Features | Accordion, image carousel |
| Social Proof | Testimonial carousel, review summary |
| FAQ | Accordion, expandable sections |
| CTA | Primary CTA, exit-intent |

### Step 4: Recommend CTA Strategy

Based on conversion goal:
- **Lead generation**: Form above fold, soft CTA mid-page, exit-intent
- **Sales**: Buy now above fold, urgency elements, sticky CTA
- **Calls**: Click-to-call above fold, callback request mid-page
- **Forms**: Short form above fold, long form at bottom

### Step 5: Generate Output

Create implementation-ready recommendations with:
- Block type
- Placement (section, position)
- Content suggestions
- Design notes (style, colours)

## Example Output

```markdown
# UX Block Recommendations — Bad Credit Car Finance

## Hero Section
**Recommended Blocks:**
1. Trust Badges (top right)
   - "No impact on credit score"
   - "FCA authorised"
   - "4.8/5 Trustpilot"

2. Primary CTA (below H1)
   - Button text: "Check your eligibility"
   - Style: High contrast, large
   - Link: /apply

## Problem/Pain Section
**Recommended Blocks:**
1. Statistics (left column)
   - "89% approval rate"
   - "£500-£50,000 finance available"
   - "Decision in 2 minutes"

2. Pain Point Icons (right column)
   - "Bad credit? No problem"
   - "CCJs? We can help"
   - "IVA? Still accepted"

## Solution Section
**Recommended Blocks:**
1. Video Embed (centered)
   - "How our process works"
   - 60-second explainer

2. Process Steps (timeline)
   - "1. Check eligibility"
   - "2. Compare quotes"
   - "3. Choose your car"
   - "4. Drive away"

## Benefits Section
**Recommended Blocks:**
1. Comparison Table
   - "Us vs Traditional Lenders"

2. Benefit Icons (grid)
   - "Low APR"
   - "Flexible terms"
   - "No deposit"

## Social Proof Section
**Recommended Blocks:**
1. Testimonial Carousel
   - 5 customer stories
   - Auto-rotate, 5 seconds

2. Review Summary
   - "4.8/5 from 2,847 reviews"
   - Trustpilot logo

## FAQ Section
**Recommended Blocks:**
1. Accordion
   - Expandable questions
   - Schema-ready for FAQ markup

## CTA Section
**Recommended Blocks:**
1. Exit-Intent Popup
   - "Wait! Get your free quote"
   - Email capture form

2. Sticky CTA (mobile)
   - "Get your quote"
   - Fixed bottom, always visible

## CTA Strategy

| CTA Type | Placement | Text | Goal |
|----------|------------|------|------|
| Primary | Hero section | "Check your eligibility" | Form start |
| Secondary | Mid-page | "Compare quotes now" | Engagement |
| Exit-intent | On exit | "Wait! Get your free quote" | Lead capture |
| Sticky | Mobile | "Get your quote" | Conversion |
```

## Constraints

- Do NOT design actual UI — only recommend block types
- Do NOT generate content for blocks — only suggestions
- Maximum 3 CTAs per page (above fold, mid-page, bottom)
- Trust signals must be accurate and verifiable
- Social proof must be real (no fake testimonials)

## Error Handling

- If brand_id not found, use generic UX recommendations
- If conversion_goal not specified, default to "lead"
- If page_type not specified, default to "service"