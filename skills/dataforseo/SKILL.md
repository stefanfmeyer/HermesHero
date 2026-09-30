# DataForSEO Skill

Interact with DataForSEO API v3 for SEO data: SERP queries, keyword rankings, competitor research, and backlink analysis.

## Authentication

DataForSEO uses **Basic Auth** — encode your `login:password` as Base64.

```
Authorization: Basic base64(login:password)
```

Get credentials at: https://app.dataforseo.com/api-access

## Environment Setup

Store credentials in `~/.openclaw/credentials.json`:

```json
{
  "dataforseo": {
    "login": "ben@former-employer.co.uk",
    "password": "968a5fe797ff29f3"
  }
}
```

Or set env vars directly:
```
DATAFORSEO_LOGIN=your_email@example.com
DATAFORSEO_PASSWORD=your_api_password
```

## API Base URL

```
https://api.dataforseo.com/v3/
```

## Common Endpoints

### SERP Google Organic Live (sync, for small batches)
```
POST https://api.dataforseo.com/v3/serp/google/organic/live/advanced
```
Note: payload must be a JSON array of tasks, e.g. `[{"keyword":"seo tools","language_name":"English","location_name":"United Kingdom"}]`

### SERP Google Organic Task POST (async, for large batches)
```
POST https://api.dataforseo.com/v3/serp/google/organic/task_post
GET  https://api.dataforseo.com/v3/serp/google/organic/task_get/{id}
```

### Keyword Rankings
```
POST https://api.dataforseo.com/v3/keywords_data/google/{metric}/task_post
GET  https://api.dataforseo.com/v3/keywords_data/google/{metric}/task_get/{id}
```

Metrics: `organic`, `search_volume`, `keyword_info`

### Locations & Languages
```
GET https://api.dataforseo.com/v3/serp/google/locations
GET https://api.dataforseo.com/v3/serp/google/languages
```

## Bash Helper Script

```bash
#!/bin/bash
# Usage: dfseo_auth "login" "password"
# Returns: base64-encoded auth header value
echo -n "$1:$2" | base64
```

## Rate Limits

- Rate limit headers: `X-RateLimit-Limit` and `X-RateLimit-Remaining`
- Results stored for 30 days (standard method)
- Live method: not stored

## Pricing

~ $0.0006 per SERP query (varies by request type). Check https://dataforseo.com/pricing

## When to Use

- SERP tracking and rank monitoring
- Keyword research (volume, difficulty, CPC)
- Competitor analysis
- Backlink data
- On-page analysis
