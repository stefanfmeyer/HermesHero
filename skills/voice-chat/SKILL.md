---
name: voice-chat
description: Handle voice messages from iMessage and Discord, transcribe them, convert responses to speech, and send voice replies. Use when receiving voice messages or audio attachments from the user via BlueBubbles (iMessage) or Discord. Handles the complete voice pipeline: receive audio → Whisper transcription → process → TTS response → send voice back.
---

# Voice Chat Skill

Complete voice message handling for iMessage and Discord.

## Pipeline Overview

```
Incoming voice message
    ↓
Save audio file (.m4a/.wav/.mp3)
    ↓
Transcribe with Whisper.cpp
    ↓
Process as text (OpenStef responds)
    ↓
TTS response with macOS say
    ↓
Send voice reply via same channel
```

## Dependencies

- **Whisper.cpp**: `brew install whisper-cpp`
- **sox**: `brew install sox`
- **Model**: Base English model at `~/.local/voice/models/ggml-base.en.bin`

## Core Scripts

### Transcribe Audio

```javascript
// voice-pipeline.js
const { execSync } = require('child_process');
const path = require('path');

const WHISPER_CLI = '/opt/homebrew/Cellar/whisper-cpp/1.8.4/bin/whisper-cli';
const MODEL = path.join(process.env.HOME, '.local/voice/models/ggml-base.en.bin');

function transcribe(audioPath) {
  const result = execSync(
    `"${WHISPER_CLI}" -m "${MODEL}" -f "${audioPath}" -l en --no-timestamps --no-prints`,
    { encoding: 'utf8' }
  );
  return result.trim();
}

module.exports = { transcribe };
```

### Text to Speech

```bash
# Uses macOS say command
say -v Daniel -o output.wav --file /dev/stdin <<< "Text to speak"
```

## Workflow

1. **Receive voice message** with audio attachment
2. **Download/save** audio file to `/tmp/voice_input.m4a`
3. **Convert** to wav format if needed: `sox input.m4a -r 16000 -c 1 output.wav`
4. **Transcribe**: Run Whisper on the wav file
5. **Process**: Feed transcription to OpenStef as text
6. **Respond**: Generate TTS audio of response
7. **Send**: Send voice file back via same channel

## Handling Audio Formats

```bash
# Convert m4a to wav for Whisper
sox input.m4a -r 16000 -c 1 -b 16 /tmp/voice_input.wav

# Convert mp3
sox input.mp3 -r 16000 -c 1 -b 16 /tmp/voice_input.wav

# Convert ogg
sox input.ogg -r 16000 -c 1 -b 16 /tmp/voice_input.wav
```

## Voice Options

macOS built-in voices (no download needed):
- `Daniel` - British English male
- `Karen` - Australian English female  
- `Ting-Ting` - Chinese female
- `Moira` - Irish English female

## File Paths

- Whisper CLI: `/opt/homebrew/Cellar/whisper-cpp/1.8.4/bin/whisper-cli`
- Model: `~/.local/voice/models/ggml-base.en.bin`
- Temp audio: `/tmp/voice_input.wav`
- Temp output: `/tmp/voice_response.wav`

## Error Handling

- **No speech detected**: Respond "I didn't catch that, could you repeat it?"
- **Whisper fails**: Log error, respond "Sorry, I had trouble processing the audio"
- **TTS fails**: Send text response instead
- **Unsupported format**: Attempt conversion, fail gracefully with text
