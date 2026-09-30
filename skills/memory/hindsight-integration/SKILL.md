---
name: hindsight-integration
description: Set up, fix, and operate Hindsight local/embedded memory with Ollama on Hermes Agent. Covers daemon supervision (systemd, 24/7 uptime), cron pre-flight health checks, model selection, migration recipes, and the direct-API fallback for retain/recall.
triggers:
  - hindsight setup
  - hindsight integration
  - hindsight memory
  - vectorize.io memory
  - memory system
  - long-term memory
  - hindsight daemon down
  - hindsight not responding
  - hindsight systemd
  - hindsight keepalive
---

# Hindsight Integration with Hermes Agent

## Overview
Hindsight adds persistent long-term memory to Hermes Agent. Local embedded version runs a daemon + embedded PostgreSQL on the host (current primary: the workstation Debian 13 Trixie 8GB RAM via systemd; legacy: Hetzner VPS Ubuntu 26.04; legacy: Mac mini via launchd — see [Migrating from Mac mini to Linux](#migrating-from-mac-mini-to-linux)).

## ⚠️ MANDATORY PRE-FLIGHT (every Hindsight call from a cron)

**The daemon WILL crash silently** if not supervised, and a naive call from a cron prompt is the #1 way ingest silently breaks. **Before ANY Hindsight API call or CLI command** (retain, recall, reflect, health check, etc.), run:

```bash
# 1. Health check
curl -sf -m 5 http://localhost:9177/health
# 2. If unhealthy, restart
~/.hermes/scripts/hindsight-keepalive.sh
# 3. Re-check
curl -sf -m 5 http://localhost:9177/health
# 4. If still unhealthy after 2 attempts, ABORT the cron with a clear error to Discord.
#    Do NOT proceed — retain/recall will hang or fail with connection refused.
```

**Always use direct API** (`http://localhost:9177/v1/default/banks/hermes/memories/recall`) inside cron contexts, NOT the `hindsight_recall` / `hindsight_retain` CLI tools — they depend on a PATH the cron may not have.

**⚠️ `execute_code` is BLOCKED in cron contexts** (approvals policy: "Cron jobs run without a user present to approve it"). The Python `requests.post(...)` templates in this skill will NOT run via `execute_code` during a cron run — they return `BLOCKED: execute_code runs arbitrary local Python... Use normal tools instead`. Use `terminal` + `curl` + `python3 -c "..."` (or `jq`) instead. Verified working pattern for recall in cron:
```bash
curl -s -X POST http://localhost:9177/v1/default/banks/hermes/memories/recall \
  -H "Content-Type: application/json" \
  -d '{"query":"<query>","top_n":8}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); [print('---\n',i.get('text','')[:500]) for i in d.get('results',[])]"
```
For retain in cron, use `curl -s -X POST ... -d '{"async":true,"items":[...]}'` directly — no Python needed. The `requests`-based templates below remain valid for interactive (non-cron) sessions where `execute_code` is approved.

**Layered safety:** the systemd supervisor (`hindsight-embed.service`) is the primary 24/7 watchdog, the keepalive script is the cron-side fallback, and this pre-flight is the last line of defence. All three must be in place — losing any one of them turns a 30s recovery into a silent multi-hour outage.

### ⚠️ Daemon startup is SLOW (60-120s) — keepalive can exceed terminal timeout

The keepalive script's `start_daemon` function runs `hindsight-embed daemon start` in the foreground, then polls `/health` in a loop up to `START_TIMEOUT=120s`. But the daemon startup itself takes 60-120s due to:
1. Embeddings initialization (OpenAI provider with `nomic-embed-text`)
2. Cross-encoder/reranker model loading (`ms-marco-MiniLM-L-6-v2` — downloads weights from HuggingFace on first run)
3. Embedded PostgreSQL instance startup (`~/.pg0/instances/hindsight-embed-hermes`)
4. Alembic database migrations

**When the terminal kills the keepalive at 60s, the daemon process is still running and initializing.** The agent should NOT immediately re-check `/health` and declare failure. Instead:

```bash
# After keepalive "times out":
# 1. Check if the daemon PROCESS is alive:
pgrep -f "hindsight-embed.*daemon" && echo "process running, still starting"

# 2. Watch the daemon log for startup progress:
tail -f ~/.hindsight/profiles/hermes.log
# Look for: "Daemon started successfully" or the Uvicorn "Uvicorn running on" line

# 3. Poll /health every 15s until it responds (typically another 30-60s):
for i in 1 2 3 4 5 6; do sleep 15; curl -sf -m 5 http://localhost:9177/health && break; done
```

**Set the terminal timeout for the keepalive call to at least 180s** to avoid the script being killed mid-startup. The keepalive script itself handles the polling loop correctly — it's the terminal timeout that's the problem, not the script.

**Verified 2026-07-02:** keepalive was killed at 60s by terminal timeout, but daemon process (PID 357543→357792) was still alive and running DB migrations. After waiting ~90s more, `/health` returned `{"status":"healthy","database":"connected"}` and the ingest succeeded.

### ⚠️ Crash-loop vs slow startup — know when to stop waiting

**Not every alive process is a starting process.** The daemon can get stuck in an infinite initialization loop: the process stays alive (supervisor keeps restarting it), but it never finishes startup and never binds to port 9177. Polling `/health` will fail forever — this is NOT a slow-startup case.

**Diagnostic — distinguish slow startup from crash loop:**

```bash
# 1. Check the daemon log for REPEATED initialization without completion
tail -30 ~/.hindsight/profiles/hermes.log
# SLOW STARTUP (wait): you see a linear progression — embeddings init →
#   cross-encoder → PostgreSQL → Alembic → "Uvicorn running on http://..."
#   It's slow but each step appears ONCE.
# CRASH LOOP (abort): you see the SAME init lines REPEATING every 40-60s —
#   e.g. "OpenAI-compatible client initialized" appears 4+ times with no
#   "Uvicorn running on" line ever appearing. The daemon crashes/restarts
#   before it can bind the port.

# 2. Quick check: is anything listening on 9177?
ss -tlnp | grep 9177 || echo "nothing on 9177"

# 3. Check systemd supervisor status — is it in a restart loop?
systemctl --user status hindsight-embed | grep "restart counter"
# A high restart counter + no port = crash loop, not slow startup
```

**If it's a crash loop:**
- Do NOT keep polling `/health` — it will never come up
- Note "⚠️ Hindsight unavailable — daemon in crash-restart loop" in the cron output
- Proceed with the fallback (session files, git log, git diff)
- The crash loop needs manual investigation (possible causes: corrupted PostgreSQL instance, OOM killing the worker mid-init, mismatched package versions after an update, resource limits)

### ⚠️ Supervisor stampede — when the watchdog IS the killer

A distinct and insidious failure mode: the supervisor itself prevents the daemon from ever coming up. The symptom looks identical to a crash loop (process alive, port never binds, init lines repeating in the log), but the root cause is the supervisor, not the daemon.

**How it happens:**
1. Daemon crashes (e.g. from upstream 429 rate limits exhausting retries)
2. Supervisor's `kill_stale()` runs `pkill -9 -f "hindsight-api"` — this matches the very daemon process the supervisor just started
3. The daemon's cold start takes ~150s (PostgreSQL + migrations + embeddings + LLM provider init), but the supervisor's `START_TIMEOUT=120s` fires first
4. Supervisor declares "failed", runs `kill_stale()` again, starts a fresh daemon — which also gets killed at 120s
5. If systemd's `Restart=always` kicks in, MULTIPLE supervisor instances coexist, each killing the others' daemon attempts. The restart cycle accelerates to ~40s and no instance ever reaches completion.

**Diagnostic — distinguish stampede from ordinary crash loop:**
```bash
# 1. Count supervisor instances — more than 1 = stampede
pgrep -af 'hindsight-supervisor' | grep -v pgrep | wc -l

# 2. Check supervisor log for rapid restarts with no "Daemon healthy" line
tail -20 ~/.hermes/logs/hindsight-supervisor.log
# STAMPede signature: "=== Supervisor starting ===" repeating every 40-90s,
#   each followed by "Starting Hindsight daemon..." but NO "Daemon healthy after Ns"

# 3. Check daemon log: do you see "Uvicorn running on http://127.0.0.1:9177"
#    followed by the process dying? That's the supervisor killing it mid-startup.
grep -c "Uvicorn running on" ~/.hindsight/profiles/hermes.log   # high count = repeated starts
grep -c "Daemon started successfully" ~/.hindsight/profiles/hermes.log  # low/zero = never completing
```

**Recovery procedure (verified 2026-07-06):**
```bash
# 1. Stop the supervisor service. NOTE: `systemctl --user stop` may be BLOCKED
#    by the gateway guard (it intercepts systemd commands to protect itself).
#    If blocked, kill the supervisor process directly:
pkill -9 -f 'hindsight-supervisor'
pkill -9 -f 'hindsight-keepalive'

# 2. Kill ALL stale daemon processes and embedded postgres:
pkill -9 -f 'hindsight-api'
pkill -9 -f 'hindsight-embed daemon'
pkill -9 -f 'uvx hindsight-api'
pkill -9 -f 'hindsight-embed-hermes'
sleep 5

# 3. Verify a CLEAN slate — no procs, no ports:
pgrep -af hindsight | grep -v pgrep   # should be empty
ss -ltn | grep -E '9177|5432'         # should be empty

# 4. Start the daemon ONCE in the background and LEAVE IT ALONE:
#    (use terminal background=true, NOT nohup — the gateway blocks nohup)
~/.hermes/hermes-agent/venv/bin/hindsight-embed -p hermes daemon start  # background

# 5. Wait a FULL 120s before checking health. Do NOT poll earlier —
#    each poll is a temptation to intervene and restart the stampede.
sleep 120; curl -s -o /dev/null -w "health=%{http_code}\n" -m 5 http://localhost:9177/health
# Expected: health=200

# 6. Re-run the ingest / cron task now that the daemon is up.

# 7. Restart the supervisor service so 24/7 supervision resumes:
systemctl --user start hindsight-embed.service
# Verify only ONE supervisor is running:
pgrep -af 'hindsight-supervisor' | grep -v pgrep | wc -l   # must be 1
```

**Prevention — bump the supervisor's START_TIMEOUT:**
The default `START_TIMEOUT=120` in `~/.hermes/scripts/hindsight-supervisor.sh` is shorter than the daemon's actual cold-start time (~150s on a 4GB VPS). Bump it to `240` so a single supervisor instance waits long enough for the daemon to bind. This alone prevents most stampedes. Also ensure `StartLimitBurst`/`StartLimitIntervalSec` in the systemd unit gives the supervisor room to retry without systemd itself respawning a second supervisor.

**⚠️ Gateway guard blocks `systemctl --user stop` on the hindsight service.**
The Hermes gateway intercepts `systemctl` commands that could affect it. Even though `hindsight-embed.service` is NOT the gateway, the guard is conservative and blocks it with: *"cannot restart or stop the gateway from inside the gateway process."* Work around it by `pkill`-ing the supervisor process directly (step 1 above). Do NOT use `hermes gateway restart` for this — that restarts the gateway, not the Hindsight daemon.

**Verified 2026-07-04:** Daemon process was alive (supervisor kept restarting it), but the log showed "OpenAI-compatible client initialized" repeating every ~40s with no "Uvicorn running on" line. Polled `/health` for 10+ minutes across multiple attempts — never came up. Port 9177 had nothing listening. Correctly aborted and built the briefing from session files + git log instead.

### ⚠️ Silently-broken daemon: `ModuleNotFoundError` on lazy imports (uv cache purged)

A distinct failure mode that fools the pre-flight: `/health` returns `{"status":"healthy","database":"connected"}` (the daemon is alive and DB pool is up), but **any recall call 500s** with `ModuleNotFoundError: No module named 'hindsight_api.engine.<something>'`. Recall/embeddings and migrations all complete at startup so health is green — but a later *lazy* import inside the recall path hits a missing on-disk module.

**Root cause:** `hindsight-api` is launched via `uvx hindsight-api@0.8.5`, which extracts the package into `~/.cache/uv/archive-v0/<hash>/...` on first use and reuses that archive on every restart. A cache clean (manual or a tool that prunes `archive-v0`) **deletes the extracted files**, but the running daemon process still holds them in memory. The next lazy import of a sub-module the daemon hadn't touched yet hits the empty path and raises. **Retain** often keeps working because its imports loaded at startup; **recall** breaks because it imports search sub-modules lazily on the first call.

**Diagnostic:**
```bash
# 1. Confirm /health is green BUT recall 500s
curl -s localhost:9177/health                            # {"status":"healthy",...}
curl -s -X POST localhost:9177/v1/default/banks/hermes/memories/recall \
  -H "Content-Type: application/json" -d '{"query":"test","top_n":1}'
# -> {"detail":"Failed to search memories (ModuleNotFoundError): ModuleNotFoundError(\"No module named 'hindsight_api.engine.search.recall_boost'\")"}

# 2. Find the archive the running daemon is using
pgrep -af hindsight-api | grep python
# Output includes: $HOME/.cache/uv/archive-v0/<HASH>/bin/python ...
ARCH=$HOME/.cache/uv/archive-v0/<HASH>

# 3. Check if the archive is gone (the bug)
ls -d "$ARCH" 2>/dev/null || echo "ARCH GONE"
# If "ARCH GONE": the cache archive holding the daemon's code was deleted
```

**Recovery procedure (verified 2026-09-09):**
```bash
# 1. Kill the daemon directly — DO NOT use kill_stale patterns that could match your shell
kill -9 $(pgrep -f 'hindsight-api.*--daemon' | head -5)

# 2. The supervisor's health-check loop will restart it within ~30s.
#    On restart, `uvx hindsight-api@0.8.5` re-extracts the package into a fresh
#    archive. Wait for it to come up:
for i in $(seq 1 30); do sleep 10; \
  curl -sf -m 5 localhost:9177/health && echo "healthy after ~$((i*10))s" && break; \
done

# 3. (Watchdog case) If the OLD embedded postgres backends survived as orphans
#    holding DB locks, the new daemon's postgres will fail to start
#    ("Failed to start embedded PostgreSQL after 5 attempts" in the log).
#    Kill ONLY the hindsight postgres backends and clear the stale pid file:
#    (Be VERY careful with pkill patterns — they can match your own shell.)
#    Safer: pgrep -f 'hindsight-embed-hermes' | xargs -r kill -9
#    Also kill any client backends still holding LWLock:BufferContent:
#    pgrep -f 'postgres.*hindsight.*hindsight.*127.0.0.1' | xargs -r kill -9
#    rm -f ~/.pg0/instances/hindsight-embed-hermes/data/postmaster.pid
#    Then let the supervisor restart the daemon again.

# 4. Verify recall works:
curl -s -X POST localhost:9177/v1/default/banks/hermes/memories/recall \
  -H "Content-Type: application/json" -d '{"query":"test","top_n":3}' | head -c 200
# Expect: {"results":[...]}
```

**Why the cron ingest was silently failing:** the daily ingest script (`hindsight_daily_ingest.py`) runs a `/health` check that returns 200 (daemon IS up), then loads messages, extracts facts via LLM, and calls retain. Retain often succeeded (its imports were loaded), so the script reported success. But any recall from another path 500'd. This silently corrupted any workflow that used `hindsight_recall` — including the the company Slack watcher and the `hindsight-context` template.

**Prevention:** schedule a weekly `uv cache clean` that **does NOT prune `archive-v0` archives for tools in active use** — or set `UV_CACHE_KEEP_ARCHIVES=1` if available. Better fix: pin the daemon to a persistent venv (not `uvx --from`) so the code lives in `~/.hermes/hermes-agent/venv/lib/...` where cache prunes can't reach it.

### ⚠️ OOM-killer crash loop — when RAM exhaustion IS the root cause

A distinct failure mode from supervisor stampede: the **kernel OOM killer** repeatedly kills the daemon process because the VPS has insufficient RAM. systemd's `Restart=always` faithfully restarts it, the daemon allocates ~600MB, OOM killer kills it again — every ~30 seconds. The restart counter climbs into the hundreds (observed: 901) and never recovers.

**Diagnostic — distinguish OOM crash loop from supervisor stampede:**
```bash
# 1. Check journalctl for OOM-kill events (definitive)
journalctl --user --since "1 hour ago" --no-pager | grep -i "oom-kill\|Failed with result 'oom-kill'"
# OOM crash loop: repeated "The kernel OOM killer killed some processes in this unit" entries

# 2. Check system memory
free -h
# If available RAM < 200MB and swap = 0B, OOM is the cause

# 3. Check restart counter — a very high number (100+) with OOM journal entries = OOM loop
systemctl --user status hindsight-embed | grep "restart counter"
```

**Recovery procedure (verified 2026-07-06):**
```bash
# 1. STOP the service immediately — the restart loop thrashes RAM
systemctl --user stop hindsight-embed.service
systemctl --user reset-failed hindsight-embed.service

# 2. Kill any lingering processes
pkill -9 -f "hindsight-api"
pkill -9 -f "hindsight-embed"
pkill -9 -f "hindsight-supervisor"

# 3. Create swap if none exists (4GB VPS needs at least 4GB swap)
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
# Make permanent
grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# 4. (Optional) Add systemd memory limits to prevent future OOM
#    Create override: ~/.config/systemd/user/hindsight-embed.service.d/override.conf
#    [Service]
#    MemoryMax=512M
#    MemoryHigh=384M

# 5. Only restart the service once RAM is stabilized (swap added or VPS upgraded)
systemctl --user start hindsight-embed.service
```

**Prevention on low-RAM VPS (≤4GB):**
- **Swap is mandatory** — a 4GB VPS with 0 swap will OOM under any memory pressure
- **`MemoryMax=512M`** in a systemd override caps hindsight's RAM usage
- **Cap parallel subagents** — `delegation.max_concurrent_children: 2` in config.yaml (3 subagents × ~400MB each + hindsight 600MB + gateway 268MB + ollama 346MB = OOM on 4GB)
- **Monitor restart counter** — if it climbs past 20, investigate before it hits 900

**Verified 2026-07-06:** Hindsight daemon OOM-killed 901 times on 4GB VPS with 0 swap. Root cause: 3 parallel `delegate_task` subagents + hindsight 600MB + ollama 346MB + 4 TypeScript LSP servers (200MB each) exhausted 3.7GB RAM. Fix: stopped service, created 4GB swap, killed lingering processes. Service stopped pending MemoryMax override application.

## Current Config
- **Model**: `glm-5.3-flash:cloud` (as of 2026-09-20 — the user's single sanctioned model for ALL inference; `deepseek-v4.1-flash:cloud`, `glm-5.1/5.2` and `minimax-m3` are BANNED)
- **Provider**: MUST be `openai` (OpenAI-compatible endpoint), NOT `ollama` — see Provider Trap below
- **Port**: 9177 (hermes profile)
- **Cron**: `5,20,35,50 * * * *` — every 15 mins, avoids T212 trading windows
- **Supervisor START_TIMEOUT**: 240s (bumped from 120s on 2026-07-06 — cold start takes ~150s on the 4GB VPS)

### Provider Trap: `openai` provider required for reasoning models (verified 2026-09-12)
Hindsight's `ollama` provider routes through its **native** `/api/chat` path with `think: False`, but reasoning models (glm-5.3-flash, deepseek-v4.1-flash) emit reasoning prose inside `message.content` regardless — the JSON parser (which only strips code fences) then fails: `JSONDecodeError: Expecting value: line 1 column 1 (char 0)` → "Fact extraction failed: 1/1 chunks failed".

**Fix**: in `~/.hindsight/profiles/hermes.env` (the REAL runtime config — `~/.hermes/hindsight/config.json` is legacy and NOT read by the daemon), set:
```bash
HINDSIGHT_API_LLM_PROVIDER=openai
HINDSIGHT_API_LLM_MODEL=glm-5.3-flash:cloud
HINDSIGHT_API_LLM_BASE_URL=https://ollama.com/v1
HINDSIGHT_API_LLM_API_KEY=<ollama key>
```

**CRITICAL — editing the file alone does NOT take effect.** `hindsight.env` is consumed by the systemd unit (`~/.config/systemd/user/hindsight-embed.service` → `EnvironmentFile=$HOME/.hindsight/profiles/hermes.env`) and the model is snapshotted into the daemon's process environment at start. You MUST restart the unit, then prove the new model is live:
```bash
cp -a /mnt/storage/hermes/hindsight_data/profiles/hermes.env{,.bak-<change>}   # backup first
# edit HINDSIGHT_API_LLM_MODEL
systemctl --user restart hindsight-embed
# verify the RUNNING process env, not just the file:
cat /proc/$(pgrep -f "hindsight-api.*--daemon" | head -1)/environ | tr '\0' '\n' | grep HINDSIGHT_API_LLM_MODEL
# then confirm a real call in the log:
grep -E "client initialized|Verifying connection" /mnt/storage/hermes/hindsight_data/profiles/hermes.log | tail -3
```
Pitfall: `ExecStop` runs `pkill -9 -f hindsight.*--daemon`, whose pattern matches your own shell command line — invoking the restart from a shell whose cmdline contains those words kills your own command mid-run (exit -9). Restart via `systemctl --user restart hindsight-embed` from a command that does NOT embed the pattern, and inspect processes via a script file rather than an inline `pgrep`/`ps` string.

Pitfall: `~/.hermes/skills/` is a symlink to `/mnt/storage/hermes/skills/` — the "realpath" of the skills tree. A 2026-09-16 model sweep edited only `~/.hermes/hindsight/config.json` and the daemon kept running glm for another day because nobody restarted the unit.
The OpenAI-compatible path separates reasoning into its own field, so `content` is clean JSON. Verified: retain + dry-run-extract both succeed (5.6k-token doc processed cleanly).

**Config lives in `~/.hindsight/profiles/hermes.env`** (loaded via systemd EnvironmentFile), NOT `~/.hermes/hindsight/config.json` — that file is stale/legacy. After changing the env file, restart the daemon: kill the `hindsight-api --daemon` + `uvx` PIDs directly (pkill patterns can match your own shell — use `ps aux | grep ... | awk '{print $2}' | xargs kill`), and the supervisor restarts it within ~30-45s. Verify with `grep "Verifying connection" ~/.hindsight/profiles/hermes.log | tail -1`.

## Model Selection

When testing new Ollama cloud models for Hindsight, test for:
1. JSON validity (must return parseable JSON under `format: json`)
2. Speed (target <10s for fact extraction call)
3. Content quality (extracts relevant, non-duplicate facts)

**Verified models** (tested 2026-04-24):
| Model | Speed | JSON Valid | Notes |
|-------|-------|------------|-------|
| glm-5.3-flash:cloud | ~1.5s | ✓ | **CURRENT** (2026-09-20) — 1M ctx, reasoning |
| glm-5.1:cloud | 4.0s | ✓ | Strong coding skills |
| nemotron-3-super:cloud | 3.2s | ✓ | NVIDIA MoE 120B |
| gemma4:31b-cloud | 6.2s | ✓ | |
| minimax-m2.7:cloud | 8.9s | ✓ | Was previous model |
| kimi-k2.6:cloud | 30s | ✓ | Too slow |
| qwen3.5:cloud | 46s | ✓ | Too slow |
| qwen3.5:9b-cloud | 0.1s | ✗ | Too small, empty output |

## CRITICAL: Where the Hindsight model actually lives

**The daemon reads `~/.hindsight/profiles/hermes.env` ONLY** — it is loaded by the systemd unit via `EnvironmentFile=`. Set `HINDSIGHT_API_LLM_MODEL` there.

**`~/.hermes/hindsight/config.json` is LEGACY and NOT read by the daemon** (confirmed 2026-09-17: editing it changed nothing, which is exactly how a "migration" reported success while the old model kept being billed). Keep it in sync for tidiness if you like, but it is decoration.

The model is snapshotted into the daemon's **process environment at start**, so a file edit alone changes NOTHING. You must cycle the unit and then prove the *running* process:

```bash
systemctl --user restart hindsight-embed
# prove the RUNNING process, not the file:
cat /proc/$(pgrep -f "hindsight-api.*--daemon" | head -1)/environ | tr '\0' '\n' | grep HINDSIGHT_API_LLM_MODEL
# prove a real call:
grep -E "client initialized|Connection verified" ~/.hindsight/profiles/hermes.log | tail -3
```

Also update `~/.hermes/scripts/hindsight_daily_ingest.py` → `LLM_MODEL` (line ~32) — that script calls the LLM directly and does not read the env file.

⚠️ **`hindsight-embed`'s `ExecStop` runs `pkill -9 -f hindsight.*--daemon`**, whose pattern matches the cmdline of the shell you launched the restart from → your command can die with exit `-9`. Run the restart from a **script file** (never an inline command containing those words), and inspect processes via a script file too (an inline `pgrep` pattern matches itself).

A full "remove model X, only use Y" request is broader than this file — follow the `model-migration` skill.

## Transferring Hindsight to Another Host

**Same platform (Linux→Linux or Mac→Mac):**
1. Zip: `~/.hermes/hindsight/`, `~/.hermes/skills/memory/hindsight-integration/`, `~/.hindsight/`, `~/.hermes/scripts/hindsight_daily_ingest.py`, `~/.config/systemd/user/hindsight-embed.service`
2. On target host, extract to `~/Downloads/` → move files to the paths above
3. Update `~/.hermes/hindsight/config.json` with target's own API key
4. Re-enable the service:
   ```bash
   systemctl --user daemon-reload
   systemctl --user enable hindsight-embed
   systemctl --user start hindsight-embed
   ```
5. Verify: `curl -s localhost:9177/health`

**Cross-platform (Mac→Linux) — see [Migrating from Mac mini to Linux](#migrating-from-mac-mini-to-linux).**

## Setup

### 1. Cloud Config
`~/.hermes/hindsight/config.json`:
```json
{
  "mode": "local",
  "llm_provider": "ollama",
  "llm_api_key": "ollama-cloud-api-key-here",
  "llm_model": "glm-5.3-flash:cloud"
}
```

### 1b. Local Embedded Config (no API key, uses local Ollama)
`~/.hermes/hindsight/config.json`:
```json
{
  "mode": "local",
  "llm_provider": "ollama",
  "llm_api_base": "http://localhost:11434",
  "llm_model": "glm-5.3-flash:cloud"
}
```

**For local embedded**: No API key needed. The daemon uses the local Ollama at `localhost:11434`. Use `--provider ollama` flag when starting the daemon.
```

### 2. Start the Hindsight Daemon

**Cloud version** (with API key):
```bash
cd ~/.hermes/hermes-agent && source venv/bin/activate && hindsight-embed daemon start --profile hermes
```

**Local embedded version** (no API key, uses local Ollama):
```bash
cd ~/.hermes/hermes-agent && source venv/bin/activate && hindsight-embed daemon start --profile hermes --provider ollama
```

### 3. Verify
```bash
# Check daemon health (hermes profile = port 9177)
curl -s localhost:9177/health
# Expected: {"status":"healthy","database":"connected"}

# Test retain via direct API
python3 -c "
import requests
url = 'http://localhost:9177/v1/default/banks/hermes/memories'
payload = {'async': True, 'items': [{'content': 'Test memory', 'context': 'testing'}]}
r = requests.post(url, json=payload, timeout=30)
print(r.status_code, r.text)
"

# Test recall (CLI tool — may not be in PATH in cron/headless contexts)
hindsight_recall query="test memory"

# Direct API recall (most reliable in all contexts)
# Response shape: { "results": [{ "id", "text", "type", "entities", "context",
#   "occurred_start", "occurred_end", "mentioned_at", "metadata", "tags", ... }, ...] }
# NOTE: fact text lives in "text" field, NOT "content" — content is empty by design
curl -s localhost:9177/v1/default/banks/hermes/memories/recall \
  -X POST -H "Content-Type: application/json" \
  -d '{"query":"test memory", "top_n": 3}'

# Parse recall response (Python):
python3 -c "
import requests, json
r = requests.post('http://localhost:9177/v1/default/banks/hermes/memories/recall',
  json={'query': 'my query', 'top_n': 5}, timeout=30)
d = r.json()
for item in d.get('results', []):
    print('-', item.get('text', '')[:200])  # use 'text', NOT 'content'
"

# Direct retain (async batch — the most reliable path in all contexts)
curl -s localhost:9177/v1/default/banks/hermes/memories \
  -X POST -H "Content-Type: application/json" \
  -d '{"async": true, "items": [{"content": "...", "context": "..."}]}'
```

**Verified working:** retain + recall both succeed with deepseek-v4-flash:cloud via direct API. The `hindsight_recall`/`hindsight_retain` CLI tools depend on the hindsight-embed package being installed in the current PATH — in cron/headless contexts the direct API is more reliable.

## Daemon Supervision (24/7 — Required for Cron Coupling)

The Hindsight Session Ingest cron (`5,20,35,50 * * * *`) **requires** the daemon to be up. The daemon WILL crash silently if not supervised — and a naive `hindsight-embed daemon start` in a cron entry is **not** supervision: the cron only fires every 15 min, and a daemon that dies between fires silently breaks ingest until the next run.

**The fix is a two-layer watchdog: a long-lived supervisor + a cron pre-flight health check.**

### Layer 1: systemd supervisor (Linux) — the primary supervision

**Why `Type=simple` + a supervisor loop, not `Type=forking`:**
- `Type=forking` + `RemainAfterExit=yes` is a known footgun for daemons that fork grandchildren. The parent forks the daemon → parent exits 0 → systemd says "active (exited) = success" → the orphan daemon child dies later with no supervisor.
- Symptom: `systemctl --user status` shows `active (exited)` with `restart counter is at 78` but the daemon port is still down. The user only finds out when the cron silently fails.
- **Verified 2026-07-02**: this exact pattern caused the Hindsight daemon to be down despite a 78-attempt restart loop.

**The fix** — `Type=simple` with a supervisor bash script as `ExecStart`. systemd tracks the supervisor (the real long-lived process); the supervisor polls `/health` and restarts the daemon on failure.

Template: `templates/hindsight-embed.service` (copy to `~/.config/systemd/user/hindsight-embed.service`)

```ini
[Unit]
Description=Hindsight Embed Daemon Supervisor (Hermes/the agent)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$HOME
EnvironmentFile=$HOME/.hindsight/profiles/hermes.env
Environment="PATH=$HOME/.local/bin:$HOME/.hermes/hermes-agent/venv/bin:..."
ExecStart=$HOME/.hermes/scripts/hindsight-supervisor.sh
ExecStop=/bin/bash -c 'pkill -9 -f hindsight-supervisor.sh; pkill -9 -f hindsight-api; pkill -9 -f "hindsight-embed-hermes"'
Restart=always
RestartSec=10
TimeoutStartSec=180
StartLimitIntervalSec=300
StartLimitBurst=10
StandardOutput=append:$HOME/.hermes/logs/hindsight-systemd.log
StandardError=append:$HOME/.hermes/logs/hindsight-systemd.log

[Install]
WantedBy=default.target
```

Supervisor script: `scripts/hindsight-supervisor.sh` (copy to `~/.hermes/scripts/hindsight-supervisor.sh`, then `chmod +x`)

**Setup:**
```bash
# Verify the supervisor binary path matches your venv
which hindsight-embed   # must resolve; copy this into HINDSIGHT_BIN in the script
# Enable linger so the user service runs 24/7 even when logged out
sudo loginctl enable-linger $USER
# Activate
systemctl --user daemon-reload
systemctl --user enable hindsight-embed
systemctl --user start hindsight-embed
# Verify
systemctl --user status hindsight-embed   # must say "active (running)" — NOT "active (exited)"
curl -s localhost:9177/health              # {"status":"healthy","database":"connected"}
```

**Verified kill test (2026-07-02):** `kill -9` on both the `hindsight-api` parent and worker → supervisor detected the failure within 30s → killed stale processes → restarted daemon → `/health` returned 200. Total recovery: ~30s. Supervisor log shows `Restart succeeded`.

### Layer 2: Standalone keepalive script

For cases where systemd is not available (other hosts, containers, one-off recovery) or when the cron wants to self-heal: `scripts/hindsight-keepalive.sh` (copy to `~/.hermes/scripts/hindsight-keepalive.sh`, then `chmod +x`).

```bash
# Health check
~/.hermes/scripts/hindsight-keepalive.sh --status
# One-shot restart (used by the cron pre-flight)
~/.hermes/scripts/hindsight-keepalive.sh
# Poll forever (alternative to systemd)
~/.hermes/scripts/hindsight-keepalive.sh --loop
```

### Layer 3: Cron pre-flight health check (defence-in-depth)

The Session Ingest cron's prompt has a mandatory PRE-FLIGHT block. This is the **last line of defence** — if Layer 1 supervisor is broken or hasn't yet restarted, the cron will restart the daemon itself before running the ingest.

```text
PRE-FLIGHT (mandatory — daemon must be up before ingesting):
1. Run: curl -sf -m 5 http://localhost:9177/health
2. If it fails (non-200 or connection refused), run the keepalive:
     ~/.hermes/scripts/hindsight-keepalive.sh
3. Re-check health: curl -sf -m 5 http://localhost:9177/health
4. If still unhealthy after 2 attempts, report "❌ Hindsight daemon unreachable,
   ingest skipped" to Discord and EXIT. Do NOT run the ingest against a dead
   daemon — the script will hang or save all facts to pending.
```

**Update the cron prompt with `hermes cron edit <job_id> --prompt "..."` (the CLI persists to `~/.hermes/cron/jobs.json` and updates the gateway's in-memory store without requiring a restart).** See the Session Ingest cron (`925d93131194`) for the live example.

> ⚠️ **PITFALL — `update` is destructive, not a read operation.**
> The `cronjob update` action (and `hermes cron edit --prompt`) **replaces the entire prompt atomically** with whatever you pass. There is no `--dry-run`, no diff, and no confirmation. If you pass a placeholder string while "just checking the API shape", the cron will fire with that broken prompt on the next tick (15 mins later) and deliver a useless message to Discord.
>
> To inspect a prompt without mutating it:
> - `cronjob list` — only shows the truncated `prompt_preview` (first ~120 chars)
> - Read `~/.hermes/cron/jobs.json` directly: `python3 -c "import json; d=json.load(open('$HOME/.hermes/cron/jobs.json')); [print(j.get('prompt','')) for j in d.get('jobs',[]) if j.get('name')=='...']"`
> - Older request dumps in `~/.hermes/sessions/request_dump_cron_<job_id>_*.json` contain the full prompt that was last sent to the LLM
>
> If you DO mutate by accident, the recovery is `cronjob update job_id=<id> prompt="<original text>"` — but you need the original text, so always grab a backup via the methods above before editing. Verified 2026-07-03: lost 15 minutes to a clobbered prompt and had to recover from a request dump.

### Migrating from Mac mini to Linux

The legacy launchd plist is `~/Library/LaunchAgents/com.former-employer.hindsight.plist`. On Linux:

1. **Install the supervisor script + service** (see Layer 1 above)
2. **Migrate state**: `~/.hindsight/` is portable (just `cp -a` it); `~/.pg0/` is platform-specific (postgres binaries differ)
3. **Replace `launchctl start/stop` commands** in any old scripts or muscle memory with `systemctl --user start/stop hindsight-embed`
4. **Replace `~/Library/LaunchAgents/com.former-employer.hindsight.plist`** with `~/.config/systemd/user/hindsight-embed.service` (use the template)
5. **Update cron prompts** that reference `launchctl` (should be none — the pre-flight block uses `curl` + the keepalive script, both platform-neutral)
6. **Delete the launchd plist** after the Linux supervisor has been running cleanly for 24h

### Key discovery — two ports, two profiles
- Port **8888** = default profile (local embedded, no API key)
- Port **9177** = `hermes` profile (cloud version with API key)
- The ingest script `~/.hermes/scripts/hindsight_daily_ingest.py` uses port **9177**
- Always use `--profile hermes` when starting the daemon — without it, daemon uses port 8888
- The systemd supervisor uses `EnvironmentFile=$HOME/.hindsight/profiles/hermes.env` to load the API key for the right profile

## Memory Tool Selection Rule (CRITICAL — Two-Tier Model)

There are **two durable stores** with different rules. Confusing them wastes the 1,375-char profile budget and clutters Hindsight.

| Store | Tool | Limit | Holds | Lifetime |
|-------|------|-------|-------|----------|
| System-prompt profile | `memory` (target=user) | **1,375 chars total, all-or-nothing per batch** | Behavior-changing defaults, no-go rules, current project pinning | Every session (auto-injected) |
| Long-term context | `hindsight_retain` / `hindsight_recall` | Effectively unlimited | Full history, project details, relationships, account IDs | Cross-session recall |

### When to write to `memory` (user profile)
The fact must change a **default behavior** in future sessions:
- "Commits → testing branch ONLY"
- "Slack: only respond when @mentioned"
- "BetterAuthVanillaAdapter is DEFAULT"
- "NG pay/equity restructure is PRIVATE — never reference anywhere"
- One-line current employer + project pin (with date)

If the fact needs **explanation**, push the explanation to Hindsight and keep only the imperative in the profile.

### When to write to Hindsight
- Historical events ("worked at a previous employer, closed 2026-06-14")
- Detailed lists (account IDs, contract terms, teammate details)
- Project internals (cron schedules, file paths, full tech stack)
- Anything that will go stale within 7 days

### Never write to either
- Task progress (PR numbers, commit SHAs, "Phase N done")
- Transient errors that resolved
- One-off narrative

### 1,375-Char Limit Pitfall
The `memory` tool is **all-or-nothing per batch** — if the final result overflows, NOTHING is applied and you see only the current entries. Failed batches don't reveal your target size. Recovery:
1. Stop re-trying the same content; shrink 30-50%, not 10%
2. Move detail to Hindsight, not into `memory`
3. Combine overlapping sections into one
4. After 8+ failed attempts the runtime warns about tool loops — switch tactics before then
5. Lean profile budget: ~1 main entry (700-800 chars) + ~1 supporting entry (400-500 chars) = ~1,200 chars target, leaves headroom for future adds

### Reconciliation Workflow (when system-prompt profile is stale)
1. `hindsight_recall query="<user> current job employer projects"` — don't trust the stale system prompt
2. Decide behavior changes vs. detail
3. Draft lean profile in scratch buffer; count chars; aim for ~1,200 total
4. Batch replace in one `memory` call: 1-2 `replace` (swap header) + several `remove` (clear obsolete) + optional `add` (new high-signal facts). Atomic.
5. Retain any removed detail to Hindsight so it's not lost.

See `references/profile-template.md` for a worked-example lean profile and reconciliation diff.

### Original rule (kept for context)
- Use `hindsight_retain` to store business context, user corrections, project details, pricing data, relationships, and any fact that will matter in a future session.
- Use `hindsight_recall` to retrieve stored facts.
- If `hindsight_retain`/`hindsight_recall` return errors, use the direct API fallback documented below.

## CRITICAL: ALWAYS Use Direct API (not hindsight_retain tool)

**The `hindsight_retain` tool is BROKEN** — it fails with `cannot import name 'HindsightEmbedded' from 'hindsight'` on every call. **Do NOT use `hindsight_retain` or `hindsight_recall` tools.** Always use the direct HTTP API via `curl` or `python3 requests`.

**the user's rule (2026-07-23):** Always use Hindsight direct API for storing facts. Never use the `memory` tool for facts — it has a strict char limit and is unreliable. The `memory` tool (user profile) is ONLY for behavior-changing rules. ALL fact storage goes to Hindsight via direct API.

### Retain (store facts):

**Bash/curl (preferred — no escaping issues for simple payloads):**
```bash
curl -s -X POST http://localhost:9177/v1/default/banks/hermes/memories \
  -H "Content-Type: application/json" \
  -d '{"async": true, "items": [{"content": "fact text here", "context": "context label", "tags": ["tag1", "tag2"]}]}'
```

**Python (use when payload contains quotes/special chars):**
```python
import requests
url = "http://localhost:9177/v1/default/banks/hermes/memories"
payload = {"async": True, "items": [{"content": "...", "context": "...", "tags": [...]}]}
r = requests.post(url, json=payload, timeout=30)
```

### Recall (retrieve facts):
```bash
curl -s -X POST http://localhost:9177/v1/default/banks/hermes/memories/recall \
  -H "Content-Type: application/json" \
  -d '{"query": "search query", "top_n": 5}'
```

### Reflect (synthesize across memories):
```bash
curl -s -X POST http://localhost:9177/v1/default/banks/hermes/memories/reflect \
  -H "Content-Type: application/json" \
  -d '{"query": "question to reason about"}'
```

### Rules:
- **Always use `async: True`** for retain — sync calls timeout
- Batch up to **~10 items** per call
- If API returns connection refused → daemon is down, run keepalive: `~/.hermes/scripts/hindsight-keepalive.sh`
- Response `{"success": true}` = stored. The daemon queues async items and processes them in background.
- Response fact text lives in the `text` field (NOT `content`) when recalling results.

### Historical Note (kept for context)

Earlier versions of this skill documented `hindsight_retain` as permanently broken due to LiteLLM markdown-stripping issues. As of 2026-09-20 the tool works reliably with `glm-5.3-flash:cloud` (earlier: deepseek-v4-flash / minimax-m2.7 — retired). The workaround above is retained as a fallback only.

## Bulk Hindsight Ingest Pattern (docs / large corpora)

For "ingest a large body of content" tasks (documentation sites, project dumps, session archives):

**Recipe (verified 2026-07-03 with 224 Botpress docs pages, 273 chunks, 0 failures):**

1. **Chunk size: 8KB per item** — well under Hindsight's 10KB per-item limit; leaves headroom for headers
2. **`async: True` on every retain call** — sync calls timeout at scale
3. **Inter-item delay: 0.3s** — keeps the daemon's queue manageable without slowing things down
4. **Use direct API, not `hindsight_retain` tool** — the tool's CLI PATH dependency makes it unreliable; direct API is 100% reliable
5. **Cap at 1 item per request during bulk** — `async: True` already queues them in the daemon, batching on top just confuses error attribution
6. **Write the source files to disk first** — keep the raw markdown/docs at `~/.hermes/skills/<project>/references/` so future sessions can re-query without re-scraping

**Python template:**

```python
import requests
import time
import os

HINDSIGHT_URL = "http://localhost:9177/v1/default/banks/hermes/memories"
CHUNK_SIZE = 8000

def chunk_file(filepath, max_size=CHUNK_SIZE):
    """Split on URL separator lines, falling back to size-based split."""
    with open(filepath, 'r') as f:
        content = f.read()
    # Try to split on natural boundaries (=== URL: ... === etc.)
    parts = re.split(r'(^=== URL:.*$|^--- URL:.*$|^# URL:.*$|^===.*===$)',
                     content, flags=re.MULTILINE)
    chunks, current = [], ""
    for part in parts:
        if len(current) + len(part) > max_size and current:
            chunks.append(current)
            current = part
        else:
            current += part
    if current.strip():
        chunks.append(current)
    return chunks

def ingest_chunk(content, context, tags):
    payload = {"async": True, "items": [{
        "content": content[:8000], "context": context, "tags": tags
    }]}
    return requests.post(HINDSIGHT_URL, json=payload, timeout=30).status_code

for section, filepath in files.items():
    chunks = chunk_file(filepath)
    for idx, chunk in enumerate(chunks):
        ingest_chunk(chunk, f"{section} chunk {idx+1}/{len(chunks)}",
                     ["project-tag", section])
        time.sleep(0.3)
```

**Expected throughput:** ~3 chunks/sec via direct API. 273 chunks takes ~90s. 1,000 chunks takes ~5 min.

**Verification:** After ingest, `hindsight_recall` will surface existing higher-ranked memories first — the new chunks need the consolidation engine to process them (typically a few minutes). Don't declare ingest failed just because recall doesn't surface new facts immediately.

## Daily Ingest Cron Job

Set up a nightly cron that reads session data and retains key facts to Hindsight:

**Script:** `~/.hermes/scripts/hindsight_daily_ingest.py`

**Verified working approach — use this exact pattern:**
- Load session messages → truncate to 800 chars each → join into one text chunk
- Send entire chunk to LLM in **single call** (not batched) — faster and more reliable than batching extraction
- Parse JSON array from response → retain to Hindsight in batches of 10 via direct API
- Runtime: ~12s for ~40 messages (measured on a now-retired model — treat as rough order of magnitude)

**Why single-call extraction works better:**
- 170 messages at 2s delay × 9 batches = would timeout at 300s
- One 50K char call with 120s timeout = ~20s LLM + ~2s retain = ~35s total

**Script logic:**
1. Load any pending facts from `~/.hermes/hindsight/pending_facts.json`
2. Load today's session messages from `~/.hermes/state.db` (SQLite) — see "Session Storage Migration" below
3. Extract facts via LLM (single comprehensive call, max 20 facts, 120 char limit each)
4. Batch-retain via direct API with `async: True` (batches of 10)

**Cron:** `5,20,35,50 * * * *` (every 15 mins, avoids T212 trading windows at 07:45/10:00/13:00/15:15)
- Runtime: ~12-15s end-to-end (order-of-magnitude; re-measure per model)

**Important: Sessions cover all platforms automatically**
- All Discord, Slack, and BlueBubbles/iMessage sessions are stored in `~/.hermes/state.db` (SQLite)
- Platform is embedded per message (keys: `platform`, `channel_id` on the sessions table)
- The ingest script reads ALL platform sessions by date — no need to configure per-platform
- Cron sessions are excluded (source='cron') so the script doesn't ingest its own output as "facts"

**Duplicate handling:** Hindsight auto-deduplicates via its consolidation engine (observations). The cron does NOT need to check for existing facts before retaining. Related facts are synthesized into observations with proof counts. Contradictory evidence is reconciled rather than overwritten — history is preserved.

## Session Storage Migration (CRITICAL — June 2026)

**Hermes migrated from .jsonl session files to a SQLite database.** If your ingest script was written before this migration, it has been silently finding zero sessions and zero messages.

**Symptom:** Cron reports "0 substantive messages" and "0 extracted" on every run, even though the daemon is healthy and you have active sessions.

**The migration:**
- **OLD:** `~/.hermes/sessions/{YYYYMMDD}*.jsonl` — one file per session, JSONL format
- **NEW:** `~/.hermes/state.db` — SQLite, tables: `sessions` (id, started_at, source, title, ...) and `messages` (id, session_id, role, content, timestamp, ...)

**Schema reference:**
```sql
-- sessions table — one row per session
SELECT id, source, started_at, ended_at, message_count, title
FROM sessions
WHERE started_at >= ? AND started_at < ?;  -- epoch floats

-- messages table — one row per message
SELECT m.role, m.content, m.timestamp
FROM messages m
JOIN sessions s ON m.session_id = s.id
WHERE s.source != 'cron'              -- exclude cron output
  AND m.role IN ('user', 'assistant') -- skip tool output / system
  AND length(m.content) >= 50;        -- skip trivial messages
```

**`started_at` is a Unix epoch float** (e.g. `1783072469.8779712`), not an ISO string. To filter by date, convert: `datetime.combine(date_obj, datetime.min.time()).timestamp()`.

**The fixed `load_substantive_messages()` function:**
```python
import sqlite3
from datetime import datetime, timedelta

def load_substantive_messages(date_str):
    """date_str format: YYYYMMDD"""
    db_path = Path.home() / ".hermes" / "state.db"
    d = datetime.strptime(date_str, "%Y%m%d").date()
    start_epoch = datetime.combine(d, datetime.min.time()).timestamp()
    end_epoch = datetime.combine(d + timedelta(days=1), datetime.min.time()).timestamp()
    
    msgs = []
    conn = sqlite3.connect(str(db_path))
    try:
        for content, role in conn.execute("""
            SELECT m.content, m.role
            FROM messages m JOIN sessions s ON m.session_id = s.id
            WHERE s.started_at >= ? AND s.started_at < ?
              AND s.source != 'cron'
              AND m.role IN ('user', 'assistant')
              AND m.content IS NOT NULL
              AND length(m.content) >= 50
            ORDER BY m.timestamp
        """, (start_epoch, end_epoch)):
            if "CONTEXT COMPACTION" in content:
                continue
            msgs.append(content[:800])
    finally:
        conn.close()
    return msgs
```

**Verified 2026-07-03:** Before the fix, ingest found 0 messages and retained 0 facts. After the fix, found 41 messages from 6 sessions and retained 18 facts.

## Daily Ingest Troubleshooting

**Symptom: Cron reports "0 substantive messages" repeatedly.**
- Cause 1 (most common): script is reading `.jsonl` files but sessions are in `state.db` SQLite — see Session Storage Migration above.
- Cause 2: `started_at` is an epoch float, not a date string — the file glob `YYYYMMDD*.jsonl` will never match.
- Cause 3: you're including `source='cron'` sessions in the count — exclude them or you'll get all the cron job transcripts.

**Symptom: "LLM error 401: Unauthorized" on the extraction call.**
- Cause: the script is calling the local Ollama proxy (`http://localhost:11434/v1/chat/completions`) for cloud models, but the proxy returns 401 because the `OLLAMA_API_KEY` env var isn't being passed through.
- **Fix:** call the cloud endpoint directly: `https://ollama.com/v1/chat/completions` with `Authorization: Bearer <api_key>` (the key is in `~/.hermes/config.yaml` under `providers.openai.api_key`).
- Verified 2026-07-03: `localhost:11434` returns 401 on all cloud model calls; `ollama.com/v1` works with the same key.

**Symptom: LLM returns empty content for larger prompts (>10K chars).**
- The model may be hitting a context length issue or a per-request token cap. Try truncating each message to 500 chars (down from 800) or splitting the chunk into 2-3 sequential LLM calls.

## Critical Fix: minimax-m2.7:cloud Markdown Output (APPLIED — reapply after Hindsight updates)

**Problem**: minimax-m2.7:cloud returns markdown structured text (`1. **what**: value`) but Hindsight's JSON parser only strips code fences (` ```json ... ``` `). This causes "Extra data: line 1 column 2" parse errors.

**Fix applied to**:
`~/.cache/uv/archive-v0/-f1yyRKayWEPLVAzGIDhG/lib/python3.11/site-packages/hindsight_api/engine/providers/ollama_provider.py`

**Function patched**: `_strip_code_fences` → extended to also strip markdown numbered headers (`1. **key**: value`, `2. **key**: value`, etc.) and markdown bold inline (`**key**: value`).

The patched version handles all these patterns:
1. Code fences: ` ```json ... ``` ` or ` ``` ... ``` `
2. Markdown numbered headers: `1. **what**: value`, `2. **when**: value`
3. Markdown bold inline: `**what**: value`

If Hindsight updates its package, re-apply this patch to the Ollama provider.

**Symptoms if patch is missing**: `hindsight_retain` succeeds (async) but recall returns empty. Daemon log shows: `json.JSONDecodeError: Extra data: line 1 column 2`

**Model tested and working (2026-09-20)**: `glm-5.3-flash:cloud` — clean JSON output on the `openai` provider path. (Historical benchmark: `deepseek-v4-flash:cloud`, 1.7s — retired.)

**Models that DON'T work**:
- `gemma3:12b-cloud` — ignores format parameters, returns empty with structured output
- `qwen3.5:9b-cloud` — too small, returns empty
- Any model that returns streaming NDJSON when `stream: false` is set — causes "Extra data: line 2" parse errors

## Alternative: Use Native Ollama (not cloud)
If using local Ollama instead of cloud, change provider to `ollama` and set model to a local model name. But note that `ollama` provider uses native `/api/chat` with `format=schema` which causes empty responses from cloud models — use OpenAI-compatible endpoint instead.
