# Cost Analysis - BuiltWith API

## Credit Costs (Approximate)

| Endpoint | Credits | GBP Estimate |
|----------|---------|--------------|
| WhoAmI | 0 | £0.00 |
| Usage | 0 | £0.00 |
| Free API | 0 | £0.00 |
| Domain Lookup | ~10-50 | £0.01-0.05 |
| Domain API | ~100-500 | £0.10-0.50 |
| Lists API | Varies | Varies |
| Relationships | ~200 | £0.20 |
| Company to URL | ~10 | £0.01 |
| Vector Search | 1 | £0.001 |

## £0.20 Per Lead Workflow

### Cheap Path (Best for Filtering)
1. `free1` - FREE - Pre-filter
2. `domain-lookup` - ~£0.02 - Quick tech check
3. Skip if no opportunity

**Total: ~£0.02 per domain**

### Standard Path (For Qualified Leads)
1. `free1` - FREE
2. `domain-lookup` - ~£0.02
3. `domain-api` - ~£0.10-0.15

**Total: ~£0.15 per domain**

### Full Enrichment (Hot Leads Only)
1. `free1` - FREE
2. `domain-lookup` - ~£0.02
3. `domain-api` - ~£0.10-0.15
4. `relationships` - ~£0.20 (if needed)

**Total: ~£0.35 per domain (use sparingly)**

## Bulk Operations

### CSV with 100 Domains

**Option A: Minimal (filtering only)**
- `free1` x 100 = FREE
- `domain-lookup` x 20 (promising) = ~£0.40
- Total: ~£0.40 for 100 domains = ~£0.004/lead

**Option B: Standard (qualified leads)**
- `free1` x 100 = FREE
- `domain-lookup` x 30 = ~£0.60
- `domain-api` x 10 = ~£1.00
- Total: ~£1.60 for 100 domains = ~£0.016/lead

**Option C: Full (10 hot leads)**
- `free1` x 100 = FREE
- `domain-lookup` x 50 = ~£1.00
- `domain-api` x 10 = ~£1.00
- `relationships` x 5 = ~£1.00
- Total: ~£3.00 for 10 hot leads = ~£0.30/lead

## Cost Monitoring

Check balance:
```bash
curl "https://api.builtwith.com/usagev2/api.json?KEY=$BUILTWITH_API_KEY"
```

Response:
```json
{
  "credits_total": 100000,
  "credits_used": 5000,
  "credits_available": 95000
}
```

## Cost Alerts

- Set alert at 80% usage
- Stop bulk operations if approaching limit
- Purchase only when necessary