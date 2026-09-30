---
name: site-ui-replication
description: Reverse-engineer and replicate a website's UI when the source code is unavailable — extract the shipped JS bundle for exact copy/data/theme, capture live behavior with scripted Playwright walkthroughs, then rebuild clean-room and verify side-by-side. Also covers productizing a replica afterward — individual routes, Tailwind conversion, auth gating. Use when asked to "replicate this site", "clone this page's look", "rebuild this demo", "make it functional with login", or audit a site with no repo access.
---

# Site UI Replication Without Source

Proven end-to-end (2026-09-09): replicated a Lovable-generated React SPA (seller agent demo with a 5-step onboarding wizard + 11-tab console) into a clean Vite+React repo, verified with zero JS errors, without the original source and without vision-model credits.

**Sibling skill — pick the right one.** This skill is for when the source is **unavailable** and you
must reverse-engineer it from a shipped bundle. When the source design system is **on disk** and the
job is to overlay it onto another surface in the same or a different repo ("give X the same look as
Y", "add light+dark to this page"), use `design-system-port` instead — it covers surface
disambiguation, token-layer extraction, dual light/dark entry points, glass pitfalls, the selector
sweep that proves nothing dropped, and the no-commit rule for auto-deploying repos.

## Core insight

A shipped SPA bundle IS the source. Even minified, it contains every route, component, string of copy, data constant, theme color, and inline style. Combine bundle extraction (exact content) with scripted live capture (exact behavior) and you can rebuild faithfully.

## Workflow

### Phase 1 — Recon (cheap first)

1. `curl -sL <url> -o /tmp/page.html` and read it: look for `<script type="module" src="/assets/index-*.js">`, framework meta tags (Lovable/Vite/Next), and whether `<div id="root">` is empty (SPA — content is all in the bundle).
2. Try `web_extract` on the URL — it fails on JS-only SPAs. Don't retry; go to Phase 2.
3. Check if the target doc/brief is accessible: Google Docs return **401 on ALL public routes** (`/preview`, `/mobilebasic`, `/export`) when not shared public. See "Auth-gated Google Docs" below.

### Phase 2 — Bundle extraction (exact copy, data, theme)

1. Download the JS + CSS bundles with curl.
2. **Route map**: regex `path:"/some-route",element:e.jsx(COMP,{})` to find which component renders the target route.
3. **Component source**: find `function COMP(`, extract a slice to the next top-level `function X(`. Minified but fully readable — all JSX structure, copy, inline styles.
4. **Theme palette**: search for `varName={navy:"#..."}` patterns. E.g. `{navy:"#0A1628",blue:"#1B6EF8",accent:"#FF6B35",...}`.
5. **Data constants**: minified vars like `Mr=[{product_id:...}]` hold the demo data. Write a Node script that finds `name=` then scans to the string-aware matching close bracket — don't eyeball slices.
6. **Scoped CSS**: styles often live in template literals (`MN=`.adg{...}``). Search for the literal and extract to a .css file.

### Phase 3 — Live behavior capture (scripted Playwright)

Setup: `npm i playwright && npx playwright install chromium` in a scratch dir.

Write a walkthrough script that:
- Clicks through the flow with `page.locator('button:visible', { hasText: label })` with fallbacks (last visible button)
- At each state dumps: `document.body.innerText` (exact copy) AND a **DOM outline walk** that records tag, class, own text, and picked inline styles (background, color, font-size/weight, border, padding, max-width, border-radius). This gives pixel-accurate specs with zero vision calls — critical when vision credits are exhausted.
- Full-page screenshots per state and per sidebar/tab
- Handles multi-tab consoles: enumerate sidebar buttons, click each, dump per-tab text

**Pitfalls:**
- In a `"type": "module"` project, a CommonJS Playwright script MUST be `.cjs`, not `.js`.
- Keep walkthrough clicks stateful — some flows need `waitForTimeout` after each click for React transitions.
- `page.evaluate` DOM walks: guard against elements whose `innerText` is undefined (SVG nodes) — filter to text nodes.

### Phase 4 — Clean-room rebuild

- Vite + React, mirror the original's route path (e.g. `/selleragent`) via react-router.
- Extracted data → `src/data/*.js` verbatim (values, not variable names). Theme → `src/theme.js`. Scoped CSS → `src/adg.css` with the template-literal `${}` interpolations resolved to literal hex values.
- Match typography exactly: bundle usually imports Google Fonts (`Outfit`, `Figtree`, `JetBrains Mono` in the proven case) — keep the same `@import`.
- All copy verbatim from `innerText` dumps — do not paraphrase.

### Phase 5 — Verification (test EVERY page before reporting)

1. `npm run build` must pass.
2. `npm run preview` + a verify script that walks every state/tab, screenshots each (`replica/` dir), and fails on any `pageerror`/console error.
3. Visually compare replica screenshots against the original captures. If vision analysis is unavailable (out of credits), compare the `innerText` dumps — copy and structure parity is the real fidelity test.
4. Commit only after verification passes.

## Productizing a replica (routes, Tailwind, auth)

A verified visual replica is often only phase one. When the user then asks to make it
functional — individual routes per page, Tailwind, real login — treat that as a v2 of the
same repo, NOT a new project. Key lessons from the seller-agent v2 request (2026-09-11):

- **Capture assets persist the first time; reuse them for v2.** Bundles, DOM dumps, states,
  screenshots, theme tokens under `research/demo-assets/` are the fidelity source for any
  later rework — do not recapture the live site unless the original changed.
- **Stack changes per explicit instruction win over skill defaults.** If the user says
  "React + Tailwind, DON'T use Next.js", obey verbatim and note it in the repo README/PLAN.
  Default stack (Vite+React+react-router) only needs the additions the user asked for.
- **Tabs → routes conversion:** a state-machine console (11 tabs + onboarding steps) maps to
  individual routes (e.g. `/selleragent/overview`, `/selleragent/properties`, ...) with a
  shared guarded layout shell. Keep the sidebar as the router's nav so visual parity holds.
- **Inline styles → Tailwind:** extract the theme palette into `tailwind.config`
  (e.g. navy `#0A1628`, blue `#1B6EF8`, accent `#FF6B35`) and set the Google Fonts
  (Outfit/Figtree/JetBrains Mono) via the font stack config. Convert per-component inline
  styles to utility classes; keep copy and data verbatim from the existing `src/data/`.
- **Auth is a user decision, not a default.** Ask which provider (Supabase / Firebase /
  Keycloak / custom) before building. For Keycloak: realm + Google brokered IdP +
  email/password users, frontend uses `keycloak-js` (public client, PKCE), issuer URL from
  env (`VITE_KEYCLOAK_URL`) so the frontend build is not blocked while the Keycloak server
  is still being provisioned. Guard console routes; `/login` with email/password + Google.
- **Backend/infra prerequisites may block only the deployment step, not the build.** Verify
  SSH access to the target host BEFORE promising provisioning work, and report the blocker
  (e.g. `Permission denied (publickey)`) instead of stalling the whole task — wire the
  frontend to a configurable issuer and continue.
- **Auth provider that isn't provisioned yet must not brick the UI.** If the issuer URL is
  unreachable, `keycloak-js` `init()` can hang forever and every guarded route renders
  "Loading…" with zero console errors. Add a hard timeout around init that falls back
  to a dev session (gated by `VITE_REQUIRE_AUTH`), so the console stays reviewable until
  the server is live. Verify with a real browser check — curl returning 200 + the SPA HTML
  proves nothing about runtime state.
- **Make that timeout an ENV VAR, not a constant — the timeout IS the page-load latency.**
  Because init gates first paint, the fallback delay is exactly the user-visible
  "Loading…" time, so a hardcoded 4000ms ships a console that takes ~5s to paint on every
  route (measured 5321ms). Bake it at build time (`VITE_KEYCLOAK_TIMEOUT_MS=600`), default
  it in code (`Number(import.meta.env.VITE_KEYCLOAK_TIMEOUT_MS || 4000)`), and commit the
  reason in a `.env.production` so `npm run build` reproduces it. Measured: **5321ms →
  852ms**. No `curl` or status-code check can see this; only a browser timing the first
  non-"Loading…" paint catches it:
  ```js
  const t0 = Date.now();
  for (let i = 0; i < 80; i++) {
    const t = await page.evaluate(() => document.body.innerText);
    if (!/Loading/.test(t) && t.length > 500) { console.log(Date.now() - t0); break; }
    await page.waitForTimeout(250);
  }
  ```
  Document the reverse too: delete the override (or raise it) once the issuer is real, or a
  slow-but-working IdP gets cut off early and auth silently falls open.
- **Verification after a tabs→routes conversion:** verify by visiting each route URL
  directly and asserting the page heading, plus a full wizard click-through. Vite does NOT
  fail the build on missing named imports used in JSX — they crash at first render
  (`Pill is not defined`, `fmtM is not defined`) leaving the page body empty. See
  `references/verify-routes-v2.md` for the route-based verifier and this bug class.

## Shipping a replica to a host (phase 3)

The replica's third life is hosting it somewhere a stakeholder can click. The proven
shape (seller-agent console to at-2, 2026-09-22) is: build locally, publish the
Vite `dist/` as a static nginx vhost on a spare port, keep the deploy and both
verification suites in the repo, and verify against the DEPLOYED url.

- **Find the host's existing vhost pattern and copy its idiom exactly** before writing
  a new one — same cert paths, same `ssl.conf` include, same port-block style
  (`listen <port> ssl http2` + `server_name <same-host>`). Check the ports already in
  use first (`ss -ltn`) and pick a free one; on a shared box use a NEW port rather than
  a new hostname, which needs no DNS and no certificate work.
- **An SPA needs the fallback or deep routes 404 on refresh:** `try_files $uri $uri/ /index.html;`
  Vite emits content-hashed asset filenames, so serve `/assets/` as immutable and
  `/index.html` as `no-cache`.
- **Fingerprint the neighbours before and after.** `md5sum` every other
  `sites-enabled` vhost, install yours additively, then re-hash and curl every other
  port. "I did not touch your other services" has to be shown, not asserted — see
  `references/static-spa-vhost-deploy.md`.
- **A content-hashed bundle filename is proof the new build is live.** Compare the
  asset name the server serves against the one you just built, and grep the served JS
  for the literal you changed. Do not trust `systemctl reload nginx` alone.
- **A mobile pass is a separate deliverable, not a footnote.** A replica built and
  verified only at desktop width will be broken on a phone; see
  `references/responsive-hardening.md` for the three real overflow bug classes found
  the first time a replica was opened at 390px, and `scripts/mobile_drawer_verify.cjs`
  for the 28-check suite to adapt.

## Auth-gated Google Docs (PRD/brief retrieval)

If the task brief is a Google Doc that 401s:
1. Check for a stored token: `~/.hermes/google_token.json` (keys: `token`, `refresh_token`, `token_uri`, `client_id`, `client_secret`).
2. Refresh: POST to `token_uri` with `{client_id, client_secret, refresh_token, grant_type: "refresh_token"}`; write the new `access_token` back to the file.
3. GET `https://docs.googleapis.com/v1/documents/<docId>` with `Authorization: Bearer <token>` — works if the token's scopes include `documents` or `drive`.
4. Parse the structured JSON: walk `body.content`, handle `paragraph` (concat `textRun.content`) and `table` (row cells) elements. Export as markdown for the research dir.

## When vision is unavailable

Vision-model credits can run out mid-task. The DOM-outline technique (Phase 3) replaces screenshots entirely for layout/copy fidelity: inline-style picks per element give you colors, fonts, spacing, and structure as data. Keep vision for final sanity checks only, not as a dependency.

## File layout convention for the project

```
<project>/research/          ← all captures (untracked, never push plan/requirement docs)
  demo-assets/               ← original bundles, extracted component, theme, capture scripts
  screenshots/               ← original walkthrough screenshots
  states/                    ← per-state innerText + DOM outline dumps
<project>/replica-repo/      ← the clean-room build
```

## References

- `references/capture-scripts.md` — ready-to-adapt Playwright walkthrough, DOM-outline dump, and bundle-data-extraction scripts from the proven session.
- `references/verify-routes-v2.md` — route-by-URL verifier for productized (individual-route) replicas; includes the missing-import runtime-crash bug class that survives production builds.
- `references/static-spa-vhost-deploy.md` — publishing a Vite/webpack `dist/` as its own
  nginx port-vhost: recon checklist, the vhost template, SPA `try_files` fallback, hashing
  the neighbours as "I touched nothing else" proof, and proving the new bundle is live via
  its content hash.
- `references/responsive-hardening.md` — the three real horizontal-overflow bug classes a
  desktop-only verification pass cannot see (`mx-auto` beating `align-items:stretch`,
  non-wrapping `<pre>`, fixed grids + `shrink-0`), the off-canvas drawer requirements, and
  the two false-result traps in mobile verification (`isMobile: true` misreporting the
  viewport; `documentElement.scrollWidth` as a bogus overflow signal).
- `scripts/mobile_drawer_verify.cjs` — 28-check drawer + responsive-overflow suite across
  390x844, 375x667, 1023px and a desktop guard. Adapt the CONFIG block and run it as the
  last step of the deploy script.