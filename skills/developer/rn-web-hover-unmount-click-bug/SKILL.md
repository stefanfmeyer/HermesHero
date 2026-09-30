---
name: rn-web-hover-unmount-click-bug
description: Diagnose react-native-web "button cannot be clicked" bugs — hover-reveal unmounts the control mid-press. Repro method, measurement, and the fix pattern.
tags: [react-native, react-native-web, playwright, debugging, e2e]
---

# RN-web: hover-reveal unmounts the button mid-click

## Symptom

A button that appears on hover cannot be clicked. It renders, hit-testing finds
it, Playwright "clicks" it — and nothing happens. No dialog, no navigation, no
error. It looks like a z-index/overlay problem. It usually is not.

## The mechanism (hover feedback loop)

Hover-reveal on a child of the hovered parent is a feedback loop:

1. Pointer over the parent → parent's hover state true → child button mounts
2. Pointer moves onto the child button itself → react-native-web fires the
   parent's `onHoverOut` (the pointer's target node changed)
3. Hover state false → child **unmounts under the pointer**
4. Pointer is now over the parent again → `onHoverIn` → re-mount → repeat

A click pressed the button down while mounted and released after it vanished,
so the browser never fires `click`. Measured event trace of the broken case:

```
pointerdown: <child-button>      ← correct target
pointerup:   <parent-row>        ← button already gone
(click event: never fired)
```

## How to prove it (Playwright, 15 lines)

Sample the element's presence while the pointer rests ON it:

```js
// pointer parked at the button's centre
const states = [];
for (let i = 0; i < 12; i++) {
  states.push(await page.evaluate(
    () => document.querySelectorAll('[data-testid="the-button"]').length));
  await page.wait_for_timeout(50);
}
// Broken: [0,0,0,1,1,1,0,0,0,0,1,1]   (flicker — 45 mutations during approach)
// Fixed:  [1,1,1,1,1,1,1,1,1,1,1,1]   (stable)
```

Confirm the event trace with a capturing listener (sees the true target
top-down):

```js
document.addEventListener('pointerdown', e => log(tid(e.target)), true);
document.addEventListener('pointerup',   e => log(tid(e.target)), true);
document.addEventListener('click',       e => log(tid(e.target)), true);
// Broken: ['pointerdown:child-btn', 'pointerup:parent-row'] and NO click
```

`elementFromPoint` at the button's centre returning one of the button's own
descendants is NOT an overlay — it is expected (children paint above the
parent). Chasing a phantom overlay wastes time; check for the flicker instead.

## The fix

Remove the conditional render, not the click handler. Make the control always
visible (this was also the product call — hover-reveal hides the affordance
from users who do not know to look). If a destructive action should stay
unobtrusive, reserve its slot unconditionally (fixed width/height) so the row
never reflows, and keep the touch-native gesture (swipe-to-reveal) as a second
path.

## E2E regression guards

- Assert the control is present with the pointer parked AWAY (catches
  reintroduced hover-reveal).
- Assert it stays mounted across ~8 samples with the pointer ON it (catches
  the flicker).
- Click it and assert the downstream effect (dialog opens, row count drops).

## Case study

AMA app sidebar trash (`components/chat/Sidebar.tsx`): hover-reveal on web,
swipe on touch. The trash was literally unclickable; fixed by rendering it
always, keeping swipe-to-reveal on touch. 66/66 e2e after the change.
Verified live at https://server.example.com:3400.