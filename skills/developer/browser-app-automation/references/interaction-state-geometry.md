# Interaction-state geometry: hover must not move layout

Session-derived (AMA sidebar, 2026-09-16). The user reported it precisely:
*"When I hover on a recent chat, the text inside the button moves down by a couple
of pixels. Looks like there is a padding/spacing issue."*

## Why the eye and the screenshot both miss it

2.75px of vertical shift at 1440px wide is imperceptible in a still image — before
and after look identical. Vision-checking the screenshots PASSED while the user
saw the text jump every time they moved the mouse. **A geometry claim needs a
measured delta, not a look.** This is the same class as the "false pass" traps:
the assertion must observe the thing the user observes (motion), which a single
frame cannot show.

## Root cause chain (one CSS class, three symptoms)

The delete button was `hidden group-hover:block`. On hover it entered the flex flow
**for the first time**, and its intrinsic box (28px = 16px icon + `p-1.5` padding)
was TALLER than the row's text line (22.5px). Three measured effects:

| | Idle | Hover | Δ |
|---|---|---|---|
| row height | 42.5px | 48px | **+5.5px** |
| title y (centred) | 215px | 217.75px | **+2.75px** ← what the user saw |
| title width | 264px | 232px | **−32px** → label re-truncated |

The height delta is the full 28px box vs the 22.5px line; the text shift is half of
it because the flex `items-center` alignment re-centres. The width delta is the
button's box plus its `ml-1` margin.

Generalised: **toggling `display` on a flex child changes the container's geometry.**
`hidden group-hover:block` / `group-hover:flex` is the tell. Any hover-revealed
control taller or wider than adjacent content will move that content.

## The fix pattern: absolute + reserve + opacity-only

1. **Take the control out of the flow** — `absolute`, positioned against the row.
2. **Reserve its space statically** on the side that needs it, sized from the
   control's real box (`pr-10` = 40px for a 28px button + gap), so idle and hover
   widths are identical.
3. **Toggle visibility with opacity, never `display`** — no reflow is possible if
   the element's box never changes:
   ```
   absolute right-2 top-1/2 hidden h-7 w-7 shrink-0 -translate-y-1/2 items-center
   justify-center rounded-full opacity-0 pointer-events-none transition-opacity
   duration-150 group-hover:pointer-events-auto group-hover:opacity-100
   focus-visible:pointer-events-auto focus-visible:opacity-100 sm:flex
   ```
4. **Scope breakpoint-dependently.** The desktop hover control is `hidden sm:flex`;
   touch devices have no hover, so keep the mobile path (swipe-to-reveal) on its own
   padding and leave it alone. Verify the swipe path still works — don't regress it
   while fixing hover.

## Decide reserve-vs-overlay by measuring, don't guess

Reserving space costs label width, which can newly truncate titles. Measure before
choosing: compare each title's natural width against the RESERVED width.

```js
// per row: t.clientWidth (available) vs t.scrollWidth (natural text width)
{ titleW: tB.width, titleNatural: t.scrollWidth,
  titleTruncated: t.scrollWidth > Math.ceil(tB.width) + 1 }
```

Long titles already truncate at 264px; reserving to 240px shortened a couple of
mid-length ones by ~13px, which reads as normal truncation rather than a bug. Had a
large majority newly clipped, overlay-on-hover (no reservation, label under the
button) would have been the better trade.

## Assert it as a regression, every row

Measure idle → hover each row in turn, then park the pointer away and re-measure
to prove nothing stuck:

```python
max_shift = 0
for i in range(row_count):
    await page.locator("nav > div").nth(i).hover()
    await page.wait_for_timeout(900)
    hv = await page.evaluate(GEOM)
    max_shift = max(max_shift, abs(hv[i]["titleTop"] - idle[i]["titleTop"]))
await page.mouse.move(1200, 700)      # un-hover
await page.wait_for_timeout(500)
# max_shift must be < 0.5px; row heights identical after mouse-away
```

Passing looks like `max Δh=0.0px idle=[42.5] hover=[42.5]`, `max ΔtitleTop=0px`,
`max ΔtitleW=0px`. A 0.5px threshold absorbs sub-pixel rounding without admitting a
real shift.

## Keep the revealed control working

A geometry fix can quietly break the control's own behaviour. Verify it end-to-end,
not just its presence in the DOM:

- Enumerate `nav button[title="Delete"]` and read `display`/`opacity`/`pointerEvents`
  per element. A hovered row should show one `opacity=1 pe=auto`; every other row
  `opacity=0 pe=none`. That single read catches both "invisible but clickable" and
  "revealed but unclickable".
- Click it and assert the confirmation dialog appears, then CANCEL and assert the
  stored rows are unchanged — never let a layout test mutate user data.
- Beware the selector: mobile swipe-reveal buttons often carry the same
  `title="Delete"` and are `pointer-events-none`, so a bare
  `button[title="Delete"]` matches the wrong (unclickable) element and the click
  times out with a generic `TimeoutError`. Use `:visible` or scope by DOM depth.

## Spacing changes: state the arithmetic

When asked for "about ten pixels more", express the delta from the current value and
name the utility: `space-y-0.5` (2px) → `space-y-3` (12px) = exactly +10px. Then
confirm it rendered — read the actual gaps between consecutive row boxes
(`next.top - (prev.top + prev.height)` → `[12, 12]`), because a class change can be
overridden by a later rule.
