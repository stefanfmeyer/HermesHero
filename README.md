# HermesHero

A complete, portable **Hermes Agent system** — skill library, Hindsight memory setup, scripts, and systemd service — packaged for transfer to a new machine. No personal data: no memories, no sessions, no API keys.

Built on [Hermes Agent](https://github.com/NousResearch/hermes-agent) by Nous Research.

## What's in here

| Path | What it is |
|------|------------|
| `skills/` | The full skill library (~90 skills: dev, devops, automation, memory, research, creative, SEO, productivity, mlops, gaming, messaging) |
| `hindsight/` | Hindsight long-term memory: config template + full setup guide |
| `scripts/` | Operational scripts: hindsight supervisor/keepalive/ingest, health check, dev reaper, storage manager |
| `systemd/` | `hindsight-embed.service` — 24/7 supervisor unit for the Hindsight daemon |
| `config.yaml.example` | Reference Hermes config (all keys redacted) |
| `.env.example` | Reference environment variables (all values redacted) |

## Setup Guide (for Claude or any agent)

The colleague should point Claude at `SETUP.md` — it walks through everything in order: install Hermes, deploy skills, install and configure Hindsight, install scripts + systemd service, configure providers, verify.

**Start here: [SETUP.md](SETUP.md)**

## What is deliberately NOT included

- `~/.hermes/memories/` — personal memory files (confidential)
- `~/.hermes/sessions/`, `state.db` — conversation transcripts (confidential)
- `~/.hermes/.env`, `auth.json` — API keys and tokens
- `~/.hermes/hindsight/config.json` — real config contains an API key (template only)
- Hindsight memory database (`~/.hindsight/`, `~/.pg0/`) — contains everything the agent has ever learned about its user
- Cron jobs, gateway state, pairing data

## Key components

### Hindsight memory system
Hindsight adds persistent long-term memory (fact extraction, semantic recall, consolidation) backed by an embedded PostgreSQL. The daemon runs 24/7 under a systemd supervisor with a three-layer watchdog: systemd unit → keepalive script → cron pre-flight health check. Setup: `hindsight/SETUP.md`.

### Skill system
Skills live in `~/.hermes/skills/`. Hermes auto-discovers them and loads them on demand. Skills are the agent's procedural memory: workflows, pitfalls, verified commands. Copy the whole `skills/` tree — subdirectory names (devops, memory, automation...) are organizational only.

### Supervisor scripts
`scripts/hindsight-supervisor.sh` restarts the daemon if it dies; `scripts/hindsight-keepalive.sh` is the standalone fallback; `scripts/hindsight_daily_ingest.py` retains facts from daily sessions into Hindsight every 15 minutes (wire it as a Hermes cron job — see SETUP.md).
