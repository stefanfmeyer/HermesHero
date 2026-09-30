# Hindsight Setup — Detailed Guide

Hindsight is the long-term memory system: an HTTP daemon (port 9177 for the `hermes` profile) backed by an embedded PostgreSQL instance. Hermes talks to it over `http://localhost:9177`. It extracts durable facts from conversations, stores them as structured memories, consolidates duplicates over time, and serves semantic recall.

This file covers everything `../SETUP.md` section 3-5 compresses, plus every pitfall learned running it 24/7.

## Architecture

```
Hermes Agent ──HTTP──> Hindsight daemon (port 9177)
                          │
                          ├── embedded PostgreSQL (~/.pg0/instances/hindsight-embed-hermes)
                          ├── embeddings + cross-encoder models (downloaded on first start)
                          └── LLM provider (fact extraction) — any OpenAI-compatible endpoint

Supervision (three layers):
  1. systemd unit (systemd/hindsight-embed.service) → runs supervisor script, Restart=always
  2. scripts/hindsight-supervisor.sh → polls /health, restarts daemon on failure
  3. cron pre-flight health check → last line of defence before any API call
```

## Install

```bash
# Python package into the Hermes venv (NOT plain pip — keep it in Hermes' environment)
~/.hermes/hermes-agent/venv/bin/pip install hindsight-embed

# uv — provides `uvx`, which the daemon shells out to (`uvx hindsight-api@x.x.x`)
curl -LsSf https://astral.sh/uv/install.sh | sh
# uvx lands in ~/.local/bin — make sure that's on PATH for the service user

# systemd service + supervisor (see ../SETUP.md section 4)
```

## Configuration

**The real runtime config is `~/.hindsight/profiles/hermes.env`** (loaded by the systemd unit via `EnvironmentFile=`). A `~/.hermes/hindsight/config.json` may also exist — it is effectively decorative; editing it alone changes nothing.

```bash
~/.hermes/hermes-agent/venv/bin/hindsight-embed -p hermes profile set-env hermes HINDSIGHT_API_LLM_PROVIDER "openai"
~/.hermes/hermes-agent/venv/bin/hindsight-embed -p hermes profile set-env hermes HINDSIGHT_API_LLM_MODEL "<your-model>"
~/.hermes/hermes-agent/venv/bin/hindsight-embed -p hermes profile set-env hermes HINDSIGHT_API_LLM_BASE_URL "<your-openai-compatible-endpoint>"
~/.hermes/hermes-agent/venv/bin/hindsight-embed -p hermes profile set-env hermes HINDSIGHT_API_LLM_API_KEY "<your-key>"
```

### Provider choice (IMPORTANT)

Use `HINDSIGHT_API_LLM_PROVIDER=openai` (the OpenAI-compatible path) even if the upstream is Ollama, Ollama Cloud, OpenRouter, etc. The native `ollama` provider routes through `/api/chat` with `think: False`, and **reasoning models emit reasoning prose inside `message.content` anyway**, which breaks the JSON fact parser with `JSONDecodeError`. The OpenAI-compatible path separates reasoning into its own field and `content` stays clean JSON.

Any small, fast, JSON-reliable model works for fact extraction. Test for: valid JSON under a format instruction, <10s per call, relevant non-duplicate facts.

## First start

```bash
~/.hermes/hermes-agent/venv/bin/hindsight-embed -p hermes daemon start
```

**Cold start takes 60-120 seconds.** In order: embeddings init → cross-encoder model download (HuggingFace, first run only) → embedded PostgreSQL start (`~/.pg0/instances/hindsight-embed-hermes`) → Alembic migrations → "Uvicorn running on http://...". Don't poll `/health` before 60s; watch the log instead:

```bash
tail -f ~/.hindsight/profiles/hermes.log
```

Verify:

```bash
curl -s localhost:9177/health
# {"status":"healthy","database":"connected"}
```

## Ports and profiles

- Port **9177** = `hermes` profile (what Hermes and all scripts expect)
- Port **8888** = default profile (only if you start without `-p hermes`)
- Always pass `-p hermes` when starting the daemon manually, or the scripts will be talking to nothing.

## Supervision

`systemd/hindsight-embed.service` + `scripts/hindsight-supervisor.sh`:

- `Type=simple` running the supervisor script — **do not** convert to `Type=forking`; forking daemons report "active (exited)" success and then die unsupervised.
- `START_TIMEOUT=240` in the supervisor — cold start (~150s) is longer than you'd guess; lowering this causes the supervisor to kill the daemon mid-startup and stampede (see below).
- `loginctl enable-linger $USER` is required for the user service to survive logout.

Verified recovery test: `kill -9` the daemon → supervisor detects within ~30s → fresh daemon → health 200.

### Failure modes (all verified in production)

**Crash loop vs slow startup.** If the log shows init lines repeating every 40-60s with no "Uvicorn running on" ever appearing, it's a crash loop — stop polling, stop the unit, and debug (corrupt Postgres instance, OOM, version mismatch). A *slow start* shows each init step once.

**Supervisor stampede.** If the supervisor's `START_TIMEOUT` is shorter than real cold start, it kills each attempt mid-init and starts another, and multiple supervisors end up killing each other's daemons. Signature: "Supervisor starting" lines every 40-90s, never followed by "Daemon healthy". Recovery: stop the unit, `pkill -9` all hindsight processes, start the daemon once manually, wait a full 120s before checking health, then restart the unit.

**OOM crash loop.** On hosts with ≤4GB RAM and no swap, the kernel kills the daemon every ~30s (restart counter in the hundreds). Fix: add swap first (`fallocate -l 4G /swapfile` etc.), optionally cap the unit with `MemoryMax=512M`, then start. Check `journalctl --user | grep -i oom`.

**Silently-broken recall (`ModuleNotFoundError`).** Health is green but recall 500s: the daemon was launched via `uvx`, whose extracted package archive under `~/.cache/uv/archive-v0/<hash>/` got pruned by a cache clean while the daemon still held modules in memory; a lazy import then fails. Fix: kill the daemon — the supervisor restarts it and `uvx` re-extracts a fresh archive. Prevention: don't run aggressive `uv cache clean` on hosts running Hindsight, or pin the daemon to a persistent venv.

**Env changes don't apply.** The LLM model/key are snapshotted into the daemon's process environment at start. Editing `hermes.env` alone changes nothing. `systemctl --user restart hindsight-embed`, then prove the *running* process:

```bash
cat /proc/$(pgrep -f "hindsight-api.*--daemon" | head -1)/environ | tr '\0' '\n' | grep HINDSIGHT_API_LLM_MODEL
```

## Using the API

```bash
# Retain (store facts) — ALWAYS async; sync calls timeout
curl -s -X POST http://localhost:9177/v1/default/banks/hermes/memories \
  -H "Content-Type: application/json" \
  -d '{"async": true, "items": [{"content": "fact text", "context": "label", "tags": ["t1"]}]}'

# Recall — fact text comes back in the "text" field (NOT "content")
curl -s -X POST http://localhost:9177/v1/default/banks/hermes/memories/recall \
  -H "Content-Type: application/json" \
  -d '{"query": "search terms", "top_n": 5}'

# Reflect — synthesize an answer across all stored memories
curl -s -X POST http://localhost:9177/v1/default/banks/hermes/memories/reflect \
  -H "Content-Type: application/json" \
  -d '{"query": "question"}'
```

Notes:
- Batch ≤ ~10 items per retain call; 1 item per request at bulk scale, 0.3s between calls.
- Per-item content cap is 10KB; 8KB chunks are the practical safe size.
- Hindsight auto-deduplicates and consolidates related facts into observations over time — no need to check for existing facts before retaining.
- If Hermes' built-in `hindsight_retain`/`hindsight_recall` tools error with `cannot import name 'HindsightEmbedded'` on a fresh install, that's a broken Python client package — the direct HTTP API above works regardless.

## Data locations

| Path | Contents |
|------|----------|
| `~/.hindsight/` | profiles (`hermes.env`, logs), bank metadata |
| `~/.pg0/` | embedded PostgreSQL data (the memories themselves) |
| `~/.hermes/logs/hindsight-systemd.log` | systemd unit output |
| `~/.hermes/scripts/hindsight_daily_ingest.py` | session → facts ingest job |

`~/.hindsight/` is portable across machines (`cp -a`); `~/.pg0/` is platform-specific (Postgres binaries) — on a new OS, start fresh rather than copying it.
