# Discord TTS + Display Configuration Reference

Complete reference for the config settings that control TTS delivery and
display metadata leakage in Discord gateway replies.

## The Four-Setting Checklist

When TTS is not attaching to Discord replies, OR internal metadata is leaking
into Discord messages, check these four config settings. Any one being wrong
silently breaks the user experience.

### 1. `voice.auto_tts` — Gateway auto-TTS

```yaml
voice:
  auto_tts: true   # MUST be true for auto-TTS on every reply
```

- **When false**: The gateway does NOT auto-generate TTS for replies. The
  `text_to_speech` tool still works (generates an MP3 on disk), but the gateway
  has no auto-TTS pipeline attached to its response path. The MEDIA: tag in the
  agent's text response is the only mechanism, and it can be fragile.
- **When true**: The gateway auto-generates TTS for every reply and attaches
  the audio as a Discord voice bubble or file attachment.
- **Set via**: `hermes config set voice.auto_tts true`
- **Persisted across restarts**: Yes (in config.yaml)
- **Per-chat override**: `/voice on` (voice-only mode), `/voice tts` (all mode),
  `/voice off` (disable). These persist in `~/.hermes/gateway_voice_mode.json`.

### 2. `display.final_response_markdown` — MEDIA tag survival

```yaml
display:
  final_response_markdown: plain   # NOT "strip"
```

- **When `strip`**: The gateway strips MEDIA: tags from the assistant's text
  response BEFORE the audio-attachment pipeline can process them. The MP3 file
  is generated on disk but never delivered as a Discord attachment. This is a
  silent failure — no error in logs, the audio file just sits on disk.
- **When `plain`**: MEDIA: tags survive to the gateway layer where they are
  processed into audio attachments and stripped from the visible text.
- **Set via**: `hermes config set display.final_response_markdown plain`

### 3. `display.interim_assistant_messages` — Tool progress leakage

```yaml
display:
  interim_assistant_messages: false   # NOT true
```

- **When true**: Tool progress previews leak into Discord as visible messages.
  Examples: "🔊 Generating speech...", "📝 Reading file...", etc. These appear
  as separate messages before the final reply.
- **When false**: Tool calls are silent. Only the final response is sent.
- **Set via**: `hermes config set display.interim_assistant_messages false`

### 4. `display.platforms.discord.show_reasoning` — Reasoning block leakage

```yaml
display:
  platforms:
    discord:
      show_reasoning: false   # NOT true
```

- **When true**: The agent's chain-of-thought reasoning (💭 Reasoning blocks)
  is visible in Discord messages. This includes internal deliberation about
  what to do, which the user should never see.
- **When false**: Reasoning is hidden from Discord output.
- **Set via**: `hermes config set display.platforms.discord.show_reasoning false`

## Diagnostic Flow

```
TTS missing from Discord reply?
├── Check voice.auto_tts → false? → That's the primary cause
├── Check final_response_markdown → "strip"? → MEDIA tags eaten before delivery
├── Check gateway logs for TTS/MEDIA errors
│   grep -i "tts\|media\|audio\|voice" ~/.hermes/logs/gateway.log | tail -20
├── Verify MP3 exists on disk after text_to_speech tool call
└── Remember: text_to_speech succeeding ≠ gateway auto-attaching

Internal metadata leaking into Discord?
├── "💭 Reasoning" visible? → display.platforms.discord.show_reasoning = true
├── "🔊 Generating speech" visible? → display.interim_assistant_messages = true
├── Raw "MEDIA:/path" visible as text? → final_response_markdown = strip
└── All three need /restart to take effect
```

## Quick Fix-All

```bash
hermes config set voice.auto_tts true
hermes config set display.final_response_markdown plain
hermes config set display.interim_assistant_messages false
hermes config set display.platforms.discord.show_reasoning false
# Then /restart in Discord (user must do this)
```

## Gateway Internals (for reference)

- `_auto_tts_default` in `base.py` is set from `voice.auto_tts` config value
  pushed by GatewayRunner on connect
- Per-chat overrides live in `_auto_tts_enabled_chats` and
  `_auto_tts_disabled_chats` sets, populated from `/voice` commands
- `_should_auto_tts_for_chat(chat_id)` checks: explicit enable → explicit
  disable → global default
- `MEDIA:` tag extraction happens in `extract_media()` in `base.py` — if
  `final_response_markdown: strip` removes the tag first, extraction never fires
- Voice mode state persisted in `~/.hermes/gateway_voice_mode.json`