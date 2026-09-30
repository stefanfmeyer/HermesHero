# Presentation Skill

Create SEO opportunity presentations for new clients by combining DataForSEO keyword data, Companies House company data, and other APIs into a structured slide deck deployed to Vercel.

## Confirmed Workflow

1. **Ben gives a client URL** — new prospect website
2. **I evaluate and return a Google Doc** — DataForSEO + Companies House + BuiltWith analysis, mapped to our core services. Create the doc and attach it to the right lead in Linear.
3. **Ben signs off** — approve or request changes
4. **I build and deploy the presentation** — live at `client-name.former-employer.io`

## Step 2: Research APIs

**DataForSEO** (cost cap: $0.10/session):
```bash
# Domain rank overview
curl -s -u "YmVuQG5lb25nb3JpbGxhLmNvLnVrOjk2OGE1ZmU3OTdmZjI5ZjM=" \
  "https://api.dataforseo.com/v3/dataforseo_labs/domain_rank_overview/live" \
  -d '{"domains":["client-domain.com"]}' | python3 -m json.tool

# Ranked keywords
curl -s -u "YmVuQG5lb25nb3JpbGxhLmNvLnVrOjk2OGE1ZmU3OTdmZjI5ZjM=" \
  "https://api.dataforseo.com/v3/dataforseo_labs/ranked_domains/live" \
  -d '{"domains":["client-domain.com"],"limit":50}' | python3 -m json.tool

# Competitors
curl -s -u "YmVuQG5lb25nb3JpbGxhLmNvLnVrOjk2OGE1ZmU3OTdmZjI5ZjM=" \
  "https://api.dataforseo.com/v3/dataforseo_labs/domain_competitors/live" \
  -d '{"domains":["client-domain.com"],"limit":20}' | python3 -m json.tool

# Keyword ideas (related + PAA)
curl -s -u "YmVuQG5lb25nb3JpbGxhLmNvLnVrOjk2OGE1ZmU3OTdmZjI5ZjM=" \
  "https://api.dataforseo.com/v3/dataforseo_labs/domain_keywords_organic/live" \
  -d '{"domains":["client-domain.com"],"limit":100}' | python3 -m json.tool
```

**Companies House**:
```bash
curl -s -u "87680a3c-581d-48b5-9b0b-3e6fbcc49095:" \
  "https://api.company-information.service.gov.uk/search/companies?q=CLIENT_NAME" \
  | python3 -m json.tool
```

**BuiltWith** (tech stack):
```bash
# MCP: builtwith domain-lookup
```

## Step 3: Create Google Doc

Use GOG CLI:
```bash
gog docs create "CLIENT NAME — SEO Opportunity Proposal" \
  --file /path/to/proposal.md \
  --account bruce@former-employer.io
```

Then attach to the Linear lead:
```bash
gog drive search "CLIENT NAME — SEO Opportunity Proposal" --json
# Get the docId, then link it in Linear
```

## Step 5: Deploy Presentation

```bash
cd ~/openclaw/workspace/qa-walkthrough-presentation
# Copy/symlink for new client: ln -s qa-walkthrough-presentation client-name
vercel --token $VERCEL_TOKEN deploy --prod --yes
```

Then add custom domain via Namecheap API.

## Slide Structure (11 slides)

1. **TitleSlide** — Client name + a previous employer branding
2. **Slide1Context** — Market context and opportunity
3. **Slide2TheChallenge** — The problem to solve
4. **Slide3QAFramework** — The four-layer QA system overview
5. **Slide4TestingLayers** — Detailed testing layers
6. **Slide5AutomatedTesting** — Automated testing approach
7. **Slide6ContentQA** — Content quality assurance
8. **Slide7TechnicalQA** — Technical SEO QA
9. **Slide8BrandCompliance** — Brand compliance checks
10. **Slide9GovernanceModel** — Governance and ongoing ops
11. **Slide10Summary** — Summary and next steps

## Meta Tags (index.html)

```html
<title>CLIENT NAME — QA Walkthrough | a previous employer</title>
<meta name="description" content="..." />
<meta property="og:image" content="/og-image.jpg" />
```

## Files

- OG image: `public/og-image.jpg` (1200x650)
- Favicon: `public/favicon.png` (1000x1000, generates 16/32/180px variants)
- Apple touch: `public/apple-touch-icon.png`
