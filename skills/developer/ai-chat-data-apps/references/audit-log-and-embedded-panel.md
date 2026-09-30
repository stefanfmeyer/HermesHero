# Audit log + embeddable panel: worked detail (2026-09-22)

Condensed from the session that added (a) a super-admin-only audit log to the AMA
server and (b) a split-screen panel to the RN app. The SKILL.md carries the rules;
this file carries the measurements, the exact SQL/TS shapes, and the traps with their
error text so a future session recognises them instead of re-deriving them.

---

## 1. The full route audit (45 advertiser routes, Firefox, signed in)

Enumerated from the dashboard's own router — `src/routes.tsx` and
`src/pages/Dashboard.tsx` — not from a remembered list. The value of enumerating is
the number you did NOT predict.

```
ok: 36   CRASH: 3   REDIRECT: 6   EMPTY: 0
```

`EMPTY: 0` is the reassuring one: no route silently paints a shell.

**Crashes (all one cause — blocked realtime WebSocket → ErrorBoundary):**
- `/dashboard/ads` — `AdsManager` subscribes to `ads-changes` and
  `line-item-creatives-changes` on mount.
- `/dashboard/ads?campaign=<id>` — same mount subscribe; the filter changes nothing
  about it. (The FILTER itself does work: 23 rows → that campaign's 5, sending
  `campaign_id=in.(<id>)`. So if the CSP is ever fixed this becomes a good
  destination.)
- `/dashboard/ad-server-admin` — its index route is `admin/Dashboard`, which renders
  `LiveActivityMini` → `useRealtimeApiRequests`. Found only by rendering everything.

**Redirects (each lands somewhere other than its path):**
`/dashboard/creatives/approvals` → `/creatives/library`;
`/dashboard/analytics` and `/dashboard/reporting/delivery-transparency` →
`/reporting`; `/dashboard/settings` → `/profile`;
`/dashboard/organization/brands` → `/brand-intel/brands`;
`/dashboard/organization/teams` → `/settings/users`.

**Works but unemitted** (no tool maps to them yet): `/dashboard/ads/new` (accepts
`?campaign=<id>` via `searchParams.get('campaign')`), `/dashboard/agentic`,
`/dashboard/agentic/analytics`, `/dashboard/brand-research`,
`/dashboard/brand-intel/brand-agents`, `/dashboard/brand-intel/conversation-sandbox`,
`/dashboard/reporting/manager`, `/dashboard/organization/holding-companies`.

### Root cause, verbatim from the browser

```
[JavaScript Error] "Content-Security-Policy: The page's settings blocked the
loading of a resource (connect-src) at
wss://fkbtrqjunhrwjyaijkur.supabase.co/realtime/v1/websocket?apikey=…"
[ErrorBoundary] → "Dashboard Error / An unexpected error occurred."
```

The dashboard's meta CSP allows `https://*.supabase.co` but never `wss://`, and
`default-src 'self'` blocks the WebSocket. **No `X-Frame-Options` or CSP *header* is
served** on the live 200 — the directives are meta-only, which matters for the panel
below.

`NS_ERROR_CONTENT_BLOCKED` / "The operation is insecure" is Firefox 131's wording for
the same block; the current build shows the boundary's generic message. Same cause.

### The dashboard links to its own broken page

`CampaignManager.tsx`, per-campaign menu:

```tsx
<DropdownMenuItem onClick={() => navigate(`/dashboard/ads?campaign=${campaign.id}`)}>
  <Eye className="h-3 w-3 mr-2" /> View Line Items
</DropdownMenuItem>
```

So an advertiser in Firefox reaches the Dashboard Error from the dashboard's own UI.
Not an AMA defect. (`/dashboard/ads/new?campaign=…` in the same menu is fine.)

---

## 2. `assertLinkable` — the matching rule, and why two versions broke

```ts
export const FIREFOX_BROKEN_PATHS = ["/dashboard/ads", "/dashboard/ad-server-admin"] as const;

export function assertLinkable(url: string): string {
  let path = url;
  try { path = new URL(url).pathname; } catch { path = url.split("?")[0]; }
  const bare = path.replace(/\/+$/, "") || "/";
  for (const broken of FIREFOX_BROKEN_PATHS) {
    if (bare === broken) throw new Error(`Refusing to emit ${url}: ${broken} …`);
  }
  return url;
}
```

- `url.includes("/dashboard/ads")` → also refuses `/dashboard/ads/<id>` (works). ❌
- `bare.startsWith(broken)` → same bug in the other direction. ❌
- **pathname exact-match, query dropped** → refuses the LIST, allows the per-item
  page. ✅ The test suite caught both wrong versions; that is the argument for having
  a test that asserts the GOOD URLs still pass, not just that bad ones throw.

The E2E parses the route table out of `links.ts`

```python
routes = dict(re.findall(r'(\w+):\s*"([^"]+)"', block_of("DASHBOARD_ROUTES")))
broken = re.findall(r'"([^"]+)"', block_of("FIREFOX_BROKEN_PATHS"))
if not routes or not broken:
    raise SystemExit("parsed an empty route table — refusing to assert nothing")
```

That last guard matters: an empty parse would make every assertion vacuous while the
suite reported green.

---

## 3. Id-consumption proof — the substring trap

```python
# WRONG — the navigated URL is itself a request, so this passes on every page.
page.on("request", lambda r: seen.append(r.url))
used = any(the_id in u for u in seen)          # always True

# RIGHT — only data traffic counts.
page.on("request", lambda r: data.append(r.url)
        if "/rest/v1/" in r.url or "rpc/" in r.url else None)
used = any(the_id in u for u in data)
```

Measured results:

```
/dashboard/ads/<id>        /rest/v1/ads?select=*&id=eq.<id>             USES ID
/creatives/<id>/versions   /rest/v1/advertiser_creatives?...id=eq.<id>  USES ID
/brands/<id>               /rest/v1/brands?...id=eq.<id>                USES ID
/creatives/<id>/edit       no data request carried the id              DECOY
```

The decoy's second, code-level proof — a param-name mismatch:

```tsx
// routes.tsx
<Route path="creatives/:creativeId/edit" element={<CreativeEditor />} />
// Editor.tsx
const { id: creativeId } = useParams();          // ← always undefined
const isNewCreative = !creativeId;               // silently opens "new creative"
```

A behaviour-only check cannot see this: the page renders fine either way.

---

## 4. Iframe embeddability probe (calibrated)

```python
await probe.set_content("""
  <iframe id=blocked src="https://www.google.com/"></iframe>      <!-- must refuse -->
  <iframe id=target  src="https://app.example.com/dashboard"></iframe>
""")
refusal = [m for m in console_msgs
           if "refused to display" in m.lower() or "denied by" in m.lower()]
assert any("google.com" in m for m in refusal)          # probe is calibrated
assert not any("app.example.com" in m for m in refusal) # target is allowed
```

Plus a **size** check on the real panel's frame (`getBoundingClientRect()`): embedded
documents lay out (719×852 measured); refused ones collapse.

**Do NOT use `iframe.contentWindow.location`.** Cross-origin reads ALWAYS throw
`SecurityError`, so refused and embedded are indistinguishable — and the check fails
the healthy case. It did.

Result: `frame-ancestors 'none'` in a **meta** CSP is ignored by browsers, and no
header is served, so the dashboard embeds fine despite the directive. Measured in
both Chromium and Firefox, with `example.com` as a must-load control.

Native: no iframe. `react-native-webview` is not a dependency, so return false and
offer "Open in browser".

---

## 5. Audit schema — the owner is load-bearing

```sql
create table if not exists audit_events (
  id bigserial primary key,
  occurred_at timestamptz not null default now(),
  actor_user_id uuid, actor_email text, actor_name text,
  org_id uuid, org_name text,
  surface text not null, event_type text not null,
  tool_name text, action text, outcome text not null,
  subject text,
  args jsonb, error_message text, duration_ms integer,
  model text, provider text, input_tokens integer, output_tokens integer,
  request_id text, tool_call_id text, ip text, user_agent text, metadata jsonb,
  search_tsv tsvector generated always as (to_tsvector('simple',
     coalesce(actor_email,'') || ' ' || coalesce(actor_name,'') || ' ' ||
     coalesce(org_name,'')    || ' ' || coalesce(tool_name,'')  || ' ' ||
     coalesce(subject,'')     || ' ' || coalesce(event_type,'') || ' ' ||
     coalesce(outcome,'')     || ' ' || coalesce(error_message,''))) stored
);
-- NOTE: `args` is deliberately NOT in the vector.

create or replace function audit_events_append_only() returns trigger
language plpgsql as $$
begin raise exception 'audit_events is append-only: % is not permitted', tg_op; end $$;

create trigger audit_events_no_update before update or delete on audit_events
  for each row execute function audit_events_append_only();
```

Roles (`02-roles.sql`), idempotent, applied by the bootstrap every deploy:

```sql
create role ama_audit_app    with login noinherit;   -- INSERT only
create role ama_audit_reader with login noinherit;   -- SELECT only
grant insert on table audit_events to ama_audit_app;
grant usage, select on sequence audit_events_id_seq to ama_audit_app;
grant select on table audit_events to ama_audit_reader;
revoke create on schema public from ama_audit_app, ama_audit_reader;
```

**The app must NOT create the table.** An owner bypasses grants, so an app-created
`audit_events` would make the INSERT-only claim unenforceable and silent. Production
creates it as the superuser; the app's `ensureSchema` only VERIFIES:

```ts
const ownsSchema = (process.env.AUDIT_DATABASE_OWNS_SCHEMA ?? "true") !== "false";
schemaReady = ownsSchema
  ? getPool().query("select to_regclass('public.audit_events') as t")
      .then(res => { if (!res.rows[0]?.t) throw new Error("audit_events does not exist. Apply deploy/audit-db/01-schema.sql …"); })
  : getPool().query(AUDIT_SCHEMA_SQL).then(() => undefined);
```

Deploy proves it (8 probes, fails the deploy on any violation):

```
[PASS] app CAN insert        [PASS] reader CAN select
[PASS] app CANNOT select     [PASS] reader CANNOT insert
[PASS] app CANNOT delete     [PASS] reader CANNOT delete
[PASS] app CANNOT update     [PASS] append-only trigger present
[PASS] app CANNOT truncate   [PASS] audit_events owned by ama_audit_owner
```

---

## 6. Redaction — three leaks, all found by tests

**Key matching, two tiers** (a flat substring list is wrong in both directions —
`auth` matches `author_name`; `key` matches `monkey`):

```ts
const UNAMBIGUOUS_SUBSTRINGS = ["password","passwd","secret","token","apikey",
                                "credential","private","bearer","signature","salt"];
const SENSITIVE_WORDS = ["auth","authorization","cookie","session","otp","pin"];

function words(key: string): string[] {           // apiKey / api_key / API-KEY → ["api","key"]
  return key.replace(/([a-z0-9])([A-Z])/g, "$1 $2")
            .split(/[^A-Za-z0-9]+/).filter(Boolean).map(w => w.toLowerCase());
}
export function isSensitiveKey(key: string): boolean {
  const compact = key.toLowerCase().replace(/[^a-z0-9]/g, "");
  if (UNAMBIGUOUS_SUBSTRINGS.some(p => compact.includes(p))) return true;
  return words(key).some(w => SENSITIVE_WORDS.includes(w));
}
```

**Free-text scrubbing** (key matching cannot see a secret inside a value — the exact
shape of a password echoed from a command line):

```ts
[/\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b/g, "[redacted-jwt]"],
[/\bsk[-_][A-Za-z0-9_-]{12,}\b/g, "[redacted-key]"],
[/\bBearer\s+[A-Za-z0-9._~+/-]{8,}=*/gi, "Bearer [redacted]"],
[/\b([A-Za-z0-9_]*(?:PASSWORD|PASSWD|SECRET|TOKEN|APIKEY|API_KEY|PW)[A-Za-z0-9_]*)\s*=\s*("[^"]*"|'[^']*'|\S+)/gi, "$1=[redacted]"],
```

**The real one — the read API logging its own filters.** Storing
`Object.fromEntries(url.searchParams)` meant that a search for the leaked password
WROTE IT INTO THE LOG as `q`. Structural fix:

```ts
export function safeFilterSummary(query: AuditQuery): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const key of ["from","to","userId","email","orgId","toolName",
                     "surface","outcome","action","limit","offset","order"] as const) {
    const v = query[key];
    if (v !== undefined && v !== null && v !== "") out[key] = v;
  }
  if (query.q?.trim()) out.q = `[search term withheld, ${query.q.trim().length} chars]`;
  return out;
}
```

Redaction runs INSIDE `recordAuditEvent` (the store boundary), so no caller — present
or future — can skip it. Idempotent, so early-redacting callers still work.

---

## 7. Super-admin gate — call the PLATFORM predicate as the caller

```ts
const supabase = accessToken?.trim() ? createTokenClient(accessToken.trim()) : await createClient();
const { data: userData } = await supabase.auth.getUser();
// ⚠️ caller's own client: a service-role client asks "is ANY super admin
//    configured", not "is THIS user one", which opens the gate to everyone.
const { data: isSuper, error } = await supabase.rpc("is_current_user_super_admin");
```

Discrimination measured directly (a gate that always returns true is
indistinguishable from no gate):

```
is_super_admin(random uuid)        -> false
is_super_admin(known non-admin)    -> false
is_super_admin(known super admin)  -> true
is_current_user_super_admin(anon)  -> false
```

**Middleware trap:** `/api/audit` had to be added to the middleware's Bearer
allowlist. Without it the middleware answered first with
`401 {"code":"unauthorized","message":"Sign in required."}` and the route never ran —
symptom: "even the super admin is refused". Two distinct 401s now exist on purpose;
the route's own **403** means "signed in, not an administrator".

---

## 8. Deploy traps, with their error text

**Missing `--env-file`:**
```
error while interpolating services.audit-db.environment.POSTGRES_PASSWORD:
required variable AUDIT_DB_OWNER_PASSWORD is missing a value
```
Compose interpolates from `.env` by default; this deployment keeps vars in
`.env.production` (rsync-excluded on purpose). Without the flag **no service starts**,
including the pre-existing web container.

**Init SQL mode 0600:**
```
/usr/local/bin/docker-entrypoint.sh: running /docker-entrypoint-initdb.d/01-schema.sql
psql: error: /docker-entrypoint-initdb.d/01-schema.sql: Permission denied
PostgreSQL Database directory appears to contain a database; Skipping initialization
```
The server then started **healthy**, the healthcheck passed, and the deploy failed
later on `ERROR: role "ama_audit_app" does not exist`. Fix: `chmod 644` the .sql
files (DDL, no secrets), and re-apply both idempotent files from the bootstrap script
so a one-shot initdb failure cannot leave a half-built DB.

**Password echoed into the Postgres log** (from a failing multi-role statement):
```
ERROR: role "ama_audit_app" does not exist
STATEMENT: alter role ama_audit_app with password 'zsDMv5…'; alter role ama_audit_reader with password 'XXmdae…';
```
Fix: one role per statement; values via `set_config`/`current_setting` so the
statement text carries no secret; scrub output before printing.

**psql variable interpolation:**
```
ERROR:  syntax error at or near ":"
LINE 2: ...ot exists (select 1 from pg_roles where rolname = :'role') t...
```
No `:var` interpolation for `-c`, and none inside dollar-quoted `DO $$ … $$`. Pipe
the statement in with `-f -`.

**Silent no-recording (the worst one):** the store read `AUDIT_DATABASE_URL` while
the deploy wrote `AUDIT_APP_DATABASE_URL`; `recordAuditEvent` returned early, every
request succeeded, and the log stayed empty. Caught only because the live E2E ran a
real chat turn and found no rows. Fixes: warn on stderr at the first write, have
`/api/health` report `audit.recording`, and make the deploy **fail** when it is false.

---

## 9. CSV export details

- `neutraliseFormula`: a value starting `=`, `+`, `-`, `@`, tab or CR is executed by
  Excel/Sheets — prefix with `'`. Values in this log come from model output and user
  input, so a campaign named `=HYPERLINK(...)` would become a live formula.
- RFC 4180 quoting for `,`, `"`, newline; CRLF line endings.
- Report the limit **actually applied**, not the one requested — the first version
  echoed `limit=999999` back while querying 1000, and a client paging on that number
  would silently skip records. For an audit log, silently skipping is the worst
  possible failure.
- ⚠️ **The BOM must be in the BYTES.** Passing the CSV as a JS string through
  `new Response()` drops `\uFEFF` and Excel reads CP1252. Build a `Uint8Array` with
  `EF BB BF` first.
- Blank query filters must be treated as ABSENT (`?email=` arrives as `""`, and
  `lower(actor_email) = lower('')` matches nothing — a filter the user left empty
  would return zero rows, the exact "nothing happened" answer this must never give).
