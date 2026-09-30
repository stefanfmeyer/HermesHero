# Selectable vs clickable: making a clickable label copyable

Session: the company AMA landing hero, 2026-09-16. Request: *"ensure this section on
the main chat… you cannot copy/select with mouse… Only quick message buttons in
this area should be clickable/selectable."*

This cost four deploy cycles because the symptom ("the text can't be selected")
pointed at CSS and the actual blocker was an event-ordering conflict. The
diagnostic ladder below is the reusable part.

## Final working implementation

```tsx
const DRAG_THRESHOLD_PX = 4;

function StarterCard({ text, onSend }: { text: string; onSend: (t: string) => void }) {
  const downAt = useRef<{ x: number; y: number } | null>(null);
  const dragged = useRef(false);
  return (
    <div
      // NOT a <button>: Chromium refuses drag-selection inside button elements.
      role="button"
      tabIndex={0}                        // keyboard activation preserved
      onPointerDown={(e) => { downAt.current = { x: e.clientX, y: e.clientY }; dragged.current = false; }}
      onPointerMove={(e) => {
        const d = downAt.current;
        if (!d || dragged.current) return;
        if (Math.abs(e.clientX - d.x) > DRAG_THRESHOLD_PX ||
            Math.abs(e.clientY - d.y) > DRAG_THRESHOLD_PX) dragged.current = true;
      }}
      onClick={() => {
        if (dragged.current) return;      // a drag means "copy", not "send"
        onSend(text);
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSend(text); }
      }}
      className="cursor-pointer select-text …"
    >
      {text}
    </div>
  );
}
```

Decorative chrome around it: `select-none` on the hero wrapper, `draggable={false}`
+ `pointer-events-none` on the logos.

## Diagnostic ladder (run in this order)

### 1. Confirm ancestors are not the cause

Append a `user-select:text` span INSIDE the suspect `select-none` parent and drag
it. Result: **selected 21 chars** — an ancestor `user-select:none` does NOT block
a descendant that opts back in. This clears the wrapper and saves you from
"fixing" it by removing `select-none` (which re-breaks the requirement that the
chrome be unselectable).

### 2. Synthetic probe: is the TAG the problem?

Inject identical elements with a known `user-select` into the live page and run
the same drag on each:

| probe | tag | user-select | drag result |
|---|---|---|---|
| A | `<span>` | text | **24 chars selected** |
| B | `<button>` | text | **0** |
| C | `<div>` | none | 0 (control) |

A selects, B does not ⇒ **Chromium refuses selection inside `<button>` regardless
of `user-select`.** Pre-existing browser behaviour. No amount of CSS fixes it;
the label must leave the button element.

### 3. Convert to `role="button"` div — then discover it STILL fails

After the conversion the text computed `user-select: text` and was still not
selectable. This is the step where a CSS-first mindset wastes a cycle.

### 4. Instrument the event order

Capture-phase listeners + a MutationObserver, then run one drag and read the log:

```
EV:selectstart  t=5583
EV:click        t=6391
DOC:click       t=6391
CARD_REMOVED    t=6403     <- React unmounted the card
NODE_ADDED:DIV  t=6403     <- view swapped to the chat
FINAL sel=0 bubbles=1      <- message was sent
```

**Root cause: `selectstart` fired (selection began), but `click` also fired at
mouseup because the pointer was still inside a clickable element.** The handler
sent the message, the hero unmounted, and the selection died with it. `user-select`
was never the blocker.

### 5. First guard attempt: `window.getSelection()` — REJECTED

```tsx
onClick={() => {
  const sel = window.getSelection();
  if (sel && sel.toString().trim().length > 0) return;   // ← unreliable
  send(s);
}}
```

Rationale seemed sound (Chromium clears the selection on a plain mousedown, so a
live non-empty selection at click time can only come from a drag). It passed the
first test round. Then the trial matrix exposed the hole:

| drag pattern | selection | outcome |
|---|---|---|
| fast discrete moves (12×16px) | 0 | did not send ✅ |
| slower moves (12×16px, 250ms) | 0 | did not send ✅ |
| few big jumps (3×60px) | 0 | did not send ✅ |
| **one big jump (1×150px)** | **0** | **SENT ❌** |

A drag started on the card's **padding** never forms a selection, yet still
clicks. The guard would have shipped an intermittent bug: copy the label from the
text → fine; start the drag in the whitespace → the message sends.
**Selection state is not a proxy for "the user was dragging".**

### 6. Pointer-travel threshold — the reliable signal

Track `clientX/Y` on pointerdown, set a `dragged` flag past ~4px, early-return
from `onClick`. A real drag moves far past 4px; a click does not. Verified across
all four drag patterns plus clean click and keyboard Enter.

## Verification matrix (the assertion set worth keeping)

| # | gesture | expected |
|---|---|---|
| 1 | drag across heading / "Powered by" | selects nothing |
| 2 | drag across the label's text | selects it, does NOT send |
| 3 | drag across the label's padding | does NOT send ← the case that broke the guard |
| 4 | clean click | sends |
| 5 | Enter on focused label | sends |
| 6 | drag across an unrelated chat reply | still selectable (copy unaffected) |

Case 6 is easy to false-FAIL: sweep at the text's own y, not the container's top
edge, or the bubble's `py-4` padding yields `sel=0` on a correct app. Verified
the reply is selectable (up to 97 chars at mid-height, 0 at the top padding).

## Gotchas

- **E2E selectors that match on `button` break silently.** Moving labels out of
  `<button>` made `querySelectorAll('button')` stop counting the starter cards.
  Match the accessible role instead: `'button, [role="button"]'`. Update BOTH the
  probe and any "returns to landing state" assertion.
- **`stopPropagation` on rail/nav items** whose parent has a click handler (e.g.
  a main-column click-outside that closes a sidebar) — otherwise tapping an icon
  also toggles the sidebar.
- **Keep the guard comment explaining why `getSelection()` was rejected**, or a
  future reader will "simplify" the threshold check back into the broken version.
- The full fix shipped as three commits (make chrome unselectable → move labels
  out of `<button>` → threshold guard) because each step revealed the next layer.
  Expect two or three, not one.
