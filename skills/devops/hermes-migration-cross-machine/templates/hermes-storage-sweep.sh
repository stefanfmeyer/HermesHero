#!/usr/bin/env bash
# ~/.hermes/scripts/hermes-storage-sweep.sh
#
# Hermes storage management for the SSD/HDD split architecture.
# SSD = hot/short-term (<3 days). HDD (/mnt/storage) = cold/long-term.
#
# Modes:
#   ./hermes-storage-sweep.sh            # daily sweep (default)
#   ./hermes-storage-sweep.sh --report   # weekly: just print du output, no sweeps
#   ./hermes-storage-sweep.sh --dry-run  # show what would happen, change nothing
#
# Exit codes:
#   0 = all OK
#   1 = sweep ran but alerts triggered (SSD >80% or HDD >85%)
#   2 = sweep failed (could not write, mount missing, etc.)
#
# Wired up by:
#   - Daily cron (03:00): sweep + alert on threshold breach
#   - Weekly cron (Sun 09:00): --report mode for human-readable summary
#
# User preference (encoded 2026-07-23): 256GB SSD is short-term, 1TB HDD is long-term.
# Anything older than 3 days on the SSD gets moved to HDD automatically.

set -u  # NOT -e: individual command failures should not abort the whole sweep

# --- Configuration ---
SSD_WARN_PCT=80
HDD_WARN_PCT=85
SSD_MAX_AGE_DAYS=3
HERMES_DATA=/mnt/storage/hermes
HERMES_HOME=${HERMES_HOME:-$HOME/.hermes}
LOG_DIR=$HERMES_HOME/logs
LOG_FILE=$LOG_DIR/storage-sweep.log
REPORT=0
DRY_RUN=0
ALERTS=()

for arg in "$@"; do
    case "$arg" in
        --report) REPORT=1 ;;
        --dry-run) DRY_RUN=1 ;;
        -h|--help)
            sed -n '2,25p' "$0"
            exit 0
            ;;
        *) echo "Unknown arg: $arg" >&2; exit 2 ;;
    esac
done

mkdir -p "$LOG_DIR"
exec >> "$LOG_FILE" 2>&1
echo "=== storage-sweep start: $(date -Iseconds) mode=$( [[ $REPORT -eq 1 ]] && echo report || ([[ $DRY_RUN -eq 1 ]] && echo dry-run || echo sweep) ) ==="

run() {
    if [[ $DRY_RUN -eq 1 ]]; then
        echo "[DRY-RUN] $*"
    else
        "$@"
    fi
}

alert() {
    ALERTS+=("$1")
    echo "ALERT: $1"
}

# --- 1. Verify HDD is mounted ---
if ! mountpoint -q /mnt/storage; then
    echo "FATAL: /mnt/storage not mounted — sweep aborted"
    exit 2
fi
if [[ ! -d $HERMES_DATA ]]; then
    echo "FATAL: $HERMES_DATA missing — symlink architecture not set up"
    exit 2
fi

# --- 2. Disk usage check ---
SSD_PCT=$(df --output=pcent "$HERMES_HOME" | tail -1 | tr -dc '0-9')
HDD_PCT=$(df --output=pcent /mnt/storage | tail -1 | tr -dc '0-9')
echo "SSD usage: ${SSD_PCT}% | HDD usage: ${HDD_PCT}%"

if [[ $SSD_PCT -ge $SSD_WARN_PCT ]]; then
    alert "SSD at ${SSD_PCT}% (threshold ${SSD_WARN_PCT}%)"
fi
if [[ $HDD_PCT -ge $HDD_WARN_PCT ]]; then
    alert "HDD at ${HDD_PCT}% (threshold ${HDD_WARN_PCT}%)"
fi

# --- 3. Report mode: print du summary and exit ---
if [[ $REPORT -eq 1 ]]; then
    echo "--- Hermes data (HDD) ---"
    du -sh "$HERMES_DATA"/* 2>/dev/null | sort -hr
    echo "--- Hermes runtime (SSD) ---"
    du -sh "$HERMES_HOME"/hermes-agent "$HERMES_HOME"/cache 2>/dev/null
    echo "--- Sessions (top 10 by size) ---"
    du -sh "$HERMES_DATA"/sessions/*/ 2>/dev/null | sort -hr | head -10
    exit 0
fi

# --- 4. Age out cache files from SSD ---
# Cache should be transient. Anything >3 days old is dead weight.
if [[ -d $HERMES_HOME/cache ]]; then
    # Count before
    BEFORE=$(du -sb "$HERMES_HOME/cache" 2>/dev/null | awk '{print $1}')
    run find "$HERMES_HOME/cache" -type f -atime +$SSD_MAX_AGE_DAYS -delete
    run find "$HERMES_HOME/cache" -type d -empty -delete 2>/dev/null
    AFTER=$(du -sb "$HERMES_HOME/cache" 2>/dev/null | awk '{print $1}')
    FREED=$(( ${BEFORE:-0} - ${AFTER:-0} ))
    echo "Cache: freed ${FREED} bytes (${SSD_MAX_AGE_DAYS}-day+ access age)"
fi

# --- 5. Age out any non-symlinked files in HERMES_HOME that should be on HDD ---
# These are the paths that should be symlinks to the HDD. If anything
# accidentally got written locally (e.g. before the symlink was set up),
# the symlink may have been replaced with a real dir. Detect and move.
for link in skills memories state.db sessions logs; do
    target="$HERMES_HOME/$link"
    if [[ -e $target && ! -L $target ]]; then
        echo "WARN: $link is a real path, expected symlink — moving to HDD"
        run mv "$target" "$HERMES_DATA/$link"
        run ln -s "$HERMES_DATA/$link" "$target"
    fi
done

# --- 6. Compress old session transcripts on HDD (older than 30 days) ---
if [[ -d $HERMES_DATA/sessions ]]; then
    COMPRESSED=$(find "$HERMES_DATA/sessions" -name "*.jsonl" -mtime +30 2>/dev/null | wc -l)
    if [[ $COMPRESSED -gt 0 ]]; then
        echo "Compressing $COMPRESSED old session transcripts (>30 days)"
        run find "$HERMES_DATA/sessions" -name "*.jsonl" -mtime +30 -exec gzip {} \;
    fi
fi

# --- 7. Vacuum SQLite state.db (reclaim space from deleted sessions) ---
if [[ -f $HERMES_DATA/state.db ]] && command -v sqlite3 >/dev/null; then
    BEFORE_DB=$(stat -c%s "$HERMES_DATA/state.db")
    run sqlite3 "$HERMES_DATA/state.db" "VACUUM;" 2>/dev/null
    AFTER_DB=$(stat -c%s "$HERMES_DATA/state.db")
    SAVED=$(( BEFORE_DB - AFTER_DB ))
    echo "state.db VACUUM: saved $SAVED bytes"
fi

# --- 8. Final disk check post-sweep ---
SSD_PCT_AFTER=$(df --output=pcent "$HERMES_HOME" | tail -1 | tr -dc '0-9')
HDD_PCT_AFTER=$(df --output=pcent /mnt/storage | tail -1 | tr -dc '0-9')
echo "Post-sweep: SSD ${SSD_PCT_AFTER}% | HDD ${HDD_PCT_AFTER}%"

# Re-check thresholds post-sweep
if [[ $SSD_PCT_AFTER -ge $SSD_WARN_PCT ]]; then
    alert "SSD still at ${SSD_PCT_AFTER}% after sweep (threshold ${SSD_WARN_PCT}%)"
fi

# --- 9. Summary ---
echo "=== storage-sweep end: $(date -Iseconds) alerts=${#ALERTS[@]} ==="

# Output one-line summary to stdout for cron to capture
echo "STORAGE_SWEEP: ssd=${SSD_PCT_AFTER}% hdd=${HDD_PCT_AFTER}% alerts=${#ALERTS[@]}"

if [[ ${#ALERTS[@]} -gt 0 ]]; then
    printf 'ALERT: %s\n' "${ALERTS[@]}"
    exit 1
fi
exit 0
