#!/bin/bash
# Hindsight Daemon Supervisor
# Continuously monitors and restarts the Hindsight daemon.
# Designed to be the systemd service ExecStart so systemd can track
# the actual long-running process (Type=simple) and restart the whole loop on failure.

set -u

PROFILE="hermes"
HEALTH_URL="http://localhost:9177/health"
HINDSIGHT_BIN="$HOME/.hermes/hermes-agent/venv/bin/hindsight-embed"
LOG_FILE="$HOME/.hermes/logs/hindsight-supervisor.log"
POLL_INTERVAL=30
START_TIMEOUT=240

mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*" >> "$LOG_FILE"
}

is_healthy() {
    local code
    code=$(curl -s -o /dev/null -w "%{http_code}" -m 5 "$HEALTH_URL" 2>/dev/null || echo "000")
    [ "$code" = "200" ]
}

start_daemon() {
    log "Starting Hindsight daemon (profile=$PROFILE)..."
    "$HINDSIGHT_BIN" -p "$PROFILE" daemon start >> "$LOG_FILE" 2>&1
    local rc=$?
    if [ $rc -ne 0 ]; then
        log "hindsight-embed daemon start exited rc=$rc"
        return $rc
    fi

    local elapsed=0
    while [ $elapsed -lt $START_TIMEOUT ]; do
        if is_healthy; then
            log "Daemon healthy after ${elapsed}s"
            return 0
        fi
        sleep 5
        elapsed=$((elapsed + 5))
    done
    log "Daemon failed /health within ${START_TIMEOUT}s"
    return 1
}

kill_stale() {
    pkill -9 -f "hindsight-api" 2>/dev/null || true
    pkill -9 -f "hindsight-embed daemon" 2>/dev/null || true
    pkill -9 -f "hindsight.*--daemon" 2>/dev/null || true
    pkill -9 -f "hindsight-embed-hermes" 2>/dev/null || true
    sleep 2
}

log "=== Supervisor starting (pid=$$) ==="
if ! is_healthy; then
    log "Initial state: daemon not healthy, attempting start"
    kill_stale
    if ! start_daemon; then
        log "FATAL: initial start failed; will keep retrying in main loop"
    fi
else
    log "Initial state: daemon already healthy"
fi

while true; do
    if is_healthy; then
        sleep "$POLL_INTERVAL"
    else
        log "Health check failed — daemon down. Restarting."
        kill_stale
        sleep 3
        if start_daemon; then
            log "Restart succeeded"
        else
            log "Restart failed; will retry in ${POLL_INTERVAL}s"
            sleep "$POLL_INTERVAL"
        fi
    fi
done