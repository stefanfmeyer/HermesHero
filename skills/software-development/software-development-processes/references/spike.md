# Spike — Throwaway Experiments

> Sourced from `spike` skill. Validates feasibility before committing to a real build.

## When to use

When the user wants to **feel out an idea** before committing — validating feasibility, comparing approaches, or surfacing unknowns that no amount of research will answer. Spikes are disposable by design. Throw them away once they've paid their debt.

**Activate when user says:** "let me try this", "I want to see if X works", "spike this out", "before I commit to Y", "quick prototype of Z", "is this even possible?", or "compare A vs B".

**Skip when:**
- The answer is knowable from docs or reading code — just do research
- The work is production path — use the planning process instead
- The idea is already validated — jump straight to implementation

## Core method

```
decompose  →  research  →  build  →  verdict
   ↑__________________________________________↓
              iterate on findings
```

### 1. Decompose

Break the idea into **2-5 independent feasibility questions**. Present as a table:

| # | Spike | Validates (Given/When/Then) | Risk |
|---|-------|----------------------------|------|
| 001 | websocket-streaming | Given a WS connection, when LLM streams tokens, then client receives chunks < 100ms | High |
| 002a | pdf-parse-pdfjs | Given a multi-page PDF, when parsed with pdfjs, then structured text is extractable | Medium |
| 002b | pdf-parse-camelot | Given a multi-page PDF, when parsed with camelot, then structured text is extractable | Medium |

**Order by risk** — the spike most likely to kill the idea runs first.

### 2. Build

One directory per spike. Keep it standalone. Bias toward something the user can interact with:

1. A runnable CLI that takes input and prints observable output
2. A minimal HTML page that demonstrates the behavior
3. A small web server with one endpoint
4. A unit test that exercises the question with recognizable assertions

### 3. Verdict

Each spike's `README.md` closes with:

```markdown
## Verdict: VALIDATED | PARTIAL | INVALIDATED

### What worked
- ...

### What didn't
- ...

### Surprises
- ...

### Recommendation for the real build
- ...
```

**VALIDATED** = the core question was answered yes, with evidence.
**PARTIAL** = works under constraints X, Y, Z — document them.
**INVALIDATED** = doesn't work, for this reason. This is a successful spike.

## With GSD system

If `gsd-spike` is installed (via `npx get-shit-done-cc --hermes`), prefer it for full GSD workflow: persistent `.planning/spikes/` state, MANIFEST tracking, Given/When/Then verdict format. This skill is the lightweight standalone version.

## Attribution

Adapted from the GSD (Get Shit Done) project's `/gsd-spike` workflow — MIT © 2025 Lex Christopherson.