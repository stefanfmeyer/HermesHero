---
name: subagent-large-project-pattern
description: "Delegating large multi-step tasks to large-context subagents (GLM family, 2026-07) reliably hits the 600s timeout when input context exceeds 500k tokens, even though files are 80-100% written to disk. Recovery: read the subagent's tool trace, list what's on disk, syntax-check everything (duplicate exports, pino API misuse are common GLM-5.2 bugs), write the missing 1-2 files yourself, then run a real end-to-end smoke before committing. Never trust the subagent's 'all done' self-report."
version: 1.0.0
tags: [subagent, delegation, timeout, recovery, monorepo, npm]
---

# Subagent Large Project Pattern

## The Problem

When delegating large implementation tasks (e.g., bootstrapping a full Next.js + Fastify monorepo) to subagents, the subagent **times out at the per-task ceiling** (300s in older versions, 600s in current) even though files were successfully written to disk. The slow step is almost always **dependency installation or final verification** (npm install, `python -m venv && pip install`, end-of-batch self-checks), but all source files exist.

**Three distinct interruption scenarios:**

1. **Monorepo bootstrap** — subagent writes 50+ files, then `npm install` / `pnpm install` blocks for minutes and the timeout fires. Files on disk are correct; just no install happened.
2. **Large single-package or multi-agent batch** — subagent writes 10-20 files, runs a final smoke test or verification loop, hangs on a slow tool call (HTTP fetch to a non-existent service, infinite loop in test code, etc.) and the timeout fires. Files on disk are 80-100% correct; one or two are missing or have subtle bugs.
3. **Interrupted (exit_reason: "interrupted")** — the subagent was cut off mid-response (e.g. parent turn ended, user sent a new message). The tool trace shows successful patches/writes right up to the interruption point. **The recovery is identical to timeout**: check disk, verify syntax, cross-reference against the task spec, gap-fill the unfixed items. Do NOT assume "interrupted" means "nothing was done" — in observed cases 12/12 patches were successfully applied before the interruption, and only the final summary + 1 unfixed bug remained.

**Large-context subagent note (observed on GLM-5.2, 2026-07 — historical model; delegation today inherits `delegation.model` = `glm-5.3-flash:cloud`):** With large context (>1M input tokens) the subagent reliably hits the 600s ceiling on any task producing 15+ files. Plan for it: expect to recover at least one subagent per batch. Interruptions (scenario 3) can happen at any context size.

## Recovery Pattern (After Timeout)

```bash
# 1. Check what was committed
cd /path/to/repo && git log --oneline

# 2. See what files exist
find /path/to/repo/apps -type f | sort

# 3. Identify the gap and write missing files directly
```

The subagent's self-report says "timed out, no work done". **That is almost always a lie.** Files are usually 80-100% there. Verify before redoing.

## Step 0: Read the subagent's actual tool trace

In `delegate_task` results, the `tool_trace` array shows every tool the subagent called. Look at the **last successful write** to figure out where it stopped. The hung tool is usually the last `terminal` call (npm install, a test runner, or a manual `node --check` loop on a broken file).

## Step 1: Identify what's actually on disk

Don't trust the subagent's "files written" count. List the target dir and compare to the spec:

```bash
cd /path/to/repo
ls packages/<pkg>/ 2>/dev/null  # or where the files should be
find packages/<pkg> -type f | sort
```

## Step 2: Syntax-check everything

Subagents frequently produce JS/Python files that **fail `node --check` or `ast.parse`** even when they self-report "all OK". This is the single most common bug class. Run a sweep:

```bash
# JS / JSX
err=0
for f in $(find packages/<pkg> -name "*.js" -o -name "*.jsx"); do
  node --check "$f" 2>/dev/null || { echo "FAIL: $f"; err=$((err+1)); }
done
# JSX needs babel (node --check won't parse it)
node -e "
  const p = require('@babel/parser');
  const fs = require('fs');
  const files = process.argv.slice(1);
  for (const f of files) {
    try { p.parse(fs.readFileSync(f,'utf-8'), { sourceType:'module', plugins:['jsx'] }); }
    catch(e) { console.log('FAIL ' + f + ': ' + e.message); process.exit(1); }
  }
" $(find packages/<pkg> -name "*.jsx")

# Python
python3 -c "
import ast, os
for root, _, files in os.walk('packages/<pkg>'):
    for f in files:
        if f.endswith('.py'):
            try: ast.parse(open(os.path.join(root,f)).read())
            except SyntaxError as e: print(f'FAIL {os.path.join(root,f)}: {e}')
"
```

Fix the syntax errors yourself with `patch`. Common GLM-5.2 patterns:
- **Duplicate `export function X` + `export { X }` in the same module** — script-fixable with a regex (see `references/glm-5.2-bug-patterns.md`)
- **`node --check` says "Duplicate export"** → same root cause
- **Pino `this.logger.log({level:...})`** → pino doesn't honor `level` field; switch to `this.logger[level](obj)`

## Step 3: Run a real smoke test, not just unit tests

Subagent self-tests often pass but the public API doesn't actually work. The cheapest catch:

```bash
node -e "
import('./<main-export>.js').then(async (m) => {
  // construct with mock data, call the headline method, assert shape
  const r = await m.someHeadlineMethod({ /* mock */ });
  console.log('OK', JSON.stringify(r).slice(0, 200));
}).catch(e => { console.error('FAIL:', e.message); process.exit(1); });
"
```

If the smoke test fails with a `TypeError: this.foo is not a function`, the subagent wrote a function but forgot to expose it — fix the export, don't rewrite the file.

## Step 4: Write the missing files yourself

If 1-2 files are missing, write them directly with `write_file` (NOT `execute_code` — `execute_code` is blocked in cron mode). If 3+ files are missing, spawn a focused subagent for the gap only, not a redo of the whole task.

## Step 5: Run the full end-to-end smoke before committing

The subagent's "all done" report is a self-grade — frequently too generous. Run your own end-to-end check:
- API server: start it, hit `/health`, hit each route with a real request, assert response shape
- Python service: import the module, instantiate the main class, call the public methods
- React app: `npm install && npm run build` (production build catches more than dev)

Only after your independent smoke passes is the work safe to commit.

## Git Push via HTTPS (When SSH Keys Missing)

If machine has no SSH key and git push fails with publickey:

```bash
TOKEN=$(gh auth token)
git remote set-url origin https://github.com/username/repo.git
git push origin main
```

Check SSH keys first:
```bash
ssh-add -l 2>&1 | head -3 || echo "No identities"
ls ~/.ssh/*.pub 2>/dev/null
```

## .env Files Gitignore Check

When subagents create .env files, verify gitignore BEFORE committing:
```bash
git ls-files --error-unmatch apps/api/.env 2>&1 || echo "Not tracked"
```

## Commits: Skip `Co-Authored-By` Trailer

If the user asks for commits **without** a `Co-Authored-By: Claude` trailer (some users prefer not to advertise AI authorship in git history), use a file-based commit message and pass it via `-F`:

```bash
cat > /tmp/commit-msg.txt <<'EOF'
feat: my feature

Long descriptive body...

No Co-Authored-By trailer.
EOF
git commit -F /tmp/commit-msg.txt
# To amend:
git commit --amend -F /tmp/commit-msg.txt
git push --force-with-lease origin main
```

The `--force-with-lease` is safer than `--force` — it refuses to overwrite if remote moved.

## Key Insight

Subagents write to the **same filesystem** as the parent. Files created by subagents are immediately visible to the main session. Strategy:
1. Subagent writes all source code files (interrupted by timeout, 80-100% complete)
2. Parent verifies on disk, fixes bugs, runs real smoke test
3. Parent installs deps, commits, pushes

**Do not trust the subagent's "all done" report.** The work it self-reports as 100% complete is typically 85-95% complete and has 1-3 subtle bugs that the parent's verification catches.

## Silent Patch Failure (No Timeout Required)

The subagent can complete well within the timeout (e.g. 367s of 600s) and self-report "all done, tests pass" — but **patches to existing files silently failed** while `write_file` calls for new files succeeded. Observed pattern (2026-07-07, GLM-5.2:cloud, 30 tool calls):

- **6 new files** created via `write_file` → all correct, all on disk
- **5 patches** to existing files via `patch` → **all 5 produced zero diff** (no error, no warning in tool output)
- Subagent self-reported: "All 16 tests pass, all modules import cleanly" — **true for the new files**, but the existing files were untouched
- The parent had to apply all 5 patches manually

**Why this happens:** The subagent's `patch` tool calls return `success` even when the `old_string` doesn't match (or matches whitespace-only), producing an empty diff. The subagent doesn't detect the no-op because the tool didn't error. `write_file` always succeeds (it overwrites), so new files are reliable.

**Recovery:**
```bash
# After subagent completes, check EVERY modified file for actual changes
git diff --stat
git diff --name-only
# If a file shows 0 changes but the subagent claimed to modify it, apply the patch yourself
```

**Prevention:** When delegating, instruct the subagent to use `write_file` for new files and `patch` for existing files, then verify each patch took:
```bash
git diff --name-only  # files that actually changed
```

This is distinct from the timeout pattern — the subagent finished, reported success, and was wrong. **Always run `git diff --stat` after a subagent completes, regardless of its self-report.**

**Second confirmation (2026-07-07, GLM-5.2:cloud, 367s of 600s — no timeout):** Subagent was delegated Tasks 2-9 from a plan. It self-reported "All 16 tests pass, all modules import cleanly." Reality:
- **6 new files** via `write_file` → all correct, all on disk, all passing tests
- **5 patches** to existing files (parser_service.py, handler.js, worker.js, README.md, CLAUDE.md) → **all 5 produced zero diff**. The subagent's tool trace showed `patch` calls returning `success` with empty diffs
- Parent had to apply all 5 patches manually using the `patch` tool
- The subagent's test run was real (16/16 passed) — but only because the new files were self-contained and didn't depend on the existing-file patches

**Key lesson:** `write_file` is reliable for new files. `patch` inside subagents is NOT reliable for existing files — even when the tool returns success. **Always verify with `git diff --stat` after a subagent completes.** If patches are missing, apply them yourself in the parent session.

## When to Use

- Project has 50+ files across multiple packages
- npm install would take more than 5 minutes
- Building monorepos with Next.js + Fastify + shared packages
- User wants a "build this entire project" task
- Any batch of 3+ parallel subagents producing 30+ files total (expect at least one timeout)

## When NOT to Use

- Task is fewer than 10 files or simple (just use direct writes)
- User wants subagent-only work
- Network or file issues are likely

## See Also

- `references/glm-5.2-bug-patterns.md` — the recurring GLM-5.2 code generation bugs and the fix scripts
- `references/parallel-subagent-batch-recipe.md` — proven 3-subagent parallel batch layout for multi-package projects (greenfield bootstrap)
- `references/static-analysis-batch-recipe.md` — proven 3-subagent parallel batch for pre-implementation reconnaissance (static code review + test plan + build-env audit). Use this BEFORE fixing a mature codebase, not for greenfield. Captured from the the company Botpress integration hardening (2026-07-01).
- `references/audit-driven-tdd-recipe.md` — the RED-tests-as-audit-confirmation pattern: write the test suite from the audit FIRST, confirm tests fail against the buggy code, THEN apply fixes. Captured from the second round of the the company hardening (2026-07-01, +42 tests added after the bug list was extended).
- `references/audit-driven-fix-batch-recipe.md` — dispatching parallel fix subagents from a prioritized audit bug list, then gap-filling unfixed items in the parent. Distinct from TDD: fixes are applied directly, not via test-first. Captured from the a monorepo hardening (2026-07-06, 10 bugs across 8 files, 3 parallel subagents).
- `../botpress-integration-vitest-template/SKILL.md` — the drop-in vitest test harness for any Botpress Cloud integration (helpers, mock Response, action templates, and the `.botpress` import workaround).
