# BuiltWith API Reference

Full API documentation from https://api.builtwith.com/llms.txt

## Base URL
- `https://api.builtwith.com`

## Authentication
- Query param: `KEY=YOUR_API_KEY`
- Header: `Authorization: Bearer YOUR_API_KEY`

## Endpoints

### WhoAmI
```
GET /whoamiv1/api.json?KEY=YOUR_KEY
```
Returns account info. Free.

### Usage
```
GET /usagev2/api.json?KEY=YOUR_KEY
```
Returns credit balance. Free.

### Domain API (v22)
```
GET /v22/api.json?KEY=YOUR_KEY&LOOKUP=domain.com
GET /v22/api.json?KEY=YOUR_KEY&LOOKUP=domain.com&NOPII=1
GET /v22/api.json?KEY=YOUR_KEY&LOOKUP=domain.com&NOMETA=1
GET /v22/api.json?KEY=YOUR_KEY&LOOKUP=domain.com&NOATTR=1
```
Tech stack + metadata. Supports POST for bulk (up to 1000 domains).

Optional filters:
- `NOPII` - Remove PII (emails, names)
- `NOMETA` - Remove meta section
- `NOATTR` - Remove attributes section
- `LIVEONLY` - Only live technologies
- `FDRANGE` / `LDRANGE` - First/Last Detected date range

### Free API (v1)
```
GET /free1/api.json?KEY=YOUR_KEY&LOOKUP=domain.com
```
Summary counts only. FREE.

### Lists API (v12)
```
GET /lists12/api.json?KEY=YOUR_KEY&TECH=Shopify&LIMIT=100
GET /lists12/api.json?KEY=YOUR_KEY&TECH=WordPress&OFFSET=<offset>
```
List of sites using a technology.

### Relationships API (v4)
```
GET /rv4/api.json?KEY=YOUR_KEY&LOOKUP=domain.com
```
Related domains. Returns up to 500 per page.

### Company to URL API (v3)
```
GET /ctu3/api.json?KEY=YOUR_KEY&COMPANY=Example%20Inc
```
Discover domains from company names.

### Tags API (v1)
```
GET /tag1/api.json?KEY=YOUR_KEY&LOOKUP=IP-1.2.3.4
```
Domains related to IPs and site attributes.

### Recommendations API (v1)
```
GET /rec1/api.json?KEY=YOUR_KEY&LOOKUP=domain.com
```
Tech recommendations for a domain.

### Redirects API (v1)
```
GET /redirect1/api.json?KEY=YOUR_KEY&LOOKUP=domain.com
```
Redirect history (inbound + outbound).

### Keywords API (v2)
```
GET /kw2/api.json?KEY=YOUR_KEY&LOOKUP=domain.com
```
Keywords for a domain.

### Keyword Search API (v1)
```
GET /kws1/api.json?KEY=YOUR_KEY&KEYWORD=perfume&LIMIT=100
```
Search for sites containing keyword.

### Trends API (v6)
```
GET /trends/v6/api.json?KEY=YOUR_KEY&TECH=Shopify
```
Technology trends with coverage stats.

### Product API (v1)
```
GET /productv1/api.json?KEY=YOUR_KEY&QUERY=Adidas%20Yeezy
```
Find sites selling products.

### Trust API (v1)
```
GET /trustv1/api.json?KEY=YOUR_KEY&LOOKUP=domain.com
```
Trust/fraud signals.

### Vector Search API (v1)
```
GET /vector/v1/api.json?KEY=YOUR_KEY&QUERY=react+framework&LIMIT=10
```
Semantic search for technologies. Uses 1 credit per search.

## Response Structure - Domain API

```json
{
  "Results": [{
    "Result": {
      "Spend": 987,
      "SpendHistory": [{"D": timestamp, "S": spend}],
      "Paths": [{
        "Technologies": [{
          "Name": "WordPress 6.x",
          "Categories": ["CMS"],
          "Tag": "cms",
          "FirstDetected": timestamp,
          "LastDetected": timestamp,
          "IsPremium": "No"
        }],
        "Domain": "example.com",
        "SubDomain": ""
      }],
      "Meta": {
        "CompanyName": "Example Inc",
        "Country": "US",
        "Emails": ["contact@example.com"],
        "Socials": ["twitter.com/example"]
      }
    }
  }]
}
```

## Tech Categories

Common tags:
- `cms` - Content Management System
- `javascript` - JavaScript libraries/frameworks
- `analytics` - Analytics tools
- `hosting` - Hosting providers
- `ads` - Advertising
- `shop` - Ecommerce
- `mx` - Email/marketing
- `cdn` - Content delivery
- `ssl` - Certificates
- `widgets` - Embedded tools

## Agent Payment API

Base: `https://payments.builtwith.com`

- `GET /v1/billing/api-discovery?KEY=...` - Check balance
- `GET /v1/billing/api-configuration?KEY=...` - Spending limits
- `POST /v1/billing/api-purchase` - Purchase credits (min 2000)