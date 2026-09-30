# Setup Guide

Transfer this system to a new machine. A colleague (or Claude) can follow this top to bottom.

Target layout: everything under `~/.hermes/` (Hermes home) plus Hindsight under `~/.hindsight/`.

---

## 1. Install Hermes Agent

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
hermes --version
```

Docs: https://hermes-agent.nousresearch.com/docs/

## 2. Deploy the skill library

```bash
mkdir -p ~/.hermes
cp -r skills/ ~/.hermes/skills/
chmod +x $(find ~/.hermes/skills -name "*.sh" -o -name "*.py")
hermes skills list | head -20   # verify
```

Skills are auto-discovered. Subdirectory names are organizational only — no registration step.

## 3. Install Hindsight (long-term memory)

Full guide with all pitfalls: **[hindsight/SETUP.md](hindsight/SETUP.md)**. Short version:

```bash
# 1. Python package into the Hermes venv
~/.hermes/hermes-agent/venv/bin/pip install hindsight-embed

# 2. uv (provides `uvx`, which the daemon shells out to)
curl -LsSf https://astral.sh/uv/install.sh | sh   # lands in ~/.local/bin

# 3. Configure the LLM the memory system uses for fact extraction
~/.hermes/hermes-agent/venv/bin/hindsight-embed -p hermes profile set-env hermes HINDSIGHT_API_LLM_PROVIDER "openai"
~/.hermes/hermes-agent/venv/bin/hindsight-embed -p hermes profile set-env hermes HINDSIGHT_API_LLM_MODEL "<your-model>"
~/.hermes/hermes-agent/venv/bin/hindsight-embed -p hermes profile set-env hermes HINDSIGHT_API_LLM_BASE_URL "<your-openai-compatible-endpoint>"
~/.hermes/hermes-agent/venv/bin/hindsight-embed -p hermes profile set-env hermes HINDSIGHT_API_LLM_API_KEY "<your-key>"

# 4. First start (cold start takes 60-120s — downloads models, starts embedded Postgres, runs migrations)
~/.hermes/hermes-agent/venv/bin/hindsight-embed -p hermes daemon start

# 5. Verify
curl -s http://localhost:9177/health
# {"status":"healthy","database":"connected"}
```

Notes:
- The `hermes` profile listens on port **9177** (the default profile would use 8888 — always pass `-p hermes`).
- Any OpenAI-compatible endpoint works for the LLM (Ollama cloud, OpenRouter, OpenAI, a local proxy). Reasoning models should use `HINDSIGHT_API_LLM_PROVIDER=openai` — the native ollama provider breaks their JSON output.

## 4. 24/7 supervision (systemd)

```bash
mkdir -p ~/.hermes/scripts ~/.hermes/logs
cp scripts/hindsight-supervisor.sh scripts/hindsight-keepalive.sh ~/.hermes/scripts/
cp scripts/hindsight_daily_ingest.py ~/.hermes/scripts/
chmod +x ~/.hermes/scripts/*

mkdir -p ~/.config/systemd/user
cp systemd/hindsight-embed.service ~/.config/systemd/user/
systemctl --user daemon-reload
loginctl enable-linger $USER          # CRITICAL: services die on logout without this
systemctl --user enable --now hindsight-embed
systemctl --user status hindsight-embed   # must say "active (running)", NOT "active (exited)"
```

The unit uses `%h` for the home dir, so no path edits are needed. It runs `hindsight-supervisor.sh`, which polls `/health` and restarts the daemon on failure (START_TIMEOUT=240s — cold start is slower than you think; don't lower it).

Verify recovery actually works:

```bash
pkill -9 -f "hindsight-api"   # kill the daemon
sleep 45
curl -s http://localhost:9177/health   # supervisor should have restarted it
```

## 5. Point Hermes at Hindsight

Hermes auto-detects a running Hindsight daemon on port 9177 and injects relevant memories into context. Optionally mirror the template config:

```bash
cp hindsight/config.json.example ~/.hermes/hindsight/config.json
# edit: set llm_model / llm_api_key / llm_api_base to your real values
```

Sanity checks:

```bash
# retain
curl -s -X POST http://localhost:9177/v1/default/banks/hermes/memories \
  -H "Content-Type: application/json" \
  -d '{"async": true, "items": [{"content": "Test fact", "context": "setup verification"}]}'

# recall (fact text comes back in the "text" field)
curl -s -X POST http://localhost:9177/v1/default/banks/hermes/memories/recall \
  -H "Content-Type: application/json" -d '{"query": "test fact", "top_n": 3}'
```

## 6. Configure Hermes itself

`config.yaml.example` and `.env.example` are full reference files with values stripped. Either:

```bash
hermes setup          # interactive wizard (model, tools, gateway), or
hermes model          # pick provider/model
hermes auth add <provider>
```

Worth copying from the examples even if you configure differently:
- `agent.max_turns`, `agent.reasoning_effort`, `terminal.timeout` defaults
- `checkpoints.enabled: true` (enables `/rollback`)
- compression + memory settings

Set the env vars from `.env.example` that you actually need (Discord/Slack tokens for the gateway, API keys for extra providers). Do not paste the whole file blindly — it's a menu, not a requirement.

## 7. Scheduled memory ingest (the cron that makes memory grow)

`hindsight_daily_ingest.py` reads the day's sessions from `~/.hermes/state.db`, extracts durable facts with the LLM, and retains them to Hindsight. Wire it as a Hermes cron:

```bash
hermes cron create "5,20,35,50 * * * *" \
  --name "Hindsight Session Ingest" \
  --prompt "PRE-FLIGHT: run curl -sf -m 5 http://localhost:9177/health ; if it fails run ~/.hermes/scripts/hindsight-keepalive.sh and re-check; if still unhealthy after 2 attempts report the failure and EXIT. Then run: python3 ~/.hermes/scripts/hindsight_daily_ingest.py — report extracted/retained counts."
```

Keep the pre-flight — it's the last line of defence against silent ingest failures.

## 8. Optional operational scripts

| Script | Purpose | Suggested cron |
|--------|---------|----------------|
| `health-check.sh` | RAM/CPU/disk/temps/service health; silent when healthy | `*/15 * * * *` |
| `dev-reaper.sh` | Kills idle dev servers (Vite/uvicorn/LSP) after 60 min | `*/15 * * * *` |
| `storage-manager.sh` | Storage sweep + weekly report | daily `0 3 * * *` |

All print human-readable reports; all are safe to run manually.

## 9. Verify everything

```bash
hermes doctor                      # deps + config
hermes skills list | wc -l         # ~90+ skills
systemctl --user status hindsight-embed   # active (running)
curl -s localhost:9177/health      # healthy
hermes                             # start a chat, ask it something, check `hermes memory status`
```

## Troubleshooting quick hits

- **Daemon startup looks hung** — cold start takes 60-120s (model downloads + embedded Postgres + migrations). Watch `tail -f ~/.hindsight/profiles/hermes.log`; wait for "Uvicorn running on".
- **Repeated init lines every ~40s, port never binds** — crash loop or supervisor stampede. Stop the unit, `pkill -9 -f hindsight`, start the daemon once manually, wait a full 120s before checking health.
- **Health green but recall 500s with `ModuleNotFoundError`** — the uvx archive the daemon runs from was pruned. Kill the daemon; the supervisor restarts it with a fresh extraction.
- **OOM crash loops on small hosts** — add swap before running Hindsight; the daemon needs ~600MB and Postgres adds more.
- **Config changes don't apply** — the model env is snapshotted at daemon start; `systemctl --user restart hindsight-embed` after editing `~/.hindsight/profiles/hermes.env`, then verify the running process env.

Full failure-mode documentation: `skills/memory/hindsight-integration/SKILL.md`.
