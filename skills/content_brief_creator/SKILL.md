# content_brief_creator

## Purpose
Creates a structured SEO brief combining keyword clusters, SERP patterns, and recommended page sections.

## Stage
Research (Stage 1)

## Inputs
- **keyword_data** (object): Output from keyword_research_finder
- **serp_analysis** (object): Output from serp_top20_analyser
- **content_type** (string): landing_page, blog_post, guide, etc.
- **brand_voice** (string, optional): Brand tone guidelines

## Outputs
- **page_title_suggestions**: 3-5 title options with character counts
- **meta_description_suggestions**: 3-5 meta descriptions
- **h1_suggestion**: Primary H1 based on keyword research
- **content_outline**: Recommended sections with H2/H3 structure
- **word_count_target**: Min/ideal/max word count
- **keyword_placement_guide**: Where to place primary/secondary keywords
- **ux_recommendations**: Tables, lists, media suggestions
- **internal_link_opportunities**: Related pages to link
- **competitor_gaps**: Content gaps to fill

## Execution Flow
1. Combine keyword and SERP data
2. Generate title and meta suggestions
3. Build content outline from SERP patterns
4. Calculate word count targets
5. Map keyword placements
6. Identify UX elements
7. Create comprehensive brief

## Related Skills
- **keyword_research_finder**: Provides keyword data
- **serp_top20_analyser**: Provides SERP analysis
- **landing_page_structure_builder**: Uses brief for structure
