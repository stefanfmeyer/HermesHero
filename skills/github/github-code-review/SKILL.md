---
name: github-code-review
description: "Review a contributor's PR and deliver an evidence-backed accept/reject: fetch it without gh auth, verify merge integrity, run main-vs-PR baselines, reproduce CI exactly, audit test deltas."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [code-review, pull-requests, verification, CI, GitHub, e2e]
    related_skills: [github-pr-workflow, github-auth, requesting-code-review, systematic-debugging]
---

# Reviewing Someone Else's PR

Reviewing a contributor's PR is a verification task, not a reading task. The
deliverable is a verdict (accept / reject) backed by **output you reproduced
yourself**, with each blocking claim pinned to a file:line and a real command
result.

**Core principle:** the author's own test suite passing is NOT independent
verification. A PR can ship green-by-its-own-definition tests while regressing
suites that pass on `main` today. Always compare against the baseline.

**Relation to siblings:** `requesting-code-review` verifies YOUR changes before
commit. This skill reviews OTHER people's PRs. Do not duplicate that pipeline here.

## When to Use

- "Review X's PR", "test it e2e and accept or reject"
- A contributor opened a PR you did not author
- Any "is this safe to merge" question on a branch you don't own

## Step 0: Get the PR without `gh` auth

`gh` is often not logged in, and the REST API returns **404 (not 403)** for
private/org repos without a token. `git` over SSH still works. Pull the refs:

```bash
git fetch origin 'refs/pull/<N>/head:pr-<N>' 'refs/pull/<N>/merge:pr-<N>-merge'
git log --oneline main..pr-<N>            # the real commit list
git diff --stat main...pr-<N>             # THREE dots = changes since merge-base
git merge-base main pr-<N>
```

Use `main...pr-N` (three dots), not `main..pr-N`: three dots diffs against the
merge base, so main's own progress doesn't show as the PR "removing" things.

## Step 1: Recover intent when the PR body is unreachable

With no API token you lose the PR description. Recover intent from:

```bash
git log -1 --format='%an <%ae>%n%ad%n%n%B' <head-sha>   # author + message
git diff main...pr-<N> -- README.md | head -200          # docs state the design
```

Do not claim "the PR intends X" without one of these. If intent is genuinely
ambiguous, say so rather than inventing a rationale.

## Step 2: Verify merge integrity FIRST

Contributors who merge `main` in can silently revert recent work. Prove it in one
command per landmark commit:

```bash
for c in <recent-sha-1> <recent-sha-2>; do
  git merge-base --is-ancestor $c pr-<N> && echo "OK $c present" || echo "MISSING $c"
done
```

Also spot-check that the *content* of those commits survived (a merge can carry
the commit while a later edit on the branch undoes it):

```bash
git show pr-<N>:path/to/file | grep -c '<the-thing-that-was-removed>'   # expect 0
```

## Step 3: Isolate verification in worktrees

Never verify in the user's working repo. Worktrees keep it pristine and let you
run main and the PR side by side:

```bash
git worktree add --detach /tmp/prcheck pr-<N>          # pristine: nothing preinstalled
git worktree add --detach /tmp/maincheck main
```

For lockfile/CI questions you MUST use a pristine checkout. Running
`npm install` in a checkout first **rewrites the lockfile** and hides a real
`npm ci` failure. Install deps only after you have tested `npm ci` as-is.

Clean up at the end (`git worktree remove --force <path>`) and confirm the user's
repo is untouched (`git status --short`, `git log --oneline -1`).

## Step 4: Test-delta audit: feature deleted vs coverage deleted

Count and compare assertions by name. A PR that removes checks is not neutral:

```bash
echo -n "main: "; git show main:<suite>   | grep -c 'check('
echo -n "pr:   "; git show pr-<N>:<suite> | grep -c 'check('

# which named checks exist on main but not in the PR
diff <(git show main:<suite>   | grep -o 'check("[^"]*"' | sort) \
     <(git show pr-<N>:<suite> | grep -o 'check("[^"]*"' | sort)
```

Then determine whether the **feature** went with the coverage:

```bash
git grep -c -i '<feature keyword>' main -- src/ server/
git grep -c -i '<feature keyword>' pr-<N> -- src/ server/
```

Coverage deleted but feature still present = a coverage regression (report it as
such). Both gone = a feature regression. Be precise about which; they carry very
different weight in a verdict.

## Step 5: Baseline comparison, main vs PR (the core move)

This converts "a suite fails" into "**this PR regressed** a suite", which is the
reviewable claim. Run the SAME suites, SAME commands, against a server started
from each tree:

```bash
# start the app from each worktree on separate ports
cd /tmp/maincheck && DATA_DIR=/tmp/ledger-main PORT=3398 node server/index.js   # background
cd /tmp/prcheck   && DATA_DIR=/tmp/ledger-pr   PORT=3399 node server/index.js   # background

for w in maincheck prcheck; do
  port=$([ $w = maincheck ] && echo 3398 || echo 3399)
  echo "=== $w ==="
  cd /tmp/$w && BASE=http://localhost:$port <suite-runner> 2>&1 | tail -5
done
```

Report as a table: suite | main | PR. A suite that passes on main and fails on the
PR is a hard blocker. A suite that fails on both is pre-existing (do not blame the PR).

Start servers as background processes, not with shell `&` (foreground `&` is
rejected and long-lived servers need tracked lifecycle).

## Step 6: Reproduce CI's exact invocation, then ask if CI can go green

Read the workflow's `env:` block and run the command with **exactly those vars**,
not a superset:

```bash
# what does CI actually pass to this step?
grep -n -A6 'name: <the step>' .github/workflows/*.yml
```

Then check the PR's new code doesn't demand something CI never supplies:

```bash
grep -c '<NEW_REQUIRED_VAR>' .github/workflows/*.yml      # 0 = ungreen-able
grep -cE 'docker|compose|postgres|<new-service>:' .github/workflows/*.yml
```

A hard throw on a missing env var, with no CI step that sets it, means the
pipeline fails by construction. Also check:

- **Does `deploy` have `needs: <verify job>`?** If yes, a red verify blocks deploy,
  so an ungreen-able verify is a delivery blocker, not a test-quality nit.
- **JSON duplicate keys.** `json.loads` (and npm) silently keep the LAST value.
  `grep -n '<key>' package.json` showing two lines is a real bug:
  ```bash
  python3 -c "import re;print(re.findall(r'\"(playwright)\":\s*\"([^\"]+)\"',open('package.json').read()))"
  ```
- **Lockfile drift** shows as: `npm ci` -> `lock file's X does not satisfy X`.
  Confirm the PR introduced it by running `npm ci` on the main worktree too.
- **A new dependency may be genuinely installable.** Check the registry before
  blaming it: `curl -s https://pypi.org/pypi/<pkg>/json` and confirm the pinned
  version exists.

## Step 7: Review the diff itself

Added-line secret scan (filter out placeholders and `${{ }}` refs):

```bash
git diff main...pr-<N> | grep '^+' | grep -v '^+++' | grep -iE \
  'api[_-]?key|secret|token|password|BEGIN [A-Z ]*PRIVATE KEY|bearer |sk-' \
  | grep -viE 'example|placeholder|your-|_TOKEN\)|\$\{' | head -40
```

For anything touching auth, money, or a proxy, read the actual hunks. Look for
whether the PR **strengthens or weakens** validation: a PR that moves a
decision from client-supplied payload to a server-side re-read is an improvement;
one that removes a check is not. Say which, explicitly.

## Step 8: Runtime and provisioning risks

- **Precondition vs provisioning mismatch.** A deploy gate requiring a file the
  same script excludes is unsatisfiable. Check the remote host read-only:
  ```bash
  ssh <deploy-target> 'ls -la ~/<appdir>; ls <appdir>/<required-path> 2>/dev/null || echo MISSING'
  ```
- **New mutable links on printed/irreversible artifacts.** If the PR embeds a
  rotatable token (access code, signed entry link) into signage or anything
  already printed, flag it as a design risk, not a blocker.

## Step 9: Deliver the verdict

the user's expected shape:

1. **Verdict in the first line.** `REJECT for now` / `ACCEPT`, then the PR and head sha.
2. **"What I actually ran"** - state plainly what was executed vs inferred, and
   say so when real e2e is impossible (missing credentials, live third-party).
   Never imply you ran something you didn't.
3. **Blockers**, each with exact `file:line`, the reproduced command, and its output.
4. **A main-vs-PR table** for suite results.
5. **"What's genuinely good"** - credit real improvements. A review that is only
   negative reads as adversarial and gets discounted.
6. **"To accept"** - a concrete, ordered fix list with effort estimate.
7. **Offer the next action** (send review comments, or fix it on the branch).
8. **State the repo was left clean and untouched**, and note any stray refs
   (e.g. the local `pr-N` branch) you created.

Style: no em dashes. Do not enumerate options in prose; end with a short offer.

## Pitfalls

- **Trusting the PR's own tests.** The most common miss. Run the baseline.
- **Running `npm install` before `npm ci`.** Rewrites the lockfile and evaporates
  the finding. Test `npm ci` on a pristine worktree first.
- **Reading "the suite is red" as pre-existing.** Prove it on main in the same session.
- **Concluding "no description" from a 404.** That is a missing token, not a missing PR.
- **Verifying only the suites the PR touched.** A refactor breaks suites by
  deleting what they depend on (e.g. a `?speed=4` test hook removed from the
  engine). Run ALL suites on both trees.
- **Blaming a new dependency as uninstallable.** Check the registry/version first.
- **Leaving the user's repo dirty** or forgetting to remove worktrees.
- **Skipping PDF/binary-dependent suites as "can't run".** Install the tooling
  (below) and run them; they are often where regressions hide.

## Setup notes for browser/PDF e2e suites

These walks need real tooling. Install it rather than skipping the suite:

```bash
# PDF tooling used by print walks (reads produced PDFs + rasterises pages)
sudo apt-get install -y poppler-utils          # pdftoppm, pdftotext
python3 -m venv .venv && .venv/bin/python -m pip install --quiet pypdf

# Browser: CI installs it, or point at an existing Playwright cache via CHROME_PATH
npx playwright install --with-deps chromium
export CHROME_PATH=~/.cache/ms-playwright/chromium-<rev>/chrome-linux/chrome
```

## Reference

- `references/pr-review-verification-playbook.md` - runnable command recipes plus a
  fully worked example (a 99-file backend PR rejected on four independently
  reproduced blockers, with exact output).
