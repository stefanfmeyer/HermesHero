# Project Sync Configuration

## Required Credentials

### Linear API
- **Token**: Get from Linear Settings → API → Personal API keys
- **Workspace**: `former-employer`

Set as environment variables:
```bash
export LINEAR_API_TOKEN="lin_api_REDACTED"
export LINEAR_WORKSPACE_ID="former-employer"
```

Or create a JSON config file at `~/.config/project-sync/config.json`:
```json
{
  "linear_api_token": "lin_api_REDACTED",
  "linear_workspace_id": "former-employer"
}
```

### Email Access
Currently supports Himalaya CLI for IMAP/SMTP access.

Install: `brew install himalaya` or see https://github.com/soywod/himalaya

Configure himalaya with your email account:
```bash
himalaya accounts add
```

Set environment variable:
```bash
export EMAIL_METHOD="himalaya"
export EMAIL_ACCOUNT="default"
```

### Slack (a previous employer Workspace - Read-Only)
- **User Token**: OAuth token with `channels:history`, `channels:read` scopes
- **Channels to monitor**: `["general", "operations", "engineering"]`

⚠️ **IMPORTANT**: This token is READ-ONLY. Never use it to send messages.

Set as environment variable:
```bash
export SLACK_USER_TOKEN="xoxp-xxxxx"
```

Or add to config JSON:
```json
{
  "slack_user_token": "xoxp-xxxxx",
  "slack_channels": ["general", "operations", "engineering"]
}
```

### Agentspace Slack (Output Destination)
This is where summaries are sent. OpenClaw handles this via the configured Slack integration.

- **Workspace**: Agentspace
- **Sender**: BRUCE bot
- **Target**: Ben's DM or designated channel

Get the target channel/user ID:
```bash
openclaw config get channels.slack
```

## Scheduling

### Via OpenClaw Cron

Set up cron jobs for each cadence:

**Daily (8am GMT = 0800 UTC):**
```bash
openclaw cron add "project-sync-daily" \
  --schedule "0 8 * * *" \
  --task "Run the project-sync skill for daily cadence" \
  --thinking low
```

**Weekly (Mondays 8am GMT):**
```bash
openclaw cron add "project-sync-weekly" \
  --schedule "0 8 * * 1" \
  --task "Run the project-sync skill for weekly cadence" \
  --thinking low
```

**Monthly (1st of month 8am GMT):**
```bash
openclaw cron add "project-sync-monthly" \
  --schedule "0 8 1 * *" \
  --task "Run the project-sync skill for monthly cadence" \
  --thinking low
```

**Quarterly (1st of Jan/Apr/Jul/Oct 8am GMT):**
```bash
openclaw cron add "project-sync-quarterly" \
  --schedule "0 8 1 1,4,7,10 *" \
  --task "Run the project-sync skill for quarterly cadence" \
  --thinking low
```

## Testing

Test each script individually:

```bash
# Test Linear fetch (past 7 days)
python3 scripts/fetch_linear.py --days 7

# Test email fetch
python3 scripts/fetch_emails.py --priority high --days 7

# Test Slack fetch (read-only)
python3 scripts/fetch_slack.py --workspace former-employer --days 7
```

Test full summary generation:
```bash
# Ask Bruce to generate a daily summary
openclaw chat "Generate a daily project sync summary"
```

## Channel IDs Reference

Once configured, document your specific IDs here:

```
Linear Workspace ID: [TODO]
Agentspace Slack Channel ID: [TODO]
a previous employer Slack Workspace ID: [TODO]
```

## Troubleshooting

### Linear API Issues
- Verify token has read access to issues
- Check workspace ID is correct
- Ensure API rate limits aren't exceeded

### Email Issues
- Verify himalaya is installed: `which himalaya`
- Test himalaya independently: `himalaya list`
- Check IMAP/SMTP credentials

### Slack Issues
- Verify token scopes include `channels:history` and `channels:read`
- Test token: `curl -H "Authorization: Bearer $SLACK_USER_TOKEN" https://slack.com/api/auth.test`
- Check channel IDs are correct
- **Never send messages to a previous employer Slack - read-only!**

### Scheduling Issues
- Check cron jobs: `openclaw cron list`
- Verify timezone: 8am GMT = 0800 UTC
- Check logs: `openclaw logs --follow`
