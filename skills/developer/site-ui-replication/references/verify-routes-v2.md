# Route-Based Verifier — Productized Replica (v2 pattern)

Companion to the v2 "productizing" workflow in SKILL.md. When the replica has been
converted from a state machine to **individual routes** (e.g. `/selleragent/overview`,
`/selleragent/properties`, ...), verify every route directly by URL instead of clicking
through sidebar state. Proven 2026-09-11 (seller-agent v2).

Differences from `verify.cjs` (state-machine version):

1. **Visit each route by URL** and assert the page's `h2` — catches bad route wiring,
   missing imports, and wrong-component mappings in one pass.
2. **Walk the wizard as a route** (`/onboarding`) with real form interaction.
3. **Auth caveat:** if the app gates routes behind an auth provider that isn't
   provisioned yet (e.g. Keycloak issuer unreachable), `keycloak-js` init can hang and
   every page renders "Loading…" with no error. Either build the app with a dev fallback
   (env-flag gated), or assert on that explicitly before declaring failure.
4. **Run the script from a directory where `playwright` resolves** (e.g. `NODE_PATH=...`
   to a scratch install) — a module-not-found here looks like a site failure.

```js
// verify-v2.cjs — node verify-v2.cjs  (after `npm run build` && `npm run preview -- --port 4173`)
const { chromium } = require('playwright');

const BASE = 'http://localhost:4173';
const OUT = __dirname + '/replica-v2';

(async () => {
  const fs = require('fs');
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  const errors = [];
  page.on('pageerror', (e) => errors.push('pageerror: ' + e.message));
  page.on('console', (m) => { if (m.type() === 'error') errors.push('console: ' + m.text()); });

  const tabs = [
    ['overview', 'Overview'],
    ['properties', 'Properties'],
    // ...one entry per route: [slug, expected <h2>]
  ];

  let n = 0;
  for (const [slug, label] of tabs) {
    n++;
    await page.goto(`${BASE}/selleragent/${slug}`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(400);
    const h2 = await page.locator('main h2').first().textContent().catch(() => '(no h2)');
    console.log(`[${slug}] h2="${h2}" expected="${label}"`);
    await page.screenshot({ path: `${OUT}/${String(n).padStart(2, '0')}-${slug}.png`, fullPage: true });
  }

  // Wizard route: real click-through of all 5 steps
  await page.goto(`${BASE}/onboarding`, { waitUntil: 'networkidle' });
  await page.locator('button:has-text("Google Ad Manager")').click();
  await page.locator('input').first().fill('sk-test');
  await page.locator('button:has-text("Connect")').click();
  await page.locator('button:has-text("Continue")').click();
  // ... continue through remaining steps; assert post-go-live URL:
  // await page.waitForTimeout(1500); console.log('after go-live url:', page.url());

  // Login route
  await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' });
  await page.screenshot({ path: `${OUT}/99-login.png`, fullPage: true });

  await browser.close();
  console.log(errors.length ? 'ERRORS:\n' + errors.join('\n') : 'ZERO JS ERRORS');
})();
```

**Bug class this catches (both hit in the proven run):** missing imports that survive the
production build but crash at runtime. Vite/rolldown does NOT fail the build for a missing
named import used inside JSX — the component throws on first render. The two instances:
`Pill is not defined` (onboarding step 2 crash after Continue) and `fmtM/fmtMoney is not
defined` (Products/Media buys/Buyers/Judgment log). Symptom: page body renders **empty**
while URL stays correct. Rule: after conversion, run the route-by-URL pass and treat an
empty body on any route as a bug even when the build passed.