---
name: faq-creator
description: Generates FAQ sections for SEO articles using DataForSEO PAA data, ensuring questions don't duplicate content already in the article. Uses brand context from Google Drive and outputs FAQ markdown + JSON schema for integration with the broader SEO content workflow. Accepts article_text, primary_keyword, brand_id, author_persona, and keywords_to_avoid inputs. Outputs FAQ markdown for Stage 5 and FAQ JSON schema for Stage 7.
---

# FAQ Creator

Generate FAQ sections for SEO articles using People Also Ask data, with no duplication of article content.

## Overview

This skill:
1. Fetches PAA (People Also Ask) questions from DataForSEO SERP API
2. Parses the article to identify topics already covered
3. Filters PAA questions to avoid duplication
4. Generates FAQ answers in the brand voice
5. Outputs FAQ markdown + JSON schema

## Inputs

| Input | Type | Source | Required |
|-------|------|--------|----------|
| `article_text` | string | Stage 3 (CCE output) | ✅ |
| `primary_keyword` | string | Stage 1 | ✅ |
| `brand_id` | string | User | ✅ |
| `author_persona` | string | User | Optional |
| `keywords_to_avoid` | array | Stage 1 | ✅ |

## Outputs

| Output | Format | Destination |
|--------|--------|-------------|
| FAQ Section | Markdown | Stage 5 (Internal Link Mapper) |
| FAQ Section | Google Doc | Review/approval |
| FAQ JSON Schema | JSON | Stage 7 (Schema Generator) |

## Process

### Step 1: Fetch PAA from DataForSEO

Use the working SERP API to fetch People Also Ask questions:

```python
api_post("serp/google/organic/live/advanced", [{
    "keyword": primary_keyword,
    "location_name": "United Kingdom",
    "language_name": "English",
    "max_crawl_pages": 10
}])
```

Extract questions from `items[].type == "people_also_ask"`.

### Step 2: Parse Article Content

Parse the article to identify topics already covered:

1. Extract H2 and H3 headings
2. Extract key phrases from paragraphs
3. Build a list of "covered topics"

```python
def extract_article_topics(article_text):
    topics = []
    # Extract headings
    for heading in re.findall(r'^#{2,3}\s+(.+)$', article_text, re.MULTILINE):
        topics.append(heading.lower())
    # Extract key phrases (first sentence of each paragraph)
    for para in article_text.split('\n\n'):
        first_sentence = para.split('.')[0].lower()
        if len(first_sentence) > 20:
            topics.append(first_sentence)
    return topics
```

### Step 3: Filter PAA Questions

Filter out questions that:
- Are already answered in the article
- Match `keywords_to_avoid`
- Are too similar to covered topics

```python
def should_include_question(question, article_topics, keywords_to_avoid):
    q_lower = question.lower()
    
    # Check keywords to avoid
    for kw in keywords_to_avoid:
        if kw.lower() in q_lower:
            return False
    
    # Check if topic is already covered
    for topic in article_topics:
        # If question asks about same thing as a heading, skip
        if topic in q_lower or q_lower in topic:
            return False
    
    return True
```

### Step 4: Generate FAQ Answers

For each filtered question:

1. Load brand context from Google Drive
2. Write answer in brand voice
3. Ensure answer doesn't duplicate article content
4. Keep answers concise (40-80 words)

### Step 5: Generate FAQ JSON Schema

Create FAQPage schema for Stage 7:

```json
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "Question text?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Answer text."
      }
    }
  ]
}
```

## Brand Context Loading

Access Google Drive:

```
/brand-knowledge/{brand_id}/
├── Brand Guidelines.md
├── Writing Style Guide.md
└── user-personas/
    └── {author}/
        └── Persona - {Author}.md
```

If `author_persona` is provided, load that persona. Otherwise, use brand guidelines only.

## FAQ Generation Rules

1. **5-6 FAQs maximum** — quality over quantity
2. **No duplication** — questions must not be answered in article body
3. **Brand voice** — answer in the brand's tone
4. **Concise answers** — 40-80 words each
5. **Actionable** — answers should be useful, not vague
6. **Next steps** — at least one FAQ should address next actions

## Example Output

### FAQ Markdown

```markdown
### Frequently Asked Questions

**What are the best SEO tips for beginners?**
The best SEO tips for beginners focus on three areas: technical foundation, quality content, and consistent optimization. Start with keyword research, optimize your page titles and meta descriptions, and build a simple internal linking structure.

**How long does it take to see SEO results?**
SEO is a long-term strategy. Most websites see initial ranking improvements within 3-6 months, with significant traffic growth typically taking 6-12 months of consistent effort.

**Do I need technical skills for SEO?**
Not necessarily. While technical SEO can help, many SEO tasks — like content creation and keyword optimization — don't require coding knowledge. Start with the basics and learn as you go.
```

### FAQ JSON Schema

```json
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "What are the best SEO tips for beginners?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "The best SEO tips for beginners focus on three areas: technical foundation, quality content, and consistent optimization. Start with keyword research, optimize your page titles and meta descriptions, and build a simple internal linking structure."
      }
    }
  ]
}
```

## Workflow Integration

```
Stage 3: CCE writes article
         ↓
Stage 4: faq_creator
         ├── Receives: article_text, primary_keyword, brand_id, author_persona
         ├── Loads: brand guidelines, persona from Google Drive
         ├── Fetches: PAA questions from DataForSEO SERP
         ├── Filters: removes questions covered in article
         ├── Generates: FAQ markdown + JSON schema
         └── Outputs:
              ├── FAQ markdown → Stage 5
              └── FAQ JSON schema → Stage 7
         ↓
Stage 5: Internal Link Mapper — adds internal links to article + FAQ
Stage 7: Schema Generator — creates Article + FAQPage schema
```

## Constraints

- Do NOT include questions already answered in the article
- Do NOT include questions matching `keywords_to_avoid`
- Do NOT generate more than 6 FAQs
- Do NOT write answers that duplicate article content
- Do NOT generate FAQ schema here — only pass to Stage 7

## Error Handling

- If SERP API fails, fall back to generating FAQs from article topics only
- If Google Drive access fails, use brand context from local cache if available
- If no PAA questions found, generate FAQs from article subtopics