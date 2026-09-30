---
name: cron-recovery
description: Diagnose and fix failing Hermes cron jobs — model/provider failures, script-only conversion (no_agent=True), script field path constraints, wrapper scripts for argument passing, and bulk job health audits.
trigger: When checking why cron jobs are failing, debugging cron last_status errors, converting agent-mode crons to script-only, or auditing multiple failing cron jobs at once.
tags: [cron, hermes, automation, troubleshooting, no-agent]
---

# Cron Job Recovery Patterns

When cron jobs show `last_status: "error"`, diagnose the root cause before attempting fixes. Most failures fall into one of two categories:

1. **Model/provider failures** — the agent layer can't reach the model (HTTP 403, 429, billing past due, model deprecated)
2. **Script/logic failures** — the underlying script itself is broken (missing files, permissions, bad paths)

The fix strategy differs for each. This skill covers diagnosis and recovery for both, with emphasis on the model/provider failure path since those are the most common and easiest to fix.

## Step 1: Bulk Health Audit

Always start with `cronjob action=list` to see all jobs and their status. Jobs with `last_status: "error"` need investigation. Look for patterns:
- Multiple jobs failing with the same error → shared dependency (model/provider, daemon, credential)
- Single job failing → script-specific issue

## Step 2: Read the Error Output

Error transcripts are saved per-job at `~/.hermes/cron/output/<job_id>/<timestamp>.md`. Each file contains:
- Job metadata (ID, run time, schedule)
- The prompt that was sent to the agent
- The error under a `## Error` heading

Common error patterns and their root causes:

| Error | Root Cause | Fix |
|---|---|---|
| `HTTP 403: subscription payment is past due` | Ollama Cloud billing issue | Convert to `no_agent=True` (if script-only) or switch model |
| `HTTP 429: rate limit exceeded` | Provider rate limit | Stagger schedules, switch provider, or convert to script-only |
| `RuntimeError: model not found` | Model deprecated/removed | Update job model or convert to script-only |
| `HTTP 400: Unknown Model, please check the model code` | Job pinned to a stale model code (e.g. old provider's `model:cloud` suffix) that the current provider's API rejects; global config is usually fine | Re-pin: `cronjob action=update job_id=<id> model=<current-model> provider=<current-provider>`; audit all jobs with pins via jobs.json (seen 2026-09-27: `glm-5.3-flash:cloud` rejected by z.ai after global switch) |
| `Skipped to prevent unintended spend: global inference config drifted ... unpinned` | Stale `model_snapshot` guard after a global model change | Pin job to new model, or clear `model_snapshot`/`provider_snapshot` in jobs.json (see "Config Drifted Silent Skip" below) |
| `Script not found: /home/.../bash ~/.hermes/...` | Invalid `script` field (contains bash prefix) | Use bare filename + wrapper script |
| `exit_code: 1` with script output | Script itself failed | Debug the script, not the cron |

## Step 3: Verify the Script Works Manually

Before converting a job, always run the underlying script manually:

```bash
bash ~/.hermes/scripts/<script-name>.sh
```

If it produces clean output (alert text, report, success message), the script is fine — the problem is the agent/model layer. If it errors, fix the script first.

## Step 4: Convert to Script-Only Mode (no_agent=True)

For jobs where the underlying script is self-contained (produces its own output, doesn't need LLM reasoning), convert to `no_agent=True`:

```python
cronjob(
    action="update",
    job_id="<job_id>",
    no_agent=True,
    prompt="",          # cleared — not used in script mode
    skills=[],          # cleared — not used in script mode
    script="<script-name>.sh",   # bare filename only (see rules below)
)
```

Then verify immediately:
```python
cronjob(action="run", job_id="<job_id>")
# Check: execution_success=True, last_status="ok"
```

### `script` Field Path Rules (Hard Constraints)

The `script` parameter in `cronjob update` is strictly validated:

- ✅ **Bare filename**: `storage-manager.sh` → resolves to `~/.hermes/scripts/storage-manager.sh`
- ❌ **Absolute path**: `$HOME/.hermes/scripts/storage-manager.sh` → rejected
- ❌ **Home-relative path**: `~/.hermes/scripts/storage-manager.sh` → rejected
- ❌ **bash prefix**: `bash ~/.hermes/scripts/foo.sh` → treated as literal filename, fails with "Script not found"
- ❌ **Inline arguments**: `storage-manager.sh --report` → entire string becomes filename, fails

### Wrapper Script Pattern for Argument-Passing Scripts

When the underlying script needs arguments (e.g. `storage-manager.sh --report`), create a wrapper script in `~/.hermes/scripts/`:

```bash
#!/bin/bash
# Wrapper — called by cron (no_agent mode)
exec bash ~/.hermes/scripts/storage-manager.sh --report
```

Then set `script="storage-weekly-report.sh"` on the cron job. The wrapper:
- Has a bare filename (satisfies the `script` field constraint)
- Resolves `~/.hermes/` at runtime (tilde expansion works inside bash, just not in the `script` field)
- Can pass any arguments to the underlying script
- Should be `chmod +x`'d

## Step 5: Verify All Fixed Jobs

After converting multiple jobs, run each one immediately to confirm:

```python
for job_id in [list_of_fixed_job_ids]:
    cronjob(action="run", job_id=job_id)
    # Verify: execution_success=True, last_status="ok"
```

A successful conversion shows:
- `execution_success: true`
- `last_status: "ok"`
- `no_agent: true`
- `script: "<bare-filename>.sh"`

## Failure Mode: "Config Drifted" Silent Skip (model_snapshot guard)

Unpinned agent-mode jobs record the global model at creation time as `model_snapshot` / `provider_snapshot`. On every tick the scheduler compares the snapshot against current global config; if they differ, the job **skips the run entirely** (no LLM call, no crash) and records in `last_error`:

> `RuntimeError: Skipped to prevent unintended spend: global inference config drifted since this job was created (model 'X' -> 'Y'), and this job is unpinned. No inference call was made. To run on the new config, pin it explicitly: cronjob action=update job_id=... provider=... model=...`

**This is a silent non-failure**: `last_status` may still show `ok`/no error badge from the last successful run, delivery never arrives, and no money is spent. Easy to miss for weeks (seen 2026-09-16: a daily LGC Quiz snapshot job had been skipping since a model swap).

**Diagnosis**: after ANY global model/provider change, inspect `~/.hermes/cron/jobs.json` for `model_snapshot` values that no longer match global `model.default`.

**Fix options**:
- Pin the job to the new model: `cronjob action=update job_id=<id> provider=<p> model=<m>` — makes it immune to future drift but re-flags on the next global change
- Clear the guard: remove `model_snapshot` / `provider_snapshot` keys via direct JSON edit of `jobs.json` (safe while scheduler runs; it re-reads per tick). Job then runs on whatever global config is current — right choice when the job should just follow the default
- Fix is invisible in `cronjob list` output — verify via the `jobs.json` fields and optionally `cronjob action=run` to confirm a clean execution

## Vestigial `model`/`provider` Fields on `no_agent` Jobs

When a job is converted to `no_agent=True`, the `model` and `provider` fields from the original agent-mode job **remain pinned** and are visible in `cronjob list`. These fields are **completely ignored** in script-only mode — the scheduler runs the script directly with no LLM call.

**Why this matters during debugging:** You see `model: "deepseek-v4-flash"`, `provider: "openai"` on a failing job and assume the job is still trying to call that provider. It isn't. Check `no_agent: true` first — if set, the model/provider fields are vestigial and the failure is in the **script**, not the provider.

**Diagnostic shortcut:** When a `no_agent` job shows `last_status: "error"`:
1. Check the output file (`~/.hermes/cron/output/<job_id>/<timestamp>.md`) — look for `Mode: no_agent (script)` and `Status: script failed`
2. Run the script manually: `bash ~/.hermes/scripts/<script>.sh`
3. If the script succeeds manually, the issue is transient (daemon down, permissions, race condition) — not provider-related

**When to clean up vestigial fields:** You can pass `model=None` and `provider=None` to `cronjob update` to clear them, reducing confusion for future debugging sessions. Not required for functionality, but good hygiene.

**Verified Aug 6 2026:** The `the workstation Daily Storage Sweep` job (a7ed828b179b) had `model: "deepseek-v4-flash"`, `provider: "openai"` pinned from its agent-mode days, but had already been converted to `no_agent=True`. The error messages from early August (HTTP 403/429 from Ollama Cloud) were from the *previous* agent-mode runs before conversion. The most recent runs (after conversion) succeeded silently — the script ran fine, no LLM needed. The vestigial fields caused initial confusion about whether the job was still trying to call Ollama Cloud.

## Key Principle

Script-only jobs have zero model dependency — provider billing outages, model deprecations, and API rate limits don't affect them. When a cron job's task is "run a bash script and deliver its stdout," the agent layer is unnecessary overhead and a failure point. Remove it.

## When NOT to Convert

Keep jobs as `no_agent=False` (agent mode) when:
- The job needs to reason about external data (summarize a feed, draft a briefing)
- Output depends on conditional logic based on content
- The job loads and uses skills
- The job needs web access or platform tools (Discord, Slack, email)
- The job picks interesting items from a list

## Pattern: Replacing LLM-Driven Process Reapers with Script-Only

A common cron failure mode: an LLM-driven reaper (`no_agent=False`) that's supposed to kill stale dev server processes (vite, esbuild, tsserver, nodemon, etc.) burns tokens every tick but doesn't reliably kill processes. Processes from days ago accumulate, eating RAM (tsserver alone uses ~700MB).

**Fix**: Replace with a `no_agent=True` script-only cron. The script uses `ps -eo etimes` to check elapsed time and kills processes over a threshold. Zero token cost, more reliable.

Script (`~/.hermes/scripts/kill-stale-dev-servers.sh`):
```bash
#!/usr/bin/env bash
THRESHOLD_MIN=30
KILLED=""
PIDS=$(ps -eo pid,etimes,cmd --no-headers | grep -E "vite|esbuild|tsserver|webpack-dev-server|next dev|turbo.*dev|nodemon" | grep -v grep | grep -v hermes | awk '{print $1":"$2}')
for entry in $PIDS; do
  PID=$(echo "$entry" | cut -d: -f1); ELAPSED=$(echo "$entry" | cut -d: -f2)
  if [ "$ELAPSED" -gt $((THRESHOLD_MIN * 60)) ]; then
    CMD=$(ps -p "$PID" -o cmd --no-headers 2>/dev/null | head -c 120)
    kill "$PID" 2>/dev/null; sleep 0.5; kill -9 "$PID" 2>/dev/null
    KILLED="$KILLED\n• PID $PID (${ELAPSED}s): $CMD"
  fi
done
if [ -n "$KILLED" ]; then echo -e "🧹 Killed stale dev servers (>${THRESHOLD_MIN}min):$KILLED"; fi
```

Cron job: `no_agent=True`, `schedule: "*/30 * * * *"`, `deliver: "local"`, `script: "kill-stale-dev-servers.sh"`.

**Key design points**:
- Exclude Hermes's own processes (`grep -v hermes`) — don't kill the agent runtime
- Use `ps -eo etimes` for elapsed seconds (not `ps aux` which doesn't show elapsed time directly)
- `kill` first, then `kill -9` after 0.5s for graceful shutdown
- Empty stdout = silent (no delivery) — watchdog pattern, no spam when nothing to kill
- `deliver: "local"` — no need to spam Discord with cleanups; check logs if needed

**Verified Aug 6 2026**: Replaced the LLM-driven `the workstation Dev Server Reaper` (every 15 min, burning tokens, but processes from Jul 31 were still alive after a week) with this script-only version. Freed ~850MB RAM immediately (tsserver 700MB + vite/esbuild 150MB). The LLM-driven reaper was paused and the no-agent replacement created.

## Session References

- `references/session-2026-08-06-storage-sweep-provider-failure.md` — Ollama Cloud billing outage affecting multiple cron jobs; vestigial model fields on no_agent jobs; TTS cleanup script path fix; Hindsight ingest's independent LLM dependency
- For full model-migration sweeps (which create drift-guard skips), see the `model-migration` skill (automation/) — this skill covers the cron-side symptoms it produces

## Related Skills

- `cron-patterns` — cron job creation, immutability, delivery format, watchdog pre-flight
- `daemon-watchdog-pattern` — daemon health checks and self-heal for crons that depend on long-lived services