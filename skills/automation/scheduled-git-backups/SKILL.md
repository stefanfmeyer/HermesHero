---
name: scheduled-git-backups
description: Class-level patterns for scheduled (cron) backup jobs that sync local directories to a GitHub repo — diagnosis of "sync didn't work" reports, rsync source-dir pitfalls, git identity/SSH auth for unattended runs, and full-fidelity SQLite store snapshots that bypass .gitignore.
trigger: Creating, debugging, or reviewing a cron/script job that backs up or syncs local data (Hermes dirs, session stores, notes) to a GitHub repo or remote; user reports a backup/sync job "didn't work" or looks stale.
tags: [backup, cron, git, rsync, sqlite, github]
---

# Scheduled Git Backup Jobs

Class-level playbook for unattended "sync local state to GitHub on a schedule" jobs (e.g. the workstation Daily GitHub Backup via `backup-sync.sh`). Complements the cron-management patterns in `cron-patterns` (job immutability, delivery formats, watchdog pre-flight) — this skill covers the sync payload itself.

## Job Anatomy

A robust backup-sync script has: its own log file (`~/.hermes/logs/<job>.log` — never rely on `last_status` alone), idempotent git identity setup, a pull/rebase attempt that tolerates failure, per-directory rsync syncs, a `git diff --cached --quiet` guard so quiet days produce no empty commit, then commit + push with status output (✅/❌).

## Diagnosing "the daily sync didn't work"

When the user reports a sync cron "didn't work", work through this order before assuming failure:

1. **`last_status: "ok"` only means clean exit** — it says nothing about whether data actually synced. Read the script's own log for rsync errors, push failures, or "no changes" exits.
2. **Check wall-clock vs schedule.** A daily 02:00 job reported "broken" at 01:00 with a last run ~23h ago is just the normal gap. Confirm `next_run_at` before debugging anything.
3. **Check the delivery target.** The job may deliver its ✅/❌ message to a different Discord channel (`discord:<id>`) than the one the user is looking at — no message in the current channel is not evidence of failure.
4. **Verify ground truth**, not statuses: `git fetch origin` then `git rev-list --left-right --count main...origin/main` (expect `0 0`), and compare newest files (`ls -t`) in repo vs source.

Report what you find, not what the status claimed — in one real case the job was fine and the "failure" was just schedule phase + wrong channel.

## rsync Pitfall: missing source dirs fail every run (exit 23)

`rsync -a --delete ~/.hermes/notes/ dest/` errors with `change_dir ... failed: No such file or directory` (code 23) when the source doesn't exist. The script keeps running afterwards, so `last_status` stays "ok" and the failure hides in the log indefinitely. Guard every source dir:

```bash
mkdir -p ~/.hermes/plans ~/.hermes/notes
rsync -a --delete ~/.hermes/plans/ "$REPO_DIR/plans/"
rsync -a --delete ~/.hermes/notes/ "$REPO_DIR/notes/"
```

## Unattended Git Auth

- **SSH keys (preferred on machines with key aliases):** use `GIT_SSH_COMMAND="ssh -i ~/.ssh/<key>"` inline on the pull/push calls and an SSH remote URL (`git@github.com:owner/repo.git`). No PAT in URL, nothing to expire. See memory: personal repos use `id_ed25519_personal`.
- **PAT variant:** embed in remote URL (`https://${GH_PAT}@github.com/...`), verify with `git remote -v`.
- Set repo-local identity inline (cron shells may lack global git config): `git config user.name/user.email` before commit.

## Full-Fidelity SQLite Store Snapshots

Modern Hermes stores sessions in `state.db` (SQLite; often a symlink into a storage volume, e.g. `~/.hermes/state.db -> /mnt/storage/hermes/state.db`). Legacy JSONL transcripts stop being written once the DB store is canonical, and markdown session exports are **lossy** (tool/system dumps collapsed). A backup repo carrying only markdown + old JSONLs silently lacks full-fidelity data for recent sessions. When the user asks for "full sessions and sessions data", include a raw store snapshot.

**Pattern — SQLite online backup API, named to bypass `.gitignore`:**

```bash
python3 -c "
import sqlite3, os
src='/mnt/storage/hermes/state.db'
if not os.path.exists(src): src='$HOME/.hermes/state.db'
dst='$HOME/the agent/state.db.snapshot'
s=sqlite3.connect(src); d=sqlite3.connect(dst)
s.backup(d); d.close(); s.close()
"
```

- `s.backup(d)` yields a consistent copy **even while the gateway writes** — safe for 24/7 daemons, no lock juggling, no `.db-wal`/`.db-shm` sidecar issues.
- **Name it `*.snapshot`, not `*.db`** — backup repo `.gitignore` files typically exclude `*.db` (and the GH001 >100 MB rule makes committing real DBs dangerous). The `.snapshot` suffix stages normally.
- Verify after run: snapshot opens (`sqlite3` count from `sessions`/`messages`) and `main...origin/main` = `0 0`.
- **Growth tradeoff:** the full snapshot is re-committed daily → repo grows ~snapshot-size/day (~27 MB/day for a 27 MB store). Default to safety-first full snapshots and state the tradeoff to the user; offer rotation (keep N days) or LFS only if it becomes a problem.
- Wrap in an `if` so a snapshot failure logs a WARNING and the rest of the sync still proceeds.

## Reference


## Verification Checklist (after any change or manual run)

1. Script log: no rsync code-23 errors, push line `main -> main` present, "Push successful".
2. `git rev-list --left-right --count main...origin/main` → `0 0`.
3. New artifacts exist in the repo (e.g. `state.db.snapshot` present, opens, row counts sane).
4. Next scheduled run (`next_run_at`) is set — the cron picks up changes automatically; no gateway restart needed for script-content edits (the scheduler reads the script file fresh each run).
