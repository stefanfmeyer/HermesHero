# PR Review Verification Playbook

Runnable recipes plus one fully worked example. Commands assume a local clone with
`origin` on GitHub and a known PR number `N`.

---

## Recipe 1 - Fetch a PR with no API token

```bash
# gh auth status is often "not logged into any GitHub hosts"; the REST API
# returns 404 for org repos without a token. git over SSH still works.
git fetch origin 'refs/pull/<N>/head:pr-<N>'
git log --oneline main..pr-<N>
git diff --stat main...pr-<N>          # three dots -> diff vs merge-base
git merge-base main pr-<N>

# branch name behind the PR head
git ls-remote --heads origin | grep "$(git rev-parse pr-<N>)"
```

---

## Recipe 2 - Merge integrity check

```bash
for c in $(git log --format=%h -n 6 main); do
  git merge-base --is-ancestor $c pr-<N> && echo "present $c" || echo "MISSING $c"
done

# content survived, not just the commit
for f in src/index.css README.md; do
  echo "$f: main=$(git show main:$f | grep -c '<removed-marker>') pr=$(git show pr-<N>:$f | grep -c '<removed-marker>')"
done
```

---

## Recipe 3 - Test-delta audit

```bash
SUITE=verify.cjs
echo -n "main: "; git show main:$SUITE   | grep -c 'check('
echo -n "pr:   "; git show pr-<N>:$SUITE | grep -c 'check('

diff <(git show main:$SUITE   | grep -o 'check("[^"]*"' | sort) \
     <(git show pr-<N>:$SUITE | grep -o 'check("[^"]*"' | sort)

# feature present but coverage gone?
git grep -c -i '<feature>' main -- src/ server/
git grep -c -i '<feature>' pr-<N> -- src/ server/

# did a helper other suites depend on get deleted?
diff <(git show main:src/lib/wire.js | grep -oE '^(export )?(async )?function [A-Za-z_]+' | sort -u) \
     <(git show pr-<N>:src/lib/wire.js | grep -oE '^(export )?(async )?function [A-Za-z_]+' | sort -u)
```

---

## Recipe 4 - Main-vs-PR suite baseline

```bash
git worktree add --detach /tmp/prcheck   pr-<N>
git worktree add --detach /tmp/maincheck main

# test `npm ci` AS-IS first (pristine), then install
for w in /tmp/maincheck /tmp/prcheck; do (cd $w && npm ci); done

# start each app on its own port (tracked background processes, not shell `&`)
(cd /tmp/maincheck && DATA_DIR=/tmp/l-main CODES_TOKEN=t PORT=3398 node server/index.js) &
(cd /tmp/prcheck   && DATA_DIR=/tmp/l-pr   CODES_TOKEN=t PORT=3399 node server/index.js) &

for p in 3398:maincheck 3399:prcheck; do
  port=${p%%:*}; name=${p##*:}
  echo "=== $name ==="
  (cd /tmp/$name && BASE=http://localhost:$port node verify-ticket-print.cjs 2>&1 | tail -4)
done
```

Present as a table:

| Suite | main | PR |
|---|---|---|
| verify-print | PASS 46 | PASS 46 |
| verify-ticket-print | PASS 40 | FAIL (locator timeout) |

---

## Recipe 5 - Does CI's own invocation work?

```bash
# exactly what CI passes to the step
grep -n -A6 'name: Flow walkthrough' .github/workflows/*.yml

# does the PR require a var CI never sets?
grep -c 'ENTRY_URL' .github/workflows/*.yml          # 0 == cannot go green

# does CI start the service the tests now need?
grep -cE 'docker|compose|postgres|backend:' .github/workflows/*.yml

# does a red verify block deploy?
grep -n -A3 'needs:' .github/workflows/*.yml
```

Reproduce the failure with CI's env only:

```bash
BASE=http://localhost:3399 STAFF_TOKEN=ci-only-token node verify.cjs
```

---

## Recipe 6 - Dependency sanity

```bash
# duplicate JSON keys (json.loads keeps the LAST one)
grep -n '"playwright"' package.json
python3 -c "import re,json;t=open('package.json').read();print(re.findall(r'\"(playwright[a-z-]*)\":\s*\"([^\"]+)\"',t));print('wins:',json.loads(t)['devDependencies'].get('playwright'))"

# lockfile drift
npm ci --no-audit --no-fund 2>&1 | grep -E 'Invalid|EUSAGE'

# is the pinned version of a new dep real?
curl -s https://pypi.org/pypi/<pkg>/json | python3 -c "import sys,json;print('<ver>' in json.load(sys.stdin)['releases'])"
```

---

## Recipe 7 - Read-only inspection of the deploy target

```bash
ssh -i ~/.ssh/<key> -o BatchMode=yes <user>@<host> '
  cd ~/<appdir> && ls -la | head -25
  ls <appdir>/<required-path> 2>/dev/null || echo "MISSING <required-path>"
  grep -c <NEEDED_VAR> .env 2>/dev/null'
```

A deploy gate requiring a path the rsync in the same script excludes is
unsatisfiable. Confirm with gate and exclude side by side:

```bash
grep -n '<required-file>' deploy.sh    # one hit in --exclude, one in the guard
```

---

# Worked example (2026-09, a small public repo PR #1)

A 99-file PR (+7.6k/-1.3k) adding a real FastAPI `backend/` to a booth demo,
replacing a client-side simulation. Verdict: **REJECT for now**, on four
independently reproduced blockers. Recorded because each blocker type recurs.

**Context:** `gh` not authenticated; REST API 404 for the org repo; no live services
credentials, so true e2e was impossible and was stated as such.

### Blocker 1 - `npm ci` fails (JSON duplicate key)

`package.json` gained a second `playwright` key:

```
30:    "playwright": "1.60.0",     <- added by the PR
32:    "playwright": "^1.63.0",    <- pre-existing
```

JSON keeps the last, so npm resolves `^1.63.0`, while the PR's regenerated
lockfile pins `1.60.0`:

```
npm error Invalid: lock file's playwright@1.60.0 does not satisfy playwright@1.63.0
```

Same command on `main`: `added 73 packages`, exit 0. PR-introduced, deterministic,
and it is CI's first dependency step.

> Trap: running `npm install` while investigating **regenerates the lockfile** and
> makes the error disappear. Re-verify on a pristine worktree.

### Blocker 2 - the walk demands a var CI never sets

```js
// verify.cjs:32-33
const ENTRY_URL = process.env.ENTRY_URL || (ENTRY_FILE ? ... : "");
if (!ENTRY_URL) throw new Error("Set ENTRY_URL or ENTRY_FILE to the current booth entry link before verifying.");
```

CI's step sets only `BASE` and `STAFF_TOKEN`; `ENTRY_URL` appears **0 times** in
the workflow, and no step starts the backend. Reproduced: exit 1.

### Blocker 3 - two suites that pass on main now fail

Run with **no backend**, same commands, both trees:

| Suite | main | PR |
|---|---|---|
| verify-print | PASS 46 | PASS 46 |
| verify-ticket-print | PASS 40 | FAIL |
| verify-booth | PASS 27 | FAIL |
| verify.cjs | 49 checks | 44 checks, thrown pre-run |

Cause: `verify-ticket-print.cjs:136` drives `/?speed=4#/hat`, but the PR deleted
the speed engine from `wire.js` (`readSpeed`, `SPEED_KEY` gone), while the guest
screen now waits on `/api/session`, which 502s without a backend. Net e2e delta
was **-6/+4** checks.

### Blocker 4 - unsatisfiable deploy precondition

`deploy-at2.sh:109` requires `backend/.env` and `backend/settings.docker.json`
**on the host**, but line 89 of the same script rsync-`--exclude`s both. The host
had no `backend/` directory at all. Because the check runs *after* verify, the
failure would have been misdiagnosed as a secrets problem.

### Credited as genuinely good

- `POST /api/claim` moved trust from browser-supplied price/product/buy-id to a
  server-side session re-read -> strictly stronger than main.
- Merge integrity held: recent main commits verified as ancestors and their
  content confirmed present.
- Origin checks on non-GET, `redirect: "error"`, upstream timeouts.

### Reported as coverage-only regression

The refusal feature (`buildRefusalRun` deleted from `wire.js`, but the UI and
`REFUSAL_RE` still live in `GuestFlow.jsx`) built fine. Six named checks covering
it were dropped with no test-side replacement - labelled a coverage regression,
not a broken feature.

### Reported as design risk (non-blocking)

Printed signage now embeds a **rotatable** entry link, and rotating it invalidates
older links - a card printed with a stale code is a dead QR for that visitor.
Main had no such coupling.

### Review hygiene actually applied

- Worktrees for pristine/pr/main; user's repo left at its original commit, clean.
- `git status --short` + `git log --oneline -1` shown to prove it.
- Worktrees removed at the end; the stray local `pr-<N>` ref was disclosed.
- Installed poppler-utils + a pypdf venv so the print walks could actually run
  instead of being skipped.
