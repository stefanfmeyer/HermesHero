---
name: browser-app-automation
description: Testing and driving modern web apps (react-aria/HeroUI, Next.js) via browser automation — press handling, hydration pitfalls, stale fiber state, responsive verification without viewport control, geometry-delta assertions for hover/interaction states, browser-engine divergence (a page that works in Chromium and crashes in Firefox), and app-state seeding via storage. Also covers numerically-verified CSS layout work — turning a fixed overlay into a real grid column, sticky-header offsets, rotated edge-tab labels, desktop-only gates, and proving a content-hashed bundle actually shipped. Use when a browser check should back a UI claim, when a screenshot can't settle a layout question, or when the user sends a mock to match.
---

# Browser Automation of Modern Web Apps

Class-level techniques for driving/testing web apps with the browser tool when plain `.click()` / `.type()` stop working. Originally proven on a Next.js 16 + HeroUI (react-aria) app. Also covers **verifying interaction states numerically** (hover must not move layout — a 2px shift is invisible in a screenshot but obvious to the user) and **seeding app state** without driving the UI.

## Symptom: buttons "look clickable" but nothing happens

Diagnose in order:

1. **Hydration blocked.** If the page never hydrated, NO handlers fire — synthetic or real. Check: elements have no `__reactFiber$*` / `__reactProps$*` own-properties (`Object.keys(el)` empty) → not hydrated. Common cause: dev server blocking cross-origin HMR resources (Next.js "Blocked cross-origin request to Next.js dev resource /_next/webpack-hmr"). Fix: access via the same host the server binds (e.g. `localhost` not `127.0.0.1`), or add `allowedDevOrigins` in next.config and restart.
2. **react-aria press semantics.** react-aria components (HeroUI Button, etc.) use `onPress`, driven by pointer-event sequences, NOT `onClick`. Synthetic `element.click()` does not trigger `onPress`. Native-`onClick` option cards (plain `<button onClick>`) DO respond to direct prop invocation.
3. **Disabled guard.** The handler may exist but the press is a no-op because the component prop `isDisabled` is true (canContinue-style guards). Calling the disabled handler does nothing by design.

## Workaround: invoke handlers directly via React fiber

When synthetic events won't register (react-aria press, untrusted events):

```js
// Find the fiber key
const fk = Object.keys(el).find(k => k.includes('Fiber'));      // __reactFiber$xxx
const pk = Object.keys(el).find(k => k.includes('Props'));      // __reactProps$xxx

// Plain onClick: call the props directly
el[pk].onClick({});

// onPress: walk UP the fiber tree to the component that owns it
let fiber = el[fk];
while (fiber) {
  if (fiber.memoizedProps && fiber.memoizedProps.onPress) {
    fiber.memoizedProps.onPress({});   // fires the real handler
    break;
  }
  fiber = fiber.return;
}
```

For buttons where an ancestor carries `onPress` + `isDisabled`, prefer the nearest enabled one; check `fiber.alternate.memoizedProps.isDisabled` — the committed fiber can be stale while the alternate holds fresh props.

## Pitfall: fiber `memoizedState` reads stale values

Reading state through the committed fiber (`fiber.memoizedState`) can show pre-update values even though the update fired. Before concluding "setState failed", read `fiber.alternate.memoizedState` (the in-progress tree) — the updated values live there. Batched updates also land asynchronously: wrap in `setTimeout(..., 100)` inside a console-evaluated Promise before re-reading.

## Pitfall: option-card selections "lost" after navigation

Multi-step wizards that persist drafts via debounced server calls can visually re-render option cards as unselected after advancing, even though state exists. In automation: re-read the enabled/disabled state of the primary CTA (via fiber alternate) before pressing; if disabled, re-invoke the option's `onClick` then press the enabled ancestor fiber.

## Sign-in and form submits: `browser_type` + `browser_click` can silently fail

HeroUI login forms often ignore synthetic `.click()` on the submit button (server-action
forms). If `browser_type` + `browser_click` on Sign in leaves the URL unchanged and no
error appears, escalate in this order:

1. **React-props onClick** on the submit button: `btn[propsKey].onClick({preventDefault(){}, stopPropagation(){}})` — works for plain onClick handlers but often does nothing for `action={serverAction}` forms.
2. **Dispatch a real submit event**: `form.dispatchEvent(new SubmitEvent('submit', {bubbles: true, cancelable: true}))` — this reliably triggers React's form `action` (verified on a client project's HeroUI sign-in + AI-provider settings forms after onClick failed).
3. **Walk the fiber tree from the button** (`__reactFiber$` key, follow `.return`) until `memoizedProps.action` is found, then call `props.action(new FormData(form))` directly — last resort; a direct call with a bare FormData can throw "Invalid input: expected string, received undefined" because the action may need specific state args, so prefer (2).
4. **Verify state, not the handler**: after submitting, confirm via `location.pathname` (in a `setTimeout` promise) and DB (`SELECT ai_provider, ... FROM users WHERE email=...`) rather than trusting a click "succeeded". React server-action responses don't navigate synchronously.

Also: reading form values via `input.value` works only after setting them with the native
value setter + `input`/`change` event (React controlled inputs ignore plain assignment):
```js
const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
setter.call(inp, 'text'); inp.dispatchEvent(new Event('input', {bubbles: true}));
```
Selects need the same treatment on `HTMLSelectElement.prototype.value` + a `change` event.

## Re-testing a completed flow for an existing account

Flows gated by a "completed" flag (onboarding, setup wizards) redirect away for accounts that already finished. Reset app state via the app's database before re-testing:

```sql
UPDATE users SET onboarding_completed_at = NULL, onboarding_summary = NULL WHERE email = '<test-account>';
```

Keep a dedicated test account + password for this; reuse it across sessions instead of signing up fresh each time.

## Locating a horizontal-overflow culprit: hide subtrees, don't guess

When a page pans sideways at narrow widths, element-rect hunts mislead — a table
inside an `overflow-x:auto` scroller reports a rect beyond its clip, so you chase
components that are fine. In one session that cost several rounds of blaming a
table wrapper (trying `overflow` hidden/clip/max-width/`display:contents` on it) while
the pan distance stayed at exactly 415px, unchanged — **the invariant number was the
signal that the element under suspicion was not the cause.**

Bisect instead of guessing. Hide one top-level branch at a time and measure the
symptom:

```js
const panX = () => { window.scrollTo(99999, 0); const x = Math.round(window.scrollX); window.scrollTo(0, 0); return x; };
const main = document.querySelector('main');
[...main.children].forEach((ch, i) => {
  ch.style.display = 'none';
  const x = panX();
  ch.style.display = '';
  if (x < baseline) console.log('culprit index', i, ch.tagName, ch.className, 'panX ->', x);
});
```

Recurse into the branch that moved the number; two rounds found a single
`<pre>` block. Generalise: **hide, measure, compare, recurse** works for any
geometry symptom (pan, height, z-order occlusion) and needs no selector cleverness.

## Verifying responsive layouts without viewport control

When the browser tool can't resize the viewport, verify responsive CSS numerically:

1. Render at default width, measure real geometry: `el.getBoundingClientRect()` (width, height, x, flex direction of parent).
2. Measure minimum content width for the worst-case narrow viewport: canvas `measureText('Label').width` at the button's font size + horizontal padding + icon width + gap.
3. Compare: at target viewport (e.g. 390px), available width = viewport − page padding − card padding. If min-content ≤ available, the text fits on one line.
4. Confirm computed styles that guarantee it: `white-space: nowrap` on the label, `shrink-0` on inline icons, `flex-col w-full` on stacked CTA containers.
5. Take one desktop-width screenshot to confirm the change didn't regress wide layouts.

## Reading dev-server logs as ground truth

The `next dev` process log tells you what actually ran: server-action invocations appear as `ƒ actionName({...}) in Xms`. Use it to confirm a browser-automation press really reached the backend (e.g. `generateBrandOverview` executed) rather than trusting page state alone.

API responses are visible in the same log as `POST /api/... 200 in 89s` — the response
time doubles as a pipeline-duration check (e.g. WatchTower process-trends legitimately
takes 60–90s: ~60 feed fetches + per-topic Google News searches + 1s delay per trend
insert). Don't conclude "the request hung" before that duration has elapsed.

## Writing probes that don't produce false results

A probe that reports PASS vacuously is worse than no probe — it buys false
confidence. Four ways this bit, all in one session:

1. **Playwright pseudo-classes are invalid inside `page.evaluate`.** The
   JS string is evaluated by the BROWSER, which does not know `:has-text()`,
   `:visible`, etc. — you get
   `SyntaxError: Failed to execute 'querySelector'` and the probe dies
   mid-suite. Inside `evaluate`, use `[...document.querySelectorAll('button')]`
   and filter on `innerText`; keep locator-only syntax outside `evaluate`.
2. **A class containing `/` breaks selectors.** `bg-destructive/5` cannot be
   used in `querySelector` (the slash is not escaped). Use
   `[class*="destructive"]` instead of matching utility classes verbatim.
3. **Never treat an empty result set as success.** `any_errors == []` reads as
   PASS even when the probe collected nothing. Assert the probe SAW DATA first
   (e.g. "at least one tool result was captured this turn") and only then assert
   the property over it. The tell-tale is a detail string that renders empty —
   `[]`, `{}`, `''` — next to a green check. Treat an empty detail as FAIL and
   investigate before trusting the run.
4. **Assert deltas, not totals, on a cumulative DOM.** The transcript keeps every
   previous turn's tool cards and images, so `figures === 0` fails on a correct
   reply that merely followed an earlier one which showed figures. Snapshot the
   count before the action and assert the change. The same applies to tool-card
   counts and message counts.
5. **Assert the EFFECT, not the artifact's presence.** The strongest false-pass of
   this class: a reply rendered a styled, underlined, correctly-coloured link that
   was wired to `onLinkPress={() => false}` — it looked clickable and swallowed
   every tap, and **no `href` existed at all**. Every "is the link present?"
   assertion passed. The test must perform the ACTION (click it, assert a new page
   opened on the expected host, assert the current page did not navigate) — a
   presence check can never distinguish working from decorative. Generalise: for
   any interactive element, ask "does my assertion change if the handler is a
   no-op?" If not, it is testing markup, not behaviour.
   Mutation-test it by reverting the handler to the no-op and watching it fail.
6. **Honesty/fabrication checks on streamed LLM replies must assert the RAW SSE
   stream, not only the DOM** — `innerText` strips markdown, so a fabrication
   the model emitted as `Here's **Name** — a card` reads as clean text in the
   DOM while only the raw stream carries the emphasis; a server-side `replace`
   rewrite event is invisible in the DOM too. Ban the assertion shape, never
   the bare name (an honest "I couldn't find X" legitimately echoes X), and
   strip markdown before any regex over LLM output. Full root-cause chain and
   code in `references/e2e-verification-lessons.md` §14; suite inventory §15.

7. **A probe with no must-FAIL control cannot tell the target is broken from its
   own breakage.** Before trusting any positive result, ask *what would this print
   if the thing were actually broken?* If there is no answer, the check is
   decoration. Two traps of this class, both hit in one session:
   - **A substring match over all requests matches everything.** Deciding whether a
     page *used* a URL parameter by searching every request it made ALWAYS passes,
     because the navigated URL is itself a request. Restrict the match to **data
     traffic** (`/rest/v1/`, `rpc/`) so the signal can actually differ. The same
     check reported a value as used, then unused, on consecutive runs — that
     instability is the tell.
   - **A cross-origin read always throws.** `iframe.contentWindow.location` raises
     `SecurityError` for ANY cross-origin frame, so a refused frame and a
     successfully-embedded one report the **identical** value — the check is wrong
     in *both* directions (mine failed a target that was in fact fine).
   Calibrate instead: run a known-blocked control beside the target
   (`https://www.google.com` sends `X-Frame-Options: SAMEORIGIN`) and require the
   control to FAIL while the target PASSES. Pair it with a second signal that
   genuinely differs — here the frame's rendered SIZE, since an embedded document
   lays out and a refused one collapses (719x852 measured vs a collapsed 0).

8. **An empty parse must be a HARD failure, not an empty assertion list.** A suite
   that derives its cases from source (route tables, enum lists, registry entries)
   reports GREEN when the parse silently returns nothing — the most dangerous state
   a test can be in. Fail loudly before any assertion runs:
   `if not parsed: raise SystemExit("refusing to assert nothing")`.

9. **Enumerate the surface from the source, never from memory.** Testing the pages
   you already thought of is a sample, not an audit: parsing an app's whole router
   out of the code found a crashing page the hand-picked list had missed, and gave
   the coverage count that makes the result defensible — 45 routes: 36 render /
   3 crash / 6 redirect / **0 empty**. Watch `0 empty` in particular: a route that
   paints a blank shell is the failure a status-code check can never see.

10. **Assert the DESTINATION, not that something happened.** Item 5 says perform the
   action; this is the level below it. A click check asserting "a new page opened on
   the expected host, and it was a real route" passed on `/auth` — the sign-in page —
   so a user with a broken link and a user correctly redirected to sign-in were
   **indistinguishable**, all green. Two fixes, and the first is what makes the
   second possible:
   - **Seed the target app's session in the SAME context before clicking**, or the
     navigation can never reach the real page. Close the seeding page afterwards or
     it gets counted as the link's new tab.
   - **Assert coherence between what the user was shown and where they landed.** When
     the element carries **no `href`** (a RN `Pressable` rendered to `<span>` + onClick,
     or any `preventDefault`ed handler), the DOM cannot tell you the target — the
     visible LABEL is the only comparable signal, so map label → expected path and
     assert the landing path matches. **An unmapped label must be a FAIL, not a skip:**
     a newly added destination that nobody mapped would otherwise be free to open the
     wrong page silently.
   Same mutation test as item 5: would this assertion change if the link pointed at the
   wrong page? If not, it is testing that a tab opened, not that the feature works.

11. **Separate REACHABILITY from the assertions derived from it.** A transient
   `net::ERR_NAME_NOT_RESOLVED` on the target host mid-run produced four bogus
   failures ("not a real route", "doesn't match the label") that read as a product
   defect. Retry the navigation, assert reachability as its own check, and when it
   fails report `SKIPPED (target unreachable)` for everything downstream rather than
   manufacturing failures. This is the harness-vs-product rule stated as code — and
   never quietly retry straight to green, which hides a genuine outage.

12. **A note that something is broken is an exclusion that silently costs coverage —
    re-measure it before carrying it forward.** A prior session recorded a page as
    failing in browsers lacking Web Crypto; re-tested by injecting
    `Object.defineProperty(window,'crypto',{value:{getRandomValues:(a)=>a, subtle:undefined}})`
    and rendering every destination — all fine, with and without it. There was no trap.
    Stale negative claims in a test suite or notes file read as decisions later agents
    respect, so they persist until someone measures them.

13. **Moving a UI control restructures its e2e — and converts some assertions into
    wrong-invariant checks.** When the panel toggle moved from the top bar INTO each
    assistant bubble (2026-09-24), the existing panel e2e broke three ways, each
    needing a different treatment: (a) the flow clicked the toggle before any reply
    existed — impossible now, so the flow asks a question first (restructure);
    (b) `toggle.click()` on a re-located locator that was previously count==1 needed
    `.last` once multiple bubbles carry the button; (c) the "empty panel explains
    what will fill it" check now NEVER fires in that flow — not because the empty
    state broke, but because opening after a tool-backed reply means the panel
    follows a page from birth. (c) is the important one: replace the stale assertion
    with the STRONGER one the new design implies ("the opened panel already follows
    the reply's page") and leave a comment saying the old check became unreachable
    by design, so a future reader does not "restore" it. A missing step can also be
    introduced BY the restructure — my first patch dropped the toggle click in a
    later section entirely, which would have made `frame_src` return null; diff the
    flow end-to-end after moving anything, not just the failing lines.

14. **A new prop on memoized rows must be referentially stable or the memo is
    theatre.** The transcript re-renders once per animation frame while streaming;
    a row-level `memo` only saves the markdown re-parse if every prop is stable.
    Passing an inline arrow (`onTogglePanel={() => ...}`) silently defeats it —
    60 re-parses/second per bubble. Pass a `useCallback`-stable callback; if it
    needs a value that changes (viewport width), read it through a ref
    (`widthRef.current`) instead of closing over it, so the dependency array stays
    empty. This is the same class as the existing "streaming flag must be
    referentially stable" invariant in MessageList's header comment.

15. **When a vision check on your screenshot contradicts a passing e2e, suspect the
    screenshot's SELECTOR first.** The panel e2e asserted the Split View button
    rendered and read "Split View" — while a vision analysis of my "assistant
    bubble" screenshot reported no button anywhere. The e2e was right: my
    screenshot grabbed `.last` of a structural guess (`assistant-message`) which
    had caught a tool card mid-run, not the reply bubble. Key the capture on the
    feature's own testID (screenshot the locator that the e2e itself clicks), and
    re-run before concluding the feature is flaky. A screenshot of the wrong
    element produces a confident, detailed, entirely wrong verification.

Related, when a probe must read app state after an async action: the state you
read in a callback after `await` is stale by definition — snapshot before, act,
re-read, compare.

## Assert interaction states GEOMETRICALLY, not visually

A 2–3px layout shift on hover is invisible in a screenshot and reads as "seamless"
to the eye, so a vision check passes while the user watches text jump under their
cursor. Measure idle vs hovered rects and assert the DELTA:

```python
GEOM = """() => {
  const rows = [...document.querySelectorAll('nav > div')];
  return rows.map(el => {
    const b = el.getBoundingClientRect();
    const t = el.querySelector('button[title]');
    const tb = t ? t.getBoundingClientRect() : null;
    return { h: +b.height.toFixed(2), titleTop: tb ? +tb.top.toFixed(2) : null,
             titleW: tb ? +tb.width.toFixed(2) : null };
  });
}"""
idle = await page.evaluate(GEOM)
await page.locator("nav > div").first.hover()
await page.wait_for_timeout(800)          # let transitions settle
hovered = await page.evaluate(GEOM)
# fail if max |Δh|, |ΔtitleTop| or |ΔtitleW| >= 0.5px
```

Measure height AND the inner content's y/width — a hover can move the text without
changing the row's height, and can steal width so the label re-truncates. Root cause
(`hidden group-hover:block` reflows the flex container), the absolute+reserve+
opacity-only fix, and before/after numbers: `references/interaction-state-geometry.md`.

## Third-party UI libraries: verify THEIR geometry, don't trust it

A library's own sub-elements can be systematically misplaced, and the fix is usually
to stop using that sub-element rather than to fight it. Three findings, all measured
(2026-09-21, chart hover indicator reported "off-center" from a screenshot):

- **A displacement that equals a prop 1:1 is a DOUBLE-COUNT.** The hover crosshair
  sat exactly `initialSpacing` px right of the point it reported (+35.3px at 35,
  +0.3px at 0) because the library insets its pointer container by that value *and*
  adds it inside `pointerX`. Find the constant equal to the error and vary it; the
  fix is setting it to zero, never compensating with an offset.
- **An element's bounding box LIES about clipping.** A library that wraps each axis
  label in a fixed ~310px box makes every label look clipped by `getBoundingClientRect()`.
  Measure the text's own rect via a DOM `Range`, intersected with every
  `overflow`-clipping ancestor, and assert `clippedPx == 0`. That caught 15.9px of
  real clipping (half a 31.7px label) that the box measure missed.
- **When the obvious knob moves the clip boundary together with the content, stop
  tuning and render that sub-element yourself.** Measured at four y-axis widths, the
  clip edge and the first data point moved in lockstep (44→45, 60→61, 80→81,
  100→101), so the relative error never changed — and the prop that *would* buy the
  room re-broke the pointer. Set the library's labels off and draw the row outside
  the clipped container.
- **Attribute an artifact with `elementFromPoint` + an ancestor-walk before editing
  anything.** A ⚡ and ◈ by the chart's edge were the app's product rail showing
  through a translucent glass card — pre-existing, proved by running the same probe
  against the untouched deployed build. Report it separately; don't widen the fix.

Full techniques — the throwaway variant-lab pattern (and its auth-bypass + SPA-
fallback server + restart-after-change traps), the pixel-ink confirmation of a DOM
clip claim, and the press-read-release helper that keeps a held-down-only overlay
from passing vacuously: `references/library-internal-geometry.md`.

**Ready-to-run probes (don't hand-write these again):**

- `references/layout-verification-harness.md` — the copy-and-adapt numeric layout
  harness from the fixed-overlay-to-grid-column work: one shared snapshot fn across
  open/closed states, the assertions that caught each real bug (reserved-track
  equality, spacing parity vs closed, `columnGap` computed-vs-source, viewport gate
  both directions), the Playwright/ESM + `NODE_PATH` setup, three failure signatures,
  and how to measure a supplied design mock for exact CSS values.

- `scripts/overlay_alignment_probe.py` — presses each data point and reports the
  signed overlay offset while held down, failing on an empty read and flagging a
  CONSTANT offset as a likely double-count. Takes `--root` + `--ask`.
- `scripts/embeddability_probe.py` — answers "can this URL be iframed?" the only way
  that works: loads it in a real browser with a **must-block control**
  (`google.com` sends `X-Frame-Options: SAMEORIGIN`) and a **must-load control**
  (`example.com`), then verdicts on console refusals per-origin plus the frame's
  rendered SIZE. Never use `contentWindow.location` — cross-origin reads always
  throw `SecurityError`, so refused and embedded are indistinguishable. Run this
  BEFORE designing any embedded-panel feature: a target carrying
  `frame-ancestors 'none'` in a `<meta>` CSP is still embeddable, because browsers
  ignore the directive there.
- `scripts/spa_fallback_server.py` — serves a client-routed export so deep routes
  resolve; the restart caveat is in its docstring.

### Seeding app state: write storage directly, don't drive the UI

To put an app into a state that requires N prior user actions (a populated Recent
list, onboarding complete), write the persistence key directly then reload:

```python
convs = [{"id": f"s{i}", "title": t,
          "messages": [{"role": "user", "content": t}, {"role": "assistant", "content": "Seeded."}],
          "updatedAt": 1789700000000 + i} for i, t in enumerate(titles)]
await page.evaluate("() => localStorage.setItem('ama_conversations', %s)" % json.dumps(json.dumps(convs)))
await page.reload(wait_until="domcontentloaded")
```

UI-driven seeding fails in apps with a page-level click-outside handler (`onClick`
on the main column) that swallows clicks aimed at a sidebar — Playwright retries for
30s and dies with "intercepts pointer events", which reads like a broken selector.
Find the persistence key first (`grep -n localStorage src/components/...`).

**After seeding, `page.reload()` — a second `goto()` to the same URL does NOT remount.**
This is a false-pass generator of exactly the class above. The sequence
`goto('#/desk')` → seed the staff token → `goto('#/desk')` looks like a reload, but
only the fragment changed, so nothing re-fires: the app never re-reads the storage and
the table stays empty. Measured signature in the request log:

```
REQ  GET /api/codes staff=-        <- first mount, no token yet
RESP /api/codes -> 401
--- setting localStorage ---
--- reloading ---                   <- second goto(): NO REQUEST AT ALL
headers: []                         <- zero columns; looks like a UI bug
```

With `page.reload()` the same script gives `staff=d1b0ee → 200` and
`headers: ["CODE","GUEST","BADGE QR","ITEM","CLOSED AT","HANDED OVER"]`.

**A zero-request read is the tell, and the fix is to assert the DATA, never the container.**
Two habits make this self-diagnosing:

1. **Log every `/api/` request with its auth header** while developing the probe
   (`p.on('request', r => … r.headers()['x-staff-token'])`). A request that never fires is
   indistinguishable from one that fired and returned nothing, unless you can see the log —
   and "no request at all" is a *different diagnosis* (storage not re-read) from "request
   returned empty" (server-side filter). Without the log you chase the wrong layer.
2. **Assert a cell that only renders when the authenticated fetch succeeded**, e.g.
   `rows.some(r => r[1] === "the user")` — not `headers.includes("GUEST")`. A static header
   can render from the bundle while every data fetch 401s, so the header assertion passes on
   a totally broken page. This is the same contract as item 5 above: ask "would this
   assertion change if the fetch never happened?"
3. Keep the **console-error assertion** (`console errors: 0`) — the failing fetch surfaces
   as `Failed to load resource: 401`, which is the cheap backstop when a probe forgets (1).

### Invisible is not inert

`opacity-0` still has a hit target — a faded-out control stays clickable and
focusable. Pair it with `pointer-events-none` (restored on hover/focus) so the
interactive surface matches the visual one. Verify by enumerating the controls and
reading computed `opacity` + `pointerEvents` per element; a screenshot can't tell
"absent by design" from "present but transparent". Beware duplicate
`title="Delete"` buttons (desktop + mobile swipe-reveal): a bare selector matches
the `pointer-events-none` one and the click dies with a generic `TimeoutError`.

## Making text selectable inside a clickable element

"Let the user copy this label, but keep the click working" looks like a CSS job
and is not. Three browser behaviours stack, and only the third one actually bites
(AMA landing hero, 2026-09-16; full diagnosis recipe in
`references/selectable-vs-clickable.md`):

1. **A native `<button>` cannot have its text drag-selected — at all**, whatever
   `user-select` says. Chromium refuses selection inside button elements, so
   `select-text` on a `<button>` is a no-op. The label must live in a focusable
   `role="button"` div (`tabIndex={0}` + Enter/Space `onKeyDown` to keep keyboard
   activation) for the text to become selectable.
2. **Dragging inside a clickable element still fires `click` at mouseup.** So the
   gesture that SELECTS the label also ACTIVATES it — the user tries to copy and
   the action fires instead. Fix: track pointer-down coords and treat travel past
   a small threshold (~4px) as a drag, returning early from `onClick`.
3. **Guarding on `window.getSelection()` is NOT reliable — do not ship it.** A
   drag that starts on the element's *padding* forms no selection yet still fires
   `click`, so a selection-based guard intermittently sends when the user meant to
   copy. This passed a first round of testing and only failed when a big single-step
   drag was tried. Discriminate on pointer travel, not on selection state.

### Prove which layer is at fault with a synthetic probe

Before blaming your CSS, inject two identical elements with a known `user-select`
into the live page and run the SAME drag on each:

```python
# span with user-select:text  -> selected 24 chars
# BUTTON with user-select:text -> selected 0
# div with user-select:none   -> selected 0   (control)
```

If the synthetic span selects and the synthetic button does not, the refusal is
Chromium's, not your code. Also confirm ancestors aren't the cause by appending a
`user-select:text` span INSIDE the suspect `select-none` parent — an ancestor
`user-select:none` does NOT block a descendant that opts back in.

### Instrument the event order — that's what names the real culprit

Attach capture-phase listeners plus a `MutationObserver`, run the drag, then read
the log. The sequence is self-explanatory once you have it:

```
EV:selectstart t=5583      <- selection DID start
EV:click       t=6391      <- drag ends, click fires
CARD_REMOVED   t=6403      <- the click sent, the view swap killed the selection
selection length: 0
```

Without the log this reads as "the text is unselectable, CSS must be wrong" and
sends you chasing `user-select` for a round trip that cannot fix it.

### Assert the contract, including the case that breaks the guard

Both halves, or the test is worthless — the regression test must cover the
padding-drag (no selection formed, still must not fire) alongside the
text-drag (selects, must not fire):

- chrome/decorative regions: drag selects nothing
- label: drag selects it AND does not activate
- label padding: drag does not activate (the case a `getSelection()` guard fails)
- clean click: still activates
- keyboard Enter: still activates
- unrelated text (e.g. a chat reply): still selectable — sweep at the text's own
  y, not the container's top edge, or padding makes it a false FAIL

Decorative images also want `draggable={false}` + `pointer-events-none`; without
it a drag picks the image up as a dragged element and highlights surrounding text.

## An unauthenticated `curl` is NOT proof a route serves the right content

The highest-value false-negative of this class: **a route can serve entirely the
wrong page while every unauthenticated check still passes.** An authed Next.js app
had `src/app/page.tsx` left as the untouched `create-next-app` scaffold for the
app's whole life, so a SIGNED-IN visitor to `/` got "Get started by editing
src/app/page.tsx" instead of the app. It survived because:

1. **Middleware redirected anonymous traffic to `/login` BEFORE the page rendered.**
   `curl -I https://host/` returned `307 -> /login` and looked perfectly healthy.
   The redirect is evaluated before the root page component ever runs, so the
   broken page is unreachable anonymously. Only an AUTHENTICATED request exposes it.
2. **The E2E suite loaded only `/login` and `/chat`** — never the bare root, which
   is exactly the URL a user types.

Rules that follow:

- Assert the **bare root** (`/`) inside the authenticated session, not only the
  deep routes you develop against. The root is the URL users actually type.
- Assert **both** auth states for it: anonymous `/` redirects to login, AND
  authenticated `/` lands on the real app — plus a **negative assertion that the
  scaffold/boilerplate string is absent** (`/Get started by editing|Deploy now/`).
  A "did it land somewhere?" check passes on the scaffold too.
- Treat a 200/307 from an unauthenticated `curl` as evidence about *routing only*,
  never about *content*. Load it in a real browser with a session.
- Generalise: any generator template/scaffold file left behind is a candidate for
  this bug class — diff the initial commit's untouched defaults against what the
  app should serve.

## New chrome must not eat the layout it overlaps

Adding a floating rail/toolbar/fab to an existing column: as a flex sibling it
silently steals height from the content. An icon rail added as a flex child with
`shrink-0` consumed ~110px, so the transcript and composer were no longer full
height — the user reported it instantly as "the chat isn't full height".

Make overlay chrome `position:absolute` (anchored to an already-`relative`
ancestor), and pair `pointer-events-none` on the container with
`pointer-events-auto` on the interactive children so the space behind the overlay
stays clickable. Anchor it with arithmetic off the existing layout rather than a
guess — e.g. `top-[72px]` = `pt-4` + the 48px button above ending at y=64, and
48px children to land on that button's exact centre axis. Assert numerically at
every target viewport:

```python
colTop == 0 and round(vh - col.getBoundingClientRect().bottom) <= 1
colH >= viewportH                      # the overlay subtracted nothing
getComputedStyle(rail).position == "absolute"
```

**A user report accompanied by a screenshot is a request for a MEASURED fix.** The
durable guard is the number (height, `position`, delta), never a replacement
screenshot — a screenshot cannot distinguish a 110px squeeze from a 2.75px shift,
and both arrived as screenshots in one session.

### A fixed overlay must clear the sticky header it overlaps

`position: fixed` + a high `z-index` does NOT put you above a `position: sticky`
header. An app header at `z-index: 100` beats a panel at `50`, so a full-height
drawer anchored at `top: 0` renders **underneath** the nav bar — its own title,
status label and close button simply vanish. It gets reported as "the panel is
hidden behind the top menu": a stacking + geometry bug, not a styling one.

Three-part fix, all numeric (worked example: a compliance drawer, 2026-09-22):

1. **Name the header's footprint as a token instead of hard-coding an offset.**
   Measure it — a `52px min-height` header measured `53.14px` (`min-height` + its
   1px bottom border) — and expose e.g. `--app-header-h: 54px` in `:root`.
2. **Offset the panel AND re-scope its height, or it overflows the bottom by
   exactly the offset:** `top: var(--app-header-h); height: calc(100vh - var(--app-header-h))`.
3. **Re-centre every element positioned relative to the one you moved.** A sibling
   toggle centred on `top: 50%` of the *viewport* was flush with the panel's centre
   only while the panel started at `top: 0`; after the panel shifted down 54px the
   toggle sat 27px above the panel's centre. Its fix was
   `top: calc(50% + (var(--app-header-h) / 2))`. Before shipping an offset, ask
   "what else is anchored to this element?" — that second bug is invisible in the
   screenshot that prompted the first.

Assert both, in the authenticated page:

```js
const d = document.querySelector('.compliance-drawer');
const h = document.querySelector('.app-header');
const t = document.querySelector('.compliance-drawer-toggle');
d.getBoundingClientRect().top             // 54    -> must be >= header bottom
h.getBoundingClientRect().bottom          // 53.14 -> header bottom
d.getBoundingClientRect().bottom          // == window.innerHeight (no gap at the bottom)
t.getBoundingClientRect().top + 10        // == drawer centre  (toggle still flush)
```

**A dev server's unminified source is a cheap proof your edit is live.** Vite
serves `src/styles.css` verbatim, so `curl -s :5173/src/styles.css | grep -c
'--app-header-h'` returning `1` confirms the running process has the patched file —
the same "is the server serving my build?" discipline that otherwise burns a whole
verification round. Vite also hot-reloads CSS without a restart, unlike the
config-serving cases above.

**A content-hashed bundle filename is cryptographic proof your build shipped.**
The strongest deploy check available for a Vite/webpack build: compare the hash the
server serves against the hash you just built locally.

```bash
ls packages/review-ui/dist/assets/*.css                                  # local build
curl -sk https://host/ | grep -oE '/assets/index-[A-Za-z0-9_-]+\.css'    # served
```

Equal hashes = the exact artefact is live. This beats grepping for a change-specific
string, which a stale bundle can still satisfy. Then grep the served file for a token
unique to your edit as a second check — and **assert removals with a count of 0**
(`grep -c 'old-class'` → `0` proves the deletion shipped, not just that the addition did).

**Read your sync tool's dry-run diff before applying it.** For an `rsync` deploy,
`-n --itemize-changes` should list exactly the files you edited plus `.d..t......`
directory timestamps — nothing else. A `*deleting` line, or an unrelated artefact
(a `__pycache__`/`.pytest_cache` file), means a flag is wrong; add the exclusion and
re-run the dry run. Ten seconds here beats discovering your typo on a host you were
told not to disturb.

**A shared host's container count is not a failure signal.** If you use
`docker ps | grep -vc <yourproject>` as an "estate unchanged" check, remember other
people deploy to the same host. When the number moves, attribute it before reacting:
`docker inspect <new> --format '{{index .Config.Labels "com.docker.compose.project.config_files"}} | {{.State.StartedAt}}'`
names the owning compose file and start time. A container owned by *another* compose
project that started before your deploy is not yours — report it as such and do not
restart or restore anything. Prefer listing the non-yours names over trusting a
remembered integer, which is only valid until the next teammate ships.

**State the break rather than hiding it.** The token assumes a single-row header;
below 900px the header wraps and grows taller, so the offset under-clears there.
Write the assumption into the CSS comment and into the report — a silently shipped
narrow-viewport break is worse than a flagged one.

### Rotated labels in a fixed edge tab

Turning a cryptic icon-only tab into a labelled one (same drawer, 2026-09-22)
has three traps that only surface once measured:

1. **`writing-mode: vertical-rl` reads TOP-to-BOTTOM by default.** Add
   `transform: rotate(180deg)` to flip it to bottom-to-top. Both go on a
   dedicated `<span>` — put `writing-mode` on the button itself and the chevron
   rotates with the label.
   **Do not assume the "conventional" orientation — and say which one you shipped.**
   This guidance originally called bottom-to-top conventional; the user then asked
   for "the opposite orientation", i.e. top-to-bottom, which is just the bare
   `writing-mode: vertical-rl` with the rotate removed. When a label's direction is
   a judgement call, state the choice in your reply so a one-line flip is cheap,
   and expect to be asked for the other one. The flip is a single declaration either
   way: with it = bottom-to-top, without it = top-to-bottom.
   Removing a companion element (the user also asked to drop the chevron) means
   dropping the `<span>`, its CSS rule, **and** the `flex-direction: column` + `gap`
   that existed only to stack it — leave those and the label sits off-centre.
2. **A fixed `height` clips rotated text.** The old control carried
   `width: 20px; height: 20px`; it had to become `width: 30px; min-height: 44px;
   height: auto`, plus `flex-direction: column` + a gap to stack chevron under
   label — a 30px column has no room for them side-by-side. Keep the chevron
   `aria-hidden` and leave the state in the button's `aria-label`.
3. **The label's advance width becomes your HEIGHT budget.** "Policy Checker"
   is 14 chars; at 16px it needs ~106px of line height, so the tab rendered
   149px tall. Do that arithmetic before choosing a font size, not after.

**Assert a rotation numerically — computed `transform` never says "180deg":** it
reports the matrix, so `matrix(-1, 0, 0, -1, 0, 0)` IS the assertion for a flip,
paired with the writing mode and the label's own extent:

```js
const lab = t.querySelector('.compliance-drawer-toggle-label');
getComputedStyle(lab).writingMode    // 'vertical-rl'
getComputedStyle(lab).transform      // 'matrix(-1, 0, 0, -1, 0, 0)'  <- the flip
lab.getBoundingClientRect().height   // 106.1  <- the label's extent
t.getBoundingClientRect()            // 30 x 149 <- the tab
```

**Resizing a control re-opens every coupling the previous fix established.** The
new 30x149px tab had to be re-proved flush against the open panel (tab right edge
`852 == 852` drawer left) and still vertically centred on it (`315.5 == 315.5`).
The earlier `top: calc(50% + (var(--app-header-h) / 2))` survived — but only
because the panel's own width and the toggle's height-driven centring were
untouched. Re-run both numbers after ANY footprint change; a size edit can
silently re-break a position fix that was size-dependent.

**Reading a user's pixel spec:** a figure stated as a floor ("at least 30px wide")
is the value to use. A stated range ("14-16px, or whatever fits") means pick inside
it and say why. Where the range fights the height budget, honour the explicit
number and document the assumption in the CSS comment rather than quietly
shrinking — 16px shipped, with the ~630px minimum viewport recorded alongside it.

## Turning a fixed overlay into a real layout column

A `position: fixed` panel that overlays content is often fine until the user asks
for the layout to *reflow* around it — "make it a third column", "no padding on the
left", "the content should shrink, not be covered". Worked example: a 420px
compliance drawer became column 3 of the IO review page (2026-09-22).

**The pattern that works: let the grid reserve the column, keep the panel fixed.**

```css
.pane:has(.drawer-open) {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) var(--drawer-w);
  gap: 0 var(--sp-8);          /* row gap 0; the gutter lives in the column gap */
  grid-template-rows: auto auto;
  align-content: start;
  max-width: none;             /* drop the centred max-width */
  margin: 0;
  /* ONLY the right padding may go. Zeroing the whole shorthand also removes the
     TOP inset, so the content sits flush under the nav bar while open but inset
     while closed. See trap 4. */
  padding: var(--sp-5) 0 var(--sp-5) var(--sp-5);
}
.pane:has(.drawer-open) > .header,
.pane:has(.drawer-open) > .content { grid-column: 1 / 3; }

/* The drawer keeps position: fixed — that is what makes it full-height without
   participating in track sizing. The explicit 3rd track reserves the space. */
.pane:has(.drawer-open) .drawer {
  border-left: none; border-radius: 0; box-shadow: none;
}
```

This lands only because the pane's right edge **is** the viewport's right edge
(no right padding, `max-width: none`), so column 3's rectangle and the fixed
panel's rectangle coincide exactly. Derive every width from one token
(`--drawer-w`) so the column and the panel cannot drift apart.

### Four traps, all caught by measuring

1. **A grid item that SPANS rows forces auto tracks to stretch to its height.**
   Making the drawer `grid-row: 1 / -1` (to reach the viewport bottom) pushed the
   content tracks down with it, opening **206px of dead space** between the review
   cards and the next row. The cards couldn't fill it — they clamp themselves with
   their own `max-height: calc(100vh - 280px)`. My first fix left a **41px
   regression** vs the closed state before the real cause landed. **Keep the
   overlay `fixed` and let the explicit track reserve the column**; don't make it a
   spanning grid item.

2. **`column-gap` takes ONE length — the two-value `gap` shorthand is INVALID
   there and silently drops.** `column-gap: 0 var(--sp-8)` produced *zero* gutter,
   so the cards touched the panel, and nothing errored. Use `gap: 0 var(--sp-8)`
   when you want shorthand semantics. **Verify the computed value, never the
   source:** `getComputedStyle(pane).columnGap` reported `normal` — an invalid
   declaration reads as absent, not as an error.

3. **Flipping `.pane` from `container` (centred + padded) to a full-bleed grid
   changes which ancestors a `:has()` rule needs.** `column-gap`/padding rules
   that looked right kept resolving against the old box model until the pane itself
   was switched.

4. **Zeroing the padding shorthand when only the RIGHT padding must go silently
   removes the top inset too.** `padding: 0 0 0 var(--sp-5)` looks like "keep left,
   drop right", but it also drops top and bottom. The user sees it immediately as
   the content sitting flush under the nav bar while the panel is open, while it
   has a normal inset when closed. Write the sides you intend to keep explicitly:
   `padding: var(--sp-5) 0 var(--sp-5) var(--sp-5)`. **Assert the inset is
   IDENTICAL open vs closed**, not merely "20px when open" — that comparison is
   what catches it:
   ```js
   (open.header.top - open.pane.top) === (closed.header.top - closed.pane.top)  // 20 === 20
   ```
   This is the same discipline as the spacing-parity check below: the closed state
   is the baseline, and every open-state assertion can pass while the open state has
   quietly regressed against it.

### Prove it numerically — and probe the CLOSED state as the baseline

The strongest assertion isn't "is there a third column?" but **"did anything
regress vs closed?"**. Measure the same spacing in both states and diff:

```js
// open vs closed, same probe
gapCardsToValidation: bottomGrid.top - split.bottom
```

Assert `open.gap === closed.gap` (16px == 16px here). That single comparison caught
the 41px regression that every open-state assertion passed. Also assert the drawer
geometry equals the reserved track rather than trusting `position`:

```js
drawer.left === pane.right - 420        // 977 == 1397-420  (col3 == panel rect)
split.right <= drawer.left              // no overlap; gap 32 == --sp-8
pane.paddingLeft === '20px' && pane.paddingRight === '0px'
validation.width === split.width        // a full-width row spans cols 1/3
getComputedStyle(toggle).display === 'none'   // open-state-only element hidden
```

**"Full height" and "full width" need explicit assertions.** A `grid-template-rows:
auto auto; align-content: start` grid gives natural content height — correct here,
but it means the drawer must supply its own `100vh` sizing, and the *closed* state
must be measured to know whether a gap is a bug or the normal margin.

## Desktop-only gates: render the notice, then stop rendering the app

When told "show a message below Npx, for all screens", the gate must cover the
LOGIN screen too, not just the authed routes inside the router. Put the check in
the top-level component and return early:

```jsx
function useIsNarrowViewport() {
  const [narrow, setNarrow] = useState(null);      // null until measured
  useEffect(() => {
    const mq = window.matchMedia(`(max-width: ${MIN - 1}px)`);
    const sync = () => setNarrow(mq.matches);
    sync();
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);
  return narrow === true;
}

export default function App() {
  const narrowViewport = useIsNarrowViewport();
  if (narrowViewport) return <DesktopOnly />;   // before auth, before the router
  ...
}
```

**Pitfall that cost a live debug round:** after extracting the hook, the presentational
`DesktopOnly` component was left rendering unconditionally — it became a
`position: fixed; inset: 0` overlay covering every screen at every width. Playwright
reported it precisely as `<div role="alert" class="desktop-only"> intercepts pointer
events` on an unrelated click, which reads like a bad selector. Keep the guard inside
the component that renders the overlay (`const narrow = useIsNarrowViewport(); if
(!narrow) return null;`) so it can never render unconditionally, and use `null` as
the initial state so wide screens never flash the notice before the MQ is evaluated.

Pick the threshold from the stylesheet's own narrowest breakpoint, not a round number
— 900px here, because below it the nav wraps and the review columns stack anyway.

## Assertions can be wrong about intent — check before "fixing" the code

A probe asserting `drawer.position === 'static'` failed after the final (correct)
implementation, which deliberately kept `position: fixed` and reserved the column
via the grid track instead. The assertion encoded an implementation choice, not the
requirement. When an assertion fails, first ask whether it is testing the **effect**
the user asked for ("does the panel occupy column 3, beside the content, without
overlap?") or a mechanism you happened to pick. Rewrite the probe to the geometric
truth — `drawer.left === pane.right - 420` — rather than changing working code to
satisfy a stale probe.

## Reusing an existing component beats restyling a copy

Asked to "copy the styles from panel A into panel B", the durable move was to render
the **same component** (`<ProjectPanel>`) inside B's body rather than duplicate its
markup or CSS. Restyling a copy creates two sources of truth for one dataset and they
drift. Prefer, in order: move the component → pass it in as a `panel` prop → extract a
shared component. Only restyle genuinely bespoke markup, and when you do, delete the
now-dead CSS and the props/memos that fed it (measured with
`grep -rn "<class>" --include=*.jsx .` returning empty) rather than leaving orphans.



A locally-launched dev/prod server started as a tracked background process dies
when the spawning shell's process group is reaped — typically partway through an
E2E batch, presenting as `net::ERR_CONNECTION_REFUSED` that looks like an app
regression. Launch it detached into its own session
(`subprocess.Popen(..., start_new_session=True, stdin=DEVNULL)`) and poll the
health endpoint before the batch. Even then it can die under sustained load
(~once per 5-10 chat turns); always curl health first, and when a batch fails
mid-run check the server BEFORE debugging the app.

### A long-running server does not see edits to its own config — restart it

Editing a RUNNING server's config (served directory, port, fallback rules) with a
`sed`/write changes the file on disk, not the process. The old config keeps serving.
A whole measurement round was spent validating the PREVIOUS build because the file
server still pointed at the old export directory — and the result was the worst
kind: the new assertion appeared **not** to catch the bug it was written for, which
argues for deleting a good test.

The safe sequence when the served artefact changes:

1. rebuild/export into the new directory
2. **kill** the server process (not just edit its config)
3. relaunch with the new directory
4. **confirm the served build changed** before trusting any measurement — curl a
   route, or grep the served response for a string unique to your change

Same rule as the app-server case above (`next start` serving a stale `.next`).
Whenever a verification run says "the fix had no effect", suspect the server
before the fix.

### Serving a static SPA export

A client-routed export (Expo/Next/Vite) writes one `index.html` and resolves
deep routes in the browser — `python3 -m http.server` returns 404 for them and the
route "doesn't exist". Use `scripts/spa_fallback_server.py` (rewrites unknown paths
to `/index.html`, restart caveat baked into its docstring).

**A 200 from a fallback server proves NOTHING about a route.** Every path returns
200 and an empty shell. Never decide a route works from its status code — load it
and assert the destination rendered (see the deep-link section of
`ai-chat-data-apps`, which found three decoy routes behind HTTP 200 this way).

## The browser you test in can be the reason you miss the bug

**Match your verification browser to the user's error text.** A page rendered
perfectly in Chromium and crashed in **Firefox** — same URL, same session:

- the page subscribed to a realtime WebSocket on mount;
- the app's CSP (delivered via `<meta>`) did not allow that origin in `connect-src`;
- **Firefox threw the blocked connection into the page's React `ErrorBoundary`;
  Chromium logged the same refusal as a console *warning* and carried on.**

So the user saw "Dashboard Error" and every check I had run called the page healthy:
`curl` 200 (SPA fallback), the route present in the router, and a green Chromium E2E.
Three independent green signals, all blind to the same thing.

Rules:

1. **When the user quotes an error message, treat the wording as a fingerprint —
   a HINT, not proof.** "The operation is insecure" / `NS_ERROR_CONTENT_BLOCKED` is
   Firefox **131**'s phrasing for a security exception. Later builds of the SAME bug
   show the boundary's own generic fallback ("An unexpected error occurred"), because
   the ErrorBoundary catches the throw and prints its own text. So a wording mismatch
   does **not** mean you are looking at a different bug — do not abandon a correct
   line of investigation on the strength of it. What survives across versions is the
   **console** output, so capture and assert on that.
2. **Pin the engine in the verification script and say WHY in the file header.**
   `e2e/verify_deep_links.py` opens with the root cause and the words "runs in
   FIREFOX on purpose" so a later agent does not "simplify" it back to Chromium and
   silently re-break the check.
3. **Re-audit the whole surface in the browser that fails, not just the one URL.**
   The crash was per-page, not site-wide: `/dashboard/ads` crashed while
   `/dashboard/ads/<id>`, `/campaigns`, `/reporting` and the library were fine.
   Sweep every link/route and record which are broken.
4. **Assert the negative too.** The suite also asserts the broken pages are
   *still* broken — so an upstream fix surfaces as a failed expectation you
   investigate, rather than an unnoticed improvement you never adopt.
5. **A blocked realtime WebSocket is the shape to suspect** whenever an SPA page dies
   in one engine only: check `connect-src` for the `wss://` origin, and remember that
   `frame-ancestors`/`connect-src` delivered in a `<meta>` CSP are governed by
   different rules than the same directives in a response HEADER.

### Extracting a real error from a React `ErrorBoundary`

The boundary renders a generic fallback and logs the real object, so the on-screen
text is a dead end. Two traps that make the obvious probe useless:

- **A `DOMException` serialises to `{}`** via `JSON.stringify` (its `name`/`message`
  are on the prototype) and is **not `instanceof Error` in every browser**. Read
  `x.name` / `x.message` explicitly or you log an empty object and conclude "no
  error".
- **Hook before the app's own scripts run** — `page.add_init_script(...)`. A hook
  installed after load misses the throw.

```python
await page.add_init_script("""
(() => {
  window.__errs = [];
  const orig = console.error;                      // ErrorBoundary calls console.error
  console.error = function(...a) {
    window.__errs.push(a.map(x => {
      if (x && typeof x === 'object' && (x.name || x.message))
        return 'NAME=' + x.name + ' MSG=' + x.message;
      try { return JSON.stringify(x).slice(0,200); } catch(e) { return String(x); }
    }).join(' || '));
    return orig.apply(console, a);
  };
})();
""")
page.on("pageerror", lambda e: logs.append(str(e)))
# → NAME=NS_ERROR_CONTENT_BLOCKED  STACK=connect@.../supabase-*.js
```

The `NAME=` line named both the fault (a blocked connection) and its site (the
realtime client's `connect`), which is what turned "the dashboard is broken" into a
one-line root cause.

## E2E verification discipline + session-derived gotchas

AMA-specific detail for the bare-root bug, the rail height regression, brand-mark
sourcing, sidebar row metrics, and the full 83-assertion suite map:
`references/ama-verification-and-layout.md`.

### When asked to find "the logo for X in the repo", search until you can state the negative

"Find the logos for both X and Y" has three possible answers and they need
different handling — determine *which* before building anything:

1. **A real asset exists** → use it verbatim (copy the exact path/viewBox/fill
   from the source, don't redraw a lookalike).
2. **Only an inline SVG exists** (very common on static marketing sites) → that IS
   the source of record. Extract the `d`/`fill` from the page HTML.
3. **No identity exists at all** (the product is a concept, not a shipped thing) →
   ship an **original placeholder and label it as one in the UI** (`title`/
   `aria-label` naming it a placeholder). Never silently invent brand artwork and
   let it pass as real.

Sweep order that actually settles it: live marketing pages (`/x/` vs a 404 is
strong evidence), the marketing-site repo's HTML (not `public/` asset globs —
these marks are often inline), git history for deleted assets, the design-system
repo, product docs, and the project tracker. Then **state the negative explicitly**
("no /signal page, no repo, no asset, never a product name") — that is the
finding, and it is what lets the user supply the real artwork.

See `references/e2e-verification-lessons.md` for the rest — including the
booth-loop pattern (decode QRs from pixels, drive the real UI, spy the minting
endpoint for zero calls), false-pass hygiene (page-wide `includes()` vs a ledger
table that lists everything), click-toggle loops on `aria-expanded` cards,
console-error whitelists (URL lives in `m.location()`, not the text), and
vision-checking screenshots for copy drift assertions miss. Highlights:

- **the user's rule:** test E2E with a real login and the core user action before
  claiming any feature complete — unit tests + green build are not completion.
- `crypto.randomUUID` missing over plain HTTP (tailnet/LAN hosts) — use a `uuid()`
  helper with fallbacks in all client components.
- Multi-provider LLM pickers: the client must send its actual selection, and the
  server default must follow the first provider with a configured key — else the UI
  shows one model while a keyless default runs (surfaced as confusing
  `OPENAI_API_KEY` errors when the user picked Anthropic).
- Middleware ordering: public-path check must precede the API-401 check, or
  self-authenticating API routes (MCP Bearer endpoints) get 401'd by cookie
  middleware. Verify against the built middleware bundle, not just source, and
  restart `next start` — a stale process serves the pre-fix bundle.
- Supabase Google OAuth silently falls back to the project Site URL when the
  callback origin isn't on the redirect allowlist (user lands on the OLD app).
- Tenant isolation: prefer user-JWT + Postgres RLS (SECURITY DEFINER RPCs filtering
  by `auth.uid()`) over an admin-token proxy whose scoping lives in app code; audit
  read AND write paths, and test that injected `org_id` values are ignored.
- **Playwright headless is the tool for viewport/touch claims (2026-09-14 AMA
  session):** the browser tool runs desktop-only — any mobile claim (no
  horizontal overflow, no iOS zoom, swipe gestures, drawer behavior) needs a
  headless run against the DEPLOYED URL (a fresh context isn't logged in —
  script the login). pip install is PEP-668-blocked; use a venv at /tmp with
  playwright pinned to the version matching the cached browser build
  (`~/.cache/ms-playwright/`), else `playwright install chromium-headless-shell`.
  **Two corrections (2026-09-22, seller-agent console replica — read these before
  reusing the original advice):**
  1. **Sanity-check the emulated viewport before trusting ONE geometry
     assertion.** With `is_mobile=True, has_touch=True, deviceScaleFactor=3` and
     `viewport={width:390,height:844}`, the app reported
     `window.innerWidth/Height` of **660x1429** — every measurement silently
     described a larger device, and a drawer that genuinely needed to scroll
     appeared not to. A plain `viewport` reported truthfully (390x844). Assert
     `innerWidth/innerHeight` match what you requested at the top of the suite, or
     the rest of the run is measuring the wrong screen.
  2. **`scrollWidth == innerWidth` is the wrong assertion for horizontal
     overflow.** `documentElement.scrollWidth` reports the *untruncated* width of
     wide descendants inside an `overflow-x:auto` scroller even when the page
     cannot move, so it failed correct code and also mis-scaled a real bug (805
     reported vs 415 of actual travel). Assert the user-visible truth instead —
     can they PAN the page?
     ```js
     const panX = () => page.evaluate(() => {
       window.scrollTo(99999, 0);
       const x = Math.round(window.scrollX);
       window.scrollTo(0, 0);
       return x;                       // 0 == horizontally locked
     });
     ```
     Keep the pixel-diff of `scrollWidth` only as a *secondary* signal, never as
     the pass/fail. Full bug classes and the suite:
     `site-ui-replication` → `references/responsive-hardening.md`.
- **Swipe-gesture testing**: `touchscreen.tap()` can't drag. Dispatch a
  pointer-event sequence (pointerdown → rAF-stepped pointermove → pointerup,
  `pointerType:'touch'`) in ONE `evaluate()` — React synthetic handlers
  receive these. Read the row's computed `transform` afterward as the
  assertion. Elements hidden behind a sliding row need `:scope >` selectors
  (Playwright's hover/click on the row errors with "intercepts pointer
  events" on the reveal button).
- **Vision uploads via `expect_file_chooser`**: click the upload button inside
  `expect_file_chooser()`, then `chooser.set_files([{name, mimeType,
  buffer}])` — build the image bytes in Python (never hand-roll a base64 PNG;
  providers reject synthetic 1×1s with "Could not process image", use a real
  fetched PNG).
- **Never `pkill -f next-server` / `pkill -f "next start"` from inside a
  terminal tool call.** The pattern matches the shell running your own command
  (its argv contains the command string), so the tool call is killed mid-flight
  and returns `exit_code: -15` with no output — indistinguishable from a real
  failure, and it silently aborts any `&&` chain behind it. Capture the PID
  instead (`pgrep -f next-server | head -1 | xargs -r kill`) or `kill <pid>`
  from an earlier listing.
- **Verify a rebuilt server actually serves the new bundle.** `next build` can
  appear to succeed while `next start` still serves the old `.next`. Grep the
  built output for a string unique to your change before re-testing, e.g.
  `grep -rl "no numbered list" .next/server` — an empty result means the running
  process predates the edit and every "verification" that follows is invalid.
  This caught a real false-negative: the E2E ran against a stale build and the
  prompt change looked like it had no effect.
- **Sidebar toggles are stateful**: a hamburger that toggles (not opens) plus
  a `useEffect` mobile-init that closes the drawer on mount means a test
  click right after reload can toggle it closed. Reload, then click the
  toggle, then assert row counts before proceeding.
- **Raw-SSE honesty assertions for LLM chat apps (2026-09-16 AMA)**: a deployed,
  unit-green, md5-verified honesty guard still shipped a fabrication because the
  model bolded the creative name (`** breaks the regex match`) and the DOM
  assertion couldn't see the asterisks. Assert on the raw stream (`text` deltas
  + `replace` events, reconstructed from captured `/api/chat` POST bodies), ban
  the assertion shape not the bare name, strip markdown before regex-matching
  LLM output, and add an over-fire check (no `replace` on a successful lookup).
  Details + code: `references/e2e-verification-lessons.md` §14–15.
- **Separate "did the tool run?" from "was it honest?" (2026-09-16 AMA).** Card
  assertions can only fire when a lookup happened; the model intermittently skips
  a mandated tool call when an earlier turn already listed the data (measured 1/4
  vs 4/4 by context). Gate the card checks on the tool call, print `[SKIP]` when it
  didn't run, and keep every honesty assertion unconditional — a suite that cries
  wolf gets muted. `references/e2e-verification-lessons.md` §16.