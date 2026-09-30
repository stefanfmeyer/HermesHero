---
name: skill-library-ops
description: "Install, import, audit, and uninstall skills from external repos (Claude Code / 'awesome-skills' GitHub format) into the Hermes skill library at ~/.hermes/skills/. Covers the Claude Code-to-Hermes format translation, bulk install procedure, dedupe rules, post-install verification, and runtime dependency audit. Use when asked to 'install these skills from this repo', 'copy these skills into yourself', 'import a skill pack', add skills from a GitHub repo, or share/sync skills between Hermes and Claude Code."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [skills, import, claude-code, installation, library]
    related_skills: [hermes-agent-skill-authoring, hermes-agent]
---

# Skill Library Operations

## Overview

Many high-quality skill packs are published as Claude Code skill repos (single `.md` files with `name`/`description` frontmatter, e.g. tommyjepsen/awesome-ux-skills). The content transfers 1:1 to Hermes; only the directory shape differs. This skill is the import/ops counterpart to `hermes-agent-skill-authoring` (which covers authoring skills in-repo) — use that for writing skills from scratch, this one for installing external ones.

## When to Use

- User points at a GitHub repo of skills and says "install / copy / add these"
- Auditing what is installed, where it came from, or whether a skill's runtime deps exist
- Uninstalling or force-updating an imported pack
- Don't use for: authoring brand-new skills (use `hermes-agent-skill-authoring`), in-repo skills under a hermes-agent checkout

## Format Mapping

Claude Code skill → Hermes skill:

| Claude Code | Hermes |
|---|---|
| `<repo>/<name>.md` (single file) | `~/.hermes/skills/<name>/SKILL.md` |
| frontmatter `name:` + `description:` | same fields, same validator (name ≤64 chars, description ≤1024 chars) |
| `~/.claude/skills/<name>/SKILL.md` install target | `~/.hermes/skills/<name>/SKILL.md` |
| `/skill-name` direct invocation | "use <skill-name> on this" or natural trigger phrases |

The frontmatter is compatible as-is — do not rewrite it during import. Category directories (`~/.hermes/skills/<category>/<name>/SKILL.md`) are also valid if you want to organize, but flat install matches upstream layout and keeps updates diffable.

## Import Workflow

1. **Clone shallow** to /tmp: `git clone --depth 1 <repo> /tmp/<name>`. Completion: `ls` shows the skill files.
2. **Read README + install.sh before running anything.** Upstream install scripts target Claude Code paths (`~/.claude/skills/`) — do NOT run them. Replicate their loop against `~/.hermes/skills/`. The script tells you the intended file shape (which files are skills vs docs) and any post-install steps.
3. **Identify non-skill files.** README.md and similar docs are documentation, not skills — skip them (upstream install.sh usually shows the skip list).
4. **Dedupe check:** `ls ~/.hermes/skills/ | grep -E '<new names>'`. Existing skills with the same name are a decision point — default is skip-and-report, not silent overwrite.
5. **Install:** for each skill file, `mkdir -p ~/.hermes/skills/<name> && cp <file> ~/.hermes/skills/<name>/SKILL.md`. Completion: `ls ~/.hermes/skills/` shows every expected name.
6. **Verify registration:** `skills_list` — user-local skills are visible immediately in the same session (this differs from in-repo skills, which need a fresh session; do not confuse the two).
7. **Dependency audit.** Grep the installed SKILL.md files for runtime requirements the skills assume (playwright, python venvs, API keys, specific CLIs). For each gap, report the gap PLUS the fix command to the user — never report it as "tool X is broken". Example fix: `npm i -D playwright && npx playwright install chromium`.
8. **Report to the user:** which skills installed, grouped by what they're for, and how to invoke them in chat (natural triggers vs direct "use <skill-name>"). A bare "done" is not useful — the user needs the usage guide to get value.

## Pitfalls

1. **Running upstream install.sh directly.** It writes to `~/.claude/`, not `~/.hermes/` — a silent no-op for Hermes. Replicate its loop instead.
2. **Installing README/docs as skills.** Creates noise skills with no triggers. Check the upstream skip list.
3. **Assuming the current session can't see new user-local skills.** It can (via `skills_list`). The stale-loader pitfall applies to in-repo skills only.
4. **Skipping the dependency audit.** Many skills embed scripts requiring runtimes (node/playwright etc.). Verify with a quick `node -e "try{require('playwright');...}"` style probe before the user hits it.
5. **Overwriting existing skills on re-import.** Use `--force` semantics only when the user asks for an update.

## Verification Checklist

- [ ] Every skill file from the repo (minus docs) has a `~/.hermes/skills/<name>/SKILL.md`
- [ ] `skills_list` shows all newly installed names
- [ ] No pre-existing skill was overwritten without user intent
- [ ] Runtime dependencies audited; gaps reported with fix commands
- [ ] User got a categorized "which skills + how to use them in chat" summary

## See Also

- `references/` under this skill: inventory of packs imported so far, with per-skill dependency notes.