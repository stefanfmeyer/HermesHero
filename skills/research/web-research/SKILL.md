---
name: web-research
description: Web search and scraping for AI agents — uses Obscura headless browser as default, web_search/web_extract for lightweight tasks
trigger: search the web, find stuff on the web, web scrape, scrape a page, look up, find information online, research, find links, browse web, 搜索, 爬取
---

# Web Research — Search & Scrape with Obscura

Default browser engine is **Obscura** (Rust headless browser — 30MB memory, built-in anti-detection, drop-in Puppeteer/Playwright replacement).

## When to Use

| Task | Tool | Why |
|------|------|-----|
| Quick facts / links | `web_search` | Fast, no browser needed |
| Extract content from URLs | `web_extract` | Lightweight, async |
| Interactive / JS-heavy pages | **Obscura** via `browser_navigate` | Real Chrome V8 engine, anti-detect |
| Form submission / login | **Obscura** via `browser_navigate` | Session, cookies, JS |
| CAPTCHAs / visual challenges | `browser_vision` | Screenshot + AI vision |

## Tool Priority Order

1. **`web_search`** — use first for simple queries
2. **`web_extract`** — use for content extraction from static pages
3. **Check for a raw markdown mirror** — many docs sites (Astro, Docusaurus, MkDocs, Nextra) expose a `/{path}.md` endpoint that returns clean markdown. **Always probe this first when scraping documentation sites** — it's 5-10x faster and cleaner than scraping rendered HTML. Discovered by inspecting Astro page metadata (`markdownUrl` in the page-options island).
4. **`browser_navigate`** + `browser_snapshot` — use when page is dynamic, needs JS, or anti-bot protection
5. **`browser_vision`** — use when visual verification is needed (CAPTCHA, complex layouts)

## Markdown Mirror Detection (Astro / Docusaurus / MkDocs)

Many modern documentation sites expose raw markdown at a predictable URL. Always probe before scraping HTML:

```bash
# Astro / Docusaurus / Nextra: append .md to the page path
curl -sI "https://example.com/docs/page-name.md" | head -1
# → HTTP/1.1 200 OK if it works, 404 if not

# MkDocs Material with mike / mdx: usually at the same path
# GitBook: try /__latex/, but no markdown mirror
```

**When a mirror exists:**
- HTML is typically 5-20x larger than the markdown (288KB of Astro JS+CSS vs ~5KB of markdown for a single page)
- You get clean structure: headings, code blocks, tables — no HTML noise to strip
- Fan out via parallel `curl` (or subagent) calls at high concurrency

**Verified working (2026-07-03):** https://botpress.com/docs/studio/introduction/ → 288KB HTML
vs https://botpress.com/docs/studio/introduction.md → 1.6KB clean markdown. Used to index 224 Botpress docs pages in ~40s wall time with 3 parallel subagents.

## Sitemap-Based Full-Corpus Scraping

When the task is "ingest the entire documentation site" (not just a few pages), always start with the sitemap:

```bash
# 1. Find the sitemap index
curl -sL https://example.com/sitemap-index.xml

# 2. Fetch all sub-sitemaps
curl -sL https://example.com/sitemap-0.xml | grep -oP '<loc>\K[^<]+' > /tmp/urls.txt

# 3. Filter to just the section you need
grep '/docs/' /tmp/urls.txt > /tmp/relevant_urls.txt

# 4. Convert paths to .md URLs (if markdown mirror exists)
sed 's|/$|.md|' /tmp/relevant_urls.txt > /tmp/md_urls.txt
```

**For Botpress-style sites:** 419 URLs in sitemap, 224 relevant after filtering (drop ADK, drop individual OpenAPI endpoints, drop duplicates). Categorize by URL prefix to identify sections.

**Then fan out to parallel subagents** (3 per `delegate_task` call — hard limit), each handling a slice of the URL list, fetching with `curl -sL -m 30` and concatenating into one file per section.

### Fallback: When `web_search` / `web_extract` return 400 Bad Request

Both `web_search` and `web_extract` can return `400 Bad Request` (server-side non-JSON response). This is **not** a rate-limit or auth issue — the upstream search/extract endpoint is temporarily failing.

**Immediate fallback:**
```javascript
// 1. Try browser_navigate for the target URL directly
browser_navigate(url="https://example.com")
browser_snapshot()        // read structure
browser_vision()          // read visual content (pricing tables, FAQs)

// 2. For pricing/specific data that requires interaction
browser_scroll(direction="down")
browser_vision(question="Read the pricing table and list every plan, price, and feature")
```

**Example from real session (Conversifi pricing extraction):**
- `web_extract` on `https://conversifi.io/#pricing` → 400 Bad Request
- `browser_navigate` to same URL → success
- `browser_vision` with question → extracted full pricing table ($99 Growth, $999 Agency, custom Scale)
- This pattern recovered data that was otherwise inaccessible.

**Never chain multiple web_search/web_extract retries on 400** — the failure is server-side and likely to persist for the whole session. Pivot to browser tools immediately.

## Quick Search (web_search)

```javascript
// In execute_code:
from hermes_tools import web_search
result = web_search("your query", limit=5)
# Returns: {"data": {"web": [{"url", "title", "description"}, ...]}}
```

## Extract Page Content (web_extract)

```javascript
// In execute_code:
from hermes_tools import web_extract
result = web_extract(["https://example.com", "https://example.org"])
# Returns: {"results": [{"url", "title", "content", "error"}, ...]}
```

## Using Obscura Browser

### Setup (one-time download)

```bash
# macOS Apple Silicon
curl -L https://github.com/h4ckf0r0day/obscura/releases/latest/download/obscura-macos-arm64.tar.gz | tar -xz
chmod +x obscura
./obscura --version  # verify

# Linux
curl -L https://github.com/h4ckf0r0day/obscura/releases/latest/download/obscura-linux-x86_64.tar.gz | tar -xz
chmod +x obscura

# Add to PATH (optional)
mv obscura /usr/local/bin/
```

### Navigate & Snapshot
```javascript
// Navigate to page
browser_navigate(url="https://example.com")

// Get interactive snapshot
browser_snapshot()  // compact view with @e0, @e1 refs

// Get full page content
browser_snapshot(full=true)
```

### Click & Type
```javascript
// Click element by ref
browser_click(ref="@e5")

// Type into input
browser_type(ref="@e3", text="search query")

// Press Enter
browser_press(key="Enter")
```

### Scroll & Extract
```javascript
browser_scroll(direction="down")
browser_scroll(direction="up")
browser_console()  // check for JS errors
```

### Get Images
```javascript
browser_get_images()  // list all images with URLs + alt text
```

## Web Scraping Workflow

### 1. Lightweight (static pages)
```javascript
// execute_code
from hermes_tools import web_extract, web_search

# Search for pages
sites = web_search("site:github.com headless browser rust", limit=5)

# Extract content
data = web_extract([s["url"] for s in sites["data"]["web"]])
for page in data["results"]:
    print(page["title"], page["url"])
```

### 2. Heavy (JS / anti-bot / interactive)
```javascript
# Terminal — download Obscura first
# Then in execute_code or terminal:
import subprocess
import json

# Start Obscura CDP server
proc = subprocess.Popen(["./obscura", "--remote-debugging-port=9222"])

# Use browser tools
browser_navigate(url="https://example.com")
browser_snapshot()

# Close
proc.terminate()
```

### 3. Structured Data Extraction
```javascript
// For repeating patterns, combine browser + execute_code:
from hermes_tools import web_extract

# Get page list
search_results = web_search("site:example.com products", limit=10)

# Extract from each
for result in search_results["data"]["web"]:
    page_data = web_extract([result["url"]])
    # Process...
```

## Anti-Detection (Obscura Advantage)

Obscura has **built-in anti-detection** vs none in standard headless Chrome:

```javascript
// Puppeteer with Obscura
const browser = await puppeteer.launch({
  executablePath: './obscura',  // vs /Applications/Chromium.app
  headless: true,
  args: ['--no-sandbox', '--disable-blink-features=AutomationControlled']
});
```

```javascript
// Playwright with Obscura
const browser = await chromium.launch({
  executablePath: './obscura',
  headless: true,
  args: ['--no-sandbox']
});
```

## Obscura vs Alternatives

| Tool | Memory | Anti-Detect | Best For |
|------|--------|-------------|----------|
| **Obscura** | 30MB | ✅ Built-in | AI agents, stealth scraping |
| Playwright/Chrome | 200+ MB | ❌ | General automation |
| Puppeteer | 200+ MB | ❌ | Google scraping |
| Selenium | 300+ MB | ❌ | Cross-browser testing |

## Common Pitfalls

- **403/Blocked** — try `browser_navigate` with Obscura (anti-detect built-in)
- **CAPTCHA** — use `browser_vision` to analyze, then `browser_type`/`browser_click` to solve
- **JS-heavy pages** — `web_extract` may return empty; switch to `browser_navigate`
- **Rate limiting** — add delays between requests: `time.sleep(2)`
- **Large pages** — use `browser_snapshot(full=false)` for compact view

## PDF Text Extraction — Fallback Chain

When processing PDFs (attachments, downloads, or web PDFs), follow this extraction chain:

```python
# Step 1: Try pdftotext (fastest, best layout preservation)
subprocess.run(["pdftotext", "-layout", pdf_path, "-"], capture_output=True, text=True)

# Step 2: If pdftotext is missing, use pdfplumber (pure Python, common in agent envs)
import pdfplumber
with pdfplumber.open(pdf_path) as pdf:
    for page in pdf.pages:
        text = page.extract_text()

# Step 3: If both fail, use PyPDF2 (always available but lower quality)
import PyPDF2
reader = PyPDF2.PdfReader(pdf_path)
for page in reader.pages:
    text = page.extract_text()
```

**Session evidence (a previous employer PDF, May 2026):**
- `pdftotext` was not installed → pdfplumber extracted 2,584 chars reliably.
- PyPDF2 was available as third fallback but not needed.
https://github.com/h4ckf0r0day/obscura | ~9.1k stars | Rust + V8
