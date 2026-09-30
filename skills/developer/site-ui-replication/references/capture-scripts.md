# Capture Scripts — Site UI Replication

Ready-to-adapt scripts from the proven session (2026-09-09, seller-agent demo replication). All are CommonJS (`.cjs`) — note the `require` syntax fails in `"type": "module"` projects if saved as `.js`.

## 1. Bundle data-constant extractor

Finds a minified var like `Mr=[{...}]` and extracts the full value with string-aware bracket matching.

```js
// extract-data.js — node extract-data.js
const fs = require('fs');
const js = fs.readFileSync('index-CCuBD7bY.js', 'utf8');
const targets = ['Mr', 'Nz', 'A0', 'ir', 'Ks'];  // var names found via regex recon
const approx = { Mr: 2981146, Nz: 2995754, A0: 2994054, ir: 2980162, Ks: 2980562 }; // offsets from recon
const out = {};
for (const name of targets) {
  const eq = js.indexOf('=', approx[name] + 1);
  let i = eq + 1;
  while (/\s/.test(js[i])) i++;
  const open = js[i];
  const close = open === '[' ? ']' : open === '{' ? '}' : null;
  if (!close) { out[name] = js.slice(i, i + 120); continue; }
  let depth = 0, j = i, str = null;
  while (j < js.length) {
    const c = js[j];
    if (str) { if (c === '\\') { j += 2; continue; } if (c === str) str = null; j++; continue; }
    if (c === '"' || c === "'" || c === '`') { str = c; j++; continue; }
    if (c === open) depth++;
    if (c === close) { depth--; if (depth === 0) { j++; break; } }
    j++;
  }
  out[name] = js.slice(i, j);
  console.log(name, 'len', out[name].length);
}
fs.writeFileSync('data-constants.json', JSON.stringify(out, null, 1));
```

Recon pass to find var names + offsets first:

```bash
node -e '
const js = require("fs").readFileSync("index-CCuBD7bY.js","utf8");
const re = /[,;{(]([A-Za-z0-9_$]{1,5})=\[(\{[A-Za-z0-9_$]+:)/g;
let m; while ((m = re.exec(js))) console.log(m[1] + "@" + m.index);
'
```

Theme palette: search for `={navy:"#` — the match gives the var name and full color object.

## 2. Walkthrough + DOM-outline dump (stateful click-through)

```js
// walkthrough.cjs — node walkthrough.cjs
const { chromium } = require('playwright');
const fs = require('fs');

(async () => {
  const outDir = __dirname + '/states';
  fs.mkdirSync(outDir, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  // Dumps innerText AND a style-annotated DOM outline (vision-model-free layout spec)
  const dump = (name) => page.evaluate((name) => {
    const outline = [];
    const walk = (el, depth) => {
      if (depth > 8 || outline.length > 400) return;
      const tag = el.tagName.toLowerCase();
      if (['script', 'style', 'svg', 'path'].includes(tag)) return;
      const cls = (typeof el.className === 'string') ? '.' + el.className.split(' ').slice(0, 3).join('.') : '';
      const styleBits = [];
      const st = el.getAttribute && el.getAttribute('style');
      if (st) for (const p of ['background','color','font-family','font-size','font-weight','border','border-radius','padding','max-width','display','gap','letter-spacing','text-transform']) {
        const m = st.match(new RegExp(p + ':\\s*[^;]+')); if (m) styleBits.push(m[0]);
      }
      const ownText = [...el.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join(' ').trim();
      if (ownText || styleBits.length) outline.push('  '.repeat(depth) + tag + cls + (styleBits.length ? ' [' + styleBits.join('; ') + ']' : '') + (ownText ? ' :: ' + ownText.slice(0, 140) : ''));
      for (const c of el.children) walk(c, depth + 1);
    };
    walk(document.body, 0);
    return { name, url: location.href, text: document.body.innerText, outline };
  }, name);

  const states = [];
  await page.goto('https://demo.example.com/selleragent/', { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(1200);
  states.push(await dump('01-landing'));

  const clickBtn = async (labels) => {
    for (const label of labels) {
      const btn = page.locator('button:visible', { hasText: label }).first();
      if (await btn.count()) { try { await btn.click({ timeout: 1500 }); return label; } catch {} }
    }
    const btns = page.locator('button:visible');
    const n = await btns.count();
    if (n) { await btns.nth(n - 1).click().catch(() => {}); return 'fallback'; }
    return null;
  };

  // Walk N steps of a wizard, dumping each state
  for (let i = 0; i < 14; i++) {
    const label = await clickBtn(['Connect', 'Continue', 'Next', 'Approve', 'Verify', 'Go live']);
    await page.waitForTimeout(1600);  // let React transitions settle
    const nm = 'state-' + i;
    states.push(await dump(nm));
    console.log('STATE', nm, '| clicked:', label, '| chars:', states[states.length-1].text.length);
  }

  // Walk all sidebar/console tabs
  const tabs = await page.evaluate(() =>
    [...document.querySelectorAll('button,[role=tab],a')].map(e => (e.textContent || '').trim()).filter(t => t && t.length < 30));
  for (const t of new Set(tabs)) {
    try {
      await page.locator('button,a,[role=tab]', { hasText: t }).first().click({ timeout: 1500 });
      await page.waitForTimeout(900);
      states.push(await dump('tab-' + t));
      await page.screenshot({ path: `${outDir}/tab-${t}.png`, fullPage: true });
      console.log('TAB:', t);
    } catch {}
  }

  fs.writeFileSync(outDir + '/states.json', JSON.stringify(states, null, 1));
  await browser.close();
  console.log('TOTAL STATES:', states.length);
})().catch(e => { console.error('FATAL', e); process.exit(1); });
```

## 3. Replica verifier (build → preview → walk every state/tab)

```js
// verify.cjs — node verify.cjs   (run inside the replica repo, after `npm run build` && `npm run preview -- --port 4173`)
const { chromium } = require('playwright');
const fs = require('fs');

(async () => {
  const outDir = __dirname + '/replica';
  fs.mkdirSync(outDir, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', e => errors.push(String(e)));

  await page.goto('http://localhost:4173/selleragent', { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(800);
  await page.screenshot({ path: outDir + '/01-onboarding.png', fullPage: true });

  const clickText = async (t) => { try { await page.locator('button:visible', { hasText: t }).first().click({ timeout: 2000 }); return true; } catch { return false; } };

  // Wizard steps — adapt selectors to the flow
  await page.locator('.card-x').first().click();
  await page.fill('input.inp', 'sk-demo-key');
  await clickText('Connect');
  await clickText('Continue');
  await page.fill('input.inp', 'Northline Web and AI');
  await clickText('Create agent');
  await clickText('Continue');
  await clickText('Go live');
  await page.waitForTimeout(1400);
  await page.screenshot({ path: outDir + '/07-console.png', fullPage: true });
  const ctxt = await page.evaluate(() => document.body.innerText);
  console.log('console reached:', ctxt.includes('Northline Media'));

  for (const t of ['Properties','Products','Pricing rules','Negotiations','Media buys','Reconciliation','Creatives','Buyers','Tasks','Judgment log','Seller agents']) {
    try {
      await page.locator('aside button', { hasText: t }).first().click({ timeout: 2000 });
      await page.waitForTimeout(400);
      await page.screenshot({ path: outDir + '/tab-' + t.toLowerCase().replace(/ /g,'-') + '.png', fullPage: true });
      console.log('tab ok:', t);
    } catch (e) { console.log('tab FAIL:', t, e.message.split('\n')[0]); }
  }

  console.log('JS errors:', errors.length ? errors.slice(0, 5) : 'none');
  await browser.close();
  if (errors.length) process.exit(1);
})().catch(e => { console.error('FATAL', e); process.exit(1); });
```

## 4. Google Doc retrieval via stored OAuth token

```python
# gdoc_fetch.py — refresh stored token and pull a Google Doc as structured JSON
import json, urllib.request, urllib.parse
tok = json.load(open('$HOME/.hermes/google_token.json'))
data = urllib.parse.urlencode({
    'client_id': tok['client_id'], 'client_secret': tok['client_secret'],
    'refresh_token': tok['refresh_token'], 'grant_type': 'refresh_token'
}).encode()
r = json.load(urllib.request.urlopen(urllib.request.Request(tok['token_uri'], data=data)))
at = r['access_token']
tok['token'] = at
json.dump(tok, open('$HOME/.hermes/google_token.json', 'w'), indent=2)

doc_id = "1cvJ_igS0D9BelnJCHoiy6B1Rcum7Zm_-f5dYnrmPq9c"  # replace
d = json.load(urllib.request.urlopen(urllib.request.Request(
    f"https://docs.googleapis.com/v1/documents/{doc_id}",
    headers={"Authorization": f"Bearer {at}"})))
json.dump(d, open('/tmp/doc.json', 'w'), indent=1)
print("title:", d.get('title'))
```

Requires the token's scopes to include `documents` or `drive`. Public sharing routes (`/preview`, `/mobilebasic`, `/export?format=txt`) all 401 when the doc isn't shared — don't retry them, go straight to the API.

Markdown export from the structured JSON: walk `body.content`; for `paragraph` concat `elements[].textRun.content`; for `table` iterate `tableRows[].tableCells[].content[].paragraph`.