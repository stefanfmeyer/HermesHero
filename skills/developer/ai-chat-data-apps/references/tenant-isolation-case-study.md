# Case study: AMA (the company) — tenant isolation and streaming UI

Concrete findings from building AMA (advertiser chat + MCP over the the company ad server, Sept 2026). Kept here as concrete detail behind SKILL.md rules.

## Environment

- Next.js 15 App Router, Supabase auth shared with main app (api.example.com, project ref fkbtrqjunhrwjyaijkur).
- Existing Sinatra API service (the company-api) with three audiences: advertiser `x-api-key`, publisher `x-api-key`, super-admin `x-admin-token`. Campaign write routes REQUIRE advertiser keys; admin token only valid on reporting routes.
- Platform's own advertiser-mcp: user-JWT + SECURITY DEFINER RPCs (`get_line_item_rollup_totals` filtered `WHERE c.user_id = auth.uid()`), per-request Supabase client with the caller's token. This is the model to copy.

## The super-admin RLS leak (the big one)

- User's account: `profiles.role = 'super_admin'` + 100+ org_users memberships (test orgs).
- RLS policies like "Super admins can view all campaigns" (`USING (is_current_user_super_admin())`) mean every RLS-only query returned all orgs' campaigns/brands/creatives — 100+ campaigns streamed into the chat UI mid-stream.
- User reaction: "THIS IS INCREDIBLY BAD! FIX THIS RIGHT NOW!" — cross-tenant leakage is severity-max.
- Fix that passed verification:
  1. Auth resolves primary ADVERTISER org via `org_users → orgs!inner(is_advertiser = true)` (not first membership — first was a random test org).
  2. Every query: `.eq("org_id", ctx.orgId)`.
  3. App-side re-filter of results against the session org.
  4. Reporting RPC rows post-filtered to session org's campaign ids.
  5. Writes pin `org_id` + `user_id` from session; RLS WITH CHECK + `set_campaign_org_id` trigger backstop.
- Programmatic verification with his real account: 10 campaigns returned, all one org, zero cross-org. The super-admin account is the harshest test case — use it.

## Mid-stream leak of raw tool results

- Raw tool result table (with UUID id columns) rendered `open` during streaming → user saw a wall of raw data before the LLM summary. User flagged it as a breach even though the data was his own org's.
- Fix: `<details>` collapsed by default with summary "List Campaigns · 10 rows"; raw rows only on explicit expand; compact table drops id/UUID columns, prefers name/brand/status/objective/budget/dates.
- DOM verification during streaming: `<details>` open state false; UUID regex count in body text = 0; visible `**` count = 0; raw `|` rows = 0.

## Other fixes worth remembering

- `crypto.randomUUID is not a function` over plain HTTP (tailnet/LAN, non-secure context): uuid() helper with getRandomValues → Math.random fallbacks.
- "Anthropic selected but OpenAI-key error": picker showed Anthropic by default while client sent no model; server fell back to hardcoded OpenRouter. Fix: client always sends `provider:model`; server default = first provider with a configured key; a `requireProviderKey` helper throws a per-provider clear error (the OpenAI SDK's native error names the wrong env var).
- Google OAuth bounced to the old app: Supabase redirect allowlist falls back to Site URL when `redirect_to` isn't allowlisted. Fix = add the new host URLs in Supabase dashboard (Authentication → URL Configuration). Email/password login unaffected.
- Linear project setup: add members via `projectUpdate memberIds` (there is no `projectMembershipCreate` mutation); issues carry Done checklists + repo links; duplicate blocker tickets get deleted and the existing ticket gets a linking comment.

## Verification snippet (programmatic, in-browser)

```js
// paste in browser console after a streamed answer
const all = document.body.innerText;
({
  uuidCount: (all.match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi) || []).length,
  visibleAsterisks: (all.match(/\*\*/g) || []).length,
  rawPipeRows: (all.match(/^\s*\|.*\|.*\|/gm) || []).length,
  detailsOpen: Array.from(document.querySelectorAll('details')).filter(d => d.open).length,
})
// Expect: all zeros for leaks/formatting artifacts during AND after streaming.
```