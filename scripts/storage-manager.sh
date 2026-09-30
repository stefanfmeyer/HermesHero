#!/bin/bash
# YourHost Storage Manager
# Runs daily via cron. Manages SSD/HDD storage split.
# - Cleans temp/cache files older than 3 days on SSD
# - Checks SSD usage, alerts if >80%
# - Weekly: sends storage summary to Discord
#
# Usage:
#   storage-manager.sh           # daily run (sweep + alert if needed)
#   storage-manager.sh --report  # force weekly report

set -u

SSD_DEV="/dev/nvme0n1p2"
HDD_DEV="/dev/sda"
SSD_MOUNT="/"
HDD_MOUNT="/mnt/storage"
ALERT_THRESHOLD=80
RETENTION_DAYS=3
LOG_FILE="$HOME/.hermes/logs/storage-manager.log"
REPORT_FLAG="$HOME/.hermes/logs/.storage-weekly-flag"

mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*" >> "$LOG_FILE"
}

get_ssd_usage_pct() {
    df -h "$SSD_MOUNT" | awk 'NR==2 {gsub(/%/,""); print $5}'
}

get_ssd_free_gb() {
    df -h "$SSD_MOUNT" | awk 'NR==2 {print $4}'
}

get_hdd_usage_pct() {
    df -h "$HDD_MOUNT" | awk 'NR==2 {gsub(/%/,""); print $5}'
}

get_hdd_free_gb() {
    df -h "$HDD_MOUNT" | awk 'NR==2 {print $4}'
}

get_dir_size() {
    du -sh "$1" 2>/dev/null | awk '{print $1}'
}

# --- Sweep: clean temp/cache files older than RETENTION_DAYS on SSD ---
sweep() {
    log "=== Starting sweep (retention=${RETENTION_DAYS}d) ==="

    # Clean Hermes cache
    if [ -d ~/.hermes/cache ]; then
        find ~/.hermes/cache/ -type f -mtime +${RETENTION_DAYS} -delete 2>/dev/null
        log "Cleaned ~/.hermes/cache/ (files older than ${RETENTION_DAYS}d)"
    fi

    # Clean /tmp (Hermes temp files, build artifacts)
    find /tmp -maxdepth 1 -type f -mtime +${RETENTION_DAYS} -name "hermes-*" -delete 2>/dev/null
    find /tmp -maxdepth 1 -type d -mtime +${RETENTION_DAYS} -name "hermes-*" -exec rm -rf {} + 2>/dev/null
    find /tmp -maxdepth 1 -type f -mtime +${RETENTION_DAYS} -name "hermes-work-*" -delete 2>/dev/null
    find /tmp -maxdepth 1 -type d -mtime +${RETENTION_DAYS} -name "hermes-work-*" -exec rm -rf {} + 2>/dev/null
    log "Cleaned /tmp (hermes/work files older than ${RETENTION_DAYS}d)"

    # Clean pip cache
    if [ -d ~/.cache/pip ]; then
        find ~/.cache/pip/ -type f -mtime +${RETENTION_DAYS} -delete 2>/dev/null
        log "Cleaned ~/.cache/pip/"
    fi

    # Clean npm cache (if exists)
    if [ -d ~/.cache/npm ]; then
        find ~/.cache/npm/ -type f -mtime +${RETENTION_DAYS} -delete 2>/dev/null
        log "Cleaned ~/.cache/npm/"
    fi

    # Clean old logs (keep 7 days on SSD, compress older)
    if [ -d ~/.hermes/logs ]; then
        find ~/.hermes/logs/ -name "*.log" -mtime +7 -exec gzip -f {} \; 2>/dev/null
        find ~/.hermes/logs/ -name "*.log.gz" -mtime +30 -delete 2>/dev/null
        log "Rotated logs (compressed >7d, deleted >30d)"
    fi

    # Clean uv cache (old entries)
    if [ -d ~/.cache/uv ]; then
        find ~/.cache/uv/ -maxdepth 1 -type d -mtime +${RETENTION_DAYS} -name "archive-v0*" -exec rm -rf {} + 2>/dev/null
        log "Cleaned ~/.cache/uv/ (old archives)"
    fi

    log "Sweep complete"
}

# --- Alert: check SSD usage ---
check_alert() {
    local ssd_pct
    ssd_pct=$(get_ssd_usage_pct)
    log "SSD usage: ${ssd_pct}%"

    if [ "$ssd_pct" -ge "$ALERT_THRESHOLD" ]; then
        echo "🚨 **STORAGE ALERT** — SSD is at ${ssd_pct}% capacity (threshold: ${ALERT_THRESHOLD}%)"
        echo "SSD free: $(get_ssd_free_gb) | HDD free: $(get_hdd_free_gb)"
        echo ""
        echo "Top SSD consumers:"
        du -sh ~/.hermes/ /tmp/ ~/.cache/ /var/ 2>/dev/null | sort -rh | head -10
        echo ""
        echo "Action needed: move data to HDD or clean up temp files."
        return 1
    fi
    return 0
}

# --- Weekly report ---
weekly_report() {
    local ssd_pct ssd_free hdd_pct hdd_free
    ssd_pct=$(get_ssd_usage_pct)
    ssd_free=$(get_ssd_free_gb)
    hdd_pct=$(get_hdd_usage_pct)
    hdd_free=$(get_hdd_free_gb)

    echo "📊 **YourHost Weekly Storage Report**"
    echo ""
    echo "**SSD (256GB — short-term, <3d retention):**"
    echo "  Usage: ${ssd_pct}% | Free: ${ssd_free}"
    echo "  OS + Hermes runtime"
    echo ""
    echo "**HDD (1TB — long-term storage):**"
    echo "  Usage: ${hdd_pct}% | Free: ${hdd_free}"
    echo ""
    echo "**HDD breakdown:**"
    du -sh /mnt/storage/hermes/skills/ /mnt/storage/hermes/memories/ /mnt/storage/hermes/sessions/ /mnt/storage/hermes/state.db /mnt/storage/hermes/hindsight_data/ /mnt/storage/hermes/pg0_data/ 2>/dev/null | sort -rh
    echo ""
    echo "**SSD top consumers:**"
    du -sh ~/.hermes/ ~/.cache/ /tmp/ 2>/dev/null | sort -rh | head -5
    echo ""
    echo "**Hermes services:**"
    systemctl --user is-active hermes-gateway 2>/dev/null | awk '{print "  Gateway: "$1}'
    systemctl --user is-active hindsight-embed 2>/dev/null | awk '{print "  Hindsight: "$1}'
    curl -sf -m 3 http://localhost:9177/health 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  Hindsight health: {d[\"status\"]}')" 2>/dev/null || echo "  Hindsight health: unreachable"
}

# --- Main ---
log "=== Storage manager run ==="

# Always sweep
sweep

# Check if it's Sunday (day 0) for weekly report, or --report flag
DOW=$(date +%u)
FORCE_REPORT="${1:-}"

if [ "$DOW" = "7" ] || [ "$FORCE_REPORT" = "--report" ]; then
    log "Generating weekly report"
    weekly_report
fi

# Always check for alert
check_alert

log "=== Storage manager complete ==="