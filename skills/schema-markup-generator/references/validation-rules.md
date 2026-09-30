# Schema Validation Rules

This document defines the validation rules used by `schema_validator.py` to check generated JSON-LD against schema.org standards and Google Rich Results requirements.

## Validation Layers

### 1. Schema.org Core Validation
Checks that entities conform to schema.org type definitions.

**Checks:**
- ✅ Required properties present
- ✅ Property types correct (Text, URL, Number, Date, etc.)
- ✅ Enumerated values valid
- ✅ Nested types correct

### 2. Google Rich Results Validation
Stricter requirements for Google Search features.

**Checks:**
- ✅ Minimum item counts (e.g., FAQPage ≥ 1 Q&A)
- ✅ Required properties for rich results (e.g., VideoObject.thumbnailUrl)
- ✅ Recommended properties for enhanced display

### 3. Best Practices Validation
Recommendations for optimal SEO performance.

**Checks:**
- ⚠️ Missing recommended properties
- ⚠️ Suboptimal property values
- ℹ️ Enhancement opportunities

## Type-Specific Rules

### FAQPage

**Required:**
- `mainEntity` (array of Question)

**Google Rich Results:**
- Minimum 1 Question in mainEntity
- Each Question must have:
  - `name` (the question text)
  - `acceptedAnswer` with `text`

**Common Errors:**
- Missing acceptedAnswer
- Empty question text
- Answer text too short (< 10 chars)

### FinancialProduct

**Required:**
- `name`

**Recommended:**
- `description`
- `interestRate` or `annualPercentageRate`
- `loanType` (from enumerated values)

**Enumerated Values (loanType):**
- `PersonalLoan`
- `BusinessLoan`
- `MortgageLoan`
- `StudentLoan`
- `PaydayLoan`
- `RefinanceLoan`
- `SecuredLoan`
- `UnsecuredLoan`

**Validation:**
- interestRate must be Number (0.0-1.0) or QuantitativeValue
- APR percentages converted to decimal (19.9% → 0.199)

### VideoObject

**Required:**
- `name`

**Google Rich Results Required:**
- `name`
- `description`
- `thumbnailUrl`
- `uploadDate`

**Auto-Generated:**
- `thumbnailUrl`: `https://img.youtube.com/vi/VIDEO_ID/maxresdefault.jpg`
- `uploadDate`: Current date if not extractable

**Common Errors:**
- Missing thumbnailUrl (auto-fixed for YouTube)
- Missing uploadDate (auto-fixed with current date)
- Invalid URL format

### Organization

**Required:**
- `name`

**Recommended:**
- `url` (official website)
- `logo` (URL or ImageObject)
- `sameAs` (social media profiles)
- `description`

**Extraction Sources:**
- Copyright notices (© 2024 Company Name)
- Logo alt text
- Meta tags (author, og:site_name)
- Page title patterns

### BreadcrumbList

**Required:**
- `itemListElement` (array of ListItem)

**Google Rich Results:**
- Minimum 2 items
- Each ListItem must have:
  - `position` (integer)
  - `name`
  - `item` (URL, except last item)

**Common Errors:**
- Only 1 breadcrumb item (Google requires ≥2)
- Missing position
- Invalid URL format

### HowTo

**Required:**
- `name`

**Google Rich Results:**
- Minimum 1 step
- Each step should have:
  - `text` (instruction)
  - Optional: `name`, `image`

**Filtered Out:**
- Navigation items
- Breadcrumb-like content
- Questions (these are FAQ, not HowTo)
- Very short items (< 20 chars)

### Dataset

**Required:**
- `name`

**Recommended:**
- `description`
- `variableMeasured` (column names)
- `url` (download/access URL)

**Extraction:**
- HTML tables with headers
- Comparison tables
- Data grids

## Property Type Validation

### URL
**Pattern:** `^https?://[^\s]+$`
**Examples:**
- ✅ `https://example.com`
- ✅ `http://example.com/page`
- ❌ `example.com` (missing protocol)
- ❌ `/relative/path` (not absolute)

### Email
**Pattern:** `^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$`
**Examples:**
- ✅ `contact@example.com`
- ❌ `contact@example` (missing TLD)
- ❌ `@example.com` (missing local part)

### Date
**Pattern:** `^\d{4}-\d{2}-\d{2}$`
**Examples:**
- ✅ `2024-01-15`
- ❌ `15/01/2024` (wrong format)
- ❌ `Jan 15, 2024` (wrong format)

### Number
**Type:** `int` or `float`
**Examples:**
- ✅ `19.9`
- ✅ `0.199`
- ❌ `"19.9"` (string instead of number)

### Text
**Type:** `string`
**Examples:**
- ✅ `"Product Name"`
- ✅ `"Description with <a>HTML</a> tags"` (HTML stripped)

## Error Severity Levels

### ❌ Errors (Must Fix)
Schema is invalid and may be rejected by search engines.
- Missing required properties
- Invalid property types
- Malformed JSON-LD

### ⚠️ Warnings (Should Fix)
Schema is valid but may not qualify for rich results.
- Missing Google Rich Results properties
- Suboptimal property values
- Non-standard properties

### ℹ️ Info (Consider)
Schema is valid and functional, but could be enhanced.
- Missing recommended properties
- Enhancement opportunities
- Best practice suggestions

## Validation Examples

### Example 1: Valid FAQPage
```json
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [{
    "@type": "Question",
    "name": "What is bad credit car finance?",
    "acceptedAnswer": {
      "@type": "Answer",
      "text": "Bad credit car finance is..."
    }
  }]
}
```
**Result:** ✅ VALID

### Example 2: Invalid FAQPage
```json
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [{
    "@type": "Question",
    "name": "What is bad credit car finance?"
  }]
}
```
**Result:** ❌ INVALID
**Error:** Missing required property 'acceptedAnswer'

### Example 3: VideoObject Missing Rich Results
```json
{
  "@context": "https://schema.org",
  "@type": "VideoObject",
  "name": "Product Demo",
  "embedUrl": "https://youtube.com/embed/abc123"
}
```
**Result:** ✅ VALID (schema.org)
**Warnings:** 
- ⚠️ Google Rich Results requires 'thumbnailUrl'
- ⚠️ Google Rich Results requires 'uploadDate'

## Updating Validation Rules

To add new validation rules:

1. Add type definition to `SCHEMA_TYPES` in `schema_validator.py`
2. Define required/optional properties
3. Add enumerated values if applicable
4. Add Google Rich Results requirements
5. Update this documentation

## References

- [schema.org documentation](https://schema.org/docs/documents.html)
- [Google Rich Results Test](https://search.google.com/test/rich-results)
- [Google Structured Data Guidelines](https://developers.google.com/search/docs/appearance/structured-data)
