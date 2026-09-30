---
name: contributor-pr-review
description: "Review a contributor's PR and deliver an evidence-backed accept/reject: fetch it without gh auth, verify merge integrity, run main-vs-PR baseline suites, reproduce CI's exact invocation, audit test deltas."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [code-review, pull-requests, verification, CI, GitHub, e2e, baseline]
    related_skills: [github-pr-workflow, github-auth, requesting-code-review, systematic-debugging]
---

# Reviewing a Contributor's PR

Reviewing someone else's PR is a verification task, not a reading task. The
deliverable is a verdict (accept / reject) backed by **output you reproduced
yourself**, with each blocking claim pinned to a file:line and a real command
result.

**Core principle:** the author's own test suite passing is NOT independent
verification. A PR can ship green-by-its-own-definition tests while regressing
suites that pass on `main` today. Always compare against the baseline.

**Relation to siblings:** `requesting-code-review` verifies YOUR changes before
commit. This skill reviews OTHER people's PRs and is the one to load for
"review X's PR / test it e2e / accept or reject".

## When to Use

- "Review X's PR", "test it e2e and accept or reject"
- A contributor opened a PR you did not author
- Any "is this safe to merge" question on a branch you do not own

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
merge base, so main's own progress does not show as the PR "removing" things.

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
`npm ci` failure. Test `npm ci` as-is before installing anything.

Clean up at the end (`git worktree remove --force <path>`) and confirm the user's
repo is untouched (`git status --short`, `git log --oneline -1`).

## Step 4: Test-delta audit: feature deleted vs coverage deleted

Count and compare assertions by name. A PR that removes checks is not neutral:

```bash
echo -n "main: "; git show main:<suite>   | grep -c 'check('
echo -n "pr:   "; git show pr-<N>:<suite> | grep -c 'check('

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
cd /tmp/maincheck && DATA_DIR=/tmp/ledger-main PORT=3398 node server/index.js   # background
cd /tmp/prcheck   && DATA_DIR=/tmp/ledger-pr   PORT=3399 node server/index.js   # background

for w in maincheck prcheck; do
  port=$([ $w = maincheck ] && echo 3398 || echo 3399)
  echo "=== $w ==="
  (cd /tmp/$w && BASE=http://localhost:$port <suite-runner> 2>&1 | tail -5)
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
grep -n -A6 'name: <the step>' .github/workflows/*.yml
```

Then check the PR's new code does not demand something CI never supplies:

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
whether the PR **strengthens or weakens** validation: a PR that moves a decision
from a client-supplied payload to a server-side re-read is an improvement; one
that removes a check is not. Say which, explicitly.

Also check the PR did not change what is *printed/shipped* in a way that breaks
provisioning (e.g. new required secrets, rotated tokens).

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

Expected shape:

1. **Verdict in the first line.** `REJECT for now` / `ACCEPT`, then the PR and head sha.
2. **"What I actually ran"** - state plainly what was executed vs inferred, and
   say so when real e2e is impossible (missing credentials, live third-party).
   Never imply you ran something you did not.
3. **Blockers**, each with exact `file:line`, the reproduced command, and its output.
4. **A main-vs-PR table** for suite results.
5. **"What's genuinely good"** - credit real improvements. A review that is only
   negative reads as adversarial and gets discounted.
6. **"To accept"** - a concrete, ordered fix list with effort estimate.
7. **Offer the next action** (send review comments, or fix it on the branch).
8. **State the repo was left clean and untouched**, and note any stray refs
   (e.g. the local `pr-N` branch) you created.

Style: no em dashes. Do not enumerate options in prose; end with a short offer.

## Step 10: When they merge it anyway (post-merge remediation)

A reject verdict does not stop a merge. When the user says "I merged it anyway,
make it work", the job changes from *judging* to *fixing* and the blockers you
reported are now live on `main`. Do these before touching any code.

**(a) Prove you are not about to undo the author's work.** The author's feature is
what the user actually wants, so your remediation must be additive. Enumerate both
sides and intersect them:

```bash
git diff --stat <merge-base>..<merge-commit>     # everything the author added
git diff --stat <merge-commit>..HEAD             # everything YOU changed
```

If the intersection is empty, the author's feature is structurally safe and you can
say so outright. If it is not empty, diff each shared file for **removals only** —
that list is your entire risk surface:

```bash
git diff <merge-commit>..HEAD -- <shared-file> | grep -E '^-' | grep -vE '^---'
```

**(b) Audit whether the PR deleted behaviour its own docs still describe.** A PR
that rewrites a UI routinely removes things the repo still documents. Grep the docs
for each promised feature, then check it still exists:

```bash
grep -n 'brief\|types their name\|same screen' README.md   # what the docs promise
grep -rn '<that string>' src/                              # 0 hits = doc describes a deleted screen
```

This is how you find "the README documents a composer that no longer exists".
Restoring those is remediation, not scope creep. Check the **pre-merge tree** first
to learn which copy was the user's versus the author's:

```bash
git show <merge-base>:path/to/File.jsx | grep -A5 '<the headline>'
```

If the PR replaced the user's copy with the author's, restoring the user's is
correct, and say which you kept. Do not silently overwrite the author's invention
either when it is a genuine product choice — surface it.

**(c) Make CI actually green, not merely "noted as red".** If a suite needs a live
third-party service CI cannot have, write a **contract-faithful stub double** — same
endpoints, same field names, same response shapes — and run it in CI. Say plainly
what the stub does not prove (the real third-party transaction) and where that is
verified instead. This plus the missing entry-link env var is usually enough to take
a pipeline from structurally ungreenable to green.

**(d) Never deploy a merge that makes production depend on something unprovisioned.**
If the merged build now requires a service that is not running, deploying converts a
working system into a broken one. Verify the dependency is live *before* shipping,
and be willing to stop with production untouched — then state exactly what you
verified is still serving the old build.

See `references/post-merge-audit-and-remediation.md` for the full command set and a
worked example.

## Step 11: When the contributor reports status in a ticket, verify it

A contributor's status update is a **claim**, not evidence, and it is wrong in both
directions in practice: work described as "nothing applied yet" may already be merged,
and a file described as vendored from your version may have vendored an earlier,
buggier one. Reach the linked artifacts before composing any reply.

**Find the artifacts.** PRs are often attached to a tracker issue rather than named in
the message text. On Linear, `attachments` on the **issue** holds them, and the comments
are NOT where they live:

```bash
{ issue(id:"ADG-58") {
    updatedAt                                        # cheap "did anything change" signal
    comments(first:50) { nodes {
      id createdAt user { name } body
      parent { id }                                  # non-null = a threaded reply
    } }
    attachments(first:20) { nodes { id title url } } # the PR links
} }
```
Request `parent { id }`: replies come back with it set, and a threaded reply to your own
comment otherwise looks like a duplicate of it — easy to miss, and it is usually the one
answering a question you asked.

**Then verify merge state and content, separately.** "Merged" and "applied" are
different facts, and so are "merged" and "deployed":

```bash
git fetch origin 'refs/pull/<N>/head:pr-<N>' 'refs/pull/<N>/merge:pr-<N>-merge'
git log --oneline -3 origin/main                                          # squash commit present?
git merge-base --is-ancestor pr-<N> origin/main && echo MERGED || echo OPEN
git show origin/main:<path/changed> | grep -n '<the change>'              # is the content live?
```
A squash merge hides the PR's own commits from `main`, so confirm by **commit subject and
content on main**, not by sha. An empty `git diff main pr-<N>` is the tell that it landed.

**When they vendor your file, diff it — byte-for-byte.** If a contributor says a config
was copied from a version you wrote, and that file went through revisions (a bug fixed
after your first draft), the only safe check is a real comparison:

```bash
git show pr-<N>:<vendored/path> > /tmp/theirs
diff -u <your/path> /tmp/theirs && echo IDENTICAL
wc -c <your/path> /tmp/theirs                     # size match corroborates
grep -c '<critical-line>' /tmp/theirs             # e.g. a required location block
```
Identical output plus a matching size is proof; "she said she copied it" is not.

**Audit the automation for the step a hand-run performed implicitly.** A role or script
that shells out to a CLI tool can omit flags the original manual command passed, and the
tool may still exit 0 while doing the wrong thing. Enumerate what the manual invocation
supplied, then grep the new code for each one:

```bash
grep -nE '\-\-issue|\-\-key-file|\-\-fullchain-file|\-\-reloadcmd|\-\-install-cert' <role>/tasks/*.yml
```
For anything missing, read the tool's source to establish the consequence rather than
guessing — then verify against the **live** system state the flag was supposed to produce
(e.g. `openssl s_client` for the served cert, not the tool's own store), and report it
with the traced mechanism.

## Pitfalls

- **Trusting the PR's own tests.** The most common miss. Run the baseline.
- **Undoing the author's work while "fixing" it.** Before any remediation, prove the
  intersection of your changed files and theirs. Additive-only is the goal.
- **Assuming the PR left the docs true.** Check every feature the README describes
  still exists; rewritten UIs routinely orphan documented behaviour.
- **Shipping a merge whose new dependency is not provisioned.** Taking a working
  production backwards is worse than a deploy that stops. Verify first.
- **Reading "the suite is red" as pre-existing.** Prove it on main in the same session.
- **Concluding "no description" from a 404.** That is a missing token, not a missing PR.
- **Verifying only the suites the PR touched.** A refactor breaks suites by
  deleting what they depend on (e.g. a `?speed=4` test hook removed from the
  engine). Run ALL suites on both trees.
- **Blaming a new dependency as uninstallable.** Check the registry/version first.
- **Leaving the user's repo dirty** or forgetting to remove worktrees.
- **Taking a contributor's status update at face value.** "Nothing applied yet" and
  "already merged" are both frequently wrong. Check linked PRs and the live system.
- **Believing a vendored copy matches yours.** Diff it byte-for-byte; a "copy" of an
  earlier revision silently carries the bug you already fixed.
- **Skipping PDF/binary-dependent suites as "can't run".** Install the tooling
  (below) and run them; they are often where regressions hide.

## Setup notes for browser/PDF e2e suites

These walks need real tooling. Install it rather than skipping the suite:

```bash
sudo apt-get install -y poppler-utils          # pdftoppm, pdftotext (print walks)
python3 -m venv .venv && .venv/bin/python -m pip install --quiet pypdf

npx playwright install --with-deps chromium
export CHROME_PATH=~/.cache/ms-playwright/chromium-<rev>/chrome-linux/chrome
```

## Reference

- `references/pr-review-verification-playbook.md` - runnable command recipes plus a
  fully worked example (a 99-file backend PR rejected on four independently
  reproduced blockers, with exact output).
- `scripts/ci-greens-check.sh` - deterministic probe for "can this PR's CI ever go
  green?". Finds env vars a suite requires but no workflow step sets, duplicate
  JSON keys in `package.json`, and as-is `npm ci` lockfile drift. Run it before
  hand-diagnosing a red build:
  ```bash
  bash scripts/ci-greens-check.sh .github/workflows/deploy.yml verify.cjs verify-booth.cjs
  ```
