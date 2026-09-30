#!/usr/bin/env bash
# Reproduce the CI "Build and verify" job locally against the CURRENT WORKING TREE.
# Nothing is committed or pushed — this only exercises the tree in place.
#
# Mirrors the verify job in .github/workflows/deploy.yml of a public repo.
# Use before reporting any change to that repo, especially a styling change to
# backend/static (the walks are what prove the restyle didn't break behaviour).
#
# Two guards exist because a green suite against a stale server is a FALSE PASS:
#   · a port preflight that hard-exits (a leftover server makes `nohup` die with
#     EADDRINUSE into a log, and the walks then verify the OLD process)
#   · a version assertion read back from /api/health (proves the process we
#     started is the one answering — an unmatched tag means someone else's server)
#
# Usage:  bash reproduce-ci-verify.sh [/path/to/repo]

set -uo pipefail

REPO="${1:-$HOME/Developer/my-repo}"
cd "$REPO" || { echo "repo not found: $REPO"; exit 1; }

RUN_TAG="local-$$"   # unique per run; asserted against /api/health below

echo "### 0. preflight: ports must be free (else we would test a stale server)"
for port in 3399 8091; do
  if ss -ltn 2>/dev/null | grep -q ":$port "; then
    echo "  FATAL: port $port already in use — refusing to run. Kill it first."
    exit 1
  fi
done
echo "  3399 and 8091 free"

mkdir -p /tmp/ci-ledger && rm -rf /tmp/ci-ledger/* 2>/dev/null

echo "### 1. npm run build"
npm run build >/tmp/ci-build.log 2>&1 && echo "build OK" \
  || { echo "BUILD FAILED"; tail -20 /tmp/ci-build.log; exit 1; }

echo
echo "### 2. stub backend :8091"
STUB_BACKEND_PORT=8091 STUB_ACCESS_CODE=ci-entry-code \
  nohup node scripts/stub-backend.cjs >/tmp/ci-backend.log 2>&1 &
STUB_PID=$!
for _ in $(seq 1 30); do curl -sf -o /dev/null http://127.0.0.1:8091/healthz && break; sleep 1; done
curl -sf http://127.0.0.1:8091/healthz && echo "stub backend healthy" \
  || { cat /tmp/ci-backend.log; exit 1; }

echo
echo "### 3. app :3399"
DATA_DIR=/tmp/ci-ledger CODES_TOKEN=ci-only-token BOOTH_ACCESS_CODE=ci-entry-code PORT=3399 \
  APP_VERSION="$RUN_TAG" CTV_DEMO_BACKEND_URL=http://127.0.0.1:8091 \
  nohup node server/index.js >/tmp/ci-server.log 2>&1 &
APP_PID=$!
for _ in $(seq 1 30); do curl -sf -o /dev/null http://127.0.0.1:3399/api/health && break; sleep 1; done

# The version we tagged must be the version answering. Anything else means the
# walks are about to test a process we did not start.
HEALTH=$(curl -sf http://127.0.0.1:3399/api/health) \
  || { echo "app did not come up:"; cat /tmp/ci-server.log; exit 1; }
echo "$HEALTH"
case "$HEALTH" in
  *"$RUN_TAG"*) echo "  version matched ($RUN_TAG) — this is our process" ;;
  *) echo "  FATAL: /api/health did not report $RUN_TAG — stale server on :3399"; exit 1 ;;
esac

echo
echo "### 4. npm test"
npm test 2>&1 | tail -18

echo
echo "### 5. flow walk"
BASE=http://localhost:3399 STAFF_TOKEN=ci-only-token BOOTH_ACCESS_CODE=ci-entry-code \
  node verify.cjs 2>&1 | tail -6

echo
echo "### 6. print walk"
BASE=http://localhost:3399 BOOTH_ACCESS_CODE=ci-entry-code \
  node verify-print.cjs 2>&1 | tail -6

echo
echo "### 7. ticket print walk"
BASE=http://localhost:3399 BOOTH_ACCESS_CODE=ci-entry-code \
  node verify-ticket-print.cjs 2>&1 | tail -6

echo
echo "### 8. booth walk"
BASE=http://localhost:3399 STAFF_TOKEN=ci-only-token BOOTH_ACCESS_CODE=ci-entry-code \
  node verify-booth.cjs 2>&1 | tail -6

echo
echo "### 9. visitor backend unit suite"
node backend/tests/watch.test.mjs 2>&1 | grep -E 'OK|ERR|Error' | tail -12

echo
echo "### 10. scope assertion — did the change stay inside its intended subtree?"
git diff --stat
git diff --quiet src/ server/ scripts/ \
  && echo "src/ server/ scripts/ UNCHANGED" \
  || echo ">>> those dirs CHANGED — confirm that was intended"

echo
echo "### 11. nothing committed (this repo auto-deploys on push to main)"
git status --porcelain --untracked-files=all
git log --oneline -1
git status -sb | head -1

echo
echo "### teardown (PID capture, not pattern matching)"
kill "$APP_PID" 2>/dev/null
[ -n "${STUB_PID:-}" ] && kill "$STUB_PID" 2>/dev/null
sleep 1
echo "done"
echo
echo "NOTE: teardown lives in this script on purpose. Run inline in a shell,"
echo "      'pkill -f \"node server/index.js\"' ALSO matches the shell's own command"
echo "      line and kills your session (exit -15, no output)."
