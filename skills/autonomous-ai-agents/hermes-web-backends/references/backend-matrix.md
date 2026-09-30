# Web Backend Matrix — Source Code Reference

Verified against `~/.hermes/hermes-agent/tools/web_tools.py` and
`~/.hermes/hermes-agent/plugins/web/*/provider.py` on 2026-07-23.

## Provider Plugin Locations

All 8 web providers live as plugins under `plugins/web/`:

```
plugins/web/
├── brave_free/provider.py
├── ddgs/provider.py
├── exa/provider.py
├── firecrawl/provider.py
├── parallel/provider.py
├── searxng/provider.py
├── tavily/provider.py
└── xai/provider.py
```

## supports_extract() Values

| Provider | supports_extract() | Source line |
|----------|-------------------|-------------|
| brave_free | False | `brave_free/provider.py:59` |
| ddgs | False | `ddgs/provider.py:298` |
| exa | True | `exa/provider.py:112` |
| firecrawl | True | `firecrawl/provider.py:388` |
| parallel | True | `parallel/provider.py:167` |
| searxng | False | `searxng/provider.py:65` |
| tavily | True | `tavily/provider.py:150` |
| xai | False | `xai/provider.py:143` |

## Availability Checks (_is_backend_available)

Each backend's availability probe (`_is_backend_available` in web_tools.py):

- **exa**: `_has_env("EXA_API_KEY")`
- **parallel**: `_has_env("PARALLEL_API_KEY")`
- **firecrawl**: `check_firecrawl_api_key()` → `_has_direct_firecrawl_config() or _is_tool_gateway_ready()`
- **tavily**: `_has_env("TAVILY_API_KEY")`
- **searxng**: `_has_env("SEARXNG_URL")`
- **brave-free**: `_has_env("BRAVE_SEARCH_API_KEY")`
- **ddgs**: `_ddgs_package_importable()` — tries `import ddgs`, returns True/False
- **xai**: `has_xai_credentials()` from `tools.xai_http` (env var OR auth.json OAuth tokens)

## Firecrawl Dual Auth

Firecrawl supports three auth paths:

1. **Direct API key**: `FIRECRAWL_API_KEY` in `.env`
2. **Self-hosted URL**: `FIRECRAWL_API_URL` in `.env` (no key needed)
3. **Nous Portal managed gateway**: `web.use_gateway: true` in config + Nous OAuth token

`check_firecrawl_api_key()` returns True if ANY of these are configured.
`_has_direct_firecrawl_config()` checks paths 1+2.
`_is_tool_gateway_ready()` checks path 3 via `resolve_managed_tool_gateway("firecrawl", ...)`.

## DDGS Package vs duckduckgo-search

Two distinct PyPI packages:

- `ddgs` (v9.14.4) — import name `ddgs`, what Hermes expects
- `duckduckgo-search` (v8.1.1) — import name `duckduckgo_search`, NOT recognized by Hermes

The `_ddgs_package_importable()` helper in web_tools.py does `import ddgs` — it will
fail with `duckduckgo-search` installed because that package uses a different import name.

## Config Resolution Flow

```
_get_search_backend() → _get_capability_backend("search")
_get_extract_backend() → _get_capability_backend("extract")

_get_capability_backend(capability):
  1. Read web.{capability}_backend from config
  2. If set and _is_backend_available(name) → return it
  3. Else fall through to _get_backend() (shared auto-detect)
```

## web_extract Error Messages

When extract fails, the error messages are specific:

- **Search-only backend configured for extract**: `"{provider} is a search-only backend and cannot extract URL content. Set web.extract_backend to firecrawl, tavily, exa, or parallel."`
- **No extract provider**: `"No web extract provider configured. Set web.extract_backend to firecrawl, tavily, exa, or parallel."`
- **Plugin disabled**: `"web.extract_backend is set to '{vendor}', but its plugin ('{key}') is disabled in config. Re-enable it with hermes plugins enable {key}"`

## Recommended Free Setup

```
# Search (free, no API key)
pip install ddgs
hermes config set web.search_backend ddgs

# Extract (free tier, needs API key)
# Sign up at app.tavily.com, add TAVILY_API_KEY to .env
hermes config set web.extract_backend tavily

# Verify
hermes config get web
# Should show:
#   backend: ddgs
#   search_backend: ddgs
#   extract_backend: tavily
```