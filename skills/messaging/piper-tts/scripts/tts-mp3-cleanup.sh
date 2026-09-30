#!/bin/bash
# TTS MP3 Cleanup Script — deletes audio files older than 12 hours
# and empties the trash bin. Designed to run as a Hermes cron job
# (no_agent=True, script-only, every 1h).
#
# Install location: ~/.hermes/scripts/tts-mp3-cleanup.sh
# Cron job: cronjob(action='create', schedule='every 1h', no_agent=True,
#   script='bash ~/.hermes/scripts/tts-mp3-cleanup.sh', deliver='local')

AUDIO_CACHE_DIR="$HOME/.hermes/cache/audio"
TRASH_DIR="$HOME/.local/share/Trash"

# Delete MP3 files older than 12 hours (720 minutes) from audio cache
if [ -d "$AUDIO_CACHE_DIR" ]; then
    find "$AUDIO_CACHE_DIR" -name "*.mp3" -mmin +720 -delete 2>/dev/null
    # Also clean up any .wav files older than 12h
    find "$AUDIO_CACHE_DIR" -name "*.wav" -mmin +720 -delete 2>/dev/null
fi

# Empty the trash bin (files + info)
if [ -d "$TRASH_DIR/files" ]; then
    rm -rf "$TRASH_DIR/files"/* 2>/dev/null
fi
if [ -d "$TRASH_DIR/info" ]; then
    rm -rf "$TRASH_DIR/info"/* 2>/dev/null
fi

# Also handle .Trash-1000 (common on Linux)
if [ -d "$HOME/.Trash-1000/files" ]; then
    rm -rf "$HOME/.Trash-1000/files"/* 2>/dev/null
fi
if [ -d "$HOME/.Trash-1000/info" ]; then
    rm -rf "$HOME/.Trash-1000/info"/* 2>/dev/null
fi

echo "Cleanup complete: removed MP3/WAV files older than 12h from $AUDIO_CACHE_DIR and emptied trash"