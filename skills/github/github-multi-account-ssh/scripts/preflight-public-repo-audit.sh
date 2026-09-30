#!/usr/bin/env bash
#
# Pre-push audit for a repo that is about to become public — or that was built by
# copying files out of a PRIVATE repo.
#
# Run from the repo root, ideally BEFORE the first push. Everything it reports is
# something that would be world-readable after the push and cannot be un-published
# once cloned/forks exist.
#
# Usage:  ./preflight-public-repo-audit.sh [ref]
#         ref defaults to origin/main (falls back to HEAD if no remote yet).
#
# Exit code is 1 if anything actionable is found, so it can gate a push.
set -uo pipefail

REF="${1:-origin/main}"
git rev-parse --verify -q "$REF" >/dev/null || REF="HEAD"

FOUND=0
report() { printf '  %s\n' "$*"; FOUND=1; }

echo "== auditing $REF =="
echo
echo "-- tracked file count --"
git ls-tree -r --name-only "$REF" | wc -l

echo
echo "-- internal infrastructure (hostnames, tailnets, private IPs) --"
HITS=$(git grep -I -n -iE "tailscale|tailnet|myhostname|workstation|10\.[0-9]+\.[0-9]+\.[0-9]+|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\." "$REF" -- \
        ':(exclude)package-lock.json' ':(exclude)yarn.lock' 2>/dev/null | head -20)
if [ -n "$HITS" ]; then echo "$HITS"; report "internal infra references found above"; else echo "  (clean)"; fi

echo
echo "-- credentials, key paths, secret-shaped literals --"
HITS=$(git grep -I -n -E "id_ed25519|\.ssh/|deploy_key|private key|BEGIN [A-Z ]*PRIVATE KEY|passwd|password *= *[\"'][^\"']" "$REF" -- 2>/dev/null | head -20)
if [ -n "$HITS" ]; then echo "$HITS"; report "credential-shaped content found above"; else echo "  (clean)"; fi

echo
echo "-- provider API keys (must NEVER appear) --"
HITS=$(git grep -I -n -E "sk-ant-|sk-proj-|sk-or-v1-|AIza[0-9A-Za-z_-]{30,}" "$REF" -- 2>/dev/null | head -10)
if [ -n "$HITS" ]; then echo "$HITS"; report "PROVIDER API KEY present — do not push"; else echo "  (clean)"; fi

echo
echo "-- every JWT-shaped literal, with its decoded role --"
# The prefix tells you nothing: an anon key is public by design, a service_role
# key bypasses RLS entirely. Only the decoded claim distinguishes them.
git grep -h -o -E 'eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}' "$REF" -- 2>/dev/null | sort -u | while read -r t; do
  p=$(printf '%s' "$t" | cut -d. -f2)
  pad=$(( (4 - ${#p} % 4) % 4 ))
  decoded=$(printf '%s' "$p$(printf '=%.0s' $(seq 1 "$pad"))" | base64 -d 2>/dev/null)
  role=$(printf '%s' "$decoded" | python3 -c "import sys,json;print(json.load(sys.stdin).get('role','?'))" 2>/dev/null || echo "unparseable")
  case "$role" in
    anon)         echo "  role=anon         (public by design, RLS-constrained — safe)" ;;
    service_role) echo "  role=service_role *** BYPASSES RLS — DO NOT PUSH ***"; FOUND=1 ;;
    *)            echo "  role=$role         (inspect this one)" ;;
  esac
done

echo
echo "-- env files: inspect each one by hand --"
git ls-tree -r --name-only "$REF" | grep -E '^\.env' | while read -r f; do
  echo "  $f"
  git show "$REF:$f" 2>/dev/null | grep -vE '^\s*#|^\s*$' | sed 's/=.\{12,\}/=<redacted>/'
done

echo
echo "-- gitignored directories that must NOT be on the remote --"
for d in .hermes .claude plans; do
  n=$(git ls-tree -r --name-only "$REF" | grep -c "^$d/" || true)
  if [ "$n" -gt 0 ]; then report "$d/ has $n tracked file(s) on $REF"; else echo "  $d/ -> 0 (good)"; fi
done

echo
if [ "$FOUND" -eq 0 ]; then
  echo "AUDIT PASSED — nothing actionable found."
else
  echo "AUDIT FOUND ISSUES — review the lines marked above before pushing."
fi
exit "$FOUND"
