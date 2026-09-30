---
name: news-monitor
description: RSS-based news monitoring and weekly digest generation. Fetches from multiple sources, deduplicates against previously published articles, and delivers summaries to Slack. Use when: (1) creating weekly news digests, (2) monitoring specific topics, (3) generating agent news briefings. Triggers: news digest, weekly news, news monitoring, RSS.
---

# News Monitor Skill

RSS-based news monitoring with deduplication.

## Weekly Digest Workflow

1. Fetch from 10+ RSS sources
2. Filter for relevant topics (AI, tech, SEO, business)
3. Deduplicate against previously published
4. Generate summary digest
5. Post to Slack news channel

## RSS Sources

| Source | URL | Category |
|--------|-----|----------|
| TechCrunch | https://techcrunch.com/feed/ | Tech |
| The Verge | https://www.theverge.com/rss/index.xml | Tech |
| Ars Technica | https://feeds.arstechnica.com/arstechnica/index | Tech |
| Hacker News | https://news.ycombinator.com/rss | Tech/Startup |
| MIT Tech Review | https://www.technologyreview.com/feed/ | Tech/AI |
| Wired | https://www.wired.com/feed/rss | Tech |
| SEO Blog | https://searchengineland.com/feed | SEO |
| Moz Blog | https://moz.com/blog/feed | SEO |
| AI News | https://venturebeat.com/category/ai/feed/ | AI |
| Reddit r/technology | https://www.reddit.com/r/technology/.rss | Community |

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/fetch-feeds.sh` | Fetch all RSS feeds |
| `scripts/parse-feed.py` | Parse RSS to JSON |
| `scripts/dedup.py` | Filter out published |
| `scripts/digest.py` | Generate digest markdown |
| `scripts/post-slack.sh` | Post to Slack |

## Usage

```bash
# Fetch and process all feeds
./scripts/fetch-feeds.sh

# Generate digest from fetched data
./scripts/digest.py --topic "AI" --limit 20

# Post to Slack
./scripts/post-slack.sh "#news-channel" "Digest content"
```

## Deduplication

Store published article IDs in:
```
~/.openclaw/workspace/cron/news/published-articles.json
```

Format:
```json
{
  "published": ["article-id-1", "article-id-2"],
  "last_updated": "2026-04-07T10:00:00Z"
}
```

## Cron Setup

Weekly cron job:
```json
{
  "id": "weekly-news-digest",
  "name": "Weekly News Digest",
  "schedule": "0 9 * * 1",  // Monday 9am UK
  "task": "news-monitor",
  "channel": "C0AF81MBTB4"
}
```

## Output Format

```markdown
## Weekly News Digest - [Date]

### Top Stories
1. [Article Title](url) - *Source*
   Brief summary...

### AI & Automation
...

### SEO & Content
...

### Tech Trends
...

### Community Highlights
...

---
*Generated: [timestamp]*
```

## See Also

- `references/feed-sources.md` - Full RSS source list
- `references/digest-template.md` - Digest template