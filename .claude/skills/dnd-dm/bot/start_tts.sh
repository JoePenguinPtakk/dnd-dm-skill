#!/bin/bash
# Speaks the DM's narration into the Discord voice channel.
# Run in its own terminal window: output stays live so the connection,
# the cast, and each spoken line are visible while the session runs.
# Any flag is passed through (--engine piper for a fast, flatter voice).
cd "$(dirname "$0")"
exec .venv/bin/python "$PWD/tts_bridge.py" "$@"
