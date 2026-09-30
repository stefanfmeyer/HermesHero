# Worked Example: 12-Row Ad-Platform Compliance Matrix (Sep 2026)

Session-verified example of the citation-sourcing workflow. Input: `/tmp/citation_groups/C_other_platforms.json` (fields: `line`, `scope`, `jur`, `category`, `status`, `notes`, `state_variation`). Output: `/tmp/citation_results/C_other_platforms.json` — `{"line": N, "policy_url": "..."}` per row.

## Output rules enforced

- Exactly one URL per input line; no em dashes anywhere in output.
- Sanity-check before writing: compare output line-set with input line-set, assert equal and count == 12.

## Per-row source assignments (verified Sep 2026)

**OpenAI Ads (ChatGPT) rows — two pages covered all 9 rows:**

- `https://openai.com/policies/ad-policies/` (updated Aug 10 2026) — rows 46, 47, 48, 49, 84:
  - Allowed categories: early phase limited to consumer verticals (household/consumer goods, local services, travel/entertainment, digital products/education) — "Allowed ads" section.
  - Legal services: "Ads for legal advice, representation, or legal services offered to individuals or businesses are not permitted. This includes services related to immigration, personal injury, legal claims, or document preparation." General legal education/media allowed (LSAT prep courses cited as example).
  - Healthcare/financial: restricted, case-by-case manual review for approved advertisers, US-only, proof of licensure may be required.
  - Disallowed at launch: dating/sexual content, health claims, alcohol and drugs, healthcare, financial or legal services, gambling, political content. Credit repair/debt settlement/bullion explicitly disallowed under Financial services.
- `https://help.openai.com/en/articles/20001047-ads-in-chatgpt` — rows 50, 82, 83, 85:
  - Under-18: "We do not show ads to accounts identified as belonging to people under 18" (age info + age prediction model).
  - Launch: "Ad testing started in the United States on February 9, 2026"; Free and Go plans only; Plus/Pro/Business/Enterprise/Edu ad-free; ads below the response, clearly labeled sponsored, visually separated; not in ChatGPT Atlas browser.
  - Sensitive topics: no ads near personal health, mental health, or politics; no ads in Temporary Chats; dismiss/report/see-why/clear-data controls.
  - Privacy: advertisers get aggregated reporting (views/clicks) only; "Advertisers never receive your chats, chat history, memories, name, email, precise location, IP address, or sensitive information". Ads data retained up to 30 days after clearing.
  - Supporting page: `https://help.openai.com/en/articles/20001245-ads-manager-availability` (country-by-country self-service availability; used for eligibility/geo claims).

**X (Twitter) row 199:** `https://business.x.com/en/help/ads-policies/ads-content-policies/political-content` — X permits political advertising targeting specified countries with restrictions; political campaigning ads require pre-approval via certification; country-specific election-law compliance; permitted formats limited (Promoted Ads, X Amplify, X Takeover, X Live, DPA); returned 200 to curl.

**LinkedIn row 200:** `https://www.linkedin.com/legal/ads-policy` (last revised Nov 18 2025) — "Political ads are prohibited, including ads advocating for or against a particular candidate, party, ballot proposition, law, regulation, or otherwise intended to influence an election outcome"; also bans political fundraising ads and issue-exploiting ads; EU-specific: Regulation (EU) 2024/900. Returned 200 to curl.

**CTV/Streaming row 201:** `https://www.congress.gov/crs_external_products/R/PDF/R46516/R46516.2.pdf` — CRS report R46516, "Identifying TV Political and Issue Ad Sponsors in the Digital Age" (Dana A. Scherer, Sep 9 2020). Directly supports: internet-delivered video services (CTV/AVOD) "are generally not subject to communications laws and FCC regulations"; sponsorship-ID and political-file rules attach to FCC licensees, not streaming entities. Full text extracted successfully (~106k chars) despite the page 403ing plain curl. Mirror fallback if congress.gov is unreachable: `https://www.everycrsreport.com/reports/R46516.html` (200 to curl, same content).

## Verification transcript summary

- curl loop results: business.x.com political-content → 200; linkedin.com/legal/ads-policy → 200; everycrsreport R46516 → 200; openai.com/policies/ad-policies → 403; help.openai.com ads article → 403; ads.openai.com → 403; congress.gov CRS PDF → 403.
- All 403 pages were re-verified via web_extract and contained the cited policy text; reported in the final answer with the caveat "403 to plain curl, verified via extraction". No URLs were fabricated or downgraded.