# SEO SERP Analysis Skill

## Objective

Given a target keyword, location, and language, return a **structured SERP analysis** — ranking patterns, content signals, featured snippet opportunities, and content gap recommendations.

## Inputs

```json
{
  "keyword": "string",
  "location_name": "string",
  "language_name": "string",
  "device": "desktop|mobile",
  "num_results": 10
}
```

## Process

1. **SERP capture** — pull top 10 organic results via DataForSEO SERP API
2. **Ranking analysis** — extract domain distribution, position spread, page types (blog, product, homepage)
3. **Title/tag patterns** — identify word frequency, length averages, emotional triggers
4. **Featured snippet detection** — is there a featured snippet? Who owns it? What's missing?
5. **Content gap identification** — based on what the top pages cover that the target content might not
6. **Intent confirmation** — cross-reference with what SERP shows to confirm/modify intent assumption
7. **Opportunity scoring** — how achievable is ranking here? Based on page-type diversity, domain authority spread, content gaps

## DataForSEO Call

```
POST https://api.dataforseo.com/v3/serp/google/organic/live/advanced
```

## Output Schema

```json
{
  "summary": {
    "keyword": "string",
    "location": "string",
    "language": "string",
    "device": "string",
    "num_results_analyzed": 0,
    "intent": "informational|commercial|transactional|navigational",
    "featured_snippet_present": true,
    "featured_snippet_owner": "string|null",
    "difficulty_signal": "low|medium|high",
    "opportunity_verdict": "string"
  },
  "ranking_pages": [
    {
      "position": 1,
      "domain": "string",
      "url": "string",
      "page_type": "blog|product|homepage|category|question|other",
      "title": "string",
      "title_length": 0,
      "word_count_estimate": 0,
      "has_schema": true,
      "has_video": true,
      "has_images": true,
      " publication_date": "YYYY-MM-DD|null",
      "domain_authority_signal": "high|medium|low"
    }
  ],
  "title_analysis": {
    "avg_length_chars": 0,
    "common_words": ["string"],
    "emotional_triggers": ["string"]
  },
  "featured_snippet": {
    "present": true,
    "type": "paragraph|list|table|question",
    "owner_domain": "string|null",
    "gaps": ["string"]
  },
  "content_gaps": [
    {
      "gap": "string",
      "referenced_by_count": 0,
      "difficulty_to_cover": "easy|medium|hard"
    }
  ],
  "opportunities": [
    {
      "type": "featured_snippet|question_targeting|list_post|image|video",
      "description": "string",
      "priority": "high|medium|low"
    }
  ]
}
```

## Output Files

- `seo/serp_analysis/{keyword}_{date}.json` — full structured data
- `seo/serp_analysis/{keyword}_{date}_summary.md` — human-readable

## QA Checks

- [ ] All 10 result positions populated
- [ ] Featured snippet correctly identified (or confirmed absent)
- [ ] Content gaps sound plausible and actionable
- [ ] Page types distribution matches SERP reality
- [ ] Intent verdict aligns with what SERP actually shows

## Notes

- Page type inference based on URL structure and title patterns
- Word count estimate derived from snippet density heuristics
- Domain authority signal based on number of top-10 rankings across cluster
