# web_extract Alternatives — Beyond the Built-in Backends

Investigated 2026-07-23 when no free built-in extract backend was available.
These are alternatives outside the Hermes plugin system, documented to save
future investigation time.

## Jina Reader (r.jina.ai) — Free, No API Key

Prepend `https://r.jina.ai/` to any URL to get clean LLM-ready markdown:

```bash
curl -sL "https://r.jina.ai/https://example.com"
```

**Pros:**
- Completely free, no API key required
- ~20 requests/minute rate limit (anonymous, no monthly cap)
- Returns clean markdown with title, URL source, published time
- Handles JS-rendered pages
- With a free API key (jina.ai): 1M tokens/month, higher rate limits

**Cons:**
- NOT a Hermes plugin — would need a custom plugin or `curl` wrapper
- Anonymous access can be blocked per-domain for abuse (GitHub was blocked during testing)
- No structured JSON output (just markdown)
- Rate-limited (20 RPM anonymous vs 500 RPM with key)

**Verdict:** Good enough as a fallback for occasional manual extraction via `curl`.
Not seamless enough to replace a configured `web_extract` backend. If a Jina
Reader Hermes plugin were written, this would be the best zero-config option.

## Olostep — Managed API, Not Built Into Hermes

External scraping API at https://www.olostep.com.

**Pricing:**
- Free trial: 500 scrapes (one-time, NOT monthly)
- Starter: $9/mo for 5K scrapes ($1.80/1K)
- Standard: $99/mo for 200K ($0.495/1K)

**Pros:**
- Clean markdown, HTML, JSON, screenshots, PDFs from any URL
- Python SDK (`pip install olostep`) and CLI
- Cheapest paid tier ($9/mo vs Tavily $30/mo)

**Cons:**
- NOT a Hermes plugin — would need custom plugin development
- Free tier is a one-time 500-scrape bucket, NOT monthly-resetting
- API key required

**Verdict:** Better paid pricing than Tavily, but the one-time free tier is
too small for ongoing use. Not worth writing a plugin unless paying $9/mo.

## Browser Automation — Already Available

Hermes has a built-in `browser` toolset (`browser_navigate`, `browser_snapshot`)
that can extract page content from any URL, including JS-rendered pages.

```python
# In a session:
# browser_navigate to a URL → returns compact accessibility-tree snapshot
# browser_snapshot with full=true → returns complete page content
```

**Pros:**
- Already installed and enabled — zero setup
- Handles any page a real browser can (JS, auth, dynamic content)
- No API key, no rate limits, no external dependency

**Cons:**
- Heavy: ~500 MB-1 GB RAM per browser session
- Slow: 5-10 seconds per page vs <1s for API-based extract
- Not batch-friendly (one page at a time)
- Content comes as accessibility tree, not clean markdown
- Over 15K chars, snapshot gets LLM-summarized or saved to file

**Verdict:** Good for JS-heavy pages or authenticated sessions. Overkill for
simple page extraction. Use as a fallback when no extract API backend is
configured and the page needs JS rendering.

## Summary Ranking (for low-RAM hosts like the workstation)

| Option | Free? | Monthly Quota | RAM | Setup | Hermes-Native |
|--------|-------|--------------|-----|-------|---------------|
| Tavily | ✅ | 1K/mo (resets) | Zero | 2 min | ✅ Built-in |
| Exa | ✅ | ~1K/mo | Zero | 2 min | ✅ Built-in |
| Jina Reader | ✅ | ~20 RPM (no cap) | Zero | curl | ❌ External |
| Browser | ✅ | Unlimited | 500MB-1GB | Already on | ✅ Built-in |
| Olostep | Trial | 500 one-time | Zero | Plugin needed | ❌ External |
| Firecrawl self-host | ✅ | Unlimited | 2-4 GB+ | Docker | ✅ Built-in |