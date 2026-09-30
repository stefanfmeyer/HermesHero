#!/bin/bash
# the workstation Dev Server Reaper
# Kills dev server processes (vite, node, python uvicorn, etc.) that have been
# idle (no terminal input) for more than 1 hour. Frees RAM for active work.
#
# Targets:
#   - Vite dev servers (vite --host / vite serve)
#   - Node dev servers (node server.js, npm exec, npx)
#   - Python uvicorn/fastapi dev servers
#   - Language servers (pyright, typescript-language-server, bash-language-server)
#   - esbuild service processes
#
# Exclusions:
#   - Hermes gateway (hermes_cli.main gateway run) — never touched
#   - Hindsight (hindsight-api, hindsight-embed) — never touched
#   - Tailscale (tailscaled) — never touched
#   - PostgreSQL (postgres) — never touched
#   - Processes started in the last 60 min (give them time to be used)
#   - Processes whose parent is the Hermes gateway PID (active session tools)
#
# Runs every 15 min via cron. Silent when nothing to kill.
# Use --dry-run to see what would be killed without killing.

set -u

IDLE_THRESHOLD_MIN=60
LOG_FILE="$HOME/.hermes/logs/dev-reaper.log"
PROTECTED_PATTERNS="hermes_cli\.main|hindsight|tailscaled|postgres|systemd|journald|sshd|bash -lic.*hermes"
DEV_PATTERNS="vite|node server\.js|npm exec|npx|uvicorn|fastapi|pyright-langserver|typescript-language-server|bash-language-server|esbuild"
FORCE_DRY="${1:-}"

mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*" >> "$LOG_FILE"
}

# Get the Hermes gateway PID (to protect its children)
GATEWAY_PID=$(pgrep -f "hermes_cli\.main gateway run" 2>/dev/null | head -1)

# Find dev server processes matching DEV_PATTERNS
killed=0
skipped=0

for pid in $(ps aux | grep -E "$DEV_PATTERNS" | grep -v grep | grep -vE "$PROTECTED_PATTERNS" | grep -v dev-reaper | awk '{print $2}'); do
    [ -z "$pid" ] && continue

    # Skip if this is a child of the gateway (active session tool)
    if [ -n "$GATEWAY_PID" ]; then
        ppid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')
        ancestor=$ppid
        is_child=0
        for _ in $(seq 1 10); do
            [ -z "$ancestor" ] && break
            if [ "$ancestor" = "$GATEWAY_PID" ]; then
                is_child=1
                break
            fi
            ancestor=$(ps -o ppid= -p "$ancestor" 2>/dev/null | tr -d ' ')
        done
        [ "$is_child" = "1" ] && skipped=$((skipped + 1)) && continue
    fi

    # Get elapsed time in seconds
    elapsed=$(ps -o etimes= -p "$pid" 2>/dev/null | tr -d ' ')
    [ -z "$elapsed" ] && continue

    elapsed_min=$((elapsed / 60))
    cmd=$(ps -o args= -p "$pid" 2>/dev/null | head -c 120)

    if [ "$elapsed_min" -ge "$IDLE_THRESHOLD_MIN" ]; then
        if [ "$FORCE_DRY" = "--dry-run" ]; then
            echo "WOULD KILL: PID=$pid elapsed=${elapsed_min}m cmd=$cmd"
        else
            kill -9 "$pid" 2>/dev/null
            log "Killed PID=$pid elapsed=${elapsed_min}m cmd=$cmd"
            echo "Killed: PID=$pid (${elapsed_min}m idle) — $cmd"
            killed=$((killed + 1))
        fi
    else
        skipped=$((skipped + 1))
    fi
done

if [ "$killed" -gt 0 ]; then
    log "Reaped $killed dev process(es), skipped $skipped (recent/protected)"
elif [ "$FORCE_DRY" = "--dry-run" ]; then
    [ "$skipped" -gt 0 ] && echo "Skipped $skipped process(es) — too recent or protected"
fi