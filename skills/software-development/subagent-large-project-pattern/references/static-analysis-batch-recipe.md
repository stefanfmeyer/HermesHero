# Static-Analysis / Pre-Implementation Reconnaissance Batch

A different shape from the greenfield-bootstrap recipe in `../SKILL.md`. Use this pattern when you are about to make a meaningful change to a mature codebase and need a thorough understanding of:

- What features exist and how they interact
- What the bugs / edge cases are BEFORE you start writing fixes
- What the test surface should look like
- What the build/install environment will require

Captured from the the company Botpress integration hardening (2026-07-01): 3 parallel GLM-5.2 subagents produced 38KB of audit, 48KB of test plan, 10KB of build-env audit. The parent session then wrote 65 tests, all 18 audit suites were covered, and the RED-then-GREEN cycle caught 1 HIGH bug + 7 MEDIUM bugs that the audit predicted.

## When to use this pattern

- You are hardening / fixing a mature integration (not greenfield)
- The codebase has tests but you suspect coverage is thin
- You want to know what could break before you write a single line
- You want a written test plan you can execute against, not just "add tests"
- The user said something like "do extensive testing and error checking"

**Do NOT use this pattern for:**

- Greenfield / brand-new code (use the bootstrap recipe in `../SKILL.md`)
- Trivial changes (1-2 file fixes, no behavior change)
- Code you already understand deeply

## The structure

### Batch SA (3 parallel subagents, ~5-8 min total wall time)

Each subagent owns one lens on the same codebase. **They do NOT depend on each other** — each runs read-only and produces an independent artifact under `/tmp/`.

| Subagent | Output | Lens | Cost (observed) |
|---|---|---|---|
| 1. Static code review | `/tmp/audit-static.md` | Bugs, edge cases, schema↔impl gaps, type safety, doc↔code gaps | ~125k input / 17k output |
| 2. Test plan + test code | `/tmp/test-plan-and-cases.md` | Architecture decision, mock strategy, runnable test code, import-shim plan | ~104k input / 13k output |
| 3. Build environment audit | `/tmp/build-env-audit.md` | Environment readiness, exact build commands, failure points, time estimate, blockers | ~147k input / 8k output |

All three subagents see the same source files but produce different artifacts. Read the artifacts in the parent session, synthesize them, then act.

## Subagent prompt template (lens 1: static analysis)

```text
READ-ONLY. DO NOT commit/push/modify outside /tmp.

You are performing a STATIC CODE REVIEW of the {PROJECT_NAME} integration.

Key files (absolute paths):
- /path/to/repo/{file1}
- /path/to/repo/{file2}
... (enumerate all source files)

NO node_modules installed yet (no .botpress, no dist, no build artifacts).
Don't try to install or run.

I need a thorough static-analysis code review, then write findings to a file.

Output sections required:
A. BUGS — concrete defects. For each: file:line, what is wrong, why, severity
   (CRITICAL/HIGH/MEDIUM/LOW), and the exact fix.
B. EDGE CASES NOT HANDLED — situations the code does not currently cover.
C. SCHEMA <-> IMPLEMENTATION GAPS — places where the schema declares behavior
   the implementation does not (or vice versa).
D. TYPE SAFETY — places where types lie, undefined can leak, any/cast hides bugs.
E. DOC vs CODE GAPS — places where README/hub.md/COOKBOOK describes behavior
   the code does not implement, or vice versa.

Specifically check:
- {feature-specific checks, e.g. "Is the install probe actually a no-op
  server-side? Does the code assume so?"}
- {error-mapping checks, e.g. "Does the 4xx→reason mapping cover all
  documented HTTP statuses?"}
- {data-flow checks, e.g. "When the API returns both an ad and a
  no_fill_reason, which wins?"}
- {type-checks, e.g. "Are optional fields actually optional at runtime,
  or does the implementation always return a non-null value?"}

Output to /tmp/audit-static.md via write_file. Print DONE + path at the end.
```

## Subagent prompt template (lens 2: test plan + test code)

```text
READ-ONLY. DO NOT commit/push/modify outside /tmp.

You are designing a COMPLETE AUTOMATED TEST PLAN for {PROJECT_NAME}.

The runtime is at {SOURCE_PATH}. It exports {WHAT_THE_DEFAULT_EXPORT_IS}.
The {HANDLER} action's signature is `async ({ ctx, input, logger }) => Promise<output>`.

Required test suites (write each as a describe block):
{enumerate}

For each test suite, provide:
- Test name
- Setup: what mock to install on global.fetch
- Assertions: the exact expected output shape

Write all of this as a single file /tmp/test-plan-and-cases.md with:
- Section 1: Architecture decision (how to mock fetch, how to import {HANDLER})
- Section 2: Mock server design — recommend ONE approach and explain why
- Section 3: The full test file content, written out as a tests/{file}.test.ts
  string. (Don't actually create the file — just write the content in the markdown.)
- Section 4: {Additional test files}
- Section 5: Notes on the {GENERATED_IMPORT} import — workarounds

Make the test code REAL TypeScript that will compile and run, not pseudocode.
Use vitest's vi.fn() and vi.stubGlobal() for the fetch stub. Each test must
have a clear, single assertion or a small block of related assertions.

Output to /tmp/test-plan-and-cases.md via write_file. Print DONE + path at end.
```

## Subagent prompt template (lens 3: build environment)

```text
READ-ONLY. DO NOT commit/push/modify outside /tmp.

You are auditing the BUILD ENVIRONMENT for {PROJECT_NAME}.

Read {PACKAGE_JSON_PATH} fully. Note dependencies, devDependencies, engines.
Read {TSCONFIG_PATH} (strict mode, paths mapping, module resolution).
Read {SOURCE_FILE} (note what it imports — especially any generated/CLI-built dirs).

Steps you must do:
1. Check what's available locally: `which npm node npx`, `node --version`,
   `npm --version`, `npm config get registry`, network to registry.
2. Identify the dependency build order: what depends on what, what generates
   what, what needs to run before what.
3. Find issues that would block test setup: peer dep conflicts, login-gated
   build steps, missing runtime, etc.
4. Estimate install/build time.
5. Provide a recommended test-setup recipe: the exact bash commands in order.
6. Identify blockers / showstoppers (or "none").

Output to /tmp/build-env-audit.md via write_file with structure:
- A. Environment check results
- B. Build order & exact commands
- C. Likely failure points (with severity)
- D. Recommended recipe
- E. Blockers / showstoppers
- F. Time estimate

Print DONE + path at the end.
```

## Why this works (and why the three subagents are independent)

- **Static code review** needs every source file but does not need to know about
  test infrastructure or build steps.
- **Test plan** needs to know the runtime API but does not need to know the
  bug list (the bug list is what the parent derives by READING the test
  plan against the audit). The test plan should be neutral — "test what the
  code does" — not "test the bugs". The parent's job is to cross-reference.
- **Build env audit** needs the lockfile and toolchain but does not need the
  source code (it just needs to know what's imported).

The only shared assumption between the three is the path conventions
established in the parent session's first turn.

## Synthesis step (in the parent session)

After the 3 subagents return, the parent does:

1. **Read the audit** (lens 1). Extract the bug list, ordered by severity.
2. **Read the test plan** (lens 2). Note what tests exist for each bug.
3. **Read the build audit** (lens 3). Apply the recipe to set up the env.
4. **Cross-reference**: for each bug in the audit, is there a test for it in
   the plan? If a HIGH bug lacks a test, write one before fixing.
5. **Run tests RED** — confirm the tests actually catch the bugs they
   target. If a test passes against buggy code, the test is wrong.
6. **Apply fixes** in the parent session (or a subagent per fix).
7. **Run tests GREEN** — confirm all fixes work.
8. **Independent QA subagent** (optional but high-value) — a fourth subagent
   that re-reads the diff and re-runs the test suite to catch any bugs the
   parent missed. See the QA verification section in `../SKILL.md`.

## Cost benchmarks (GLM-5.2:cloud, 2026-07-01)

| Subagent | Input tokens | Output tokens | Wall time | Outcome |
|---|---|---|---|---|
| Static code review | 125k | 17k | 220s | Clean (38KB markdown) |
| Test plan + test code | 104k | 13k | 101s | Clean (48KB markdown) |
| Build env audit | 147k | 8k | 197s | Clean (10KB markdown) |
| **Total wall time (parallel)** | — | — | **~220s** | 3 artifacts, no timeouts |
| Independent QA (4th, later) | 208k | 5k | 107s | 5/5 verification points PASS |

**Pattern:** all three fit comfortably under 200k input tokens and finish
well under 300s. The static-review was the largest at 17k output — that's
the artifact the parent uses as the primary input for the bug list.

## Why this differs from the bootstrap recipe

The bootstrap recipe (`../SKILL.md`) is for *writing new code* across many
packages. The batches have a file-output dependency: Batch B's subagents
import from Batch A's output.

This recipe is for *understanding existing code* before changing it. There
is no file-output dependency between the three subagents — they each look
at the same source from a different angle. The parent does the synthesis.

## See also

- `../SKILL.md` — parent skill (bootstrap pattern + recovery)
- `glm-5.2-bug-patterns.md` — recurring code-gen bugs to watch for
- The QA verification pattern in the parent skill's "Verify Subagent Output" section
