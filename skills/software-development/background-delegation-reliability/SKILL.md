---
name: background-delegation-reliability
description: >
  Operational rules for delegate_task background subagents: what survives a
  gateway/parent restart (nothing), which task classes fail as delegations
  (read-only analysis hitting provider rate limits), the inline-vs-delegate
  decision rule, and how to verify a delegation's real output via live
  transcripts and on-disk artifacts instead of trusting its summary.
  Use when a background delegation fails, disappears, or before choosing
  between delegating and doing work inline.
---

# Background Delegation Reliability

Lessons from repeated delegation failures (2026-09-09, GLM provider): a simple
read-only repo-analysis task failed THREE times as a background delegation
(429 retry exhaustion, mid-run interruption, gateway restart killing the
handle) before being done inline in ~10 minutes.

## Failure modes

### 1. Background delegations do NOT survive restarts
A `delegate_task` running in the background is tied to the parent session and
the gateway process. If the gateway restarts or the parent session is
interrupted mid-run, the delegation is gone: the completion message says
`interrupted`, and later `process poll` on the delegation id returns
`not_found`. Any files the subagent was supposed to write may not exist.

Recovery: check the live transcript at
`~/.hermes/cache/delegation/live/<delegation_id>/task-0.log` for what it did,
then check the target paths on disk. Assume nothing was written unless verified.

### 2. Provider 429s exhaust a read-only analysis delegation
Symptom: `exit_reason=max_iterations`, final summary is just
`HTTP 429: too many concurrent requests` after N retries. The subagent spent
its whole budget retrying provider calls and never produced the report.
Re-dispatching usually repeats the failure while the provider is saturated.

### 3. Silent patch failures (existing files)
Covered in depth by `subagent-large-project-pattern`: patches inside subagents
can return success with zero diff. Always `git diff --stat` after any
delegation that modifies existing files.

### 4. Research fan-outs time out when every item needs search+verify
Symptom: a batch dispatch of N "find a citation URL per row, verify it" tasks
where 7 of 12 subagents hit the 600s hard timeout (the completed ones were
the tightly-scoped re-dispatches). Per-item multi-round web_search +
extraction simply does not fit the budget at ~20+ rows per agent.

The pattern that worked (Sep 28 2026, 200-row policy-citation backfill):

1. **Harvest embedded data from the source first, in the parent.** ~27% of
   the rows self-cited (URLs buried in free-text notes). One parent-side
   regex pass recovered them instantly - no delegation needed.
2. **Bulk-verify in the parent with parallel curl** (ThreadPoolExecutor,
   10-12 workers). Seconds for dozens of URLs, and failures are visible
   immediately instead of buried in a subagent transcript.
3. **Direct-assign well-known hub URLs** for the remainder from domain
   knowledge, verify, and iterate on the failures.
4. **Only delegate the genuinely unknown remainder**, tightly scoped:
   ≤20 rows per agent, "verify by HEAD/GET only, never web_extract the
   page", "max ~2 searches per 5 rows", an explicit fallback policy ("fall
   back to the platform's policy hub page rather than stalling"), and a
   strict output contract (write a JSON file, one entry per input line).
   The re-dispatched pass-2 agents under these constraints finished in
   120-320s vs 600s timeouts.

Corollary: before re-dispatching a timed-out research fan-out, check whether
steps 1-3 would finish the job inline. They usually would.

## URL verification recipe (bulk, parent-side)

- **GET, not HEAD.** Google support and EUR-Lex 404 HEAD but 200 GET.
- **Try plain curl AND a browser-UA curl.** Meta/Facebook 400 some UA
  strings but 200 plain curl; other hosts are the opposite.
- **2xx counts as success** (EUR-Lex serves 202 challenge pages).
- **403/406 bot walls are acceptable** (page exists, blocks bots) - note
  them, never 404.
- **000 = host unreachable from this network**, not a bad URL - switch to
  an authoritative mirror (law.justia.com for statutes) rather than
  dropping the citation.
- Transient 5xx (e.g. business.x.com 502): retry before replacing the URL.

## Inline-vs-delegate decision rule

Delegate when: the subtask's intermediate data would flood your context
(large repo sweeps, 5+ dense files, parallel independent workstreams, or the
work produces a self-contained artifact the subagent writes to disk).

Do it INLINE when: the target is small enough to read directly (a few files /
<2k lines), the task is read-and-summarize, or a delegation for it has already
failed twice. Reading 4 files and writing a report yourself is faster and more
reliable than a third re-dispatch.

## Verification pattern (never trust the summary)

1. Read the live transcript log while it runs or after failure.
2. Verify claimed artifacts on disk yourself (`ls`, read the report file).
3. For code: build/test in the parent before committing.
4. If the delegation was interrupted and the work is small, finish it inline
   rather than re-dispatching.

## Related
- `subagent-large-project-pattern` — timeout/patch-failure recovery for large builds.
- `site-ui-replication` — example of a task where delegation for research is
  fine but the build itself is better done in the parent.