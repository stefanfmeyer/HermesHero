# SEO Keyword Research Skill

## Objective

Given a set of seed keywords and a target market, produce a **structured keyword map** — clustered topic groups with search volume, difficulty, CPC, and intent for each keyword.

## Inputs

```json
{
  "seed_keywords": ["string"],
  "location_name": "string",
  "language_name": "string",
  "include_variations": true,
  "max_keywords": 100
}
```

## Process

1. **Seed enrichment** — for each seed keyword, pull keyword_info (volume, difficulty, CPC) via DataForSEO Keywords Data API
2. **Variation expansion** — pull keyword variations for each seed
3. **Dedup + merge** — consolidate into a single keyword list
4. **Volume fetch** — batch-fetch search volume for all keywords
5. **Clustering** — group keywords by shared topic/token (simple exact-match and substring clustering)
6. **Intent labelling** — classify each as Informational, Navigational, Commercial, or Transactional based on SERP features
7. **Priority scoring** — score each cluster by: total volume × intent weight ÷ difficulty

## DataForSEO Calls

```
POST https://api.dataforseo.com/v3/keywords_data/google/keyword_info/live
POST https://api.dataforseo.com/v3/keywords_data/google/variations/live
POST https://api.dataforseo.com/v3/keywords_data/google/search_volume/live
```

## Output Schema

```json
{
  "summary": {
    "total_keywords": 0,
    "total_clusters": 0,
    "top_volume_keyword": "string",
    "top_opportunity_cluster": "string",
    "estimated_total_monthly_searches": 0
  },
  "clusters": [
    {
      "cluster_id": "string",
      "topic": "string",
      "seed_indicator": "string",
      "keywords": [
        {
          "keyword": "string",
          "volume": 0,
          "difficulty": 0,
          "cpc": 0,
          "intent": "informational|commercial|transactional|navigational",
          "last_updated": "YYYY-MM-DD"
        }
      ],
      "cluster_volume": 0,
      "cluster_difficulty_avg": 0,
      "priority_score": 0
    }
  ],
  "raw_keywords": [...]
}
```

## Output Files

- `seo/keyword_research/{query}_{date}.json` — full structured data
- `seo/keyword_research/{query}_{date}_summary.md` — human-readable summary

## QA Checks

- [ ] All seed keywords present in output
- [ ] Volume > 0 for at least some keywords (if 0, check API coverage)
- [ ] No duplicate keywords across clusters
- [ ] Each cluster has at least 2 keywords (single-keyword clusters = check clustering logic)
- [ ] Intent distribution looks reasonable

## Notes

- Difficulty 0-100 (higher = harder to rank)
- CPC in USD
- Cluster priority = sum(volume × intent_weight) / avg(difficulty)
  - Intent weights: transactional=1.0, commercial=0.7, informational=0.5, navigational=0.3
