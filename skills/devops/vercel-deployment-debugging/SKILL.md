---
name: vercel-deployment-debugging
description: "Debug and fix failing Vercel production deployments for Next.js projects — framework misconfiguration, env-var build crashes, stale output directories, and the Vercel REST API workflow for diagnosing and repairing project settings. Use when a GitHub push deploys as ERROR, when Vercel build logs show framework-detection errors (@remix-run/dev etc.), Invalid URL at page-data collection, or routes-manifest.json not found, or when project settings/env vars need repair via API."
version: 1.0
---

# Vercel Deployment Debugging

A Vercel deploy that fails while the same commit builds clean locally is almost always a
**project-settings or env-var difference**, never an app-code bug. Work top-down through
the three failure classes below. All were confirmed on real failures (2026-09-11,
example-site.com — commit built clean locally, failed on remote for three stacked reasons).

## Step 0: Get the actual build log

Never guess from the deploy state. Pull the full build events:

```
GET /v2/deployments/{deploymentUid}/events?limit=200&build=1
```

Each event's `payload.text` is a log line. The final error line alone is often misleading
(e.g. it blames a missing dependency when the real cause is a framework misconfiguration).

List deployments / find the latest UID:
```
GET /v6/deployments?projectId={projectId}&limit=3
```

## Failure Class 1: Framework misconfiguration

**Signature:** `Error: Failed to resolve "<pkg>". To fix this error, add "<pkg>" to "dependencies" in your package.json file.`

Where `<pkg>` is a framework dev dependency you have never used (e.g. `@remix-run/dev`).
Nothing in your dependency tree references it — the error comes from Vercel running the
**wrong framework builder**. Remix's builder demands `@remix-run/dev` at build start,
before it ever looks at your code.

**Diagnose:** `GET /v9/projects/{id}` — check the `framework` field.
**Fix:** `PATCH /v9/projects/{id}` with `{"framework": "nextjs"}` (and normalize
`installCommand` / clear `buildCommand` if they were set by the wrong preset).

**Pitfall:** this failure mode produces no useful error locally — `vercel build` linked to
the same project reproduces it, but grepping the codebase for the named package wastes
time because the package is genuinely absent. Go straight to project settings.

## Failure Class 2: `TypeError: Invalid URL` at page-data collection

**Signature:** compile + TypeScript succeed, then during "Collecting page data":
```
Error: Failed to collect configuration for /_not-found
  [cause]: TypeError: Invalid URL   (code: ERR_INVALID_URL, input: '[REDACTED]')
```

This is a **module-evaluation** crash: some module builds a `new URL(...)` from an env var
at import time, and the value Vercel injects is empty or malformed. Common culprits:
- DB clients that parse connection strings at module load (`postgres(process.env.POSTGRES_URL)`)
- SDKs initialized with `${process.env.BASE_URL}/path` template literals (Polar, Stripe callbacks)
- Auth secret checks that throw at module scope (`AUTH_SECRET is not set` is the sibling error)

`input: '[REDACTED]'` means Vercel's log scrubber redacted a secret-looking value — the
failing value IS an env var.

**Diagnostic technique (proves which side is wrong):**
1. Pull the failing project's env + settings: `vercel@59 pull --environment=production --project <name>` (run from a scratch dir to avoid clobbering your project's `.vercel/` link).
2. Sensitive values arrive as `[SENSITIVE]` placeholders — substitute the real values from local `.env` for the ones you trust.
3. Move the repo's `.env` aside, `set -a; source .vercel/.env.production.local; set +a`, then `npx next build`.
4. **If the local build with pulled env passes**, the remote env vars differ from what you pulled — one of the remote values is bad (stale/placeholder). Fix env vars via API.

**Finding the failing module without remote source access:** the stack trace names the
built chunk (e.g. `.next/server/chunks/ssr/_0nloklw._.js:21:799`). The same chunk exists
in your passing local build — `sed -n '21p' | cut -c600-1400` around that column shows
exactly which library is parsing the URL. No guessing.

**Fix:** update/add env vars via API (see API section). For `sensitive`-type vars the API
shows `value: ""` even with `decrypt=true` — you cannot read them, only overwrite.
`ENV_CONFLICT` on POST means the key already exists → PATCH the existing env ID instead
(list envs to get IDs from `GET /v9/projects/{id}/env`).

## Failure Class 3: Stale output directory

**Signature:** the Next.js build completes successfully (full route table prints), then:
```
Error: The file "/vercel/path0/public/routes-manifest.json" couldn't be found.
```

A framework preset (typically Remix) also set `outputDirectory: public`. Next.js outputs
to `.next` — the setting must be **unset**, not repointed:
`PATCH /v9/projects/{id}` with `{"outputDirectory": null}`.

**Rule:** when fixing a wrong `framework`, also check and clear `outputDirectory`,
`buildCommand`, and `devCommand` in the same PATCH — framework presets set all of them,
and fixing only `framework` produces failure class 3 on the next deploy.

## Project topology pitfall: stale/duplicate projects

A repo can end up with two Vercel projects: the GitHub-connected one (what prod actually
deploys from) and a stale duplicate that the local `vercel` CLI happens to link to.

**Symptom:** `vercel pull` + local `vercel build` passes → you conclude settings are fine
→ remote keeps failing. The local link points at the wrong project.

**Check:** `cat .vercel/project.json` locally vs `GET /v9/projects?limit=20` — compare
project IDs. The GitHub-connected project is the one with `link` of type github and the
org/repo in `GET /v9/projects/{id}`. Always debug against the project ID the deploy
actually belongs to (`GET /v6/deployments?projectId={id}` on the failing UID's project).

## "Why is the deployment paused?" — DEPLOYMENT_DISABLED / 402 on the live domain

Site returns HTTP 402 with `x-vercel-error: DEPLOYMENT_DISABLED` and body "Payment required",
while the Vercel API still reports every deployment `READY` and the project `paused: null`.
This is NOT a paused deployment — it is a **billing hold on the team**, which the REST API
 barely reveals. It happens when the team's billing plan was recently changed
(`billing.planChangedAt` recent) but the new billing period hasn't synced/settled yet
(`billing.period.start` is in the near future; Stripe payment not yet settled).

**Diagnostics:**
1. `curl -I https://<domain>` — `x-vercel-error: DEPLOYMENT_DISABLED` + 402 confirms billing hold, not app bug.
2. `GET /v2/teams` (list) → find team by slug → check `billing.status` (`canceled`/stale),
   `billing.planChangedAt`, `billing.period.start/end`, `billing.paymentMethod`.
3. `GET /v13/deployments/{uid}` still says READY — deployments look healthy while serving
   is disabled. Do not waste time redeploying; it changes nothing.

**Fix:** none via API — the billing profile must be fixed in the Vercel dashboard
(Settings → Billing): confirm the payment method settled (note `billing.paymentMethod`
can read `None` on the API billing profile even when working). Holds typically clear on
their own once the billing period starts; verify by curling the domain every few minutes.
**Do not trigger redeploys** — the deploy is fine; serving is disabled account-wide.

(2026-09-12: example-site.com 402'd for ~1.5h; team plan had changed to Pro/Plus the
previous day 14:00 UTC, new billing period started 07:00 UTC same morning; status
flipped to `active` and serving recovered without any redeploy.)

## "User still sees the bug in prod, but it's fixed locally"

Before debugging app code, check whether production is even running the fix. Most common
root cause for this symptom: the fix exists as **uncommitted local changes** (or committed
but unpushed). First moves, in order:

1. `git status --short` + `git log origin/main..HEAD --oneline` — uncommitted or unpushed?
2. If unpushed: commit + push, then follow the deploy-verification section below.
3. Only then compare local vs prod behavior (and confirm you're testing the same route,
   same account state, and the live project, not a stale/duplicate project).

Related pitfall: mid-session local verification proves nothing about production. An
end-to-end local test passing + "done" report without a push/deploy check is how the
2026-09-12 a client project onboarding AI-fallback bug survived a full fix-and-test cycle.

## Verifying a deploy actually triggered and finished

Don't assume a `git push` produced a production build — confirm before reporting success
(the user's standing instruction: "check builds pass on Vercel and are deployed, fix errors,
commit and push, then check again"). Poll:

```
GET /v6/deployments?projectId={projectId}&target=production&limit=3
```

Match the deployment to your commit via `meta.githubCommitMessage`, then poll the UID with
`GET /v13/deployments/{uid}` until `readyState` is READY/ERROR (a Next.js build can finish
in ~45s; poll every ~15s). Finally curl the production URL for HTTP 200.

**Deleted/renamed project pitfall:** a project ID that returns `{"error":{"code":"not_found"}}`
from `GET /v9/projects/{id}` no longer exists — deploys and env vars go to a different
project. Verify which project is live via `GET /v9/projects/{id}` (returns `name`, e.g.
`example-site.com`) or `GET /v9/projects?limit=20` before adding env vars or waiting on a
build that will never start. (2026-09-12: old `a client project` project was deleted; the live
one was `example-site.com` — env added to the dead project silently did nothing.)

## Deploying when the CLI has no auth (happy path, not a failure)

Check BEFORE asking the user for credentials: `vercel` CLI installed? (`which vercel`), token present? (`~/.local/share/com.vercel.cli/auth.json` — can be logged out/empty), `VERCEL_TOKEN` in env or any project `.env`? If all absent:

1. **Check whether it's already deployed.** If the repo is on the personal account with GitHub integration, Vercel may have auto-deployed every push already — the prod URL is `https://<repo-name>.vercel.app/`. Curl it; if HTTP 200, nothing to deploy.
2. **Verify the deployment via the public GitHub deployments API** (no auth needed for public repos): `GET api.github.com/repos/<owner>/<repo>/deployments?per_page=3` — latest deployment SHA should match your push and its `/statuses` state should be `success`. Allow ~45s after push.
3. Only if neither works, offer the user two options: (a) one-time dashboard import (no credentials shared), or (b) paste a `VERCEL_TOKEN` into chat for CLI deploy — and if a token is ever shared that way, flag it for rotation after use (matches the user's secrets rule: prefer not to put tokens in chat at all).

Real case (2026-09-29, smart-connect-bt-audio): CLI logged out, no token anywhere, and the user's repo already had GitHub integration — push alone produced a live production URL and verified-green deployment without any Vercel credential.

## Redeploying via API after fixing settings

Settings/env changes do **not** auto-redeploy the last commit:
```
POST /v13/deployments
{"name": "<project name>", "project": "<projectId>", "target": "production",
 "gitSource": {"type": "github", "org": "<org>", "repo": "<repo>", "ref": "main", "sha": "<full sha>"}}
```
Poll `GET /v6/deployments?projectId={id}&limit=1` until state is `READY`/`ERROR`.
Then verify the live domain with curl (pages 200, removed routes 404, API unauth 401)
before reporting success.

**GitHub-connected projects auto-deploy**: once settings are correct, every push to
`main` deploys automatically — subsequent fixes deploy without manual API triggers. Only
use `POST /v13/deployments` when the last commit failed under broken settings and you
need to re-run that exact SHA.

## Env-var gotchas

- **Stale env values persist silently**: a `sensitive`-type var created months ago can hold a value that no longer parses (e.g. an old DB host or a placeholder). It's invisible on read — the only signal is a module-eval crash on the deployed build. When a connection-string env var predates a DB/provider migration, PATCH it to the current value even if it "exists".
- `BASE_URL`-style vars: prefer the production domain over the value in local `.env` (localhost values get copied to prod and break callbacks/return URLs at runtime, not at build).
- Env var changes only apply to **new** deployments — always trigger a redeploy after fixing env.
- `type: "encrypted"` vs `"sensitive"`: both hide values on read; `sensitive` shows `value: ""` even with `decrypt=true`. Either works for build-time vars; both are write-only via API.
- `NEXT_PUBLIC_*` vars are inlined at build time — changing them requires the redeploy to rebuild, which the API-triggered deployment does.
- Target mismatch: a var targeting only `["production"]` is invisible to preview deploys. Match targets to what the failing deploy used (`target: "production"` in the POST body).
- Build-vs-runtime distinction: a var present on the project but with a garbage value fails at runtime; a var absent entirely fails at build (module-eval throws). Both look similar in logs — the `input` redaction hints it's a value problem, a missing-var message (`X is not set`) is explicit.

## Diagnostic workflow summary

1. Fetch build log for the failing deployment (`/v2/deployments/{uid}/events?build=1`).
2. Match signature → failure class above; check project settings (`GET /v9/projects/{id}`).
3. Reproduce locally with pulled project settings + env (scratch dir, not your linked project).
4. Fix via PATCH (settings) / POST+PATCH (env vars).
5. Redeploy via `POST /v13/deployments` with gitSource.
6. Poll to READY, curl-verify the domain, report with evidence.

## Reference

- `references/a client project-a client project-pro-2026-09-11.md` — worked example: three stacked failures on example-site.com fixed via the REST API, with project IDs, env-var inventory, exact PATCH/POST bodies, verification results, plus post-repair session state (commit ledger, page-count dynamics, and the user's UI defaults for email forms, mobile header density, and hand-authored blog posts — applicable to any Next.js marketing site deploy).

## Related skills

- `lgc-quiz-ops` — Vercel OAuth token lifecycle quirks (same team the Vercel team slug); prefer a personal dashboard API token for write access.