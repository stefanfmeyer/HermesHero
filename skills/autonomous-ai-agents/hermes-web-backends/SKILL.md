---
name: hermes-web-backends
description: "Configure Hermes Agent web search and extract backends — DDGS (free search), Tavily/Firecrawl/Exa/Parallel (extract), self-hosted options, and the config key separation between search and extract."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [hermes, web, search, extract, ddgs, firecrawl, tavily, configuration]
    related_skills: [hermes-agent]
---

# Hermes Web Backends

Configure which providers Hermes uses for `web_search` (search the web for results) and `web_extract` (fetch full page content from URLs). These are **independent capabilities** — you can mix-and-match providers (e.g. DDGS for search + Tavily for extract).

## Config Keys

```bash
# Shared fallback (used when neither capability-specific key is set)
hermes config set web.backend <name>

# Per-capability overrides (take priority over web.backend)
hermes config set web.search_backend <name>    # for web_search
hermes config set web.extract_backend <name>   # for web_extract
```

Selection priority for each capability:
1. `web.{capability}_backend` if set AND available
2. `web.backend` (shared fallback)
3. Auto-detect from env vars

**Always set both `web.search_backend` and `web.extract_backend` explicitly** when using different providers for each. Don't rely on `web.backend` alone if you need search-only + extract-capable split.

## Capability Matrix

| Backend | Search | Extract | API Key / Env | Free? |
|---------|--------|---------|---------------|-------|
| **ddgs** | ✅ | ❌ | None (pip package) | ✅ Free |
| **brave-free** | ✅ | ❌ | `BRAVE_SEARCH_API_KEY` | Free tier (2K/mo) |
| **searxng** | ✅ | ❌ | `SEARXNG_URL` | ✅ Free (self-hosted) |
| **xai** | ✅ | ❌ | `XAI_API_KEY` or OAuth | Paid |
| **firecrawl** | ✅ | ✅ | `FIRECRAWL_API_KEY` or `FIRECRAWL_API_URL` | Paid / Free (self-hosted) / Free (Nous Portal managed) |
| **tavily** | ✅ | ✅ | `TAVILY_API_KEY` | Free tier (1K extracts/mo) |
| **exa** | ✅ | ✅ | `EXA_API_KEY` | Free tier (limited) |
| **parallel** | ✅ | ✅ | `PARALLEL_API_KEY` | Paid |

**Key point:** DDGS, Brave Free, SearXNG, and xAI are **search-only** — they cannot extract page content. If `web_extract` is called with one of these as the extract backend, Hermes returns a clear "search-only backend" error.

## DDGS (Free Search — Recommended Default)

### Installation

```bash
pip install ddgs    # ← package is literally named "ddgs"
```

### ⚠️ Package Name Gotcha

There are TWO DuckDuckGo packages on PyPI:
- `ddgs` (v9.x) — **this is the one Hermes expects**. The code does `import ddgs`.
- `duckduckgo-search` (v8.x) — **wrong package**, different import name. Installing this does NOT satisfy Hermes's `_ddgs_package_importable()` check.

If `web_search` returns `"ddgs package is not installed — run pip install ddgs"`, you installed the wrong package. Run `pip install ddgs`.

### Configuration

```bash
pip install ddgs
hermes config set web.search_backend ddgs
# Also set web.backend as fallback (optional if search_backend is set)
hermes config set web.backend ddgs
```

No API key needed. DDGS is completely free.

### Limitations

- Search-only (`supports_extract() = False`)
- Rate-limited by DuckDuckGo (not suitable for high-volume batches)
- Results are metadata only (title, URL, description) — no page content

## Free web_extract Options

Since DDGS cannot extract, you need a separate extract backend. Free paths in order of recommendation:

### 1. Tavily Free Tier (Easiest — Recommended Primary)

1. Sign up at https://app.tavily.com
2. Get API key from dashboard
3. Add to `~/.hermes/.env`: `TAVILY_API_KEY=<key>`
4. `hermes config set web.extract_backend tavily`
5. Restart gateway (`/restart` in Discord)

Free tier: 1,000 extracts/month. Sufficient for typical agent use. Good content depth (grabs more of the page than Jina), 400-900ms response time.

### 2. Jina Reader (Free Fallback — Custom Plugin)

Free, no API key required (but recommended — removes rate limits). Cleanest output, 3.5x less tokens than Tavily on JS-heavy pages. Works on `https://r.jina.ai/<url>`.

**Files to create at `~/.hermes/plugins/web/jina/`:**

`__init__.py`:
```python
"""Jina Reader web extract plugin — user-installed, opt-in via plugins.enabled."""
from plugins.web.jina.provider import JinaReaderProvider

def register(ctx) -> None:
    ctx.register_web_search_provider(JinaReaderProvider())
```

`plugin.yaml`:
```yaml
name: web-jina
version: 1.0.0
description: "Jina Reader (r.jina.ai) web content extraction. Free tier: 1M tokens/mo with API key, ~20 RPM without."
author: user
kind: backend
provides_web_providers:
  - jina
```

`provider.py`: extends `WebSearchProvider` from `agent.web_search_provider`, implements `extract()` only. Key implementation details:

- API: `GET https://r.jina.ai/{url}` (keep `https://` in the URL — stripping it makes Jina return `http://` in links)
- Auth: `Authorization: Bearer $JINA_API_KEY` header (optional, recommended)
- Do NOT set `X-Return-Format: markdown` — it makes Jina return the full unstripped page (26K chars vs 7K clean)
- Parse response: lines start with `Title:`, `URL Source:`, `Published Time:`, then `Markdown Content:` header, then the actual content
- Return shape: `[{"url", "title", "content", "raw_content", "metadata"}, ...]`

Enable with: `hermes plugins enable web-jina`

Swap to Jina: `hermes config set web.extract_backend jina` then `/restart`.

**Recommended setup:** Tavily as primary (`web.extract_backend: tavily`), Jina as fallback. Swap manually if Tavily hits rate limits or fails.

### 3. Self-Hosted Firecrawl (Unlimited — ⚠️ Heavy RAM)

1. Clone the repo and run `docker compose up -d` from the firecrawl repo
2. Add to `~/.hermes/.env`: `FIRECRAWL_API_URL=http://localhost:3002`
3. `hermes config set web.extract_backend firecrawl`
4. Restart gateway

No API key needed for self-hosted. Unlimited extracts.

**⚠️ RAM requirements (verified from official docker-compose.yaml):**
Firecrawl is NOT a single container — it runs 6+ services:

| Service | Configured mem_limit |
|---------|----------------------|
| Playwright (headless Chrome) | 4 GB |
| API server + worker | 8 GB |
| Redis | ~100 MB |
| RabbitMQ | ~256 MB |
| PostgreSQL / FoundationDB | ~256 MB |
| **Total configured** | **~13 GB** |

Even idle, expect 2-4 GB minimum. **Do NOT run on hosts with <16 GB RAM** alongside other services. On the workstation (8 GB) this is a non-starter. Could work on the mini-lab EliteDesk (32 GB) if dedicated.

**Does NOT need 24/7** — can `docker compose up` / `docker compose down` on demand, but cold-start takes 30-60s and Hermes can't auto-start it when extract is needed.

### 3. Nous Portal Managed Firecrawl

1. Run `hermes auth` → add Nous Portal credentials
2. `hermes config set web.extract_backend firecrawl`
3. `hermes config set web.use_gateway true`
4. Restart gateway

Free if you have a Nous Portal subscription. The managed gateway handles Firecrawl API calls.

## Verification

After configuring, test both capabilities:

```bash
# Check config
hermes config get web

# Test search (should return JSON with results)
# In a session, use web_search tool with a simple query

# Test extract (should return page content)
# In a session, use web_extract tool with a known URL
```

## Pitfalls

- **Wrong ddgs package**: `pip install duckduckgo-search` installs the wrong thing. Hermes needs `pip install ddgs`.
- **Search-only backend for extract**: Setting `web.extract_backend: ddgs` will fail with a "search-only backend" error. Always pair DDGS with a real extract backend.
- **Self-hosted Firecrawl RAM**: The official docker-compose allocates ~13 GB across 6 containers (Playwright 4GB, API 8GB, Redis, RabbitMQ, Postgres). Even idle needs 2-4 GB. Do NOT attempt on hosts with <16 GB RAM. See `references/extract-alternatives.md` for the full breakdown.
- **Config changes need restart**: In gateway mode, run `/restart` in Discord after changing web config. In CLI, exit and relaunch.
- **No env vars set = broken web tools**: If no backend env vars are configured, both `web_search` and `web_extract` will fail. DDGS is the only backend that needs no env var (just the pip package).
- **Firecrawl dual auth**: Firecrawl supports both direct (`FIRECRAWL_API_KEY`) and managed gateway (`web.use_gateway: true`) paths. `check_firecrawl_api_key()` returns True if EITHER is configured.
- **Jina scheme stripping**: passing `r.jina.ai/example.com` (no scheme) makes Jina return `http://` in the `URL Source` header and all relative links. Always pass the full URL with `https://`.
- **Jina `X-Return-Format: markdown`**: this header makes Jina include the nav/footer in the output (26K chars for a typical page). Leave it off for clean extraction (7K chars).
- **Jina plugin needs `plugins.enabled`**: user-installed plugins at `~/.hermes/plugins/` are opt-in. Run `hermes plugins enable web-jina` after creating the files.

## Browser Automation as Extract Fallback

When no `web_extract` backend is configured, the built-in `browser` toolset
(`browser_navigate` + `browser_snapshot` with `full=true`) can extract page
content from any URL — including JS-rendered pages. Heavier on RAM
(~500MB-1GB per session) and slower (~5-10s per page), but zero setup and
handles any page a real browser can. Best for occasional extraction or
JS-heavy pages when no API backend is available.

## See Also

- `references/backend-matrix.md` — detailed per-provider notes, source code references, and extract capability verification
- `references/extract-alternatives.md` — Jina Reader (free, no key), Olostep, browser fallback, and a comparison ranking for low-RAM hosts
- Hermes Agent docs: https://hermes-agent.nousresearch.com/docs/user-guide/features/web-search
- The `hermes-agent` skill for general Hermes configuration