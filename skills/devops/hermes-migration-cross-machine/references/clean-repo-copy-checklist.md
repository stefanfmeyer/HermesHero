# Clean Repo Copy Checklist

Step-by-step checklist for creating a sanitized copy of a Hermes agent repo for a new agent instance. Verified Aug 2026 when creating the Pragmatic agent (a devops-focused agent deployed to the company servers) from the the agent repo.

## Pre-Flight

- [ ] Verify target GitHub repo exists (or create it)
- [ ] Confirm SSH key + host alias for the target GitHub account
- [ ] Check source repo structure: `ls -la`, `find . -maxdepth 2 -type d`

## Copy

- [ ] `rsync -a --exclude='.git' <source>/ <temp>/` — no history, just files
- [ ] Verify copy size is reasonable (skills should be <20MB without node_modules)

## Strip Sessions

- [ ] `rm -f sessions/*.jsonl sessions/*.json`
- [ ] `rm -f sessions/.session_*.tmp` — hidden temp files survive glob rm
- [ ] Verify `ls sessions/` is empty

## Strip Personal Memories

- [ ] Remove `memories/MEMORY.md`, `memories/USER.md`, all `memories/YYYY-MM-DD*.md`
- [ ] Remove `memories/*.db`, `memories/*.db-wal`, `memories/*.db-shm`
- [ ] Remove `memories/*.lock`, `memories/.DS_Store`
- [ ] Remove any `memories/openclaw_backup/` or other personal dirs
- [ ] Create blank template `memories/MEMORY.md` and `memories/USER.md` with comments

## Curate Skills

- [ ] Remove `.curator_backups/`, `.archive/`, `.hub/` directories
- [ ] Remove ALL `node_modules/` — `find . -name "node_modules" -type d -prune -exec rm -rf {} +`
- [ ] Remove ALL `__pycache__/` — `find . -name "__pycache__" -type d -prune -exec rm -rf {} +`
- [ ] Remove `.DS_Store` files — `find . -name ".DS_Store" -delete`
- [ ] Remove skills irrelevant to the new agent's purpose (e.g. SEO, trading, personal business ops)
- [ ] Remove project-specific skills that reference internal architecture, hostnames, IPs
- [ ] Remove personal devops skills tied to specific hardware/infra

## Remove Data Caches

- [ ] Remove `trading*/cache/` or similar API response caches
- [ ] Remove any `cache/` directories inside skills
- [ ] Check for large files: `find . -type f -size +1M -exec ls -lh {} \;`

## Scan for Leaked Secrets

- [ ] Grep for API key patterns: `sk-[a-zA-Z0-9_]{40,}`, `xox[baprs]-[A-Za-z0-9-]{20,}`, `AKIA[0-9A-Z]{16}`, `gh[pousr]_[A-Za-z0-9]{36,}`, `AIza[0-9A-Za-z_-]{35}`
- [ ] Grep for source agent's actual API keys, tokens (check config.yaml for what to look for)
- [ ] Grep for `.env` files: `find . -name ".env" -o -name ".env.*"`
- [ ] Grep for private keys: `grep -rn "BEGIN PRIVATE\|BEGIN RSA\|BEGIN OPENSSH"`
- [ ] Filter out placeholder secrets (`sk-xxx`, `xoxp-xxxxx`, `lin_api_REDACTED`)

## Scan for Personal References

- [ ] Grep for hostnames: `the workstation`, `workstation`, `phillies2008`
- [ ] Grep for IPs: `100.x.y.z`, `100.x.y.z`, any Tailscale IPs
- [ ] Grep for emails: `<yourname>@`, `<yourname>@gmail`, `<yourname>@former-employer`
- [ ] Grep for SSH key names: `id_ed25519_personal`
- [ ] Grep for GitHub usernames: `yourusername`
- [ ] Genericize every match with sed or manual edits

## Genericize Scripts

- [ ] Replace `/home/<user>` with `$HOME` in all `.sh` and `.py`
- [ ] Replace hardcoded SSH key paths with `${GIT_SSH_KEY:-$HOME/.ssh/id_ed25519}`
- [ ] Replace personal git identity with `${GIT_USER_NAME:-...}` / `${GIT_USER_EMAIL:-...}`
- [ ] Replace machine names with generic terms ("your host", "the server")
- [ ] Replace Tailscale IPs with `your-tailscale-ip`
- [ ] Remove references to specific RAM amounts, disk sizes, hardware models

## Genericize Skills

- [ ] Check github skills for personal account names, emails, SSH key configs
- [ ] Check devops skills for personal hostnames, paths, infra details
- [ ] Check memory skills for personal profile templates
- [ ] Check email/messaging skills for personal email addresses
- [ ] Check creative/research skills for personal project references

## Final Verification

- [ ] Re-run ALL grep scans — should return zero matches
- [ ] Check `du -sh` — repo should be <20MB
- [ ] Verify `sessions/` is empty
- [ ] Verify `memories/` only has template files
- [ ] Verify scripts have no hardcoded paths
- [ ] Count skills and confirm relevant ones remain

## Commit and Push

- [ ] `git init` in the temp directory
- [ ] `git branch -m main`
- [ ] `git config user.name` and `user.email` for the TARGET account
- [ ] `git remote add origin git@github.com-<alias>:<account>/<repo>.git`
- [ ] `git add -A`
- [ ] Verify staged files: `git diff --cached --name-only | wc -l`
- [ ] Check for any remaining sensitive files in staging
- [ ] `git commit -m "Initial commit: <agent name> ..."`
- [ ] `GIT_SSH_COMMAND="ssh -i <key>" git push -u origin main`
- [ ] Verify push succeeded

## Additional Pitfalls (Aug 2026 Pragmatic creation)

- **Git-crypt encrypted artifacts** — Files like `_meta.json`, `__init__.py`, and `@graphql-typed-document-node/` may be git-crypt encrypted binary garbage. They show up as `\x00GITCRYPT\x00...` when read. Remove them — they serve no purpose in the new repo.
- **`.gitignore` can exclude template memory files** — The source repo's `.gitignore` had `MEMORY.md` at the end, which prevented the template `memories/MEMORY.md` from being committed. Check `.gitignore` for `MEMORY.md`, `USER.md`, `SOUL.md` entries and remove them if you want the templates in the repo.
- **Personal references in skill DESCRIPTION.md files** — Category-level `DESCRIPTION.md` files (e.g. `skills/productivity/DESCRIPTION.md`) and `skills/README.md` often reference the source agent's name and personal skill list. Remove or genericize these.
- **Personal references in hindsight profile templates** — `skills/memory/hindsight-integration/references/profile-template.md` contained real user names, emails, employer details, partner names, and project specifics. Genericize ALL personal data in reference files, not just SKILL.md files.
- **Script comments reference the source platform** — `health-check.sh` said "sends output to Discord" and `storage-manager.sh` said "sends storage summary to Discord". When the new agent uses Slack, scan ALL script comments for platform references and update them.
- **Skill README.md from source agent** — `skills/README.md` referenced the source agent's name (the agent) and listed personal skills (SEO, trading, etc.). Remove it — the new repo's top-level README is the authoritative description.
- **Personal names in code examples** — `github-pr-workflow/SKILL.md` had `git config user.name "Your Name"` and `cron-patterns/SKILL.md` had `${HERMES_GIT_NAME:-Your Name}`. Scan ALL skill files for personal names in code examples and genericize them.
- **Trading/personal project references in dev skills** — `nextjs-development-patterns/SKILL.md` referenced "Your Name's t212-intelligence style dashboards" and `~/t212-intelligence` paths. Scan development skills for personal project names and paths.
- **User ID references in messaging skills** — `slack-channel-resolution-fix/SKILL.md` had real Slack user IDs mapped to real names (e.g. "U0ALJ30JGLC = Sean O'Connor"). Genericize ALL user ID → name mappings.
- **Second pass pruning** — After initial skill pruning, re-scan remaining skills for personal references. The first pass removes entire skill directories; the second pass cleans files inside kept skills. Both passes are necessary.

## Numbers from the Pragmatic creation (Aug 2026)

- Source: the agent repo (7,711 session files, 94 skill dirs, 1.2GB)
- Initial result: 37 skill dirs, 721 files, ~10MB
- Skills removed: 57 (SEO, trading, personal business, project-specific)
- **Second pass (Aug 14):** Pruned 20+ more non-coding skill categories (creative, media, mlops, research, email, voice-chat, presentation, design, computer-use, data-science, red-teaming, seo, project-sync, hermes-desktop-plugins, hermes-themes). Down to 11 top-level skill directories.
- Productivity sub-skills pruned: kept only linear, notion, docx, pdf, xlsx (removed airtable, google-workspace, maps, powerpoint, etc.)
- Messaging sub-skills pruned: kept only slack-channel-resolution-fix (removed discord-connection-troubleshooting, piper-tts)
- Secrets found: 0 (all clean after genericization)
- Personal references found and cleaned: ~30+ files across github, devops, memory, messaging, developer, operations, software-development skills
- Git-crypt artifacts removed: 3 (_meta.json, __init__.py, @graphql-typed-document-node/)
- Script platform references fixed: 2 (health-check.sh, storage-manager.sh — Discord → Slack)
- .gitignore fixed: removed MEMORY.md exclusion so template gets committed