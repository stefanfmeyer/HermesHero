# Zapier Webhook Skill

**Purpose:** Send structured data to Zapier for multi-service automation (Linear, Google Calendar, Slack, etc.)

**Webhook URL:** `https://hooks.zapier.com/hooks/catch/26594046/u02e6wi/`

**Integration:** Zero-config. Use `exec` tool with curl or HTTP libraries.

---

## Configuration

**Option 1: Environment Variable (Recommended)**

Add to `~/.openclaw/openclaw.json`:
```json
{
  "env": {
    "ZAPIER_WEBHOOK_URL": "https://hooks.zapier.com/hooks/catch/26594046/u02e6wi/"
  }
}
```

**Option 2: Direct Use**

Use the URL directly in curl commands (for testing/one-offs).

---

## Common Workflows

### 1. Create Linear Issue

```bash
curl -X POST "$ZAPIER_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow": "create_issue",
    "issue": {
      "title": "Build authentication system",
      "description": "Implement OAuth2 with Google + GitHub providers",
      "priority": "high",
      "labels": ["backend", "security"],
      "assignee": "yourname",
      "project": "Q1 2026"
    }
  }'
```

**Zapier Mapping:**
- Action: **Linear → Create Issue**
- Map fields: `issue.title`, `issue.description`, `issue.priority`, etc.

---

### 2. Create Calendar Event

```bash
curl -X POST "$ZAPIER_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow": "create_event",
    "event": {
      "summary": "Review architecture proposals",
      "description": "Compare microservices vs monolith for AI pipeline",
      "start": "2026-02-27T14:00:00Z",
      "end": "2026-02-27T15:30:00Z",
      "attendees": ["you@example.com"],
      "location": "Zoom"
    }
  }'
```

**Zapier Mapping:**
- Action: **Google Calendar → Create Detailed Event**
- Map fields: `event.summary`, `event.start`, `event.end`, etc.

---

### 3. Combined: Issue + Calendar Event

```bash
curl -X POST "$ZAPIER_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow": "issue_and_event",
    "issue": {
      "title": "Research n8n automation patterns",
      "description": "Evaluate n8n vs Zapier for complex workflows",
      "priority": "medium",
      "labels": ["research", "automation"]
    },
    "event": {
      "summary": "Research session: n8n evaluation",
      "start": "2026-02-28T10:00:00Z",
      "end": "2026-02-28T12:00:00Z",
      "description": "Deep dive into n8n capabilities and integration patterns"
    }
  }'
```

**Zapier Setup:**
- Use **Paths** or **Filter** to route based on `workflow` field
- Path 1: If `workflow == "issue_and_event"` → Create Issue + Create Event
- Path 2: If `workflow == "create_issue"` → Create Issue only
- Path 3: If `workflow == "create_event"` → Create Event only

---

### 4. Slack Notification

```bash
curl -X POST "$ZAPIER_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow": "slack_notification",
    "message": {
      "channel": "#dev-updates",
      "text": "✅ Deployment complete: AI content pipeline v2.1",
      "blocks": [
        {
          "type": "section",
          "text": {
            "type": "mrkdwn",
            "text": "*Deployment Summary*\n• Version: 2.1\n• Status: Success\n• Deploy time: 3m 42s"
          }
        }
      ]
    }
  }'
```

**Zapier Mapping:**
- Action: **Slack → Send Channel Message**
- Map fields: `message.channel`, `message.text`

---

## Usage from OpenClaw

### Method 1: Direct exec (Quick)

```bash
exec curl -X POST "$ZAPIER_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{"workflow": "create_issue", "issue": {"title": "Test", "priority": "low"}}'
```

### Method 2: Python Script (Structured)

Create `skills/zapier-webhook/send.py`:
```python
#!/usr/bin/env python3
import os
import sys
import json
import requests

WEBHOOK_URL = os.getenv("ZAPIER_WEBHOOK_URL")

def send_to_zapier(payload):
    response = requests.post(
        WEBHOOK_URL,
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    return response.status_code, response.text

if __name__ == "__main__":
    payload = json.loads(sys.argv[1])
    status, text = send_to_zapier(payload)
    print(f"Status: {status}")
    print(f"Response: {text}")
```

**Usage:**
```bash
exec python3 skills/zapier-webhook/send.py '{"workflow": "create_issue", "issue": {...}}'
```

---

## Payload Schemas

### Create Issue Schema

```json
{
  "workflow": "create_issue",
  "issue": {
    "title": "string (required)",
    "description": "string (optional)",
    "priority": "low|medium|high|urgent (optional)",
    "labels": ["string", "..."] (optional),
    "assignee": "string (optional)",
    "project": "string (optional)",
    "dueDate": "ISO 8601 date (optional)"
  }
}
```

### Create Event Schema

```json
{
  "workflow": "create_event",
  "event": {
    "summary": "string (required)",
    "description": "string (optional)",
    "start": "ISO 8601 datetime (required)",
    "end": "ISO 8601 datetime (required)",
    "attendees": ["email@example.com", "..."] (optional),
    "location": "string (optional)",
    "reminders": {
      "useDefault": false,
      "overrides": [
        {"method": "email", "minutes": 1440},
        {"method": "popup", "minutes": 30}
      ]
    } (optional)
  }
}
```

### Combined Schema

```json
{
  "workflow": "issue_and_event",
  "issue": { /* same as Create Issue */ },
  "event": { /* same as Create Event */ }
}
```

---

## Zapier Zap Configuration

**Trigger:**
- **Webhooks by Zapier** → Catch Hook
- Test with sample payload to populate fields

**Actions (based on workflow type):**

**For "create_issue":**
1. **Filter:** Only continue if `workflow` = "create_issue"
2. **Linear:** Create Issue
   - Title: `{{issue__title}}`
   - Description: `{{issue__description}}`
   - Priority: `{{issue__priority}}`
   - Labels: `{{issue__labels}}`

**For "create_event":**
1. **Filter:** Only continue if `workflow` = "create_event"
2. **Google Calendar:** Create Detailed Event
   - Summary: `{{event__summary}}`
   - Start DateTime: `{{event__start}}`
   - End DateTime: `{{event__end}}`
   - Description: `{{event__description}}`

**For "issue_and_event":**
1. **Filter:** Only continue if `workflow` = "issue_and_event"
2. **Linear:** Create Issue (same mapping)
3. **Google Calendar:** Create Detailed Event (same mapping)

**For "slack_notification":**
1. **Filter:** Only continue if `workflow` = "slack_notification"
2. **Slack:** Send Channel Message
   - Channel: `{{message__channel}}`
   - Message Text: `{{message__text}}`

---

## Workflow Triggers (Auto-Activation)

**When the user says:**
- "Create a Linear issue for..."
- "Schedule a meeting to..."
- "Add to calendar..."
- "Remind me to..."
- "Track this in Linear..."

**OpenStef will:**
1. Detect intent (issue creation, event scheduling, combined)
2. Format appropriate payload
3. Send to Zapier webhook
4. Confirm action taken

---

## Testing

**Test webhook is working:**
```bash
curl -X POST "https://hooks.zapier.com/hooks/catch/26594046/u02e6wi/" \
  -H "Content-Type: application/json" \
  -d '{"test": true, "message": "OpenClaw test payload"}'
```

**Check in Zapier:**
- Go to Zap → Trigger → "Test trigger"
- Should see the payload received

---

## Security Notes

⚠️ **Webhook URL is SENSITIVE** — Treat like an API key:
- Anyone with this URL can trigger your Zaps
- Don't commit to public repos
- Rotate if exposed (Zapier → Settings → Regenerate Webhook URL)

✅ **Stored securely in:**
- `~/.openclaw/openclaw.json` (local config, git-ignored)
- Environment variable: `ZAPIER_WEBHOOK_URL`

---

## Error Handling

**Zapier will:**
- Return `200 OK` if webhook received (even if actions fail)
- Retry failed actions automatically
- Send email on repeated failures

**OpenClaw should:**
- Check HTTP status code (200 = received)
- Log payload for debugging
- Don't retry on 200 (Zapier handles it)

---

## Examples for Common Tasks

### Example 1: Create issue from conversation

**the user:** "Track this: Research AI video generation models (Sora, Runway, Pika)"

**OpenStef:**
```bash
exec curl -X POST "$ZAPIER_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow": "create_issue",
    "issue": {
      "title": "Research AI video generation models",
      "description": "Compare Sora, Runway, and Pika for content production use cases",
      "priority": "medium",
      "labels": ["research", "ai", "video"]
    }
  }'
```

**Zapier:** Creates Linear issue automatically

---

### Example 2: Schedule review meeting

**the user:** "Schedule 1-hour architecture review for Friday 2pm"

**OpenStef:**
```bash
exec curl -X POST "$ZAPIER_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow": "create_event",
    "event": {
      "summary": "Architecture Review",
      "start": "2026-02-28T14:00:00Z",
      "end": "2026-02-28T15:00:00Z",
      "description": "Review proposed system architecture and technical decisions"
    }
  }'
```

**Zapier:** Creates Google Calendar event

---

### Example 3: Combined workflow

**the user:** "Create an issue for database migration planning and schedule a 2-hour session tomorrow at 10am"

**OpenStef:**
```bash
exec curl -X POST "$ZAPIER_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow": "issue_and_event",
    "issue": {
      "title": "Database migration planning",
      "description": "Plan migration strategy from PostgreSQL to distributed setup",
      "priority": "high",
      "labels": ["infrastructure", "database"]
    },
    "event": {
      "summary": "Database Migration Planning Session",
      "start": "2026-02-26T10:00:00Z",
      "end": "2026-02-26T12:00:00Z",
      "description": "Deep dive into migration strategy and risk assessment"
    }
  }'
```

**Zapier:** Creates both Linear issue AND Google Calendar event

---

## Integration with Other Skills

**Combine with:**
- **mermaid-architect:** Generate diagram → Create issue with diagram link
- **github:** Create issue from PR review → Schedule follow-up
- **web-research:** Research findings → Create issue with summary + schedule review

**Example workflow:**
1. Research topic (web-research skill)
2. Generate architecture diagram (mermaid-architect)
3. Create Linear issue with findings + diagram
4. Schedule review meeting
5. Send Slack notification to team

---

## Maintenance

**When to update this skill:**
- Zapier webhook URL changes (rotate/regenerate)
- New Zapier actions added (new integrations)
- Payload schemas change (field mappings updated)

**Location:** `skills/zapier-webhook/SKILL.md`

**Last Updated:** 2026-02-25  
**Webhook URL:** `https://hooks.zapier.com/hooks/catch/26594046/u02e6wi/`  
**Status:** Active ✅
