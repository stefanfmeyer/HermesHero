---
name: html_sitemap_generator
description: Generate HTML and XML sitemaps for websites. Creates user-friendly HTML sitemaps and search-engine-optimised XML sitemaps with proper priority and change frequency tags.
---

# HTML Sitemap Generator

Generate HTML and XML sitemaps for websites.

## Overview

This skill:
1. Takes site structure or existing pages
2. Generates user-friendly HTML sitemap
3. Generates XML sitemap for search engines
4. Sets priority scores based on page importance
5. Sets change frequency appropriately
6. Outputs implementation-ready sitemaps

## Inputs

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `site_url` | string | ✅ | Base URL of the site |
| `pages` | array | ✅ | List of pages with URLs, titles, types |
| `brand_id` | string | ❌ | Brand identifier for styling |
| `xml_format` | string | ❌ | "standard", "image", "video", "news" |
| `lastmod` | date | ❌ | Last modification date for all pages |

## Outputs

| Output | Format | Description |
|--------|--------|-------------|
| HTML Sitemap | HTML | User-friendly sitemap page |
| XML Sitemap | XML | Search engine sitemap |
| Sitemap Index | XML | If multiple sitemaps |
| robots.txt Entry | text | Sitemap declaration for robots.txt |

## Page Types & Settings

| Page Type | Priority | Change Frequency |
|-----------|----------|-----------------|
| Homepage | 1.0 | weekly |
| Main Service | 0.9 | monthly |
| Landing Page | 0.8 | monthly |
| Blog/Article | 0.7 | weekly |
| FAQ | 0.6 | monthly |
| Contact | 0.5 | monthly |
| Category | 0.7 | weekly |
| Sub-page | 0.4 | yearly |

## Process

### Step 1: Categorize Pages

Group pages by:
- Primary pages (homepage, main services)
- Content pages (blogs, resources)
- Utility pages (contact, about)
- Archive pages (categories, tags)

### Step 2: Calculate Priority

Set priority based on:
- Page importance (homepage = 1.0)
- Link depth (closer to homepage = higher)
- Traffic potential (high-volume pages = higher)
- Conversion value (landing pages = higher)

### Step 3: Set Change Frequency

| Page Type | Change Frequency |
|-----------|-----------------|
| Homepage | always or daily |
| Blog/News | weekly |
| Category | weekly |
| Service/Product | monthly |
| Static (About, Contact) | yearly |
| Archive | never or yearly |

### Step 4: Generate HTML Sitemap

HTML sitemap rules:
- Group by category
- Display page title and brief description
- Link to each page
- Include last modified date
- Mobile-friendly design
- Accessible navigation

### Step 5: Generate XML Sitemap

XML sitemap rules:
- UTF-8 encoding
- Proper XML namespace
- Valid URL format
- Lastmod in ISO 8601 format
- Include loc, lastmod, changefreq, priority
- Maximum 50,000 URLs per sitemap
- Maximum 50MB per sitemap

## Example Output

### HTML Sitemap

```html
<!-- HTML Sitemap Example -->
<section class="sitemap">
  <h1>Site Map</h1>
  
  <div class="sitemap-section">
    <h2>Services</h2>
    <ul>
      <li><a href="/car-finance/">Car Finance</a></li>
      <li><a href="/bad-credit-car-finance/">Bad Credit Car Finance</a></li>
      <li><a href="/guarantor-car-finance/">Guarantor Car Finance</a></li>
    </ul>
  </div>
  
  <div class="sitemap-section">
    <h2>Resources</h2>
    <ul>
      <li><a href="/guides/">Guides</a></li>
      <li><a href="/blog/">Blog</a></li>
      <li><a href="/calculator/">Calculator</a></li>
    </ul>
  </div>
</section>
```

### XML Sitemap

```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://choosemycar.com/</loc>
    <lastmod>2026-04-08</lastmod>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>https://choosemycar.com/bad-credit-car-finance/</loc>
    <lastmod>2026-04-08</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
  </url>
</urlset>
```

## robots.txt Entry

```
Sitemap: https://choosemycar.com/sitemap.xml
```

## Constraints

- Maximum 50,000 URLs per XML sitemap
- Maximum 50MB per XML sitemap file
- All URLs must use same protocol (http or https)
- All URLs must be fully qualified
- Do NOT include URLs with query parameters (unless intentional)
- Do NOT include duplicate URLs
- Do NOT include blocked pages (robots.txt disallow)

## Error Handling

- If site_url not provided or invalid, return error
- If pages array is empty, generate from sitemap discovery
- If lastmod not provided, use current date
- If URL count exceeds 50,000, split into multiple sitemaps