---
name: html-to-nextjs-conversion
description: Convert standalone single-file HTML apps (inline CSS/JS/data, base64 assets) to Next.js App Router projects for Vercel — verbatim-fidelity port workflow, data/asset extraction, and parity verification against the original.
tags: [nextjs, react, conversion, vercel, migration, static-site]
---

# HTML App → Next.js Conversion (Vercel-bound)

Class of task: "convert X to a simple NextJS app with all functions, styles and
features intact, I'll host it on Vercel." the user's intent is a **faithful port,
not a redesign** — preserve quirks verbatim (empty cells, TBC dates, mixed date
formats, masked phone numbers), flag them, never silently "fix" them.

Proven end-to-end 2026-09-30 (veracity-lgc-search: 556KB single-file catalogue
with a 913-row analyte search → Next.js 15 static export, 20/20 parity checks).

## Workflow

### 1. Map the source before writing anything
- Count `<style>`/`<script>` blocks; confirm single-page vs multi-page.
- List every element ID the script touches (`getElementById`) — these are the
  interactive surfaces that must survive the port.
- Extract three artifacts to /tmp: the style block, the script block, and the
  body markup (substitute `src="data:image...;base64,..."` with a placeholder
  first so the body is readable).
- Dead code exists in real files (element refs with no markup). Port only what
  the CURRENT file renders; keep the original file in the repo as reference.

### 2. Extract data, never re-type it
- Inline JS data arrays (`const X = [{...}, ...]`): parse with a regex or
  balanced-bracket scan into typed TS modules (`export interface` +
  `export const X: T[]`). **Verify parsed count == object-literal count** in
  the source text — a silent partial parse is the classic failure.
- Static `<table>` rows: parse `<tr>/<td>` with regex into typed arrays the
  same way. Trim/normalize whitespace inside cells only.

### 3. Extract embedded assets
- Regex all `data:(image|font)/...;base64,` URIs, base64-decode into `public/`
  named from the element class (`logo-lgc` → `lgc-logo.png`).
- In the CSS, replace ONLY the `@font-face` data-URI `url(...)` with the static
  path — every other rule stays byte-identical. Byte-identical CSS is the
  fidelity guarantee; do not reformat, do not modernize.

### 4. Scaffold minimal Next.js
- Next 15 + React 19 + TS. For Vercel static import set
  `output: "export"` and `images: { unoptimized: true }` in next.config.ts.
- App logic goes verbatim into a small `"use client"` component (search/filter
  functions port line-for-line, same normalize/tiering/order semantics);
  the server page renders static markup + data tables with `.map()`.
- Balance: metadata/viewport exports replace `<title>`/`<meta>` tags.

### 5. Verify by PARITY, not vibes — the step that matters
Playwright harness that loads BOTH the built app (serve `out/` with
`python3 -m http.server`) AND the original `index.html` (file://), then asserts:
- structural: title, headings, input/button labels, logo count
- data: table row counts equal; first-row content equal
- behaviour: the same search query returns the SAME result count and rows in
  both; empty state matches; clearing hides results
- visual: full-page screenshots of both for vision side-by-side
- quality: no console/page errors; no horizontal overflow at 390px

Harness template: `templates/html-to-nextjs-verify.cjs` — parameterise URLs and
expected counts per project. Write it with write_file and run plain
`node verify.cjs` (inline heredoc payloads get blocked by the command parser).

### 6. Ship
- README stating what was ported and what was deliberately left verbatim.
- Commit + push; Vercel import auto-detects Next.js, no settings needed.

## Pitfalls
- **Partial data parse**: always assert parsed-count == source-count.
- **Porting from the OLD file**: repos often keep `indexOLD.html`; check which
  one is current before extracting.
- **"Helpfully" cleaning the data** (normalizing dates, filling blanks) breaks
  the fidelity contract the user asked for.
- **Trusting the visual check alone**: a pixel-similar page can still have
  wrong search behaviour — run the behavioural parity queries.
- **Serving `out/` in foreground with `&`**: rejected; use
  terminal(background=true) for the static server, then test.
- **Turbopack CSS parser is stricter than webpack** (hit 2026-09-30): CSS
  extracted from an HTML `<style>` block built fine on Next 15/webpack but
  failed the Next 16/Turbopack build with
  `Parsing CSS source code failed — Invalid empty selector` at a stray `>`
  line. Two debris types: a leftover `>` from slicing between `<style` and
  `</style>` (off-by-one), and a doubled `format("woff2") format("woff2")`
  left behind after string-replacing a base64 `url(...)`. **Rule: `head` the
  generated globals.css and inspect the first lines before building** —
  webpack ignores what Turbopack hard-fails on.
- **Vercel CVE version block** (hit with next 15.5.4 / CVE-2025-66478): the
  log shows `✓ Build Completed` then
  `Vulnerable version of Next.js detected, please update immediately` — the
  build SUCCEEDED, Vercel refused to ship it. Fix: upgrade to the patched
  backport on the SAME minor line, found via the npm dist-tag literally named
  `backport`:
  ```bash
  npm view next dist-tags --json   # "backport": "15.5.26"
  npm install next@15.5.26 --save-exact
  ```
  Do NOT major-jump to `latest` to clear the block on a fidelity port. One
  informational transitive audit item (e.g. postcss) may remain after the
  backport; it does not block deploys.
- **Read WHICH branch failed before debugging a Vercel log**: the failing
  build may be a Dependabot PR branch (e.g. `dependabot/npm_and_yarn/next-16.x`),
  not main — Dependabot opens major bumps off the same CVE signal. Verify a
  major bump in a throwaway worktree, never the working checkout:
  ```bash
  git worktree add /tmp/test -b test-major origin/main && cd /tmp/test
  npm install next@<major> --save-exact && npm run build
  git worktree remove --force /tmp/test && git branch -D test-major
  ```
  Note Next 16 defaults to Turbopack — that's how the CSS debris above first
  surfaced.

## Ship
- README stating what was ported and what was deliberately left verbatim.
- Commit + push; Vercel import auto-detects Next.js, no settings needed.
- After the first deploy, pull the production URL and re-run the parity
  harness against LIVE before declaring done (the user: "verify every health
  endpoint before reporting running"). If the deploy is blocked, see the CVE
  pitfall above.

## Reference implementation
`~/Developer/veracity-lgc-search` — analytes.ts/mixes.ts data modules,
MoleculeSearch.tsx ported search, page.tsx, next.config.ts with export mode.
Final state: next 15.5.26 (CVE backport), CSS debris fixed, 20/20 parity
checks pass on both 15.5.26/webpack and 16.3.7/Turbopack builds.