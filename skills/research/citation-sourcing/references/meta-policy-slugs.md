# Meta Ad Policy Citation Map (Sep 2026, HEAD-only run)

Session-verified example of a fast bulk run: 19 Meta rows from `/tmp/citation_groups/B_meta_tiktok.json` (Meta lines 15-26, 86-88, 191-194; TikTok rows in the input were out of scope). Mode was "verification-by-HEAD only" per the run spec, so rows were NOT content-verified — URLs were matched by search results + Wayback CDX slug discovery, then HEAD-checked. Output: `/tmp/citation_results/B1_meta.json`.

## Final URL assignments (all 200 to plain curl)

- L15 adult content: `https://transparency.meta.com/policies/ad-standards/objectionable-content/adult-nudity-and-sexual-activity/`
- L16 tobacco/vaping: `https://transparency.meta.com/policies/ad-standards/restricted-goods-services/tobacco-related-products/`
- L17 weapons/ammunition: `https://transparency.meta.com/policies/ad-standards/restricted-goods-services/weapons-ammunitions-explosives/`
- L18 THC cannabis/drugs: `https://transparency.meta.com/policies/ad-standards/restricted-goods-services/drugs-pharmaceuticals/`
- L19 CBD/hemp (LegitScript, US-only): `https://www.facebook.com/business/help/5356017181162381`
- L20 alcohol (21+ US): `https://www.facebook.com/business/help/1145883309641178/`
- L21 gambling/sports betting (written permission): `https://www.facebook.com/business/help/4740325989340856/`
- L22 housing Special Ad Category: `https://www.facebook.com/business/help/1198401317374558/`
- L23 employment SAC: `https://www.facebook.com/business/help/298000447747885/` (How to Choose a Special Ad Category)
- L24 financial products & services SAC: `https://www.facebook.com/business/help/1157846251802527/` (About Ads for Financial products and services)
- L25 social issues/elections/politics: `https://www.facebook.com/business/help/208949576550051/` (Get Authorized...) — also reused for L191 (same authorization process)
- L26 personal attributes: `https://transparency.meta.com/policies/ad-standards/objectionable-content/privacy-violations-personal-attributes/`
- L86 Advantage+ Shopping Campaigns: `https://www.facebook.com/business/help/3171236526530970/`
- L87 Advantage+ creative AI transformations: `https://www.facebook.com/business/help/308193048565708/`
- L88 Instagram Teen Accounts: `https://transparency.meta.com/policies/age-appropriate-content/`
- L191 political authorization (US): same as L25
- L192 political ad AI disclosure: `https://transparency.meta.com/policies/other-policies/meta-AI-disclosures/` (used instead of an about.fb.com URL in the row's notes, due to run's domain constraint)
- L193 SIEP policy (final-week blackout): `https://transparency.meta.com/policies/ad-standards/SIEP-advertising/SIEP/`
- L194 branded content / political content: `https://transparency.meta.com/features/approach-to-political-content/`

## Slug-discovery lesson (transparency.meta.com)

- Live pages are JS-rendered: curl gets ~280KB of shell HTML with zero usable hrefs; sitemap.xml returns HTML; the real sitemap (`sitemap/transparency_meta_com_sitemap.xml.gz` from robots.txt) 403s curl.
- Guessed slugs 404 — Meta's actual slugs are counterintuitive (`weapons-ammunitions-explosives`, `drugs-pharmaceuticals`, `tobacco-related-products`).
- Fix: Wayback CDX prefix query on the topic directory (command in SKILL.md pitfalls) enumerates all real slugs; clean them and HEAD-verify each on the live site. All three slugs above were confirmed 200 live.
- Note: the bare category index `/restricted-goods-services/` itself 404s; only leaf pages exist.

## Meta Help Center quirks

- Search results carry tracking params (`?locale=`, `?recommended_by=`, `?itcat=`, `?id=`); strip to canonical `/business/help/<id>/`.
- web_search's site: operator returns junk for facebook.com/business/help (generic /help/ root, unrelated payout articles) — better to query without site: and filter results by domain, or query distinctive article-title phrasing.
- One article can legitimately serve two rows (authorization article for both L25 and L191); that is acceptable — the rule is one URL per row, not one unique URL per row.

## Run-spec constraint lesson

- The input JSON's `notes` fields contained embedded source URLs (e.g. about.fb.com for L192). Run-spec domain constraints override URLs found in the input's own notes.