#!/usr/bin/env bash
# ci-greens-check.sh — can this PR's CI ever go green?
#
# Catches two failure classes that both present as "CI is red but the code looks fine":
#
#   1. A suite now REQUIRES an env var that no workflow step sets. The suite
#      hard-throws before doing any work, and CI fails by construction.
#   2. package.json has a DUPLICATE JSON key. json.loads (and npm) keep only the
#      LAST occurrence, so the resolved version silently differs from what the
#      regenerated lockfile pins -> `npm ci` dies with "lock file's X does not
#      satisfy X".
#
# Usage:
#   ./ci-greens-check.sh <workflow.yml> <suite-file> [suite-file...]
#
# Example:
#   ./ci-greens-check.sh .github/workflows/deploy.yml verify.cjs verify-booth.cjs
#
# Exit: 0 = no findings, 1 = findings (each printed as FINDING).

set -uo pipefail

WORKFLOW="${1:-}"
if [ -z "$WORKFLOW" ] || [ ! -f "$WORKFLOW" ]; then
  echo "usage: $0 <workflow.yml> <suite-file> [suite-file...]" >&2
  exit 2
fi
shift

findings=0
note() { echo "  $*"; }
FINDING() { echo "FINDING: $*"; findings=$((findings + 1)); }

echo "=== workflow: $WORKFLOW ==="
if command -v actionlint >/dev/null 2>&1; then
  actionlint "$WORKFLOW" >/dev/null 2>&1 && echo "actionlint: clean" || echo "actionlint: reports problems"
else
  echo "actionlint: not installed (skipped)"
fi

# ---------------------------------------------------------------------------
# 1. env vars a suite reads vs env vars the workflow sets
# ---------------------------------------------------------------------------
if [ "$#" -gt 0 ]; then
  # every process.env.X / os.environ[...] the suites reference
  REQUIRED=$(grep -hoE 'process\.env\.[A-Z_][A-Z0-9_]*|os\.environ(\.get)?\(?\[?["'"'"']([A-Z_][A-Z0-9_]*)' "$@" 2>/dev/null \
    | grep -oE '[A-Z_][A-Z0-9_]*' \
    | grep -vE '^(NODE_ENV|PATH|HOME|CI|TZ|LANG|PWD|USER|SHELL)$' \
    | sort -u)

  if [ -z "$REQUIRED" ]; then
    echo "env-check: suites reference no env vars"
  else
    echo "env-check: suites reference: $(echo "$REQUIRED" | tr '\n' ' ')"
    while read -r var; do
      [ -z "$var" ] && continue
      # does any step set it (env: block, exports, or an inline VAR= cmd)?
      if ! grep -qE "(^|[[:space:]]|[-{])${var}(:|: |=[[:space:]]|$)|export[[:space:]]+${var}" "$WORKFLOW"; then
        FINDING "suite requires \$$var but $WORKFLOW never sets it -> this step cannot pass (hard throw or silent default)"
      fi
    done <<< "$REQUIRED"
  fi
fi

# ---------------------------------------------------------------------------
# 2. duplicate JSON keys in package.json (if present)
# ---------------------------------------------------------------------------
if [ -f package.json ]; then
  echo "=== package.json ==="
  python3 - <<'PY'
import json, re, sys
raw = open("package.json").read()
dupes = 0
for block in ("dependencies", "devDependencies", "peerDependencies"):
    m = re.search(r'"%s"\s*:\s*\{(.*?)\n\s*\}' % block, raw, re.S)
    if not m:
        continue
    keys = re.findall(r'"([^"]+)"\s*:', m.group(1))
    seen = {}
    for k in keys:
        seen[k] = seen.get(k, 0) + 1
    for k, n in seen.items():
        if n > 1:
            vals = re.findall(r'"%s"\s*:\s*"([^"]+)"' % re.escape(k), m.group(1))
            print(f"FINDING: duplicate key '{k}' in {block}: {vals} -> json keeps the LAST ({vals[-1]})")
            dupes += 1
try:
    json.loads(raw)
    print("package.json: parses (duplicate keys are still silently collapsed)")
except Exception as e:
    print(f"FINDING: package.json does not parse: {e}")
    dupes += 1
sys.exit(1 if dupes else 0)
PY
  [ $? -ne 0 ] && findings=$((findings + 1))

  # lockfile drift, tested AS-IS (never after an `npm install`)
  if [ -f package-lock.json ]; then
    echo "=== npm ci (as-is; do NOT run npm install first) ==="
    if npm ci --no-audit --no-fund >/tmp/ci-greens-npmci.log 2>&1; then
      echo "npm ci: OK"
    else
      FINDING "npm ci fails -> CI's dependency step is red"
      grep -E 'Invalid|EUSAGE|not in sync' /tmp/ci-greens-npmci.log | sort -u | head -5 | while read -r l; do note "$l"; done
    fi
  fi
else
  echo "package.json: not present (skipped)"
fi

echo
if [ "$findings" -eq 0 ]; then
  echo "RESULT: no blocking findings"
else
  echo "RESULT: $findings blocking finding(s)"
fi
exit $([ "$findings" -eq 0 ] && echo 0 || echo 1)
