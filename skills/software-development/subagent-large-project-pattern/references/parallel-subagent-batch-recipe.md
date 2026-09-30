# Parallel Subagent Batch Recipe

Proven layout for delegating a 5-package monorepo bootstrap to 3 concurrent GLM-5.2 subagents. Captured from that build 2026-07-01 (3 batches, 2 subagent timeouts, 99 files, 0 broken code at commit time).

## When to use this pattern

- Multi-package greenfield project (5+ new packages)
- Each package is 5-15 files of self-contained code
- 3 is the maximum concurrent subagents in your `config.yaml` (`delegation.max_concurrent_children`)
- Total file count 30-100

## The structure

### Batch A (3 parallel subagents, ~10 min)

Each subagent owns one self-contained package. **They do NOT depend on each other** for files. The only shared assumption is the path conventions established in the main session.

| Subagent | Output | Cost (observed) |
|---|---|---|
| 1. Core schema + parser | `packages/parser/schema/`, `packages/parser/extractors/`, `packages/parser/llm/prompts/` | ~1.2M input / 30k output |
| 2. API server | `packages/api/server.js`, `routes/`, `middleware/`, `db.js`, `schemas/io.js` | ~190k input / 12k output |
| 3. Ingestion queue | `packages/ingestion/queue.js`, `worker.js`, `upload/`, `email/`, `slack/` | ~275k input / 13k output |

### Batch B (3 parallel subagents, ~10 min)

Runs after Batch A finishes. Cross-package imports are now safe (the modules exist).

| Subagent | Output |
|---|---|
| 4. Campaign builder | `packages/campaign-builder/builder.js`, `adapters/`, `rollback.js`, `dry-run.js` |
| 5. Validation | `packages/validation/index.js`, `validators/` |
| 6. Amendment detector | `packages/amendment/detector.js`, `diff.js`, `scope.js`, `change_log.js` |

### Batch C (1-2 subagents, ~10 min)

Smaller, often finishes without timeout. Cross-cuts the whole system.

| Subagent | Output |
|---|---|
| 7. Review UI | `packages/review-ui/src/`, `package.json`, `vite.config.js` |
| 8. Notification agent (optional, can be in Batch B) | `packages/notifications/email.js`, `slack.js`, `audit_log.js`, `webhook.js`, `notifier.js` |

## Why this works

- **Batch A's 3 subagents are independent.** Schema, API, and ingestion don't need each other's files. They each only read existing repo files (`README.md`, `docs/`, `samples/`) plus the canonical schema spec.
- **Batch B runs after A.** By then the schema exists and Batch B subagents can import from it. This avoids the "import path doesn't exist yet" failure mode.
- **Single-subagent packages in Batch C.** Review UI is the largest single package and it usually times out — give it room by running it solo (don't compete with other subagents for the 3 slots).

## Subagent prompt template

The prompt that works. Replace `{PLACEHOLDERS}` per task.

```text
READ-ONLY. DO NOT commit/push/modify outside /tmp/build/.

You are building {TASK_DESCRIPTION} for {PROJECT}.

ALSO READ (do not modify):
- /path/to/repo/README.md
- /path/to/repo/docs/{relevant-spec}.md
- /path/to/build/{modules-this-depends-on}/

OUTPUT FILES:
A. /path/to/build/packages/{pkg}/{file1}.{ext}
B. /path/to/build/packages/{pkg}/{file2}.{ext}
... (enumerate every file you expect to write)

{SPECIFIC_REQUIREMENTS_FOR_EACH_FILE}

VERIFICATION (you must do this before declaring done):
- All .{ext} files must pass {syntax-checker}
- Run a functional smoke: {smoke-test-description}
- Output: "DONE — {N} files" with a one-line per file summary
```

**Critical sections of the prompt that prevent most bugs:**

1. **"READ-ONLY" + explicit out-dir** — prevents the subagent from committing/pushing on its own
2. **"OUTPUT FILES" enumeration** — gives the subagent a checklist so it doesn't forget files
3. **"VERIFICATION"** — forces the subagent to do its own checks before declaring done (still need your re-verification, but at least it tries)
4. **"ALSO READ"** with exact paths — prevents the subagent from making up module APIs
5. **"Output: 'DONE — N files'"** — gives you a clean terminal signature to grep for in batch results

## Recovery when a subagent times out

In one build, subagents #2 (validation) and #1 (review UI) both timed out at 600s. **Both delivered 80-100% of their files before the hang.** The hang was on the final verification step (Node `--check` on a broken file, or running a long smoke test).

Recovery recipe (3 minutes):

```bash
# 1. Find the timed-out subagent's session
ps -ef | grep -E "delegate|task" | head -5

# 2. Check what files it left behind
ls -la /path/to/build/packages/<timed-out-pkg>/ 2>/dev/null
find /path/to/build/packages/<timed-out-pkg> -type f | sort

# 3. Compare to the spec's "OUTPUT FILES" list — what's missing?

# 4. Syntax-check what exists (catches ~80% of remaining bugs)
err=0
for f in $(find /path/to/build/packages/<timed-out-pkg> -name "*.js" -o -name "*.jsx"); do
  if [[ "$f" == *.jsx ]]; then
    # JSX needs babel — see references/glm-5.2-bug-patterns.md §5
    :
  else
    node --check "$f" 2>/dev/null || { echo "FAIL: $f"; err=$((err+1)); }
  fi
done
echo "$err failures"

# 5. Read the failing files, understand the bug, fix with patch
# (Common fixes: see references/glm-5.2-bug-patterns.md)

# 6. Write the missing 1-2 files yourself with write_file
# (Don't re-spawn a subagent for 1-2 missing files)

# 7. Functional smoke before committing
cd /path/to/build/packages/<timed-out-pkg>
npm install  # or pip install
node -e "import('./<main-export>.js').then(m => /* smoke test */).catch(e => process.exit(1))"
```

## Cost benchmarks (GLM-5.2:cloud via Ollama, 2026-07-01)

| Task | Input tokens | Output tokens | Wall time | Outcome |
|---|---|---|---|---|
| Schema (Pydantic + Zod, 2 files) | 127k | 25k | 145s | Clean |
| API server (11 files) | 191k | 13k | 191s | Clean |
| Ingestion (10 files) | 275k | 13k | 192s | Clean |
| LLM prompt + 3 few-shot (4 files, large context) | 1.25M | 29k | 363s | Clean |
| Parser service (9 files) | 51k | 7k | 56s | Clean |
| Campaign builder (12 files) | 171k | 16k | 339s | Clean |
| Validation (7 files) | 490k | 22k | 600s timeout | 100% files, 23 bug fixes needed |
| Amendment (9 files) | 191k | 16k | 600s timeout | 100% files, smoke tests pass |
| Notifications (23 files) | 491k | 22k | 597s | Clean |
| Review UI (20 files) | 1.0M+ est | est 25k | 600s timeout | 19/20 files, 2 written manually |

**Pattern:** tasks with input > 500k tokens reliably hit 600s. Tasks < 200k input usually finish in 200-300s with clean output.

**Mitigation:** keep subagent prompts under 500k input tokens. If a prompt is too long, split the task or make the subagent read files lazily.

## See also

- `../SKILL.md` — parent skill
- `glm-5.2-bug-patterns.md` — the recurring code-gen bugs and fixes
