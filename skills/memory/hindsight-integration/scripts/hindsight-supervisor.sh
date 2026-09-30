#!/bin/bash
# Hindsight Daemon Supervisor
# Continuously monitors and restarts the Hindsight daemon.
# Designed to be the systemd service ExecStart so systemd can track
# the actual long-running process (Type=simple) and restart the whole loop on failure.
#
# Behavior:
#   - Polls http://localhost:9177/health every 30s
#   - If unhealthy, kills stale processes, restarts daemon, waits up to 240s for /health
#     (was 120s — too short for cold start on a 4GB VPS; caused supervisor stampedes
#     where kill_stale murdered the daemon mid-init. See SKILL.md "Supervisor stampede".)
#   - Logs to ~/.hermes/logs/hindsight-supervisor.log
#   - Exits non-zero only on fatal config errors (so systemd Restart=always fires)
#
# Verified 2026-07-02: with Type=simple + Restart=always, the supervisor
# survived a manual kill -9 of the daemon — restart succeeded at T+30s.
# This replaces a broken Type=forking+RemainAfterExit=yes setup that
# silently declared "success" while the real daemon died.

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

    # Wait for /health to come up
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
    # The daemon spawns hindsight-api (uvicorn) and embedded postgres.
    # Kill the whole process group so children don't orphan.
    pkill -9 -f "hindsight-api" 2>/dev/null || true
    pkill -9 -f "hindsight-embed daemon" 2>/dev/null || true
    pkill -9 -f "hindsight.*--daemon" 2>/dev/null || true
    # Embedded postgres data dir hint
    pkill -9 -f "hindsight-embed-hermes" 2>/dev/null || true
    sleep 2
}

# Verify daemon is healthy at startup; if not, start it.
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

# Main supervisor loop
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
