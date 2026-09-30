---
name: landing_page_writer
description: Write complete landing page content from structure and brand guidelines. Generates conversion-focused copy optimised for specific conversion goals.
---

# Landing Page Writer

Write complete landing page content from structure.

## Overview

This skill:
1. Takes landing page structure from structure builder
2. Writes complete copy for each section
3. Optimises for conversion goal
4. Maintains brand voice and tone
5. Integrates keywords naturally
6. Outputs full landing page ready for QA

## Inputs

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `page_structure` | JSON | ✅ | Output from landing_page_structure_builder |
| `brand_id` | string | ✅ | Brand identifier |
| `conversion_goal` | string | ✅ | "lead", "sale", "call", "form" |
| `primary_keyword` | string | ✅ | Primary keyword |
| `secondary_keywords` | array | ❌ | Secondary keywords |
| `cta_text` | string | ❌ | Specific CTA text to use |
| `testimonials` | array | ❌ | Customer testimonials to include |

## Outputs

| Output | Format | Description |
|--------|--------|-------------|
| Landing Page Copy | Markdown | Full landing page content |
| Landing Page Copy | Google Doc | For review/approval |
| Word Count Report | JSON | Section word counts vs targets |

## Process

### Step 1: Load Brand Context

Load:
- Brand voice and tone
- Writing style guide
- USP/differentiators
- CTA preferences
- Example copy (if available)

### Step 2: Write Hero Section

- H1 with primary keyword
- Opening paragraph (2-3 sentences)
- Value proposition bullets
- Primary CTA placement

### Step 3: Write Problem Section

- Acknowledge pain points
- Validate reader's situation
- Build empathy before solution

### Step 4: Write Solution Section

- Present offering clearly
- Benefits-focused (not features)
- Social proof integration

### Step 5: Write Supporting Sections

- Benefits section (bullet points)
- Features section (detailed)
- Trust signals (badges, stats)
- Testimonials (real quotes)

### Step 6: Write FAQ Section

- Address common objections
- Prepare for CTA
- FAQ schema-ready format

### Step 7: Write Final CTA

- Strong close
- Urgency or value statement
- Final conversion action

## Example Output

```markdown
# Bad Credit Car Finance — Landing Page

## Hero

### Bad Credit Car Finance — Get Approved Today

Your credit history doesn't have to hold you back. We work with specialist lenders who look at more than just your credit score. Get car finance approved, even with bad credit, CCJs, or defaults.

**✓ No credit impact check**
**✓ FCA authorised lenders**
**✓ 89% approval rate**
**✓ Decision in 2 minutes**

[Check Your Eligibility →] *(PRIMARY CTA)*

---

## Problem — Why Traditional Lenders Say No

High street banks rely on credit scores as the be-all and end-all. Miss one payment two years ago? Declined. Have a CCJ from 2019? Declined. This isn't fair — it's a system that punishes people for past mistakes.

But here's the thing: your credit history is a snapshot, not a verdict. It doesn't show lenders how you manage money today.

**The old system:** Credit score alone = instant decline
**The better approach:** Whole financial picture = real approval chances

---

## Solution — How We Help You Get Approved

We work with lenders who see past the credit score. They look at your income, employment, and current financial situation. The result? A much better chance of approval — even for people traditional lenders have turned away.

**How it works:**

1. **Tell us about your situation** — Takes 2 minutes, no credit impact
2. **We find the right lenders** — From our panel of 40+ specialist lenders
3. **You compare quotes** — Real rates, no obligations
4. **Choose and apply** — Full support through to delivery

**Already know you qualify?** [Skip the check and apply directly →]

---

## Benefits — Why People Choose Us

| | Traditional Bank | ChooseMyCar |
|---|---|---|
| Credit score focus | Yes — instant decline | No — we look deeper |
| Lender options | 1-2 | 40+ |
| Approval rate | ~30% | 89% |
| Decision time | Days/weeks | 2 minutes |
| FCA authorised | Yes | Yes |

---

## Social Proof

*"Didn't think I'd get approved with my credit history. ChooseMyCar found me a lender within 30 minutes. Driving my new car now."*
— Sarah M., Birmingham, Verified Customer

**4.8/5 from 2,847 Trustpilot reviews**

---

## FAQ

**Will applying affect my credit score?**
No. Our initial eligibility check uses a soft search that doesn't leave a footprint on your credit file.

**What credit situations do you accept?**
We work with lenders who accept bad credit, CCJs, defaults, IVAs, and bankruptcy (discharged). Even if you've been declined elsewhere, we may still be able to help.

**How much can I borrow?**
£500 to £50,000, with terms from 12 to 60 months. Your rate and amount depend on your circumstances.

---

## Get Your Free Quote

Don't let bad credit keep you out of the driver's seat. Check your eligibility in 2 minutes — it won't affect your credit score.

[Check Your Eligibility — It's Free →]

---

**Word Count:** 1,247 words | **Conversion Goal:** Form submission | **Status:** Ready for QA
```

## Constraints

- Do NOT write more than 10% over target word count
- Do NOT use hedging language
- Do NOT make claims that can't be verified
- Do NOT use US English spellings
- Primary keyword must appear in H1
- CTA must appear above fold

## Error Handling

- If brand_id not found, use generic professional tone
- If conversion_goal not specified, default to "lead"
- If testimonials not provided, use placeholder [TESTIMONIAL]
- If CTA not specified, use brand default CTA