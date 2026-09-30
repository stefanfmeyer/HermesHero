# Responsive hardening: making a desktop-verified replica survive a phone

First done on the seller-agent console replica (Vite + React 19 + Tailwind 4), 390px
viewport, 2026-09-22. The trigger was a one-line request — "make the menu collapsible
for mobile" — which uncovered **three pre-existing horizontal-overflow bugs** that were
invisible at desktop width, because a page that overflows sideways only shows its
symptom when you try to pan it: a large empty white region appears beside the content.

The general lesson: **a desktop-only verification pass certifies a layout that is
broken on mobile.** Budget a mobile pass whenever a UI is going to be shown to anyone
on a phone, and expect it to find real bugs rather than to just confirm the nav.

## Bug class 1 — `mx-auto` overrides `align-items: stretch`

An auto margin on a flex child beats the container's `align-items`. So a
`flex-1 ... mx-auto` child sizes to its **content**, not the viewport.

```jsx
// BEFORE: 390px viewport, <main> measured 660px wide -> page panned sideways
<div className="min-h-screen flex flex-col lg:flex-row">
  <main className="flex-1 px-4 max-w-[1200px] mx-auto min-w-0">
//  AFTER: w-full restores stretch, mx-auto still centres within the max-width
  <main className="w-full flex-1 px-4 max-w-[1200px] mx-auto min-w-0">
```

This is easy to *introduce yourself* when converting a horizontal flex shell to
`flex-col` for mobile: the original `flex-1` was fine in a row, and adding
column direction is what let content sizing win. `min-w-0` alone does not fix it —
that only stops flex *items* from refusing to shrink; `w-full` is what stops the
auto margin from taking over.

## Bug class 2 — `<pre>` never wraps

Any `<pre>` rendering JSON or a long URL stretches the whole document, because
`white-space: pre` has no wrapping and the element reports its full intrinsic width.

```
Properties page: docScrollWidth 805 in a 390 viewport, panX=415
-> blamed TableWrap, tried overflow hidden/clip/max-width/display:contents on it
-> panX stayed 415 through ALL of them (that was the signal it was the wrong element)
```

Find it by **hiding subtrees until the page stops moving**, rather than by guessing
at suspect components:

```js
[...document.querySelectorAll('main > *')].forEach((ch, i) => {
  ch.style.display = 'none';
  const x = panX();                    // measure with this branch hidden
  ch.style.display = '';
  if (x < baseline) console.log('culprit index', i, ch.tagName, ch.className);
});
```

Then recurse into that child. That walk located a single `<pre className="mono ...">`
in two clicks after the element-rect approach had failed for several rounds.

Fix: `overflow-x-auto` on **each** `<pre>` itself. Grep for `count(<pre>)` vs
`count(overflow-x-auto)` — in the real case 3 `<pre>` blocks existed and only 1 had it.

```bash
grep -rn '<pre' src/
```

## Bug class 3 — fixed grids and `shrink-0` set minimum widths

Both encode a minimum that cannot shrink below the phone width:

| Offender | Symptom | Fix |
|---|---|---|
| `grid grid-cols-4` (x2), `grid-cols-3`, `grid-cols-2` (x4) | KPI/card rows forced 4 columns into 390px | `grid-cols-1 sm:grid-cols-N` |
| `shrink-0` on a right-aligned span | long label pushed past the edge | `min-w-0 break-words text-right` |
| long unbroken `<code>` URL | 481px doc width | `break-all` |

Sweep for them rather than waiting for a symptom:

```bash
grep -rn "grid-cols-" src/          # every hit is a candidate
grep -rn "shrink-0" src/
```

## Tables: the wrapper must scroll, not the page

A shared table wrapper is the right place to fix wide tables app-wide:

```jsx
// overflow-hidden clips the rounded corners but makes wide tables push the PAGE wide
<div className="... rounded-xl overflow-hidden">
// overflow-x-auto keeps the corner clipping AND lets the table scroll in its own card
<div className="... rounded-xl overflow-x-auto">
```

It **must** be on the wrapper; putting it on the `<table>` does nothing. Verify both
directions: the table overflows its wrapper (`scrollWidth > clientWidth`, so it *can*
scroll) and the page does not pan.

## The off-canvas drawer pattern

Requirements that mattered, each of which was a separate bug when omitted:

- **Close on the ACTION, not a route effect.** An effect watching `pathname` and
  calling `setNavOpen(false)` is a setState-inside-effect: it cascades a render and
  oxlint's `react(set-state-in-effect)` flags it. Close on the link's own `onClick`,
  plus scrim, Escape, and the close button.
- **Escape** via a `keydown` listener, added only while open.
- **Body scroll lock** while open — but only below the breakpoint, or a desktop user
  who somehow opens it gets a locked page:

  ```js
  useEffect(() => {
    if (!navOpen) return;
    if (window.matchMedia('(min-width: 1024px)').matches) return;   // lock mobile only
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = prev; };
  }, [navOpen]);
  ```
- **The drawer must scroll itself.** 12 nav links + footer need ~774px of height; on a
  375x667 phone the last link is unreachable unless the aside has
  `overflow-y-auto` and `inset-y-0`.
- **`aria-expanded` / `aria-controls` on the burger, `aria-label` on the close button** —
  which is also what makes the elements findable in the verification suite.
- Keep the desktop sidebar a plain `lg:static lg:translate-x-0` override so there is
  one markup tree, not two.

## Verification: two traps that produce FALSE results

### Trap 1 — Playwright `isMobile: true` misreported the viewport

With `isMobile: true, hasTouch: true, deviceScaleFactor: 3` and a 390x844 viewport,
the app reported `window.innerWidth/innerHeight` of **660x1429**. Every geometry
assertion silently measured a different, larger device, and a drawer that needed to
scroll appeared not to need it. Use a plain `viewport` — it reports truthfully:

```
plain 390x844    -> innerH=844  innerW=390    needsScroll=false
isMobile 390x844 -> innerH=1429 innerW=660    needsScroll=false   <-- wrong device
```

Also do not click a nav link that may sit outside the scrolled viewport (Playwright
retries 30s then dies "element is outside of the viewport"); click it through the DOM
so the assertion does not depend on scroll position:

```js
await page.evaluate((l) => {
  [...document.querySelectorAll('#selleragent-nav a')]
    .find((n) => n.textContent.trim().startsWith(l)).click();
}, label);
```

### Trap 2 — `documentElement.scrollWidth` is not an overflow signal here

It reports the **untruncated** width of wide descendants inside an `overflow-x:auto`
scroller even when the page itself cannot move, so a correctly-contained table reads
as a failure — while the actual panning bug on another route was only 415px against a
reported 805px. Both directions are wrong.

**Assert what the user experiences: can they pan the page?**

```js
const panX = () => page.evaluate(() => {
  window.scrollTo(99999, 0);
  const x = Math.round(window.scrollX);
  window.scrollTo(0, 0);
  return x;
});
// panX === 0 means the page is locked horizontally
```

A second corroborating signal: after panning, screenshot and look for the empty void.
The pan value alone is sufficient once calibrated.

## Suite shape

`scripts/mobile_drawer_verify.cjs` in this skill is the adapt-ready version: 28 checks
across 390x844, 375x667 and 1023px, plus a desktop 1440px guard asserting the sidebar
is still static and the burger/scrim are hidden. Run it **in addition to** the desktop
route suite, from the same deploy script, against the deployed URL.
