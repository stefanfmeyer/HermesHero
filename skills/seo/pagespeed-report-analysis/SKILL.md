---
name: pagespeed-report-analysis
title: PageSpeed / Lighthouse Report Analysis
version: 1.0
description: Analyze raw PageSpeed Insights or Lighthouse text reports, identify performance bottlenecks, and produce a prioritized fix list.
triggers:
  - User sends a Lighthouse / PageSpeed Insights text dump, screenshot, or JSON report
  - User asks "why is my PageSpeed score low?" or "analyze this performance report"
  - Any request to interpret PSI metrics, Core Web Vitals, or diagnostics
---

## 1. Parse the Report
Extract these key figures first — they drive the priority order:

| Metric | Field (CrUX) | Lab (Lighthouse) | Target |
|---|---|---|---|
| LCP | Largest Contentful Paint | Largest Contentful Paint | ≤ 2.5 s |
| INP | Interaction to Next Paint | (use TBT as proxy) | ≤ 200 ms |
| CLS | Cumulative Layout Shift | Cumulative Layout Shift | ≤ 0.1 |
| TBT | — | Total Blocking Time | ≤ 200 ms |
| FCP | First Contentful Paint | First Contentful Paint | ≤ 1.8 s |
| SI | — | Speed Index | ≤ 3.4 s |

- **Field data** (28-day CrUX) is what Google uses for ranking — prioritize this.
- **Lab data** is the single-run snapshot — use it to find root causes.

## 2. Identify the #1 Bottleneck
Look for the metric with the worst lab score or the one failing in the field.

Common patterns:
- **LCP > 4 s** → Usually render-blocking CSS/JS, unoptimized hero image, or a cookie banner being measured as the LCP element.
- **TBT > 1 s** → Heavy 3rd-party scripts (GTM, trackers, ads), large 1st-party bundles, no code splitting.
- **CLS > 0.1** → Images/ads/embeds without explicit `width`/`height`, late-loading fonts.
- **FCP/TTFB high** → Slow server response, no caching, render-blocking resources.

## 3. Deep-Dive Diagnostics
Read these Lighthouse sections carefully:

### Critical Path / Network Dependency Tree
- Find the **maximum critical path latency**.
- Look for long chains like: HTML → CSS → font CSS → font file.
- Fix: `preconnect` to font CDN, `preload` the critical font, use `font-display: swap`.

### Render-Blocking Resources
- List every `.css`, `.js` flagged as render-blocking.
- Fix: Inline critical CSS, defer non-critical JS, async third-party scripts.

### JavaScript Execution
- Look at **Minimize main-thread work** and **Reduce JS execution time**.
- Identify the top CPU consumers by origin:
  - 1st-party → code-split, lazy-load, remove dead code.
  - 3rd-party (GTM, FB Pixel, Mouseflow, Cookiebot, etc.) → load conditionally, defer, or remove duplicates.
- Check for **duplicate scripts** (e.g. two GTM containers, two FB pixels).

### Caching
- Lighthouse flags assets with short or missing `Cache-Control`.
- Fix: Cache static assets (`img`, `css`, `js`, `svg`, `webp`) for 30+ days.

### Unused JS / CSS
- Note the estimated savings.
- Fix: Tree-shake, split bundles by route, load polyfills only for old browsers.

### Forced Reflows
- Flagged under **Avoid forced reflows** or in the Performance panel.
- Fix: Batch DOM reads/writes, avoid reading geometric properties after DOM mutations.

### LCP Element
- Check **LCP breakdown** (subparts: TTFB, load delay, load time, render delay).
- If render delay is huge, the LCP element is likely being blocked by scripts/styles or is a late-injected cookie banner.

## 4. Structure the Output
Present findings in this order for maximum clarity:

1. **Summary Bar** — scores + Core Web Vitals pass/fail.
2. **Critical Issues** — the 2-5 things that directly tank the score.
3. **Quick-Win Table** — issue | impact | estimated savings | fix.
4. **3rd-Party Audit** — separate table for trackers, ads, widgets; mark duplicates.
5. **Accessibility / SEO / Best Practices** — brief note only if they’re relevant to performance (e.g. missing image dimensions → CLS).
6. **Prioritized Action List** — numbered, easiest/biggest impact first.

## 5. Pitfalls
- **Don’t confuse lab LCP with field LCP.** A user might field-pass but lab-fail (or vice versa). Always mention both.
- **Cookie banners as LCP elements.** If the LCP element is `<div id="CybotCookiebotDialog...">`, the real content is delayed by the consent modal. This is a common false signal — the fix is delaying the banner or optimizing its render path, not the banner itself.
- **TypeKit / Google Fonts on critical path.** Font services often chain multiple CSS requests. Preconnect alone isn’t enough — consider self-hosting critical fonts.
- **Two GTM containers.** Easy to miss in the script list, but doubles the JS overhead.
- **Affiliate/tracking domains (e.g., `vjd2trk.com`).** Often uncached and heavy; worth questioning if the revenue justifies the performance cost.

## 6. Verification (optional)
If you have live access to the site:
- `curl -I https://example.com` — check `cache-control`, `content-encoding`.
- DevTools → Network → click the LCP element in the Performance timeline to confirm what it is.
- DevTools → Coverage — find unused JS/CSS percentages.
