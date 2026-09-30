#!/bin/bash
# the workstation System Health Check
# Runs every 15 min via cron. Checks RAM, disk, CPU, temps, services.
# Two modes:
#   health-check.sh           # alert-only (silent if healthy)
#   health-check.sh --full    # always print full report
#
# Cron wiring (Hermes cron, every 15 min):
#   hermes cron create "*/15 * * * *" \
#     --name "System Health Check" \
#     --prompt 'Run bash ~/.hermes/scripts/health-check.sh. If output is non-empty, deliver it to Discord. If empty (healthy), deliver nothing.' \
#     --deliver discord:<channel_id>
#
# For always-post mode (user preference, verified 2026-07-23):
#   --prompt 'Run bash ~/.hermes/scripts/health-check.sh --full. Always deliver the full report to Discord.'
#
# Thresholds (adjust for your hardware):
#   RAM >85%, Swap >50%, SSD >80%, HDD >90%, CPU >90%, Load >2x CPU cores
#   CPU temp >80°C, NVMe temp >70°C

set -u

SSD_MOUNT="/"
HDD_MOUNT="/mnt/storage"
RAM_ALERT_PCT=85
SSD_ALERT_PCT=80
HDD_ALERT_PCT=90
CPU_ALERT_PCT=90
LOAD_ALERT_MULT=2
SWAP_ALERT_PCT=50
CPU_TEMP_ALERT=80     # °C
SSD_TEMP_ALERT=70     # °C (NVMe)

ALERTS=""
HAS_ALERT=0

add_alert() {
    ALERTS="${ALERTS}${1}\n"
    HAS_ALERT=1
}

# --- CPU cores ---
CPU_CORES=$(nproc)

# --- RAM ---
RAM_TOTAL=$(free -m | awk '/^Mem:/ {print $2}')
RAM_USED=$(free -m | awk '/^Mem:/ {print $3}')
RAM_AVAIL=$(free -m | awk '/^Mem:/ {print $7}')
RAM_PCT=$(awk "BEGIN {printf \"%.0f\", ($RAM_USED / $RAM_TOTAL) * 100}")

# --- Swap ---
SWAP_TOTAL=$(free -m | awk '/^Swap:/ {print $2}')
SWAP_USED=$(free -m | awk '/^Swap:/ {print $3}')
if [ "$SWAP_TOTAL" -gt 0 ]; then
    SWAP_PCT=$(awk "BEGIN {printf \"%.0f\", ($SWAP_USED / $SWAP_TOTAL) * 100}")
else
    SWAP_PCT=0
fi

# --- CPU usage ---
CPU_IDLE=$(top -bn1 | awk '/^%Cpu/ {print $8}')
CPU_PCT=$(awk "BEGIN {printf \"%.0f\", 100 - $CPU_IDLE}")

# --- Load average ---
LOAD_1M=$(awk '{print $1}' /proc/loadavg)
LOAD_5M=$(awk '{print $2}' /proc/loadavg)
LOAD_THRESHOLD=$(awk "BEGIN {printf \"%.2f\", $CPU_CORES * $LOAD_ALERT_MULT}")

# --- Disk usage ---
SSD_PCT=$(df -h "$SSD_MOUNT" | awk 'NR==2 {gsub(/%/,""); print $5}')
SSD_FREE=$(df -h "$SSD_MOUNT" | awk 'NR==2 {print $4}')
HDD_PCT=$(df -h "$HDD_MOUNT" | awk 'NR==2 {gsub(/%/,""); print $5}')
HDD_FREE=$(df -h "$HDD_MOUNT" | awk 'NR==2 {print $4}')

# --- Services ---
GATEWAY_STATUS=$(systemctl --user is-active hermes-gateway 2>/dev/null || echo "unknown")
HINDSIGHT_STATUS=$(systemctl --user is-active hindsight-embed 2>/dev/null || echo "unknown")
HINDSIGHT_HEALTH=$(curl -sf -m 3 http://localhost:9177/health 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['status'])" 2>/dev/null || echo "unreachable")

# --- Uptime ---
UPTIME=$(uptime -p | sed 's/up //')

# --- Temperatures (via hwmon) ---
# CPU temp from coretemp
CPU_TEMP=$(cat /sys/class/hwmon/hwmon*/temp1_input 2>/dev/null | head -1 | awk '{printf "%.0f", $1/1000}')
CPU_TEMP=${CPU_TEMP:-0}

# NVMe SSD temp (composite temperature)
NVME_TEMP=$(cat /sys/class/hwmon/hwmon*/temp2_input 2>/dev/null | head -1 | awk '{printf "%.0f", $1/1000}')
NVME_TEMP=${NVME_TEMP:-0}

# --- Check thresholds ---
if [ "$RAM_PCT" -ge "$RAM_ALERT_PCT" ]; then
    add_alert "🚨 **RAM**: ${RAM_PCT}% used (${RAM_USED}MB/${RAM_TOTAL}MB) — threshold ${RAM_ALERT_PCT}%"
fi

if [ "$SWAP_PCT" -ge "$SWAP_ALERT_PCT" ]; then
    add_alert "🚨 **Swap**: ${SWAP_PCT}% used (${SWAP_USED}MB/${SWAP_TOTAL}MB) — threshold ${SWAP_ALERT_PCT}%"
fi

if [ "$SSD_PCT" -ge "$SSD_ALERT_PCT" ]; then
    add_alert "🚨 **SSD**: ${SSD_PCT}% used (free: ${SSD_FREE}) — threshold ${SSD_ALERT_PCT}%"
fi

if [ "$HDD_PCT" -ge "$HDD_ALERT_PCT" ]; then
    add_alert "🚨 **HDD**: ${HDD_PCT}% used (free: ${HDD_FREE}) — threshold ${HDD_ALERT_PCT}%"
fi

if [ "$CPU_PCT" -ge "$CPU_ALERT_PCT" ]; then
    add_alert "🚨 **CPU**: ${CPU_PCT}% — threshold ${CPU_ALERT_PCT}%"
fi

LOAD_CMP=$(awk "BEGIN {print ($LOAD_1M > $LOAD_THRESHOLD) ? 1 : 0}")
if [ "$LOAD_CMP" = "1" ]; then
    add_alert "🚨 **Load**: ${LOAD_1M} (cores: ${CPU_CORES}, threshold: ${LOAD_THRESHOLD})"
fi

if [ "$GATEWAY_STATUS" != "active" ]; then
    add_alert "🚨 **Gateway**: ${GATEWAY_STATUS}"
fi

if [ "$HINDSIGHT_STATUS" != "active" ]; then
    add_alert "🚨 **Hindsight service**: ${HINDSIGHT_STATUS}"
fi

if [ "$HINDSIGHT_HEALTH" != "healthy" ]; then
    add_alert "🚨 **Hindsight daemon**: ${HINDSIGHT_HEALTH}"
fi

if [ "$CPU_TEMP" -ge "$CPU_TEMP_ALERT" ]; then
    add_alert "🚨 **CPU temp**: ${CPU_TEMP}°C — threshold ${CPU_TEMP_ALERT}°C"
fi

if [ "$NVME_TEMP" -ge "$SSD_TEMP_ALERT" ]; then
    add_alert "🚨 **NVMe temp**: ${NVME_TEMP}°C — threshold ${SSD_TEMP_ALERT}°C"
fi

# --- Output ---
FORCE_FULL="${1:-}"

if [ "$HAS_ALERT" = "1" ]; then
    echo "⚠️ **the workstation Health Alert** — issues detected:"
    echo ""
    echo -e "$ALERTS"
    echo ""
    echo "**System summary:**"
    echo "  RAM: ${RAM_PCT}% (${RAM_USED}MB/${RAM_TOTAL}MB) | Swap: ${SWAP_PCT}% (${SWAP_USED}MB)"
    echo "  CPU: ${CPU_PCT}% | Load: ${LOAD_1M}/${LOAD_5M} (cores: ${CPU_CORES})"
    echo "  SSD: ${SSD_PCT}% (free: ${SSD_FREE}) | HDD: ${HDD_PCT}% (free: ${HDD_FREE})"
    echo "  Temps: CPU ${CPU_TEMP}°C | NVMe ${NVME_TEMP}°C"
    echo "  Gateway: ${GATEWAY_STATUS} | Hindsight: ${HINDSIGHT_STATUS}/${HINDSIGHT_HEALTH}"
    echo "  Uptime: ${UPTIME}"
elif [ "$FORCE_FULL" = "--full" ]; then
    echo "✅ **the workstation Health** — all systems normal"
    echo ""
    echo "**RAM:** ${RAM_PCT}% used (${RAM_USED}MB/${RAM_TOTAL}MB) — ${RAM_AVAIL}MB available"
    echo "**Swap:** ${SWAP_PCT}% used (${SWAP_USED}MB/${SWAP_TOTAL}MB)"
    echo "**CPU:** ${CPU_PCT}% | Load: ${LOAD_1M}/${LOAD_5M}/${CPU_CORES} cores"
    echo "**SSD:** ${SSD_PCT}% used (free: ${SSD_FREE})"
    echo "**HDD:** ${HDD_PCT}% used (free: ${HDD_FREE})"
    echo "**Temps:** CPU ${CPU_TEMP}°C | NVMe ${NVME_TEMP}°C"
    echo "**Gateway:** ${GATEWAY_STATUS}"
    echo "**Hindsight:** ${HINDSIGHT_STATUS} / ${HINDSIGHT_HEALTH}"
    echo "**Uptime:** ${UPTIME}"
else
    # Silent — everything is fine, no output
    :
fi