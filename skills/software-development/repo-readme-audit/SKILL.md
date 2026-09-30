---
name: repo-readme-audit
description: "Audit a repo's README against actual filesystem, config, and runtime state. Correct discrepancies, commit, and push. Use when asked to verify a README is correct, update docs to match reality, or review a repo's documentation accuracy."
version: 1.0.0
author: Hermes Agent
metadata:
  hermes:
    tags: [README, documentation, audit, git, repo]
    related_skills: [github-repo-management]
---

# Repo README Audit

## When to Use
- User asks to verify a README is correct
- User asks to ensure README details the correct architecture
- User asks to review/update repo documentation
- After significant infra changes (host migration, framework rename, memory system swap)

## Methodology

### 1. Read the Current README
```bash
read_file(path="/path/to/repo/README.md")
```
Note every factual claim: framework name, host hardware, model names, skill counts, cron schedules, platform connections, directory structure.

### 2. List Actual Repo Contents
```bash
# Top-level structure
find /path/to/repo -maxdepth 2 -not -path '*/.git/*' -not -path '*/node_modules/*' | sort

# Skill/module count — count SKILL.md files, NOT directories
# (directories can exist without SKILL.md, and nested skills are missed by ls -d)
find skills/ -name "SKILL.md" | wc -l
find skills/ -name "SKILL.md" | sort

# Per-category breakdown
find skills/ -name "SKILL.md" | sed 's|skills/||;s|/SKILL.md||' | cut -d/ -f1 | sort | uniq -c
```

### 3. Verify Each README Claim Against Reality

**Skills/modules — bidirectional check:**
1. Forward: for each skill the README lists, verify it exists:
```bash
for s in skill1 skill2 skill3; do
  [ -d "skills/$s" ] && echo "EXISTS: $s" || echo "MISSING: $s"
done
```
2. Reverse: for each skill that actually exists, check if the README mentions it. This catches skills that EXIST but are omitted from the README (the most common drift pattern for growing repos):
```bash
find skills/ -name "SKILL.md" | sed 's|skills/||;s|/SKILL.md||' | while read s; do
  grep -q "$s" README.md || echo "UNDOCUMENTED: $s"
done
```

**Script descriptions:** Read each script's header/header docstring to verify the README's description matches what the script actually does:
```bash
head -20 scripts/some_script.sh   # or .py
```
READMEs often describe what a script was INTENDED to do, not what it currently does.

**Config:** Read the actual config file (if accessible):
```bash
cat ~/.hermes/config.yaml | head -80
```

**Cron jobs:** Parse the actual cron definitions:
```bash
cat ~/.hermes/cron/jobs.json | python3 -c "
import json, sys
for j in json.load(sys.stdin)['jobs']:
    print(f\"{j['schedule_display']:20} {j['name']:40} enabled={j['enabled']}\")"
```

**Memory/runtime systems:** Check what's actually running:
```bash
curl -s http://localhost:9177/health    # Hindsight
ps aux | grep hindsight                   # daemon processes
```

**Git identity:** Confirm the repo's git config:
```bash
cd /path/to/repo && git config user.name && git config user.email && git remote -v
```

**Memory files:** Read actual memory files to verify descriptions match:
```bash
cat memories/MEMORY.md
cat memories/USER.md
```

### 4. Document Discrepancies
List every mismatch between README claims and actual state. Common drift patterns:
- Framework/product renamed since README was written
- Host hardware changed (e.g., Mac mini → Linux server)
- Memory system replaced (e.g., OpenViking → Hindsight)
- Skills added/removed but README count not updated
- Cron schedules changed but README not updated
- Platforms connected/disconnected but README still lists old state
- Directory structure in README doesn't match actual layout

### 5. Rewrite README
- Only include verified facts from step 2-3
- Remove non-existent skills/modules from listings
- Update counts, schedules, paths to match actual state
- Keep the structure/sections from the old README where still accurate
- Use the correct framework name, host name, and model names

### 6. Commit and Push
```bash
cd /path/to/repo
git config user.name "correct-identity"
git config user.email "correct-email@example.com"
git add README.md
git commit -m "Update README with correct architecture and details

- List key corrections (what was wrong → what's right)
- Include counts of items removed/updated"
git push origin main
```

## Pitfalls

1. **Don't trust the README** — it was written at a point in time and drifts. Every claim must be verified against the actual filesystem/config/runtime.

2. **Phantom skills** — READMEs often list skills that were planned, renamed, or removed. Always `[ -d "skills/$s" ]` check each one.

3. **Undocumented skills (reverse drift)** — the MOST common drift pattern for growing repos: skills were added but the README never updated. Always run the reverse check (find skills that exist but aren't mentioned in the README). In the Pragmatic audit (2026-08-17), 10 of 17 software-development skills existed on disk but were completely absent from the README's skills table.

4. **Wrong framework name** — products get renamed (OpenClaw → Hermes Agent). Check the actual config and docs URL for the current name.

5. **Stale cron schedules** — cron jobs get added/removed/modified. Parse the actual `jobs.json` rather than trusting the README table.

6. **Directory structure mismatch** — READMEs often show idealized or outdated directory trees. Run `find` to see what's actually there.

7. **Git identity matters** — repos belonging to different accounts need different `user.name`/`user.email`. Always verify which identity the repo should use before committing. See `github-multi-account-ssh` skill.

8. **Config files are gitignored** — don't accidentally stage `config.yaml` or `.env` when pushing README updates. Check `.gitignore` first.

9. **Runtime-only directories listed as repo content** — directories like `sessions/` may be gitignored and created at deploy time but still appear in the README's structure tree. Cross-reference every path in the tree against `.gitignore` and the actual filesystem. If a directory is gitignored, note it as "runtime-only, gitignored" in the tree.

10. **Script descriptions drift from actual behavior** — READMEs describe what a script was INTENDED to do, not what it currently does. Read each script's header/docstring and verify the description matches. In the Pragmatic audit, `hindsight_daily_ingest.py` was described as "Daily Hindsight session embedding" but actually reads from SQLite `state.db`, extracts facts via LLM, and retains to the Hindsight API.

11. **Count SKILL.md files, not directories** — `ls -d skills/*/` misses nested skills (e.g., `skills/software-development/subagent-driven-development/SKILL.md`) and counts empty directories. Always use `find skills/ -name "SKILL.md" | wc -l` for the real count.

## References

- `references/pragmatic-repo-audit.md` — Pragmatic README audit (2026-08-17): 10 undocumented skills found via reverse check, script description drift, runtime-only directory listed as repo content.