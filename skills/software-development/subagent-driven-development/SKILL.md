---
name: subagent-driven-development
description: "Execute plans via delegate_task subagents (2-stage review)."
version: 1.1.0
author: Hermes Agent (adapted from obra/superpowers)
license: MIT
metadata:
  hermes:
    tags: [delegation, subagent, implementation, workflow, parallel]
    related_skills: [writing-plans, requesting-code-review, test-driven-development]
---

# Subagent-Driven Development

## Overview

Execute implementation plans by dispatching fresh subagents per task with systematic two-stage review.

**Core principle:** Fresh subagent per task + two-stage review (spec then quality) = high quality, fast iteration.

## When to Use

Use this skill when:
- You have an implementation plan (from writing-plans skill or user requirements)
- Tasks are mostly independent
- Quality and spec compliance are important
- You want automated review between tasks

**vs. manual execution:**
- Fresh context per task (no confusion from accumulated state)
- Automated review process catches issues early
- Consistent quality checks across all tasks
- Subagents can ask questions before starting work

## The Process

### 1. Read and Parse Plan

Read the plan file. Extract ALL tasks with their full text and context upfront. Create a todo list:

```python
# Read the plan
read_file("docs/plans/feature-plan.md")

# Create todo list with all tasks
todo([
    {"id": "task-1", "content": "Create User model with email field", "status": "pending"},
    {"id": "task-2", "content": "Add password hashing utility", "status": "pending"},
    {"id": "task-3", "content": "Create login endpoint", "status": "pending"},
])
```

**Key:** Read the plan ONCE. Extract everything. Don't make subagents read the plan file — provide the full task text directly in context.

### 2. Per-Task Workflow

For EACH task in the plan:

#### Step 1: Dispatch Implementer Subagent

Use `delegate_task` with complete context:

```python
delegate_task(
    goal="Implement Task 1: Create User model with email and password_hash fields",
    context="""
    TASK FROM PLAN:
    - Create: src/models/user.py
    - Add User class with email (str) and password_hash (str) fields
    - Use bcrypt for password hashing
    - Include __repr__ for debugging

    FOLLOW TDD:
    1. Write failing test in tests/models/test_user.py
    2. Run: pytest tests/models/test_user.py -v (verify FAIL)
    3. Write minimal implementation
    4. Run: pytest tests/models/test_user.py -v (verify PASS)
    5. Run: pytest tests/ -q (verify no regressions)
    6. Commit: git add -A && git commit -m "feat: add User model with password hashing"

    PROJECT CONTEXT:
    - Python 3.11, Flask app in src/app.py
    - Existing models in src/models/
    - Tests use pytest, run from project root
    - bcrypt already in requirements.txt
    """,
    toolsets=['terminal', 'file']
)
```

#### Step 2: Dispatch Spec Compliance Reviewer

After the implementer completes, verify against the original spec:

```python
delegate_task(
    goal="Review if implementation matches the spec from the plan",
    context="""
    ORIGINAL TASK SPEC:
    - Create src/models/user.py with User class
    - Fields: email (str), password_hash (str)
    - Use bcrypt for password hashing
    - Include __repr__

    CHECK:
    - [ ] All requirements from spec implemented?
    - [ ] File paths match spec?
    - [ ] Function signatures match spec?
    - [ ] Behavior matches expected?
    - [ ] Nothing extra added (no scope creep)?

    OUTPUT: PASS or list of specific spec gaps to fix.
    """,
    toolsets=['file']
)
```

**If spec issues found:** Fix gaps, then re-run spec review. Continue only when spec-compliant.

#### Step 3: Dispatch Code Quality Reviewer

After spec compliance passes:

```python
delegate_task(
    goal="Review code quality for Task 1 implementation",
    context="""
    FILES TO REVIEW:
    - src/models/user.py
    - tests/models/test_user.py

    CHECK:
    - [ ] Follows project conventions and style?
    - [ ] Proper error handling?
    - [ ] Clear variable/function names?
    - [ ] Adequate test coverage?
    - [ ] No obvious bugs or missed edge cases?
    - [ ] No security issues?

    OUTPUT FORMAT:
    - Critical Issues: [must fix before proceeding]
    - Important Issues: [should fix]
    - Minor Issues: [optional]
    - Verdict: APPROVED or REQUEST_CHANGES
    """,
    toolsets=['file']
)
```

**If quality issues found:** Fix issues, re-review. Continue only when approved.

#### Step 4: Mark Complete

```python
todo([{"id": "task-1", "content": "Create User model with email field", "status": "completed"}], merge=True)
```

### 3. Final Review

After ALL tasks are complete, dispatch a final integration reviewer:

```python
delegate_task(
    goal="Review the entire implementation for consistency and integration issues",
    context="""
    All tasks from the plan are complete. Review the full implementation:
    - Do all components work together?
    - Any inconsistencies between tasks?
    - All tests passing?
    - Ready for merge?
    """,
    toolsets=['terminal', 'file']
)
```

### 4. Verify and Commit

```bash
# Run full test suite
pytest tests/ -q

# Review all changes
git diff --stat

# Final commit if needed
git add -A && git commit -m "feat: complete [feature name] implementation"
```

## Task Granularity

**Each task = 2-5 minutes of focused work.**

**Too big:**
- "Implement user authentication system"

**Right size:**
- "Create User model with email and password fields"
- "Add password hashing function"
- "Create login endpoint"
- "Add JWT token generation"
- "Create registration endpoint"

## Memory-Constrained Environments (CRITICAL — learned 2026-07-10)

**On machines with limited RAM (4GB or less), subagents can exhaust memory and cause system instability.** the user explicitly said: "Don't use subagents, execute the plan yourself. We don't have enough memory on your machine for subagents."

**Rule:** Before dispatching subagents, check the available memory. If the machine has ≤4GB RAM (common on VPS deployments like Hetzner cx23), **execute the plan directly in the controller session** — do not spawn subagents. The two-stage review process can be replaced by self-verification (run the tests yourself, read the code yourself, verify imports/syntax yourself).

**When direct execution is required:**
- Still follow the plan's task ordering
- Still write tests first (TDD)
- Verify each task's output yourself: `python -c 'import ast; ...'`, `python -m pytest tests/ -v`, `node --check file.js`
- The "fresh context per task" benefit is lost, but so is the memory overhead of spawning parallel LLM sessions
- Batch independent file reads/writes to compensate for the lost parallelism

**Detection:** Check `free -h` or look for known memory constraints in the user's environment (e.g. Hindsight OOM-killed 901x on 4GB VPS is a clear signal). When in doubt, ask the user before dispatching subagents on a VPS or low-RAM machine.

## Red Flags — Never Do These

- Start implementation without a plan
- Skip reviews (spec compliance OR code quality)
- Proceed with unfixed critical/important issues
- Dispatch multiple implementation subagents for tasks that touch the same files
- Make subagent read the plan file (provide full text in context instead)
- Skip scene-setting context (subagent needs to understand where the task fits)
- Ignore subagent questions (answer before letting them proceed)
- Accept "close enough" on spec compliance
- Skip review loops (reviewer found issues → implementer fixes → review again)
- Let implementer self-review replace actual review (both are needed)
- **Start code quality review before spec compliance is PASS** (wrong order)
- Move to next task while either review has open issues
- **Trust subagent self-reports** — always verify the work yourself before declaring done (see "Verify Subagent Output" below)
- **Add a mid-execution permission gate the user didn't ask for** — once scope is clear, ship the whole batch and surface the diff at the end (see "User-Scope Discipline" below)

## Handling Issues

### If Subagent Asks Questions

- Answer clearly and completely
- Provide additional context if needed
- Don't rush them into implementation

### If Reviewer Finds Issues

- Implementer subagent (or a new one) fixes them
- Reviewer reviews again
- Repeat until approved
- Don't skip the re-review

### If Subagent Fails a Task

- Dispatch a new fix subagent with specific instructions about what went wrong
- Don't try to fix manually in the controller session (context pollution)

### If Subagent Silently Exits Without Writing the Output File

**GLM-5.2 (and similar long-context subagents) sometimes hit `max_iterations` and exit before calling `write_file` for their final artifact.** Symptoms:
- Subagent returns `status: 'completed'` with a self-report like "report written to /tmp/..."
- File does NOT exist on disk
- `exit_reason: 'max_iterations'` in the response

**Recovery:**
1. **Verify immediately after subagent returns**: `ls -la /tmp/<expected-output>.md` (or `wc -l`, `head`, `tail`)
2. If file is missing, re-run with the same prompt — GLM-5.2 has good reliability on retry
3. The re-run usually completes faster because the model has already done the research; tell it explicitly: "the previous run did the reads but failed to write. Skip re-research, just write_file now."
4. **Defensive prompt design for the future**: tell the subagent in its prompt to verify the file exists at the end with `terminal("ls -la /tmp/<path>")` and re-write if missing.

**Pattern that works** (from Prebid S2S research, June 20 2026): end the subagent prompt with
> "Output to /tmp/...md via write_file. Then run `ls -la /tmp/...md` to verify. If missing, write_file again. End your final message with: 'DONE /tmp/...md'."

## Verify Subagent Output (don't trust the self-report)

**Subagent self-reports are SELF-REPORTS, not verified facts.** A subagent that returns `status: 'completed'` with text like "all tests pass" or "DONE — schema built" can be wrong. In one 5-subagent batch (a multi-package platform build, 2026-07-01), three subagents reported "done" with file counts and verification claims, and **all three had real bugs** that surfaced only when the parent session ran the verifications itself:

- Schema subagent: built Zod + Pydantic models that rejected raw LLM output because `_meta` and `Meta.notes` were required (they should be optional — `_meta` is parser-internal metadata, not LLM output).
- Parser subagent: documented function as `extract_docx` but the actual export was `extract` — the parent's first import attempt failed.
- API subagent: shipped a CJS-bridge shim (`schemas/index.js` using `createRequire`) that worked at `node --check` time but crashed the server at boot in Node 22 because the consumer package was `"type": "module"` and Node 22's strict ESM resolution bypassed the bridge.

**Required verification gates after every subagent batch** (do this in the parent session, not by trusting the subagent):

| Subagent wrote | Verify with |
|---|---|
| Python files | `python3 -c 'import ast; [ast.parse(open(f).read()) for f in [...]]'` |
| JS/TS files | `node --check path/to/file.js` for each file |
| JSON fixtures | `python3 -c 'import json; json.load(open(f))'` |
| Pydantic models | `python3 -c 'from m import M; M.model_validate(json.load(open("sample.json")))'` against real sample data |
| Zod schemas | `node -e "const {IORecord} = require('./schemas/io.js'); IORecord.safeParse(sample)"` against real sample data |
| FastAPI/Express server | Actually start it: `terminal(background=true)`, then `curl /health` and a real endpoint, then `process(action='kill')` |
| BullMQ/queue code | `node --check` for syntax; runtime test requires Redis — flag if not available |
| LLM prompts | `python3 -c "open('prompts/system.txt').read()"` for size, `json.load('prompts/few_shot.json')` for JSON examples |

**Rule:** if a subagent claims something works, the parent must independently confirm before telling the user. The 30 seconds spent on verification prevents the user from discovering the bug 10 minutes later.

## User-Scope Discipline (don't add permission gates the user didn't ask for)

When the user gives a multi-step task with a clear scope, they want the work done — not a series of mid-execution permission prompts. the user (the user this pattern is named for) explicitly stated: "Don't require confirmation between each wave."

**Default to ship-the-whole-batch:**
- Plan the work upfront (todos, wave structure) and surface the plan in your first reply
- Note any decisions you're making on the user's behalf ("I'm working in /tmp/project-build/, no commits until you say")
- Then execute the whole thing without stopping
- Surface a single comprehensive diff/report at the end for review

**When mid-execution clarification IS warranted:**
- The task is ambiguous in a way that affects the deliverable shape (not just detail)
- A destructive action is queued (commits, force-pushes, deletes, deploys)
- The user explicitly said "stop and ask" or "confirm before..."
- Two reasonable approaches have materially different cost/benefit

**When mid-execution clarification is NOT warranted:**
- Working directory choice (separate build dir vs in-repo) — pick a sensible default
- Parallelism strategy — pick the limit and go
- Subagent prompt wording — internal detail
- File naming, internal organization — internal detail
- Whether to verify with curl or with a unit test — internal detail

**The test:** if you're pausing to ask, would the user's most likely answer change the shape of the deliverable? If no, ship the default. If yes and the choice is reversible, pick one and call it out. If yes and the choice is irreversible (commit, push, delete), then ask.

This pattern is named for the user (July 1 2026, platform build), but it's general: if a user gives you a multi-wave plan and doesn't ask for checkpoints, treat the whole thing as one deliverable.

## Efficiency Notes

**Why fresh subagent per task:**
- Prevents context pollution from accumulated state
- Each subagent gets clean, focused context
- No confusion from prior tasks' code or reasoning

**Why two-stage review:**
- Spec review catches under/over-building early
- Quality review ensures the implementation is well-built
- Catches issues before they compound across tasks

**Cost trade-off:**
- More subagent invocations (implementer + 2 reviewers per task)
- But catches issues early (cheaper than debugging compounded problems later)

## Integration with Other Skills

### With writing-plans

This skill EXECUTES plans created by the writing-plans skill:
1. User requirements → writing-plans → implementation plan
2. Implementation plan → subagent-driven-development → working code

### With test-driven-development

Implementer subagents should follow TDD:
1. Write failing test first
2. Implement minimal code
3. Verify test passes
4. Commit

Include TDD instructions in every implementer context.

### With requesting-code-review

The two-stage review process IS the code review. For final integration review, use the requesting-code-review skill's review dimensions.

### With systematic-debugging

If a subagent encounters bugs during implementation:
1. Follow systematic-debugging process
2. Find root cause before fixing
3. Write regression test
4. Resume implementation

## Example Workflow

```
[Read plan: docs/plans/auth-feature.md]
[Create todo list with 5 tasks]

--- Task 1: Create User model ---
[Dispatch implementer subagent]
  Implementer: "Should email be unique?"
  You: "Yes, email must be unique"
  Implementer: Implemented, 3/3 tests passing, committed.

[Dispatch spec reviewer]
  Spec reviewer: ✅ PASS — all requirements met

[Dispatch quality reviewer]
  Quality reviewer: ✅ APPROVED — clean code, good tests

[Mark Task 1 complete]

--- Task 2: Password hashing ---
[Dispatch implementer subagent]
  Implementer: No questions, implemented, 5/5 tests passing.

[Dispatch spec reviewer]
  Spec reviewer: ❌ Missing: password strength validation (spec says "min 8 chars")

[Implementer fixes]
  Implementer: Added validation, 7/7 tests passing.

[Dispatch spec reviewer again]
  Spec reviewer: ✅ PASS

[Dispatch quality reviewer]
  Quality reviewer: Important: Magic number 8, extract to constant
  Implementer: Extracted MIN_PASSWORD_LENGTH constant
  Quality reviewer: ✅ APPROVED

[Mark Task 2 complete]

... (continue for all tasks)

[After all tasks: dispatch final integration reviewer]
[Run full test suite: all passing]
[Done!]
```

## Remember

```
Fresh subagent per task
Two-stage review every time
Spec compliance FIRST
Code quality SECOND
Never skip reviews
Catch issues early
```

**Quality is not an accident. It's the result of systematic process.**

## Further reading (load when relevant)

When the orchestration involves significant context usage, long review loops, or complex validation checkpoints, load these references for the specific discipline:

- **`references/context-budget-discipline.md`** — Four-tier context degradation model (PEAK / GOOD / DEGRADING / POOR), read-depth rules that scale with context window size, and early warning signs of silent degradation. Load when a run will clearly consume significant context (multi-phase plans, many subagents, large artifacts).
- **`references/gates-taxonomy.md`** — The four canonical gate types (Pre-flight, Revision, Escalation, Abort) with behavior, recovery, and examples. Load when designing or reviewing any workflow that has validation checkpoints — use the vocabulary explicitly so each gate has defined entry, failure behavior, and resumption rules.

Both references adapted from gsd-build/get-shit-done (MIT © 2025 Lex Christopherson).
