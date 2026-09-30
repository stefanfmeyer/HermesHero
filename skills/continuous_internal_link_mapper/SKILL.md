---
name: continuous_internal_link_mapper
description: Continuously monitor and improve internal linking across a website. Identifies new linking opportunities as content grows, prevents link decay, and maintains optimal link equity distribution.
---

# Continuous Internal Link Mapper

Continuously monitor and improve internal linking.

## Overview

This skill:
1. Monitors existing internal links
2. Identifies new linking opportunities as content grows
3. Prevents link decay (broken or redirected links)
4. Maintains optimal link equity distribution
5. Suggests new links for recent content
6. Outputs ongoing link improvement recommendations

## Inputs

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `site_url` | string | ✅ | Base URL for the site |
| `existing_pages` | array | ✅ | List of existing page URLs and metadata |
| `new_pages` | array | ❌ | Recently published pages needing links |
| `link_targets` | array | ❌ | Priority pages to link to |
| `max_suggestions` | integer | ❌ | Maximum suggestions per run (default: 20) |

## Outputs

| Output | Format | Description |
|--------|--------|-------------|
| Link Opportunities | JSON | New linking opportunities identified |
| Link Health Report | Markdown | Broken/redirected links found |
| Link Equity Map | JSON | Distribution of link equity across site |
| Implementation Queue | Markdown | Prioritised list of link changes |

## Monitoring Metrics

| Metric | Healthy | Warning | Critical |
|--------|----------|----------|----------|
| Links per page | 3-8 | 1-2 or 9-15 | 0 or 15+ |
| Orphan pages | 0-5% | 5-10% | 10%+ |
| Link equity distribution | Gini < 0.4 | Gini 0.4-0.6 | Gini > 0.6 |
| Broken links | 0 | 1-3 | 3+ |

## Process

### Step 1: Audit Existing Links

Check:
- Internal link count per page
- Broken links (404s)
- Redirected links (301/302 chains)
- Orphan pages (no internal links pointing to them)
- Link equity distribution

### Step 2: Identify New Opportunities

For each new page:
1. Analyse keyword themes
2. Match to existing related pages
3. Score linking opportunities
4. Rank by relevance and page authority

### Step 3: Prioritise Link Targets

Priority pages to link to:
- High-value pages needing more authority
- Pages with low internal link counts
- New service/landing pages
- Key conversion pages

### Step 4: Generate Recommendations

For each opportunity:
- Source page and anchor text
- Target page
- Linking rationale
- Estimated impact (low/medium/high)

### Step 5: Monitor Link Health

Track:
- Links pointing to removed pages
- Links affected by URL changes
- Natural link decay over time

## Example Output

```markdown
# Continuous Internal Link Report — April 2026

**Site:** choosemycar.com
**Pages Analysed:** 247
**New Opportunities Found:** 18
**Broken Links Fixed:** 4
**Orphan Pages:** 3 (flagged for review)

---

## New Linking Opportunities

### HIGH PRIORITY

**1. New guide needs links**
- **Source:** /guides/car-finance-for-first-time-buyers/ *(published Mar 2026)*
- **Suggested Link:** "car finance eligibility" → /eligibility/car-finance/
- **Rationale:** New guide mentions eligibility, existing page has high authority
- **Anchor Text:** "check your eligibility before applying"
- **Impact:** High (links new page to authority page)

**2. Service page cross-link**
- **Source:** /car-finance/ *(service page)*
- **Suggested Link:** "bad credit car finance" → /bad-credit-car-finance/
- **Rationale:** Service page should reference sub-service
- **Anchor Text:** "bad credit? See our specialist product"
- **Impact:** Medium (distributes link equity to sub-service)

---

## Broken Links Fixed

| Source Page | Target | Issue | Action |
|-------------|--------|-------|--------|
| /blog/old-post/ | /guides/old-guide/ | 404 | Removed |
| /car-finance/ | /contact-us/ | 301 chain | Updated to direct URL |
| /blog/2024/ | /guides/car-finance-tips/ | 404 | Redirect to updated URL |

---

## Orphan Pages (Needs Internal Links)

| Page | Link Count | Recommendation |
|------|-----------|----------------|
| /promotional-offers/ | 0 | Add links from /car-finance/ and /blog/ |
| /partner-with-us/ | 1 | Add links from relevant service pages |
| /accessibility-statement/ | 1 | Link from footer sitemap |

---

## Link Equity Distribution

| Page Type | Avg Internal Links | Target | Status |
|----------|-------------------|--------|--------|
| Homepage | 47 | 40+ | ✅ Good |
| Service Pages | 12 | 8-15 | ✅ Good |
| Blog Posts | 4 | 3-8 | ✅ Good |
| Landing Pages | 8 | 5-10 | ✅ Good |
| Utility Pages | 2 | 1-5 | ⚠️ Low |

**Site-wide Gini Coefficient:** 0.35 (Good distribution)

---

## Implementation Queue

| Priority | Action | Source | Target | Effort |
|----------|--------|--------|--------|--------|
| 1 | Add link | /guides/first-time-buyer/ | /eligibility/car-finance/ | 5 min |
| 2 | Add link | /car-finance/ | /bad-credit-car-finance/ | 5 min |
| 3 | Fix link | /blog/2024/ | /guides/car-finance-tips/ (new URL) | 5 min |
| 4 | Add links | /car-finance/ | /promotional-offers/ | 10 min |
| 5 | Add links | /blog/ | /partner-with-us/ | 10 min |

**Total Implementation Time:** ~35 minutes
**Recommended Frequency:** Weekly monitoring
```

## Constraints

- Do NOT add more than 5 links per page in one update
- Do NOT use exact-match anchor text (looks manipulative)
- Do NOT link to low-quality or thin content pages
- Do NOT create links that don't add user value
- Prefer contextual links over navigation links

## Error Handling

- If site_url is invalid or unreachable, report error
- If existing_pages list is empty, crawl to discover
- If new_pages not provided, skip new opportunity detection
- If broken link cannot be fixed automatically, flag for dev