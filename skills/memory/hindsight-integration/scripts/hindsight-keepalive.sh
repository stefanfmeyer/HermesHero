#!/bin/bash
# Hindsight Keepalive Watchdog
# Standalone one-shot / looping restart script.
#
# Usage:
#   hindsight-keepalive.sh             # one-shot: check + restart if down, then exit
#   hindsight-keepalive.sh --loop      # poll forever, restart on failure
#   hindsight-keepalive.sh --status    # report daemon health and exit
#
# Use cases:
#   1. Cron pre-flight — the Hindsight Session Ingest cron calls this BEFORE
#      running the ingest, so it self-heals if the daemon died between runs.
#   2. Manual nudge — invoke by hand to restart a stuck daemon.
#   3. Alternative to systemd supervisor — on hosts without systemd, run
#      with --loop from a tmux/screen session or another cron entry.
#
# Exits 0 if daemon healthy (or successfully restarted), 1 otherwise.

set -u

PROFILE="hermes"
HEALTH_URL="http://localhost:9177/health"
HINDSIGHT_BIN="$HOME/.hermes/hermes-agent/venv/bin/hindsight-embed"
LOG_FILE="$HOME/.hermes/logs/hindsight-keepalive.log"
POLL_INTERVAL=30
START_TIMEOUT=120

mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*" | tee -a "$LOG_FILE" >&2
}

is_healthy() {
    local code
    code=$(curl -s -o /dev/null -w "%{http_code}" -m 5 "$HEALTH_URL" 2>/dev/null || echo "000")
    [ "$code" = "200" ]
}

kill_stale() {
    pkill -9 -f "hindsight-api" 2>/dev/null || true
    pkill -9 -f "hindsight-embed daemon" 2>/dev/null || true
    pkill -9 -f "hindsight.*--daemon" 2>/dev/null || true
    pkill -9 -f "hindsight-embed-hermes" 2>/dev/null || true
    sleep 2
}

start_daemon() {
    log "Starting Hindsight daemon (profile=$PROFILE)..."
    "$HINDSIGHT_BIN" -p "$PROFILE" daemon start >> "$LOG_FILE" 2>&1
    local rc=$?
    [ $rc -ne 0 ] && { log "hindsight-embed exited rc=$rc"; return $rc; }

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

case "${1:-once}" in
    --status)
        if is_healthy; then
            echo "Hindsight daemon: HEALTHY (profile=$PROFILE)"
            curl -s -m 3 "$HEALTH_URL"
            echo
            exit 0
        else
            echo "Hindsight daemon: UNREACHABLE on $HEALTH_URL"
            exit 1
        fi
        ;;
    --loop)
        log "=== Keepalive loop starting (pid=$$) ==="
        while true; do
            if is_healthy; then
                sleep "$POLL_INTERVAL"
            else
                log "Health check failed — restarting"
                kill_stale
                sleep 3
                if start_daemon; then
                    log "Restart succeeded"
                else
                    log "Restart failed; retry in ${POLL_INTERVAL}s"
                    sleep "$POLL_INTERVAL"
                fi
            fi
        done
        ;;
    once|--once|"")
        log "=== Keepalive one-shot ==="
        if is_healthy; then
            log "Already healthy — nothing to do"
            exit 0
        fi
        log "Unhealthy — killing stale processes and restarting"
        kill_stale
        if start_daemon; then
            log "One-shot restart succeeded"
            exit 0
        else
            log "One-shot restart FAILED"
            exit 1
        fi
        ;;
    -h|--help)
        cat <<EOF
hindsight-keepalive.sh — Hindsight daemon watchdog

Usage:
  hindsight-keepalive.sh [once]     # default: one-shot health check + restart if down
  hindsight-keepalive.sh --loop     # poll forever
  hindsight-keepalive.sh --status   # print health and exit
  hindsight-keepalive.sh --help     # this help
EOF
        exit 0
        ;;
    *)
        echo "Unknown arg: $1" >&2
        exit 2
        ;;
esac
