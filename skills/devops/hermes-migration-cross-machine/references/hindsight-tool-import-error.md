# Hindsight Tools Import Error on Fresh Install

## Symptom

On a fresh Hindsight install (pip `hindsight-embed` + `uvx hindsight-api`), the Hermes integrated tools `hindsight_retain` and `hindsight_recall` fail with:

```
Failed to store memory: cannot import name 'HindsightEmbedded' from 'hindsight' (unknown location)
```

## Root cause

The `hindsight-embed` pip package (installed into the Hermes venv) and the `hindsight-api` uvx package (fetched on-demand into `~/.cache/uv/archive-v0/.../`) are separate distributions with different module structures. The Hermes tools try to `import HindsightEmbedded from 'hindsight'` (the pip package), but the API server runs from the uvx cache which has a different module layout.

## Fix

Use the direct HTTP API (curl) for retain/recall. It works 100% reliably regardless of package layout:

```bash
# Retain
curl -s -X POST http://localhost:9177/v1/default/banks/hermes/memories \
  -H "Content-Type: application/json" \
  -d '{"async": true, "items": [{"content": "...", "context": "..."}]}'

# Recall
curl -s -X POST http://localhost:9177/v1/default/banks/hermes/memories/recall \
  -H "Content-Type: application/json" \
  -d '{"query": "...", "top_n": 5}'
```

The tools are a convenience layer; the HTTP API is the canonical path. This was verified 2026-07-23 on Debian 13 Trixie — tools failed with import error, but curl worked perfectly for both retain and recall.

## When this may resolve itself

If a future Hermes update bundles a compatible `hindsight` package or the tools are updated to use HTTP-only, this issue will disappear. Check `hindsight_retain` after Hermes updates — if it works, switch back to the tool for convenience.