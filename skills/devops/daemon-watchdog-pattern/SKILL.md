---
name: daemon-watchdog-pattern
description: Three-layer daemon watchdog pattern for 24/7 supervision of long-lived services (Hindsight, Ollama, custom daemons) coupled to cron jobs. Use when a daemon crashes silently, a cron's health check is naive, or systemd `Type=forking` setup is hiding a real outage. Encodes the verified fix — supervisor loop plus standalone keepalive plus cron pre-flight.
triggers:
  - daemon watchdog
  - daemon keeps dying
  - cron fails silently
  - systemd Type=forking
  - service crash silent
  - supervisor script
  - keepalive bash
  - hindsight daemon down
  - daemon 24/7
---

# Daemon Watchdog Pattern (3-Layer)

When a cron job or agent depends on a long-lived daemon that crashes silently, **never** rely on a single layer of supervision. The daemon WILL die between cron fires, and naive `service start` in a cron entry isn't supervision — the cron only fires every N minutes.

## When to apply

A daemon is in this danger zone if ANY of:
- A cron job calls it (e.g. Hindsight Session Ingest every 15 min)
- `systemctl status` shows `active (exited)` for a daemon with `Type=forking` (footgun: parent forks + exits 0, systemd lies about liveness)
- The daemon spawns children (embedded postgres, worker pool) — if the child dies, the parent often does too
- You've seen `restart counter is at N` in journalctl — systemd is trying, but the underlying service definition is broken
- Cron prompt has a `curl localhost:PORT/health` with no fallback

## The three layers

### Layer 1 — systemd supervisor (primary, 24/7)

**The footgun:** `Type=forking` + `RemainAfterExit=yes` causes systemd to declare "active (exited) = success" even if the daemon child later dies. Symptom: `restart counter is at 78` but port 9177 is still down.

**The fix:** `Type=simple` with a supervisor bash script as `ExecStart`. systemd tracks the supervisor (the real long-lived process); the supervisor polls `/health` and restarts the daemon on failure.

Service template:
```ini
[Unit]
Description=<Daemon> Supervisor
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$HOME
EnvironmentFile=/path/to/profile.env
Environment="PATH=..."
ExecStart=$HOME/.hermes/scripts/<daemon>-supervisor.sh
ExecStop=/bin/bash -c 'pkill -9 -f <daemon>-supervisor; pkill -9 -f <daemon>-child'
Restart=always
RestartSec=10
TimeoutStartSec=180
StartLimitIntervalSec=300
StartLimitBurst=10
StandardOutput=append:$HOME/.hermes/logs/<daemon>-systemd.log
StandardError=append:$HOME/.hermes/logs/<daemon>-systemd.log

[Install]
WantedBy=default.target
```

Supervisor script (`<daemon>-supervisor.sh`):
- Polls `http://localhost:PORT/health` every 30s
- If unhealthy: `pkill -9 -f <daemon>` → sleep 2 → `<daemon> start` → wait up to 120s for `/health`
- Logs to `~/.hermes/logs/<daemon>-supervisor.log`
- Exit non-zero only on fatal config errors (so `Restart=always` fires)
- Use `set -u` (NOT `set -e` — health check is allowed to return non-zero)

Setup:
```bash
sudo loginctl enable-linger $USER   # REQUIRED for 24/7 user service
systemctl --user daemon-reload
systemctl --user enable <daemon>
systemctl --user start <daemon>
systemctl --user status <daemon>    # MUST say "active (running)" — not "exited"
curl -s localhost:PORT/health
```

### Layer 2 — Standalone keepalive script (cron-side fallback)

Three modes — defaults to one-shot for cron use:
```bash
<daemon>-keepalive.sh             # one-shot: check + restart if down, exit
<daemon>-keepalive.sh --loop      # poll forever (alternative to systemd)
<daemon>-keepalive.sh --status    # health check, exit 0/1
```

Same logic as supervisor (kill stale → start → wait for /health) but a single bash file with no external dependencies. Useful when:
- systemd is not available (other hosts, containers)
- The cron wants to self-heal
- You want to manually nudge a stuck daemon

### Layer 3 — Cron pre-flight (last line of defence)

Belt-and-braces. Bake into every cron prompt that touches the daemon:

```text
PRE-FLIGHT (MANDATORY):
1. curl -sf -m 5 http://localhost:PORT/health
2. If it fails, run: ~/.hermes/scripts/<daemon>-keepalive.sh
3. Re-check: curl -sf -m 5 http://localhost:PORT/health
4. If still unhealthy after 2 attempts, ABORT and report error.
   Do NOT call the daemon API against a dead daemon — it will hang.
```

Update with `hermes cron edit <job_id> --prompt "..."` (audited path; persists to `~/.hermes/cron/jobs.json` AND updates the gateway's in-memory store without a restart).

**NEVER** edit `jobs.json` directly via Python — the gateway won't see the change. Always use `hermes cron edit`.

## Verify with a kill test

The whole pattern is proven by this:
```bash
# 1. Confirm healthy baseline
curl -s localhost:PORT/health
# 2. Find and kill the daemon PIDs (NOT the supervisor)
ps -ef | grep -E "<daemon>-api|<daemon>-worker" | grep -v grep | awk '{print $2}' | xargs kill -9
# 3. Wait up to 60s for supervisor to detect + restart
for i in 5 15 30 45 60; do sleep $((i - prev)); curl -s localhost:PORT/health; prev=$i; done
# Expected: healthy by T+30s, supervisor log shows "Restart succeeded"
```

## ⚠️ Slow startup: keepalive may exceed terminal timeout

Daemons with heavy initialization (model loading, embedded databases, DB migrations) can take 60-120s to become healthy after the process starts. The keepalive script's `start_daemon` polls `/health` in a loop up to `START_TIMEOUT=120s`, which is correct — but the **terminal calling the keepalive** may have a shorter timeout (default 60s).

When the terminal kills the keepalive at 60s, the daemon **process is still alive and initializing** — it has NOT failed. The agent should:

1. Check if the daemon process is alive: `pgrep -f "<daemon>.*daemon"` or `pgrep -f "<daemon>-api"`
2. Watch the daemon log for startup progress (look for the "started successfully" or Uvicorn/Gunicorn "running on" line)
3. Poll `/health` every 15s until it responds, up to the keepalive's `START_TIMEOUT`
4. **Set the terminal timeout for the keepalive call to at least 180s** to let the script finish its own polling loop

Example (Hindsight): keepalive killed at 60s by terminal timeout → daemon process still running DB migrations → `/health` returned 200 after ~90s more → ingest succeeded.

## ⚠️ OOM-killer crash loop — RAM exhaustion vs supervisor failure

A distinct failure mode that looks like a crash loop but has a completely different root cause: the **kernel OOM killer** is killing the daemon because the host has insufficient RAM. systemd's `Restart=always` faithfully restarts it, the daemon allocates its working set, OOM killer kills it again — every ~30s. The restart counter climbs into the hundreds and never recovers.

**This is NOT a supervisor problem — fixing the supervisor or bumping START_TIMEOUT won't help.** The daemon never gets a chance to bind because the kernel kills it mid-initialization.

**Diagnostic:**
```bash
# Definitive check — OOM-kill events in journalctl
journalctl --user --since "1 hour ago" --no-pager | grep -i "oom-kill"
# Also check:
free -h   # if available < 200MB and swap = 0B, OOM is the cause
```

**Fix:**
1. **Stop the service** to end the RAM-thrashing restart loop
2. **Create swap** (`sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile` — add to `/etc/fstab` for persistence)
3. **Add `MemoryMax=` to a systemd override** so the daemon is capped below the OOM threshold
4. **Restart the service** only after RAM is stabilized

**Prevention on low-RAM hosts (≤4GB):**
- Swap is mandatory — 0 swap + 4GB RAM = guaranteed OOM under any memory pressure
- Cap `delegation.max_concurrent_children` to 2 (each subagent adds ~400MB to the gateway process)
- Add `MemoryMax=512M` for hindsight, `MemoryMax=1G` for the gateway

**Verified 2026-07-06:** Hindsight daemon OOM-killed 901 times on 4GB VPS (0 swap). 3 parallel subagents + hindsight 600MB + ollama 346MB + 4 TS LSP servers exhausted RAM. Fix: 4GB swap + service stop + memory limits.

## Don't apply this pattern to

- **System services already supervised by systemd with `Restart=always` + low `RestartSec`** (e.g. ollama, the gateway). They're fine.
- **Short-lived processes** (cron tasks, batch jobs). Just use systemd `oneshot`.
- **Daemons that need ordered startup** (postgres, redis). Add `After=postgres.service` in the unit — they need the DB to be ready.

## Gateway restart and secret redaction constraints

When diagnosing daemon issues that require a gateway restart or config toggle, see `references/gateway-restart-limitations.md`. Key facts:
- **Cannot restart the gateway from inside the gateway process** — safety hooks block SIGTERM-propagating commands. Use `/restart` in Discord or SSH from outside.
- **`security.redact_secrets` is snapshotted at startup** — toggling it mid-session has no effect until the next restart.
- **The gateway itself can be OOM-killed** on low-RAM VPS — same swap + MemoryMax mitigation applies.

## Reference implementation

Verified 2026-07-02 on the Hindsight daemon (Ubuntu 26.04 VPS, user service, port 9177):
- `~/.hermes/scripts/hindsight-supervisor.sh`
- `~/.hermes/scripts/hindsight-keepalive.sh`
- `~/.config/systemd/user/hindsight-embed.service`
- Skill: `~/.hermes/skills/memory/hindsight-integration/`
- Cron prompts updated: `925d93131194` (Session Ingest), `1f0176d5f222` (the company)
- Kill test passed: `kill -9` on both uvicorn parent + worker → supervisor restarted at T+30s → `/health` 200
