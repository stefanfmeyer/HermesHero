# Entity Hierarchy Rules

Proper schema hierarchy ensures search engines understand relationships between entities and avoids conflicts.

## Core Principles

1. **One primary entity per page** — Unless multiple entities are clearly required
2. **Nested relationships** — Child entities inside parent where logical
3. **No duplication** — Avoid duplicate Organization blocks, conflicting definitions
4. **No empty properties** — Omit properties rather than using placeholders
5. **No placeholder values** — Never fabricate missing data

## Valid Hierarchies

### Product Page

```json
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "Product Name",
  "description": "...",
  "offers": {
    "@type": "Offer",
    "price": "99.99",
    "priceCurrency": "GBP",
    "availability": "https://schema.org/InStock"
  },
  "aggregateRating": {
    "@type": "AggregateRating",
    "ratingValue": "4.5",
    "reviewCount": "127"
  },
  "review": [...]
}
```

**Hierarchy:**
- Product (primary)
  - Offer (nested)
  - AggregateRating (nested)
  - Review[] (nested)
- BreadcrumbList (sibling, linked via mainEntity)
- FAQPage (sibling, linked via mainEntity)

### Article Page

```json
{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "Article Title",
  "author": {
    "@type": "Person",
    "name": "Author Name"
  },
  "publisher": {
    "@type": "Organization",
    "name": "Publisher Name",
    "logo": {
      "@type": "ImageObject",
      "url": "..."
    }
  }
}
```

**Hierarchy:**
- Article (primary)
  - Person/Author (nested)
  - Organization/Publisher (nested)
    - ImageObject/Logo (nested)
- BreadcrumbList (sibling)
- FAQPage (sibling, if FAQ content present)

### Service Page

```json
{
  "@context": "https://schema.org",
  "@type": "Service",
  "name": "Service Name",
  "provider": {
    "@type": "Organization",
    "name": "Company Name",
    "logo": "...",
    "url": "..."
  }
}
```

**Hierarchy:**
- Service (primary)
  - Organization/Provider (nested)
- BreadcrumbList (sibling)
- FAQPage (sibling)

### Category/Collection Page

```json
{
  "@context": "https://schema.org",
  "@type": "CollectionPage",
  "name": "Category Name",
  "mainEntity": {
    "@type": "ItemList",
    "numberOfItems": 24,
    "itemListElement": [
      {
        "@type": "ListItem",
        "position": 1,
        "url": "/product-1"
      }
    ]
  }
}
```

**Hierarchy:**
- CollectionPage (primary)
  - ItemList (nested as mainEntity)
- BreadcrumbList (sibling)
- Organization (sibling, from sitewide entities)

### Finance Page

```json
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "Car Finance",
  "description": "...",
  "offers": {
    "@type": "Offer",
    ...
  },
  "offers": {
    "@type": "FinancialProduct",
    "annualPercentageRate": "5.9",
    "loanTerm": "P60M"
  }
}
```

**Hierarchy:**
- Product (primary)
  - FinancialProduct or LoanOrCredit (nested under offers or as separate nested entity)
- FAQPage (sibling)
- Organization (sibling)

### Local Business Page

```json
{
  "@context": "https://schema.org",
  "@type": "LocalBusiness",
  "name": "Business Name",
  "address": {
    "@type": "PostalAddress",
    "streetAddress": "...",
    "addressLocality": "...",
    "postalCode": "...",
    "addressCountry": "GB"
  },
  "geo": {
    "@type": "GeoCoordinates",
    "latitude": "51.5074",
    "longitude": "-0.1278"
  },
  "openingHours": "Mo-Fr 09:00-17:00"
}
```

**Hierarchy:**
- LocalBusiness (primary, extends Organization)
  - PostalAddress (nested)
  - GeoCoordinates (nested)
- BreadcrumbList (sibling)

## Using @graph for Multiple Entities

When multiple top-level entities are needed, use `@graph`:

```json
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Product",
      "@id": "#product",
      "name": "..."
    },
    {
      "@type": "Organization",
      "@id": "#organization",
      "name": "..."
    },
    {
      "@type": "BreadcrumbList",
      "itemListElement": [
        {
          "@type": "ListItem",
          "position": 1,
          "item": {
            "@id": "#organization"
          }
        }
      ]
    }
  ]
}
```

**Use @graph when:**
- Multiple independent entities exist (not nested)
- Entities need to reference each other via @id
- Keeping schema modular and extensible

## Common Mistakes to Avoid

### ❌ Duplicate Organization

```json
// WRONG: Two Organization blocks
{
  "@graph": [
    {"@type": "Organization", "name": "Company A"},
    {"@type": "Organization", "name": "Company A"}
  ]
}
```

```json
// RIGHT: Single Organization, referenced where needed
{
  "@graph": [
    {"@type": "Organization", "@id": "#org", "name": "Company A"},
    {"@type": "Service", "provider": {"@id": "#org"}}
  ]
}
```

### ❌ Conflicting Primary Entities

```json
// WRONG: Both Product and Article as primary
{
  "@type": "Product",
  ...
}
{
  "@type": "Article",
  ...
}
```

```json
// RIGHT: One primary, one supporting (if truly both apply)
{
  "@type": "Product",
  "description": "...",
  "review": {
    "@type": "Article",
    "headline": "Review Title"
  }
}
```

### ❌ Empty Properties

```json
// WRONG: Empty or placeholder values
{
  "@type": "Product",
  "name": "",
  "price": "TBD",
  "description": "Lorem ipsum..."
}
```

```json
// RIGHT: Omit missing properties
{
  "@type": "Product",
  "name": "Product Name",
  "description": "Actual description..."
}
```

### ❌ Fabricated Data

```json
// WRONG: Made-up values
{
  "@type": "Product",
  "aggregateRating": {
    "ratingValue": "5",
    "reviewCount": "1000"
  }
}
```

```json
// RIGHT: Only include if actually present on page
{
  "@type": "Product",
  "name": "Product Name"
  // No aggregateRating if not present
}
```

## Entity Linking Patterns

### BreadcrumbLink to Primary Entity

```json
{
  "@graph": [
    {
      "@type": "Product",
      "@id": "#product"
    },
    {
      "@type": "BreadcrumbList",
      "itemListElement": [
        {
          "@type": "ListItem",
          "position": 1,
          "name": "Home",
          "item": "https://example.com/"
        },
        {
          "@type": "ListItem",
          "position": 2,
          "name": "Products",
          "item": "https://example.com/products/"
        },
        {
          "@type": "ListItem",
          "position": 3,
          "item": {"@id": "#product"}
        }
      ]
    }
  ]
}
```

### FAQPage to Primary Entity

```json
{
  "@graph": [
    {
      "@type": "Product",
      "@id": "#product"
    },
    {
      "@type": "FAQPage",
      "mainEntity": [...],
      "about": {"@id": "#product"}
    }
  ]
}
```

## Sitewide Entity Injection

When `sitewide_entities` JSON is provided:

1. **Organization** — Always inject as top-level entity if not detected on page
2. **Link to primary** — Reference Organization in Service.provider or Article.publisher
3. **Avoid duplication** — If Organization already detected on page, merge rather than duplicate

```json
// Sitewide entities input
{
  "organization_name": "a previous employer Ltd",
  "organization_logo": "https://example.com/logo.png",
  "organization_url": "https://example.com",
  "social_profiles": [
    "https://facebook.com/former-employer",
    "https://twitter.com/former-employer"
  ]
}
```

```json
// Injected into schema
{
  "@type": "Organization",
  "name": "a previous employer Ltd",
  "logo": "https://example.com/logo.png",
  "url": "https://example.com",
  "sameAs": [
    "https://facebook.com/former-employer",
    "https://twitter.com/former-employer"
  ]
}
```

## Page-Type Specific Patterns

### E-commerce Product
Primary: Product → Offer, AggregateRating, Review
Supporting: BreadcrumbList, FAQPage, Organization

### Blog Post
Primary: Article or BlogPosting → Person/Author, Organization/Publisher
Supporting: BreadcrumbList, FAQPage (if comments/FAQ present)

### Service Landing
Primary: Service → Organization/Provider
Supporting: BreadcrumbList, FAQPage, LocalBusiness (if location-specific)

### Category/Collection
Primary: CollectionPage → ItemList
Supporting: BreadcrumbList, Organization

### Software Product
Primary: SoftwareApplication → Offer, AggregateRating
Supporting: BreadcrumbList, FAQPage, Organization

### Finance Product
Primary: Product or FinancialProduct → LoanOrCredit, Offer
Supporting: FAQPage, Organization, BreadcrumbList
