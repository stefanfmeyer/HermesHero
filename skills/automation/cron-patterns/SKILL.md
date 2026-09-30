---
name: cron-patterns
description: Cron job patterns for Hermes Agent — immutable job management, gateway in-memory store synchronization, agent-task crons vs script crons, daemon pre-flight + self-heal watchdog patterns (curl health check → keepalive → bail), and Kanban orchestrator/worker conventions.
trigger: Creating, updating, debugging, or troubleshooting Hermes cron jobs — immutable jobs, gateway restart, agent-task vs script mode, watchdog patterns, and delivery failures.
tags: [cron, hermes, automation, gateway, kanban]
---

# Cron Job Patterns for Hermes Agent

## Core Rule: Cron Jobs Are Immutable

Once created, cron job fields cannot be patched in-place via `cronjob update`. Must recreate from existing job.

### Why `cronjob update` doesn't work

The `cronjob` tool's `patch` action to `~/.hermes/cron/jobs.json` does NOT update the gateway's in-memory cron store. The gateway daemon runs crons from its own memory, not from the disk file directly. Patching the file on disk then `cronjob run` will still execute the OLD prompts from memory.

### Correct Workflow for Updating a Cron Prompt

**Prefer the CLI (recommended, 2026-07+):** `hermes cron edit <job_id> --prompt "..."` — persists to `~/.hermes/cron/jobs.json` AND updates the gateway's in-memory store without requiring a restart. Use this for prompt-only edits. (Older instructions in this skill recommend editing the JSON file directly + pause/enable; that still works, but the CLI is faster and less error-prone.)

```bash
# Example: update the Hindsight Session Ingest cron prompt
hermes cron edit 925d93131194 --prompt "$(cat /tmp/new_prompt.txt)"
```

**Fallback (still works for schedule/delivery/skill changes that the CLI may not support):**
1. Edit `~/.hermes/cron/jobs.json` directly (Python or terminal `sed`/`cat`)
2. **Reload the gateway** — either:
   - `hermes gateway restart` (full restart — authoritative) — **requires user approval**
   - **OR** pause and unpause the job: `cronjob pause <job_id>` → `cronjob enable <job_id>` (the gateway re-reads the disk file on re-enable)
3. Verify with `cronjob list` — check that `prompt_preview` shows the new text
4. Then `cronjob run` — will now use the updated prompt

### Why `cronjob list` Shows Updated Prompts but `cronjob run` Uses Old Ones

`cronjob list` reads from the disk file. `cronjob run` dispatches to the gateway's in-memory job definition. The gateway only syncs from disk on startup or explicit pause/enable cycle.

> ⚠️ **Gateway shutdown rule:** Only use `hermes gateway restart` when the user explicitly approves. Never restart proactively.

### Cron Job Delivery — Discord Channel Format

**Correct format:** `discord:CHANNEL_ID` (e.g. `discord:1516578131312382114`)

**Wrong format that silently fails:** `platform:discord:CHANNEL_ID` — produces `"unknown platform 'platform'"` delivery error. The `platform:` prefix is NOT valid for the `deliver` field.

If Discord delivery fails after fixing the format, the bot may be in the server but lack permission to post in that channel. See `discord-connection-troubleshooting` skill for diagnosis.

### Cron Job Script vs Agent Task Mode

**`no_agent=False` (default):** LLM-driven job — the agent runs the prompt each tick. Skills can be attached. Good for: summarize a feed, draft a daily briefing, pick interesting items, follow conditional logic based on content.

**`no_agent=True`:** Script-only watchdog — the scheduler just runs `script` on schedule and delivers its stdout verbatim. No tokens, no agent loop, no model override honoured.

**When to use `no_agent=True`:**
- Recurring script-only pings where the script itself produces the exact message text
- Monitoring scripts (disk/GPU watchdogs, threshold alerts, heartbeats, CI notifications, API pollers with a fixed output shape)
- Jobs that should stay silent when there's nothing to report

**When to use `no_agent=False`:**
- Anything that needs reasoning
- Tasks where the output depends on external data or conditional logic
- Tasks where skills need to be loaded

### Cron Jobs Must Be Agent Tasks for Platform Tools

Cron jobs that need web access, platform tools (Discord, Slack, email), or agent-only features must run as agent tasks. Standalone scripts cannot use `hermes_tools` — the cron must run as an agent task with the appropriate toolsets enabled.

For script-only pings to platform APIs (Discord webhook, Slack webhook), write a short Node/Python script that the cron runs directly, but treat the script as a data-collection tool, not a self-contained automation.

### Fixing SILENT Suppression on Cron Output

Sometimes cron output is silently suppressed — the job runs but the result is not delivered. This can happen when:
1. The job's deliver target is misconfigured
2. The output is empty and `no_agent=True` (silent delivery on empty stdout — this is the WATCHDOG pattern)
3. The platform delivery fails silently

For watchdog-pattern jobs (monitoring scripts), design the script to stay quiet when there's nothing to report. For agent-driven jobs, ensure the final response contains meaningful content.

---

## Watchdog Patterns

Cron jobs that depend on long-lived daemons (Hindsight, Ollama, a custom FastAPI, a database) **must** do a pre-flight health check before doing the actual work. A naive cron prompt that just calls the service will silently fail (or hang) if the daemon died between runs.

### The Pattern: Pre-Flight + Self-Heal + Bail

```text
PRE-FLIGHT (mandatory — daemon must be up before <task>):
1. Run: curl -sf -m 5 http://localhost:PORT/health
2. If it fails (non-200 or connection refused), run the keepalive:
     ~/.hermes/scripts/<service>-keepalive.sh
3. Re-check health: curl -sf -m 5 http://localhost:PORT/health
4. If still unhealthy after 2 attempts, report "❌ <service> daemon unreachable,
   <task> skipped" to <deliver target> and EXIT. Do NOT run the task against
   a dead daemon.

TASK:
1. ...
```

**Why this is needed even when a systemd supervisor is in place:** supervisors have a poll interval (typically 30s), so there's a window where the daemon is down and the supervisor hasn't yet restarted it. The cron pre-flight closes that window and self-heals without waiting 15 minutes for the next run.

**Why bail after 2 attempts, not loop forever:** if the keepalive fails twice, something is structurally wrong (DB migration broken, port conflict, missing binary). A tight restart loop in the cron will eat tokens and flood Discord with no-ops. Better to log clearly and skip this run — the supervisor will keep trying in the background.

**⚠️ Keepalive call timeout:** daemons with heavy initialization (model loading, embedded PostgreSQL, DB migrations) can take 60-120s to start. The keepalive script polls `/health` in a loop up to 120s, but the terminal calling it may have a shorter default timeout. **Set the terminal timeout for the keepalive call to at least 180s** (`timeout=180` in terminal tool, or the script gets killed mid-startup). If the keepalive does get killed early, check if the daemon process is still alive (`pgrep -f <daemon>`) and poll `/health` manually — the process is likely still initializing, not failed.

### Reference Implementation: Hindsight Session Ingest (2026-07-02)

The Hindsight Session Ingest cron (`925d93131194`, every 15 min) uses this exact pattern. The keepalive script and supervisor are bundled with the `hindsight-integration` skill:
- `~/.hermes/scripts/hindsight-keepalive.sh` — one-shot: check + restart if down
- `~/.hermes/scripts/hindsight-supervisor.sh` — long-lived supervisor for systemd

## Kanban Orchestrator Pattern

Decomposition playbook + specialist-roster conventions + anti-temptation rules for an orchestrator profile routing work through Kanban.

### The "Don't Do the Work Yourself" Rule

The orchestrator's job is to decompose and delegate, not to execute the work itself. Every task that could be done by a specialist should be delegated.

### Lifecycle
1. **Decompose** incoming work into atomic tasks
2. **Assign** to specialist workers based on role/roster
3. **Review** results, not execution details
4. **Compose** final deliverable from worker outputs

### Kanban Worker Conventions

Workers receive tasks via `delegate_task`. Each worker:
- Reports completion with a verifiable handle (URL, ID, absolute path)
- Cannot use `clarify` — tasks must be self-contained
- Should use session_search for cross-session context

### Anti-Temptation Rules
- Don't pick up tasks that belong in another specialist's queue
- Don't "help" by doing work that should be delegated — it creates a bottleneck
- Review the output, not the execution trace

### Cron Job Prompt Update Workflow (legacy / fallback)

The CLI workflow above is preferred. The file-editing flow is retained for cases where the CLI doesn't support the change (e.g. unusual `deliver` targets, schedule tweaks on some Hermes versions):

1. `cronjob list` — find the `job_id` of the job to update
2. Edit `~/.hermes/cron/jobs.json` directly (Python or terminal `sed`/`cat`)
3. **Pause and unpause the job:** `cronjob pause <job_id>` then `cronjob enable <job_id>`
4. Verify with `cronjob list` — `prompt_preview` must show new text
5. `cronjob run <job_id>` — will now use the updated prompt

Or: `hermes gateway restart` (requires user approval) — authoritative sync.

---

## Cron + Vercel Background processes

For long-running processes triggered by cron:
- Use `terminal(background=True)` with `notify_on_complete=True`
- Or use `cronjob` with `no_agent=True` and a script that stays resident
- For Vercel: combine with Vercel Cron (`vercel.json` `crons` block) for scheduled invocations

See `vps-background-process` skill for running long-lived processes on remote VPS via SSH without timeout killing them.

---

## Daily Git-Sync Cron Pattern

A common cron pattern is: sync a local directory (e.g. `~/.hermes/`) to a GitHub repo on a schedule. The naive `git add && commit && push` recipe is fragile in cron because:

- The agent run has no interactive user to fix anything mid-stream
- The host may have diverged from `origin/main` since the last successful run
- The remote URL in `.git/config` may not contain credentials (cron can't prompt)
- Git may have no configured `user.email`/`user.name`

### Pitfalls and the Robust Recipe

**1. Configure git identity first (idempotent).** Cron runs have no global git config. Set repo-local identity inline, with a sensible noreply fallback:

```bash
cd ~/.hermes
git config user.email  "${HERMES_GIT_EMAIL:-yourusername@users.noreply.github.com}"
git config user.name   "${HERMES_GIT_NAME:-Your Name}"
```

If the cron prompt explicitly names an email/name, use those instead of the fallback.

**2. Verify the remote URL embeds the PAT.** The cron prompt may *state* the remote URL with a PAT in it, but the actual `.git/config` often has a credential-less URL. If `git push` ever prompts "could not read Username", the PAT is missing from the URL. Fix once with:

```bash
git remote set-url origin "https://${GH_PAT}@github.com/owner/repo.git"
```

…and verify the PAT is in the URL (`git remote -v`). This is a one-time setup; future pushes authenticate silently.

**3. If local and `origin/main` have diverged, reset and rebuild.** The naive `git pull --rebase` can stall in interactive mode (cron can't answer conflict prompts) and is fragile when there are untracked files (e.g. `*.lock`, `*.bak`) that block the rebase's reset step. The robust pattern for a "snapshot backup" repo is:

```bash
cd ~/.hermes
git fetch origin
# Reset to remote, throwing away the local-only commit (its content will be re-captured)
git reset --hard origin/main
# Re-stage current state of the working tree
git add -A
if git diff --cached --quiet; then
  echo "no changes"
else
  git commit -m "Daily sync: $(date '+%Y-%m-%d %H:%M')"
  git push origin main
fi
```

This is destructive locally but the goal is "remote is the source of truth, local is a working copy to snapshot" — exactly the cron backup pattern.

**4. Always check for changes before committing.** Wrap `git add -A` in a `git diff --cached --quiet` guard so the cron stays silent (and doesn't create empty commits) on quiet days:

```bash
git add -A
if git diff --cached --quiet; then
  echo "no changes"
else
  git commit -m "Daily sync: $(date '+%Y-%m-%d %H:%M')"
  git push origin main
fi
```

### Untracked-File Landmines

`git reset --hard` refuses to overwrite *untracked* files that exist locally but not on the remote. Common offenders in `~/.hermes/`:

- `*.db.init.lock`, `*.db-shm`, `*.db-wal` (sqlite sidecars)
- `*.bak`, `*.corrupt.*` (renamed config files)
- `*.lock` (gateway/memory locks)

**Before** running `git reset --hard origin/main`, remove or rename the offending untracked file:

```bash
rm -f <untracked-file>            # if it's safe to delete (lock/sidecar/bak)
# OR
mv <untracked-file> "${untracked_file}.removed.$(date +%s)"  # if you want to keep it
```

Failing to do this leaves the rebase/reset half-applied and forces a manual `git rebase --abort` recovery.

### Large-File-in-History Push Failure (GH001)

Even after removing a large file from the working tree and committing, `git push` can still be rejected if the file existed in any prior commit. GitHub checks the full object graph, not just HEAD.

**Error:**
```
remote: error: File state.db is 100.11 MB; this exceeds GitHub's file size limit of 100.00 MB
remote: error: GH001: Large files detected.
! [remote rejected] main -> main (pre-receive hook declined)
```

**Fix (one-time history rewrite):**
```bash
pip install git-filter-repo -q
git filter-repo --invert-paths --path state.db --path state.db-shm --path state.db-wal --force
# filter-repo removes the origin remote — re-add it:
git remote add origin "https://ghp_${GH_PAT}@github.com/owner/repo.git"
git push origin main --force
```

**Prevention (always):** Add binary database patterns to `.gitignore` before staging:
```bash
printf '%s\n' "*.db" "*.db-shm" "*.db-wal" "*.sqlite" "*.sqlite3" >> .gitignore
git add .gitignore && git commit -m "chore: ignore binary database files"
```

### Cron Prompt Must Match Real State

Cron prompts are often copy-pasted and go stale. A prompt that says "the remote URL has the PAT in it" when it doesn't is worse than no prompt at all — the agent trusts the prompt and wastes a turn discovering reality. If you maintain a daily-sync cron, audit the prompt against `git remote -v` and `git config --get user.email` periodically.

### Reference: First-Run Recovery (this session's actual transcript)

1. `git add -A && commit` → failed: "Author identity unknown"
2. Set repo-local `user.email`/`user.name`; re-ran → commit succeeded, push failed: "could not read Username"
3. `git remote -v` confirmed URL was credential-less; `git remote set-url` with PAT
4. `git push` → rejected: "remote contains work that you do not have locally" (3 commits ahead)
5. `git pull --rebase --autostash` → conflict on `config.yaml`, fell into interactive rebase state
6. `git rebase --abort` → blocked by untracked `kanban.db.init.lock`
7. `rm -f kanban.db.init.lock && git rebase --abort` → clean; diverged 1↔3
8. `git reset --hard origin/main` → aligned; then re-staged and pushed cleanly

The robust recipe above collapses steps 1–8 into a single idempotent command.