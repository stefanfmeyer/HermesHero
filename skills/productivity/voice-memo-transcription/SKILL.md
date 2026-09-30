---
name: voice-memo-transcription
description: Transcribe iPhone voice memos (.m4a), extract key insights, and post structured training/output to Slack #internal-agent-chat.
---

# Voice Memo Transcription Pipeline

Handle iPhone voice memo recordings received as audio files via Discord, iMessage, or local file path.

## Pipeline

```
Receiving audio file (.m4a/.mp3/.wav/.ogg)
    ↓
Save to ~/.hermes/voice-memos/
    ↓
Transcribe with Whisper.cpp
    ↓
Generate two files:
  1. Full transcription: YYYY-MM-DD_topic.md
  2. Structured insights: YYYY-MM-DD_topic_guide.md
    ↓
Post to Slack #internal-agent-chat (C0ASCRQPU4Q)
  - Message 1: Rich guide with user tags
  - Message 2: Full transcription as file upload
```

## File Structure

- **Folder**: `~/.hermes/voice-memos/` (create if not exists)
- **Full transcript**: `YYYY-MM-DD_topic.md` — raw verbatim transcription
- **Training guide**: `YYYY-MM-DD_topic_guide.md` — structured insights with scripts, bullet points, actionable takeaways

## Transcription

Whisper.cpp is installed at:
- CLI: `/opt/homebrew/Cellar/whisper-cpp/1.8.4/bin/whisper-cli`
- Model: `~/.local/voice/models/ggml-base.en.bin`

```bash
whisper-cli -m ~/.local/voice/models/ggml-base.en.bin -f input.m4a -l en --no-timestamps --no-prints
```

Convert non-wav formats first:
```bash
sox input.m4a -r 16000 -c 1 -b 16 /tmp/voice_input.wav
```

## Guide Format

When extracting key facts/training from a transcript, structure as:

1. **Key Takeaways** — bullet list of core lessons
2. **Ready-to-Use Scripts** — numbered, per-situation scripts with placeholders
   - (A) Gatekeeper bypass
   - (B) Upfront contract
   - (C) Time honouring
   - (D) Psychology hacks
   - (E) Voicemail template
   - (F) Scenario-specific approach
3. **Pain-Unveiling Framework** — question progression table
4. **Delivery Rules** — tone, pace, 30/70 rule
5. **Practice / Mindset** — role play, warm-up calls, rejection reframing

## Posting to Slack

Use the direct Slack API workaround documented in the `slack-channel-resolution-fix` skill (gateway tool can't resolve private channel IDs). Follow that skill's instructions for `chat.postMessage` and `files_upload_v2`.

### Channel & User IDs
- Channel: `C0ASCRQPU4Q` (#internal-agent-chat)
- Ben: `<@U0AH6GJV80Y>`
- Sean: `<@U0ALJ30JGLC>`
- the user: `<@U0AHL5TBJHY>`

### Block Kit Tips
- Max 3000 chars per mrkdwn section block
- Use divider blocks between sections
- `"text"` top-level field = notification fallback
- Split long content across multiple section blocks

## Skill Dependencies

- `voice-chat` — for receiving voice messages from iMessage/Discord
- `slack-channel-resolution-fix` — for the direct Slack API workaround (read this for token access and curl/Python examples)

## Pitfalls

- Gateway `send_message` tool CANNOT resolve private channel IDs like `C0ASCRQPU4Q` (stale cache). Always use direct API documented in slack-channel-resolution-fix.
- Old `files.upload` API is deprecated. Use `files_upload_v2()` via slack_sdk.
- Check char limits on Block Kit blocks — split long content.
- Always save to `~/.hermes/voice-memos/` (create dir if missing).
- Always create TWO files: a raw transcript AND a structured guide.
