---
name: company-enrichment
description: Enrich company profiles using UK Companies House API. Fetch company details, officers, filing history. Use when: (1) looking up UK company information, (2) checking company status, (3) finding directors/officers. Triggers: company lookup, companies house, UK company, company directors.
---

# Company Enrichment Skill

Enrich UK company profiles using Companies House API.

## API Details

- **Base URL:** `https://api.company-information.service.gov.uk`
- **Auth:** Basic auth (API key as username, empty password)
- **API Key:** `87680a3c-581d-48b5-9b0b-3e6fbcc49095`

## Key Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /company/{number}` | Company details |
| `GET /company/{number}/officers` | Directors/secretaries |
| `GET /company/{number}/filing-history` | Filed documents |
| `GET /search/companies?q={query}` | Search by name |

## Usage

### Company Search

```bash
curl -u "API_KEY:" "https://api.company-information.service.gov.uk/search/companies?q=NEON%20GORILLA"
```

### Company Details

```bash
curl -u "API_KEY:" "https://api.company-information.service.gov.uk/company/12345678"
```

### Officers

```bash
curl -u "API_KEY:" "https://api.company-information.service.gov.uk/company/12345678/officers"
```

## Output Format

```markdown
## Company: [Name]

### Basic Info
- Company Number: [number]
- Status: [active/dissolved]
- Incorporated: [date]
- Type: [ltd/plc/llp]

### Officers
- Director: [Name] (appointed [date])
- Secretary: [Name]

### Filing History
- Most recent: [document description]
- Next accounts due: [date]

### Registered Office
- Address: [full address]
```

## Use Cases

1. **Lead qualification:** Verify company exists and is active
2. **Due diligence:** Check officer history
3. **Enrichment:** Add company details to CRM
4. **Risk assessment:** Check filing status