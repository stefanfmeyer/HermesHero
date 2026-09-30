# SEO Analysis Full - Skill

## Trigger
- URL posted in #sales-internal with 🔍 reaction
- Or manual request: "full SEO analysis for [domain]"

## Workflow

### 1. Website Fetch
- Fetch homepage + key pages (services, about, contact, blog)
- Detect: platform, blog location (/news/, /blog/, /blog/), content structure

### 2. DataForSEO Enrichment (Budget: <£0.25/call)
```
Endpoints to try:
- /v3/domain_analytics/whois/overview/live → traffic + backlinks
- /v3/keywords_data/Google/search_volume/live → keyword research
- /v3/domain_analytics/technologies/overview/live → tech stack
```
**Note:** Large sites (former-employer.co.uk) return full data. Small UK sites often return null.

### 3. Customer Value Research
- Search for industry avg contract value
- Example: plant hire = £160/day mini digger, £250-600/day excavators
- B2B contracts typically £1,000-10,000+

### 4. Traffic & Keyword Analysis
- Extract: current organic clicks, top 5 keywords, click volumes
- Calculate: 1% CRO → leads → estimated revenue

## Pricing Matrix (Blog Retainer)

| Organic Clicks/Mo | Blogs/Mo | Price/Blog | Monthly Fee |
|-------------------|----------|------------|-------------|
| 1,000 | 10 | £100 | £1,000 |
| 5,000 | 30 | £95 | £2,850 |
| 10,000 | 50 | £90 | £4,500 |
| 20,000 | 100 | £80 | £8,000 |
| 50,000 | 200 | £60 | £12,000 |
| 100,000 | 300 | £50 | £15,000 |

### Technical Setup Fees
- **Small** (<5k organic): £500 one-off
- **Medium** (5-20k): £1,000 one-off  
- **Large** (20k+): £1,500 one-off

## Output Format

### ENHANCED ANALYSIS: [Domain]

**SITE OVERVIEW**
- URL, Platform, Business, Location, Services

**TECH STACK**
- CMS, Blog (verify at /news/, /blog/), Schema markup

**CURRENT SEO PERFORMANCE**
- Organic clicks/mo (or "No data available")
- Top 5 keywords with clicks

**KEYWORD OPPORTUNITIES**
- UK search volumes for industry keywords

**CUSTOMER VALUE**
- Avg contract/job value from research
- Industry benchmarks

**TIERED PRICING**
- Technical Foundation: £500-£1,500 (one-off)
- Content Starter: X blogs/mo @ £Y = £Z/mo
- Full Growth: X blogs/mo @ £Y = £Z/mo

**ROI ANALYSIS**
- At 1% CRO: estimated leads + revenue potential
- Break-even analysis

**CONTENT PLAN (3 Months)**
- Month 1: Foundation articles
- Month 2: Problem-solving articles
- Month 3: Industry-specific articles

## Tools Used
- web_fetch → website content
- DataForSEO API → traffic, backlinks, keywords
- web_search → customer value research
- Slack API → post to thread

## Cost Control
- Max 3 DataForSEO calls per analysis
- Use cached data where possible
- Stay under £0.25 API cost per analysis