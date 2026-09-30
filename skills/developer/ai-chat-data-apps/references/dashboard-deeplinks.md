# Deep links from an assistant reply into the platform UI

Session-derived (AMA + app.example.com, 2026-09-21). Request: *"Please include deep
links in the MCP/Chat for the app.example.com pages that users of AMA can click and
open the page relevant to what they are seeing in the current assistant message.
The deep link must be included in the assistant message every time (where
applicable)."*

The feature existed and was **completely dead** — the renderer swallowed every tap.
Then, once taps worked, the links landed on a page that **crashes in Firefox**.
This file records the verified route map, the browser-specific root cause, the
design that makes one change cover both surfaces, and the ways it silently fails.

---

## 0. The Firefox-only crash (read this before trusting ANY route)

User report, verbatim: *"I clicked the link, and it didn't send me to the right
page. Also, I saw this on the page that it sent me to: 'Dashboard Error / The
operation is insecure.'"*

Root cause, from the real error — not a guess:

- `/dashboard/ads` (AdsManager) **subscribes to Supabase realtime** in a mount
  `useEffect` (`supabase.channel('ads-changes').on('postgres_changes', ...).subscribe()`).
- The dashboard ships its CSP in a **`<meta>` tag**, and that policy's
  `connect-src` has no entry for the Supabase realtime WebSocket origin
  (`wss://<ref>.supabase.co/realtime/v1/websocket`).
- **Firefox throws the blocked connection as `NS_ERROR_CONTENT_BLOCKED` and it
  propagates into the page's `ErrorBoundary`.** Chromium logs the identical
  refusal as a console *warning* and continues.
- The boundary renders `error.message`, which is why the user saw a generic
  "The operation is insecure" (Firefox's wording) rather than a CSP message.

**Everything about that page looked fine from my side:** `curl` → 200 (SPA
fallback), the router had the route, and a Chromium E2E passed. Three independent
green checks, all blind to the same thing. **Reproduce with
`p.firefox.launch()`.**

### Getting the real error out of an ErrorBoundary

The boundary logs `console.error("[ErrorBoundary]", error, errorInfo)`, and the
on-screen text is only the fallback. Two traps when capturing it:

- A `DOMException` **serialises to `{}`** through `JSON.stringify` (its `name` and
  `message` live on the prototype) and is **not `instanceof Error` in every
  browser** — so the obvious probe logs `{}` and reports nothing useful. Read
  `x.name` / `x.message` explicitly.
- You must hook **before** any page script runs, i.e. `page.add_init_script(...)`.
  An injected-after-load hook misses the throw.

```python
await page.add_init_script("""
(() => {
  window.__errs = [];
  const orig = console.error;
  console.error = function(...a) {
    window.__errs.push(a.map(x => {
      if (x && typeof x === 'object' && (x.name || x.message))
        return 'NAME=' + x.name + ' MSG=' + x.message;
      try { return JSON.stringify(x).slice(0,200); } catch(e) { return String(x); }
    }).join(' || '));
    return orig.apply(console, a);
  };
})();
""")
page.on("pageerror", lambda e: logs.append(str(e)))
# → NAME=NS_ERROR_CONTENT_BLOCKED  STACK=connect@.../supabase-*.js
```

### The lesson that generalises

**When the user's error text is not one your browser produces, you are testing the
wrong browser.** "The operation is insecure" is Firefox. Pin the browser in the
verification script and say why in the file header, so a later agent does not
"simplify" it back to Chromium and re-break the check.

---

## 1. The verified route map (and the decoys)

**Method matters more than the table.** Three checks all pass a link that is
broken for the user — run all three before believing a route works:

1. `curl` proves NOTHING. The host serves `index.html` for EVERY path, so
   `curl -o /dev/null -w '%{http_code}'` returns **200 for a path that renders
   nothing**.
2. Reading the router also proves nothing — routes exist that never use their
   params (see the decoys below).
3. **A page can render in Chromium and CRASH in Firefox.** See §0 above. This one
   shipped a broken link.

So the only reliable method: log in for real, visit the candidate, and assert the
destination RENDERED (the row count changed; the id appeared in a REST call via
`page.on("request")` filtered to `rest/v1`) — **in FIREFOX**.

| Candidate | Reality (measured, signed in, in Firefox) |
|---|---|
| `/dashboard/ads` | **BROKEN — never link here.** See §0. Subscribes to Supabase realtime on mount; Firefox's CSP refusal reaches the page's ErrorBoundary as "Dashboard Error / The operation is insecure". Chromium logs the same refusal and carries on, so this looks healthy in Chromium. |
| `/dashboard/ads?campaign=<id>` | **BROKEN** (same page, same crash). The `campaign` param itself was verified functionally — the table went 23 rows → that campaign's 5 and the request became `ads?...&campaign_id=in.(<id>)` — but the page it filters cannot render. Do not link it. |
| `/dashboard/ads/<line-item-id>` | **WORKS** — the per-item page is a DIFFERENT component (`ads/:id` → `Edit.tsx`, `const { id } = useParams()` → `getAdWithIncludes(id)`) with no realtime subscribe. **This is the correct line-item link.** |
| `/dashboard/campaigns` | real, flat list. **No per-campaign page exists** — a campaign row opens no detail view. |
| `/dashboard/creatives/library` | real |
| `/dashboard/creatives/<id>/versions` | **WORKS** — issues `advertiser_creatives?...id=eq.<id>` and `creative_versions?...creative_id=eq.<id>` |
| `/dashboard/creatives/<id>/edit` | **DECOY.** Route declared, returns 200, but the editor never reads the id: NO request contained it and it rendered an empty shell. |
| `/dashboard/creatives/approvals` | **DECOY.** Super-admin only; every other role is a `<Navigate>` to the library, so the intent is discarded. |
| `/dashboard/reporting`, `/reporting/builder`, `/reporting/manager` | real |
| `/dashboard/brand-intel/brands/<id>` | real — declares `brand-intel/brands/:id` and requests carry the id |
| `/dashboard/analytics`, `/reporting/delivery-transparency`, `/settings` | `<Navigate>` redirects — they merely land on `/reporting` and `/profile`. |

Corroborate the router with the app's OWN nav: click each sidebar label and record
where it lands. That is authoritative in a way the route table is not
(`"Line Items"` → `/dashboard/ads` is the kind of mapping a guess gets wrong).

**Record the decoys in the code**, next to the link builder, so a later change
does not "restore" one.

---

## 2. One change covers chat AND MCP

Both surfaces consume the same registry: the chat route via `toolsForLlm()` →
`TOOLS`, and the MCP route via `import { TOOLS }`. So decorate the shared
`withValidation` wrapper, not each tool:

```ts
const result = await t.execute(parsed, ctx);
if (result == null || typeof result !== "object") return result;
const obj = result as Record<string, unknown>;
if (typeof obj.error === "string" && obj.error.trim()) return result;   // no link on failure
const links = linksForToolResult(t.name, result);
if (!links) return result;
return { ...obj, links: { primary: links.primary, related: links.related ?? [] } };
```

Properties worth keeping:

- **Success only.** A `{ error }` soft failure with a link invites the user to click
  through to a page about something the tool could not read.
- **Link building is a pure, tool-name-keyed function** in its own module, so the
  wrapper stays a pipeline rather than a second routing table.
- **Only ids the tool itself returned** build a URL — never a guessed name — so a
  link cannot point at another organization's object.
- MCP verified separately: `tools/call` returned `links` inside BOTH `content[].text`
  (the stringified payload) and `structuredContent`.

### The nested-payload trap

Tool results wrap their object under their own key, so a top-level id read produces
**no link at all — no throw, no log**:

```
get_campaign          → { campaign: { id, name, ... } }
list_line_items       → { campaign: {...}, line_items: [...] }
get_line_item         → { line_item: { id, campaign_id, ... } }
get_creative          → { creatives: [{ id, ... }] }          ← id inside the array head
create/activate/update_campaign_status → { <verb>: true, campaign: {...} }
get_budgets           → { campaigns: [...], line_items, totals }   (org-wide; no single id)
```

Read the tool source for each shape; then walk the known wrappers and **fall back to
the general page** rather than emitting a URL containing `undefined`.

---

## 3. THE bug: a styled link that swallows every tap

```tsx
onLinkPress={() => false}      // BUG
```

`react-native-markdown-display` applies the `link` style (accent colour +
underline) and then, because the handler returned `false`, handles nothing. The
link renders as a real `span` with `text-decoration: underline` and
`color: rgb(11,87,208)` — indistinguishable from a working link — and **no `href`
attribute exists at all**. Every "is the link present?" assertion passes.

Fix, and the two decisions inside it:

```ts
if (!isOpenableUrl(url)) return false;                  // scheme guard, separate module
if (Platform.OS === "web") {
  const win = window.open(url, "_blank", "noopener,noreferrer");
  if (!win) await Linking.openURL(url);                 // popup-blocked fallback
} else {
  await Linking.openURL(url);
}
```

- **New tab on web.** A plain `Linking.openURL` on web is `window.location.assign`,
  which navigates the SPA away from the conversation — the user loses their chat to
  look at a dashboard page.
- **`noopener`** because the dashboard is a different origin.
- **Never throws** — a rejected `openURL` (no handler, user cancels) must not
  produce an unhandled rejection in the render path.

### Guard the scheme in a PURE module

The link target is model output rendered as markdown — an injection surface.
Whitelist `http`/`https`; refuse `javascript:`, `data:`, `file:`, custom schemes
(`the company-ama://` is a valid link *into* the app but a reply must never trigger
it), relative paths, and embedded whitespace/newlines.

Put the predicate in its own file with **no React Native import** — the RN app's
vitest config is `environment: "node"` and only collects `lib/**` modules that
avoid RN, so a rule living inside an RN-importing file cannot be unit-tested at all.

---

## 4. Assert the CLICK, not the link

The dead-link bug shipped behind green checks precisely because presence was
asserted and behaviour was not. The E2E must click:

```python
opened = []
ctx.on("page", lambda pg: opened.append(pg))
chat_url_before = page.url
await page.get_by_text("Open creative library", exact=True).first.click()
await page.wait_for_timeout(5000)
# a page opened, on the platform host, and the chat did NOT navigate away
```

Expect the opened tab to show the dashboard's **sign-in page** unless that browser
context holds a platform session — a fresh context does not. So:

- in the chat E2E, assert a page opened on the platform host and that the chat URL
  is unchanged (that is the property the fix provides);
- exercise the **deep link itself** separately, signed in, and assert the filtered
  rows — otherwise "it opened something" hides a link that lands on the wrong page.

Also assert the affordance: `textDecorationLine == "underline"` and a non-black
colour. If it renders as plain text the user has no reason to try.

---

## 4b. Verify the links the product EMITS, and the page the click LANDS ON (2026-09-22)

The suite in §1/§4 proved the routes *someone had listed* rendered. Re-running the
same request ("ensure all deeplinks resolve to the correct pages") exposed two holes
that every existing green check walked straight past.

### The emission hole: a route sweep is still a list you wrote

A reply cannot link anything `linksForToolResult` does not return, so the set that
actually matters is **what the deployed server emits right now**. The suite now calls
every read-shaped tool through `/api/mcp`, collects `links.primary` + `links.related`
from the `structuredContent`, and renders each URL in Firefox signed in:

```python
emitted = emitted_links(token, ids)          # tool -> URLs, read live
if not emitted:
    raise SystemExit("the live server emitted no links at all — refusing to "
                     "report a green run from an empty set")
```

That empty-set guard is not decoration: a tool that starts erroring emits nothing,
and without it the suite shrinks to zero assertions and still prints PASS.

**Assert the specific page PER TOOL.** "It renders" cannot distinguish the right page
from a generic one, so pin `links.primary.key` for every tool whose answer is about a
single object:

```python
expected_specific = {
    "get_line_item": "line_item_detail",
    "list_line_item_creatives": "line_item_detail",
    "get_creative": "creative_versions",
}.get(tool)
if expected_specific:
    check("links the page for the object it answered about",
          primary.get("key") == expected_specific, f"key={primary.get('key')}")
```

### A real wrong destination: `list_brands` → the brand LIST

`list_brands` is both "list the brands" **and** how the model resolves one named
brand (it is the only brand-reading tool), and it always emitted the list page.
`brandDetailUrl` existed, was verified by a data request carrying
`id=eq.<id>` — and had **NO CALLER**, so a brand's own page was unreachable from any
reply. The fix branches on the payload:

```ts
const rows = Array.isArray(obj.brands) ? obj.brands : null;
const only = rows && rows.length === 1 ? asRecord(rows[0]) : asRecord(obj.brand);
const brandId = typeof only?.id === "string" && only.id.trim() ? only.id : null;
return brandId
  ? { primary: specific("brand_detail", "Open this brand", brandDetailUrl(brandId)),
      related: [link("brands", "Open brands")] }
  : { primary: link("brands", "Open brands") };
```

⚠️ **The count is the discriminator, deliberately — the first version shortcut to the
array head and the test suite caught it.** `list_brands` orders by `created_at desc`,
so `brands[0]` is merely the NEWEST brand, and "which brands do we have?" got sent to
whichever one happened to be newest. One row → that row's page; anything else → the
list.

### The test's own org trap (a false product bug)

Ids were originally harvested with a raw REST query. This account is a platform
super-admin with memberships in many orgs, so `advertiser_creatives?limit=1` returned
a creative belonging to a **different org** than the tools scope to. `get_creative`
then returned a soft "not found" with no links block — which read as a product bug and
took a debugging round to trace to the harness. Harvest from the tools' own payloads:

```python
campaigns = mcp_call(token, "list_campaigns", {}).get("campaigns") or []
# also: walk campaigns until one actually HAS line items — the first campaign in an
# org can legitimately have none, which yields /dashboard/ads/None
```

### Cross-repo org coupling (latent, not a defect)

AMA picks its org with `.limit(1)` among memberships; the dashboard picks its own. If
they diverge, every link resolves to the **wrong organization's** data while rendering
perfectly. Measured: they agree today (all 11 campaign names AMA returned were visible
on the dashboard's campaigns page). Check it rather than assume it — nothing enforces
the coupling, and a silent mismatch would look like a data bug in the assistant.

### The click hole: `/auth` is a valid dashboard route

The client-side click check asserted the new tab was "a real dashboard route", and
`/auth` satisfied it — so a signed-in user with a broken link and a signed-out user
sent to sign-in were **indistinguishable**, all green. Two changes:

1. **Seed a dashboard session in the SAME browser context before clicking**, so the
   tab resolves to the real page (cookies ride along; close the seeding page so it is
   not counted as the link's new tab):

```python
dash_probe = await ctx.new_page()
await reach_dashboard(dash_probe, "https://app.example.com/auth")   # retried
...sign in with EMAIL/PW...
await dash_probe.close()
```

2. **Assert COHERENCE between the label shown and the path that opens.** The link
   element carries **no href** (RN `Pressable` → `<span>` + onClick), so the target
   cannot be read off the DOM — the label is the only comparable signal:

```python
LABEL_TO_PATH = [
    ("Open this line item", r"^/dashboard/ads/[0-9a-f-]{36}$"),
    ("Open this creative",  r"^/dashboard/creatives/[0-9a-f-]{36}/versions$"),
    ("Open this brand",     r"^/dashboard/brand-intel/brands/[0-9a-f-]{36}$"),
    ("Open creative library", r"^/dashboard/creatives/library$"),
    ("Open campaigns", r"^/dashboard/campaigns$"),
    ("Open reporting", r"^/dashboard/reporting$"),
    ("Open dashboard", r"^/dashboard$"),
    ("Open brands",    r"^/dashboard/brand-intel/brands$"),
]
```

An **unmapped label is a FAIL**, not a skip — a new destination added without updating
the map would otherwise be able to open the wrong page unnoticed. "Open campaigns"
landing on the creative library is exactly the regression this catches.

### Reachability is asserted ONCE; derived checks are skipped, not failed

A transient `net::ERR_NAME_NOT_RESOLVED` on `app.example.com` mid-run produced **four
bogus failures** ("not a real dashboard route", "matches the label"…) that read as a
product defect. Retry the navigation, assert reachability as its own check, and when it
fails print `SKIPPED (dashboard unreachable)` for the derived assertions rather than
manufacturing failures. Same class as the harness-vs-product rule: say which it was.

### One earlier note in this file was WRONG, and measuring fixed it

The creative library had been recorded as failing in browsers without Web Crypto
(`crypto.subtle`). Re-measured in Chromium by injecting
`Object.defineProperty(window,'crypto',{value:{getRandomValues:(a)=>a, subtle:undefined}})`
and rendering all six destinations: **all render fine with and without it.** There was
no such trap. A stale negative claim in a notes file is an exclusion that quietly
removes coverage — when a note asserts something is broken, re-measure it before
carrying it forward.

---

## 5. Live end-to-end check that the reply carries links

Ask several different question shapes through the real SSE stream and parse the
markdown links out of the finished reply — one happy path cannot distinguish this
from a single hard-coded link:

| question | tool | link(s) surfaced |
|---|---|---|
| "How many creatives do we have?" | `count_creatives` | Open creative library |
| "Show me our campaigns" | `list_campaigns` | Open campaigns |
| "Impressions for last month" | `get_performance_summary` | Open reporting · Open dashboard |
| "What is our budget?" | `get_budgets` | Open campaigns · Open reporting |
| "Show me the line items for <campaign name>" | `list_line_items` | Open campaigns · Open reporting (**no** `/dashboard/ads` link — see §0) |
| "Tell me about the line item <name>" | `get_line_item` | **Open this line item** → `/dashboard/ads/<id>` |

Also assert the NEGATIVE: no reply in the matrix contains a link to
`/dashboard/ads` without a trailing id. That single assertion is what would have
caught the shipped bug, and it is cheap:

```python
bad = [u for _, u in md_links if "/dashboard/ads" in u and "/dashboard/ads/" not in u]
print(">>> BROKEN LIST LINK PRESENT:", bad or "none")
```

A campaign answer cannot link its line items (that page is broken) and there is no
per-campaign page, so it links the **campaign list** — say that in the code comment
so the choice reads as deliberate rather than as a missing feature.

Prompt rule that makes this reliable: render `links.primary` at the END as a
markdown link using **its own label** as the text, add `related` on the same line
separated by ` · `, use the URL **exactly as returned**, and never invent a link
when a result has no `links` field. Strengthen it with why: every URL in the payload
has been verified to render, and a hand-built URL (especially `/dashboard/ads`) has
not. Keep the example out of backticks inside a template literal — a `[label](url)`
example containing backticks breaks the prompt string and fails the build with
`',' expected`.
