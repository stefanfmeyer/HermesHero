# Hindsight Fresh Install on a New Host

Verified 2026-07-23 on Debian 13 Trixie (the workstation, HP ProDesk 600 G3, 8GB RAM).

## Prerequisites

### 1. Install hindsight-embed into the Hermes venv

```bash
~/.hermes/hermes-agent/venv/bin/pip install hindsight-embed
```

This installs the CLI wrapper. The actual `hindsight-api` server is fetched on-demand by `uvx`.

### 2. Install uv (provides uvx)

**CRITICAL — without this, the daemon cannot start.**

`hindsight-embed daemon start` shells out to `uvx hindsight-api@0.8.5 --daemon --port 9177`.
Without `uv`/`uvx` on PATH, the daemon exits with:
```
Command not found: uvx
Failed to start daemon
```

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# Installs uv + uvx to ~/.local/bin
# Ensure ~/.local/bin is on PATH for the systemd service
```

### 3. Set up profile env vars via CLI

**Use the `profile set-env` CLI — NOT manual file editing.** The CLI writes correct
variable names to `~/.hindsight/profiles/hermes.env`. Manual editing gets names wrong.

```bash
HINDSIGHT_BIN=~/.hermes/hermes-agent/venv/bin/hindsight-embed

$HINDSIGHT_BIN -p hermes profile set-env hermes HINDSIGHT_API_LLM_PROVIDER "openai"
$HINDSIGHT_BIN -p hermes profile set-env hermes HINDSIGHT_API_LLM_API_KEY "<ollama-cloud-api-key>"
$HINDSIGHT_BIN -p hermes profile set-env hermes HINDSIGHT_API_LLM_MODEL "glm-5.3-flash:cloud"  # current sanctioned model (2026-09-20)
$HINDSIGHT_BIN -p hermes profile set-env hermes HINDSIGHT_API_LLM_BASE_URL "https://ollama.com/v1"
```

### Env var name gotcha (cost 30 min of debugging)

The base URL env var is `HINDSIGHT_API_LLM_BASE_URL` — NOT `HINDSIGHT_API_LLM_API_BASE`.

The config.py reads:
```python
ENV_LLM_BASE_URL = "HINDSIGHT_API_LLM_BASE_URL"
```

Setting `HINDSIGHT_API_LLM_API_BASE` (wrong name) silently falls back to `openai.com`.
The daemon starts and reports healthy, but all retain operations fail during async
fact extraction with:
```
AuthenticationError: Error code: 401 - Incorrect API key provided
```

The error message masks the real URL (says "openai.com" not "ollama.com"), making it
look like the API key is wrong when actually the base URL wasn't set.

### 4. Install supervisor + keepalive scripts

Copy from the hindsight-integration skill:
- `scripts/hindsight-supervisor.sh` → `~/.hermes/scripts/hindsight-supervisor.sh`
- `scripts/hindsight-keepalive.sh` → `~/.hermes/scripts/hindsight-keepalive.sh`
- `templates/hindsight-embed.service` → `~/.config/systemd/user/hindsight-embed.service`

```bash
chmod +x ~/.hermes/scripts/hindsight-supervisor.sh
chmod +x ~/.hermes/scripts/hindsight-keepalive.sh
systemctl --user daemon-reload
systemctl --user enable hindsight-embed.service
```

### 5. Move data to HDD (if SSD/HDD split architecture)

```bash
systemctl --user stop hindsight-embed.service
pkill -9 -f "hindsight-api" 2>/dev/null
pkill -9 -f "postgres.*hindsight" 2>/dev/null
sleep 5

mv ~/.hindsight /mnt/storage/hermes/hindsight_data
ln -s /mnt/storage/hermes/hindsight_data ~/.hindsight

mv ~/.pg0 /mnt/storage/hermes/pg0_data
ln -s /mnt/storage/hermes/pg0_data ~/.pg0

systemctl --user start hindsight-embed.service
```

### 6. Wait for cold start (60-120s)

The daemon needs time for:
1. `uvx` to download/cache `hindsight-api` package (first run only, ~10s)
2. Embedded PostgreSQL startup (`~/.pg0/instances/hindsight-embed-hermes`)
3. Alembic database migrations
4. Embeddings model initialization (downloads weights from HuggingFace)
5. Cross-encoder/reranker model loading

```bash
# Poll health every 15s for up to 3 minutes
for i in $(seq 1 12); do
    sleep 15
    if curl -sf -m 5 http://localhost:9177/health 2>/dev/null; then
        echo "HEALTHY!"
        break
    fi
done
```

Expected: `{"status":"healthy","database":"connected"}`

### 7. Verify retain + recall

**IMPORTANT:** The Hermes integrated tools (`hindsight_retain`, `hindsight_recall`) may fail on a fresh install with `cannot import name 'HindsightEmbedded' from 'hindsight'`. Use the direct HTTP API (curl) instead — it works 100% reliably. See `references/hindsight-tool-import-error.md` for details.

```bash
# Test retain (async) via direct API
curl -s -X POST http://localhost:9177/v1/default/banks/hermes/memories \
  -H "Content-Type: application/json" \
  -d '{"async": true, "items": [{"content": "Test memory from fresh install", "context": "verification"}]}'

# Wait 15-20s for async processing, then recall
sleep 20
curl -s -X POST http://localhost:9177/v1/default/banks/hermes/memories/recall \
  -H "Content-Type: application/json" \
  -d '{"query": "test memory", "top_n": 3}' | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'{len(d.get(\"results\",[]))} results')
for r in d.get('results', []):
    print(f'- {r.get(\"text\",\"\")[:200]}')
"
```

## RAM Usage

On an 8GB machine (Debian 13, no other heavy services):
- Hindsight daemon: ~1.0-1.4GB RSS (includes embedded PostgreSQL + embeddings model)
- Cold start peak: ~1.4GB
- Steady state: ~1.0GB

With Hermes gateway (~500MB-1GB) + Hindsight (~1.4GB) on 8GB total, you have ~5GB
headroom. Comfortable. The old 4GB VPS OOM-killed Hindsight 901x — 8GB is the minimum
for running both reliably.