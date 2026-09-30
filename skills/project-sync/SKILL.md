---
name: project-sync
description: Generate project management summaries from Linear, high-priority emails, and Slack at different time horizons (daily, weekly, monthly, quarterly). Use when: (1) running scheduled project updates, (2) generating status reports, (3) Ben requests project sync or update, (4) at 8am GMT for automated summaries. Sends formatted summaries to Agentspace Slack.
---

# Project Sync

## Overview

This skill aggregates project data from multiple sources (Linear, email, Slack) and generates time-based summaries sent to Ben via Agentspace Slack. It supports four cadences with different time horizons:

- **Daily** (8am GMT): Review past 24-48 hours
- **Weekly** (8am GMT): Review past 7-14 days
- **Monthly** (8am GMT): Review past 30-60 days
- **Quarterly** (8am GMT): Review full quarter vs next quarter

## Data Sources

### 1. Linear (a previous employer)
- Recent issues, status changes, completions
- High-priority items and blockers
- Project milestones

### 2. High-Priority Emails
- Unread high-priority messages
- Important threads requiring action
- Client/stakeholder communications

### 3. Slack (a previous employer - Read-Only)
- Key decisions and discussions
- Team updates and announcements
- Important threads and mentions

**Important**: Never send messages to a previous employer Slack. Read-only access for context gathering only.

## Workflow

### Step 1: Determine Cadence and Time Range

Based on the request or schedule, identify:
- Cadence: daily, weekly, monthly, or quarterly
- Primary time range: 24h, 7d, 30d, or 90d
- Comparison time range: 48h, 14d, 60d, or next 90d

### Step 2: Fetch Data from All Sources

Use the bundled scripts to collect data:

```bash
# Linear data
python3 scripts/fetch_linear.py --days <N>

# High-priority emails
python3 scripts/fetch_emails.py --priority high --days <N>

# Slack messages (read-only from former-employer workspace)
python3 scripts/fetch_slack.py --workspace former-employer --days <N>
```

### Step 3: Synthesize the Summary

Format the summary with different "heights" based on cadence:

**Daily Summary Structure:**
```
📊 Daily Project Sync - [Date]

🎯 Key Highlights (24h)
- Top 3 completions
- Active blockers
- Urgent items

📈 Velocity Check (48h comparison)
- Issues closed: X (+/- Y from yesterday)
- New priorities added

💬 Team Context
- Key Slack discussions
- Important emails

⚡ Action Items
- What needs attention today
```

**Weekly Summary Structure:**
```
📊 Weekly Project Sync - Week of [Date]

🎯 Week in Review (7 days)
- Major milestones hit
- Projects progressed
- Blockers resolved

📈 Trend Analysis (14-day comparison)
- Velocity trends
- Priority shifts
- Resource allocation

💬 Team Momentum
- Key decisions made
- Cross-functional updates

🔮 Week Ahead
- Upcoming deadlines
- Planned releases
```

**Monthly Summary Structure:**
```
📊 Monthly Project Sync - [Month Year]

🎯 Month in Review (30 days)
- Strategic objectives achieved
- Product releases
- Major pivots or decisions

📈 Performance Metrics (60-day trend)
- Delivery velocity
- Priority distribution
- Team capacity

💬 Organizational Context
- Major announcements
- Strategic discussions

🔮 Month Ahead
- Quarterly goals check-in
- Upcoming initiatives
```

**Quarterly Summary Structure:**
```
📊 Quarterly Review - Q[N] [Year]

🎯 Quarter Achievements
- OKRs completed
- Major product launches
- Strategic wins

📈 Performance Analysis
- Quarter-over-quarter trends
- Resource efficiency
- Velocity evolution

💬 Leadership Context
- Major decisions and pivots
- Org changes
- Strategic direction shifts

🔮 Next Quarter Preview (Q[N+1])
- Planned OKRs
- Strategic bets
- Resource planning
```

### Step 4: Send to Agentspace

Send the formatted summary via Slack to the Agentspace workspace:

```bash
# Use the message tool with channel=slack, target=agentspace
message --action send --channel slack --target "<agentspace-channel-id>" --message "<formatted-summary>"
```

**Important**: The message should come from BRUCE (Agentspace app), not from a previous employer Slack.

## Scheduling

This skill should run via OpenClaw cron at **8am GMT** for each cadence:

- Daily: `0 8 * * *` (every day at 8am GMT)
- Weekly: `0 8 * * 1` (every Monday at 8am GMT)
- Monthly: `0 8 1 * *` (1st of month at 8am GMT)
- Quarterly: `0 8 1 1,4,7,10 *` (1st of Jan/Apr/Jul/Oct at 8am GMT)

## Configuration

See `references/config.md` for:
- Linear API token and workspace ID
- Email access configuration
- Slack workspace IDs and channel mappings
- Agentspace Slack channel ID

## Resources

### scripts/
- `fetch_linear.py` - Fetch Linear issues and updates
- `fetch_emails.py` - Fetch high-priority emails
- `fetch_slack.py` - Fetch Slack messages (read-only)

### references/
- `config.md` - API tokens and configuration
