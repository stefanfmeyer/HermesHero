# SEO Content Brief Skill

## Objective

Given a target keyword and SERP analysis data, produce a **writer-ready content brief** — structured spec covering angle, structure, word count, references, FAQs, and quality signals the writer must hit.

## Inputs

```json
{
  "keyword": "string",
  "target_url": "string",
  "location_name": "string",
  "language_name": "string",
  "target_word_count": 1200,
  "style_guide": "informative|persuasive|transactional|educational"
}
```

Requires output from `seo-serp-analysis` skill as input — run that first.

## Process

1. **Reference review** — pull top 3 ranking pages, extract their structure and key points
2. **Angle definition** — based on keyword intent and competitor gaps, define the content angle
3. **Heading structure** — draft H2/H3 outline based on what competitors cover + gaps
4. **Word count allocation** — distribute target word count across sections
5. **Reference gathering** — extract data points, stats, and sources from competitors
6. **FAQ extraction** — pull "People Also Ask" and related searches from SERP to include
7. **Quality signals** — define schema requirements, internal linking, media, and E-E-A-T signals
8. **Brief assembly** — output formatted brief ready for writer

## DataForSEO Calls

```
POST https://api.dataforseo.com/v3/serp/google/organic/live/advanced  (for SERP + PAA)
```

## Output Schema

```json
{
  "brief_meta": {
    "keyword": "string",
    "target_url": "string",
    "location": "string",
    "language": "string",
    "target_word_count": 0,
    "style": "string",
    "created": "YYYY-MM-DD",
    "serp_opportunity_verdict": "string"
  },
  "content_angle": {
    "primary_angle": "string",
    "unique_value_proposition": "string",
    "why_this_page_will_rank": ["string"]
  },
  "heading_structure": [
    {
      "heading": "H2: string",
      "h3s": ["string"],
      "purpose": "string",
      "word_count_target": 0,
      "key_points": ["string"],
      "keywords_to_naturally_include": ["string"]
    }
  ],
  "references_and_data": [
    {
      "claim": "string",
      "source_url": "string",
      "source_domain": "string",
      "stat_or_fact": "string"
    }
  ],
  "faq_section": [
    {
      "question": "string",
      "answer_guidance": "string",
      "source": "string"
    }
  ],
  "quality_signals": {
    "schema_required": ["string"],
    "internal_links_target": ["string"],
    "external_links_required": ["string"],
    "media_required": ["image|video|infographic"],
    "eeat_signals": ["string"]
  },
  "writing_guidance": {
    "tone": "string",
    "readability_level": "string",
    "sentence_structure_notes": ["string"],
    "things_to_avoid": ["string"]
  },
  "competitor_reference": [
    {
      "domain": "string",
      "url": "string",
      "what_to_learn_from_it": ["string"]
    }
  ]
}
```

## Output Files

- `seo/content_briefs/{keyword}_{date}.json` — full brief data
- `seo/content_briefs/{keyword}_{date}_brief.md` — writer-facing formatted brief

## QA Checks

- [ ] Heading structure covers all key competitor topics
- [ ] Word count distributed realistically across sections
- [ ] FAQ questions sourced from real SERP data
- [ ] References are real (domains match competitor data)
- [ ] Quality signals are specific and testable
- [ ] Angle is clearly differentiated from top-ranking content

## Notes

- Brief is the bridge between SEO analysis and content production
- Always ground headings in actual competitor gaps, not assumptions
- FAQ section should draw from People Also Ask + related searches
- Schema requirements should match competitor patterns, not random suggestions
