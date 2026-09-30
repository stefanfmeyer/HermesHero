---
name: systematic-debugging
description: Use when encountering any bug, test failure, or unexpected behavior. 4-phase root cause investigation — NO fixes without understanding the problem first.
version: 1.1.0
author: Hermes Agent (adapted from obra/superpowers)
license: MIT
metadata:
  hermes:
    tags: [debugging, troubleshooting, problem-solving, root-cause, investigation]
    related_skills: [test-driven-development, writing-plans, subagent-driven-development]
---

# Systematic Debugging

## Overview

Random fixes waste time and create new bugs. Quick patches mask underlying issues.

**Core principle:** ALWAYS find root cause before attempting fixes. Symptom fixes are failure.

**Violating the letter of this process is violating the spirit of debugging.**

## The Iron Law

```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

If you haven't completed Phase 1, you cannot propose fixes.

## When to Use

Use for ANY technical issue:
- Test failures
- Bugs in production
- Unexpected behavior
- Performance problems
- Build failures
- Integration issues

**Use this ESPECIALLY when:**
- Under time pressure (emergencies make guessing tempting)
- "Just one quick fix" seems obvious
- You've already tried multiple fixes
- Previous fix didn't work
- You don't fully understand the issue

**Don't skip when:**
- Issue seems simple (simple bugs have root causes too)
- You're in a hurry (rushing guarantees rework)
- Someone wants it fixed NOW (systematic is faster than thrashing)

## The Four Phases

You MUST complete each phase before proceeding to the next.

---

## Phase 1: Root Cause Investigation

**BEFORE attempting ANY fix:**

### 1. Read Error Messages Carefully

- Don't skip past errors or warnings
- They often contain the exact solution
- Read stack traces completely
- Note line numbers, file paths, error codes

**Action:** Use `read_file` on the relevant source files. Use `search_files` to find the error string in the codebase.

### 2. Reproduce Consistently

- Can you trigger it reliably?
- What are the exact steps?
- Does it happen every time?
- If not reproducible → gather more data, don't guess

**Action:** Use the `terminal` tool to run the failing test or trigger the bug:

```bash
# Run specific failing test
pytest tests/test_module.py::test_name -v

# Run with verbose output
pytest tests/test_module.py -v --tb=long
```

### 3. Check Recent Changes

- What changed that could cause this?
- Git diff, recent commits
- New dependencies, config changes

**Action:**

```bash
# Recent commits
git log --oneline -10

# Uncommitted changes
git diff

# Changes in specific file
git log -p --follow src/problematic_file.py | head -100
```

### 4. Gather Evidence in Multi-Component Systems

**WHEN system has multiple components (API → service → database, CI → build → deploy):**

**BEFORE proposing fixes, add diagnostic instrumentation:**

For EACH component boundary:
- Log what data enters the component
- Log what data exits the component
- Verify environment/config propagation
- Check state at each layer

Run once to gather evidence showing WHERE it breaks.
THEN analyze evidence to identify the failing component.
THEN investigate that specific component.

### 5. Trace Data Flow

**WHEN error is deep in the call stack:**

- Where does the bad value originate?
- What called this function with the bad value?
- Keep tracing upstream until you find the source
- Fix at the source, not at the symptom

**Action:** Use `search_files` to trace references:

```python
# Find where the function is called
search_files("function_name(", path="src/", file_glob="*.py")

# Find where the variable is set
search_files("variable_name\\s*=", path="src/", file_glob="*.py")
```

### Phase 1 Completion Checklist

- [ ] Error messages fully read and understood
- [ ] Issue reproduced consistently
- [ ] Recent changes identified and reviewed
- [ ] Evidence gathered (logs, state, data flow)
- [ ] Problem isolated to specific component/code
- [ ] Root cause hypothesis formed

**STOP:** Do not proceed to Phase 2 until you understand WHY it's happening.

---

## Phase 2: Pattern Analysis

**Find the pattern before fixing:**

### 1. Find Working Examples

- Locate similar working code in the same codebase
- What works that's similar to what's broken?

**Action:** Use `search_files` to find comparable patterns:

```python
search_files("similar_pattern", path="src/", file_glob="*.py")
```

### 2. Compare Against References

- If implementing a pattern, read the reference implementation COMPLETELY
- Don't skim — read every line
- Understand the pattern fully before applying

### 3. Identify Differences

- What's different between working and broken?
- List every difference, however small
- Don't assume "that can't matter"

### 4. Understand Dependencies

- What other components does this need?
- What settings, config, environment?
- What assumptions does it make?

---

## Phase 3: Hypothesis and Testing

**Scientific method:**

### 1. Form a Single Hypothesis

- State clearly: "I think X is the root cause because Y"
- Write it down
- Be specific, not vague

### 2. Test Minimally

- Make the SMALLEST possible change to test the hypothesis
- One variable at a time
- Don't fix multiple things at once

### 3. Verify Before Continuing

- Did it work? → Phase 4
- Didn't work? → Form NEW hypothesis
- DON'T add more fixes on top

### 4. When You Don't Know

- Say "I don't understand X"
- Don't pretend to know
- Ask the user for help
- Research more

---

## Phase 4: Implementation

**Fix the root cause, not the symptom:**

### 1. Create Failing Test Case

- Simplest possible reproduction
- Automated test if possible
- MUST have before fixing
- Use the `test-driven-development` skill

### 2. Implement Single Fix

- Address the root cause identified
- ONE change at a time
- No "while I'm here" improvements
- No bundled refactoring

### 3. Verify Fix

```bash
# Run the specific regression test
pytest tests/test_module.py::test_regression -v

# Run full suite — no regressions
pytest tests/ -q
```

### 4. If Fix Doesn't Work — The Rule of Three

- **STOP.**
- Count: How many fixes have you tried?
- If < 3: Return to Phase 1, re-analyze with new information
- **If ≥ 3: STOP and question the architecture (step 5 below)**
- DON'T attempt Fix #4 without architectural discussion

### 5. If 3+ Fixes Failed: Question Architecture

**Pattern indicating an architectural problem:**
- Each fix reveals new shared state/coupling in a different place
- Fixes require "massive refactoring" to implement
- Each fix creates new symptoms elsewhere

**STOP and question fundamentals:**
- Is this pattern fundamentally sound?
- Are we "sticking with it through sheer inertia"?
- Should we refactor the architecture vs. continue fixing symptoms?

**Discuss with the user before attempting more fixes.**

This is NOT a failed hypothesis — this is a wrong architecture.

---

## Red Flags — STOP and Follow Process

If you catch yourself thinking:
- "Quick fix for now, investigate later"
- "Just try changing X and see if it works"
- "Add multiple changes, run tests"
- "Skip the test, I'll manually verify"
- "It's probably X, let me fix that"
- "I don't fully understand but this might work"
- "Pattern says X but I'll adapt it differently"
- "Here are the main problems: [lists fixes without investigation]"
- Proposing solutions before tracing data flow
- **"One more fix attempt" (when already tried 2+)**
- **Each fix reveals a new problem in a different place**

**ALL of these mean: STOP. Return to Phase 1.**

**If 3+ fixes failed:** Question the architecture (Phase 4 step 5).

## Common Rationalizations

| Excuse | Reality |
|--------|---------|
| "Issue is simple, don't need process" | Simple issues have root causes too. Process is fast for simple bugs. |
| "Emergency, no time for process" | Systematic debugging is FASTER than guess-and-check thrashing. |
| "Just try this first, then investigate" | First fix sets the pattern. Do it right from the start. |
| "I'll write test after confirming fix works" | Untested fixes don't stick. Test first proves it. |
| "Multiple fixes at once saves time" | Can't isolate what worked. Causes new bugs. |
| "Reference too long, I'll adapt the pattern" | Partial understanding guarantees bugs. Read it completely. |
| "I see the problem, let me fix it" | Seeing symptoms ≠ understanding root cause. |
| "One more fix attempt" (after 2+ failures) | 3+ failures = architectural problem. Question the pattern, don't fix again. |

## Quick Reference

| Phase | Key Activities | Success Criteria |
|-------|---------------|------------------|
| **1. Root Cause** | Read errors, reproduce, check changes, gather evidence, trace data flow | Understand WHAT and WHY |
| **2. Pattern** | Find working examples, compare, identify differences | Know what's different |
| **3. Hypothesis** | Form theory, test minimally, one variable at a time | Confirmed or new hypothesis |
| **4. Implementation** | Create regression test, fix root cause, verify | Bug resolved, all tests pass |

## Hermes Agent Integration

### Investigation Tools

Use these Hermes tools during Phase 1:

- **`search_files`** — Find error strings, trace function calls, locate patterns
- **`read_file`** — Read source code with line numbers for precise analysis
- **`terminal`** — Run tests, check git history, reproduce bugs
- **`web_search`/`web_extract`** — Research error messages, library docs

### With delegate_task

For complex multi-component debugging, dispatch investigation subagents:

```python
delegate_task(
    goal="Investigate why [specific test/behavior] fails",
    context="""
    Follow systematic-debugging skill:
    1. Read the error message carefully
    2. Reproduce the issue
    3. Trace the data flow to find root cause
    4. Report findings — do NOT fix yet

    Error: [paste full error]
    File: [path to failing code]
    Test command: [exact command]
    """,
    toolsets=['terminal', 'file']
)
```

### Subprocess stdout capture silently returns empty (critical)

When a Python script uses `sys.stdout.write()` (not `print()`) and you capture output with `subprocess.run(capture_output=True)`:

**The problem:** Python's stdout is **fully buffered** when connected to a pipe, not line-buffered. Output is held in a buffer and may not appear in `result.stdout` until the subprocess exits — but if the script also writes to stderr on error, or if something else drains the buffer, it can be lost entirely. `bufsize=1` (line buffering) does NOT override this for piped stdout in Python 3.

**The telltale signs:**
- Direct shell execution (`python3 script.py 2>&1 | head`) produces output
- `subprocess.run(["python3", "script.py"], capture_output=True).stdout` is empty
- `result.stderr` might be empty too
- `result.returncode` is 0
- The script appears to succeed but produces nothing

**The fix — two changes needed together:**
```python
# 1. Explicit PIPE + line-buffering + DEVNULL for stdin
result = subprocess.run(
    ["python3", script_path] + args,
    stdin=subprocess.DEVNULL,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1,           # line-buffered on supported platforms
    timeout=600,
    cwd=os.path.dirname(os.path.abspath(script_path))
)

# 2. In the subprocess script — flush after sys.stdout.write()
sys.stdout.write(article)
sys.stdout.flush()   # critical: force buffer flush before exit
```

**Also:** When using `os.path.dirname(script_path)` as `cwd`, ensure `script_path` is absolute — a relative `script_path` with a relative `cwd` results in a non-existent directory, silently returning empty output with returncode 127 ("file not found").

**When investigating this:**
1. Run the script directly in shell first — if it produces output there but not via subprocess, it's a capture issue
2. Check `result.stderr` — it may contain the real error even when `result.stdout` is empty
3. Check returncode — 0 means "success" from the OS, but the script may have exited abnormally
4. Add `log(stage_num, "Script output ({0} chars)".format(len(output)))` immediately after `result.stdout` to see exactly what was captured

### Differential Diagnosis: curl vs Browser

When a request works from `curl` but fails in a browser, the difference is in the **headers** the browser sends automatically:

**Browser adds these that curl doesn't:**
- `Origin: https://hostname` — the critical difference for CORS
- `User-Agent` (usually harmless)
- `Accept` headers
- `Connection: keep-alive`

**How to use this pattern:**
```bash
# Test WITHOUT Origin header (like curl)
curl -I http://localhost:8787/path

# Test WITH Origin header (like browser from Tailscale)
curl -I -H "Origin: https://tailscale-fqdn" http://localhost:8787/path

# Compare: if second fails with CORS/403 but first works → origin policy issue
```

**Why this catches Tailscale/reverse-proxy bugs:**
- Tailscale sets `X-Forwarded-Host`, strips the port from `Host` header
- Browser sends `Origin: https://tailscale-fqdn` (port 443 implicit)
- The app sees origin port 443 but socket is on a different port
- CORS origin check fails even though it's the same host

**Socket port inference pattern for same-hostname reverse proxies:**
When `origin.hostname === host.hostname` and `origin.port === 443` (TLS terminated by proxy), use `request.socket.localPort` as the effective port instead of the origin port.

### With test-driven-development

When fixing bugs:
1. Write a test that reproduces the bug (RED)
2. Debug systematically to find root cause
3. Fix the root cause (GREEN)
4. The test proves the fix and prevents regression

## Real-World Impact

From debugging sessions:
- Systematic approach: 15-30 minutes to fix
- Random fixes approach: 2-3 hours of thrashing
- First-time fix rate: 95% vs 40%
- New bugs introduced: Near zero vs common

**No shortcuts. No guessing. Systematic always wins.**

## Pitfalls

### Bulk sed Replacement on Comma-Separated Object/Array Literals

**Pattern:** Replacing a key from multiple files containing comma-separated object or array literals — e.g. removing `'NFLX'` from `'TSLA':'TSLA', 'NFLX':'NFLX', 'CRM':'CRM'`.

**What goes wrong:** Simple `sed -i '' "s/, 'NFLX'//g"` removes the `'NFLX'` entry but leaves a trailing comma from the previous entry, or the comma that was before `'NFLX'` attaches to the next item:

```
Before: 'TSLA':'TSLA', 'NFLX':'NFLX', 'CRM':'CRM'
After:  'TSLA':'TSLA': 'CRM':'CRM'   ← DOUBLE COLON, syntax error
```

**When it bites you:** Bulk ticker removal, bulk feature flag removal, bulk any-key removal across multiple files. The sed succeeds silently and the file looks fine until you run `node --check`.

**Prevention:**
1. Use Node.js to do string replacement — it lets you handle adjacent commas properly
2. Always `node --check` immediately after each file
3. If you must use sed, do ONE file at a time with immediate verification

**Detection:** Run `node --check` across all modified files immediately. Syntax errors will be the first sign.

**2026-05-07 example:** 8 files corrupted during NFLX removal. Sed patterns removed `'NFLX'` from multi-item comma-separated lines, leaving orphaned colons. Required manual repair of `03-check-exits.js`, `fetch-rss.js`, `place-orders.js`, `execute-trades.js`, `fetch-prices.js`, `track-performance.js`, `record-executions.js`, `alphavantage-data.js`.
