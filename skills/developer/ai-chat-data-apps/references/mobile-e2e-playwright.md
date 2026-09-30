# Mobile E2E for chat UIs — working Playwright recipe

Verified 2026-09-14 against AMA (Next.js 15 chat app). Reuse with modifications.

## Setup gotchas (fresh venv)

- System python is PEP-668 managed: `python3 -m venv /tmp/pw-venv && /tmp/pw-venv/bin/pip install playwright`.
- Playwright latest wants its OWN browser revision even when
  `~/.cache/ms-playwright` has chromium builds from another install —
  either `playwright install chromium-headless-shell` (2.3 MiB, fast) or pin
  the playwright version that matches the cached build. The mismatch error
  names the exact missing revision dir. (Hit 2026-09-14: cached
  chromium-1243 + latest pip playwright wanted chromium_headless_shell-1234;
  pinning `playwright==1.49.1` alone did NOT match either — the reliable fix
  was running `pw-venv/bin/python -m playwright install chromium-headless-shell`
  once, then system-cached browsers worked.)
- Image-upload E2E: `page.expect_file_chooser()` around the `+` click, then
  `chooser.set_files([{name, mimeType, buffer}])` with real image bytes
  (fetched from the app itself, e.g. the logo URL). Anthropic rejects
  synthetic 1×1 base64 PNGs with "Could not process image" — not a bug in
  the upload path.

## The script (mobile iPhone profile, real login, full assertion set)

```python
import asyncio, json
from playwright.async_api import async_playwright

URL = "https://your-app.example"   # app base URL

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=3,
            is_mobile=True,
            has_touch=True,
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        )
        page = await ctx.new_page()
        await page.goto(URL + "/login")
        await page.fill('input[type="email"]', EMAIL)
        await page.fill('input[type="password"]', PASSWORD)
        await page.click('button:has-text("Sign in")')
        await page.wait_for_url("**/chat", timeout=20000)
        await page.wait_for_timeout(1500)

        # fresh state for deterministic screenshots
        await page.evaluate("localStorage.removeItem('ama_conversations')")
        await page.reload(); await page.wait_for_timeout(1500)

        # 1) no horizontal scroll on empty state + 16px input font + viewport meta
        m = await page.evaluate("""() => ({
            innerWidth: window.innerWidth,
            scrollWidth: document.documentElement.scrollWidth,
            overflowX: document.documentElement.scrollWidth > window.innerWidth,
            taFont: getComputedStyle(document.querySelector('textarea')).fontSize,
            viewportMeta: document.querySelector('meta[name=viewport]')?.content,
        })""")
        assert not m["overflowX"], m
        assert m["taFont"] == "16px", m   # iOS zoom prevention
        await page.screenshot(path="/tmp/mobile_home.png")

        # 2) still no overflow mid-conversation (wide tables break only when rendered)
        await page.fill("textarea", "What campaigns am I running?")
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(14000)
        m2 = await page.evaluate("() => ({overflowX: document.documentElement.scrollWidth > window.innerWidth})")
        assert not m2["overflowX"], m2
        await page.screenshot(path="/tmp/mobile_chat.png")

        # 3) drawer open state
        await page.click('button[title="Toggle sidebar"]')
        await page.wait_for_timeout(500)
        await page.screenshot(path="/tmp/mobile_drawer.png")

        await browser.close()

asyncio.run(main())
```

## What to actually assert (the four failure modes that matter)

1. `scrollWidth == innerWidth` on the empty state AND after a table-heavy
   reply — tables are the only element that reliably forces overflow.
2. Textarea computed font-size = 16px on <768px. If 14px, iOS will zoom the
   viewport on focus; the CSS override lives in globals.css
   (`@media (max-width: 767px) { input, textarea, select { font-size: 16px !important; } }`).
3. Viewport meta contains `maximum-scale=1` (belt) — but the 16px rule is the
   real fix (braces).
4. Screenshots at each state, inspected with vision, not trusted from metrics
   alone — the model-picker 3-line wrap bug passed all numeric checks and was
   only caught visually.

## Login form gotcha

If programmatic `.click()` on the submit button from a JS bridge doesn't
navigate, the button may be a Next.js form-submit: drive it from a real
Playwright click as in the script (never `requestSubmit` from the page's own
console when testing the deployed artifact — you want to exercise what a
user exercises).

## Touch gestures: how to actually fire a touch-only handler

A swipe handler written as `if (e.pointerType !== "touch") return;` is
invisible to most test driving. Each of these fails, and the failure is
SILENT — the row simply doesn't move, so it looks like a product bug:

| Attempt | Why it fails |
|---|---|
| `page.mouse.down/move/up` | synthesized as `pointerType: "mouse"` |
| `locator.drag_to(...)` | same — mouse |
| `page.touchscreen.tap()` | taps only, no move/drag sequence |
| CDP `Input.dispatchTouchEvent` | Chromium did NOT deliver these to the page listener in this setup (0 events logged) |

**What works** — dispatch synthetic `PointerEvent`s with an explicit
`pointerType: 'touch'` inside one `evaluate`, so the handler sees a real
`touch` sequence:

```js
await page.evaluate((idx) => {
  const w = document.querySelectorAll('aside nav > div.relative.overflow-hidden')[idx];
  const row = w.querySelector(':scope > div');
  const r = w.getBoundingClientRect();
  const y  = Math.round(r.y + r.height / 2);
  const x0 = Math.round(r.x + r.width - 24);    // start near the right edge
  const x1 = Math.round(r.x + r.width - 160);   // drag left past the threshold
  const mk = (t, x) => new PointerEvent(t, {
    pointerType: 'touch', clientX: x, clientY: y, bubbles: true,
    cancelable: true, pointerId: 1, isPrimary: true,
    buttons: t === 'pointerup' ? 0 : 1,
  });
  row.dispatchEvent(mk('pointerdown', x0));
  for (let k = 1; k <= 12; k++) row.dispatchEvent(mk('pointermove', x0 + (x1 - x0) * k / 12));
  row.dispatchEvent(mk('pointerup', x1));
}, 0);
await page.wait_for_timeout(450);   // let the snap transition settle
```

Assert the outcome from computed style, not the class string:

```js
{ transform: row.style.transform,            // expect translateX(-72px)
  btnOpacity: getComputedStyle(btn).opacity, // expect 1
  btnPE: getComputedStyle(btn).pointerEvents } // expect auto
```

**Debugging tip that paid for itself**: instrument the handler first. Attach
`pointerdown/move/up` listeners that push `e.pointerType` into
`window.__seen`, then try each input method and read `__seen`. `['pointerdown:touch', ...]`
confirms the handler is reachable; an empty array means your input method
never produced touch events — a harness problem, not a product problem.

Also verify the tap-after-reveal and Cancel paths, not just Delete:
tap-while-revealed must snap shut (`translateX(0px)`) instead of opening the
chat, and Cancel must leave the item count unchanged.

## Never name a scratch script after a stdlib module

A one-off probe saved as `/tmp/inspect.py` broke the entire test harness with
a confusing error that points nowhere near the real cause:

```
ImportError: cannot import name 'AbstractEventLoop' from partially initialized
module 'asyncio' (most likely due to a circular import) (/usr/lib/python3.13/asyncio/__init__.py)
```

Nothing is wrong with `asyncio`. Python puts the script's own directory on
`sys.path` FIRST, so `import inspect` (pulled in transitively by playwright's
own imports) resolved to `/tmp/inspect.py` instead of the stdlib module — and
the partially-initialized-module cascade surfaced as an `asyncio` failure.

Rule: name throwaway probes for the TASK, never a module —
`composer_probe.py`, `spin_test.py`, `swipe_probe.py`. Avoid `inspect.py`,
`json.py`, `types.py`, `select.py`, `test.py`, `email.py`, `code.py`, `copy.py`.
If you see a circular-import error in a stdlib module you never touched,
suspect a shadowing filename in the working directory before suspecting the
interpreter.

## Scope DOM probes to a container — shared class tokens lie

When asserting on "the assistant bubbles", do NOT select by the classes they
visually share with other surfaces. In this app family the COMPOSER pill also
carries `rounded-[28px] bg-card`, so

```js
[...document.querySelectorAll('div')].filter(d =>
  d.className.includes('bg-card') && d.className.includes('rounded-[28px]'))
```

returns the composer as the last "bubble". Ordered assertions built on it
(`bubbles[bubbles.length-1].contains(spinner)`) then report a **false**
"spinner on an earlier message" — a product bug that does not exist, which is
the worst kind of test failure because it sends you editing working code.

Scope to the container that uniquely owns the region, then walk its children:

```js
const root = [...document.querySelectorAll('div')].find(d =>
    typeof d.className === 'string' && d.className.trim() === 'space-y-8');
const kids = [...root.children];   // one child per message, in order
```

Two supporting rules:
- `className` is not always a string (SVG elements give an `SVGAnimatedString`),
  so guard with `typeof d.className === 'string'` before `.includes`.
- Escape hatch for Tailwind arbitrary values in `page.evaluate` strings:
  `div.rounded-\[28px\].bg-card` is fragile through Python→JS quoting. Prefer
  comparing class names in JS over writing them into a CSS selector. A
  `SyntaxError: … is not a valid selector` naming your Tailwind class means the
  backslashes didn't survive the Python→JS→CSS chain — switch to a JS
  `className.includes(...)` filter immediately instead of adding more escaping.

## Finding the real send control before driving it

`page.click('form button')` and `button:has-text("Send")` both time out on
this app family because there is **no `<form>`** — the composer is a bare
`div` with a `<textarea>` and buttons whose only handle is an aria-label.
Probe once and print, instead of guessing selectors:

```js
// what buttons actually exist beside the composer, and what are they?
[...document.querySelector('textarea').closest('div').parentElement
   .querySelectorAll('button')].map(b => ({title: b.title, aria: b.getAttribute('aria-label'), type: b.type}))
```

The send control here is `button[aria-label="Send"]` (and the `+` is
`button[title="Upload image"]`). Note the `+`/send buttons carry
`type="submit"` despite no ancestor form — so `type` is not a reliable signal
either. Print the inventory; then click the exact handle.

## Attribute a failure before reporting it

Every one of these failures was a harness bug, not a product bug — and each
looked exactly like one:

| Symptom | Actually was |
|---|---|
| Row never moved after a drag | `page.mouse` emits `pointerType: "mouse"`; handler is touch-only |
| "No saved chats" rendered, row selectors timed out | seed interpolated as `[object Object]` |
| Spinner "on an earlier message" | probe matched the composer pill |
| `click()` timed out, "subtree intercepts pointer events" | clicking a `pointer-events-none` inner node instead of its handler row |
| Every playwright import died with an `asyncio` circular-import error | the probe script was named `/tmp/inspect.py`, shadowing the stdlib module |
| `page.click('form button')` timed out | there is no `<form>`; the send button is `button[aria-label="Send"]` |
| `is not a valid selector` naming a Tailwind class | `rounded-\[28px\]` backslashes lost through Python→JS→CSS; use a JS `className.includes()` filter |

Rule: when an assertion fails, re-derive the FIXTURE and the SELECTOR before
touching product code. Print the seeded storage value and the container's
`outerHTML`; if the empty state or the composer shows up in that output, you
are testing wrong, not fixing a bug. Report harness vs product distinctly —
never quietly retry until green.

A self-hosted font that "looks fine" is not evidence it loaded. A
fallback-font render is nearly indistinguishable in a screenshot, and the
failure is visible only in the console.

**Symptom**: `Failed to decode downloaded font: …/GoogleSans-400.woff2` plus
`OTS parsing error: invalid sfntVersion: 1008813135`. That magic number is
the bytes `<!DO` — i.e. the server returned an **HTML page** where a font was
requested (here: a 307 redirect to `/login`).

**Root cause class**: an auth middleware whose matcher excludes only
`svg|png|jpg|jpeg|gif|webp|ico` intercepts `woff2/woff/ttf/otf` and
redirects them to the login route. The font then "works" in dev (where the
middleware may not run) and silently fails in production.

**Fix** — add font extensions to the exclusion set:
```ts
"/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico|woff2?|ttf|otf)$).*)"
```

**Verify with three checks, not one** (curl alone would also pass if a
proxy returned HTML with 200):
1. `curl -D -` → status `200`, `content-type: font/woff2`, exact byte size
2. `document.fonts` → `['Google Sans/400/loaded', 'Google Sans/500/loaded']`
   (`error` status is the tell)
3. `getComputedStyle(document.body).fontFamily` → resolves to the real family

Local sanity check that the file is genuine before blaming the server:
`open(f,'rb').read()[:4] == b'wOF2'`.

## Seeding localStorage — the `[object Object]` trap

To get deterministic rows/fixtures, seed storage before reload. Doing it by
interpolating a Python object into the JS string silently produces garbage:

```python
# ❌ BAD — Python list interpolates via repr/str → JS sees an OBJECT, not JSON
await page.evaluate(f"localStorage.setItem('ama_conversations', {SEED_LIST})")
# stored value becomes the literal string "[object Object],[object Object]"
# → your UI renders its "No saved chats" empty state, your row selectors time
#   out, and it reads exactly like a broken feature
```

```python
# ✅ GOOD — pass the JSON string as an ARGUMENT; Playwright serializes it correctly
SEED = json.dumps([{"id": "a", "title": "Chat A", "messages": [], "updatedAt": 3}])
await page.evaluate("(v) => localStorage.setItem('ama_conversations', v)", SEED)
```

Always read it back and print before asserting on the UI:

```python
print(await page.evaluate("() => localStorage.getItem('ama_conversations')"))
```

**Generalisation**: when a selector times out on the deployed app, verify the
FIXTURE before the FEATURE. Query the DOM for the container's `outerHTML` —
seeing the deliberate "no saved chats" empty state proves the seed didn't
land, which is a different bug from "the row component is broken".

## Re-running against a redeployed build

- Each fresh browser context starts logged-out; the script's login step
  handles it, but the shared interactive browser session may hold stale
  localStorage (old theme key, old conversation shape). Prefer the
  headless script over the shared session for final verification.
- A new context that skips login (navigating straight to /chat) times out
  waiting for UI selectors — every context must do the real login first.
- Re-run the FULL script after every polish commit (e.g. picker nowrap
  fixes), not just the first run: the fix that passed can regress the next
  deploy if the final script run was against an older build.