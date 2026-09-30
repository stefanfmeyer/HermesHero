// Parity verification harness for HTML → Next.js conversions.
// Adapted 2026-09-30 from the veracity-lgc-search run (20/20 pass).
// USAGE: parameterise the three consts below, then: node verify.cjs
// Serve the built export first:  cd out && python3 -m http.server 3487 (background)
const NEW_URL = "http://127.0.0.1:3487/";                 // built app
const ORIGINAL_URL = "file:///absolute/path/to/index.html"; // original
const EXPECTED_TABLE_ROWS = 52;                            // static table rows
const PROBE_QUERY = "aldicarb";                            // search probe (or null)

const { chromium } = require("playwright");

(async () => {
  const browser = await chromium.launch();
  const results = [];
  const check = (name, ok, detail = "") => {
    results.push({ name, ok });
    console.log(`${ok ? "PASS" : "FAIL"} ${name}${detail ? " — " + detail : ""}`);
  };

  // ---- New app ----
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  await page.goto(NEW_URL, { waitUntil: "networkidle" });

  const input = page.locator("input[type=search], .mym-search-input").first();
  check("search input present", (await input.count()) > 0);

  const tableRows = await page.locator("table tbody tr").count();
  check(`static table rows = ${EXPECTED_TABLE_ROWS}`, tableRows >= EXPECTED_TABLE_ROWS, String(tableRows));

  let newProbeRows = null;
  if (PROBE_QUERY) {
    await input.fill(PROBE_QUERY);
    await page.waitForTimeout(300);
    newProbeRows = await page.locator("table tbody tr").count();
    console.log(`  new app rows for "${PROBE_QUERY}":`, newProbeRows);
    await input.fill("");
    await page.waitForTimeout(250);
  }

  await page.screenshot({ path: "/tmp/converted-full.png", fullPage: true });

  // ---- Original ----
  const orig = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const origErrors = [];
  orig.on("pageerror", (e) => origErrors.push(String(e)));
  await orig.goto(ORIGINAL_URL, { waitUntil: "load" });
  await orig.waitForTimeout(800);

  const origTableRows = await orig.locator("table tbody tr").count();
  check("original table rows equal new", origTableRows === tableRows, `orig=${origTableRows} new=${tableRows}`);

  let origProbeRows = null;
  if (PROBE_QUERY) {
    const origInput = orig.locator("input[type=search], input").first();
    await origInput.fill(PROBE_QUERY);
    await orig.waitForTimeout(400);
    origProbeRows = await orig.locator("table tbody tr").count();
    console.log(`  original rows for "${PROBE_QUERY}":`, origProbeRows);
    check(
      `behaviour parity for "${PROBE_QUERY}"`,
      origProbeRows === newProbeRows,
      `orig=${origProbeRows} new=${newProbeRows}`,
    );
  }

  await orig.screenshot({ path: "/tmp/original-full.png", fullPage: true });

  // ---- Quality ----
  check("no js errors on converted app", errors.length === 0, errors.join(" | ").slice(0, 300));

  // ---- Mobile ----
  const mob = await browser.newPage({ viewport: { width: 390, height: 844 } });
  await mob.goto(NEW_URL, { waitUntil: "networkidle" });
  const overflow = await mob.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 2,
  );
  check("no horizontal overflow @390px", !overflow);
  await mob.screenshot({ path: "/tmp/converted-mobile.png" });

  const pass = results.filter((r) => r.ok).length;
  console.log(`\n=== ${pass}/${results.length} checks passed ===`);
  await browser.close();
  process.exit(pass === results.length ? 0 : 1);
})();
