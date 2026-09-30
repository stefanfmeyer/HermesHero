# E2E Verification Lessons — Web Apps (the user's sessions)

Session-derived lessons for building + verifying user-facing apps. These complement
`browser-app-automation` (mechanics of driving the browser) and
`nextjs-development-patterns` (framework gotchas).

---

## 1. Test E2E with a real login before claiming complete (the user's rule)

the user's explicit correction: *"Please test e2e chat interactions/usage before saying
you have completed the task!"*

For any user-facing feature, "done" means:

1. Real browser (browser tool) against the actual host users will use (including
   tailnet hostnames, not just localhost).
2. Real login with the user's provided credentials.
3. Perform the core action the feature exists for (send a message, click the flow).
4. Confirm the visible result + zero console errors (`browser_console`).

A green unit-test suite and a passing production build are NOT completion. Unit tests
verify logic; E2E verifies the thing shipped.

---

## 2. `crypto.randomUUID` missing in non-secure contexts

**Symptom:** `Uncaught TypeError: crypto.randomUUID is not a function` on click/keydown,
only when the app is served over **plain HTTP on a non-localhost hostname** (tailnet
hostname like `http://myhost:3199`, LAN IP, internal DNS). Works in localhost testing;
breaks for the user on the first non-HTTPS host.

**Root cause:** `crypto.randomUUID()` is secure-context-only. HTTPS and `localhost`
have it; `http://<hostname>:<port>` does not.

**Fix — a `uuid()` helper with fallbacks, used everywhere client-side:**

```ts
export function uuid(): string {
  const c = globalThis.crypto;
  if (c && typeof c.randomUUID === "function") return c.randomUUID();
  if (c && typeof c.getRandomValues === "function") {
    return "10000000-1000-4000-8000-100000000000".replace(/[018]/g, (ch) => {
      const n = Number(ch);
      return (n ^ (c.getRandomValues(new Uint8Array(1))[0] & (15 >> (n / 4)))).toString(16);
    });
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (ch) => {
    const r = (Math.random() * 16) | 0;
    return ((ch === "x") ? ((r & 0x3) | 0x8) : (r & 0xf) | 0x8).toString(16);
  });
}
```

After scaffolding, grep client components for `crypto.randomUUID` — scaffold generators
and AI-written code reach for it by reflex. Same class of hazard: any other
secure-context-only API (`navigator.clipboard`, WebAuthn, service workers).

---

## 3. Multi-provider LLM selection: honest defaults

**Bug class:** The UI model-picker shows "Anthropic Claude Sonnet 4.5" by default, but
the client sends no model → server falls back to a hardcoded default whose API key is
NOT configured → user sees `Missing credentials ... set the OPENAI_API_KEY` (an
OpenAI-compatible SDK's confusing error naming a different provider than selected).

**Rules:**
1. The client ALWAYS sends its actual selection (`"<provider>:<model>"`); never depend
   on the server default matching what the UI displays.
2. The server default = **first provider with a configured key**, not a hardcoded one:
   ```ts
   function firstConfiguredProvider() {
     for (const p of PROVIDERS) if (providerApiKey(p.id)) return { provider: p.id, model: p.defaultModel };
     return null;
   }
   ```
3. Per-provider missing-key errors must name the provider and the remedy
   ("the anthropic API key is not configured on this server; pick another model…") —
   never surface the raw SDK error.
4. Model catalog endpoint only offers providers whose keys are configured.

---

## 4. Middleware auth ordering + self-authenticating API routes

Ordering bug: middleware checked `if (!user && isApiRoute) → 401` BEFORE the
public-path check, so an API route that authenticates itself (e.g. an MCP endpoint
verifying a Bearer token against Supabase) never received requests — it got the
middleware's 401.

Rules:
- `isPublic(pathname)` short-circuits FIRST → then API-401 → then page redirect.
- Any API route doing its own auth (Bearer/OAuth-client-credential style) must be
  exempted from cookie-based middleware.
- Verify against the BUILT bundle, not the source: `grep api/mcp
  .next/server/src/middleware.js` — and restart `next start`, because a stale server
  process serves the pre-fix bundle and poisons your verification.

---

## 5. Supabase Google OAuth: redirect allowlist fallback

**Symptom:** After Google consent, the user lands on the OLD app
(`https://app.example.com/dashboard`) instead of the new app's callback.

**Root cause:** Supabase Auth rejects any OAuth `redirect_to` not on the project's
allowlist and silently falls back to the project's **Site URL** (the main app's
domain). No error is shown anywhere — the user is just logged into the other app.

**Fix:** Supabase Dashboard → Authentication → URL Configuration → Redirect URLs →
add the app's callback origins (e.g. `http://myhost:3199/**`, prod domain). The
password (`signInWithPassword`) path is unaffected — it never leaves your domain.

**Verification trick without a Google account:** hit
`https://<supabase>/auth/v1/authorize?provider=google&redirect_to=<your-callback>`
and inspect the 302 chain — the flow is wired correctly if Google's consent URL comes
back with your `redirect_to` carried in `state`; the allowlist rejection only shows
at the end of a real consent.

Related: `devops/neon-auth-oauth-flows` covers the Neon/Better-Auth flavor of the
same problem class (OAuth cookies landing on the wrong domain).

---

## 6. Tenant isolation: user-JWT + RLS beats an admin-token proxy

When building a tenant-scoped surface (MCP server, chat API, BFF) over a Supabase
backend, two architectures exist:

**A. Admin/service token at the app layer (weaker):** server holds an admin token,
resolves the caller's org from the verified JWT, passes `org_id` explicitly on every
call. Problems: scoping rests on application code (a bug widens scope); admin token
is a single high-value secret; often the upstream API doesn't even accept it on all
routes (e.g. per-tenant write routes requiring per-tenant keys).

**B. User's own JWT + Postgres RLS (preferred, platform-native):** forward the
verified Supabase access token; the DB's RLS policies (`is_org_member(auth.uid(),
org_id)`) enforce isolation at the data layer. For reporting, prefer SECURITY DEFINER
RPC functions that filter by `auth.uid()` internally (e.g. a
`get_user_reporting_facts()` pattern) — the caller physically cannot read another
tenant's rows.

**Rules:**
- Audit BOTH read and write paths; isolation bugs usually hide in writes (the read
  path is what everyone tests).
- Defense in depth: even with RLS, keep schema validation on tool inputs (UUID
  checks) so injected `org_id` values die at validation, not at the DB.
- Write tests asserting the session's org is passed downstream and injected values
  are ignored/rejected — before claiming isolation is "done."
- Check what the upstream service actually accepts before designing around it
  (route-by-route: admin-only vs per-tenant-key vs user-JWT).

---

## 7. Print E2E: verifying output that goes to PAPER (hat drop, 2026-09-15)

A print feature cannot be verified by clicking the button — clicking proves nothing about
the paper. Full CSS pipeline in `project/web-microsite-builder` →
`references/print-that-actually-prints.md`; the browser-automation half:

- **`emulateMedia` sticks into `page.pdf()`.** A PDF captured after
  `emulateMedia({media:'screen'})` renders with SCREEN styles spread over pages — it looks
  plausible (right page count!) and is completely wrong. Always re-set
  `emulateMedia({media:'print'})` immediately before every `page.pdf()`.
- **Two-layer assertion:** (1) geometry in the DOM under print media
  (`getBoundingClientRect() / (96/25.4)` → exact mm) — the whole run must be exactly
  N×297mm (phantom blank pages come from a few mm of container padding), each piece at its
  claimed size; (2) an actual PDF whose QR codes are **decoded from the rendered pixels**
  (`pdftoppm -r 200` → jsQR) with a decoded-size assertion in mm.
- **QR decode from paper: jsQR + pngjs (pure JS), never pyzbar** (needs system libzbar,
  PEP-668 blocks the install). jsQR throws "Malformed data passed to binarizer" unless the
  buffer is exactly w×h×4 RGBA — pngjs can emit grayscale/RGB, normalise. Full-page decode
  FAILS for QRs on dark backgrounds (finder detection vs the dark surround) — fall back to
  quadrant crops and report `via: "page" | "region"`. The same decode-from-element trick
  works on the live app (ticket screens), not just PDFs: `locator.screenshot()` the
  `<img>` and decode — it proves a real scanner would read the user's screen.
- **Don't measure ink bounding boxes from rendered PDF pages** — mostly-white pieces give
  meaningless extents. DOM-under-print-media is the exact geometry source; use the PDF for
  page count + QR decode only.
- **Vision on a rendered PDF page is the fastest diagnostic.** The screenshot showing
  "card bottoms only, cut off at top" identified a page overflow that the numeric failures
  didn't.
- **`window.print` mock + timing:** mock print to only COUNT the call (a real dialog hangs
  headless), expose a `__fireAfterprint()` helper, and release it only when the test wants
  the post-dialog state — firing it synchronously restores any print-time DOM marks before
  the capture. Also assert marks are restored after (`data-print-hidden` etc.).

---

## 8. Assertion hygiene: false passes that read the WHOLE page (hat drop, 2026-09-16)

**The trap:** asserting an action worked with `await page.locator("body").innerText()`
then `text.includes(code)`. On a staff desk that renders a ledger table of EVERY issued
code, `includes(guestCode)` was true from page load — the assertion passed with zero
evidence the hand-over resolved. **A page-wide `includes()` proves nothing when the
page already lists the thing you're looking for.**

Rules:
- Assert on the **narrowest UI artifact that only renders after the action** — e.g.
  the `[role="status"]` hand-over confirmation panel, an error `<p role="status">`, a
  toast. Scope the locator, don't scan the body.
- Negative assertions (`not rendered`) must also be page-region-scoped, or they
  silently test the wrong thing.
- When a test "passes" on the first run after a rewrite, ask what SPECIFIC DOM state
  only exists because of the action under test. If you can't name it, the check is a
  smoke test, not an assertion.
- For "did the desk recognize this input?" style checks, read the component's own
  hint/legend text (`form p`) — it is scoped and it changes with input kind.

---

## 9. Click-toggle loops: opening cards twice closes them (same session)

Collapsible cards (`aria-expanded`) bite assertion code twice:

- **A click on an open card CLOSES it.** A loop that "opens everything" by clicking
  every matching button toggles already-open ones shut. Gate on state:
  ```js
  for (const btn of await page.locator('button:has-text("get_products")').all()) {
    if ((await btn.getAttribute("aria-expanded")) === "false") await btn.click();
  }
  ```
- **`"sel >> nth=1"` does not survive string surgery.** Building the selector as
  `` `button:has-text("${label.split(" >> ")[0]}")` `` throws away the `nth=` part and
  every iteration clicks `.first()` — open, close, open... The test took three runs
  to converge because each fix moved a different card. If a helper takes a
  Playwright selector, pass it through untouched.
- **Enter already submits.** In an input inside a `<form>`, `keyboard.press("Enter")`
  fires submit; a subsequent `click()` on the submit button finds it emptied and
  `disabled` and hangs 30s. Choose one submission path per test and assert the
  result of THAT path.
- **Regex patching via tool calls can double-escape.** Patching `\$$` through a
  Python/JSON layer produced `\\$` in the test file — the regex silently matched
  nothing and the assertion read `NaN`. After patching regexes in test files, run the
  file's own grep line or a one-liner to confirm the pattern still matches.

---

## 10. Console-error whitelists in Playwright watchers

Playwright's failed-fetch console error is `"Failed to load resource: the server
responded with a status of 401 ()"` — the STATUS is in the text but the URL is in
`m.location().url`, not the text. A whitelist matching `/40[149]/ && /\/api\//`
against text-only never matches, and deliberate UI states (401 pre-token poll, 404
unknown code, 409 replay) get reported as bugs:

```js
page.on("console", (m) => {
  if (m.type() !== "error") return;
  const t = m.text(), where = m.location?.()?.url || "";
  if (/40[149]/.test(t) && /\/api\//.test(where)) return;   // URL from location()
  if (/Failed to load resource/.test(t) && /40[149]/.test(t)) return;
  errors.push(`${label}: ${t} @ ${where}`);
});
```

Keep the whitelist to statuses the UI DELIBERATELY renders, and count + print
whatever survives — "0 errors" is only meaningful if the watcher would have caught one.

---

## 11. Read the screenshots — vision catches what assertions miss

After a green assertion run, actually LOOK at the E2E screenshots with vision. In the
hat-drop session the visual pass caught stale customer-facing copy ("One per badge."
on the ticket, "One hat per device." on the walled screen) that every assertion —
including a suite written specifically to check copy — had missed, because the
assertions checked the strings that were CHANGED, not the ones that SHOULD have been.

Rules:
- Vision-check the money screens (ticket/confirmation, error, refusal) on every E2E
  pass; the screenshots are already being taken.
- When the user specifies exact copy, grep the BUILT bundle for the stale variants
  too (`grep -c "One per badge" dist/assets/*.js`) — a fix that misses one string is
  invisible to a test that only asserts the new string exists.
- Then add a regression guard that asserts the ABSENCE of the stale string, not just
  the presence of the new one. Absence-checks are the ones that catch drift.
- Add copy regression guards to the suite that drives the screen the copy lives on
  (booth E2E for the walled screen, flow E2E for the ticket), not just one suite.

---

## 12. The booth-loop E2E pattern: verify the artifact chain, not app state (hat drop, 2026-09-16)

For a physical-flow demo (QR at a booth → code on a phone → desk redemption), assert
the chain the way the PHYSICAL world sees it:

1. Decode the SIGN's QR from pixels — it must point at the guest flow.
2. Run the guest flow; read the code as a human would (regex off the body text).
3. Decode the TICKET's QR from pixels (`locator.screenshot()` + jsQR) — proves a real
   scanner reads the user's screen.
4. Feed the decoded value to the desk UI; assert the hand-over confirmation panel
   names the guest's code and records the read mode ("QR scan").
5. Replay the same artifact — the second hand-over must be refused with the server's
   reason.
6. Feed an artifact that was never issued — refused, nothing issued.
7. The one-per-X wall: fresh context passes, same context walled with ITS OWN code
   back, clearing site data does not get through (the wall is server-side).
8. Server-side gates directly: unauthenticated ledger read → 401; the ledger row
   records `redeemedVia`.
9. The no-side-effect branch (refusal): arm a route spy on the minting endpoint and
   assert ZERO calls — a UI-only refusal that still mints is the failure mode.

This "decode from pixels + drive the real UI + spy the ledger" pattern transfers to
any flow where the test could otherwise end up verifying the app's internal state
against itself.

---

## 13. E2E that changes UI behavior requires re-walking the assertions (same session)

When a UI change lands (e.g. "collapse all payload cards by default"), the EXISTING
E2E suite is silently invalidated if it read text that is now hidden. The suite failed
three times before converging because each fix addressed one of: (a) cards must be
opened before reading, (b) the open-loop double-click bug, (c) the selector-surgery
bug. Rule: after any change to default visibility/collapse/scroll state, re-read the
E2E's text-extraction points and convert body-scoped greps to scoped, opened-card
reads BEFORE the first run, instead of discovering them by failure.

---

## 14. Honest-failure E2E: assert the RAW SSE stream, not only the DOM (AMA, 2026-09-16)

**The failure that taught this:** a prod E2E failed 4 honesty assertions (fabricated
creative in the reply) while the server-side guard was DEPLOYED, code-identical to
local (md5-verified), and its unit tests were green — and an isolated live repro of
the same flow PASSED. The intermittent shape pointed away from deployment and at the
reply text itself.

**Root cause chain, two layers deep:**
1. The model emitted the fabrication with markdown —
   `Here's **AI: the company Test Brand: Outdoor Enthusiast** — a card…`. The guard's
   regex wanted a literal `here's ai:` with a space; the `**` broke the match. A
   variants test proved **4 of 10 markdown rendering variants escaped the guard**
   while rendering as the SAME visible sentence.
2. The E2E's DOM assertions couldn't catch it: `innerText` strips the asterisks, so
   the fabrication read as clean plain text in the DOM while the raw stream carried
   the bolded name. DOM-green + unit-green + deployed = still shipped.

**Rules for honesty/fabrication E2E:**
- Capture the SSE frames and reconstruct the RAW stream — the accumulated `text`
  deltas plus whether a `replace` (server rewrite) event fired:
  ```python
  def raw_stream(frames):
      text, replaced = "", False
      for f in frames:
          for line in f.split("\n"):
              if not line.startswith("data:"):
                  continue
              try: ev = json.loads(line[5:].strip())
              except Exception: continue
              if ev.get("type") == "text":   text += ev.get("delta") or ""
              elif ev.get("type") == "replace": replaced = True; text = ev.get("content") or ""
      return text, replaced
  ```
  Frame capture: `page.on("response", lambda r: asyncio.create_task(on_resp(r)))` with
  `frames.append(await resp.text())` inside try/except.
- Assert BOTH layers: DOM (what the user sees) AND raw stream (what was sent, and
  whether the guard's replacement fired).
- **An over-strict honesty check false-fails on honest replies.** First version
  banned any mention of the fabricated name in the raw stream — but the honest reply
  legitimately echoes it ("I couldn't find a creative with that exact name"). Ban the
  ASSERTION shape (DOM pattern with emphasis markers made optional, run against
  de-marked text), never the bare name.
- **Regex-validating LLM output: strip markdown before matching, always.** Models
  wrap names in `**bold**` / `*italics*` / backticks. De-mark (`re.sub(r"[*`_]",
  "", s)`), normalise curly quotes, and unit-test every pattern in BOTH plain and
  emphasised forms. Deployment/identity checks (md5 source, grep built bundle for a
  unique string) rule out staleness — when those pass but prod fails intermittently,
  suspect the reply TEXT rendering, not the deployment.
- **Add an over-fire check to guard suites:** with a SUCCESSFUL lookup in the turn,
  assert NO `replace` event fired — a guard that clobbers true answers is as bad as
  one that misses fabrications.
- **Intermittent E2E honesty failures are signal, not noise.** The isolated repro
  passing while the suite failed was the key clue: it meant the guard's *recognition*
  depended on the reply's phrasing that turn. Reproduce with raw-SSE capture before
  concluding "flaky model".

---

## 15. LLM-app honesty suites: assertion inventory (AMA, 2026-09-16)

Beyond what to stream-assert, the shape of a full honesty suite for a tool-calling
chat app (64 assertions in the AMA suite, sections = flows):

- **Per-flow tool discipline:** one lookup for "show ONE creative" (assert the
  specific tool was called AND the bulk tool was NOT), one call for coverage
  questions (no per-campaign loop), deltas not totals on cumulative DOM.
- **Honest failure shape:** soft error surfaces on the tool card (`{error: ...}` in
  the SSE `tool_result`), card shows the reason not "running…", gallery never
  contains the fabricated name, reply admits not-found, no "artwork displayed"
  claim, no display-excuse narration, no UI narration ("the card above").
- **Cross-org/inaccessible entities:** tool reports `unresolved_links`, card does
  not read "0 rows", reply explains "not accessible in your organization", no
  fabricated fallback in any gallery.
- **Over-fire check:** the honest success flow must NEVER be rewritten by the guard.
- Chips contextual, not canned; write-confirmation gate actually gates; raw-stream
  honesty for every failure flow** (14 above).
- Console-error watcher with a whitelist for deliberately-rendered statuses (10
  above); mobile 390 layout block per `browser-app-automation` (Playwright headless
  for viewport claims).

---

## 16. Gate card assertions on the tool call; keep honesty assertions unconditional
(AMA, 2026-09-16)

Two suite runs failed `soft error surfaced on the card` and `card shows the failure
reason, not 'done'` while EVERY honesty assertion passed. Measured the cause instead
of re-running and hoping:

| context | `get_creative` called | card shows error |
|---|---|---|
| a preceding turn already LISTED creatives | **1/4 runs** | 1/4 |
| no such preceding turn | **4/4 runs** | 4/4 |

In the failing runs the model made **zero tool calls** (`calls=[]`) and answered
from the listing it had seen a turn earlier — its reply was still honest
(`I couldn't find a creative with that exact name`), so no error card existed to
assert on. That is **prompt adherence, not dishonesty**, and conflating the two
makes a suite that cries wolf.

**Rules:**
- Card/UI assertions that presuppose a tool ran must be **gated on that tool having
  been called** in the turn; print `[SKIP] … (no lookup this turn)` when it wasn't,
  rather than passing vacuously or failing spuriously.
- **Honesty assertions stay unconditional.** No fabrication in the reply, the raw
  stream, or any rendered gallery — checked on every run regardless of which path
  the model took.
- Do NOT relax this into "the assertion is flaky, delete it". Separate the two
  claims (did it look up? / was it honest?) and keep maximum pressure on honesty.
- Diagnose suite-only flakes by **bisecting the conversation context**, not by
  re-running: the isolated repro passed 6/6 because it lacked the preceding turn;
  reproducing the suite's exact context produced the failure reliably.
- When the model skips a mandated call, the durable fix is a sharper prompt rule
  plus the gated assertion — the guard cannot manufacture a lookup that never
  happened.
