# Imported Skill Packs — Inventory & Dependency Notes

## tommyjepsen/awesome-ux-skills (imported 2026-09-23)

23 UX/product-design skills installed flat to `~/.hermes/skills/` (Claude Code single-file format, frontmatter reused as-is).

### Installed
- UX research & strategy: ux-research-methods, ux-personas, empathy-mapping, journey-mapping, ux-storyboard, double-diamond, like-wish-what-if
- UI analysis & critique: design-analysis, general-design-review, accessibility, ux-heuristics-review, dieter-rams-principles, craft, cognitive-load-conversion, persuasive-ux, feature-prioritization, low-effort-high-reward
- AI product design: ai-governors, ai-identifiers, ai-inputs, ai-trust-builders, ai-tuners, ai-wayfinders

### Dependency notes
- `design-analysis` embeds a Node/Playwright capture script (`/tmp/design-analysis/capture.mjs` pattern) for URL forensics (screenshot + computed-style harvest). **Playwright not installed on the workstation at import time.** Fix if needed: `npm i -D playwright && npx playwright install chromium`. Screenshot-based analysis (user pastes an image) works without Playwright — only URL capture needs it.
- All other skills are pure-prompt (no runtime deps).

### Update procedure
Re-clone and re-copy with force semantics, only on user request (the upstream repo's `./install.sh --force` equivalent).