---
name: software-development-processes
description: "Structured software development lifecycle — planning, implementation, verification, and debugging. Covers TDD, systematic debugging, plan execution via subagents, and pre-commit code review."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [development, workflow, process, planning, implementation, verification, debugging, tdd, code-review, delegation]
    related_skills: [github-pr-workflow, systematic-debugging, writing-plans, test-driven-development, subagent-driven-development, requesting-code-review]
---

# Software Development Processes

A structured approach to the full software development lifecycle — from understanding requirements to shipping verified code. These skills compose together: `writing-plans` creates the roadmap, `subagent-driven-development` executes it, `test-driven-development` ensures correctness, `systematic-debugging` investigates failures, and `requesting-code-review` verifies before commit.

## Skill Map

| Skill | Role | When to Load |
|-------|------|-------------|
| `writing-plans` | Decompose requirements into bite-sized tasks | Before any multi-step implementation |
| `subagent-driven-development` | Execute plans via isolated subagents with 2-stage review | Implementing a written plan |
| `test-driven-development` | RED-GREEN-REFACTOR discipline | Writing any new code or fixing bugs |
| `systematic-debugging` | 4-phase root cause investigation | Any bug, test failure, or unexpected behavior |
| `requesting-code-review` | Pre-commit security + quality verification | Before `git commit` or `git push` |
| `spike` | Throwaway feasibility experiments | Before committing to an unproven approach — see `references/spike.md` |

## The Full Lifecycle

```
Requirements → writing-plans → subagent-driven-development
                                          ↓
                              [per task: TDD cycle]
                                          ↓
                              [per task: requesting-code-review]
                                          ↓
                              systematic-debugging (if issues found)
                                          ↓
                                    Shipped code
```

---

## writing-plans

Write implementation plans assuming the implementer has zero context. Document everything: file paths, complete code, exact commands, verification steps.

**Core principle:** A good plan makes implementation obvious. If someone has to guess, the plan is incomplete.

**Each task = 2-5 minutes of focused work.** Every step is one action.

### When to use

- Multi-step features
- Complex requirements
- Delegating to subagents

### Plan structure

Every plan starts with:

```markdown
# [Feature] Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan.

**Goal:** [One sentence]
**Architecture:** [2-3 sentences]
**Tech Stack:** [Key technologies]
```

Each task follows:

````markdown
### Task N: [Name]

**Objective:** What this accomplishes

**Files:**
- Create: `exact/path/file.py`
- Modify: `existing.py:45-67`

**Step 1: Write failing test**
```python
def test_behavior():
    assert function(input) == expected
```

**Step 2: Run test — verify FAIL**
`pytest tests/path/test.py::test_behavior -v`

**Step 3: Write minimal implementation**
```python
def function(input):
    return expected
```

**Step 4: Run test — verify PASS**
`pytest tests/path/test.py::test_behavior -v`

**Step 5: Commit**
`git add tests/path/test.py src/path/file.py && git commit -m "feat: add behavior"`
````

### Principles

- **DRY** — extract shared logic, don't repeat
- **YAGNI** — implement only what's needed now
- **TDD** — test-first for every behavior
- **Frequent commits** — after every task

See `writing-plans` skill for full details.

---

## subagent-driven-development

Execute implementation plans by dispatching fresh subagents per task with systematic two-stage review (spec compliance then code quality).

**Core principle:** Fresh subagent per task + two-stage review = high quality, fast iteration.

### When to use

- You have an implementation plan
- Tasks are mostly independent
- Quality and spec compliance are important

### The process

1. **Read the plan once** — extract ALL tasks with full context upfront. Don't make subagents re-read.
2. **Per task:** Dispatch implementer → spec reviewer → quality reviewer → mark complete
3. **Final integration review** after all tasks

### Per-task workflow

```
Implementer subagent → Spec reviewer → Quality reviewer → ✓ Task done
     ↑ (if issues)         ↑ (if issues)    ↑ (if issues)
     └──────────────────────┴─────────────────┘
              Fix and re-review
```

### Red flags — never do

- Start without a plan
- Skip reviews
- Dispatch multiple subagents for tasks that touch the same files
- Let implementer self-review
- Move to next task while review has open issues
- Start code quality review before spec compliance passes

See `subagent-driven-development` skill for full details.

---

## test-driven-development

Write the test first. Watch it fail. Write minimal code to pass.

**Iron Law:** `NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST`

### The cycle

```
RED    → Write failing test
GREEN  → Write minimal code to pass
REFACTOR → Clean up (tests stay green)
```

### RED — Write Failing Test

Good test:
```python
def test_retries_failed_operations_3_times():
    attempts = 0
    def operation():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise Exception('fail')
        return 'success'

    result = retry_operation(operation)
    assert result == 'success'
    assert attempts == 3
```

### GREEN — Minimal Code

Write the simplest thing that passes. Nothing more. No features, no "improvements."

### REFACTOR — Clean Up

After green only: remove duplication, improve names, extract helpers. Keep tests green.

### Why order matters

Tests written after code pass immediately. Passing immediately proves nothing:
- Might test the wrong thing
- Might miss edge cases
- Can't catch the bug you found

Test-first forces you to see the test fail, proving it tests something real.

### When stuck

| Problem | Solution |
|---------|----------|
| Don't know how to test | Write the wished-for API, assertion first |
| Test too complicated | Design too complicated — simplify the interface |
| Must mock everything | Code too coupled — use dependency injection |

See `test-driven-development` skill for full details.

---

## systematic-debugging

Random fixes waste time and create new bugs. **ALWAYS find root cause before attempting fixes.**

**Iron Law:** `NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST`

### The four phases

```
Phase 1: Root Cause  →  Phase 2: Pattern  →  Phase 3: Hypothesis  →  Phase 4: Fix
(understand WHY)         (what's different)    (test minimally)       (at the source)
```

### Phase 1: Root Cause Investigation

Before attempting ANY fix:
1. Read error messages carefully — note line numbers, file paths, error codes
2. Reproduce consistently — what are the exact steps?
3. Check recent changes — `git log --oneline -10`, `git diff`
4. Trace data flow — where does the bad value originate?

**Completion checklist:**
- [ ] Error messages fully read and understood
- [ ] Issue reproduced consistently
- [ ] Recent changes identified and reviewed
- [ ] Evidence gathered (logs, state, data flow)
- [ ] Root cause hypothesis formed

**STOP — do not proceed to Phase 2 until you understand WHY it's happening.**

### Phase 2: Pattern Analysis

Find working examples. Compare against broken code. Identify every difference.

### Phase 3: Hypothesis and Testing

Form ONE clear hypothesis. Make the SMALLEST possible change to test it. One variable at a time.

### Phase 4: Implementation

1. Create a failing test case reproducing the bug
2. Fix the root cause — ONE change at a time
3. Verify: `pytest tests/ -q`

**If 3+ fixes failed:** Question the architecture. This is not a failed hypothesis — it's a wrong architecture.

### Red flags — STOP

- "Quick fix for now, investigate later"
- "Just try changing X and see if it works"
- "I don't fully understand but this might work"
- "One more fix attempt" (after 2+ failures)

All mean: Return to Phase 1.

### Subprocess stdout capture gotcha

Python's `sys.stdout.write()` + `subprocess.run(capture_output=True)` = silent empty output. Fix: add `sys.stdout.flush()` after `sys.stdout.write()` and use `stdin=subprocess.DEVNULL`.

### curl vs browser differential diagnosis

When a request works from `curl` but fails in browser: the difference is the `Origin:` header. Use `curl -H "Origin: https://hostname"` to replicate browser behavior and catch CORS issues in reverse-proxy setups.

See `systematic-debugging` skill for full details.

---

## requesting-code-review

Automated verification pipeline before code lands: static scans, baseline-aware quality gates, independent reviewer subagent, and auto-fix loop.

**Core principle:** No agent should verify its own work. Fresh context finds what you miss.

### When to use

- After implementing a feature or bug fix, before `git commit` or `git push`
- After completing a task with 2+ file edits
- After each task in subagent-driven-development

**Skip for:** documentation-only changes, pure config tweaks.

### The pipeline

```
Step 1: Get the diff       → git diff --cached
Step 2: Static scan        → secrets, injection, eval()
Step 3: Baseline tests     → compare against pre-change failures
Step 4: Self-review        → quick checklist scan
Step 5: Reviewer subagent  → independent verdict (fail-closed)
Step 6: Evaluate           → all pass? → commit
Step 7: Auto-fix loop      → max 2 cycles, third agent fixes only reported issues
Step 8: Commit             → git commit -m "[verified] description"
```

### Baseline rule

Run the test suite **before** your changes (stash, run, pop). Only NEW failures introduced by your changes block the commit.

### Auto-fix limits

Maximum 2 fix-and-reverify cycles. After that: escalate to user with remaining issues.

See `requesting-code-review` skill for full details.

---

## How They Compose

### Starting a feature

```
1. Load writing-plans → understand requirements
2. Write the plan with exact tasks
3. Offer: "Ready to execute using subagent-driven-development?"
```

### During implementation (per task)

```
1. TDD cycle (test-driven-development)
2. requesting-code-review pipeline
3. If review fails → auto-fix loop
4. If bugs found → systematic-debugging
```

### Bug fix flow

```
1. systematic-debugging → find root cause
2. test-driven-development → write regression test
3. Fix the root cause
4. requesting-code-review → verify clean
```

### Pre-commit gate

Every code change goes through `requesting-code-review` before `git commit`.

---

## Principles That Apply Everywhere

- **Frequent commits** — small, logical, verifiable
- **No shortcuts** — systematic always beats guess-and-check
- **Independent verification** — never self-verify your own work
- **Root cause before fixes** — symptom fixes are failure
- **Test-first** — tests passing immediately proves nothing

## Workflow Pacing — Don't Over-Ask or Over-Document

User frustration signals to watch for: "Cmon already!", "stop doing X", "this is too verbose", "you always do Y and I hate it", "don't ask me about Z", "just give me the answer", "just push it". When the user has stated a clear action ("push it", "commit and push", "add X"), the implicit instruction is **execute, not plan more**.

**Default to action, not clarification, when:**
- The instruction is unambiguous ("push everything", "commit and push", "fix this")
- The trade-off is small (test scripts staying in build dir vs repo is reversible)
- The user has already said "go" or "do it" once and you're still asking

**Default to one short clarifying question, not a multi-question `clarify` panel, when:**
- The choice has material consequences (orchestration tool for a multi-package project)
- AND the answer is genuinely not inferable from context

**Anti-patterns that burn user patience:**

- Asking Q1/Q2/Q3 in a single `clarify` call when one question would do — user often only sees the first, forcing a re-ask
- Re-asking a question that was already partially answered
- Writing TESTING.md sections, README addenda, or other documentation the user did not request ("I'll add a guide to the repo" when user said "push what I have")
- Adding unprompted "next steps" suggestions after a successful push — user said push, not "and also do these other things"
- Treating "I'll write a TESTING.md" as obvious follow-up work when the user has not asked for it
- **Asking "which orchestration tool?" when the user said "make it work on my machine"** — both `make` and `npm scripts` are reasonable defaults. Pick one (npm scripts for cross-platform), ship, and offer the swap in the bookend if the user wants the other. Asking trades 5 seconds of clarification for 30 minutes of user waiting. (a project, 2026-07-02: agent asked 4 questions about tool choice, user replied "Don't ask me about orchestration tools / Cmon already! You're taking too long!")

**Rule of thumb:** if the user gave an instruction 30 seconds ago and you're still typing questions or writing docs they didn't ask for, you are over-asking or over-documenting. Stop. Execute.

## Per-Item Commit + Push + Test Cycle (User Preference)

When the user gives a **multi-item task list** and says "commit and push after each one is built" (or "commit each", "push each", "build and push them in order", etc.), the default workflow is:

```
For each item in the list:
  1. Build it (write code, run unit tests for the new code in isolation)
  2. Verify it (run the full test suite + lint — 0 errors required)
  3. Commit it (one focused commit per item, conventional commit message)
  4. Push it (git push origin main)
  5. Move to next item
After all items done: short status report, ask if user wants to continue
```

**Why this matters:**
- Each commit is small and revertable — if item #7 breaks something, you bisect to a 30-line diff, not 800 lines across 10 features.
- The user can review each push on GitHub as it lands, instead of staring at one giant "trust me" PR.
- If the user says "stop" mid-list, what you have so far is already on `main` and not stranded on a branch.
- "Test before pushing" is non-negotiable per the user's explicit rule — never push a commit that fails `node --test` / `pytest` / `eslint`.

**What "test before pushing" actually means:**
- For JS: `node --test` on the relevant test files AND `npx eslint` on the changed files (0 errors). If a per-package `npm test` exists, run that.
- For Python: `python -m pytest <relevant test files>` (0 failures). Don't run image/OCR tests that need Tesseract unless the change touched that code.
- Run the full repo-level test runner (`node scripts/run-tests.js` or equivalent) as a final gate if one exists — that catches regressions in unchanged files.
- "Tests pass" = both new tests AND existing tests still pass. Never lower the bar because "I only changed this one file."

**Tooling tip — track progress with `todo`:**
When the list has 3+ items, build a `todo` list at the start. Mark each item `in_progress` when you start it, `completed` immediately after the push lands, not before. Cancelled items get `cancelled` with a one-line reason, not silently dropped. The todo list is your bookend honesty check — if you claim an item is done, it must be marked completed in the todo.

**Status report format that works for this pattern:**
Short markdown table:

```
| # | Commit | Description |
|---|--------|-------------|
| 1 | abc123 | ESLint flat configs for all 7 packages |
| 2 | def456 | Pinned parser requirements.txt |
... (one row per item, real commit hash from `git log --oneline`)
```

Then a one-line "X of N complete" summary and a direct "want me to continue with #X, #Y?" question. The table is the verifiable receipt — every claim in the table is backed by a real commit on `main`. If the user later asks "did you actually push #4?", you can point at the commit hash, not your memory of intending to.

**Anti-pattern — single mega-commit at the end:** batching 10 features into one commit so you can "push once" defeats the purpose. The user asked for per-item commits; give them per-item commits. Pushing is cheap; reviewing a 2000-line PR is not.

## Common Implementation Gotchas

When implementing multi-step features in Node.js / ESM / Express, recurring foot-guns surface in predictable places. Before you refactor sync → async, add a route handler that needs to await, or bundle a heavy client lib, read `references/common-js-esm-async-gotchas.md` — it covers:

- The `await` in non-`async` function trap (Express handlers especially)
- The pool/db helper that returns a Promise but callers don't await
- The `process.env` vs `import.meta.env.VITE_*` split in Vite builds
- PDF.js worker bundling via Vite `?url` and render cancellation
- Duplicate object keys via spread, `case` block declarations, `hasOwnProperty` direct calls
- The "command looks like a server" misdetection of `vite build`

## Bookend Honesty — Verify Your Own Claims Before Reporting Them

Session-bookend summaries ("we pushed 3 commits", "all clean", "10/10 tests pass") are **claims the agent makes to the user** and they MUST be verified before being asserted. In one session (2026-07-02 project), the agent's bookend said "Pushed 3 commits: 8f3a2b4, 1a7c4f9, 0e9d3c1" — but `git reflog` on the actual repo showed no such commits. The "pushes" never happened. The session had only uncommitted changes sitting in a build dir.

**Before any "All done" or "Pushed N commits" message, run:**

```bash
cd <repo> && git log --oneline -10
git ls-remote origin main    # what remote actually has
git rev-parse HEAD           # what local actually has
```

If `local != remote` after you claimed a push, you didn't push — fix it before reporting success.

**Why this happens:** the agent's bookend is generated at the end of a turn, often from memory of what it *intended* to do, not from a fresh `git log` check. Memory is unreliable; `git log` is ground truth. **Always re-verify repo state at end of turn before claiming success.**

This compounds with the session-recall rule: when a future session asks "what did we do yesterday", trust the git log of the actual repo, not the previous session's bookend text. The bookend can be wrong even if everything else in the session went well.