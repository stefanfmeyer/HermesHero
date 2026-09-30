# Audit-Driven Fix Batch Recipe

Distinct from the static-analysis batch (`static-analysis-batch-recipe.md`) and the greenfield bootstrap (`parallel-subagent-batch-recipe.md`). Use this pattern when you **already have a prioritized bug list** (from a prior static audit or test-RED cycle) and need to apply fixes across multiple packages in parallel.

Captured from the a monorepo hardening (2026-07-06): 3 parallel GLM-5.2 subagents fixed 10 HIGH/MEDIUM bugs across 8 files in 8 packages. 2 subagents completed cleanly, 1 was interrupted mid-task with 12/12 patches applied. Parent gap-filled the remaining unfixed bug + 1 GLM-5.2 duplicate export.

## When to use this pattern

- You have a written audit with prioritized bugs (HIGH/MEDIUM/LOW)
- Bugs span multiple packages (3+ files across 2+ packages)
- Bugs are independent enough that 3 subagents won't edit the same file
- You are NOT greenfield (code exists, you're fixing it)

**Do NOT use this pattern for:**
- Single-file fixes (just patch it directly)
- Bugs that all cluster in one package (one subagent, not 3)
- Greenfield scaffolding (use `parallel-subagent-batch-recipe.md`)

## The structure

### Batch F (3 parallel subagents, ~5-10 min)

Partition the bug list by package area so no two subagents touch the same file.

| Subagent | Bug scope | Files it may edit |
|---|---|---|
| 1. Parser (Python) | parser_service.py, field_extractor.py | packages/parser/** |
| 2. Amendment + db | amendment/index.js, api/db.js, builder.js | packages/amendment/**, packages/api/db.js, packages/campaign-builder/builder.js |
| 3. Campaign-builder + API routes | the company.js, campaigns.js, email.js | packages/campaign-builder/**, packages/api/routes/**, packages/notifications/email.js |

**Critical partitioning rule:** if two bugs touch the same file, they MUST be in the same subagent. For example, `builder.js` had both a verify-step bug (BUG 3) and missing amendment methods (BUG 2) — both went to subagent 2+3 respectively, but the parent verified no overlap in the actual diff hunks.

### When a subagent shares a file with another

In this session, `builder.js` was modified by both subagent B (amendment methods) and subagent C (verify step). This worked because:
- Subagent B's patches were in the class body (new methods after `buildForIo`)
- Subagent C's patch was inside `buildForIo` itself (adding verify step)
- Both used `patch` (targeted find-replace), not `write_file` (full overwrite)

If two subagents need to edit the same file with `write_file`, serialize them instead. `patch` is safe for concurrent non-overlapping hunks.

## Subagent prompt template

```text
Fix {N} {SEVERITY} bugs in the {PACKAGE_AREA}. Make changes directly to files in
{ALLOWED_PATHS}. Do NOT push, do NOT run any production server, do NOT touch any
other repo.

BUG 1 ({SEVERITY}): {file}:{line} — {description of what's wrong}
Fix approach: {specific fix direction, e.g. "Add the three missing methods to the
Store class: getIoByIoNumber, writeAuditLog, getCampaignStatus"}

BUG 2 ({SEVERITY}): {file}:{line} — {description}
Fix approach: {specific fix direction}

{... more bugs}

CONSTRAINTS:
- Only modify files under {ALLOWED_PATHS}
- Do NOT commit or push anything
- Do NOT run any servers or production APIs
- Do NOT touch other repos
- Keep changes minimal and focused on these bugs
- All JS must pass `node --check` after modifications
- All Python must pass `ast.parse` after modifications
- Preserve all existing exports and function signatures that other packages depend on

After making changes, verify syntax with:
  {exact verification command}

Print a summary of ALL files you modified and the exact changes made.
```

**Key sections that prevent bugs:**
1. **Explicit allowed paths** — prevents the subagent from editing files outside its lane
2. **"Fix approach" per bug** — gives direction without dictating exact code; the subagent fills in the implementation
3. **"Do NOT commit/push/run servers"** — prevents side effects
4. **Syntax verification command** — forces the subagent to self-check
5. **"Preserve existing exports"** — prevents the subagent from breaking downstream consumers

## Parent verification sequence (after all subagents return)

This is the critical step. Do NOT trust subagent self-reports. Run this sequence:

```bash
# 1. What changed?
cd /path/to/repo && git diff --stat

# 2. Syntax check ALL JS files (not just the ones subagents claim to have modified)
err=0
for f in $(find packages -name '*.js' | grep -v node_modules | sort); do
  node --check "$f" 2>&1 || { echo "FAIL: $f"; err=$((err+1)); }
done
echo "JS errors: $err"

# 3. Syntax check ALL Python files
python3 -c "
import ast, os
errs=0
for root, _, files in os.walk('packages/parser'):
    for f in files:
        if f.endswith('.py'):
            p = os.path.join(root, f)
            try: ast.parse(open(p).read())
            except SyntaxError as e: print(f'FAIL {p}: {e}'); errs+=1
print(f'PY errors: {errs}')
"

# 4. Cross-reference: for each bug in the original spec, was it actually fixed?
#    Read the diff for each file and confirm the fix is present.
git diff packages/path/to/file.js

# 5. Run existing tests (if any)
cd packages/amendment && node --test test/smoke.test.mjs

# 6. Run smoke tests from the build audit
cd packages/validation && node -e "import('./index.js').then(m => /* smoke */)"
cd packages/campaign-builder && node -e "import('./__init__.js').then(m => /* dry-run */)"
```

## Gap-filling (when a subagent was interrupted or timed out)

After the verification sequence, identify which bugs from the original spec were NOT fixed:

1. **Read the diff** for each file the subagent was supposed to modify
2. **Cross-reference** against the bug list — is each bug's fix present in the diff?
3. **For unfixed bugs**: patch them directly in the parent session (don't re-spawn a subagent for 1-2 missing fixes)

In that session:
- Subagent C was interrupted (exit_reason: "interrupted") with 12/12 patches applied
- Verification revealed BUG 1 (dry-run stub) was NOT fixed — the subagent ran out of time before reaching it
- Parent patched it directly: replaced the stub with `buildDryRunPayload(io, platform)` call
- Also fixed a GLM-5.2 (historical model, 2026-07) duplicate export in `__init__.js` that the subagent had introduced

## Cost benchmarks (GLM-5.2:cloud, 2026-07-06)

| Subagent | Input tokens | Output tokens | Wall time | Outcome |
|---|---|---|---|---|
| Parser (3 bugs, Python) | 280k | 7k | 282s | Clean — all 3 bugs fixed |
| Amendment + db (3 bugs, JS) | 243k | 17k | 526s | Clean — all 3 bugs fixed |
| Campaign-builder + API (7 bugs, JS) | 618k | 8k | 272s | Interrupted — 6/7 bugs fixed, 1 gap-filled by parent |
| **Total wall time (parallel)** | — | — | **~526s** | 10 bugs fixed, 1 gap-filled, 1 GLM-5.2 bug fixed |

**Pattern:** fix-batch subagents tend to be cheaper than bootstrap subagents because they read fewer files (only the ones with bugs). The 618k-input subagent was the largest and was interrupted — consistent with the >500k token threshold for timeouts/interruptions.

## Commit hygiene

- Commit all subagent + parent fixes in a single commit with a clear summary
- Use `git commit -F /tmp/commit-msg.txt` with a file-based message
- Author as the user (e.g. `--author="the user <you@example.com>"`)
- No `Co-Authored-By` trailers (per user preference)
- Do NOT push — present the commit summary and ask for review

## See also

- `../SKILL.md` — parent skill (timeout/interruption recovery, git push patterns)
- `glm-5.2-bug-patterns.md` — recurring code-gen bugs to watch for during verification
- `static-analysis-batch-recipe.md` — the audit phase that produces the bug list this recipe consumes
- `audit-driven-tdd-recipe.md` — alternative: write tests from the audit FIRST, then fix