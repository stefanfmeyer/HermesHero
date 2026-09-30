# RN-web layout, resize, and the scroll bug that `onContentSizeChange` cannot see

Companion to SKILL.md Step 8.6b. Written from the AMA port (Expo SDK 57 /
react-native-web) where the transcript was left 61–102px short of the bottom
after every turn and three successive fixes silently did nothing.

## The bug

The transcript is scrolled programmatically on content growth. That handles
images and galleries arriving late, which is what the handler was written for.
What it does **not** handle: the composer growing, which shrinks the transcript's
**viewport** while the **content height is unchanged**.

Anything rendering *above* the composer input makes the composer taller:
suggestion chips after a turn, a confirmation card, a pending-attachment row.
The transcript's `clientHeight` drops and the newest content falls below the
fold. `onContentSizeChange` never fires, so nothing re-pins.

It presents as **intermittent** because it depends on whether the reply's tail
lands in the last 61–102px.

## Raw measurement — the whole diagnosis in one table

Sampled every 300ms after a turn went idle. Note `scrollHeight` is constant
throughout: the *content* never changed.

```
  t(s)  clientH   dist  inputTop  chips
   0.0      862      0       941      0
   ...
   2.7      862      0       941      0
   3.0      801     61       941      3      <-- chips appear
        ^ clientH -61  inputTop +0  chips 0->3
   3.3      801     61       941      3
   ...
   6.9      801     61       941      3
```

`inputTop` does not move — the composer grows *downward into the viewport*, so
watching the input's position finds nothing. The chip count going `0->3` at the
exact frame `clientHeight` drops is what identifies the cause. Across runs the
shrink was 61px (3 chips) and 102px (4 chips).

A second probe (`diagnose_scroll_settle.py`) is what rules late-loading content
*out*: it samples geometry repeatedly after idle and reports whether
`scrollHeight` or `clientHeight` changed. Content-growth bugs show as
`scrollHeight` increasing; this one shows as `clientHeight` alone changing. Both
probes are worth keeping — the distinction is not visible in the symptom.

## The two mechanisms that look right and do nothing

Both were measured on the live bundle. Both fail **silently**, which is why each
cost a full deploy-and-verify cycle.

### `onLayout` on the ScrollView fires zero times

Instrumented to push to `window.__dbgT` on every callback:

```
onLayout events: NONE — onLayout never fired
final geometry: {'dist': 61, 'scrollH': 979, 'clientH': 801, 'scrollTop': 117}
```

Zero callbacks across an entire turn, *including for the resize it was supposed
to catch*, while the viewport shrank underneath it. Do not use `onLayout` on
react-native-web for resize detection.

### `domScrollerRef.current` is never assigned on web

The component already had a callback ref on the ScrollView that captured the DOM
node (`domScrollerRef`). Instrumenting the observer's attach path:

```
[
 {"at": "attach-attempt", "hasEl": false, "h": null}
]
```

One attempt, no element, and — because the effect's dependency array did not
include the mount condition — never retried. The RN ref on web does not populate
this, so every path gated on it is a no-op. **Resolve the node by query:**

```ts
const el = document.querySelector('[data-testid="transcript"]') as HTMLElement | null;
```

### Bonus: which node actually resizes

A standalone `ResizeObserver` on the outer node and its first few descendants:

```
ResizeObserver events: [{"i":0,"h":862}, {"i":1,"h":946}, {"i":2,"h":946},
                        {"i":3,"h":946}, {"i":4,"h":52}, {"i":5,"h":22},
                        {"i":0,"h":801}]
```

Only index 0 — the scrolling node carrying `testID="transcript"` — reports the
change. The inner content wrapper holds at 946px and would never fire. Observe
the element with the testID, not its wrapper.

## The fix

```tsx
/**
 * Re-pin the transcript when its VIEWPORT shrinks (not its content).
 * Re-pins only if we were already at the bottom — never yank a user who is
 * reading further up.
 */
const repinIfViewportShrank = useCallback((clientH: number) => {
  const prev = viewportHeightRef.current;
  viewportHeightRef.current = clientH;
  if (prev <= 0 || clientH >= prev - 1) return;      // grew or unchanged
  if (userScrolledAwayRef.current) return;
  const el = document.querySelector('[data-testid="transcript"]') as HTMLElement | null;
  if (!el) return;
  const dist = el.scrollHeight - el.clientHeight - el.scrollTop;
  if (dist > 1) scrollToBottom();                     // sub-pixel = already at end
}, [scrollToBottom]);
```

Wire it up — and note the third dependency, which is the non-obvious part:

```tsx
useEffect(() => {
  if (Platform.OS !== "web" || !transcriptMounted) return;
  const el = document.querySelector('[data-testid="transcript"]') as HTMLElement | null;
  if (!el) return;
  viewportHeightRef.current = el.clientHeight;   // seed, or the first
                                                 // callback looks like a resize
  const ro = new ResizeObserver(() => repinIfViewportShrank(el.clientHeight));
  ro.observe(el);

  const onWinResize = () => repinIfViewportShrank(el.clientHeight);
  window.addEventListener("resize", onWinResize);  // window resizes have no
                                                   // layout hook either
  return () => {
    window.removeEventListener("resize", onWinResize);
    ro.disconnect();
  };
}, [repinIfViewportShrank, transcriptMounted]);
```

### `transcriptMounted` — conditionally-rendered nodes have no node to observe

The transcript and the hero are branches of one ternary, so **on a fresh chat
there is nothing to attach to**:

```tsx
{messages.length === 0 ? <hero/> : <transcript/>}
```

A mount-time-only attach finds no node and does nothing. Derive the condition and
put it in the dependency array:

```tsx
const transcriptMounted = messages.length > 0;
```

This is a general React lesson, not an RN one: **any effect that binds to a node
rendered behind a condition needs that condition as a dependency.**

## Ordering trap: the callback must be defined after its dependency

`repinIfViewportShrank` depends on `scrollToBottom`, so it must be declared
*after* it. Placing the refs and the callback above `scrollToBottom` produces:

```
error TS2448: Block-scoped variable 'scrollToBottom' used before its declaration.
```

Keep refs where they are grouped; move the callback below the function it calls.

## Result

```
3.6      801      0       941      4      <-- viewport still shrinks 61-102px,
3.9      801      0       941      4          but dist is now 0
```

The viewport still shrinks — that is correct behaviour. The transcript is
re-pinned, so nothing is hidden. Assert `dist == 0`, **not** that the viewport
stopped shrinking.

## Attributing a flaky E2E failure honestly

Mid-work the RN E2E began dying with `TargetClosedError` (chromium process death)
about 1 run in 6, reporting **zero failed checks** when it happened. It is worth
knowing whether your change caused it, and the answer must be evidence:

```bash
git stash push -m "wip" <changed-file>     # revert just the suspect file
./deploy/deploy-at2.sh                     # redeploy HEAD's build
./e2e/run_e2e_repeat.sh 6                  # same loop, same count
```

It reproduced on unmodified HEAD, so it was pre-existing — not caused by the
change. `git stash pop` and redeploy (confirm the bundle hash matches the
pre-stash build to prove the restore is clean).

Two supporting details that make this diagnosis trustworthy:

- A crash is distinguishable from an assertion failure by the summary line: a
  failure prints `FAILED: <check>`, a crash prints nothing and exits non-zero
  with zero `[FAIL]` lines. Check for the *absence* of the summary rather than
  assuming a failure.
- A `git stash`-based A/B is only valid if the deploy actually changed. Compare
  the printed `local index.html` / `remote index.html` hashes — identical hashes
  between the two arms mean you tested the same build twice and proved nothing.

## Probe scripts

Keep these committed; they are what turn "the scroll is a bit off sometimes" into
a line number.

| Script | Answers |
|---|---|
| `diagnose_scroll_settle.py` | Content growth or viewport resize? Reports which of `scrollHeight` / `clientHeight` changes after idle. |
| `diagnose_viewport_resize.py` | What caused it? Samples `clientHeight`, distance-to-bottom, `inputTop`, and chip count together, so the trigger is visible in the frame it fires. |
| `run_e2e_repeat.sh N` | Is a failure deterministic? Runs the suite N times, prints exit code + fail count + the summary line per run. |
| `verify_all_live.sh` | Full sweep: unit tests, every live probe, the full E2E. |

Instrument first. Both dead mechanisms above were identified in one run each by
pushing callback invocations to `window.__dbg*` and reading them back — after two
full cycles lost writing layout handlers that never fired.
