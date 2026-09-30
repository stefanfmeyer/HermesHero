#!/bin/bash
# Restart the memory daemon + prove the RUNNING process got the new model.
# Script file (not inline) so the unit's ExecStop pkill patterns can never match
# this shell's own command line.
set -u

echo "== pre-restart process env =="
for pid in $(ls /proc | grep -E '^[0-9]+$'); do
  [ -r "/proc/$pid/environ" ] || continue
  v=$(tr '\0' '\n' < "/proc/$pid/environ" 2>/dev/null | grep '^HINDSIGHT_API_LLM_MODEL=' || true)
  [ -n "$v" ] && echo "  pid $pid $v"
done

echo "== restarting unit =="
systemctl --user restart hindsight-embed
echo "restart issued, exit=$?"

echo "== waiting for health (cold start up to ~200s) =="
for i in $(seq 1 40); do
  code=$(curl -s -o /dev/null -w '%{http_code}' -m 5 http://localhost:9177/health || echo 000)
  echo "  t=$((i*5))s health=$code"
  [ "$code" = "200" ] && break
  sleep 5
done

echo "== post-restart process env =="
for pid in $(ls /proc | grep -E '^[0-9]+$'); do
  [ -r "/proc/$pid/environ" ] || continue
  v=$(tr '\0' '\n' < "/proc/$pid/environ" 2>/dev/null | grep '^HINDSIGHT_API_LLM_MODEL=' || true)
  [ -n "$v" ] && echo "  pid $pid $v"
done

echo "== unit state =="
systemctl --user show hindsight-embed -p ActiveState -p ExecMainStartTimestamp
