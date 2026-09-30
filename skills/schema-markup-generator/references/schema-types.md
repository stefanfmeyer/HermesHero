# Schema Type Mappings

Detailed signal mappings for each schema type. Use this reference when extending detection logic.

## Product

**Primary signals:**
- Price symbols (£, $, €) or explicit price text
- SKU, Model, or Product ID references
- Add to cart / Buy now / Checkout buttons
- Product specifications tables
- Review/rating sections
- Availability text (in stock, ships in)
- Variant selectors (size, color, options)

**Properties to extract:**
- name (from H1 or title)
- description (meta description or first paragraph)
- image (og:image or main product image)
- url (canonical)
- sku (if detected)
- offers (if price detected)
- aggregateRating (if reviews detected)

## Article / BlogPosting / NewsArticle

**Primary signals:**
- Publication date (published, posted, updated)
- Author byline
- Reading time indicator
- Table of contents
- Blog/article/post terminology

**Properties to extract:**
- headline (title)
- description (meta description)
- author (from byline)
- datePublished (from meta or visible date)
- dateModified (if updated date present)
- image (og:image or featured image)
- mainEntityOfPage (canonical)

## Service

**Primary signals:**
- Conversion CTAs (get a quote, contact us, book now)
- Lead generation forms
- Benefits/why choose sections
- No explicit pricing

**Properties to extract:**
- name (from H1)
- description
- provider (Organization from sitewide entities)
- areaServed (if location mentioned)
- hasOfferCatalog (if service list present)

## FAQPage

**Primary signals:**
- Accordion/collapse/toggle elements
- Question-answer HTML structure (dt/dd, itemscope)
- Multiple question headings (ending with ? or starting with how/what/why)

**Properties to extract:**
- mainEntity array of Question/Answer pairs
- Extract question from heading
- Extract answer from following content block

## Organization

**Primary signals:**
- Logo in header/footer
- Company name in copyright notice
- Contact information
- Social media profile links

**Properties to extract:**
- name (from copyright or explicit company name)
- logo (image URL)
- url (canonical domain)
- sameAs (social profile URLs)
- contactPoint (if contact info present)
- address (if physical address present)

## LocalBusiness

**Primary signals:**
- All Organization signals plus:
- Physical address
- Phone number
- Opening hours
- Map embed
- Service area mentions

**Properties to extract:**
- All Organization properties plus:
- address (structured)
- telephone
- openingHours
- geo (coordinates if map present)
- priceRange (if indicated)

## CollectionPage / ItemList

**Primary signals:**
- Product grid/card layouts
- Filter/sort controls
- Pagination
- Category/archive terminology

**Properties to extract:**
- name (page title)
- description
- itemListElement (extract item names from cards)
- numberOfItems (count of items)

## BreadcrumbList

**Primary signals:**
- Navigation breadcrumb element
- Hierarchical link structure (Home > Category > Current)
- Breadcrumb schema/class names

**Properties to extract:**
- itemListElement array with position, name, item (URL)
- Build from navigation structure or URL path

## VideoObject

**Primary signals:**
- Video embed (YouTube, Vimeo, self-hosted)
- Video player controls
- Duration display

**Properties to extract:**
- name (video title)
- description
- thumbnailUrl
- uploadDate
- duration (if available)
- embedUrl or contentUrl

## SoftwareApplication / WebApplication

**Primary signals:**
- Feature lists
- Pricing tiers (basic, pro, enterprise)
- Platform mentions (Windows, Mac, iOS, Android)
- Download/install/trial CTAs

**Properties to extract:**
- name
- description
- applicationCategory
- operatingSystem (platforms supported)
- offers (if pricing present)
- aggregateRating (if reviews present)

## FinancialProduct / LoanOrCredit

**Primary signals:**
- APR percentages
- Loan/payment calculators
- Eligibility criteria
- Finance terms (hire purchase, PCP, conditional sale)

**Properties to extract:**
- name
- description
- annualPercentageRate (if explicit)
- loanTerm (if mentioned)
- requiredQualifications (eligibility criteria)

## Review / AggregateRating

**Primary signals:**
- Star ratings (visual or numeric)
- Rating values (X out of 5)
- Review count
- Testimonial sections

**Properties to extract:**
- ratingValue
- bestRating (usually 5)
- worstRating (usually 1)
- reviewCount
- reviewBody (for individual reviews)

## Person

**Primary signals:**
- Author bylines
- Team member profiles
- Bio sections

**Properties to extract:**
- name
- jobTitle
- worksFor (Organization)
- image (headshot)
- sameAs (social profiles)

## ImageObject

**Primary signals:**
- Image galleries
- Lightbox/carousel elements
- Schema-tagged images

**Properties to extract:**
- contentUrl (image URL)
- caption (if present)
- width/height (if available)
