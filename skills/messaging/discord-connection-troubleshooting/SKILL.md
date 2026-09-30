---
name: discord-connection-troubleshooting
description: Diagnose and fix Discord bot connection issues - verify token, check bot is in server, construct OAuth URL manually.
version: 1.0.0
tags: [discord, hermes, troubleshooting, oauth]
---

# Discord Connection Troubleshooting

## Quick Diagnosis

### 0. Check If Gateway Is Running (CRITICAL — CLI agent ≠ gateway!)
```bash
# WRONG: ps aux | grep hermes shows the CLI agent, NOT the gateway
# The CLI agent (hermes --resume session_id) runs as YOUR user on a pseudoterminal (s000+)
# The gateway runs under launchd as a different parent process
ps aux | grep -i "hermes\|gateway" | grep -v grep
# Correct check: look for Discord websocket activity
lsof -i -P | grep -i "discord\|webhook" | head -5
# Also check: launchctl list | grep hermes
```

### 1. Verify Bot Token is Valid
curl -s -H "Authorization: Bot YOUR_TOKEN" https://discord.com/api/v10/users/@me

Should return JSON with bot username. If error, token is invalid.

### 2. Check if Bot is in Any Servers
curl -s -H "Authorization: Bot YOUR_TOKEN" https://discord.com/api/v10/users/@me/guilds

- [] = bot NOT in any server (most common issue)
- Returns array of guilds if added somewhere

### 3. Check Gateway Loading Token
ps eww $(pgrep -f "hermes gateway") | grep DISCORD

## Stale PID File / Launchd Race (Gateway Won't Restart)
### Stale PID File / Launchd Race (Gateway Won't Restart)

Symptom: `ERROR gateway.run: PID file race lost to another gateway instance. Exiting.` repeatedly in `gateway.error.log`, gateway won't stay up.

Cause: `gateway.pid` has an old stale PID (e.g., from days ago). Launchd KeepAlive keeps trying to restart with `--replace` flag but each new instance immediately exits because the PID file already claims that PID is in use. Even `hermes gateway restart` can fail to resolve this when both `gateway.pid` AND `gateway_state.json` are stale.

Diagnosis:
```bash
# Check gateway_state.json — if "gateway_state": "draining" with old timestamp, it's deadlocked
cat ~/.hermes/gateway_state.json

# Confirm PID is actually dead
kill -0 $(cat ~/.hermes/gateway.pid)  # "Exited: 1" = PID is dead
```

Fix — complete cleanup in order:
```bash
# 1. Confirm the PID in gateway.pid is dead
kill -0 $(cat ~/.hermes/gateway.pid) 2>/dev/null && echo "ALIVE" || echo "DEAD — safe to clear"

# 2. Clear BOTH gateway_state.json and gateway.pid
echo '{"pid": null, "gateway_state": "stopped", "active_agents": 0}' > ~/.hermes/gateway_state.json
rm ~/.hermes/gateway.pid

# 3. Restart via launchctl
launchctl unload ~/Library/LaunchAgents/ai.hermes.gateway.plist
sleep 2
launchctl load ~/Library/LaunchAgents/ai.hermes.gateway.plist

# 4. Verify
sleep 6
ps aux | grep "hermes.*gateway.*run" | grep -v grep
cat ~/.hermes/gateway_state.json  # should show new PID + "connected"
```

Note: `hermes gateway restart` alone won't fix this when both files are stale — must manually clear them first. The launchd plist uses `--replace` flag which requires a clean state to start fresh.

### Stale Discord Thread References (404 Unknown Channel)
Symptom: Cron jobs fail with `Discord API error (404): Unknown Channel` but bot token is valid.

Cause: `discord_threads.json` and `channel_directory.json` contain references to Discord threads that were deleted in Discord.

Fix:
```bash
# Remove stale thread from discord_threads.json
python3 -c "
import json
with open('~/.hermes/discord_threads.json') as f:
    threads = json.load(f)
# Filter out the known-bad thread ID
cleaned = [t for t in threads if t != 'BAD_THREAD_ID']
with open('~/.hermes/discord_threads.json', 'w') as f:
    json.dump(cleaned, f)
print(f'Removed {len(threads)-len(cleaned)} thread(s)')
"

# Remove stale entry from channel_directory.json
python3 -c "
import json
with open('~/.hermes/channel_directory.json') as f:
    d = json.load(f)
discord = d.get('platforms', {}).get('discord', [])
original = len(discord)
discord = [x for x in discord if x.get('thread_id') != 'BAD_THREAD_ID']
with open('~/.hermes/channel_directory.json', 'w') as f:
    json.dump(d, f, indent=2)
print(f'Removed {original - len(discord)} channel entries')
"
```

## Adding Bot to Server

If guilds returns [], bot needs to be added via OAuth.

### Manual OAuth URL

If Discord portal URL generator fails, construct manually:

```
https://discord.com/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=PERMISSIONS&scope=bot
```

Find Client ID: Discord Developer Portal → OAuth2 → General

Permission values:
- 1024 = Basic (Read/Send Messages, Embed Links)
- 2048 = Plus Reactions
-  proc_517024 = Administrator

## Gateway Config

DISCORD_BOT_TOKEN environment variable must be set before starting gateway.

Restart after adding: hermes gateway restart

## Required Permissions

Minimum: Read Messages, Send Messages, Embed Links, Use Slash Commands

## REST API vs Gateway Token Usage

A Discord bot can be **connected and receiving messages** via gateway (websocket) while its **REST API token returns 401** for direct API calls.

Symptoms:
- `curl ... https://discord.com/api/v10/users/@me` → 401 Unauthorized
- But gateway is running and processing incoming messages fine
- the agent receives and responds to Discord messages correctly

This means the token is valid for the gateway's internal Discord WebSocket connection but not for raw REST API calls from external tools.

**Channel posting failures (401) when gateway works:**
- Cron jobs that `POST /channels/{channel_id}/messages` return 401
- But the bot receives @mentions and responds correctly
- Root cause: the bot is in the server but **lacks permission to post in that specific channel** (channel overwrite/permissions), OR the channel belongs to a server the bot is not a member of
- Fix: add bot to the server with Send Messages permission in that channel

If you must call Discord REST API directly and get 401:
1. Token may be truncated/masked in `.env` display — extract it programmatically, not from terminal echo
2. Token may have been reset in Discord Developer Portal — regenerate it
3. Check `~/.hermes/logs/gateway.error.log` for Discord errors (websocket errors differ from REST errors)
4. Verify bot is in the same server as the target channel — use `GET /users/@me/guilds` to list guilds the bot is in
5. Verify channel permissions: bot needs "Send Messages" in the channel's overwrite settings

## Logs

tail -f ~/.hermes/logs/gateway.error.log
