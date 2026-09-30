---
name: design-system-port
description: Port a shared in-house design-token system (glass surfaces, light+dark modes, Google Sans / pill radii / ambient backdrop) onto another UI surface in the same or another repo — without breaking the selectors that E2E suites bind to, and without committing when the repo auto-deploys. Use when asked to "make X look like Y", "give Eduardo's UI my glass look", "same UI as the front-end I built", "add light and dark mode to <surface>", or to unify the visual language across two surfaces.
version: 1.0.0
---

# Porting a Design System Onto Another Surface

Class-level procedure for taking an existing, already-shipped design language and overlaying
it onto a **different** surface — a teammate's admin UI, a legacy static page, a second app in
the same repo. Proven case: overlaying the user's guest-app glass language (Google Sans, `#fafdff`,
28px pills, `#c4e7ff`/`#d3e3fd` accents, ambient backdrop, light+dark) onto the visitor backend
pages in `backend/static/` of a Vite/React + FastAPI repo.

Distinct from `site-ui-replication` (rebuilding a site with no source) — here the source **and**
the target are both on disk; the job is token transfer plus behaviour preservation.

## Order of operations

```
1. Confirm repo + surface (literally)   ← most expensive mistake when skipped
2. Inventory the target surface
3. Read the source token layer completely
4. Write a separate token layer; do not inline values
5. Restyle the surface, preserving every behaviour hook
6. Prove nothing dropped (selector sweep) + run every suite
7. Preview on stub data if the real backend can't boot
8. Report uncommitted  ← unless/until asked to ship, then §9b
```

## 1. Confirm the repo AND the surface before editing anything

This is where the whole task can go wrong. One repo can hold **several unrelated UIs**, and the
user's phrase for the target ("the UI Eduardo built") may map to none of the ones you have open.

- **State the target back in one line** — repo, plus the exact directory/file surface. If the
  user gives a URL or path, use it literally.
- **Enumerate candidate surfaces before touching anything.** In the proven case a single repo held
  (a) the user's React/Vite glass app under `src/` and (b) the teammate's backend UI under
  `backend/static/`. Styling the wrong one happened *twice, in both directions*, because the
  phrase "the UI I built" was resolved by assumption.
  ```bash
  ls -1 <repo>                       # what surfaces exist at all
  wc -l src/**/*.css <other>/static/*.css
  ```
- **"Same repo as X, not a separate repo" is a correction, not a hint.** It means you were editing
  a clone elsewhere — stop, kill that clone's servers, move into the named repo's working tree.
- **A clone under `~/tmp/` or a sibling dir is a red flag.** If the work belongs to a repo the user
  named, it happens inside that repo.
- **Verify scope at the end** so the claim is a receipt, not an assertion:
  ```bash
  git diff --stat                                    # must list only the intended subtree
  git diff --quiet <everything-else> && echo UNCHANGED
  ```

## 2. Inventory the target surface (and find what the tests bind to)

Before restyling, establish what must **not** change. Behaviour hooks outrank appearance:

- **Which selectors do the E2E/walk suites depend on?** Grep the walk scripts for the target pages:
  ```bash
  grep -n "getByLabel\|getByRole\|locator(\|querySelector" verify*.cjs <backend>/e2e.cjs
  ```
  Suites overwhelmingly bind to **ids, `aria-label`s, `role`s, `data-*` attributes and text
  strings** — not class names. In the proven case every walk bound to
  `[data-action=cap]`, `#visitor-name`, `#brief`, `role=button {name:...}`, so a class-level
  restyle was safe and the green walks proved it. Confirm this for your target before assuming.
- **Never touch:** ids, `data-*` values, `aria-label`/`role`/`aria-live`/`hidden` attributes,
  element text, form field names, or the markup structure a selector walks.
- **Free to change:** class names, CSS files, fonts, colours, radii, shadows, spacing, adding
  wrapper elements and new stylesheets.
- Note any server-side route that renders the page (`FileResponse(ROOT / "static/x.html")`) — you
  are changing what it serves, so its own tests count too.

## 3. Token layer first, in its own file

Put the design tokens in a **separate stylesheet** (`tokens.css`) and let the surface stylesheet
consume them. This makes the port reviewable, keeps the diff legible, and lets the same token file
be lifted to the next surface.

- **Copy the exact values from the source** — never re-derive an approximation. Read the source
  token file end to end and transcribe `:root`, the dark set, radii, fonts, ambient gradient and
  glass tints.
- **Copy the font binaries too** — if the source uses a self-hosted face (Google Sans woff2),
  copy the actual files into the target's static dir and add the `@font-face` rules. Verify with
  `md5sum` that they are byte-identical rather than re-encoding them.
- **Keep the surface's own additions additive** — brand colours the target legitimately needs
  (e.g. the CTV-demo navy/orange) belong in the token file as extra variables, documented as
  additions, not as edits to the ported values.

## 4. Dual light/dark entry points, and no flash

A ported surface must respond to BOTH the explicit choice and the OS preference. Encode all of it:

```css
:root { /* light tokens */ }
:root[data-theme="dark"], :root.dark { /* dark tokens */ }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { /* dark tokens */ } }
```

- **Two entry points on purpose:** `[data-theme]` (explicit) and `.dark` (class, keeps the surface
  interchangeable with the source app's own stylesheet). Repeat the dark block for the media query
  — CSS custom properties can't be aliased across a media query without duplication.
- **Set `color-scheme: light`/`dark`** so form controls and scrollbars follow.
- **Kill the flash:** load the theme script **synchronously in `<head>`** (a classic script, not
  `type="module"`), resolve and set the attribute before first paint.
- Resolution order: **explicit stored choice → live OS preference (listen to `matchMedia` change)
  → default**. Also sync across tabs via the `storage` event.
- **Update the `theme-color` meta** on toggle so mobile browser chrome matches.
- **Ship a visible toggle** in the chrome. Make the glyph reflect the **current** scheme (sun =
  light active), and keep `aria-label`/`aria-pressed`/`title` in sync — then assert the resolved
  scheme in the browser, not the click.
- Respect `prefers-reduced-transparency: reduce` (drop backdrop-filter, fall back to the solid
  card colour) and `prefers-reduced-motion`.

## 5. Glass-specific pitfalls (these all bit in the proven port)

- **The glass border is invisible on a light page.** `rgba(255,255,255,.55)` reads fine on the
  source's dark hero and vanishes on a `#fafdff` background, so panels merge into the page. For
  **structural** panels use the token border (`1px solid var(--border)`) and keep the glass only for
  the blur/shadow. Reserve the white-alpha glass border for elements that sit over media.
- **Nested glass needs a value step, not a bigger shadow.** Cards inside an already-tinted panel
  disappear when they reuse the same tint. Give the inner surface the *stronger* tint token
  (`--glass-tint-strong`) so the hierarchy is legible in both modes.
- **The ambient backdrop must be a real element in the markup.** `backdrop-filter` refracts only
  what's behind the panel; without the fixed ambient gradient layer the glass renders flat. Add
  `<div class="app-ambient" aria-hidden="true"><div class="app-ambient-field"></div></div>` and
  give content a stacking context (`position: relative; z-index: 1`).
- **Don't over-apply the treatment.** the user's standing preference: a visual effect is an *accent,
  not a theme* — apply it to chrome, cards and panels, keep dense data/text flat. His recorded
  reaction to glass everywhere was "too much use of the liquid glass".
- **Media overlays stay legible:** pills/badges over video need their own opaque-ish background,
  not the page's glass tokens.

## 6. Prove nothing dropped — the selector sweep

A restyle that silently drops a class the JS toggles is a bug the eye cannot see. Diff the
selectors, don't guess:

```python
# referenced by markup/JS vs defined in CSS, and new CSS vs the previous stylesheet
refs   = class="..." | className='...' | classList.toggle('...') | id="..." | getElementById('...')
defined= re.findall(r'\.([A-Za-z][\w-]*)', css) | re.findall(r'#([A-Za-z][\w-]*)', css)
old_css = subprocess.run(["git","show","HEAD:path/to/style.css"], ...).stdout   # the BEFORE file
print("referenced but unstyled:", refs - defined)
print("selectors lost vs HEAD :", old_selectors - new_selectors)
```

Expect a small, explainable residue both ways (JS-only hooks styled via element selectors; hex
colours and font filenames that moved into `tokens.css`). Anything else is a regression. Then run
**every** suite: build, unit tests, and all browser walks — the walks are what prove behaviour
survived the restyle.

## 7. Preview on stub data when the real backend can't boot

The target may need live services (API, database, generated config) that don't exist locally.
Don't declare it unviewable and don't fake the app — **serve the real static files through a small
stub that mirrors the app's own routes**:

```js
// /, /watch, /static/*  -> the real files verbatim
// the handful of /api/* the page reads -> plausible stub JSON
```

Tag the stubbed responses as stubs in the copy (`"Styling preview: no <service> here."`) so the
preview can never be mistaken for a working integration, and say so when handing over the URL.
Serve it on the tailnet (see `multi-service-project-runner` for the health-check discipline).

## 8. Verification: shoot viewport-sized, not full-page

- **`position: fixed` backdrops only cover the first viewport in a `fullPage` screenshot**, which
  shows up as a hard edge that isn't real. Capture **viewport-sized** shots (and
  `scrollIntoViewIfNeeded()` for lower sections) when verifying anything with a fixed backdrop.
- Verify both schemes for **every** page, and assert the resolved state programmatically
  (`data-theme`, computed background, loaded font family, toggle label, persistence across
  navigation) rather than trusting the screenshot alone.
- `deviceScaleFactor: 2` makes the evidence readable when reporting back.

## 9. Never commit — until the user explicitly says to ship

Several of this user's repos deploy to production on push to `main` via GitHub Actions. Standing
rule: **working-tree changes only, no commits, no pushes.**

- Do not "helpfully" commit at the end — an uncommitted tree IS the deliverable; a commit silently
  deploys it.
- Report the uncommitted list verbatim so the user can see nothing shipped:
  ```bash
  git status --porcelain --untracked-files=all
  ```
- Delete any scratch files you added outside the intended subtree before reporting.
- **"Don't commit" is a default, not a vow.** In the proven case the same user asked for a revert,
  then later said *"DO THIS! Then commit and push to remote, and on server"* — an explicit reversal
  covering all three (commit, push, deploy). When that happens the rule inverts immediately: do not
  cite the earlier instruction back at them, do not ask for confirmation again, just ship. A user
  who has told you twice not to commit is *more* likely to be annoyed by a third permission check
  than by shipping, once they have asked in plain words. See §9b.

## 9b. The ship sequence when told to commit, push and deploy

Order matters — each step below exists because skipping it produced a real failure.

1. **`git fetch` and inspect before committing.** The branch may have moved while you worked: in the
   proven case a teammate merged a PR mid-task and the local base was 2 commits behind. Committing
   on a stale base is how you either conflict at push time or silently discard their work.
   ```bash
   git fetch origin && git rev-list --left-right --count origin/main...HEAD   # left=behind
   git diff --stat <base>..origin/main                                       # what landed
   git diff --name-only <base>..origin/main | grep -E 'your|files'           # conflict check
   ```
2. **If upstream touched none of your files, fast-forward and re-verify on the NEW base.** Run
   `git pull --ff-only origin main`, then re-run the whole suite on top of their code *before*
   committing. Verifying on the stale base and committing on the new one ships an untested
   combination — the failure this step prevents.
3. **Commit a message that explains the defect and why the fix sits at that layer** — the *where*
   and *why*, not just the *what*. If you removed a gate, say which layer enforces it now.
4. **Push** (`git push origin main`).
5. **Deploy through the repo's own script**, never a hand-rolled equivalent, with the SHA stamped in:
   ```bash
   APP_VERSION=$(git rev-parse --short HEAD) bash ./deploy-at2.sh
   ```
6. **Verify from outside, four ways** — recipe in
   `github-actions-ssh-deploy` → `references/ship-a-fix-to-production.md`: health reports the SHA ·
   the **deployed bundle no longer contains the removed string** · the protected routes still
   refuse (401) · **no other container on the box moved**.
7. **Report container uptimes before/after**, so "nothing else moved" is a receipt rather than a
   claim. This box hosts other people's stacks; that reassurance is part of the deliverable.

## 10. If the user says you broke something — revert FIRST, then attribute

When a regression is reported while your uncommitted changes are present, the user **and you**
cannot tell your work from the pre-existing bug. Order:

1. **Revert immediately if asked** (`git checkout -- <paths>` + `rm` the untracked files you added).
   Confirm the clean state (`git status --porcelain --untracked-files=all` empty + HEAD hash).
   Reverting is not a concession of blame — it removes the confound and it is what was asked.
2. **Then attribute with evidence:** `git log --format='%h %an %ad %s' --date=short -- <file>` to
   name the author/date; `git diff --quiet <dir> && echo UNCHANGED` to prove a file was never in
   your diff; and grep the **deployed** bundle (`curl -s <prod> | grep -o 'assets/index-[A-Za-z0-9_-]*\.js'`
   then grep it) to show the string predates and bypasses your working copy.
3. **Reproduce both states side by side** from the same running app (e.g. no-cookie → gate page,
   valid-cookie → real flow) and screenshot both.
4. **Report (a) what I reverted, (b) whose change it is, (c) likely root cause, (d) recommendation —
   and only act on (d) with permission** if the culprit is a teammate's commit outside your assigned
   scope.

   **But do not let the caveat become the message.** In the proven case the report ended with a
   paragraph of hand-wringing — *"that's Eduardo's file and a behaviour change, and you've told me
   twice not to commit anything — so I've left it exactly as it is and haven't touched it"* — and the
   user replied by quoting **that paragraph verbatim** with the instruction *"Fix this"*. The
   ownership caveat was not reassurance; it was the obstacle. Two rules follow:

   - **The user already knows their own constraints.** Reciting "you told me not to commit" back at
     them reads as an excuse for inaction, not as diligence. State the constraint once, in a clause,
     and never as the reason you didn't act.
   - **When you have root-caused a bug that breaks the user's live production flow, the deliverable
     is the fix, not a menu.** Say what's broken, say what the fix is, say who wrote the offending
     commit in one line — then either fix it or ask a single yes/no. Offering *"should I do this, or
     hand it to Eduardo?"* invites a round trip the user does not want.
   - **Don't end with a list of judgement calls you invite them to reverse.** It reads as
     offloading decisions back onto the person who asked you to decide. Pick the defensible default,
     state it, and note exclusions in one line.
5. **If the user then says "fix this" (or approves your recommendation), it is now a scope change —
   do the minimum that restores the flow.** The fix usually belongs to a *different layer* than the
   one the bug appears in; see §11, and keep the suite green per §12. Once they've approved, the
   "never commit" default is also back in play unless they say otherwise — ask nothing further.

**Corollary:** a regression can arrive on `main` without you touching anything. A commit you pulled
can break the main flow days later (a stricter admission gate that locks the bare `/` route for
every visitor when its code is unset). Check recent commits on the branch before assuming a fresh
clone is a known-good baseline.

## 11. A gate on the render path is the wrong layer — enforce at the API

When a flow is "broken" by a gate, the instinct is to fix the gate's *copy or condition*. The real
defect is usually **where the gate lives**. In the proven case an admission check was added to the
client render path: it checked admission and, when false, returned a **full-page dead end** instead
of the app. Every guest without the admission cookie — including anyone hitting the bare `/` without
the QR link — saw a page with no way forward.

The fix, and the principle:

- **The server already enforced the same rule on the API** (`/api/*` and `/ws` return 403 until
  admitted). So the client gate added **zero** protection and its only observable effect was the
  dead-end page. **Grep the server for the real enforcement before touching the client** — if it
  exists, the render-path gate is redundant and can simply be deleted.
- **Delete the gate; let the app render; let the API refuse.** The guest flow almost always already
  has a designed failure path for a 403 — find it and point it at the right copy rather than
  inventing a new screen. In the proven case `GuestFlow` already had a `failureMessage(result)`
  branch that turned a 403 into an inline alert plus a *Retry connection* button — a good experience
  that was simply never reached, because the page-level gate short-circuited first.
- **Distinguish "not admitted" from "misconfigured".** A 403 is the caller's fault (scan the QR);
  a 401 or a `demo_configuration` code is the operator's (ask the booth team). Collapsing them into
  one message sends guests to staff for a problem only they can fix, and sends staff hunting for a
  config bug that isn't there.
- **Do not weaken the underlying rule** — *unless the rule is wrong for how the artifact is
  consumed.* Removing a redundant client gate must leave the real enforcement intact — assert the
  403 still happens (§12). But see §11c: when the gate protects a **printed deliverable**, the rule
  itself has to go, and removing it is a correction rather than a regression.

## 11c. When the artifact lives on paper, the gate itself is the bug

§11 said "delete the redundant client gate, let the API refuse." That was right for a *screen*. It is
wrong for **physical promotional material**, and this is the distinction to carry forward.

Proven 2026-09-22 on the same repo. The printed QR carried `/?code=<BOOTH_ACCESS_CODE>#/hat`, and the
cards page only minted the codes once an operator typed that secret. The user's correction:

> *"We shouldn't need to have the BOOTH ENTRY CODE. The qr codes should just be there to scan. They
> will be used on physical promotional material."*

Symptoms that looked like a QR-encoding bug and were not: **grey placeholder boxes** where the QRs
should be, and a **disabled "Print all pieces"** button — both consequences of a gated *generator*.
Before debugging a payload, check whether the artifact renders at all and what has to happen first.

The rule for anything that leaves the screen:

- **The artifact must be self-sufficient.** The QR is the app URL itself (`<origin>/#/hat`, plus
  `?sku=` variants) — no query-string secret.
- **Never gate generation of a printed artifact behind a typed value.** One forgotten step is blank
  paper, and a *rotatable* secret turns cards already on the table into dead links.
- **Keep old links resolving** — accept the legacy `?code=...`, 303 it onto the app, and say in the
  comment that it now authorizes nothing.
- **A public run and a locked ledger are separate gates.** Removing visitor admission must not unlock
  `/api/codes`, `/api/redeem`, `/api/stats`; those keep their staff token. Assert both in the same
  suite: "a plain scan reaches the app" **and** "staff routes stay locked."
- **Replacing an admission test, not deleting it.** Swap "unadmitted device is refused" for "a plain
  URL with no entry code offers the run, and the booth mints a ticket without a handshake."

**Removing a gate is cross-cutting — expect all seven layers.** Grep the variable name repo-wide and
do not stop at the server: route table → the module + its unit test → integration tests → browser/
print/booth walks (helpers that filled the field, assertions that the param was *present*) → the stub
backend mirroring the gate → CI `env:` blocks + `docker-compose.yml`'s `${VAR:?err}` + the deploy
precondition → `.env*.example`, both READMEs, local-stack script. A half-removed gate passes locally
and fails in CI on a missing env var.

Class-level detail, the `jsQR`/`pngjs` decode recipe, the print-typography fix (`text-balance` +
a `ch` measure — the ask is line breaking, *not* `letter-spacing`), and the full removal checklist:
`web-microsite-builder` → `references/physical-print-artifacts.md`.

## 11b. Where the refusal goes once the gate is gone — order, not just copy

Removing the dead-end gate (§11) is only half the fix. The refusal still has to **land in the right
place in the reading order**, and getting that wrong is what makes the user report the page as
*still broken* after a technically-correct fix.

In the proven case the refusal rendered as a small underlined link-style line **below** a row of
reward tiles — and those tiles were `disabled` because no inventory could be fetched for an
unadmitted device. The user's screenshot of that state is the whole complaint: the first interactive
thing on screen was a row of dead controls, with the explanation underneath them. It reads as a
broken product, not as "you're not checked in".

Rules that fixed it:

- **A refusal goes above the controls it disables, never below them.** If an error state disables
  interactive elements, it must precede them — a user reads top-down and acts before they finish
  scrolling. Put the message directly under the introduction/heading, before the first form field.
- **Give it its own labelled card, not inline link text.** A `.glass-surface` card with a small
  uppercase label (`Booth check-in`), the sentence, and the recovery action as a **primary-styled
  pill button** — not an underlined text link. It must look like a deliberate state, not a footnote.
- **Never leave a disabled control as the first thing on screen.** If the refusal precedes it, the
  dead row reads as a consequence; if it follows, the row reads as a bug.
- **Recovery action travels with the message it retries.** Moving the alert is also moving its
  `Retry connection` button — don't leave the button behind under the disabled row.
- **Kill the duplicate.** When you relocate a state block, delete the old one in the same edit.
  Leaving both is how the same message ends up rendered twice with different styling.
- **Distinguish the two refusal kinds in the copy** (403 → *scan the QR*; 401 / `demo_configuration`
  → *ask the booth team*) per §11, and keep the exact strings the walks assert.

## 12. Verification integrity: a green suite against a stale server is a false pass

**This bit hard, and it is the most dangerous failure mode in this whole class of work.** A first
run reported `RESULT: PASS` on the change — but the app process had died with `EADDRINUSE` because
a *leftover server from an earlier session* already held the port. The walk had connected to that
stale process and happily verified the **pre-fix** code. The suite was green and the evidence was
worthless.

Guard every run that starts a server:

- **Port preflight that exits non-zero** — refuse to run if the port is occupied, rather than
  letting `nohup` fail quietly into a log you never read:
  ```bash
  for port in 3399 8091; do
    ss -ltn | grep -q ":$port " && { echo "FATAL: $port in use"; exit 1; }
  done
  ```
- **Assert the process you started is the one answering.** Pass a unique `APP_VERSION`/`--version`
  and read it back from the health endpoint; the expected string appears nowhere else:
  ```bash
  curl -s .../api/health          # {"ok":true,"version":"admission-fix"} ← must match your tag
  ```
  A mismatched version is the tell that you are talking to someone else's process.
- **Never trust a background start.** Health-poll a bounded loop, then hard-fail with the log
  contents (`cat /tmp/x.log`) — `EADDRINUSE` and a stack trace belong in your face, not in a file.
- **Kill by captured PID, not by pattern.** `$!` from each background start; then `kill` those.
- **The `pkill -f` self-kill trap:** run **inline** in a shell, `pkill -f 'node server/index.js'`
  matches the shell's *own* command line and kills your session (`exit_code: -15`, no output). It is
  safe inside a script file (the pattern isn't in the script's argv) — so keep teardown in the
  script, and use PID capture when running anything inline.
- Wipe shared state between runs (`rm -rf /tmp/ci-ledger`) — a stale ledger pollutes assertions.

### The mirror image: a RED suite against a dead helper is a false failure

§12 above is the false *pass*. The same fragility produces the opposite error, and it is just as
expensive because it makes you hunt a regression that does not exist.

In the proven case the first post-pull run showed `verify.cjs` **failing** with a stack trace, then
`verify-ticket-print.cjs` and `verify-booth.cjs` both erroring with:

```
http://localhost:3399/healthz -> HTTP 502
A 502 here means CTV_DEMO_BACKEND_URL names nothing that is listening.
```

Nothing had changed in the code the walks exercise. The **stub backend had died** partway through
the run — `/tmp/*-app.log` showed `proxy GET /healthz: connect ECONNREFUSED 127.0.0.1:8091`, while
the stub's own log contained only its single startup line and nothing after. A re-run with the
helper's stdout captured live was fully green.

Triage rule — do these three before believing a red:

1. **Re-run with the helper's log captured *and printed on failure*.** A helper that dies silently
   (`nohup … > log 2>&1 &` with nothing ever `cat`-ing it) turns every downstream assertion into a
   false negative. Print the log on the failure path so the next reader sees *why* it stopped.
2. **Check whether the change under test can even reach the failing code.** This pull was `docs/` +
   one `scripts/` runner — neither is imported by the walks. A diff that cannot touch the failing
   assertion is strong evidence the failure is environmental, not a regression.
3. **Ask whether the helper is still alive** (`kill -0 $PID`) *before* and *after* the walk. Record
   it: "stub alive before walk: YES / alive after walk: YES" turns "it passed on retry" into a
   diagnosis.

Report it as what it is — a harness flake with the evidence, not as a green run and not as a
mystery. In the proven case the correct sentence was *"his diff touches nothing the walks use, and
the green re-run confirms it"* rather than either "all green" (hiding a real red) or "it failed"
(crying wolf about a teammate's clean PR).

## Reference

  the stub preview server, verification results, and the admission-gate regression that turned out
  to be a teammate's commit.
- `scripts/reproduce-ci-verify.sh` — re-runnable local reproduction of the `verify` job
  (build → stub backend → app → unit suites → all four browser walks), ending with the scope
  assertion and the uncommitted-file receipt. Run it before reporting any change to that repo;
  the walks are what prove a restyle didn't break behaviour.
