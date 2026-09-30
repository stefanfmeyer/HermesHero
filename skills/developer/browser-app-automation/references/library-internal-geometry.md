# Verifying a third-party UI library's internal geometry (and attributing artifacts)

Session-derived (AMA chart hover indicator, 2026-09-21). The user reported
*"The interactive charts on hover are showing the points off-center. (SEE IMAGE)"*.
The indicator was landing **+35px to the right** of the point it described, and the
offset was caused by a prop I had set myself.

This file covers four techniques that generalise to ANY third-party component whose
internals you cannot read cleanly:

1. diagnosing a fixed offset by varying the suspect prop
2. building a throwaway variant lab instead of reading minified internals
3. measuring glyph clipping when an element's bounding box lies
4. attributing a visual artifact to the right DOM element before "fixing" it

---

## 1. A fixed offset that tracks a prop exactly is a DOUBLE-COUNT

The first useful move is not to read the library's source (it was bundled/minified
and cross-package) but to **vary the suspect prop and see whether the error tracks
it**. Measured by pressing each data point and reading where the crosshair landed:

| `initialSpacing` | crosshair offset from the point |
|---|---|
| 35 | **+35.3px** |
| 0 | **+0.3px** |

The offset equalling the prop value *exactly* is the signature. A rounding artefact
or a coordinate-space mistake gives an arbitrary small delta; a double-count gives
`offset == prop`. Confirmed cause: the library insets its pointer overlay container
by `initialSpacing` **and** computes `pointerX = initialSpacing + sum(spacing…)`, so
the inset is applied twice.

**Generalise:** when a rendered element is displaced by a constant amount, find the
one prop/constant that equals that amount and vary it. If the error follows it 1:1,
you have a double-application, not a layout bug — and the fix is to set it to zero,
not to compensate with an offset.

### The residual you should NOT chase

After the fix the first point's crosshair sat ~5px right of its dot. That is the
library clamping at the plot's left edge (`Math.max(0.1, …)` plus radius). The
per-item `pointerShiftX` prop moves the strip **line** but not the **dot**, so using
it makes the two disagree — worse than a uniform 5px on one point. Assert the loose
bound deliberately (`<= 6px` for the first point, `<= 3px` elsewhere) with the
reason in the assertion comment. An unexplained tolerance rots; an explained one is
documentation.

---

## 2. Build a throwaway variant lab rather than reading minified internals

When two constraints conflict inside a library's layout, comparing candidate
geometries empirically beats source archaeology. Add a temporary route with N
variants side by side, measure all of them in one run, then **delete it**:

```
app/chartlab.tsx     # variants A..G, each with a testID, no links to it anywhere
```

```tsx
<Chart id="A-current" initialSpacing={35} rightRoom={0}      ... />
<Chart id="B-zero"    initialSpacing={0}  rightRoom={LABEL_HALF} ... />
<Chart id="C-narrow"  initialSpacing={0}  rightRoom={LABEL_HALF} width={W - 70} ... />
```

Measured output in one pass, which is what settled the design:

```
variant           spacing  ptr off(last)   clipped labels
A-current            343.5    0.3          ['Sep 18(15.9px)']
B-init35             343.5   35.3          none
F-init0-7d           114.5    0.3          ['Sep 14(15.9px)']
```

**Two gotchas that cost time:**

- **An auth-gated SPA will redirect the lab route to /login.** Temporarily exempt
  the route in the layout's auth effect (`if (segments[0] === "chartlab") return;`)
  and **remove that bypass before committing** — verify with
  `grep -rn "chartlab" app/ components/` returning nothing.
- **A static SPA export needs an SPA-fallback server.** `python3 -m http.server`
  returns 404 for the deep route; a `do_GET` handler that rewrites unknown paths to
  `/index.html` is the fix. Without it the lab "doesn't exist" and you debug the
  wrong thing.
- **Restart the file server after changing its served directory.** A `sed` on the
  config file does NOT affect the already-running process — one whole measurement
  round was spent testing the previous build. Kill and relaunch, then re-verify the
  served variant IDs are the new ones.

---

## 3. Measuring glyph clipping: an element's bounding box LIES

Asserting "the label is not clipped" via `el.getBoundingClientRect()` is **useless**
when the library wraps each label in a fixed-width box (~310px for a ~32px label):
every label looks clipped by that measure, so you learn nothing. The label DID get
clipped — "Sep 18" rendered as "» 18" — and the first measurement missed it entirely.

Correct method: measure the **text's own rect** with a DOM `Range`, then intersect it
with every ancestor that clips in x:

```js
const rg = document.createRange();
rg.selectNodeContents(el);
const g = rg.getBoundingClientRect();
let visL = g.left, visR = g.right;
let n = el;
while (n && n !== document.body) {
  const s = getComputedStyle(n);
  if (/(hidden|clip|scroll|auto)/.test(s.overflowX)) {
    const r = n.getBoundingClientRect();
    visL = Math.max(visL, r.left);
    visR = Math.min(visR, r.right);
  }
  n = n.parentElement;
}
const clippedPx = Math.max(0, (g.right - g.left) - (visR - visL));
// assert clippedPx === 0 for every label
```

The clipped case measured **15.9px** — exactly half of a 31.7px label, because the
label is centre-positioned on a point that sits ON the clip boundary.

### Where the clip boundary comes from, and why "just widen the gutter" fails

Measured at four y-axis widths, the clip edge and the first data point move
**together**:

| y-axis gutter | clip edge / first point x |
|---|---|
| 44 | 45 |
| 60 | 61 |
| 80 | 81 |
| 100 | 101 |

So the first label always loses half its glyphs once the first point sits at
`initialSpacing: 0`. And you cannot use `initialSpacing` to buy the room back
because it re-breaks the pointer (§1). **The two constraints are mutually exclusive
inside the library's layout** — the resolution is to stop using the library's labels
(`xAxisLabelsHeight={0}`, every datum `label: ""`) and render your own row outside
the clipped container, positioned from the same `spacing` the series uses. Result:
every label complete and centred within 1px at 1280px and 390px.

**Generalise:** when a library's own sub-element is clipped and the obvious knob
moves the clip boundary together with the content (so the relative error never
changes), stop tuning and render that sub-element yourself. Also check the pixel
truth once (below) — a DOM measurement and the rendered glyphs can disagree.

### Pixel-confirm the DOM claim

To be certain the glyphs really are cut (and not just the rect arithmetic), read the
rendered pixels and cluster ink columns:

```python
ink = (np.array(Image.open(png).convert("L")) < 200).sum(axis=0)
cols = np.where(ink > 0)[0]
# group into clusters with a ~12px gap threshold; a detached fragment at x≈0
# followed by a gap then the rest of the word == a hard clip at the edge
```

Measured: ink clusters `[(108,120), (183,228), ...]` — a stray 12px fragment then a
gap then "18". That is the "» 18" the user-equivalent screenshot showed.

---

## 4. Attribute an artifact to the right element BEFORE fixing it

A small ⚡ glyph and a ◈ diamond appeared near the chart's y-axis on mobile. Both
were **real pixels** and looked exactly like a chart bug. They were not chart
elements at all:

```js
const el = document.elementFromPoint(x, y);   // then walk up reading className
```

The walk returned `product-rail-spark` / `product-rail-signal` — the app's **product
rail** (collapsed left sidebar), showing *through* the translucent glass card. A
pre-existing property of the glass material, present on the deployed build before
the change, and nothing to do with the component under test.

**Rules:**

- **`elementFromPoint` + ancestor-walk is the attribution tool.** Never start
  editing the component you suspect; locate the node first.
- **Prove pre-existing vs introduced by running the same probe against the
  untouched deployed build.** The identical coordinates/glyphs on prod is what
  justified "not mine".
- **A screenshot-scaled artifact may not exist.** A `device_scale_factor` re-render
  showed a diamond where a native-scale capture showed none; the 4x crop of the same
  spot was clean. Confirm at 1x before believing a small glyph is real — but note
  both cases here were genuine, so *check*, don't assume noise.
- Report it separately as a decision for the user ("mask the rail behind cards, or
  accept it") rather than silently widening the fix or ignoring it.

---

## 5. The assertions that actually catch these

Both invariants were invisible to visual review — a 35px pointer error reads as
"nearly right", and half a missing first letter reads as a rendering quirk. They
survived a vision check and were only caught by measuring.

**Atomicity: the crosshair only exists while the pointer is HELD DOWN.** Measuring
before the press finds no crosshair and the check **passes vacuously**. Do
press → read → release inside one helper:

```python
async def measure_strip(page, box, target_x):
    y = box["y"] + box["height"] * 0.45        # inside the plot's responder area
    await page.mouse.move(box["x"] + target_x, y)
    await page.mouse.down(); await page.wait_for_timeout(140)
    await page.mouse.move(box["x"] + target_x + 0.5, y, steps=2)
    await page.wait_for_timeout(420)
    xs = await page.evaluate(...)               # read the tall vertical <line>
    await page.mouse.up()
    return xs[0] if xs else None                # None must FAIL, not pass
```

- **The press Y matters.** Only part of the card's height is the chart's responder
  area; pressing at `height * 0.5` produced no crosshair at all while `0.45` worked
  at every height measured. Press at a *data point's own y* when you can.
- **Re-measure the element's box immediately before pressing.** An earlier drag had
  scrolled the transcript, so the box captured minutes earlier was stale and the
  press landed outside the chart → "no crosshair rendered", which nearly read as a
  real failure. `scroll_into_view_if_needed()` then re-`bounding_box()`.
- **Identify the overlay by a structural property, not colour.** The crosshair is
  the only tall vertical `<line>` (`|y2 - y1| > 60`); enumerating by fill/background
  colour matched unrelated absolutely-positioned divs.
- **`None` from the probe must fail the assertion.** `if strip is None: check(..., False, "no crosshair rendered while pressed")` — otherwise an empty read is a
  silent green tick.

### Mutation-test the assertion, with the reported magnitude

A new geometry assertion is only trustworthy once you have watched it fail. Restore
the bug, rebuild, re-run:

- restore `initialSpacing = edge` (value 35) → **FAILS with 35.3px**, the exact
  magnitude the user reported
- move the label row back inside the chart's container → **FAILS with 15.9px** clipped

A `git stash` of the whole component file was the wrong mutation instrument — it
reverted the feature wholesale and the chart did not render at all (`0 cards`),
which tests nothing. **Mutate the single line under test** and re-export.

### A mutation run needs the served bundle actually swapped

The file server must be restarted between mutations (§2). Otherwise the "old code"
run silently serves the new build and the assertion appears not to catch the bug —
the most misleading possible result, since it argues for deleting a good test.
Verified correct sequence: rebuild → **kill** the server → relaunch → confirm the
served variant/behaviour changed.
