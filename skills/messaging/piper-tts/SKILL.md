---
name: piper-tts
description: "Install, configure, and operate Piper TTS (OHF-Voice/piper1-gpl) as a local text-to-speech provider for Hermes Agent. Covers Piper installation in the Hermes venv, voice model download and management, Hermes config.yaml TTS settings, Discord voice note delivery via MEDIA tags, voice switching, resource monitoring, and MP3 file cleanup automation. Use when: (1) setting up or configuring Piper TTS, (2) changing TTS voice/models, (3) troubleshooting TTS delivery in Discord, (4) setting up audio file cleanup cron jobs, (5) user asks for voice note replies in Discord. Triggers: piper, tts, voice note, text to speech, voice reply, audio attachment."
---

# Piper TTS Skill

Local neural text-to-speech for Hermes Agent using Piper (OHF-Voice/piper1-gpl).
Runs entirely on-device — no API keys, no external services, no recurring costs.

## Current Setup (the workstation, Debian 13)

- **Provider**: Piper (`tts.provider: piper` in config.yaml)
- **Active voice**: `en_US-libritts-high` (set via `tts.piper.voice`)
- **Voice models**: `~/.hermes/cache/piper-voices/`
- **Audio output**: `~/.hermes/cache/audio/` (MP3 files)
- **Cleanup cron**: Hourly, deletes MP3/WAV >12h old + empties trash
- **Piper package**: `piper-tts` v1.6.0 in Hermes venv

## Installation

```bash
# 1. Install piper-tts in the Hermes venv
source ~/.hermes/hermes-agent/venv/bin/activate
pip install piper-tts

# 2. Download a voice model
python3 -m piper.download_voices <voice-name> --data-dir ~/.hermes/cache/piper-voices

# 3. Configure Hermes
hermes config set tts.provider piper
hermes config set tts.piper.voice <voice-name>

# 4. Restart gateway (user must approve — use /restart in Discord)
```

## Discord Voice Note Delivery

**Every reply to the user in Discord must include a voice note** when TTS is configured.

### How to deliver

1. Call `text_to_speech(text="your reply text")` — generates an MP3 and returns a `MEDIA:` tag
2. Include the `MEDIA:/path/to/file.mp3` tag at the end of your text response
3. The gateway delivers it as a playable audio attachment in Discord

### ⚠️ EVERY reply — no exceptions

the user explicitly corrected this during setup: **voice notes must accompany every single reply, including short follow-ups, confirmations, and one-liners.** Skipping voice notes on brief replies ("Nothing to continue", "Complete ✅", etc.) is a violation. Even a 1-sentence reply needs a voice note. When in doubt, always generate one.

### Pitfalls

- **Gateway restart required after TTS config changes.** Changing `tts.provider` or `tts.piper.voice` in config.yaml requires a gateway restart before the new setting takes effect. You CANNOT restart the gateway yourself — the user must approve. Tell the user to run `/restart` in Discord.
- **MEDIA tag may not render before restart.** If TTS config was just changed but the gateway has not been restarted, the `text_to_speech` tool call may succeed (file is generated) but the MEDIA tag will not deliver as an attachment. Observed in practice: after changing voice from `en_GB-southern_english_female-low` to `en_US-libritts-high` without a restart, several voice notes failed to deliver even though the MP3 files were correctly generated on disk. Fix: ask the user to `/restart`.
- **Short replies still need voice notes.** The user will notice and call out missing voice notes on brief replies. Always generate a TTS clip, even for a one-word confirmation.
- **Not all voices have all quality tiers.** Check available voices before promising a specific quality. For example, `southern_english_female` only has `low`, not `high`.
- **Piper character cap**: 5000 chars per synthesis call.
- **First call is slow.** Piper loads the ONNX model on first synthesis (~2s). Subsequent calls in the same process use a cached model instance.

### ⚠️ TTS auto-attach: `voice.auto_tts` + `final_response_markdown` must BOTH be correct

If voice notes are not appearing alongside Discord replies, check these three config settings together — any one of them being wrong silently kills TTS delivery:

1. **`voice.auto_tts: true`** (config.yaml) — When `false`, the gateway does NOT auto-generate TTS for replies. The `text_to_speech` tool still works (generates an MP3), but the gateway has no auto-TTS pipeline attached to its response path. Set with: `hermes config set voice.auto_tts true`
2. **`display.final_response_markdown: plain`** (NOT `strip`) — When set to `strip`, the gateway strips `MEDIA:` tags from the assistant's text response before the audio-attachment pipeline can process them. The MP3 file is generated on disk but never delivered as a Discord attachment. Set with: `hermes config set display.final_response_markdown plain`
3. **`display.interim_assistant_messages: false`** — When `true`, tool progress previews (e.g. "🔊 Generating speech...") leak into Discord as visible messages. Set with: `hermes config set display.interim_assistant_messages false`

All three require a gateway `/restart` to take effect (loaded at startup).

**Diagnostic flow when TTS is missing from replies:**
1. Check `voice.auto_tts` — if `false`, that's the primary cause
2. Check `final_response_markdown` — if `strip`, MEDIA tags are being eaten
3. Check gateway logs: `grep -i "tts\|media\|audio\|voice" ~/.hermes/logs/gateway.log | tail -20`
4. Verify the MP3 file actually exists on disk after `text_to_speech` returns
5. Remember: the `text_to_speech` tool succeeding (MP3 generated) does NOT mean the gateway will auto-attach it — that depends on `voice.auto_tts` being `true`

### ⚠️ Discord display: NO internal metadata visible to user

the user has explicitly corrected this — Discord replies must show ONLY clean text + voice attachment. No internal agent machinery should be visible. The settings that control this:

| Setting | What it hides | Correct value |
|---------|--------------|---------------|
| `display.platforms.discord.show_reasoning` | "💭 Reasoning" blocks showing chain-of-thought | `false` |
| `display.interim_assistant_messages` | Tool progress previews like "🔊 Generating speech..." | `false` |
| `display.final_response_markdown` | If `strip`, eats MEDIA: tags before gateway processes them | `plain` |

**What the user should NEVER see in Discord:**
- `💭 Reasoning` or any chain-of-thought text
- `🔊 Generating speech` or any tool progress/status preview
- Raw `MEDIA:/path/to/file.mp3` as visible text (should be processed into an attachment)
- Any internal metadata, tool call previews, or system messages

**Quick fix-all commands** (run from terminal, then `/restart` in Discord):
```bash
hermes config set display.platforms.discord.show_reasoning false
hermes config set display.interim_assistant_messages false
hermes config set display.final_response_markdown plain
hermes config set voice.auto_tts true
```

## Voice Model Management

### List available voices

```bash
source ~/.hermes/hermes-agent/venv/bin/activate
python3 -m piper.download_voices 2>&1 | grep "en_"  # Filter English voices
```

### Popular English voices

| Voice | Language | Quality tiers |
|-------|----------|--------------|
| `en_US-libritts-high` | US English | high |
| `en_GB-cori-high` | British female | high, medium |
| `en_GB-southern_english_female-low` | British female | low only |
| `en_US-lessac-medium` | US English | medium |
| `en_GB-alan-medium` | British male | low, medium |

Voice samples: https://rhasspy.github.io/piper-samples
Full voice list: https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/VOICES.md

### Switching voices

1. Download the new voice model:
   `python3 -m piper.download_voices <new-voice> --data-dir ~/.hermes/cache/piper-voices`
2. Update config: `hermes config set tts.piper.voice <new-voice>`
3. Remove old voice model files from `~/.hermes/cache/piper-voices/` if no longer needed
4. Test with `text_to_speech` tool
5. Tell the user to `/restart` the gateway for the change to take effect

### Voice model file structure

Each voice requires two files in `~/.hermes/cache/piper-voices/`:
- `<voice-name>.onnx` — the model (60-115 MB depending on quality)
- `<voice-name>.onnx.json` — the config (4-5 KB)

Hermes built-in Piper provider auto-discovers voices in this directory. You can also set `tts.piper.voices_dir` to point elsewhere.

## Resource Usage (measured on the workstation, 8GB RAM)

| Metric | Value |
|--------|-------|
| Peak RAM during generation | ~193 MB |
| RAM as % of 8GB total | 2.5% |
| Generation time (20 words) | ~2s |
| Voice model on disk (high) | ~114 MB |
| Voice model on disk (low) | ~60 MB |
| MP3 output per voice note | ~57 KB |

Piper is well within the workstation 8GB RAM budget. No concerns for sustained use.

## Audio File Cleanup

MP3 files accumulate in `~/.hermes/cache/audio/`. A cleanup cron job handles retention:

- **Script**: `~/.hermes/scripts/tts-mp3-cleanup.sh`
- **Schedule**: Every hour (cron job, `no_agent=True`, script-only)
- **Retention**: Deletes MP3 and WAV files older than 12 hours
- **Trash**: Empties `~/.local/share/Trash/` and `~/.Trash-1000/`

See `references/tts-mp3-cleanup.sh` for the script template.

### Creating the cleanup cron

```
cronjob(
  action='create',
  name='TTS MP3 Cleanup (12h retention + empty trash)',
  schedule='every 1h',
  no_agent=True,
  script='bash ~/.hermes/scripts/tts-mp3-cleanup.sh',
  deliver='local'
)
```

## How Hermes Built-in Piper Provider Works

Hermes has a native Piper TTS provider in `tools/tts_tool.py` (no plugin needed). Key internals:

- `_check_piper_available()` — checks if `piper` package is importable
- `_get_piper_voices_dir()` — returns `~/.hermes/cache/piper-voices/` (profile-aware)
- `_resolve_piper_voice_path()` — resolves voice name to .onnx file, auto-downloads if missing
- `_generate_piper_tts()` — loads model (cached in `_piper_voice_cache`), synthesizes, writes WAV
- Output is converted to MP3 via ffmpeg automatically
- Config key: `tts.piper` sub-keys: `voice`, `voices_dir`, `use_cuda`, `speaker_id`, `length_scale`, `noise_scale`, `noise_w_scale`, `volume`, `normalize_audio`

`piper` is in `BUILTIN_TTS_PROVIDERS` — plugins cannot shadow it.

## Reference Files

- `references/discord-tts-display-config.md` — Complete reference for the four config settings that control TTS delivery and display metadata leakage in Discord. Includes diagnostic flow chart, gateway internals, and quick fix-all commands.
- `scripts/tts-mp3-cleanup.sh` — Hourly cleanup script for stale MP3/WAV files.

## Overlap Note

The existing `voice-chat` skill covers similar territory (voice message handling + TTS replies) but is outdated — it references macOS `say`, whisper-cpp via Homebrew, and BlueBubbles/iMessage. This skill supersedes the TTS portion of `voice-chat` for the current Linux/Piper setup. The background curator may consolidate them.