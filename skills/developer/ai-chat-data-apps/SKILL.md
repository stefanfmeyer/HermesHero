---
name: ai-chat-data-apps
description: Build LLM chat/MCP interfaces over an existing platform's production data — tenant isolation, tool-result rendering, streaming UI pitfalls, and E2E verification. Use when asked for a "chat interface for our users to ask about their data", an MCP server on top of existing APIs, or fixing data leakage in such an app.
tags: [llm, chat-ui, multi-tenant, supabase, mcp, security]
---

# AI Chat Apps Over Production Data

Class guide for "chat interface + MCP server so our users can ask questions about their own data" projects. The hard parts are never the chat itself — they are (1) tenant isolation, (2) what the UI shows mid-stream, and (3) honest E2E verification.

## Architecture that works

One shared **tool layer** exposed two ways: an LLM tool-calling pipeline (`/api/chat`, SSE streaming) and an MCP streamable-HTTP endpoint (`/api/mcp`, Bearer = the user's access token). Both call the same tool modules with a per-request context derived from the **verified session**.

Auth model: reuse the platform's existing user pool (e.g. Supabase auth shared with the main app). Resolve tenant/org server-side from membership tables using the user's own token — never from tool arguments.

## Tenant isolation — RLS alone is NOT enough

See `references/tenant-isolation-case-study.md` for the full case. Rules:

1. **RLS "super admin can view all" policies bypass org scoping for staff accounts.** A user with a super-admin profile sees every tenant's rows through perfectly-correct-looking RLS queries. Always ALSO filter explicitly by the session org (`.eq("org_id", ctx.orgId)`) and re-filter results app-side (defense in depth).
2. Resolve the user's **primary org deterministically** (e.g. the `is_advertiser = true` org), not "first membership" — staff accounts often hold 100+ org memberships in test data.
3. Writes: pin `org_id`/`user_id` from the session server-side; injected values must be overwritten or schema-rejected (UUID zod schemas reject most injection payloads).
4. Cross-org reads of a specific id must return "not found in your organization" — never empty success.
5. When integrating with an existing API service, READ its auth code first: routes may require different credential types than you assume (e.g. an admin token rejected on write routes that require per-tenant API keys). The platform's own MCP server often already solved scoping the right way — copy its model (SECURITY DEFINER RPCs filtered by `auth.uid()` beats admin-token proxies).

## Tool-result rendering (the #1 user complaint)

Raw tool JSON/data tables streaming into the chat reads as a security breach even when the data is the user's own:

- Tool results render as **collapsed chips** ("List Campaigns · 10 rows" / "running…") during AND after streaming. Raw rows only on explicit click-to-expand.
- Expanded compact tables show **human columns** (name, status, budget) — drop id/UUID columns.
- Render assistant text with a real markdown renderer (react-markdown + remark-gfm): visible `**asterisks**` or raw `| pipe |` rows look broken. Style tables with the product's design tokens (hairline borders, uppercase muted headers, tabular numerals).
- System prompt: instruct markdown tables for tabular data.
- **Errors never render raw, even mid-stream.** A zod validation dump flashing
  in the chat reads as a security breach (user screenshot proves it). Three
  layers: (1) server catches ZodError per-tool and sends a human message
  ("campaign_id: Invalid UUID"), never `e.message`; (2) the UI's error card is
  a collapsed `<details>` chip ("Get Campaign failed") with detail on expand —
  same treatment as results; (3) client-side `summarizeError()` still collapses
  JSON-array payloads as a backstop.
- **Tool events must PERSIST into the final message.** Classic bug: the
  streaming loop attaches `toolEvents` to the message but the `finally` block
  rebuilds the message with a shallow copy `{...assistantMsg}` — silently
  dropping every tool chip the moment streaming ends ("it just overwrites/
  clears the tool calls"). Rebuild the final message WITH toolEvents, in the
  error path too.
- **Quick-reply chips: generate them with an LLM call, NOT a regex (superseded
  2026-09-15).** The extractor approach below — parsing markdown table rows and
  bold spans — shipped, and the user reported the chips as "too inconsistent"
  and asked for context-awareness *or removal*. It failed because a heuristic
  can only ever fall back to canned chips ("Last 7 days", "Campaign list")
  whenever its patterns miss, regardless of what was just said. A single extra
  LLM call against the finished reply fixed it outright.
  - `POST /api/suggestions` takes `{reply}` → `{suggestions:[{label, message}]}`.
    Session-authenticated like `/api/chat` (do NOT add to the middleware
    PUBLIC_PATHS allowlist — verify it 401s unauthenticated).
  - Start it the moment the reply TEXT is final — **not** after the stream
    call returns (corrected 2026-09-18). `runStream` gained an `onDone`
    callback fired at the end of the server stream and BEFORE the reveal pump
    drains its backlog; the chips request launches there, never awaited. The
    earlier "fetch after the stream ends" rule added up to ~600ms of purely
    COSMETIC animation (the character-reveal drain) to the user's wait for
    chips, for no benefit — the chips only need the text, which is complete at
    that point. Timing, not model, is the first lever on chip latency.
  - **Best-effort**: return `{suggestions: []}` on every error path so a
    suggestion failure can never touch the conversation.
  - Drop unusable entries server-side: placeholder text (`<campaign>`), missing
    label/message, >300-char "messages" (those are drafted replies), duplicates.
    A chip that breaks when clicked is worse than no chip.
  - Guard stale responses: mirror `activeId`/`messages` into refs and bail if
    either moved while the fetch was in flight, or a chip gets attributed to the
    wrong reply.
  - **The staleness guard must be a per-turn COUNTER, not a message-length
    comparison, once the request starts mid-stream** (found 2026-09-18). Length
    comparison (`messagesRef.current.length > forMessages.length`) reads STALE
    state when the fetch launches from `onDone` before the stream's final
    update has been applied — so it can drop the chip response it just asked
    for. Use `suggestionSeqRef.current++` per turn and bail when the token
    changed.
  - **Mint the conversation id ONCE per turn.** On the first turn of a new chat
    the id was computed in two places (the chips request and the persistence
    call), each `activeIdRef.current ?? uuid()`, so they produced two DIFFERENT
    uuids — and the chips' conversation guard then rejected its own response.
    Symptom: chips never appear on a NEW chat, but work on subsequent turns.
    Resolve `const conversationId = activeIdRef.current ?? uuid()` once before
    the stream starts and share it.
  - **Bound the output tokens.** Plumb `maxTokens` through the provider client
    and pass ~512 for chips. The shared 4096 chat default let a model spend a
    long budget on a payload that needs ~32, and the response cannot be parsed
    until it finishes.
  - **NEVER substitute a cheaper/faster model to cut latency — it is a product
    constraint, not a tuning knob.** See "Model choice is a constraint" below.
  - Full worked example with all the measurements (stream-tail check, endpoint
    decomposition, the parse-brace bug, the two bugs this change introduced,
    and how to verify the deployed model): `references/helper-call-latency.md`.
  - Next.js route files may only export known handlers — exporting a helper
    (`parseSuggestions`) fails the build with `"…" is not a valid Route export
    field`. Put the parser in `src/lib/` (which also makes it unit-testable).
  - Verify by asking 5-6 *different* questions in ONE conversation and asserting
    the chips differ per reply and name real entities from that reply — a single
    happy-path check cannot distinguish this from the old fallbacks.
  - Layout: a `max-h-[84px] overflow-hidden` chip row cuts a wrapped second row
    in half (4 chips wrap on mobile). Size the row to its content.
  - Original heuristic (kept for historical context, no longer used): parse the
    markdown TABLE ROWS — first cell per row, stripping `**`, skipping
    separator/header rows — not just bold spans, because the model often renders
    entity names as plain table cells. Superseded by the LLM call above.
- **The assistant's own option bullets are the chips (verified user
  correction, 2026-09-14).** When the reply ends with offered options
  ("Would you like me to: - Show your overall account performance summary?
  - Activate this campaign?"), those bullets must become clickable chips
  verbatim, suppressing generic chips. The LLM-generated approach above
  satisfies this naturally — the prompt says the reply's own options ARE the
  chips.

## Charts in tool results: pick by web support, then measure the geometry

When a tool result is a time series, chart it in place. The library choice and two
geometry bugs are decided by constraints, not taste (all verified 2026-09-21).

**Choose the library on web support first, because one codebase must serve
iOS + Android + a deployed web build.** That eliminates the fastest options:

| Library | Verdict |
|---|---|
| **react-native-gifted-charts** (on `react-native-svg`) | chosen — `react-native-svg` ships a real `.web.js` implementation (Expo SDK 57 pins 15.15.4), so ONE component renders on all three targets |
| Victory Native | fastest (Skia) but **states it does not support the web target**, and needs a dev build |
| react-native-svg-charts | abandoned; peer `react-native-svg ^6 \|\| ^7` vs SDK-57's v15 → **does not install** |
| react-native-chart-kit | SVG but no built-in touch interaction |

**Prepare the data as a pure, unit-tested module — never plot server rows raw.**
Real rollup data repeats a `date_key` (rows are per-campaign), which plots one
date at two x positions and draws a shape the data does not have. Sum duplicates,
fill gaps (emit zero buckets so a dormant span reads as dormant), bucket to weeks
past ~60 days, and disclose every transformation in a caveat on the card. Assert
on the **real production payload** as the fixture. Also force integer ticks for
count metrics (`niceAxis` 1/2/5 ladder) — an impressions axis showing `0.5`/`1.5`
reads as broken.

### Two geometry bugs a screenshot will not catch

**1. `initialSpacing` is counted TWICE on the pointer overlay.** gifted-charts
renders the crosshair/dot/tooltip in a container already inset by
`initialSpacing`, and `pointerX` is *itself* `initialSpacing + sum(spacing…)`. So
the hover indicator lands exactly `initialSpacing` px to the RIGHT of the point it
reports. Measured by pressing each point and reading where the crosshair landed:

| `initialSpacing` | crosshair offset |
|---|---|
| 35 | **+35.3px** |
| 0 | **+0.3px** |

Keep it at **0** and buy any right-hand room with a slightly smaller `spacing`.
The offset tracking the inset *exactly* is what identifies a double-count rather
than a rounding artefact. (Residual, deliberate: the library clamps the crosshair
at the plot's left edge, so the first point's crosshair sits ~5px right.
`pointerShiftX` moves the strip line but not the dot, so using it would make them
disagree — worse than a uniform 5px on one point.)

**2. The library's x labels are clipped at the first point — so render your own
axis row.** Each label is centred on its point inside a fixed box that an ancestor
clips at the y-axis gutter. With `initialSpacing: 0` the first point sits exactly
on that boundary, so the first label loses half its glyphs ("Sep 18" → "» 18").
**These two constraints are mutually exclusive inside the library's layout** —
measured at four gutter widths, the clip edge and the first point move together
(44→45, 60→61, 80→81, 100→101), so widening the gutter fixes nothing, and using
`initialSpacing` to buy the room re-breaks the pointer. Fix: set
`xAxisLabelsHeight={0}` and every datum `label: ""`, then draw the row yourself
underneath, positioned from the same `spacing` the series uses.

### Assert both on geometry, never on a screenshot

A 35px pointer error reads as "nearly right" to the eye, and half a missing first
letter reads as a rendering quirk. Both survived visual review.

- **Pointer:** press each data point, read the x of the crosshair (the only tall
  vertical `<line>` in the SVG), assert `|Δ| <= 3px`. Mutation-tested: restoring
  `initialSpacing=35` fails with 35.3px.
- **Labels:** measure each label's **glyph rect** (DOM `Range`) intersected with
  every `overflow`-clipping ancestor, and assert `clippedPx == 0`. Measuring the
  element's bounding box instead is useless — the library wraps each label in a
  ~310px box, so *every* label would look clipped. Mutation-tested: moving the row
  back inside the chart's container fails with 15.9px.
- The crosshair **only exists while the pointer is held down**, so press → read →
  release in one action; measuring before the press finds nothing and the check
  passes vacuously. And re-measure the element's box right before pressing — an
  earlier drag can scroll the transcript and leave a stale box.

Also note `adjustToWidth` fits the series to the **window** width (not the card),
and container padding does NOT fix label clipping because it sits outside the
library's own clipped box.

## Dashboard deep links: verify the PATH and the CLICK, not the route table

When the user asks for "a link to the page for what the assistant just said", the
work is mostly verification, because every naive check passes a broken link (all
verified 2026-09-21 on app.example.com).

**0. Render the link IN THE USER'S BROWSER. HTTP 200, the router, and Chromium
all lie.** This is the lesson that cost a shipped bug. The user clicked "Open line
items" and got the dashboard's own ErrorBoundary: "Dashboard Error / The operation
is insecure".

- `/dashboard/ads` (the line-item list) subscribes to Supabase realtime on mount.
- The dashboard's meta CSP lists `https://*.supabase.co` but **never `wss://`**, and
  `default-src 'self'` then blocks the WebSocket.
- **Firefox throws that refusal into the page's ErrorBoundary. Chromium logs the
  identical refusal as a console warning and carries on.**

Capture the browser's own words rather than paraphrasing them — the first version of
this note guessed at the mechanism and got the message text wrong:

```
[JavaScript Error] "Content-Security-Policy: The page's settings blocked the
loading of a resource (connect-src) at
wss://<project>.supabase.co/realtime/v1/websocket?apikey=…"
[ErrorBoundary] → body reads "Dashboard Error / An unexpected error occurred."
```

So the page was broken for the user and healthy in every check I had run: `curl`
gave 200 (SPA fallback), the router read looked right, and my Chromium E2E passed.
**A blocked realtime WebSocket is the shape to suspect whenever an SPA page dies in
one browser only**, and the dashboard's meta CSP is where to look.

⚠️ **The user's error TEXT is version-specific — do not treat a mismatch as evidence
you are looking at a different bug.** `NS_ERROR_CONTENT_BLOCKED` ("The operation is
insecure") is Firefox **131**'s wording; the current build renders the boundary's
generic "An unexpected error occurred." because the ErrorBoundary catches the refusal
and prints its own fallback. Same cause, different string. What survives across
versions is the **console** output above, which is what to assert on. Get the real
error by hooking `console.error` with `add_init_script` and reading
`name`/`message` explicitly: a `DOMException` serialises to `{}` in
`JSON.stringify` and is not `instanceof Error` in every browser, so the obvious
probe reports nothing. Reproduce with `p.firefox.launch()`.

**1. A status code proves nothing — the dashboard is a SPA.** The fallback serves
`index.html` for EVERY path, so a dead path still returns **200** and paints an
empty shell. Reading the router also turns up routes that exist but are **decoys**.

**Enumerate the WHOLE router from source; do not audit the routes you remembered.**
A hand-picked list is a sample, not an audit. Rendering all **45** advertiser routes
(enumerated from `src/routes.tsx` + `src/pages/Dashboard.tsx`) gave **36 render, 3
CRASH, 6 redirect, 0 empty** — and found a third crashing page the previous audit had
missed entirely. 0 EMPTY is the reassuring number: it means no route silently paints
a shell.

| Candidate | Reality (measured, in Firefox, signed in) |
|---|---|
| `/dashboard/ads`, `/dashboard/ads?campaign=<id>` | **CRASH** — ErrorBoundary. Never link |
| `/dashboard/ad-server-admin` | **CRASH** — its index renders `admin/Dashboard` → `LiveActivityMini` → the same realtime hook |
| `/dashboard/ads/<line-item-id>` | **works** — a real per-item page. This is the correct line-item link |
| `/dashboard/creatives/<id>/edit` | 200, renders FINE, but the editor never receives the id — a **DECOY**, see below |
| `/dashboard/creatives/<id>/versions` | works — fetches the creative by id |
| `/dashboard/creatives/approvals` | super-admin only; every other role is a `<Navigate>` to the library |
| `/dashboard/campaigns` | works — and there is **no per-campaign page** (flat list, no row detail) |
| `/dashboard/brand-intel/brands`, `/reporting`, `/creatives/library`, `/dashboard` | work |

Record the broken/decoy routes IN THE CODE with the reason, and have the E2E
assert the broken ones are *still* broken — so if the upstream CSP is ever fixed
you learn about it instead of silently missing an upgrade.

**⚠️ The dashboard's OWN menu links to the crashing page.** `CampaignManager.tsx`
renders a per-campaign "View Line Items" item whose onClick is
`navigate('/dashboard/ads?campaign=' + id)`. So an advertiser in Firefox hits the
Dashboard Error with this app nowhere in sight — it is a **dashboard-repo bug**, not
an integration defect. Check the dashboard's own navigation before framing a broken
destination as yours, and say clearly in the report which repo owns it.

**⚠️ "Did any request contain the id?" is a WORTHLESS proof of id consumption.**
The previous version of this table recorded the creative editor as *not* using its
id based on that check — and the same check reported the editor as **USING** it the
next time it ran. The reason: the navigated URL IS itself a request, so a substring
match over all requests matches on every page and always passes. Restrict the match
to **Supabase REST/rpc data traffic** (`/rest/v1/`, `rpc/`); then the evidence is
real:

```
/dashboard/ads/<id>        /rest/v1/ads?select=*&id=eq.<id>              USES ID
/creatives/<id>/versions   /rest/v1/advertiser_creatives?...id=eq.<id>   USES ID
/brands/<id>              /rest/v1/brands?...id=eq.<id>                  USES ID
/creatives/<id>/edit       no data request carried the id                DECOY
```

Two independent proofs of the decoy, and the second is the one to reach for when a
behaviour-only check cannot see it: the router declares `:creativeId` while
`Editor.tsx` destructures **`const { id: creativeId } = useParams()`** — the names
do not match, so the param is ALWAYS undefined and the page silently opens its "new
creative" path. **A param-name mismatch between the route and `useParams()` is a
silent decoy that renders perfectly**, so grep the component's destructuring, not
just the route table.

**The exclusion is enforced in CODE, not just documented.** `FIREFOX_BROKEN_PATHS`
as data + one `assertLinkable()` chokepoint that every emitted URL passes through
(`dashboardUrl`, and every `*Url()` builder). Two matching rules that both break it,
so pick carefully:
- a **prefix/startsWith** test refuses `/dashboard/ads/<id>` (a different, working
  route) — wrong in one direction;
- a raw **`includes`** test has the same bug — it also flags the good URL.
- **Correct: exact pathname comparison, with the query dropped**, because
  `/dashboard/ads?campaign=<id>` must be refused while `/dashboard/ads/<id>` must
  not. The test suite caught both wrong versions; the throw is what made it loud.

**Make the E2E read the route table FROM THE SOURCE, not from itself.** A script
with a hard-coded path list can only confirm what someone already remembered — the
original failure mode was never "a link is wrong", it was "a link nobody audited
shipped". Parse `DASHBOARD_ROUTES` and `FIREFOX_BROKEN_PATHS` out of `links.ts` with
a narrow regex, so a key ADDED is tested automatically and an exclusion REMOVED is
asserted-broken automatically. Make an empty parse a hard failure (refuse to run)
rather than an empty assertion list, which would make the whole file vacuous.

**2. Attach the link in the SHARED tool wrapper, not per tool.** When chat and MCP
both consume one `TOOLS` registry, decorating `withValidation` gives both surfaces
the links from one place and no future tool can forget. Attach on SUCCESS only — a
`{ error }` soft failure with a link invites a click to a page about something the
tool could not read.

**3. The payloads are NESTED, so a wrong field is a SILENT no-link.** Read the tool
source, don't assume: `{ campaign: {...} }`, `{ line_item: {...} }`,
`{ creatives: [{...}] }`. A top-level `data.campaign_id` read found nothing and
produced no link at all — no throw, no log. Walk the known wrappers, and fall back
to the general page rather than emitting a URL containing a missing id.

**4. THE LINK MUST ACTUALLY OPEN.** The markdown renderer was wired to
`onLinkPress={() => false}`, which applies the link style (accent + underline) and
then swallows the tap. The link looked clickable and did nothing, which is worse
than plain text. On **web** open a **new tab**: a plain `Linking.openURL` is
`window.location.assign`, which navigates the SPA away from the conversation. Add
`noopener` (different origin) and fall back to same-tab when a popup blocker
returns null.

**5. Guard the scheme.** The link target is model output rendered as markdown, so
it is an injection surface. Whitelist `http`/`https`; refuse `javascript:`,
`data:`, `file:`, custom schemes, relative paths, embedded whitespace. Put the rule
in a pure module (no RN import) so it is unit-testable in the host runner — the RN
app's vitest config is node-only and only picks up `lib/**` that avoids RN.

**6. Assert the CLICK, not the link's presence, and assert the DESTINATION
renders.** A reply containing a dead link passes every "is the link there" check —
that is how point 4 shipped, and a Chromium-only destination check is how point 0
shipped. Two separate assertions: (a) click it in the app E2E and assert a page
opened without the chat navigating away; (b) visit every emitted link in
**Firefox**, signed in, and assert no error boundary and no redirect off the path.

**7. When a UI is removed from a repo, the middleware must stop REDIRECTING.** A
cookie gate that answers anonymous traffic with `redirect('/login')` points at a
file that no longer exists, turning a clean 401 into a broken page. Change it to a
JSON 404 naming the repo that owns the UI, keep the Bearer allowlist intact, and
run the build as the proof: `next build` must emit API routes ONLY — a page route
means UI crept back in. Also assert it in the deploy script (`/` must be 404) so the
split cannot regress unnoticed.

**8. Enumerate the links the product EMITS — the route table is still a list you
wrote (2026-09-22).** The source-derived sweep above closes the "a link nobody
audited shipped" hole for *routes*; it does not close it for *emissions*. A reply
can only ever link what `linksForToolResult` returns, so the strongest suite calls
**every tool through the deployed MCP endpoint, collects the URLs that come back,
and renders each one**. That is the difference the original bug lived in, and it
catches a tool that silently emits nothing.

- **Refuse to report a green run from an EMPTY set.** `if not emitted: raise
  SystemExit("the live server emitted no links at all")`. A broken tool otherwise
  reduces the suite to zero assertions and it still reports PASS.
- **Assert the specific page PER TOOL, not just "it renders".** A generic page
  renders perfectly, so a regression that sends "this line item" to the campaign
  list passes every renders-only check. Assert `links.primary.key` equals
  `line_item_detail` / `creative_versions` for the tools whose answer is about ONE
  object. This found `list_brands` emitting the brand LIST for a payload naming one
  brand — and `brandDetailUrl` had been written, verified against a real data
  request, and **had no caller at all**, so that page was unreachable from a reply.
- **When one tool answers two questions, the destination depends on the answer.**
  `list_brands` is both "list the brands" and how the model resolves one named
  brand. Branch on the payload: exactly one row → that row's page; more than one →
  the list. **Do not shortcut on the array head** — the query orders by
  `created_at desc`, so the head is merely the NEWEST brand, not the one asked
  about. Use the COUNT as the discriminator.
- **Harvest test ids from the TOOLS' OWN payloads, never a raw REST query.** This
  account is a platform super-admin holding many org memberships, so
  `advertiser_creatives?limit=1` returns a row the user can SEE that belongs to a
  **different org** than the tools scope to. Feeding that id to `get_creative`
  produced a soft "not found" with no links — a false alarm that read as a product
  bug and cost a debugging round. The tools' payloads are already scoped to the
  picked org, so they are the only correct source.
- **A shared org PICK is an unpinned coupling between two repos.** AMA resolves its
  org with `.limit(1)` among memberships; the dashboard resolves its own. If they
  ever diverge, links land on the *wrong organization's* data while rendering
  perfectly. Measured: they agree today (every campaign name AMA returned was
  visible on the dashboard's campaigns page) — so this is a latent risk, not a
  defect, and it is worth checking rather than assuming, because nothing enforces
  it.

Full detail — the verified route map WITH its broken/decoy routes, the
Firefox `NS_ERROR_CONTENT_BLOCKED` root cause and how to extract a real error out
of an ErrorBoundary, the per-tool nested payload shapes, the pure-module scheme
guard, the session-seeded click-coherence check, and the live per-question link
matrix: `references/dashboard-deeplinks.md`.

## Split panel: show the linked page BESIDE the chat (2026-09-22)

The natural follow-up to deep links: instead of the link sending the user away, a
toggle opens the page for the current answer next to the conversation, so the reply
and its evidence are visible at once. A request for "separate tab and split-screen
for the task at hand, hidden by a toggle" is this.

- **Two modes, one row layout.** Docked shares the viewport; tab gives the page the
  whole viewport. Use a **row** (`flexDirection: "row"`, chat `flex: 1`), never
  absolute positioning — the chat must genuinely give up the space, or the panel
  covers the very answer it is showing evidence for. Assert it by measuring BOTH
  boxes and requiring **no overlap** (chat `x + w <= panel.x`). A "the panel exists"
  check passes while the transcript is hidden.
- **Follow the newest tool result's link, and never build a URL locally.** Derive
  the target from `links.primary` of the newest result (`latestPanelTarget`), not
  from state that can go stale. A URL assembled client-side from a name or guessed
  id could point at another organization's object.
- **Auto-follow must PAUSE when the user takes control** (they clicked through, or
  navigated themselves). Otherwise every follow-up question yanks the page away from
  under them. Show the paused state explicitly ("Paused · Follow") — a silently
  paused panel reads as broken, and the fix becomes invisible.
- **A tool result that is merely PENDING or FAILED must not drive the panel.** A
  `start` has no payload; an error card points at a page about something the tool
  could not read. Only resolved results.

### ⚠️ Embeddability is an UPSTREAM property — measure it, and measure the probe

Whether the target can be iframed is not yours to decide, and the naive reasoning is
wrong in both directions. Here the dashboard carries `frame-ancestors 'none'` in its
HTML, which reads as "cannot embed" — but it is delivered in a **`<meta>` CSP, which
browsers IGNORE**, and the live response sends no `X-Frame-Options` and no CSP
*header* at all. Measured with a real browser: **it embeds fine.**

Run a calibrated probe BEFORE designing around it, with a must-block control so a
blank frame is distinguishable from a broken probe:

| Frame | Expected | Chromium | Firefox |
|---|---|---|---|
| `google.com` (control — sends `X-Frame-Options: SAMEORIGIN`) | must be refused | refused | denied |
| `example.com` (control — embeddable) | must load | loads | loads |
| `app.example.com/dashboard` | the question | **loads** | **loads** |

**⚠️ Do NOT probe with `iframe.contentWindow.location` — it is worthless.** Reading
`location` across origins ALWAYS throws `SecurityError`, so a refused frame and a
successfully-embedded frame report the **identical** value, and the check is wrong in
both directions. Mine failed the dashboard while the dashboard was fine. Signals
that actually differ:
1. **console refusal messages** for the control and not for the target
   (`"Refused to display … X-Frame-Options"` / `"denied by X-Frame-Options"`);
2. **the frame's rendered size** — an embedded document lays out and takes real
   dimensions, a refused one collapses (the live panel frame measured 719×852).

Also: native has no iframe. Embedding there needs `react-native-webview`, so return
false for non-web and offer an explicit "Open in browser" action — a blank frame
looks like a bug. And note a cross-platform trap that *is* in your control: if your
own nginx/Next config ever gains a CSP, its `frame-src` must include the embedded
origin, or the frame silently dies everywhere at once.

## Audit log: who did what, super-admin only (2026-09-22)

"Track every action by what user, searchable/filterable/exportable" — for a
compliance owner (here referred to as Andries). Requested with the constraint **only
super-admin may read it**, given mid-flight; treat that as a first-class requirement,
not a detail to defer.

**Instrument ONE chokepoint, not the call sites.** A shared tool wrapper that both
the chat route and the MCP route funnel through (here `withValidation`) means a tool
cannot exist without being audited — including one written by someone who never
heard of the feature. Two per-surface implementations would drift, and a third
surface added later would silently log nothing. Log on **both** the success and the
throw path, plus soft errors (`{ error }`), which are the normal not-found path.

**Snapshot the actor; don't reference it.** Store email/name/org as values so a
later rename does not rewrite history. Record the org the payload actually answered
for (from its own `scope`), not just the session's primary org.

### The security claim must be PROVEN by a test, not asserted by a grant

"The app can INSERT but cannot READ history" is the whole point, and it is silently
false under two very ordinary conditions:

1. **If the app owns the table.** An owner has every privilege implicitly and
   `GRANT`/`REVOKE` cannot restrain it. So the **superuser** creates the schema
   (`deploy/audit-db/01-schema.sql` at container init, mounted into
   `docker-entrypoint-initdb.d`), the app role gets `INSERT` only, a second role gets
   `SELECT` only, and the app's `ensureSchema` **VERIFIES the table exists instead of
   creating it**. Assert the owner in the deploy, because this is the failure nobody
   would notice.
2. **If a retention/cleanup path exists.** Make the log append-only with a
   `BEFORE UPDATE OR DELETE` trigger raising an exception — stronger than a
   convention, and it stops a future "cleanup" script or an ad-hoc `psql` session.

Then have the deploy **attempt the forbidden operations** and fail if any succeed:
insert/select/update/delete/truncate as the app role, insert/delete as the reader.
Eight probes; they are cheap and they are the actual evidence.

### ⚠️ Redact at the STORE boundary, never at the call site

Put redaction inside the single insert function. A store that only redacts when
asked is not a guarantee: the audit *read* API logs its own query string, so a
caller that forgot — or a new surface that never knew — writes the secret verbatim.
Three real leaks surfaced here, each found by a test rather than by reading:

1. **Over-broad key matching.** A substring list containing `auth` also matches
   `author_name`/`authors`/`authority`, and `key` matches `monkey` — silently
   redacting legitimate fields, making the log quietly less useful than it claims.
   Use **two tiers**: unambiguous substrings (`password`, `token`, `apikey`,
   `secret`) matched anywhere, plus short/ambiguous words (`auth`, `session`, `pin`)
   matched only as WHOLE WORDS after splitting on separators and camelCase.
2. **Key-based redaction cannot see a secret inside a value.** Scrub every string
   through shape patterns too — JWTs (`eyJ…`), provider keys (`sk-…`), `Bearer …`,
   and `SOMETHING_PW='…'` / `SOMETHING_PASSWORD=…` anywhere in the text. This is the
   same leak class as a secret echoed into a transcript from a command line.
3. **The one that matters: the search endpoint logs its own filters.** Storing
   `Object.fromEntries(url.searchParams)` meant that searching the log for a
   credential WROTE THE CREDENTIAL INTO THE LOG as the `q` value. No pattern could
   catch it — the key is `q`, the value is arbitrary text. Fix **structurally**:
   record values for the closed-set filters (ids, enums, dates) and reduce the one
   open free-text field to its **length**. Losing "which user searched for what" is
   the right trade when the search box accepts anything anyone can type.

Free text also gets capped (string length, array length, nesting depth) so one pasted
document cannot fill a row, and `args` is deliberately kept **out of the full-text
index** (extract the useful part into an indexed `subject` column instead) — an index
over arbitrary argument text invites it being returned by a search meant to find a
person.

### Access, and the two failure directions

- Check super-admin with the **platform's own predicate**, called with the CALLER's
  own client (`supabase.rpc("is_current_user_super_admin")`). A service-role client
  would ask "is ANY super admin configured" instead of "is THIS user one" and open
  the gate to everyone. **Fail closed** on any exception.
- **Prove the gate DISCRIMINATES, not just that it returns true.** A check that
  always says yes is indistinguishable from no check: measure a random uuid → false,
  a known non-admin → false, a super admin → true, and anonymous → false.
- **Answer identically for "not signed in" and "signed in but not an admin"** (both
  401, one message). Distinguishing them tells an ordinary user the log exists and
  that they merely may not see it.
- **Log the refusal itself** — a probe against the audit endpoint is exactly the kind
  of event an audit log exists to record.
- **The write path fails OPEN and loud; the read path fails CLOSED.** A logging
  outage must not fail the user's request, so writes are fire-and-forget and report
  on stderr with a greppable prefix. Reads must never render a partial page: return
  5xx, never an empty 200, because "no events" is a claim about what happened.
- ⚠️ **The middleware may answer before your route does.** A self-authenticating API
  route must be added to the middleware's Bearer allowlist, or a blanket
  `401 "Sign in required."` intercepts it and the endpoint is unreachable — the
  symptom is "even the super admin is refused".

### Deploying a database with the feature (traps, all hit for real)

- ⚠️ **`docker compose` needs `--env-file .env.production`** when that is where the
  variables live (a `--delete` rsync deliberately excludes it). Without the flag
  `${VAR}` fails to interpolate and compose **refuses to start ANY service**,
  including the pre-existing one.
- ⚠️ **A mounted init `.sql` must be world-readable (644).** Shipped 0600, the
  container's postgres user could not read it: initdb logged
  `psql: error: 01-schema.sql: Permission denied`, the server **still came up
  healthy**, and the deploy failed later on a confusing `role "…" does not exist`.
  Re-apply the idempotent schema/roles from the bootstrap script so a broken one-shot
  initdb cannot leave a half-built database.
- ⚠️ **An `ALTER ROLE … PASSWORD '…'` that FAILS echoes the password into the
  Postgres log** (visible in `docker logs`). Set one role at a time; pass the value
  via `set_config`/`current_setting` so the statement text contains no secret; and
  scrub the output before printing it.
- ⚠️ **psql does no `:var` interpolation for `-c` arguments**, and none at all inside
  dollar-quoted `DO $$ … $$` blocks. Pipe the statement in with **`-f -`**.
- ⚠️ **The env var NAME is a silent-failure surface.** The store read
  `AUDIT_DATABASE_URL` while the deploy wrote `AUDIT_APP_DATABASE_URL`, so the app
  recorded nothing while looking perfectly healthy. **Make `/api/health` report
  whether the log is actually recording** (`"recording": true`) and have the deploy
  **fail** if it does not — an empty-but-healthy audit trail is the worst outcome
  this feature can have, because people make decisions on it.
- Verify the write path end-to-end live: run one REAL chat turn, then find the
  resulting row through the read API. The audit write is fire-and-forget, so **poll
  rather than sleep** — a single-shot assertion right after the turn is racy and
  reports a search bug that is really a commit-ordering artifact.
- CSV export for Excel/Sheets: RFC 4180 quoting; **neutralise formula injection**
  (a value starting `=`/`+`/`-`/`@`/tab/CR is executed — prefix with an apostrophe);
  and put the UTF-8 BOM in the **bytes**, because passing the CSV as a JS string
  through `new Response()` **drops** the `\uFEFF` and Excel then reads CP1252.

Full worked detail — the verbatim browser capture of the CSP block, the 45-route
result table, the append-only schema + role grants, the redaction patterns, the
calibrated iframe probe, and every deploy trap with its exact error text:
`references/audit-log-and-embedded-panel.md`.

## Repo split: server vs UI (user directive, 2026-09-21)

the user's rule for this product, and it is absolute: **`the company/the company-ama` is
the MCP/API SERVER ONLY — no UI. ALL UI/UX lives in `the company/the company-ama-app`
(React Native / Expo).** Any UI change goes to the app repo, never the server repo.

When asked to enforce that split, the trap is deleting too much or too little.
Resolve it by reading what the CLIENT actually calls, not by guessing from names:

- **KEEP** every route the client hits and everything they import: the chat SSE
  route, suggestions, models, MCP, health, **and `/auth/callback`** — the RN
  *web* build reuses that OAuth return, so deleting it as "web UI" breaks Google
  sign-in on web.
- **REMOVE** the pages, the chat/glass components, the markdown renderer, and the
  UI-only dependencies (`react`, `react-dom`, `react-markdown`, `remark-gfm`,
  `tailwind`, `jsdom`) — check each is genuinely unreferenced first, and drop
  `jsdom` only after confirming no test needs a DOM.
- **REMOVE the UI E2E suite** if it drives pages that no longer exist, but keep
  and FIX the API tests: assertions like "unauthenticated /login serves the login
  page" now encode the deleted surface and must be inverted to "is 404".
- **Tag before you delete** (`git tag pre-ui-removal HEAD`) so the removal is
  reversible, and push the tag.

Verification that the split actually held: `next build` lists API routes only, and
`/`, `/login`, `/chat` return 404 — not 200, not a redirect.

## Model choice is a CONSTRAINT, not a tuning knob (user correction, hard rule, 2026-09-18)

Some product owners mandate the model. the user does: **AMA runs Claude Sonnet 4.5
for EVERY call, including small helper calls like the quick-reply chips.** Do not
substitute a cheaper or faster model to reduce latency, however good the
benchmarks look, and do not treat "it's only a tiny JSON-extraction task" as
licence to downgrade. When you feel the urge to swap the model for speed, that is
the signal you have mis-framed the problem.

What happened: the chip endpoint was optimised by defaulting it to Haiku, backed
by genuine measurements (Sonnet 3.4-5.0s vs Haiku 2.5s; Sonnet named 1/4
campaigns, Haiku 4/4). The numbers were accurate and irrelevant. The owner
overrode it forcefully ("WE NEED SONNET. NOT HAIKU! … This is unacceptable") and
it was reverted the same day.

**The latent trap — a per-request `model` field the client fills with ITS
default.** `/api/suggestions` accepted `{reply, model}` and the client sent
`DEFAULT_MODEL`. That is exactly how a heavy conversation model silently became
the helper-call model, and why "which model does this endpoint use?" had no
answer in the code. Either drop the field server-side so the endpoint owns its
model, or make the server's choice explicit in one named function.

**Where the latency actually lives (all model-independent — do these first):**

1. **When the call starts** — biggest single win. See the `onDone` timing fix
   above. ~600ms of cosmetic animation was in the user's path.
2. **Token budget** — a shared 4096 default on a ~32-token payload.
3. **Parsing** — see the brace bug below; a parse failure shows up as *missing
   chips*, not as a slow response, so it hides from latency work.
4. **Streaming the helper's output** so the first chip paints on first token.

After the revert, with Sonnet restored, reply-finished→chips still went
3.84/4.56s → 2.92/3.36s. **Most of the gain survived because it never came from
the model.** Report it that way: the revert cost less than it appears, and
claiming the model was the win would be false.

**Verify the model from the BUILT artefact, not the source.** A source read
proves intent, not what production executes. Two false signals to avoid:
- the model literal lands in a webpack **chunk**, so grepping `route.js` for it
  returns a false negative — locate the file that actually contains the
  function and read its compiled body;
- a model-picker list still names the cheaper model, so a bare
  `grep -r haiku` is a false POSITIVE.

## Helper-call parsing: a swallow-everything extractor hides its own failures

`parseSuggestions` returned **ZERO chips** whenever the surrounding text
contained a brace — it sliced from the first `{` to the last `}`, so any prose
brace broke `JSON.parse`, and the `catch` swallowed it with nothing logged.
Symptom the user sees: chips intermittently just don't appear. Symptom the logs
show: nothing at all.

Rules for extracting JSON from model output:
- **Try each `{` as a candidate start** and find its matching `}` by counting
  depth, tracking string state so a brace inside a string value doesn't end the
  object early. Return the first candidate that yields a usable payload.
- **Bound the scan** (e.g. 12 candidates) — the input is model output and may be
  brace-heavy prose.
- **Prove the fix by mutation**: write the prose-brace, trailing-brace, and
  brace-inside-a-string cases as tests and confirm the OLD implementation returns
  0 for each. A test that passes both before and after proves nothing.
- **Beware the naive partial fix**: a brace AFTER the JSON broke it too (slicing
  to the last `}` over-extends past the closing brace) — that case is why depth
  counting is required rather than "first brace to last brace".



Gating destructive tools behind a UI confirmation card is table stakes, but the
naive implementation loops forever: after the user clicks Confirm, the model
RESUMES the stream by re-emitting the tool call with a brand-new `callId`, so
a server gate checking `confirmedIds.includes(callId)` fails again and the
card re-prompts. Fix (deployed and E2E-verified):

- Client, on confirm: push BOTH the pending callId AND a synthetic marker
  `` `__confirmed:${toolName}` `` into the confirmed-ids list it sends back.
- Server gate accepts `confirmedIds.includes(tc.id) || confirmedIds.includes(`__confirmed:${tc.name}`)`.
  Every dangerous call WITHOUT the marker still gates — the marker only
  certifies the tool name, which is what the user actually approved.
- The confirmation card itself renders above the composer (not inside the
  message list) and styles to the theme's card surface — a warning-tinted
  amber background reads as brown and was explicitly rejected by the user.

## Name-based entity resolution beats UUIDs

Users say "add targeting to the the company Test Ad line item" — never a UUID.
Forcing `campaign_id` in tool schemas produces "expected string, received
undefined" failures. Give every entity-scoped tool a shared ref schema
accepting `id` OR `name`: resolve server-side per-request, org-scoped —
exact case-insensitive match → unique fuzzy `contains` → ambiguity error
listing the candidates. Same for line items nested under campaigns (resolve
via the parent campaign's org). The system prompt must tell the model to
pass names, not ids.

## Redesigning to match a reference screenshot (user's workflow, 2026-09-14)

When the user posts reference screenshots (e.g. "study these, replicate the
design exactly, don't copy X"), the contract is:

- **Replicate the design language exactly**: same Google font (self-host the
  woff2 — see `references/gemini-design-replication.md` for the recipe),
  same surface colors, same radii scale (Gemini uses 28px pills), same
  spacing/padding rhythm. "Exactly" means a side-by-side would pass.
- **Exclude exactly what the user names and nothing more** — they list
  exclusions up front ("don't copy the Gemini name", "no Upgrade button",
  "no blue band behind the input"). Substitute the product's own identity
  (name → "AmA", logo → existing logo) without re-asking.
- Restyle EVERYTHING in one pass: top bar, composer, sidebar, message
  bubbles, tool cards, chips — partial restyles look broken next to the
  reference. Keep all functionality (chips, pickers, gates) and restyle it
  to fit the new language rather than removing it.
- Verify with side-by-side vision checks: screenshot the result at mobile
  AND desktop, list every element the reference shows, and check each one.

## Mobile-first is a hard requirement for chat UIs

The user reviews chat products on a phone first. Requirements verified
against a reference screenshot and a real 390×844 device emulation:

- **Light theme only — dark mode was REMOVED entirely (2026-09-18), superseding
  the earlier "dark only on explicit toggle" rule below.** The user asked to
  disable dark mode "for now" and remove the toggle. Dark mode is now commented
  out, not deleted. Two lessons:
  - **Removing the toggle does NOT disable dark mode.** The scheme fell back to
    the DEVICE preference (`useColorScheme()` / `prefers-color-scheme`), so a
    user with a dark OS got a dark app with no way back — the visible control was
    the *exit*, not the *behaviour*. Disable at the chokepoint every consumer
    reads (here one `useTheme()` hook), not at the surface. Full recipe:
    `web-to-react-native-migration` → `references/feature-disable-and-theming.md`.
  - **"For now" means comment, don't delete.** Mark each disabled region with WHY
    plus the restore steps, and keep the handler functional so restoring is a
    one-line uncomment. Keeping `scheme` typed `"light" | "dark"` on the context
    lets every existing `scheme === "dark"` branch keep compiling and simply
    never fire.
  - Verifying it needs a positive proof + a mutation test — asserting on
    `document.body` is vacuous on RN Web (the root is transparent under BOTH
    schemes), and "no dark colours found" is also what a blank page reports.
  - Original rule (kept as context, no longer the desired end state): light theme
    default; dark only on explicit toggle — don't key the default off
    `prefers-color-scheme`, since users expect the default they were shown.
- Composer = floating rounded card (rounded-2xl, border, subtle shadow) with
  borderless input inside and an icon send button — not a full-width
  top-bordered bar.
- Sidebar: static column ≥768px, overlay drawer with backdrop on mobile
  (`window.innerWidth < 768` at mount). Hamburger always visible in the top
  bar; `h-[100dvh]` (not `h-screen`) so mobile browser chrome doesn't clip
  the composer.
- **Sidebar starts CLOSED on every load and refresh, on EVERY viewport**
  (user request, 2026-09-14: "the side menu is hidden/unactive by default.
  Until they press the burger menu to open"). Initialize the state to
  `false` and do NOT auto-open it on desktop — the common default of
  `useState(true)` + "close it only if mobile" is the wrong way round here.
  Verify by reading `aside.getBoundingClientRect().width === 0` on fresh
  login AND again after an explicit `page.reload()`, then non-zero after the
  burger click.
- **No horizontal scroll, ever**: `overflow-x: hidden` on body and the main
  column, `overflow-x-auto` only on data tables; verify with
  `document.documentElement.scrollWidth > window.innerWidth`.
- **No zoom-on-focus (iOS)**: inputs/textarea at 16px on <768px (CSS media
  override), viewport meta `maximum-scale=1, viewportFit=cover`, and
  `env(safe-area-inset-bottom)` padding under the composer.
- Buttons with long labels (model pickers, chips) need `whitespace-nowrap` +
  `truncate` + `max-w` or they wrap to 3 lines on narrow screens.

## Design follow-up micro-iterations are the norm (user's workflow, 2026-09-14)

After the initial replication the user ships a rapid series of one-line visual
corrections, each with a screenshot ("remove the things in green", "the cog
should be a dark/light toggle", "the icon while waiting should be a spinner",
"only 2 lines of quick replies on mobile"). Handle them as a batch discipline:

- **Iterate on the live deployed app, not a plan.** Each batch: patch → tsc →
  next build → commit+push → rsync+docker rebuild → Playwright/vision verify
  → report. Do not propose mockups or ask which variant; just ship.
- **The user QUEUES work mid-flight** — "after you have completed that, do
  this", plus mid-turn out-of-band messages that arrive while you are already
  deploying. Treat each queued item as its own self-contained batch: finish
  and verify the in-flight one, then immediately start the next; do NOT fold
  two unrelated asks into one commit, and do NOT stop to ask whether to
  proceed. Committing them separately keeps each revertable and each report
  checkable. If a queued ask arrives while a deploy is still running, finish
  the deploy + verification first (the repo must be clean before the next
  patch), then move on.
- **When the user points at a color in a screenshot ("brown", "light blue
  faded bg"), hunt the token**, not the component: the "blue tint" was
  `--background: #f0f4f9` + `--muted: #e9eef6`, both swapped to pure
  `#ffffff`/`#f2f2f2` when he said "It should be white" (later confirmed
  again for light AND dark mode). "Remove the background" can also mean a
  literal overlay div — grep for the gradient before assuming it's a token.
- **Icon semantics matter more than the icon set**: a theme toggle must show
  the mode it will switch TO (moon in light mode, sun in dark mode), which
  requires reactive React state synced from `documentElement.classList` on
  mount — a stateless onClick toggle can't do it.
- **Streaming indicator — scope it to the LAST message, not the flag
  (corrected 2026-09-14 after a user-reported bug)**: users read a pulsing bar
  as "stuck". Replace with a circular spinner (`animate-spin rounded-full
  border-2 border-x-muted border-t-primary`). The naive version gates the
  spinner on the global `streaming` boolean INSIDE the per-message render —
  which paints a spinner on EVERY assistant bubble in the thread at once
  (user: "Loading spinner can be seen in previous box after sending new user
  chat message… only show in the new assistant chat message bubble"). Compute
  a per-message flag in the map and use it everywhere:
  ```tsx
  {messages.map((m, index) => {
    const isStreamingTarget = streaming && index === messages.length - 1;
  ```
  SECOND HALF of the same bug: the assistant bubble was only rendered when
  `m.content` was non-empty, so during the first-token wait the NEW message had
  no bubble at all while the OLD one wore the spinner. Render the bubble when
  `m.content || isStreamingTarget` and guard the markdown child separately.
  Assistant replies render inside a white card bubble with the shared card
  shadow (user request: "AI assistant chat response should be in a white
  bubble, like the smaller white bubbles around the tool calls").
  Verify mid-stream with a per-message spinner census, not a total — assert
  `max simultaneous == 1`, `spinner on an earlier message == False`, and
  `0 after completion`. Ready probe: `scripts/streaming_spinner_probe.py`.
- **Capping quick-reply rows on mobile**: `max-h-[84px] overflow-hidden
  sm:max-h-none` on the chip wrapper is enough (2 rows at ~13px chips +
  gap); no JS needed.
- **Exact-hex background swaps go in the CSS variable, not the component**:
  when the user gives a literal color for the main shell ("use #fafdff as
  the background"), change `--background` in globals.css — every surface
  using `bg-background` (chat, login) picks it up. Verify with
  `getComputedStyle` on the shell div.
- **White cards are invisible on near-white surfaces without the shadow**:
  after moving to `#fafdff`, `bg-card` starter buttons "disappeared" —
  "same background as the assistant reply bubble" really meant the same
  CARD TREATMENT (white bg + the soft two-layer shadow
  `0_1px_3px_rgba(0,0,0,0.08),0_4px_12px_rgba(0,0,0,0.06)`). Reuse one
  shadow token for all floating cards (assistant bubble, tool cards,
  composer, starters) so they read as one material.
- **Cap bold text at font-weight 500 when the font only ships 400/500**
  (Google Sans, Product Sans): 600/700 triggers faux-bold synthesis with
  artificially thickened strokes. Belt: markdown `strong` renderer + table
  headers use `font-medium`; braces: global CSS
  `strong, b { font-weight: 500 !important; }`. Verify by reading
  `getComputedStyle(el).fontWeight` on rendered bold spans.
- **On interrupted tool calls (orphan recovery), re-inspect before
  retrying**: `git status` / `git log -1` first — the commit may already
  have landed, and blind retries double-commit. A background deploy that
  was cut off gets polled with `process poll/wait`, not re-run.
- **Never hide a hover-revealed control with `display` — it re-enters the flex
  flow and moves the row.** A sidebar delete button was `hidden
  group-hover:block`. Hovering put it into the flex flow *for the first time*,
  and its 28px box (16px icon + `p-1.5`) was taller than the 22.5px text line,
  so the row grew 5.5px and the vertically-centred title dropped 2.75px — which
  the user reported, correctly, as "the text inside the button moves down by a
  couple of pixels". It ALSO stole 32px of width, so the title re-truncated on
  hover: one cause, three visible symptoms, and the user only saw the middle
  one. Fix: take the control OUT of the flow (`absolute` + `right-2 top-1/2
  -translate-y-1/2`), reserve its space statically on the row (`pr-10`), and
  toggle **opacity only**. Add `pointer-events-none` so an invisible control
  isn't clickable at rest. On touch there is no hover, so mobile keeps its
  own path (swipe-to-reveal) — scope the reserved padding with a breakpoint.
  **A 2.75px shift reads as "seamless" in a screenshot**, so this class of bug
  is only findable by MEASURING idle-vs-hover geometry:
  `getBoundingClientRect()` on the row and the title before/after
  `.hover()`, asserting deltas < 0.5px on row height, title y AND title width.
  Commit that as an E2E assertion — it is cheap and it fails loudly.
- **Spacing corrections: compute the delta, don't eyeball the token.** "Add
  about ten pixels between each item" against `space-y-0.5` (2px) means
  `space-y-3` (12px) — 2 + 10. State the arithmetic in the commit and verify by
  reading the actual gaps between rendered boxes, not by looking at a
  screenshot.
- **Interactive rows need an explicit pointer cursor** (2026-09-14): a sidebar
  conversation row is a `<div>` with pointer handlers, not a `<button>`, so it
  inherits `cursor: default` and the user notices ("when hovering on recent
  chat bubble, please show pointer mouse icon"). Put `cursor-pointer` on BOTH
  the row container and the inner (pointer-events-none) text node.
- **Long labels: shrink the font, don't truncate the words.** Asked to change a
  short brand wordmark ("AmA") to a longer phrase ("Ask Me Anything") and told
  to "make the text small enough so it can be read properly. View it yourself
  and decide how small" — the answer is a size that fits the full phrase on one
  line at drawer width (15px in a 320px drawer, 17px ≥640px), plus
  `min-w-0 truncate` only as overflow insurance. Verify `scrollWidth ===
  clientWidth` on the element AND check the screenshot: an ellipsised product
  name is worse than a smaller one. Decide-and-report, don't ask.
- **Attribution footers go directly UNDER the thing they describe**: "Powered by
  the company.ai" with the brand logo belongs beneath the starter/quick-message
  cards (centred, muted 11px "Powered by" + logo image), not in the sidebar or
  the top bar. Assert each card's `bottom <= footer.top` rather than eyeballing
  it, and constrain the logo by HEIGHT (`h-5 w-auto`) so wide horizontal
  wordmarks keep their aspect ratio.
- **Trim transparent padding off supplied logo PNGs before shipping them.**
  Attachments often arrive with a large transparent border, which makes
  height-constrained logos render tiny. `im.split()[-1].getbbox()` → `im.crop()`
  (here 1053×246 → 974×154). If the user names a file that isn't on disk
  (`company-logo.png`), use the image attached to the thread and SAY so in the
  report — offer to swap in the real source file.
- **Never set BOTH width and height on a logo you didn't measure.** Asked to
  "double the size of the logo", the naive edit is `h-[144px] w-[144px]` from
  the old `72×72` — but the AMA mark is naturally **423×380**, so a pinned
  square squashes it. Read `img.naturalWidth/naturalHeight` FIRST, then set
  only the constrained axis and let the other follow: `className="h-[144px]
  w-auto"` with the matching `height` attribute. Verify the rendered box
  (`160×144` for a 423×380 source) preserves the source ratio — and view the
  screenshot, since a mild squash passes numeric checks but looks wrong.
  Same rule for horizontal wordmarks: constrain by height (`h-5 w-auto`).
- **Saved-chat lists need platform-appropriate delete affordances**: mobile =
  swipe right-to-left
  on the row to reveal a red delete action behind it (translateX the row over
  an absolutely-positioned button, lock axis after ~8px so vertical scroll
  still works, snap open past ~40px else snap shut, tap-when-revealed closes
  instead of opening), desktop = keep hover-revealed trash. BOTH paths must
  open a shared confirm modal ("Delete chat? … cannot be undone") before
  deleting — never delete on the raw gesture. E2E: dispatch synthetic
  PointerEvents (pointerType 'touch') in one evaluate and read the row's
  computed `transform`; for the hover trash assert computed `display`
  none→block. Playwright's own `hover()` on a row behind a sliding
  div will hit "intercepts pointer events" on the reveal button — target the
  correct inner button (`:scope > div > button`) in selectors.
  **Mouse drags and CDP touch events DO NOT exercise a touch-only handler** —
  see `references/mobile-e2e-playwright.md` § Touch gestures for the exact
  dispatch recipe that works.
- **The reveal action bleeds past a rounded row (user-reported "red border")**:
  an absolutely-positioned reveal button with square corners sitting behind a
  `rounded-full` row leaks its corners past the parent's curve — the user sees
  thin red arcs at the right edge of every list row and reports it as a
  "red border". Two fixes, apply BOTH: (1) match the outer edge
  (`rounded-r-full overflow-hidden` on the reveal button) and (2) render
  nothing at rest — `opacity-0 pointer-events-none tabIndex={-1}` driven by
  `offset < 0`, fading in only while swiped. Verify by walking every element in
  the container and asserting no element with a destructive background or text
  colour has `opacity !== '0'`.
- **Drawer closes on outside click — and the toggle must stopPropagation**:
  put the `onClick={() => sidebarOpen && setSidebarOpen(false)}` on the MAIN
  COLUMN wrapper (sibling of the `<aside>`), not a document listener. The
  hamburger that toggles it needs `e.stopPropagation()`, otherwise its click
  bubbles to the wrapper and instantly recloses the drawer the same tick.
  Verify with a click at a far-from-drawer coordinate, then read
  `aside.getBoundingClientRect().width === 0`.
- **Aligning a drawer header with the main top bar**: matching
  `pt-4` on both is not enough — the bar's control is a 48px square/circle
  while the drawer's wordmark is a ~22px text line, so their *centres* differ
  even when their *tops* match. Give the drawer header the same
  `h-12 items-center` box plus `leading-none` on the text; centre offsets of a
  few px then read as one line visually. Confirm with a screenshot, not the
  numeric centres alone.
- **Vision upload wiring** (added 2026-09-14, E2E-verified with the real
  logo): `+` button → hidden `<input type=file accept=image/* multiple>` →
  FileReader to data URLs → thumbnails with remove buttons above the pill →
  send as `{mime, base64}` array on the LAST user message only → API filters
  to `image/(png|jpeg|webp|gif)` under ~4 MB, max 4 → provider mapping:
  Anthropic native `image` source blocks, OpenAI/OpenRouter data-URL
  `image_url` content parts. NOTE: Anthropic rejects some synthetic images
  ("Could not process image") — test with a real photograph or a served
  PNG, never a hand-built 1×1 base64 PNG.

## Working style for this user on these apps (verified repeatedly, 2026-09-14)

- **Ship, don't propose.** Each request is a small batch: patch → `tsc --noEmit`
  → `next build` → commit+push → rsync + `docker compose up -d --build` →
  Playwright/vision verify → report with the numbers. Never answer a visual
  correction with a mockup, a variant menu, or "which would you prefer" —
  pick the defensible default, state exclusions, and deploy.
- **Report with evidence, and lead with what the user asked about.** Open the
  completion message with their item, then any extra findings. Quote real
  measurements (`transform: translateX(-72px)`, `200 font/woff2 49896`,
  `Google Sans/400/loaded`) rather than adjectives.
- **Surface adjacent bugs you trip over, clearly separated.** Swipe-delete
  verification is what turned up the font-loading bug; reporting it as
  "bonus bug found and fixed" was correct. Don't bundle it into the main
  claim as if it were part of the request.
- **When a check fails, distinguish harness from product before reporting.**
  Three separate "failures" here were test-harness artifacts (mouse events not
  producing touch, a bad localStorage seed, a selector hitting a covered
  button). Say which it was — never report a harness bug as a product bug,
  and never quietly retry until green.
- **Do not announce a side effect before verifying it exists.** After the E2E
  run I offered to "clean up the test conversation in your sidebar" — but the
  conversation history is `localStorage` in a throwaway Playwright profile, so
  there was nothing to clean. The cost of checking is one command; the cost of
  the claim is that the user starts worrying about data they don't have. Verify
  the mechanism (server-side vs client-side state, which profile was used)
  before flagging a risk.
- **When the user asks "test e2e and ensure everything works", that means the
  full surface, not the feature just changed.** Auth/redirects, every tool flow,
  the confirmation gate, persistence across reload, theme, mobile 390, console
  errors — a suite of ~60 assertions. Building it once and committing it beats
  re-deriving probes each session, and it is what caught the fabrications that
  four rounds of targeted manual fixes missed.
- **A "bonus bug" report must not overclaim.** Finding the font-loader bug
  while verifying swipe-delete was real and worth surfacing — but saying the
  product "rendered in a system fallback font for weeks" was a claim the
  evidence didn't support (the fix had been committed in the same session
  chain). Report the mechanism and the measurement; don't extrapolate a
  duration you never observed.
- **Linear/project board stays current** when the user has asked once.

## Auth middleware silently swallows self-hosted fonts (verified 2026-09-14)

The auth middleware that guards these apps excludes static assets by a
negative-lookahead extension list. That list is a **denylist** — anything you
add later is intercepted until you add it. A self-hosted brand font
(`/GoogleSans-400.woff2`) was being 307-redirected to `/login`, so the browser
received an HTML page as a "font" and the whole product quietly rendered in a
system fallback for weeks. The console is the only visible symptom:

```
Failed to decode downloaded font: …/GoogleSans-400.woff2
OTS parsing error: invalid sfntVersion: 1008813135
```

`1008813135` = the bytes `<!DO`, i.e. an HTML document served where a font was
expected. Fix — exclude font extensions in the matcher:

```ts
"/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico|woff2?|ttf|otf)$).*)"
```

Rules: (1) whenever you add a new public asset type (`wasm`, `mp4`, `pdf`,
manifest `json`), extend the matcher in the same commit; (2) verify with
`curl -D -` for `200` + `content-type: font/woff2` AND `document.fonts`
status `loaded` AND a resolved `fontFamily` — a screenshot of correct-looking
type is NOT evidence the font loaded; (3) do this on every app whose auth
middleware fronts the public dir, and re-check after any middleware change.
See `references/mobile-e2e-playwright.md` § Verifying static assets.

## Verify E2E — including mid-stream

"Build passed + final answer correct" is NOT done for a chat UI. Verify:

- **Commit the E2E suite into the repo as infrastructure.** A suite that lives in
  `/tmp` dies with the session, and these assertions are the only thing standing
  between a plausible-sounding reply and a fabrication. Ship `e2e/e2e.py` +
  `e2e/README.md` and an `npm run e2e`. Make it self-sufficient: read the account
  password from `$AMA_PW` (never from the file), and if the browser library isn't
  a project dependency, have the script re-exec itself under a venv that has it.
  Document the honesty assertions as load-bearing so they aren't deleted later.
- **Escalate prompt → code after a fabrication recurs a SECOND time.** Four
  successive prompt rules still let the model invent a record on the live app;
  one deterministic server-side guard took it to zero uncorrected in 64 trials.
  Prompt rules are probabilistic. Do not keep rewording them.
- **A regex honesty guard MUST strip markdown before matching, or it silently
  misses half the fabrications.** The deployed guard was code-identical to
  local, its unit tests were green, and it still shipped a fabrication because
  the model emitted `Here's **AI: Brand: Outdoor Enthusiast** — a card…` and the
  pattern wanted a literal `here's ai:` with a space — the `**` broke the match.
  Worse, the DOM assertion passed anyway: `innerText` strips the asterisks, so
  the reply *looked* clean. Fix: a `stripMarkdown()` normaliser (bold/italic/
  code + curly→straight quotes) run before every pattern. Reproduce the class of
  bug with a variants test — one visible sentence, N raw renderings — which is
  what turned "intermittent" into "4 of 10 variants escaped". Full recipe:
  `references/honesty-guard-and-raw-stream-assertions.md`.
- **Assert honesty on the RAW SSE stream, not just the DOM.** The raw stream is
  what the server sent and what the user can quote; `innerText` is a lossy
  projection of it. Parse the captured `data:` frames for `text`/`replace`
  events and assert there. Keep the DOM assertion too — but the raw one is the
  load-bearing check, and its absence is exactly how a fabrication shipped to
  production behind a green suite. Tolerate the HONEST echo: a correct
  "I couldn't find a creative named **X**" legitimately contains the name, so
  fail only when a sentence both names the entity AND asserts it.
- **Gate card-based assertions on the tool call having happened; keep honesty
  assertions unconditional.** The model intermittently skips a mandated lookup
  when an EARLIER turn already listed the same entities — measured 1/4 runs with
  a preceding coverage turn vs 4/4 without, sometimes making zero tool calls.
  No lookup means no error card, so "the card shows the failure reason" fails
  even though the reply was honest. That is prompt adherence, not honesty.
  Print `[SKIP]` for the card checks when no lookup occurred; never relax the
  fabrication checks. And do not treat one flaky red run as a regression from
  your own change — isolate it (fresh context vs warm context) before believing
  either explanation. Add the prompt rule too: "a list you saw in an earlier
  turn is not a lookup, and you cannot search it for one name".
- **Verify the suite doesn't mutate production data.** A write-confirmation test
  attempts a real write — after the run, read the join table back and confirm it
  is unchanged rather than assuming the Cancel path held. And check whether
  conversation history is server-side or `localStorage` before telling the user
  the tests "left a conversation in their sidebar".
- **Mid-run `ERR_CONNECTION_REFUSED` is usually the test server, not the app.**
  Locally-launched dev servers die between tool calls (process-group reaping).
  Curl the health endpoint before every batch, and launch detached
  (`start_new_session=True`) so the server outlives the shell that started it.
- **Seed `localStorage` directly instead of driving the UI to set up test
  state.** Driving the app to produce 3 conversations wasted a run: the main
  column's click-outside handler swallows clicks aimed at the sidebar
  ("intercepts pointer events"), and the app's own New-chat flow fought back.
  Writing the persisted key in one `page.evaluate` then reloading is instant and
  deterministic — the app reads its own store on mount exactly as it would after
  a real session. Look up the persistence key + record shape from the source
  first (`ama_conversations`: `{id,title,messages[],updatedAt}`), seed
  generously (long titles, to catch truncation), and keep it in the probe, not
  the product.
- **A "failure" that only reproduces inside the full suite is a CONTEXT bug,
  not a timing bug — bisect the preceding turns.** Two assertions failed in the
  suite but passed in an isolated repro. Rather than calling it flake, build a
  two-arm experiment (warm context = the suite's preceding turn; plain context =
  without it) and run each N times. Result was unambiguous: 1/4 vs 4/4. The
  preceding coverage turn was the trigger. This is the general shape — when N/N
  isolation passes but the suite fails, the difference is whatever ran before,
  so vary exactly that.
- Real login with a real account (ask the user for test credentials if needed).
- **Credentials for a redeployed/compounded app can be recovered from past
  sessions** — don't burn attempts guessing: `session_search` with the
  account email + "password" surfaces earlier tool calls that used them
  (Supabase auth payloads embed the password in plaintext).
- Send the flagship prompts ("what campaigns am I running?") in a real browser.
- **Inspect the mid-stream state** (screenshot + DOM probe): no raw rows, no UUIDs, no visible `**`, no raw `|` rows. The user WILL screenshot mid-stream.
- DOM-level assertions beat screenshots: count UUIDs in `document.body.innerText`, count `<details>` open state, check `document.querySelectorAll('table')`.
- Negative tests: injected `org_id` in tool args is stripped; cross-org id returns not-found.
- `crypto.randomUUID()` crashes over plain HTTP (tailnet/LAN) — ship a fallback uuid helper for non-secure contexts.
- OAuth via a shared auth provider redirects to the provider's configured allowlist; if login bounces to the OLD app, add your URL to the allowlist (dashboard access needed — tell the user exactly what to add).
- **Mobile E2E = real device-emulation Playwright run, not a resized
  desktop screenshot.** `new_context(viewport={390×844}, is_mobile=True,
  has_touch=True)`; assert `document.documentElement.scrollWidth ==
  window.innerWidth` both on the empty state AND mid-conversation (wide
  markdown tables break overflow only when they exist); read the computed
  `font-size` of the textarea (must be 16px on mobile); screenshot home,
  input-focused, chat, and drawer-open states. See
  `references/mobile-e2e-playwright.md` for the ready script. NOTE: a
  shared browser session is desktop-only — mobile claims require the
  headless device-emulation run.
- **A cookie-less health check is not proof the live URL works for the
  user.** `curl` sends no cookies, so it never reproduces auth-cookie-driven
  failures — a 502 that only the user sees (and only in one browser) sails
  straight through a green `curl -o /dev/null -w "%{http_code}"` check, and
  every deploy for weeks reports success. When the user reports a live error
  you cannot reproduce, reproduce their **cookie jar and user-agent**, not
  just the URL. See the nginx section below and
  `references/nginx-502-auth-cookie-headers.md`.
- **Sibling trap, same root cause — an unauthenticated request cannot verify ANY
  route behind auth middleware. Load every route, especially the BARE ROOT, as a
  SIGNED-IN user.** `src/app/page.tsx` was still the untouched
  `create-next-app` scaffold for the entire life of an app, so any signed-in
  visitor to `https://host/` got Next.js boilerplate ("Get started by editing
  src/app/page.tsx") instead of the product. The user found it; my own check had
  reported the root healthy, because auth middleware redirects anonymous traffic
  to `/login` BEFORE the root page renders — so an unauthenticated curl returns
  `307 → /login` and looks perfect. The E2E suite compounded it by only ever
  loading `/login` and `/chat`, never `/`.
  - Fix the route, then make the ROOT a first-class assertion: authenticated `/`
    is not the scaffold, lands on the app path, and carries the app's chrome;
    anonymous `/` redirects and never shows the scaffold. Cheapest form — a
    `page.evaluate` on `document.body.innerText` matching scaffold strings
    (`/Get started by editing|Deploy now|Read our docs|nextjs\.org/`) against
    product strings.
  - Generalize: **audit an app of unknown provenance for leftover
    `create-next-app` template content** — `next.svg` / `vercel.svg` / `file.svg`
    / `globe.svg` / `window.svg` sitting unreferenced in `public/`, and "Get
    started by editing" in any `page.tsx`. Unreferenced scaffold SVGs are the
    tell that a root page was never replaced.
  - A scaffolded root also means the app's real entry point is a SUBPATH
    (`/chat`) — check where login and OAuth callbacks actually redirect before
    assuming `/` is the entry, and make `/` forward there
    (`redirect(user ? "/chat" : "/login")`).
  - This hid behind three green signals at once (unauthenticated curl, unit
    tests, an E2E that never visited `/`). Whenever a user reports "I just see X"
    at a URL you believe is fine, **reload that exact URL as an authenticated
    user** before theorising about deployment, caching, or staleness.

## Hosting behind nginx on a shared box (docker + TLS)

When the app deploys as an isolated docker compose project on a server that
already runs other services behind nginx:

- Bind the container to **loopback only** (`127.0.0.1:3210:3200` in compose).
  Binding `0.0.0.0` on the app's target port blocks nginx from listening and
  yields ERR_SSL_PROTOCOL_ERROR in the browser — and rsync deploys that
  overwrite compose will silently revert the fix, so commit the loopback
  mapping in the repo.
- nginx vhost terminates TLS on the public port with the host's existing
  cert, proxying to loopback with streaming-safe settings: `proxy_http_version
  1.1`, Upgrade headers, `proxy_buffering off`, long read timeout (SSE
  breaks otherwise). Remove stray `sites-enabled/*` backup files — a
  duplicate `default_server` fails `nginx -t` for the whole box.
- Health endpoint (`/api/health` → `{"ok":true}`) + curl-through-TLS check in
  the deploy command verifies the full chain, not just the container.
- **502 Bad Gateway with a HEALTHY container = nginx proxy buffer overflow,
  not a dead app.** Supabase/NextAuth chunked auth cookies make the response
  `Set-Cookie` headers exceed nginx's 4 KB `proxy_buffer_size` default
  (`upstream sent too big header while reading response header from upstream`).
  It is browser-dependent (Brave 502s, Safari doesn't — differing cookie jar
  sizes) and **cookie-less curl returns 200 every time**, which is exactly why
  it reads as "transient" and gets missed. Raise `proxy_buffer_size` /
  `proxy_buffers` / `proxy_busy_buffers_size`; note
  `client_header_buffer_size` / `large_client_header_buffers` are valid at
  `http`/`server` level ONLY — putting them in `location` fails `nginx -t` and
  leaves an invalid config on disk. Always read `nginx/error.log` before
  dismissing a 502 as transient, and verify with a forged ~5.6 KB `Cookie:`
  header plus a real browser login. Full recipe, contexts table, deploy
  sequence and verification:
  `references/nginx-502-auth-cookie-headers.md`. This fix lives on the SERVER,
  not in the repo — say so in the report.

## Ops

- Tailnet/LAN hosting: `next start -H 0.0.0.0 -p <port>`; users access via MagicDNS name. Mention reboot persistence (systemd) as an option.
- **Before planning any "rewrite/port this to <other stack>" ask, first ask what CANNOT move.** Server-only secrets (LLM/provider keys, service-role DB keys, admin tokens) mean the server cannot be dropped — so an "architecture switch" to React Native / a desktop shell / a mobile app is usually a **CLIENT** migration with the existing Next.js server kept as the API. That single check turns a rewrite into a re-render: the tool layer, LLM plumbing and the honesty guard keep working untouched. Then look for an already-existing Bearer/token auth path on the API routes before designing one. Also freeze the SSE event protocol as the migration contract and treat bespoke glass/effects as a rewrite, not a port. Full worked example (RN, incl. platform glass fidelity table and the questions to put to the user):
  `the company` skill → `references/react-native-migration-assessment.md`.
- Keep a Linear/project board updated as work happens when the user asks once — create issues with Done checklists of what actually shipped, post project updates at milestones, and delete/repoint duplicate blocker tickets.

## Pitfalls

- "Model X selected" must mean model X runs: client always sends its selection; server default = first provider with a configured key; per-provider clear error if a key is missing (the OpenAI SDK's error otherwise names the wrong env var and confuses everyone).
- Don't fabricate the tool's auth path — audit the existing service's actual auth middleware before wiring credentials.
- After any isolation claim, run a programmatic check with the user's real account (super-admin accounts are the harshest test) and quote the numbers.