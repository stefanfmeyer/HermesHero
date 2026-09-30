# TikTok Ad Policy Citation Map (Sep 2026, HEAD-only run)

Session-verified example: 20 TikTok rows from `/tmp/citation_groups/B_meta_tiktok.json` (lines 27-36, 73-81, 98). Mode was "verification-by-HEAD only" per the run spec. Output: `/tmp/citation_results/B2_tiktok.json`.

## The real URL pattern

TikTok ads policy pages live at:

    https://ads.tiktok.com/help/article/<slug>?lang=en

The obvious patterns are SPA shells that return HTTP 200 for ANY slug — do not use them as citations without shell detection (see SKILL.md pitfall):
- `www.tiktok.com/business/help/article/<anything>` — 200 + generic `<title>TikTok For Business</title>` for every slug, real or fake.
- `ads.tiktok.com/business/en/help/<anything>` — same catch-all (~1MB shell).

## Final URL assignments (all HEAD-200, content-checked)

- L27/28/29/30/35 (alcohol, tobacco/vaping, weapons, THC/drugs, adult content — all prohibited): `https://ads.tiktok.com/help/article/tiktok-ads-policy-prohibited-content?lang=en`
- L31 gambling/betting: `https://ads.tiktok.com/help/article/tiktok-ads-policy-gambling-and-games?lang=en`
- L32/75 financial services: `https://ads.tiktok.com/help/article/tiktok-ads-policy-financial-services?lang=en`
- L33/77 health supplements / wellness: `https://ads.tiktok.com/help/article/tiktok-ads-policy-health-and-wellness?lang=en`
- L34/74 dating services: `https://ads.tiktok.com/help/article/tiktok-ads-policy-dating-services?lang=en`
- L36/78 AI-generated / synthetic media: `https://ads.tiktok.com/help/article/tiktok-ads-policy-synthetic-media?lang=en`
- L73 alcohol (2026 restricted): `https://ads.tiktok.com/help/article/tiktok-ads-policy-alcohol?lang=en`
- L76 OTC medications / healthcare: `https://ads.tiktok.com/help/article/tiktok-ads-policy-healthcare-pharmaceuticals?lang=en`
- L79 livestream eligibility: `https://support.tiktok.com/en/using-tiktok/going-live-on-tiktok`
- L80 first-party data / Events API: `https://ads.tiktok.com/help/article/supported-standard-events?lang=en`
- L81 branded content: `https://www.tiktok.com/legal/page/global/bc-policy/en`
- L98 political ads: `https://ads.tiktok.com/help/article/tiktok-ads-policy-politics-government-and-elections?lang=en`

## Slug-discovery lesson

- web_search `site:tiktok.com/...` returns junk: SPA shells, localized blog variants (`/ms/`, `/nb-NO/`, `/id/`), and unrelated pages. Query without site: and filter results by domain + URL pattern, or probe known slug shapes directly.
- Useful search query that surfaced the real pattern: `TikTok policy "paid political advertising" prohibited governmental entities tiktok.com/legal`.
- Real slugs follow the shape `tiktok-ads-policy-<topic>`; singular topics map to `prohibited-content` rather than per-topic articles.
- `www.tiktok.com/legal/page/global/<slug>/en` is a separate legal-domain surface (branded content policy lives there) — but guessed legal slugs (e.g. `political-ads-policy`) return a small ~33KB 404-in-200 shell with a bare `<title>TikTok</title>`; grep the body for policy keywords to tell real from fake.

## Shell-detection recipe (ads.tiktok.com)

1. Fetch a deliberately fake slug (`nonexistent-slug-check-404`) and record its byte size + md5 (was ~1,518,937 bytes).
2. Fetch each candidate and compare: distinct size/md5 = real page (financial 1.81MB, healthcare 1.94MB, gambling 1.75MB, political 1.55MB all differed from the shell).
3. Sizes near the shell size need a keyword grep (e.g. `grep -oiE 'alcohol|gambling'`) and a `\b404\b` count to confirm.
4. HEAD-verify every distinct URL in a batched curl loop for the honest status report.