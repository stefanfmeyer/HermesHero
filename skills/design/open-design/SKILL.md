---
name: open-design
description: Open Design by nexu-io — open-source alternative to Claude Design. Local-first web-deployable design system and prototype generator. Uses any coding agent CLI via natural language. Clone at ~/Developer/open-design.
version: 1.0.0
author: Hermes Agent for StefActual
license: MIT
metadata:
  hermes:
    tags: [Design, Prototyping, UI, Web, Claude-Code, Open-Design, Design-Systems]
    related_skills: [claude-code, design-extract]
---

# Open Design — Quick Reference

Local-first open-source alternative to Claude Design. Generates web prototypes, decks, templates, and design systems via coding agent CLIs.

**Repo:** `https://github.com/nexu-io/open-design`
**Clone:** `~/Developer/open-design`

## Quick Start

```bash
cd ~/Developer/open-design
pnpm install          # first time only
pnpm tools-dev start web   # start daemon + web
# Open http://localhost:64238
```

## Key Commands

| Command | Purpose |
|---------|---------|
| `pnpm tools-dev start web` | Daemon + web (background) |
| `pnpm tools-dev run web` | Daemon + web (foreground) |
| `pnpm tools-dev stop` | Stop all |
| `pnpm tools-dev status` | Check what's running |
| `pnpm tools-dev logs` | View logs |
| `pnpm build` | Production build |
| `pnpm typecheck` | TypeScript check |
| `pnpm test` | Run tests |

## Architecture

- `apps/web` — Next.js 16 + React 18 web UI
- `apps/daemon` — Local daemon, owns `/api/*`, agent spawning, skills, artifacts
- `skills/` — 19 bundled artifact skills
- `design-systems/` — 129 brand design systems
- `craft/` — Universal craft rules (typography, color, anti-ai-slop)

## Skills

19 built-in skills across 4 modes:
- **Prototype** — web-prototype, saas-landing, dashboard, pricing-page, docs-page, blog-post, mobile-app
- **Deck** — simple-deck, magazine-web-ppt
- **Template** — pre-made templates
- **Design System** — design-system-skill

## Troubleshooting

- **"od bin not found"** — run `pnpm build` from daemon first
- **Port conflicts** — `pnpm tools-dev stop` then restart
- **Node version warning** — Node 25.7 works despite ~24 warning
