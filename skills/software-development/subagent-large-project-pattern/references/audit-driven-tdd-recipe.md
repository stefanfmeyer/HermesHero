# Audit-Driven TDD: RED Tests as Audit Confirmation

A specific TDD variant where the "spec" is an audit report (from a
subagent batch) and the test suite is the proof that the audit was right.
Use this when the user asks for "extensive testing", "audit the code",
"verify everything works", or "find all the bugs".

Captured from the second round of the the company Botpress integration
hardening (2026-07-01). After the first round (audit → fix → 65 tests),
the parent session identified additional audit findings (B1, B2, B3, B6,
B7, C3) and applied this pattern: **write tests targeting each finding
FIRST, confirm they fail, THEN fix.** Result: 42 more tests added in
one batch with no false positives and no missed bugs.

## The invariant

**If a test passes against the buggy code, the test is wrong.**

This is the core principle. A test for bug X must fail when bug X is
present and pass when bug X is fixed. If it passes both ways, it is
not testing the bug — it is testing something else, or it is broken,
or the bug was already fixed (in which case delete the test).

## The pattern (5 steps)

### Step 1: Take the audit, ordered by severity

The audit from `static-analysis-batch-recipe.md` produces a list of
bugs, edge cases, and contract gaps. Order them by severity (CRITICAL
→ HIGH → MEDIUM → LOW). Skip items the user has explicitly said are
out of scope (e.g. "we don't care about E7 right now").

### Step 2: For each finding, write a test BEFORE fixing

For each bug:
- Identify the *behavior* the bug violates. This becomes the test
  assertion.
- Identify the *input* that triggers the bug. This becomes the test
  setup.
- Write a test that asserts the *correct* behavior (not the buggy one).

Example from the the company round 2:

| Audit finding | Test that catches it |
|---|---|
| B1: `turnCount` omission bypasses gate | `turnCount=undefined → fetch fires, turn_count key absent` |
| B2: `z.number()` rejects string | `turnCount schema coerces "3" to 3` (B2 fix target) |
| B3: `ads` as object silently dropped | `ads as object → no-fill api_error + warn` |
| B6: ad+reason discards reason silently | `ad+reason → ad served AND warn fires with reason` |
| B7: empty client_ip sent as "" | `clientIp="" → client_ip key absent` |
| C3: `?? 2` dead code masks bugs | `minTurnCount=undefined → throws diagnostic` |

### Step 3: Run the suite RED

Run the full test suite. The new tests should fail. The failure
messages should match the audit's predicted behavior — if a test
fails with a different error than expected, the test is testing the
wrong thing.

**Verify the RED state explicitly:**

```bash
npm test 2>&1 | tail -50
# Count: "X failed, Y passed"
# Cross-check: every bug from the audit should have at least one
# failing test. Bugs without failing tests are unaddressed.
```

### Step 4: Apply the fixes

For each failing test, apply the production fix. Use the audit's
"exact fix" section as the patch source — the audit's job was to
diagnose; now you just transcribe the fix.

### Step 5: Run the suite GREEN

```bash
npm test 2>&1 | tail -10
# All green.
```

If a test still fails after the fix:
- The fix is incomplete (e.g. you fixed the !ad branch but forgot
  the !field branch).
- The test is asserting wrong behavior (e.g. you wrote "no_fill_reason
  is the API's reason" but the fix correctly maps to a different
  reason).
- The audit was wrong (rare; double-check by reading the actual code
  path the test exercises).

In all three cases, the failing test is a real signal — don't silence
it by changing the test, fix the underlying issue.

## Why this is different from regular TDD

Regular TDD: spec → test → fail → code → pass.

Audit-driven TDD: audit (which IS a spec, just from a subagent) →
test (which encodes the audit's expectations) → fail (which proves
the audit is right) → code (which transcribes the audit's fix) →
pass (which proves the fix works).

The key difference: the audit already exists, and the parent session
should not silently generate it from scratch. Use the subagent batch
to produce the audit (static-analysis-batch-recipe.md), then apply
this recipe to act on it.

## Why "tests pass against buggy code" is a red flag

Consider this common mistake: you read the audit, see "A1: !ad branch
discards no_fill_reason", write a test:

```ts
it('surface_inactive + ads=[] → noFillReason="surface_inactive"', async () => {
  fetchMock.mockResolvedValue(res(200, { ads: [], no_fill_reason: 'surface_inactive' }))
  const out = await getHandlers().serveAd({ ctx: makeCtx(), input: makeInput(), logger: makeLogger().logger })
  expect(out.noFillReason).toBe('surface_inactive')
})
```

This test will pass against the original buggy code if you forgot to
also set the input's `turnCount` (in which case the local gate fires
and returns `min_turn_not_reached`, which is the wrong reason for this
test). Or if the fixture has `ads: []` but the code returns
`no_eligible_ads` instead of `surface_inactive`, the test fails —
which is the point. The test must fail when the bug is present.

If your test passes against the buggy code, you have a test that
doesn't test the bug. Common causes:

- **The test setup accidentally avoids the bug.** E.g. you set
  `turnCount=5` and `minTurnCount=2`, so the local gate passes — but
  the audit is about a code path that only triggers when the API
  responds with `ads: []` and a non-`min_turn_not_reached` reason.
  The setup accidentally bypasses the bug.
- **The test asserts the wrong thing.** E.g. you assert `hasAd=false`
  but not the specific `noFillReason` value. The buggy code also
  returns `hasAd=false`, just with a different reason.
- **The bug is in a code path the test doesn't reach.** E.g. you
  test the happy path but the bug is in the !ad branch.

## Worked example (B3 from the the company audit)

The audit said:

> B3: API returns `ads` as a single object instead of an array.
> Current behavior: `result.data.ads?.[0]` on a non-array returns
> `undefined`. The ad is silently lost; `!ad` branch returns
> `no_eligible_ads`. Expected: detect non-array `ads` and either
> extract the object or return an `api_error` with a log.

The test (written BEFORE the fix):

```ts
describe('B3 — `ads` is not an array', () => {
  it('ads as a single object (not array) → no-fill api_error with warn', async () => {
    fetchMock.mockResolvedValue(
      res(200, {
        ads: { title: 'T', body: 'B', cta: 'C', click_url: 'u', impression_url: 'i' },
      })
    )
    const { logger, calls } = makeLogger()
    const out = await getHandlers().serveAd({ ctx: makeCtx(), input: makeInput(), logger })
    expect(out.hasAd).toBe(false)
    expect(out.noFillReason).toBe('api_error')
    expect(calls.warn.some((m) => m.includes('not an array'))).toBe(true)
  })
})
```

Run RED: `out.noFillReason` is `'no_eligible_ads'` (the bug — falls
through the !ad branch). Test fails. ✓

Apply the fix (in `fetchAd`):

```ts
if (data.ads !== undefined && !Array.isArray(data.ads)) {
  params.logger.forBot().warn('[the company] Response `ads` field is not an array. Serving no-fill.')
  return { ok: false, reason: 'api_error' }
}
```

Run GREEN: `out.noFillReason` is now `'api_error'`. Test passes. ✓

## When NOT to use this pattern

- The audit is from a different session and the code has changed
  since. Re-run the audit first; don't trust stale findings.
- The bug is "trivial" (a typo, a one-line fix). Just fix it; no
  test needed unless the fix is in a critical path.
- The audit is purely about docs (no code change). Skip the
  test, update the doc.

## See also

- `../SKILL.md` — parent skill covering GLM-5.2 subagent timeout
  recovery and git push patterns.
- `static-analysis-batch-recipe.md` — the 3-subagent pre-implementation
  batch that produces the audit this recipe acts on.
- `../test-driven-development` — the general TDD recipe.
