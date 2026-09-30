#!/usr/bin/env node
/**
 * Mobile drawer / responsive-overflow verifier for a collapsible-nav SPA.
 *
 * Adapt the CONFIG block and the labels/route lists, then run against the DEPLOYED
 * url (or a local preview):
 *
 *   BASE=https://host:3500 NODE_PATH=~/node_modules node mobile_drawer_verify.cjs
 *
 * Why this exists (three traps it encodes, all of which produced false results when
 * hand-rolled):
 *   1. It does NOT set playwright `isMobile: true`. With that flag the app under test
 *      reported a 660x1429 window for a 390x844 viewport, so every geometry assertion
 *      silently measured the wrong device and a drawer that needed to scroll looked
 *      like it did not.
 *   2. It asserts horizontal overflow by PAN (window.scrollX after scrollTo(99999,0)),
 *      not by documentElement.scrollWidth — that reports the untruncated width of wide
 *      content inside an overflow-x:auto scroller even when the page cannot move, so
 *      it fails correct code and mis-measures real bugs (805 reported vs 415 actual).
 *   3. It clicks nav links through the DOM, not via a locator, so an assertion never
 *      depends on whether the link happens to sit inside the scrolled viewport
 *      (Playwright otherwise retries 30s then dies "element is outside of the viewport").
 *
 * Exits non-zero if any check fails, so it is safe as the last step of a deploy script.
 */
const { chromium } = require('playwright');
const os = require('os');
const fs = require('fs');

// ----------------------------------------------------------------- CONFIG
const BASE = process.env.BASE || 'http://localhost:4173';
const OUT = process.env.OUT || os.tmpdir() + '/drawer-verify';
const DRAWER = '#selleragent-nav';              // the aside/drawer selector
const BURGER = 'button[aria-label="Open navigation menu"]';
const CLOSE_BTN = 'button[aria-label="Close navigation menu"]';
const SCRIM = 'div[aria-hidden="true"]';         // the backdrop element
const DRAWER_W = 240;                            // px; off-canvas when x + this <= 1
const LG_BREAKPOINT = 1024;                      // px; drawer collapses BELOW this
const CONTENT_MARKER = 'Sign out';               // chrome text; page body follows it
const NAV_LABELS = ['Properties', 'Products', 'Pricing rules', 'Negotiations',
  'Media buys', 'Reconciliation', 'Creatives', 'Buyers', 'Tasks', 'Judgment log',
  'Seller agents'];
const ROUTES = ['overview', 'properties', 'products', 'pricing-rules', 'negotiations',
  'media-buys', 'reconciliation', 'creatives', 'buyers', 'tasks', 'judgment-log',
  'seller-agents'];
const ROUTE_PREFIX = '/selleragent/';
const WIDE_TABLE_ROUTE = '/selleragent/properties';   // a route that REALLY has a table
// -----------------------------------------------------------------

const results = [];
const check = (label, ok, detail) => results.push({ label, ok: !!ok, detail: detail || '' });

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const errors = [];

  // ---- helpers bound to a page
  const drawerLeft = (p) => p.evaluate((sel) => Math.round(
    document.querySelector(sel).getBoundingClientRect().x), DRAWER);
  const offCanvas = (x) => x + DRAWER_W <= 1;
  const bodyOverflow = (p) => p.evaluate(() => getComputedStyle(document.body).overflow);
  // The scrim usually stays mounted and fades via opacity, so isVisible() is always
  // true. Inert means opacity 0 AND not clickable.
  const scrimState = (p) => p.evaluate((sel) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    const cs = getComputedStyle(el);
    return { opacity: cs.opacity, pe: cs.pointerEvents };
  }, SCRIM);
  const scrimInert = async (p) => {
    const s = await scrimState(p);
    return s && s.opacity === '0' && s.pe === 'none';
  };
  const scrimActive = async (p) => {
    const s = await scrimState(p);
    return s && s.opacity === '1' && s.pe !== 'none';
  };
  // GROUND TRUTH for horizontal overflow: can the user actually pan the page?
  const panX = (p) => p.evaluate(() => {
    window.scrollTo(99999, 0);
    const x = Math.round(window.scrollX);
    window.scrollTo(0, 0);
    return x;
  });
  const goto = async (p, path) => {
    await p.goto(BASE + path, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await p.waitForTimeout(2200);
  };
  const clickNav = (p, label) => p.evaluate((args) => {
    const a = [...document.querySelectorAll(args.sel + ' a')]
      .find((n) => n.textContent.trim().startsWith(args.l));
    if (!a) return false;
    a.click();
    return true;
  }, { sel: DRAWER, l: label });

  // ================================================== MOBILE 390x844
  // NOTE: no isMobile/hasTouch — see header trap 1.
  const mctx = await browser.newContext({ viewport: { width: 390, height: 844 }, ignoreHTTPSErrors: true });
  const page = await mctx.newPage();
  page.on('pageerror', (e) => errors.push(String(e)));

  await goto(page, ROUTE_PREFIX + 'overview');
  const burger = page.locator(BURGER);

  check('mobile: hamburger visible', await burger.isVisible(), '');
  let x = await drawerLeft(page);
  check('mobile: drawer starts off-canvas', offCanvas(x), 'x=' + x);
  let pan = await panX(page);
  check('mobile: no horizontal page pan when closed', pan === 0, 'panX=' + pan);
  check('mobile: scrim inert when closed', await scrimInert(page), JSON.stringify(await scrimState(page)));
  await page.screenshot({ path: OUT + '/01-closed.png' });

  await burger.click();
  await page.waitForTimeout(450);
  x = await drawerLeft(page);
  check('mobile: drawer slides in on tap', x === 0, 'x=' + x);
  check('mobile: scrim active when open', await scrimActive(page), JSON.stringify(await scrimState(page)));
  check('mobile: body scroll locked while open', (await bodyOverflow(page)) === 'hidden', '');
  await page.screenshot({ path: OUT + '/02-open.png' });

  // every nav link navigates, and the drawer gets out of the way
  let reachable = 0;
  for (const l of NAV_LABELS) {
    if (!offCanvas(await drawerLeft(page))) { await burger.click(); await page.waitForTimeout(320); }
    if (!(await clickNav(page, l))) continue;
    await page.waitForTimeout(420);
    const body = (await page.evaluate(() => document.body.innerText))
      .split(CONTENT_MARKER).pop().trim();
    if (body.toLowerCase().startsWith(l.toLowerCase())) reachable++;
  }
  check(`mobile: all ${NAV_LABELS.length} nav links navigate`, reachable === NAV_LABELS.length,
    reachable + '/' + NAV_LABELS.length);
  x = await drawerLeft(page);
  check('mobile: drawer auto-closes after navigating', offCanvas(x), 'x=' + x);
  check('mobile: scrim inert after navigating', await scrimInert(page), '');
  check('mobile: body scroll unlocked after closing', (await bodyOverflow(page)) !== 'hidden', '');

  // three close paths
  await burger.click(); await page.waitForTimeout(420);
  await page.mouse.click(360, 640);                       // right side = scrim, not drawer
  await page.waitForTimeout(420);
  x = await drawerLeft(page);
  check('mobile: scrim tap closes drawer', offCanvas(x), 'x=' + x);

  await burger.click(); await page.waitForTimeout(420);
  await page.keyboard.press('Escape');
  await page.waitForTimeout(420);
  x = await drawerLeft(page);
  check('mobile: Escape closes drawer', offCanvas(x), 'x=' + x);

  await burger.click(); await page.waitForTimeout(420);
  await page.locator(CLOSE_BTN).click();
  await page.waitForTimeout(420);
  x = await drawerLeft(page);
  check('mobile: close button closes drawer', offCanvas(x), 'x=' + x);

  // ---- wide table: contained in its own scroller, page still locked
  await goto(page, WIDE_TABLE_ROUTE);
  pan = await panX(page);
  check('mobile: wide table does not pan the page', pan === 0, 'panX=' + pan);
  await page.screenshot({ path: OUT + '/04-table.png' });
  const tw = await page.evaluate(() => {
    const d = [...document.querySelectorAll('div')].find((e) => e.querySelector(':scope > table'));
    if (!d) return { found: false };
    const needs = d.scrollWidth > d.clientWidth + 1;
    d.scrollLeft = 99999;
    return { found: true, needs, scrolled: Math.round(d.scrollLeft) };
  });
  check('mobile: a real table exists on the wide-table route', tw.found, '(pick another route if not)');
  check('mobile: that table overflows its wrapper (so it can scroll)', tw.needs, '');
  check('mobile: table scrolls inside its wrapper, not the page', tw.scrolled > 0,
    'wrapperScrollLeft=' + tw.scrolled);

  // ---- NO route may pan horizontally. Regression guard for the whole bug class:
  //      flex + auto-margin sizing, non-wrapping <pre>, fixed grids.
  const panning = [];
  for (const r of ROUTES) {
    await goto(page, ROUTE_PREFIX + r);
    const px = await panX(page);
    if (px > 0) panning.push(r + '(panX=' + px + ')');
  }
  check(`mobile: no route pans horizontally (${ROUTES.length} routes)`, panning.length === 0,
    panning.length ? panning.join(' ') : 'all locked');

  // ================================================== SHORT VIEWPORT 375x667
  const sctx = await browser.newContext({ viewport: { width: 375, height: 667 }, ignoreHTTPSErrors: true });
  const sp = await sctx.newPage();
  await goto(sp, ROUTE_PREFIX + 'overview');
  await sp.locator(BURGER).click();
  await sp.waitForTimeout(450);
  const si = await sp.evaluate((sel) => {
    const a = document.querySelector(sel);
    return { needs: a.scrollHeight > a.clientHeight + 1, sh: a.scrollHeight, ch: a.clientHeight };
  }, DRAWER);
  check('mobile 375x667: drawer scrolls when taller than viewport', si.needs,
    'scrollH=' + si.sh + ' clientH=' + si.ch);
  await sp.evaluate((sel) => { document.querySelector(sel).scrollTop = 99999; }, DRAWER);
  await sp.waitForTimeout(250);
  const lastOk = await sp.evaluate((sel) => {
    const links = [...document.querySelectorAll(sel + ' a')];
    const r = links[links.length - 1].getBoundingClientRect();
    return r.bottom <= window.innerHeight + 1 && r.bottom > 0;
  }, DRAWER);
  check('mobile 375x667: last nav link reachable by scrolling', lastOk, '');
  await sp.screenshot({ path: OUT + '/03-short-viewport-scrolled.png' });

  // ================================================== DESKTOP 1440x900
  const dctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, ignoreHTTPSErrors: true });
  const dp = await dctx.newPage();
  await goto(dp, ROUTE_PREFIX + 'overview');
  const db = await dp.locator(DRAWER).boundingBox();
  check('desktop: sidebar static and visible', !!db && Math.round(db.x) === 0 && db.width > 200,
    db ? 'x=' + Math.round(db.x) + ' w=' + Math.round(db.width) : 'none');
  check('desktop: hamburger hidden', !(await dp.locator(BURGER).isVisible()), '');
  check('desktop: close button hidden', !(await dp.locator(CLOSE_BTN).isVisible()), '');
  check('desktop: no horizontal pan', (await panX(dp)) === 0, '');
  await dp.screenshot({ path: OUT + '/10-desktop.png' });

  // ================================================== TABLET just below lg
  const tctx = await browser.newContext({
    viewport: { width: LG_BREAKPOINT - 1, height: 800 }, ignoreHTTPSErrors: true });
  const tp = await tctx.newPage();
  await goto(tp, ROUTE_PREFIX + 'overview');
  const tx = await drawerLeft(tp);
  check(`tablet ${LG_BREAKPOINT - 1}px: still collapsed (below lg)`, offCanvas(tx), 'x=' + tx);
  check(`tablet ${LG_BREAKPOINT - 1}px: hamburger available`, await tp.locator(BURGER).isVisible(), '');
  await tp.screenshot({ path: OUT + '/11-tablet-closed.png' });

  await browser.close();

  const pass = results.filter((r) => r.ok).length;
  console.log('\n===== MOBILE DRAWER VERIFY: ' + BASE + ' =====\n');
  for (const r of results) console.log((r.ok ? '  PASS  ' : '  FAIL  ') + r.label + (r.detail ? '   [' + r.detail + ']' : ''));
  console.log('\n' + pass + '/' + results.length + ' checks passed');
  console.log('JS errors: ' + errors.length + (errors.length ? ' :: ' + errors.slice(0, 3).join(' | ') : ''));
  console.log('Screenshots -> ' + OUT);
  if (pass !== results.length) process.exit(1);
})();
