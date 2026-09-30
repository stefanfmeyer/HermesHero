#!/bin/bash
# Prove a REAL Hindsight LLM call uses the new model + exercise a retain/recall cycle.
LOG=/mnt/storage/hermes/hindsight_data/profiles/hermes.log

echo "== client init line =="
grep -E "client initialized|Connection verified" "$LOG" | tail -5

echo
echo "== real call: retain via API =="
curl -s -X POST http://localhost:9177/memories \
  -H 'Content-Type: application/json' \
  -d '{"bank_id":"hermes","content":"Connectivity check: hindsight retain path is alive.","context":"infra check","tags":["migration"]}' \
  -m 180 -o /tmp/hs_retain.json -w 'http=%{http_code}\n'
head -c 400 /tmp/hs_retain.json; echo

echo
echo "== model used for the call (post-restart) =="
tail -c 200000 "$LOG" | grep -oE "scope=[a-z_]+, model=[^,]+" | tail -8

echo
echo "== models seen since last client init =="
python3 - <<'EOF'
import re
t=open("/mnt/storage/hermes/hindsight_data/profiles/hermes.log",errors="ignore").read()[-300000:]
i=t.rfind("client initialized")
post=t[i:] if i>0 else t
print(sorted(set(re.findall(r"model=(\S+?)[,\s]", post))))
EOF
