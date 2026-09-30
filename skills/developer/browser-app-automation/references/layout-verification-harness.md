# Layout Verification Harness (Playwright, numeric)

Proven 2026-09-22 on a review page (turning a fixed drawer into a grid
column + a desktop-only gate). Copy and adapt; do not hand-write this each time.

## Why numeric, not visual

Every bug in that session was invisible to a screenshot but obvious to a number:

| Bug | Screenshot said | Numbers said |
|---|---|---|
| `column-gap: 0 var(--sp-8)` silently dropped | "looks fine" | `columnGap: normal`, gutter `0px` (wanted `32px`) |
| spanning fixed drawer stretched the tracks | "looks fine" | dead space `206px` between card and next row |
| follow-up fix regressed closed-state spacing | "looks fine" | `57px` vs closed `16px` |
| `DesktopOnly` rendered unconditionally | "looks fine" | a click was intercepted by `role=alert` overlay |

The pattern: **assert the property you claim, and assert it against the closed/
baseline state too.** A green open-state assertion set let a 41px regression through.

## Setup

`require()` of playwright inside a `"type": "module"` repo fails. Run from a directory
that has playwright, with `NODE_PATH` pointing at it:

```bash
NODE_PATH=$HOME/node_modules node /tmp/verify_layout.js
```

Find an existing install rather than `npm i`-ing a new one:
`find / -maxdepth 7 -type d -name playwright -path "*node_modules*"`.

A `const { chromium } = require('playwright')` script must be `.cjs` or run from a
non-module dir; `.js` under `"type":"module"` is parsed as ESM.

## The harness

```js
const { chromium } = require('playwright');
const CREDS = { user: '<u>', pass: '<p>' };

async function login(page, url) {
  await page.goto(url, { waitUntil: 'networkidle' });
  if (await page.locator('input[type="password"]').count()) {
    await page.fill('input[type="text"], input[name="username"]', CREDS.user);
    await page.fill('input[type="password"]', CREDS.pass);
    await page.click('button:has-text("Sign In")');
    await page.waitForTimeout(2500);
  }
  if (!page.url().includes('/ios/')) {          // SPA may not have navigated yet
    await page.goto(url, { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);
  }
}

// ONE snapshot fn used for every state, so open/closed/baseline are comparable.
const SNAP = () => {
  const R = s => { const e = document.querySelector(s); if (!e) return null;
    const b = e.getBoundingClientRect();
    return { l: Math.round(b.left), r: Math.round(b.right),
             t: Math.round(b.top), b: Math.round(b.bottom),
             w: Math.round(b.width), h: Math.round(b.height) }; };
  const pane = document.querySelector('.pane');
  return {
    pane: R('.pane'),
    display: pane ? getComputedStyle(pane).display : null,
    padLeft: pane ? getComputedStyle(pane).paddingLeft : null,
    padRight: pane ? getComputedStyle(pane).paddingRight : null,
    cols: pane ? getComputedStyle(pane).gridTemplateColumns : null,
    colGap: pane ? getComputedStyle(pane).columnGap : null,   // catches invalid decls
    split: R('.split'), row2: R('.row-2'),
    drawer: R('.drawer'),
    toggleDisplay: (() => { const t = document.querySelector('.toggle');
      return t ? getComputedStyle(t).display : 'absent'; })(),
    vw: window.innerWidth, vh: window.innerHeight,
  };
};

const chk = (n, cond, extra = '') =>
  console.log((cond ? 'PASS' : 'FAIL') + '  ' + n + (extra ? '  [' + extra + ']' : ''));
```

## Assertions that actually caught bugs

```js
// 1. The overlay occupies the RESERVED TRACK, not just "isn't overlapping".
chk('overlay == reserved column',
    Math.abs(open.drawer.l - (open.pane.r - 420)) < 1 &&
    Math.abs(open.drawer.r - open.pane.r) < 1);

// 2. No overlap AND the gutter is the intended token width.
chk('gutter is --sp-8', open.drawer.l - open.split.r === 32,
    'gap=' + (open.drawer.l - open.split.r));

// 3. THE BIG ONE: does anything regress vs the closed state?
chk('spacing parity vs closed',
    (open.row2.t - open.split.b) === (closed.row2.t - closed.split.b),
    'open=' + (open.row2.t - open.split.b) + ' closed=' + (closed.row2.t - closed.split.b));

// 4. "full width"/"full height" need their own assertion.
chk('row spans both content cols', open.row2.w === open.split.w);
chk('overlay reaches viewport bottom', open.drawer.b >= open.vh - 1);

// 5. Invalid CSS reads as ABSENT — assert the computed value, not the source.
chk('column gap applied', open.colGap === '32px', open.colGap);

// 6. State-only elements.
chk('toggle hidden while open', open.toggleDisplay === 'none');
```

## Responsive gate + revert check

Always test BOTH directions — that the notice appears narrow AND clears wide again.
A gate that latches on is a common bug.

```js
await page.setViewportSize({ width: 820, height: 900 });
await page.waitForTimeout(900);              // let the matchMedia listener fire
const narrow = await page.evaluate(() => {
  const el = document.querySelector('.desktop-only');
  return { present: !!el, display: el ? getComputedStyle(el).display : null };
});
chk('notice shown at 820px', narrow.present && narrow.display !== 'none');

await page.setViewportSize({ width: 1397, height: 1016 });
await page.waitForTimeout(900);
chk('notice cleared at 1397px',
    !(await page.evaluate(() => !!document.querySelector('.desktop-only'))));
```

Also verify the gate covers the LOGIN route (unauthenticated), not just authed pages.

## Failure signatures worth recognising

- **`<div role="alert" class="desktop-only"> intercepts pointer events`** on a click
  aimed at an unrelated element = an overlay is rendering when it shouldn't. It reads
  like a bad selector (Playwright retries for 30s then times out); it is actually a
  layout/visibility bug. Check the overlay's mount condition, not the selector.
- **Page shows "Loading…" in a screenshot** = you screenshotted mid-transition. The
  harness clicked close/reopen and shot immediately. Add a `waitForTimeout` and
  re-shoot; don't debug the app.
- **`net::ERR_CONNECTION_REFUSED`** = the dev server died between runs (it gets reaped
  with its shell's process group). Curl the health endpoint before blaming the app.

## Reading a design mock for exact numbers

When the user supplies a target screenshot, measure it instead of eyeballing. Load it
with PIL, take run-lengths of a horizontal scanline to find column edges, then
reconcile:

```python
# edges found at x=21..542 / 543..550(border) / 552..567(gap) / 569..1090 / 1091..1098 / 1100..1149(dark)
# => viewport 1397 at 112% zoom. Derive each CSS value from the ratios,
#    don't copy raw pixels.
```

The derivation that mattered: content left edge = 20px (`--sp-5`), gutter = 32px
(`--sp-8`, the same token the inner grid already used), drawer = 420px. **A gap that
matches an existing spacing token is almost certainly that token** — reaching for
`--sp-8` rather than a literal `32px` made the whole layout self-consistent.

Confirm a *text orientation* claim by cropping and magnifying the region ~7x
(`crop().resize((w*7, h*7), Image.LANCZOS)`), then reading it in a vision call. A
16px vertical label read from a full-page screenshot is a coin flip; at 7x it is
unambiguous. Do this before "fixing" an orientation the user describes — it settled
that top-to-bottom was already correct and that a separate request was the flip.

### Scan BOTH axes — a horizontal scanline only gives you column widths

The horizontal run-length scan tells you nothing about vertical insets. Scan a
vertical column too, and in **each region separately**:

```python
for x_label, x in (("content col", 300), ("drawer col", 1200)):
    prev = None
    for y in range(40, 92):
        c = px[x, y]
        if prev is None or max(abs(c[i] - prev[i]) for i in range(3)) > 3:
            print(" %s y=%d %s" % (x_label, y, c))
        prev = c
```

Measured result on the mock: header bar ends at `y=51`; the **content card
starts at `y=71` (a 20px inset)** while the **drawer starts flush at `y=52`**. So the
mock's insets are **asymmetric** — content inset, panel flush.

**Do not generalise one region's inset to another.** The temptation is to measure the
content's 20px top inset and apply it everywhere; the panel genuinely starts flush.
This is exactly the bug it caught: the open-state grid had been written as
`padding: 0 0 0 var(--sp-5)`, so the content lost its 20px top inset and sat flush
under the nav bar while open, but inset while closed. The mock proved the intent.

### Background colour can hide an edge — use the border column, then magnify

The drawer background and the page background were the **same** colour
(`(19,19,19)`), so a vertical scan inside the drawer column showed no boundary at
all — the "drawer starts at y=52 or y=71?" question was unanswerable from pixels
alone, and the two candidate readings implied opposite fixes. Two ways out:

1. **Find the panel's border/edge column** (a 1–2px contrast line) and scan its
   extent, rather than scanning the fill: at `x=1099` a `(38,38,38)` border column
   existed for `y>=74` and not above, which bound the panel's true top.
2. **Crop and magnify the corner and look at it.** Reading a 3x-magnified crop of the
   nav-bar/panel junction settled it in one call: the panel visibly starts
   immediately below the bar (no gap) while the left content shows background. When
   pixel archaeology is ambiguous between two readings that imply *different fixes*,
   stop deriving and look — one vision call beats a chain of inferred boundaries.

