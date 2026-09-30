---
name: builtwith-enrichment
description: Enrich company profiles with technology stack data using BuiltWith API. Cost-optimized with £0.20 per lead cap. Use when: (1) checking what technologies a domain uses, (2) filtering CSV of domains by tech stack, (3) comparing tech stacks of prospects, (4) finding sites using specific technologies, (5) company-to-domain discovery. Triggers: enrich, tech stack, builtwith, what technologies, tech lookup.
---

# BuiltWith Enrichment Skill

Efficient tech stack enrichment with cost controls.

## Cost Rules (CRITICAL)

**Cap: £0.20 per lead**

| Endpoint | Cost | Use Case |
|----------|------|----------|
| `free1` | FREE | Pre-filter domains |
| `domain-lookup` | ~£0.01 | Quick tech check |
| `domain-api` | ~£0.10-0.50 | Full data, qualified only |

**Balance check before bulk:**
```bash
curl "https://api.builtwith.com/usagev2/api.json?KEY=$BUILTWITH_API_KEY"
```

## Core Workflows

### 1. Single Domain Tech Check

```bash
# Quick lookup (preferred)
curl "https://api.builtwith.com/v22/api.json?KEY=$BUILTWITH_API_KEY&LOOKUP=domain.com&NOPII=1"

# Full enrichment (only if qualified lead)
curl "https://api.builtwith.com/v22/api.json?KEY=$BUILTWITH_API_KEY&LOOKUP=domain.com"
```

### 2. CSV Bulk Filter

1. `free1` for all domains (FREE) - get group counts
2. Filter based on tech gaps/opportunities
3. `domain-lookup` for promising domains only
4. `domain-api` only for hot leads

### 3. Find Sites Using Tech

```bash
curl "https://api.builtwith.com/lists12/api.json?KEY=$BUILTWITH_API_KEY&TECH=Shopify&LIMIT=100"
```

### 4. Semantic Tech Search

```bash
curl "https://api.builtwith.com/vector/v1/api.json?KEY=$BUILTWITH_API_KEY&QUERY=react+framework"
```

## Key Endpoints

| Endpoint | Purpose |
|----------|---------|
| `/v22/api.json` | Tech stack + metadata |
| `/free1/api.json` | Summary counts (FREE) |
| `/lists12/api.json` | Sites using technology |
| `/ctu3/api.json` | Company → domain |
| `/trends/v6/api.json` | Technology trends |
| `/vector/v1/api.json` | Semantic tech search |

## Opportunity Signals

**High-value:**
- `Spend > 500` → Has tech budget
- `IsPremium: "Yes"` → Pays for tools
- Old tech versions → Upgrade opportunity
- No analytics → Tracking gap

**Red flags:**
- All `IsPremium: "No"` → Low budget
- `Parked: true` → Not active

## Output Format

```markdown
## Tech Stack: domain.com

### Platform
- CMS: [value]
- Hosting: [value]

### Marketing
- Analytics: [value]
- SEO: [value]

### Opportunities
1. [Tech gap → sales angle]
2. [Budget signal]

### Recommended Pitch
[Focus area based on tech analysis]
```

## See Also

- `references/api-details.md` - Full endpoint documentation
- `references/cost-analysis.md` - Credit usage patterns