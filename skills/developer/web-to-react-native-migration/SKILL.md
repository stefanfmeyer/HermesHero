---
name: web-to-react-native-migration
description: Plan, scope AND EXECUTE porting an existing Next.js/web app to React Native (Expo) for iOS + Android while keeping desktop working. Covers the server-secret constraint that forbids a pure client rewrite, the cookie-middleware trap that silently blocks every native request, the SSE/streaming risk, per-platform glass/blur fidelity, what ports verbatim vs must be rewritten, RN-web layout traps (flex vs width, UA focus rings), repo strategy, browser-based verification of the RN-web build, and how to write then run the migration plan.
trigger: Asked to "switch the architecture to React Native", "make this great on mobile and desktop", "do the complete port over to React Native", port a web app to Expo/iOS/Android, or evaluate whether a mobile app can reuse an existing web codebase. Also covers the execution phase — enabling Bearer auth on the server, building the Expo client, and verifying it.
tags: [react-native, expo, migration, mobile, nextjs, architecture, execution]
---

# Web → React Native Migration

Class-level playbook for porting an existing web app (typically Next.js App
Router) to React Native / Expo so it ships on iOS + Android, without breaking the
desktop experience.

**Default stance: this is a CLIENT migration, not a rewrite.** Establish that
first — it changes the whole plan.

**Steps 1–7 are planning. Step 8 is the traps that only appear when you execute.**
If you have been asked to do the port (not just scope it), read Step 8 before
writing code — it lists the server changes that will silently block the client.

## Step 1 — Find the constraint that decides the architecture

Before planning anything, grep the env/secret surface and ask: *what must never
reach a device?*

Look for LLM provider keys, service-role/admin DB keys, and any key that bypasses
row-level security:

```bash
grep -oE '^[A-Z_]+=' .env.production | sort -u
grep -rn "process.env" src/app/api --include=*.ts | head
```

If the answer is "the app calls an LLM / a privileged API with a server-side key",
then **the server cannot be dropped.** A mobile bundle is trivially unpacked from
the IPA/APK, so shipping those keys hands every user the billing credential — and a
Supabase `SERVICE_ROLE_KEY` bypasses RLS entirely, moving the tenant boundary out
of Postgres and into client code.

Consequence: the RN app is a **pure client** against the existing backend. The
tool layer, LLM orchestration, and any server-side guard stay exactly where they
are and need **zero** porting work. Say this explicitly — it is the single biggest
scope reduction available and users usually fear the opposite.

## Step 2 — Check whether the API already supports token auth

The migration usually hinges on one small change. Look for an existing
optional-token code path:

```bash
grep -rn "accessToken\|Bearer\|authorization" src/lib/auth.ts src/app/api/*/route.ts
```

Common finding: an `resolveAuthContext(accessToken?: string)` already exists for a
secondary endpoint (e.g. an MCP route), while the main chat route is cookie-only.
Then the enabling change is **one line** — read `Authorization: Bearer <token>`
and pass it through, falling back to cookies. No auth redesign. Lead the plan with
this, because it converts a scary migration into a tractable one.

Also budget for **CORS**: a separate-origin native client needs preflight handling
that a same-origin web app never did.

## Step 3 — Freeze the wire protocol

Whatever the client consumes (SSE events, JSON shapes) becomes the contract that
makes the port tractable. Enumerate the event types from the server, then note that
the RN client re-implements the *same* switch statement. Quote the exact event names
in the plan — this is what lets the UI be "re-rendered against an unchanged
contract" rather than reinterpreted.

## Step 4 — Inventory the client honestly, by porting character

Do not present this as a refactor. Count the lines and classify each area:

| Class | Examples | Effort |
|---|---|---|
| **Verbatim** | pure helpers, parsers, guards, formatters (no DOM/React) | copy unchanged; check with `grep -cE "document\.\|window\.\|useState"` returning 0 |
| **Rewrite** | bespoke visual effects (SVG-filter refraction, WebGL, canvas) | full rewrite — plan it as its own workstream, never a "port" |
| **Substantial** | main shell, layout, gestures, tables, markdown | `div`→`View`, `button`→`Pressable`, `matchMedia`→`useWindowDimensions`, CSS overflow→`ScrollView`/`FlatList`, absolute+translate gestures→`react-native-gesture-handler` |
| **Small** | login, pickers, static screens | straightforward |

Run this to size it before promising anything:
```bash
find src -type f \( -name "*.tsx" -o -name "*.ts" \) | xargs wc -l | sort -rn | head -20
for a in "document\." "window\." "localStorage" "backdrop-filter" "PointerEvent"; do
  echo "$a -> $(grep -rl "$a" src/ | wc -l) files"; done
```

## Step 5 — Name the fidelity tradeoff instead of hiding it

Custom visual effects are where "just port it" breaks. React Native has **no
`backdrop-filter` and no SVG filter chain** in either native renderer, so
web-only effects (e.g. `feDisplacementMap` refraction) cannot be reproduced. Native
gives *different*, not identical, results:

| Platform | Implementation | Fidelity |
|---|---|---|
| iOS 26+ | `expo-glass-effect` (`GlassView`, native `UIGlassEffect`) | genuine system glass — arguably better, **not pixel-identical** |
| iOS < 26 | `expo-blur` `BlurView` | frosted only |
| Android 33+ | `react-native-liquid-glassmorphism` (RenderEffect + AGSL) | closest to web refraction |
| Android < 33 | `expo-blur` | frosted only |
| Web (RN Web) | the **existing** CSS/SVG path still works in Blink | identical to today |

Present it as a decision for the user, not a footnote, and offer a scoped option
where mobile ships simplified native glass and web keeps the true effect.

## Step 6 — Know the RN platform gotchas before writing the plan

- **Streaming is the #1 risk — de-risk it FIRST, before any UI work.** Stock React
  Native `fetch` does **not** expose `response.body.getReader()`. Expo SDK 52+ ships
  `expo/fetch`, which supports streaming; alternatives are `react-native-sse` or an
  XHR-based SSE reader. If streaming does not work, nothing else matters, so make it
  the first task after auth.
- **Desktop via React Native Web is still DOM.** "Great on desktop" from RN means a
  client-rendered SPA, not anything architecturally new. You lose SSR (usually
  irrelevant for an authed chat app) and gain a separate-origin API (needs CORS).
  If the real pain is mobile, a **mobile-only** build that leaves the web app
  untouched is ~60% of the work with none of the RN Web risk — always offer it.
- **Auth storage differs per platform:** `expo-secure-store` on native,
  `AsyncStorage` on web, behind one adapter interface passed to the Supabase client.
- **OAuth deep links need a redirect URL registered** (`myscheme://`) in the auth
  provider's allowlist — the native twin of the web redirect-allowlist trap.
- `react-markdown` has no RN equivalent — use `react-native-markdown-display`.
  Two things it needs that the docs do not make obvious: enable `mergeStyle`, or
  your partial style map silently deletes the library's layout defaults (tables
  collapse to a single column — see Step 8.5); and `multiline` TextInputs do not
  fire `onSubmitEditing` on web (Step 8.8).
- Layout lessons do NOT port as CSS: re-apply the *intent* (e.g. overlay chrome must
  be absolute, not a flex sibling) in RN primitives. Touch has no hover, so
  hover-revealed controls become swipe/tap-revealed.
- Native polish is its own phase: keyboard avoidance, safe areas, haptics, image
  picker, list virtualisation, `useColorScheme`.

## Step 7 — Repo and test strategy

- **Separate repo over monorepo** unless there's a reason: different toolchains
  (Metro vs Next), different deploy targets (EAS/static vs Docker), different CI.
  Vendoring ~200 lines of pure helpers with a pointer comment naming the canonical
  source is cheaper than a workspace build on day one (YAGNI).
- **Nothing load-bearing should be duplicated.** If a server-side guard works by the
  server emitting a rewrite event, the client never needs it — say so.
- **The existing web E2E suite must keep passing** for as long as the web client
  ships. Add a native runner (Maestro is simpler than Detox) for iOS + Android.
- **Re-implement the honesty/security assertions natively, including the
  raw-stream ones** — a DOM-only check misses markdown-wrapped content. See the
  `browser-app-automation` skill.
- Flag external dependencies early: Apple Developer + Google Play accounts for
  TestFlight/Play (dev builds need neither), and decide whether the web app stays
  live or is replaced — that decides whether the old E2E suite is retired.

### Step 7b — After the client ships, REMOVE the old UI from the server repo

The migration is not finished when the RN client works. The server repo is still
carrying a second, now-abandoned web UI, and leaving it there is how the two drift
apart. (User directive, 2026-09-21: *"remove the old UI from this repo, ensuring we
only have the MCP server in this repo"* — and it is absolute for AMA:
`the company-ama` is the server, `the company-ama-app` is the UI; any UI change goes to
the app repo.)

**Resolve what to delete by reading what the CLIENT actually calls — not by
names.** Grep the client for its endpoints and keep everything they import:

- **KEEP every route the client hits**, including ones that LOOK like web UI:
  `/api/chat`, `/api/suggestions`, `/api/models`, `/api/mcp`, `/api/health`, and
  **`/auth/callback`** — the RN **web** build reuses that OAuth return. Deleting it
  as "web UI" breaks Google sign-in on web. Verify by grepping the client's
  `redirectUri()` / OAuth module before you touch it.
- **REMOVE** the pages, the chat/glass components, the markdown renderer, and the
  UI-only dependencies (`react`, `react-dom`, `react-markdown`, `remark-gfm`,
  `tailwind`, `jsdom`) — confirming each is genuinely unreferenced first, and
  dropping `jsdom` only after checking no test needs a DOM.
- **Tag before you delete** (`git tag pre-ui-removal HEAD`) and push the tag, so
  the removal is reversible.
- **REMOVE the UI E2E suite** if it drives pages that no longer exist — but keep
  and FIX the API tests. Assertions like *"unauthenticated `/login` serves the
  login page"* now encode the deleted surface and must be **inverted** to "is 404".

**The middleware must stop REDIRECTING.** This is the trap that bites. A cookie
gate that answers anonymous traffic with `redirect('/login')` now points at a file
that no longer exists, turning a clean 401 into a broken page. Change it to a JSON
404 naming the repo that owns the UI, and keep the Bearer allowlist intact.

**Verify the split held, three ways:**

1. `next build` lists **API routes only** — a page route means UI crept back in.
2. `/`, `/login`, `/chat` return **404** — not 200, not a redirect.
3. Assert (1) and (2) **in the deploy script**, so the split cannot regress
   unnoticed on a later push.

Then re-run the bearer/API suite against the deployed split — it should pass
unchanged, plus the new no-UI checks.

## Plan output

Write it to `.hermes/plans/` (untracked — see the project's plan-doc rule) using the
`plan` skill's structure. A good migration plan leads with the two findings that
shape everything (the server-secret constraint; the existing token-auth path),
states the honest scope in lines-of-code, names the fidelity tradeoff, sequences
phases so **nothing touches production until the client is proven**, and ends with
2–3 scoped alternatives (mobile-only / full-with-simplified-native-glass / full)
plus the open questions that actually change the shape of the work.

## Step 8 — Executing the port (traps found by actually doing it)

Planning is not executing. These are the things that only surfaced once the port
was built and tested against a real server, in rough order of surprise.

**1. The cookie middleware will silently block every native request.**
This is the highest-value trap. Grep for it before writing any client code:

```bash
grep -rn "getUser()\|401\|matcher" src/middleware.ts
```

A Next.js auth middleware typically runs a *cookie-only* session check on every
non-static path and 401s `/api/*` when absent. A native client holds no cookies,
so it never reaches the route that was modified to accept Bearer tokens — and the
symptom is a bare 401 that looks like a bad token. The middleware needs an
explicit carve-out for Bearer-carrying API routes, and a `method === "OPTIONS"`
pass-through so CORS preflight (which by design carries no credentials) is not
rejected before the route's handler runs. Document in the code that the
middleware is then a *routing* gate, not the security boundary, and that each
carved-out route must verify the token itself.

**2. Resolving the org with a cookie client fails for token auth.**
Look for the pattern where `resolveAuthContext` verifies the user with the
passed token but then opens a *fresh cookie-scoped* client for subsequent
RLS-scoped queries:

```bash
grep -n "createClient()" src/lib/auth.ts
```

For a native request that client is anonymous, so the RLS-scoped `org_users`
lookup returns nothing and auth fails with a confusing authorization error. Every
RLS-scoped query on the token path must use a token-carrying client
(`createClient(url, anon, { global: { headers: { Authorization: 'Bearer …' } } })`).
Best: route *both* auth models through one token client once the token is known,
so there is a single code path to reason about.

**3. Audit for routes protected only by the middleware.**
Once Bearer requests bypass the cookie gate, any `/api/*` route that relied on
the middleware for auth is reachable by a request with a *bogus* Bearer header.
`/api/models`, `/api/health` and similar read-only routes are the usual
offenders. Add route-level verification. This is a real security regression
introduced by the migration — check for it deliberately, and cover it with a test
that sends `Authorization: Bearer not.a.real.token` and asserts 401.

**4. Test the SSE framing as a pure module, not through the app.**
`expo/fetch` only resolves inside the Expo/Metro runtime, so any module importing
it is untestable on the host. Split framing (`parseSseChunk`) into its own file
with zero platform imports and unit-test the edge cases: an event split across
two network chunks, several events in one chunk, `data:` with and without the
trailing space, keep-alive comments, CRLF rewritten by a proxy, multi-line data
payloads, and one malformed frame that must not kill the stream. Also handle the
final frame arriving without a trailing blank line.

**5. `mergeStyle` — partial style overrides silently delete layout you relied on.**
With `react-native-markdown-display` (and similar RN renderers), passing a style
map *replaces* the library's defaults. The visible symptom is bizarre: tables
render as a single vertical column. The cause is that the `tr` rule lost its
`flexDirection: 'row'`. Either turn `mergeStyle` on, or carry every layout
property each rule's default provided. Verify tables visually — a text-only
assertion that no raw `|` leaked will pass while the table is unreadable.

**6. Auto-scroll needs to be retried, and `scrollToEnd` may be a no-op.**
Content grows asynchronously after the last stream event (remote images, a
gallery). One `scrollToEnd()` on the last event leaves the newest content below
the fold — and on react-native-web `scrollToEnd` can measure the wrong node and
do nothing at all. Prefer `scrollTo({ y: measuredContentHeight })`, driven from
`onContentSizeChange`, repeated on a couple of staggered timers, and only while
the turn is active so a user who scrolled up to read is not yanked back down.
When a scroll "doesn't work", test whether a direct DOM/JS scroll to the same
offset works before rewriting the component — that distinguishes a broken ref
from a broken style.

**6b. …but `onContentSizeChange` only covers CONTENT growth. Pin the viewport too.**
This is the half of the scroll problem that survives the fix above, and it reads
as intermittent because it depends on where the reply's tail happens to land.
The composer grows when anything renders **above the input** — suggestion chips,
a confirmation card, an attachment row — which **shrinks the transcript's
viewport** while the content height is *unchanged*. Measured: 862→801 and
862→760px across runs, leaving the last line of the reply **61–102px below the
fold** until the user touched the wheel. Nothing re-scrolled, because the only
handler wired up (`onContentSizeChange`) never fires.

**Two mechanisms on RN-web look like the fix and silently do nothing. Both were
measured, not assumed:**

- **`onLayout` on the ScrollView fires ZERO times.** Zero callbacks across a whole
  turn, including for the very resize it was meant to catch, while the viewport
  shrank normally underneath it. A layout-handler fix *cannot* work here — and it
  fails invisibly, so you ship "a fix" that changes nothing.
- **`domScrollerRef.current` is never assigned on web.** The callback ref on the
  ScrollView was measured to stay `null` for the entire session. Every attach
  path gated on it bailed out, so a `ResizeObserver` that looked correct was
  never installed. Resolve scroller nodes by **DOM query** instead:

```ts
const el = document.querySelector('[data-testid="transcript"]') as HTMLElement | null;
```

Use a `ResizeObserver` on that element plus a window `resize` listener, and
re-pin **only if the transcript was already at the bottom** (`dist > 1`) — never
pull a user who is reading further up. Note the scrolling node carrying the
testID *is* the one that shrinks; its inner content wrapper keeps full height and
never reports the change.

**A third trap is about React, not layout: sibling alternatives have no node to
observe.** The transcript and the hero are branches of one ternary
(`messages.length === 0 ? <hero> : <transcript>`), so on a fresh chat a
mount-time attach finds nothing and does nothing. Any effect that must bind to a
conditionally-rendered node needs that condition as a dependency:

```ts
useEffect(() => { /* attach */ }, [repin, messages.length > 0]);
```

Full measured transcript, the observer recipe, and the diagnostic probes:
`references/rn-web-layout-and-resize.md`.

**7. An absolute overlay with children larger than itself causes overflow.**
A full-bleed decorative layer (ambient gradients, glows) whose children extend
past the viewport widens the document and produces horizontal scroll on phones.
Give the overlay `overflow: "hidden"`. Also: RN has no radial-gradient, and
faking one with a solid circle at the CSS alpha value renders as a hard-edged
disc — visually wrong. Reproduce CSS gradients verbatim on web (they pass through
react-native-web) and use much lower alpha plus nested ellipses on native.

**8. Web-only niceties you did not port on purpose.**
`multiline` TextInput does **not** fire `onSubmitEditing` on web — Enter inserts a
newline, so send-on-Enter needs an explicit key handler there. Also expect
`useNativeDriver` warnings on web; they are harmless and worth filtering out of
your console-error assertion rather than "fixing".

**9. Give automated tests a real signal to wait on.**
Polling a timeout makes a suite either flaky or slow, and an obvious handle is
often wrong: the send button is disabled while streaming *and whenever the input
is empty*, which is every moment after a send. A first attempt that waits on it
times out every run. Render an explicit state probe (`turn-active` / `turn-idle`)
and wait on that. Related: react-native-web *removes* `aria-disabled` when it
re-enables rather than setting it to `false`, so selectors matching `="false"`
never match.

**10. Repo creation is a hard external blocker — check it at the start.**
`git` over SSH can *push to an existing* repo but cannot *create* one; that needs
a token or authenticated CLI. Before promising to push, verify:
`gh auth status` and whether the target repo already resolves. If neither holds,
do the work, commit locally, and report the blocker with the two ways to unblock
rather than discovering it at the end.

**11. Static rendering will try to run your app server-side.**
`expo export --platform web` with `output: "static"` renders the routes in Node,
which means your Supabase client, `window` and storage accesses execute at build
time — typically failing with something like `supabaseKey is required`. For an
authed SPA, `"output": "single"` is the correct setting and removes an entire
class of build failure.

**12. Version pinning: `react-dom` must match `react`.**
Expo pins `react` to an exact version; a floating `react-dom` will resolve to a
newer minor whose peer requirement excludes it, and you get an unreadable
ERESOLVE tree. Install them together with `--save-exact`.

**13. `flex: 1` beats an explicit `width`.**
A fixed-width panel (drawer, rail, sidebar) placed in a row parent with
`flex: 1` **grows to fill the available space regardless of the width you pass
it**. The prop looks respected in the source and the element silently renders
full-width. Use `flexGrow: 0, flexShrink: 0, flexBasis: "auto"` for
fixed-size children.

**14. RN style props do not always beat the UA stylesheet.**
Setting `outlineStyle: "none"` (or `outline`/`boxShadow`) in a React Native
style does **not** necessarily remove a browser focus ring on react-native-web:
the UA's `:focus-visible { outline: auto }` rule still wins. Verify by measuring
`getComputedStyle(el).outline` while the element is actually focused — and fix
it with a real injected CSS rule (a small `<style>` added on web only), not more
RN style props.

**15. Vertical alignment in a composer row — TWO stacked bugs, and the second
one defeats the obvious fix.** Reported twice; the first fix did not hold.

*Layer 1 — row alignment.* `alignItems: "flex-end"` on the composer row looks
right with a tall textarea but hangs the 40px buttons **below** the text's centre
line once the input collapses to one line. `center` is the correct default.

*Layer 2 — the input's intrinsic height, which `center` cannot fix.*
react-native-web renders a multiline `TextInput` as **`<textarea rows="2">`**, so
the element is intrinsically **two lines tall** (measured: 54px = 2×22px
line-height + 10px padding) while holding one line of text. The text renders at
the **top** of that box, so the placeholder sat **11px above** the pill's centre
line even with the row correctly centre-aligned. Fix: `rows={1}` on web.

*The tradeoff rows=1 introduces.* A `<textarea rows=1>` **does not grow with its
content** the way RN's multiline input does — four lines stayed at 32px. Drive
the height explicitly from a measurement, clamped at the cap:

```ts
useEffect(() => {
  if (Platform.OS !== "web") return;
  const node = document.querySelector('[data-testid="composer-input"]') as HTMLTextAreaElement | null;
  if (!node) return;
  node.style.height = "auto";              // MUST reset first — measuring with a
  const contentHeight = node.scrollHeight;  // fixed height returns the box, not the content
  const next = Math.min(contentHeight, 130);
  setWebInputHeight(next);
  node.style.height = `${next}px`;
}, [input]);
```

Verified: 1 line = 32px, 4 lines = 98px. Native needs none of this — it grows by
itself, so gate every part of it behind `Platform.OS === "web"`.

**15b. Measure the TEXT's visual centre, not the element's rect centre.**
This is why the bug survived a round of "verification". The textarea's **rect**
was correctly centred after the layer-1 fix, so an assertion on
`rect.top + rect.height/2` passed — while the placeholder was still 11px high,
because the rect was taller than its content. Derive the first line's centre from
the box model instead:

```js
const textCentre = rect.top + parseFloat(cs.paddingTop) + parseFloat(cs.lineHeight) / 2;
```

Then assert `|textCentre − iconCentre| <= 4`. Also assert the box is not
*stretched beyond its content* (`inputH − contentH <= 6`) — a stretched box is
the signature of this whole class of bug. Generalise: when a UI assertion passes
but the screenshot still looks wrong, you are measuring the wrong thing.

**16. Assert against a testID on the element you mean — never an ancestor walk.**
A test that walked up from the drawer's contents to "the widest ancestor"
reached the full-width overlay wrapper and reported the viewport width as the
drawer width. It "failed" for three runs while the real bug was in the
component. Put a `testID` on the element itself (`sidebar-panel`) and measure
that. Corollary: when a test is the only thing failing, first prove the test is
reading the right node.

**17. Deploy verification: compare the built artefact, not the exit code.**
A single `rsync --delete` with an `--include` list dropped the compose file, so
`docker compose up` errored while the container **kept serving the previous
build** — the worst outcome, since the deploy reports a failure and the site
looks fine. Sync the bundle and the deploy context separately, and after
deploying compare a hash of the local `index.html` against the one inside the
container. A deploy is only successful when the artefact on the box is provably
the one you built.

**18. A port publishes to a NEW repo — audit it before the first push.**
The port's deliverable is a fresh repo, frequently public, and you are usually
copying files *out of* a private one. Internal context travels with the copy in
places a code review does not look:

- **Comments.** A helper comment carried across verbatim named an internal host
  and a tailnet URL ("served over plain HTTP at `http://<internal-host>:3199`")
  while the code itself was clean. The whole file is committed — grep comments.
- **Script defaults.** A deploy script defaulting to `~/.ssh/<specific-key-name>`
  both leaks which key is used and breaks for every other machine. Require it
  from the environment and fail loudly when unset, rather than falling back to a
  path that exists on one developer's box.
- **JWT-shaped literals.** Decode the `role` claim before judging one. A Supabase
  `anon` key is *designed* to be public (RLS-constrained; the same key the web
  app ships) and is safe to commit — its presence is not a leak. A `service_role`
  key bypasses RLS and must never ship. Only the decoded claim distinguishes them.

```bash
grep -rniE "tailscale|tailnet|100\.[0-9]+\.[0-9]+\.[0-9]+|<internal-host>" \
  --include='*.ts' --include='*.tsx' --include='*.py' --include='*.md' \
  --include='*.json' --include='*.sh' --include='*.yml' . | grep -v node_modules
grep -rniE "id_ed25519|\.ssh/|deploy_key|private key" \
  --include='*.ts' --include='*.py' --include='*.md' --include='*.sh' . | grep -v node_modules
```

Then confirm the gitignored paths really stayed out of the remote — a plan doc
directory is the usual one:

```bash
git ls-tree -r --name-only origin/main | grep -c '^\.hermes/'   # must be 0
```

**19. Do not render the reply bubble before there is a reply.**
A chat UI that creates the assistant's bubble immediately and puts a spinner
inside it shows an **empty glass pill** while waiting. Users read that as a
broken/blank message, not as loading — it was reported as a bug in review. Split
it into two distinct states:

| State | Render |
|---|---|
| nothing back yet (no text, no tool cards) | the spinner **alone**, no surface around it |
| text streaming in | the bubble, containing the text and the spinner |

```ts
const hasContent = m.content.trim().length > 0;
const showSpinnerOnly = isStreamingTarget && !hasContent && !m.toolEvents?.length;
```

Do not gate this on "is the last message" alone — a turn that emits tool events
before any text should already show the cards, so include them in the condition.
Give the standalone spinner its own `testID` and assert **both** directions: no
empty bubble exists at any point, and the spinner is gone once text arrives.

**20. Hover-revealed controls: keep the reserved slot in the layout.**
Converting a hover-revealed action to a touch-friendly one is the easy half. The
trap is letting the row **reflow** when the control appears — titles jump and the
list height shifts as the pointer moves across it. Reserve a fixed-size slot that
is always present and reveal only the icon inside it:

```tsx
<View style={styles.rowTrailing}>        {/* always rendered, fixed 28x28 */}
  {isWeb && hovered ? <TrashIcon /> : null}
</View>
```

Draw the icon from **Views, not an icon font or SVG** — no dependency, and
identical rendering on iOS, Android and web. Add an assertion that the row's
height is unchanged with and without the control (measured before/after).

**21. Disabling a feature "for now" — pin the chokepoint, not the surface.**
Request: *"remove dark mode for now. Just comment it out 🙂 remove the toggle
button too."* The naive reading is "delete the button", and it **does not disable
dark mode**: the scheme fell back to the **device** preference
(`useColorScheme()`), so anyone whose OS is in dark mode still got a dark app with
no way back. Removing the visible control removed the *exit*, not the *behaviour*.

A feature-disable request means "make the capability unreachable" — a different
thing from "remove the element". Find the single chokepoint every consumer routes
through and pin it there. Here every component resolves colour through one
`useTheme()` hook, so pinning the scheme in `useThemeValue()` made the whole app
light with **zero component changes**:

```ts
const scheme: Scheme = "light";   // was: override ?? (device === "dark" ? "dark" : "light")
// const device = useColorScheme();
```

**Keep the interface intact so the union branches still compile.** Leave `scheme`
on the context typed `"light" | "dark"` and leave every `scheme === "dark"`
branch in `Glass.tsx` / `MessageList.tsx` exactly where it is — it simply never
fires. Two consequences to handle:

- Pinning to a single literal makes a union comparison a **type error**:
  `This comparison appears to be unintentional because the types '"light"' and
  '"dark"' have no overlap`. For arithmetic that needs the real value (the
  `toggle`), keep a separate `const activeScheme: Scheme = override ?? "light"`
  rather than widening `scheme` back to the union.
- Disabled code leaves **unused bindings**: destructures (`const { t, scheme,
  toggle }`) and imports (`useColorScheme`, the `dark` token set) now go unused.
  Drop them and note in a comment what to re-add.

**Comment, don't delete** — the user asked for exactly this, and it is the right
default for any "for now" request. Mark each disabled region with WHY and the
restore steps, and leave the removed handler functional on the context so
restoring the control is a one-line uncomment.

Full file-by-file recipe, the restore checklist, and the verifier traps:
`references/feature-disable-and-theming.md`.

**22. Asserting an ABSENCE still needs a positive proof — and a mutation test.**
Verifying "dark mode is off" is where a weak test silently proves nothing. Two
traps, both of which produced a **passing** check against an app that was still
rendering dark:

- **Asserting on `document.body` is vacuous.** On React Native Web the root is
  **transparent**, so `getComputedStyle(document.body).backgroundColor` is
  `rgba(0, 0, 0, 0)` under BOTH schemes. An assertion like "body background is not
  the dark token" passes on a light app, a dark app, and a blank page alike.
- **"No dark colours found" is not a positive result.** Absence of the dark
  palette is also what a failed render reports. Count painted colours across real
  elements and assert the **light token is present**, not merely that dark is
  absent.

```js
const bgCount = {};
for (const el of document.querySelectorAll('*')) {
  const bg = getComputedStyle(el).backgroundColor;
  if (bg && bg !== 'rgba(0, 0, 0, 0)') bgCount[bg] = (bgCount[bg] || 0) + 1;
}
// then: LIGHT_BG must be IN the set, and DARK_BG must NOT be
```

**The decisive test is the emulated OS preference.** Set Playwright's
`color_scheme="dark"` (a separate `browser.new_context` per scheme) and assert the
app paints the same palette as under light — that is the check that catches the
`useColorScheme()` fallback. Compare the **set** of painted colours, not ranked
counts: counts vary with incidental DOM state (is the sidebar open, how many rows)
and made a correct app look like a failure.

Finally, **mutation-test it before believing it**: re-enable the device fallback,
redeploy, and confirm the check FAILS with the dark palette detected; then restore
and confirm the bundle hash matches the pre-mutation build.

**23. "Remove X once Y has happened" — hide it for the whole transition, and
assert the transition, not just the end state.**
Request: *"Remove this from main chat screen after first assistant message is
returned: Your org's data only · writes require confirmation."*

Two things are easy to get wrong. First, tie the condition to the **message
count, not the stream's completion** — if the note only disappears when the reply
finishes, it sits under the answer and then blinks away a beat later, which reads
as a glitch. `messages.length === 0` hides it from the first message onward,
including while that reply streams:

```tsx
{messages.length === 0 ? (
  <Text testID="scope-disclaimer">…</Text>
) : null}
```

Second, and more important for the check itself: **asserting only the end state
proves nothing.** "Not present after the first reply" also passes on an app that
never rendered the note at all — the check is satisfied by the absence of the
feature. Assert the transition (present before → absent after), and match on
**text as well as testID** so the assertion does not silently stop testing when
someone re-adds the element without the tag:

```python
before["byTestId"] and before["byText"]   # present on the empty chat
mid["byText"] == 0                        # already gone mid-stream
after["byText"] == 0                      # still gone after
```

General rule: **a test that can only ever observe one state cannot tell
"correctly hidden" from "never existed".** Give it a state it must observe first.

**24. OAuth redirect config: the provider sees Supabase's callback, not yours.**

Request: *"What do I add to supabase auth for google OAuth to ensure it redirects
to login for AMA?"* The native answer is one string, but three things around it
are easy to get wrong.

Add the client's own deep link to **Redirect URLs** — from `app.json` `scheme`
plus the path the client sends (`app/lib/oauth.ts`):

```
the company-ama://auth-callback
```

- **Redirect URLs, not Site URL.** Site URL is the fallback for *everything*
  (email confirmations, password resets, and any redirect that fails validation),
  and a custom scheme is not a valid `http(s)` origin for those. Put it in the
  additional-redirects list.
- **The symptom of a missing entry is SILENT.** Supabase does not error — it falls
  back to Site URL. So "Google completes and then dumps the user on the wrong
  page / on the main app's login" *is* the missing-allowlist symptom. Worth
  setting Site URL to the app's own login so that fallback at least lands
  somewhere sensible.
- **Do not wildcard a hardcoded value.** The app sends one fixed string, so match
  it exactly. Supabase's glob rules are asymmetric and easy to get wrong:
  separators are `.` and `/`, so `the company-ama://*` matches `auth-callback` but
  **not** `a/b`, and it would also match `the company-ama://evil-callback`.
  `the company-ama://**` is broader still.
- **The Google Cloud console needs nothing app-specific — check before sending
  anyone there.** Decode the authorize redirect and read `redirect_uri`; it is
  Supabase's own fixed callback for *every* project:

```bash
ENC=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1],safe=''))" "the company-ama://auth-callback")
curl -s -D - -o /dev/null "https://<supabase-host>/auth/v1/authorize?provider=google&redirect_to=$ENC" \
  -H "apikey: $ANON" | grep -i '^location:'
# -> redirect_uri=https://<supabase-host>/auth/v1/callback   (and client_id, scope)
```

  Only the Supabase allowlist needs the per-app entry; the Google console entry
  stays `https://<supabase-host>/auth/v1/callback`.
- **You cannot read the current allowlist — say so.** `/auth/v1/settings` returns
  provider flags only; verified that `site_url`, `uri_allow_list` and
  `additional_redirect_urls` are **not** in the response (nor are
  `redirect_urls` / `external_redirect_urls`). So never assert what is already
  configured — state what to add and say the current contents are unverifiable
  from the anon key.

**The web twin of this trap is a redirect target that is not a route — and HTTP
200 hides it.** The web branch of `redirectUri()` returned
`${origin}/auth/callback`, but the Expo Router app had no such route file, so it
rendered **"Unmatched Route / Page could not be found."** — while
`curl -o /dev/null -w "%{http_code}"` reported **200**, because the SPA fallback
serves `index.html` for every unmatched path. A status-code check cannot see
this class of bug at all.

Assert on rendered content, not status:

```python
await page.goto(f"{APP}/auth/callback?code=fake-test-code")
assert "Unmatched Route" not in await page.inner_text("body")
```

General rule: **on a SPA, `curl`'s status code says nothing about whether a route
exists.** Verify routes by rendering them and looking for the not-found marker.
Applies to every allowlisted redirect target, every deep-link path, and any
"does this page exist" question. Full recipe, glob table and probe commands:
`references/supabase-oauth-redirects.md`.

## Step 9 — Verifying the port (the RN-web build is testable in a browser)

You do **not** need a device to get real verification of the port. The RN-web
build is DOM, so Playwright drives it exactly like the original web app — same
login, same streaming, same assertions. This is how you prove the port rather
than eyeballing a screenshot.

**Build once, then serve it statically:**

```bash
npx expo export --platform web          # produces dist/ (index.html + one JS bundle)
npx --yes serve dist -l 3401 --single   # --single = SPA fallback for deep routes
```

Then point the browser at that. Two things this immediately catches:

- **CORS against the real API.** The exported bundle talks to the real server
  from a *different origin*, so a missing CORS allowance fails here and only
  here. A localhost origin will pass while the deployed origin still fails —
  which is why you must also run the suite against the deployed URL.
- **The bare-root route.** Assert the root serves the app (not a scaffold) and
  that an anonymous visitor lands on login. This exact bug shipped once on the
  web twin and was invisible to an unauthenticated `curl`.

**Make the app testable rather than guessing at the DOM.** Add small `testID`
props for the surfaces assertions need — the transcript scroller, the assistant
message bubble, the drawer panel, the composer, the streaming state. An
explicit `turn-active` / `turn-idle` probe is far more reliable than inferring
"is it streaming" from a button's disabled state (see Step 8.9). See
`references/rn-web-e2e-harness.md` for the concrete selectors and the waiting
helper.

**Re-implement the original honesty assertions, then re-run them against the
deployment.** Porting a UI without porting its correctness assertions means the
port is unverified where it matters. Carry over every check about whose data is
shown, what the model may claim, and what must never be invented — and scope
each assertion to the element that actually holds the content (Step 8.16).
`references/rn-web-e2e-harness.md` has the text-extraction and
unicode-normalisation recipes that were needed to make those assertions precise.

**A false failure is worse than a missing test.** When an assertion fails, first
prove it is reading the right thing before changing the app. Three separate
assertions in one session reported correct app behaviour as broken because they
searched the whole page (which includes the user's own message and tool-card
captions) or matched ASCII punctuation against a model's curly quotes.

**Run the suite three ways before claiming done:** local export, then the
deployed URL, then the original web suite. Each catches a different class of
error — and the deployed-URL run is the only one that proves the deploy.

## Pitfalls

- **Do not propose moving the API/tool layer into the app.** Re-read Step 1 whenever
  a plan starts drifting that way.
- **Do not call a bespoke visual effect a port.** It is a rewrite; budget it.
- **Do not put streaming late.** It is the highest-risk unknown with the biggest
  blast radius.
- **Do not assume the server must be rewritten too** — verify before scoping.
- **Ask who consumes the desktop build** before assuming RN Web is acceptable; a
  distributable desktop binary (`.dmg`/`.exe`) is a different, much heavier track.
- Environment/toolchain failures (missing Xcode, EAS login) are setup state — fix
  them, don't record them as constraints.

## References

- `references/ama-react-native-scoping.md` — a worked example: the AMA
  (Next.js 15 + Supabase + multi-provider LLM) scoping analysis, including the
  secret inventory, the Bearer-token enabler, the line-count inventory, and the
  phase breakdown. **Executed** — the same file records what actually happened
  against the plan.
- `references/rn-web-e2e-harness.md` — the verification recipes: testIDs to add,
  why zero-size probes need `state="attached"`, scoping text assertions to the
  reply bubble, unicode punctuation normalisation, the "echoing a not-found name
  is not fabrication" rule, the loading-state (no empty bubble) and
  hover-revealed-control assertions, and the measured before/after table for
  composer geometry. **Read the "a passing measurement can still be measuring the
  wrong thing" section before trusting your own alignment assertion.** Read this
  before writing the E2E suite.
- `references/feature-disable-and-theming.md` — how to honour a "remove X for
  now, just comment it out" request: disabling a capability by pinning its
  chokepoint rather than deleting the visible control, the union-comparison type
  errors that follow, the unused bindings a disable leaves behind, the full
  file-by-file recipe for theming, and the two traps that make a dark-mode
  verifier pass vacuously. Read before disabling any feature "temporarily".
- `references/rn-web-layout-and-resize.md` — the viewport-vs-content scroll bug,
  the two dead RN-web mechanisms (`onLayout`, `domScrollerRef`) with the raw
  measurements that prove them dead, the `ResizeObserver` + window-resize
  recipe, the conditionally-rendered-node trap, and the diagnostic probe scripts
  used to attribute a flaky E2E failure to pre-existing behaviour.
  **Read this before writing any resize/scroll handler.**
- `references/supabase-oauth-redirects.md` — what to add to Supabase for a native
  or RN-web client's Google OAuth: the exact deep-link string and where it comes
  from in the repo, why a missing allowlist entry redirects silently to Site URL,
  the asymmetric glob table, the `authorize` probe that proves the provider's
  callback is Supabase's own (so the Google console needs no per-app entry), the
  keys `/auth/v1/settings` does NOT return (so the current allowlist cannot be
  read from the anon key), and the "allowlisted target is not a route, but
  reports HTTP 200" trap. **Read before answering any OAuth redirect question.**

## Scripts

- `scripts/verify_dark_mode_disabled.py` — env-driven probe that proves an app is
  light-only by emulating a DARK OS preference (Playwright `color_scheme`) and
  requiring the light tokens to be positively painted. Also asserts the theme
  toggle is absent. Mutation-test it before trusting it.

## Pitfalls

- **Do not propose moving the API/tool layer into the app.** Re-read Step 1 whenever
  a plan starts drifting that way.
- **Do not call a bespoke visual effect a port.** It is a rewrite; budget it.
- **Do not put streaming late.** It is the highest-risk unknown with the biggest
  blast radius.
- **Do not assume the server must be rewritten too** — verify before scoping.
- **Do not read "remove the button" as "disable the feature."** A visible control
  is only the entry point; the capability usually has a second trigger (device
  preference, a default, a stored value). Disable it at the chokepoint — see
  Step 8.21.
- **Do not fix a scroll/reflow bug with `onLayout` on RN-web, and do not trust
  `domScrollerRef.current`.** Both were measured to be dead — `onLayout` fires
  zero times and the ref stays `null` for the session. Query the DOM by `testID`
  and use a `ResizeObserver`. A fix built on either one changes nothing while
  looking correct — see Step 8.6b.
- **Do not answer an OAuth redirect question by reading the current config.**
  Supabase's allowlist is not exposed by `/auth/v1/settings` (verified: no
  `site_url`, no `uri_allow_list`). State what to add and say the existing
  contents are unverifiable. And do not send the user to the Google console for a
  per-app redirect — decode the `authorize` call and you will see Supabase's own
  fixed callback is what the provider sees. See Step 8.24.
- **Do not trust an HTTP 200 to mean a route exists.** On a SPA, the fallback
  serves `index.html` for unmatched paths — an allowlisted redirect target that
  renders "Unmatched Route" still reports 200 to `curl`. Render it and look for
  the not-found marker.
- **Do not finish the migration with the old UI still in the server repo.** Once
  the RN client ships, the abandoned web UI is dead weight that drifts from the
  real one. Remove it (Step 7b) — but decide what to delete by grepping what the
  CLIENT calls, not by file names: `/auth/callback` looks like web UI and is the
  RN *web* build's OAuth return. Tag before deleting, invert the now-obsolete
  UI assertions, stop the middleware redirecting to a deleted `/login`, and prove
  it with `next build` (API routes only) plus `/` returning 404.
- **When a fix "doesn't work" after two attempts, instrument before attempt
  three.** Two whole iterations were lost here writing plausible layout handlers
  that never fired. Dumping the actual callback invocations (`window.__dbg`)
  settled it in one run.
- **Ask who consumes the desktop build** before assuming RN Web is acceptable; a
  distributable desktop binary (`.dmg`/`.exe`) is a different, much heavier track.
- Environment/toolchain failures (missing Xcode, EAS login) are setup state — fix
  them, don't record them as constraints.
