#!/bin/bash
# Daily GitHub Backup Sync for Hermes data
# Syncs skills, memories, sessions, and scripts to a private GitHub repo.
# Uses a dedicated SSH key for the repo owner account.
#
# Usage:
#   backup-sync.sh              # run the sync
#   backup-sync.sh --dry-run     # show what would be pushed
#
# Setup:
#   1. Clone the backup repo: git clone git@github.com:<user>/<repo>.git ~/<repo>
#   2. Set per-repo SSH key: git config core.sshCommand "ssh -i ~/.ssh/id_ed25519_<account>"
#   3. Create .gitignore to exclude secrets (.env, auth.json, config.yaml, *.db, etc.)
#   4. Schedule as a Hermes cron at 2 AM daily
#
# What gets synced:
#   - ~/.hermes/skills/     → repo/skills/
#   - ~/.hermes/memories/   → repo/memories/
#   - ~/.hermes/sessions/   → repo/sessions/
#   - ~/.hermes/scripts/    → repo/scripts/   (backup, health check, storage scripts)
#
# What does NOT get synced (must be in .gitignore):
#   - .env, auth.json, config.yaml (secrets)
#   - cache/, logs/, hindsight/, hermes-agent/ (runtime/binary)
#   - bin/, lsp/, webui/ (binaries)

set -u

REPO_DIR="${REPO_DIR:-$HOME/the agent}"
LOG_FILE="$HOME/.hermes/logs/backup-sync.log"
GIT_KEY="${GIT_KEY:-$HOME/.ssh/id_ed25519_personal}"

mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*" >> "$LOG_FILE"
}

log "=== Daily backup sync starting ==="

if [ ! -d "$REPO_DIR/.git" ]; then
    log "ERROR: Repo not found at $REPO_DIR"
    echo "❌ Backup failed: repo not found at $REPO_DIR"
    exit 1
fi

cd "$REPO_DIR"

# Pull remote changes first
log "Pulling remote changes..."
GIT_SSH_COMMAND="ssh -i $GIT_KEY" git pull --rebase origin main 2>>"$LOG_FILE"
if [ $? -ne 0 ]; then
    log "WARNING: git pull failed, continuing with sync anyway"
fi

# Sync data directories
for dir in skills memories sessions scripts; do
    log "Syncing $dir..."
    mkdir -p "$REPO_DIR/$dir"
    rsync -a --delete --exclude='.git' "$HOME/.hermes/$dir/" "$REPO_DIR/$dir/" 2>>"$LOG_FILE"
done

# Stage, commit, push
git add -A 2>>"$LOG_FILE"

if git diff --cached --quiet; then
    log "No changes to commit — everything already in sync"
    echo "✅ Backup sync complete — no changes since last sync"
    exit 0
fi

CHANGED=$(git diff --cached --name-only | wc -l)
log "Committing $CHANGED changed file(s)..."
git commit -m "Daily sync: $(date -u '+%Y-%m-%d %H:%M')" 2>>"$LOG_FILE"

log "Pushing to GitHub..."
GIT_SSH_COMMAND="ssh -i $GIT_KEY" git push origin main 2>>"$LOG_FILE"

if [ $? -eq 0 ]; then
    log "Push successful — $CHANGED file(s) synced"
    echo "✅ Backup sync complete — $CHANGED file(s) pushed to GitHub"
else
    log "ERROR: git push failed"
    echo "❌ Backup sync failed: git push error"
    exit 1
fi

log "=== Daily backup sync complete ==="