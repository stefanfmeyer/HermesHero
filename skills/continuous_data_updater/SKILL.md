---
name: continuous_data_updater
description: Monitor and update SEO content with fresh data. Tracks content decay, identifies outdated statistics or claims, and triggers updates to maintain content freshness and search rankings.
---

# Continuous Data Updater

Monitor and update SEO content with fresh data.

## Overview

This skill:
1. Monitors content performance (rankings, traffic)
2. Identifies content decay signals
3. Detects outdated statistics or claims
4. Triggers content refresh workflow
5. Updates content automatically when safe
6. Reports on content freshness score

## Inputs

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `pages` | array | ✅ | Pages to monitor |
| `data_sources` | array | ✅ | Sources to check for updates |
| `refresh_threshold` | integer | ❌ | Days before refresh needed (default: 90) |
| `performance_metrics` | JSON | ❌ | GSC data for ranking signals |
| `brand_id` | string | ❌ | Brand identifier |

## Outputs

| Output | Format | Description |
|--------|--------|-------------|
| Freshness Report | Markdown | Content freshness by page |
| Update Recommendations | JSON | Pages needing updates |
| Update Queue | JSON | Prioritised list for content team |
| Automated Updates | Markdown | Changes auto-applied |

## Freshness Signals

| Signal | Threshold | Action |
|--------|-----------|--------|
| Ranking drop | >5 positions | Review/update |
| Traffic decline | >20% month-over-month | Investigate |
| Outdated statistics | Fact older than threshold | Update |
| Broken links | Any found | Fix immediately |
| Algorithm update | Major core update | Audit affected pages |
| SERP feature loss | Dropped from featured snippet | Prioritise update |

## Data Sources to Monitor

- Google Search Console (rankings, impressions, clicks)
- Google Analytics (traffic, engagement)
- Third-party data (industry statistics, benchmarks)
- News feeds (industry updates)
- Competitor content (new publications)
- Product/service changes (internal updates)

## Process

### Step 1: Gather Performance Data

Collect from:
- Google Search Console (ranking positions, impressions)
- Google Analytics (traffic, bounce rate, time on page)
- DataForSEO (ranking monitoring)

### Step 2: Identify Decay Signals

Detect:
- Ranking drops (position decline >5)
- Traffic decline (visits down >20% MoM)
- Engagement drop (time on page declining)
- Outdated content (statistics >1 year old)
- Broken links (404s or redirect chains)
- Algorithm impact (core updates)

### Step 3: Check Data Sources

For each flagged page:
1. Identify outdated statistics/claims
2. Check data source dates
3. Find updated figures from authoritative sources
4. Flag for human review if sensitive

### Step 4: Generate Recommendations

Prioritise by:
- Traffic impact (high-traffic pages first)
- Ranking risk (pages dropping fast)
- Update ease (factual updates vs rewrite)
- Business impact (converting pages)

### Step 5: Apply Automated Updates

Safe automated updates:
- Broken link fixes
- Minor statistic updates (with source citation)
- Date updates (publish date, review date)
- Typo corrections
- Format improvements

Human review required:
- Major rewrites
- New sections or removed sections
- Claim changes
- Strategy pivots

## Example Output

```markdown
# Content Freshness Report — April 2026

**Pages Monitored:** 24
**Pages Needing Update:** 6
**Automated Updates Applied:** 3
**Human Review Required:** 3

---

## Priority Update Queue

### 🔴 HIGH PRIORITY

**1. Bad Credit Car Finance Guide**
- **URL:** /bad-credit-car-finance/
- **Issue:** Ranking dropped from #3 to #8
- **Cause:** Outdated statistic (2019 data still cited)
- **Action:** Update to 2025 statistics
- **Effort:** 30 minutes (fact update)
- **Status:** Ready for automated update

**2. Car Finance Eligibility**
- **URL:** /eligibility/car-finance/
- **Issue:** Dropped from featured snippet
- **Cause:** Competitor updated their content
- **Action:** Expand FAQ section, add new data point
- **Effort:** 2 hours (human review)
- **Status:** Needs human writer

---

### 🟡 MEDIUM PRIORITY

**3. Best Car Finance Deals 2025**
- **URL:** /best-car-finance-deals/
- **Issue:** Article contains "2025" in title, now outdated
- **Cause:** Seasonal content decay
- **Action:** Update to 2026 or archive
- **Effort:** 1 hour
- **Status:** Needs decision

---

## Automated Updates Applied

### ✅ Car Finance Calculator
- **URL:** /calculator/
- **Fix:** Updated interest rate from 7.9% to 6.5% (per current lender data)
- **Verification:** Confirmed with lender partner
- **Impact:** Low risk, high accuracy

### ✅ Contact Us Page
- **URL:** /contact/
- **Fix:** Updated phone number (changed March 2026)
- **Verification:** Confirmed with operations
- **Impact:** Medium impact (contact usability)

---

## Freshness Scores

| Page | Freshness Score | Last Updated | Status |
|------|-----------------|--------------|--------|
| Bad Credit Car Finance | 65/100 | Jan 2025 | ⚠️ Update needed |
| Car Finance Eligibility | 72/100 | Nov 2024 | ⚠️ Update needed |
| Best Car Finance Deals 2025 | 40/100 | Dec 2024 | 🔴 Critical |
| Car Finance Calculator | 95/100 | Mar 2026 | ✅ Current |
| Guarantor Car Finance | 88/100 | Feb 2026 | ✅ Good |

---

**Next Review:** 2026-04-15
**Overall Site Freshness:** 78/100 (Good)
```

## Constraints

- Do NOT automatically update claims that affect legal/compliance
- Do NOT apply updates without source verification
- Do NOT rewrite major sections without human approval
- Maximum 5 automated updates per day
- All automated updates must be logged

## Error Handling

- If performance data unavailable, skip that page
- If data source is down, use last known good data
- If update fails, flag for human review
- If ranking data is stale (>7 days), warn user