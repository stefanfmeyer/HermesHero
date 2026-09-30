---
name: design-extract
description: Clone website designs using design-extract (Manavarya09/GitHub). Use when user says "copy a website design".
---

# design-extract

Clone website designs using **design-extract** by Manavarya09.

**Repo:** `https://github.com/Manavarya09/design-extract`
**Install:** `cd ~/Developer/design-extract && npm install`
**Requires:** Node 20+, Playwright

## CLI Usage
```bash
# Extract full design system from a URL
designlang <url>

# Clone → generate a Next.js starter from a site's design
designlang clone <url>

# Extract + apply directly to your project
designlang apply <url>
```

## Key Flags
- `--screenshots` — component screenshots
- `--full` — screenshots + responsive + interactions + deep-interact
- `--platforms ios,android,flutter,wordpress` — multi-platform output
- `--storybook` — emit a runnable Storybook project
- `--smart` — LLM fallback for low-confidence classifiers (needs OpenAI/Anthropic key)
- `--dark` — also extract dark mode
- `--depth N` — crawl N internal pages
- `--selector ".pricing-card"` — extract only matching elements

## Other Commands
- `designlang score <url>` — design system quality score
- `designlang grade <url>` — Design Report Card
- `designlang diff <urlA> <urlB>` — compare two sites
- `designlang studio` — local web studio over the last extraction

## Output Formats
web tokens, iOS SwiftUI, Android Compose, Flutter, WordPress, Tailwind v4, Figma variables, shadcn/ui
