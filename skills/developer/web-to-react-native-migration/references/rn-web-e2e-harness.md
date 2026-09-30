# Driving the RN-web build with Playwright

Concrete recipes for verifying a React Native Web port without a device. Written
from the AMA port (Expo SDK 57 / RN 0.86 / react-native-web), where this suite
reached 42 passing checks against both a local export and the deployed URL.

## Why this works at all

`expo export --platform web` emits a DOM SPA. `data-testid` set via an RN
`testID` prop lands on the element as `data-testid`, so Playwright's
`get_by_test_id()` works unchanged. No Detox, no simulator.

```bash
npx expo export --platform web
npx --yes serve dist -l 3401 --single      # --single: SPA fallback so /chat
                                           # does not 404 on hard refresh
```

`--single` matters: the router owns routing client-side, so any path that is not
a real file must return the shell.

## testIDs worth adding to the app (not just for tests)

| testID | On | Why it must exist |
|---|---|---|
| `composer-input` / `composer-send` | input + send button | drive a turn |
| `turn-active` / `turn-idle` | a **zero-size** probe View | the streaming signal — see below |
| `transcript` | the ScrollView | measure scroll position |
| `assistant-message` | each assistant bubble | scope text assertions to the reply |
| `sidebar-panel` | the drawer panel itself | measure the drawer's width |
| `tool-card` | tool cards | exclude captions from prose assertions |

`testID` must be threaded through any wrapper component that renders the surface
(e.g. a `Glass` component needs a `testID?: string` prop), otherwise the prop is
dropped and the element is unaddressable. RN views are also `collapsable` by
default and can be flattened out of the tree — pass `collapsable={false}` when an
element must survive.

## Zero-size probes need `state="attached"` — both directions

A probe rendered as `{ width: 0, height: 0 }` is **not visible**, so Playwright's
default `wait_for_selector(..., state="visible")` times out even though the
element is present. Wait for it as attached:

```python
await page.wait_for_selector('[data-testid="turn-idle"]', state="attached", timeout=120000)
```

Two further traps in the same area:

- **The probe's testID toggles with state.** `testID={streaming ? "turn-active" : "turn-idle"}`
  means you wait for `turn-idle` to know the turn finished. Assert the *opposite*
  marker exists before the turn, or a stray always-idle probe would pass forever.
- **react-native-web removes `aria-disabled` when it re-enables** rather than
  setting it to `"false"`. A selector like `[aria-disabled="false"]` never
  matches — which is what made an early attempt to wait on the send button time
  out on every run. Poll for "not true" instead, or better, use a state probe.

## Do not infer streaming from the send button

The send button is disabled while streaming **and whenever the input is empty** —
which is every moment immediately after a send. Waiting on it is guaranteed to
either time out or pass instantly and wrongly. This is the single most expensive
mistake in this harness; use an explicit probe.

## Scoping text assertions correctly

Searching `document.body.innerText` is almost always wrong for an assertion about
the model's reply, because the page also contains:

- the user's own message (so asking about `"Thing X"` matches the question),
- tool cards, whose creative captions are real data that drown the signal.

Scope to the reply bubble you tagged:

```python
reply = await page.evaluate("""() => {
    const bubbles = Array.from(
        document.querySelectorAll('[data-testid="assistant-message"]')
    );
    return bubbles.length ? (bubbles[bubbles.length - 1].textContent || '').trim() : '';
}""")
```

## Normalise unicode punctuation before matching

Models emit curly apostrophes and quotes. An ASCII substring match silently fails:

```python
def normalise(s):
    return (s.replace("\u2019", "'").replace("\u2018", "'")
             .replace("\u201c", '"').replace("\u201d", '"').lower())
```

A real example: the reply *"I couldn't find a creative called X"* contains
`couldn’t` (U+2019), so `"couldn't" in reply` was `False` and a correct behaviour
was reported as a failure.

## Echoing a not-found name is not fabrication

When a "does not exist" probe is echoed back — *"I couldn't find a creative
called «the name I just asked for»"* — that is correct, not invention. Assert the
**negative property**: it must not present the fictional item as existing.

Keep the keyword list to unambiguous claims (`has artwork`, `here it is`,
`status is`, `displayed above`). Do **not** include generic words like `format`
or `status`: a reply legitimately offers *"search by brand or format"*, and a
bare-word match flags that as fabrication. This exact false positive fired only
on the deployed run, not locally, because the wording varied.

## Measuring instead of eyeballing

Numeric assertions are what make a UI fix stick. Measure centres and report the
spread:

```python
mid = "e => Math.round(e.getBoundingClientRect().top + e.getBoundingClientRect().height / 2)"
spread = max(iconMid, sendMid) - min(iconMid, sendMid)
```

Real before/after from one session, all from such measurements:

| Property | Before | After |
|---|---|---|
| composer pill height | 64px | 54px |
| centre spread (text / icon / send) | 12px | 0px |
| focus outline while focused | `rgb(16,16,16) auto 1px` | `none 0px` |
| desktop drawer width | 1440px (viewport) | 320px |
| composer text vs icon centre | 11px apart | 0px apart |
| input box vs its content | 54px vs 32px (stretched) | equal |
| 4-line input height | 32px (would not grow) | 98px |

### A passing measurement can still be measuring the wrong thing

The row above is the lesson. A first fix centre-aligned the row and an assertion
on **`rect.top + rect.height / 2` passed** — while the placeholder was still 11px
high, because the textarea's rect was *taller than its content*. Two corrections:

```js
// The text's OWN visual centre — derive it from the box model, not the rect.
const textCentre = rect.top + parseFloat(cs.paddingTop) + parseFloat(cs.lineHeight) / 2;

// And assert the box is not stretched beyond what it holds. A stretched input
// is the signature of this entire bug class.
const stretch = Math.round(rect.height - (paddingTop + paddingBottom + lineHeight));
```

Root cause in this case: react-native-web renders a multiline `TextInput` as
`<textarea rows="2">`, so the box is intrinsically two lines tall while holding
one. `rows={1}` on web fixes it — and then the height must be driven from a
measured `scrollHeight` because a `rows=1` textarea stops growing on its own.

Rule of thumb: **if the assertion passes but the screenshot still looks wrong,
you are measuring the wrong thing.** Prefer the value the user actually sees
(text baseline, rendered height) over the container's geometry.

## Loading state: assert the ABSENCE of an empty bubble

An empty assistant bubble containing only a spinner reads as a broken message.
Two assertions cover it, and both are needed:

```python
# mid-turn: no empty bubble may exist, and either the standalone spinner or a
# bubble-with-text is present
check("no empty assistant bubble while waiting", not early["emptyBubble"])
# after the turn: the standalone spinner must be gone
check("standalone spinner gone once the reply arrives", after["pendingGone"])
```

Tag the standalone spinner separately (`pending-spinner`) from the reply bubble
(`assistant-message`) — otherwise "is the spinner showing" and "is the reply
showing" cannot be distinguished.

## Hover-revealed controls need a hover-capable assertion

`page.hover()` works on RN-web pressables (they render as DOM nodes with
pointer events). Assert the control is **absent before** hovering and **present
after** — a control that is always in the tree will pass a naive existence check:

```python
before = await page.evaluate("() => document.querySelectorAll('[data-testid^=\"conversation-delete-\"]').length")
await row.hover()
after = await page.evaluate("() => document.querySelectorAll('[data-testid^=\"conversation-delete-\"]').length")
assert before == 0 and after > 0
```

Also assert the control is **icon-shaped** (`<= 40px`, empty text) so a
regression back to a text button is caught, and that the row's height is
**identical** with and without it (no reflow).

## Wait for the turn, not for a duration

```python
async def wait_for_idle(page, timeout_ms=120000):
    await page.wait_for_selector('[data-testid="turn-idle"]',
                                 state="attached", timeout=timeout_ms)
    await page.wait_for_timeout(4000)   # let late images / galleries lay out
```

The trailing settle is needed because remote images and galleries finish laying
out *after* the stream ends — content size keeps changing for a moment.

## Always run the suite against the deployed URL too

A localhost run passes without exercising CORS (a localhost origin is usually
allowlisted for dev). The deployed run is what proves:

- the real origin is in the server's CORS allowlist,
- the server picked up a newly added env var (a container must be **restarted**
  to load a changed `.env` — adding the var to the file is not enough),
- the served bundle is the one you built.

That last one is worth a hash comparison; see Step 8.17.

## Console-error assertion: filter the known-benign noise

Assert zero uncaught JS errors, but exclude:

- `useNativeDriver is not supported ... falling back to JS-based animation` —
  expected on RN-web,
- CORS/`Failed to fetch` noise *only if* you are deliberately testing a
  misconfiguration.

Everything else is a real finding. A 401 from a pre-login `fetch` showed up here
and was a genuine bug (an authenticated endpoint being called before sign-in) —
so filter narrowly and by exact message, never by a broad regex.

## A crash is not a failure — and a flaky result needs attribution

The suite intermittently dies with `TargetClosedError` (chromium process death),
roughly 1 run in 6, **before** streaming starts. Distinguish it from an assertion
failure by the summary line:

| Outcome | Signature | Meaning |
|---|---|---|
| assertion failed | `FAILED: <check name>` and a fail count | a real product finding |
| crash | **no summary at all**, non-zero exit, zero `[FAIL]` lines | environmental |

Check for the **absence of the summary** rather than assuming a failure — a
crash reports zero failed checks, which reads as "all good" if you only grep for
`FAIL`.

Before blaming a crash on your own change, attribute it with a controlled A/B:

```bash
git stash push -m wip <suspect-file>   # revert only the suspect file
./deploy/deploy-at2.sh
./e2e/run_e2e_repeat.sh 6              # same loop, same count
git stash pop && ./deploy/deploy-at2.sh
```

Two conditions make this sound:

- **Compare the deploy hashes.** If the printed `local index.html` /
  `remote index.html` hashes match across both arms, you deployed the same build
  twice and proved nothing.
- **Reproduce on the unmodified arm.** If it does, the flake is pre-existing and
  belongs in the report as such — not silently worked around, and not "fixed" by
  widening a timeout.

Then re-run the full sweep and confirm the restored build's hash matches the
pre-stash build before continuing.

