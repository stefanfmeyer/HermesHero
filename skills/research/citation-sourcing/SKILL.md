---
name: citation-sourcing
description: Find and verify primary-source citation URLs for claims in policy/compliance tables — map each claim row to one authoritative URL, verify content and reachability, write structured results
trigger: find citations, primary source URLs, cite the source for, citation lookup, policy citations, verify sources, source verification, map claims to sources
---

# Citation Sourcing — Claims to Primary-Source URLs

Class of task: a table/matrix of policy or compliance claims needs one verified primary-source citation URL per row. Seen variants: ad-platform compliance matrices (OpenAI Ads, X, LinkedIn, CTV regulatory rows), regulatory fact tables, fact-check matrices. The input is usually a JSON of claim rows; the deliverable is a parallel JSON with a URL per row.

## Non-negotiable rules

1. **Never cite a URL you haven't read.** Keyword-matching a search snippet is not verification. Extract the page and confirm the row's actual claim appears in the text.
2. **Content verification is the real gate; HTTP status is only for the honest report.** A 200 does not prove relevance (boilerplate-only pages exist); a 403 does not mean dead (bot-blocked pages load fine via web_extract).
3. **Exactly one URL per input row, full coverage.** Compare output line-set against input line-set before writing; assert parity.
4. **Report weaknesses honestly.** If a URL 403s to plain curl but verified via extraction, say so. If a claim rests on a mirror instead of the official source, say so. Never fabricate or substitute a plausible-looking source.

## Workflow

1. **Search** — web_search per platform/topic for the official policy page (query: platform + "ad policy" / "advertising policy" / "terms"). Batch independent searches in one turn.
2. **Extract & verify** — web_extract each candidate page; check each row's specific claims against the extracted text. Long pages often cover several rows at once; read the saved cache file (`~/.hermes/cache/web/<host>-<hash>.md`) with read_file to pull section-by-section facts.
3. **Status loop** — batch all candidate URLs in one shell loop:
   `for u in ...; do code=$(curl -sIL -o /dev/null -w '%{http_code}' --max-time 30 "$u"); echo "$code $u"; done`
4. **Re-verify failures via web_extract** — any URL that failed the loop gets retried through web_extract before being dropped or downgraded.
5. **Write results** — assert line coverage parity, then write the output file.

## Verification modes

Some runs specify the verification depth up front (e.g. "fast, verification-by-HEAD only" for bulk batches). Honor the user's stated mode instead of silently upgrading to full content verification — but the mode only relaxes the *content check*, never the other rules: still respect domain constraints from the run spec, still assert line-coverage parity, still report which mode was used in the final summary. Note that run-spec constraints override URLs embedded in the input's own notes fields (e.g. a row's notes may cite about.fb.com when the run only allows transparency.meta.com / business help domains).

## Source-preference ladder

1. The platform's/issuer's own policy page.
2. Their help-center/docs article for facts the policy page omits (launch dates, plan eligibility, retention windows, country availability).
3. Official government/regulator documents over mirrors — but a reputable mirror (e.g. everycrsreport.com for CRS reports) is acceptable when the official URL is hard to reach; note it.
4. Secondary/press sources as last resort, flagged as weak citations.

## Pitfalls

- **403 to plain curl ≠ dead URL.** Corporate/legal pages (openai.com, help.openai.com, ads.openai.com, congress.gov PDFs) commonly 403 curl/Cloudflare but load fine via web_extract. Re-verify before discarding.
- **JS-rendered policy sites hide their slugs.** transparency.meta.com (and similar React-rendered policy portals) return empty HTML body links via curl, 403 their sitemap.xml, and 404 on guessed slugs. Don't brute-force guesses — pull the Wayback CDX index for the topic prefix instead:
  `curl "https://web.archive.org/cdx/search/cdx?url=transparency.meta.com/policies/ad-standards/restricted-goods-services/&matchType=prefix&output=json&limit=500&collapse=urlkey&fl=original"`
  This reveals the *current live* slugs (e.g. Meta's real slugs are `tobacco-related-products`, `weapons-ammunitions-explosives`, `drugs-pharmaceuticals` — not the obvious guesses). CDX-captured URLs may carry query-string junk (js bundles, `?fbclid=`) — filter to clean path-only URLs and HEAD-verify each on the live site before use.
- **Help-center numeric URLs drift in search results.** facebook.com/business/help and similar numeric-article IDs surface with tracking params (`?locale=`, `?recommended_by=`, `?itcat=`) in search results — strip params to the clean canonical `/business/help/<id>/` form before verifying.
- **Below-the-fold content.** Help-center pages hide Q&A sections below the extract's truncation point — read the saved cache file with a raised offset rather than concluding the fact isn't there.
- **Universal-200 SPA catch-alls defeat HEAD-only verification.** Some help centers (e.g. `www.tiktok.com/business/help/article/*`, `ads.tiktok.com/business/en/help/*`) return HTTP 200 with a generic title for ANY slug, real or fake — a 200 there proves nothing. Detect shells cheaply: fetch a deliberately fake slug and compare byte size/md5 (a shell page is byte-identical regardless of slug); pages near the shell size need a keyword grep (`grep -oiE '<topic keywords>'`) plus a `\b404\b` count. Distinct sizes (real articles embed per-topic content) = genuine page. See also the small-shell variant under TikTok below.
- **One page, many rows.** Extract once, cite many — don't re-extract per row.
- **Output hygiene.** Keep output machine-readable and free of typographic characters (e.g. em dashes) when the downstream parser is strict.

## Detailed example

See `references/policy-citation-lookups.md` for a full worked example (12-row ad-platform compliance matrix: OpenAI/X/LinkedIn/CTV) including file conventions, exact commands, and per-row source assignments. See `references/meta-policy-slugs.md` for a Meta-specific worked example (19-row HEAD-only bulk run, transparency.meta.com slug map, Meta Help Center article IDs). See `references/tiktok-policy-slugs.md` for a TikTok-specific worked example (20-row HEAD-only run, real `ads.tiktok.com/help/article/<slug>` pattern vs. universal-200 SPA shells, slug map).