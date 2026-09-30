---
name: serp_top20_analyser
description: Analyse top 20 SERP results for a target keyword to extract heading structures, content patterns, and competitive insights. Identifies common H2/H3 structures, word count ranges, and SERP feature opportunities.
---

# SERP Top 20 Analyser

Analyse top 20 ranking pages for a target keyword to extract structural patterns and competitive insights.

## Overview

This skill:
1. Fetches top 20 organic SERP results for a target keyword
2. Extracts H1, H2, H3 heading structures from each page
3. Identifies common heading patterns (40%+ frequency)
4. Calculates word count ranges (min, max, median)
5. Detects SERP features (featured snippet, PAA, video, images)
6. Outputs structural recommendations for content planning

## Inputs

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `keyword` | string | ✅ | Target keyword to analyse |
| `location` | string | ✅ | Location for SERP (e.g., "United Kingdom") |
| `language` | string | ✅ | Language for SERP (e.g., "English") |
| `competitors` | array | ❌ | URLs to exclude from analysis |
| `min_results` | integer | ❌ | Minimum results to analyse (default: 20) |

## Outputs

| Output | Format | Description |
|--------|--------|-------------|
| SERP Analysis | JSON | Top 20 results with URLs, titles, positions |
| Heading Structure | JSON | H1/H2/H3 structures extracted from each page |
| Pattern Analysis | JSON | Common heading patterns (40%+ frequency) |
| Word Count Stats | JSON | Min, max, median, quartiles |
| SERP Features | JSON | Featured snippet, PAA, video, images detected |
| Recommendations | Markdown | Structural recommendations for content planning |

## API Dependencies

- **DataForSEO SERP API**: `serp/google/organic/live/advanced`
- **DataForSEO On-Page API**: `on_page/content_parsing`

## Process

### Step 1: Fetch SERP Results

Use DataForSEO SERP API:

```python
api_post("serp/google/organic/live/advanced", [{
    "keyword": keyword,
    "location_name": location,
    "language_name": language,
    "max_crawl_pages": 10
}])
```

### Step 2: Extract Heading Structures

For each organic result URL:
1. Fetch page content using On-Page API
2. Extract H1, H2, H3 headings
3. Normalise headings (lowercase, remove numbers)
4. Store structure

### Step 3: Pattern Detection

Identify patterns appearing on 40%+ of pages:
- Common H2 headings (e.g., "What is X", "How to X")
- Common H3 subtopics
- Heading order patterns

### Step 4: Word Count Analysis

Calculate:
- Minimum word count
- Maximum word count
- Median word count
- 25th and 75th quartiles
- Recommended range

### Step 5: SERP Feature Detection

Detect:
- Featured snippet present?
- People Also Ask questions?
- Video carousel?
- Image pack?
- Local pack?

## Example Usage

```bash
serp_top20_analyser --keyword "bad credit car finance" --location "United Kingdom" --language "English"
```

## Output Format

```json
{
  "keyword": "bad credit car finance",
  "analysis_date": "2026-04-08",
  "results_analysed": 20,
  "heading_patterns": {
    "h1_patterns": [
      {"pattern": "bad credit car finance", "frequency": 0.85}
    ],
    "h2_patterns": [
      {"pattern": "what is bad credit car finance", "frequency": 0.65},
      {"pattern": "eligibility requirements", "frequency": 0.55},
      {"pattern": "how to apply", "frequency": 0.45}
    ]
  },
  "word_count_stats": {
    "min": 800,
    "max": 3500,
    "median": 1800,
    "recommended_range": "1500-2500"
  },
  "serp_features": {
    "featured_snippet": true,
    "people_also_ask": true,
    "video_carousel": false,
    "image_pack": false
  }
}
```

## Constraints

- Do NOT scrape pages directly — use DataForSEO API
- Do NOT include competitor URLs from exclude list
- Minimum 10 results for pattern analysis
- Maximum 30 results per analysis
- Do NOT store page content — only extracted structures

## Error Handling

- If SERP API fails, retry with exponential backoff
- If On-Page API fails for a URL, skip that result
- If fewer than 10 results available, warn user