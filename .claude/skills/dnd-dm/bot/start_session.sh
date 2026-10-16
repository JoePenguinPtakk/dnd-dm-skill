#!/usr/bin/env bash
# One command to get a dnd-dm campaign's live session on the air.
# Campaign-agnostic: ships with the dnd-dm skill and is copied into each
# campaign's bot/ folder. Everything campaign-specific is in bot/.env.
#
# Everything that cost us a live session on 2026-08-16 is checked here,
# before the table is waiting: missing voice dependencies that only fail at
# the moment the bot joins voice, a blank channel ID, a TTS cursor that
# replays the whole previous session aloud, and restarts that silently left
# the old process running.
#
#   bot/start_session.sh          preflight, then start relay + TTS, health-checked
#   bot/start_session.sh --check  preflight only; starts nothing, changes nothing
#   bot/start_session.sh --stop   stop both processes and exit
#   bot/start_session.sh --engine piper    (any extra flags pass through to the TTS bridge)
#
# Exit code is 0 only if every check passed and both processes reported ready.

set -uo pipefail

BOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$BOT/.venv/bin/python"
PIP="$BOT/.venv/bin/pip"
ENV_FILE="$BOT/.env"
# The mailbox: MAILBOX_DIR in .env, else bot/mailbox/ if it exists, else bot/
# (the same rule relay.py and tts_bridge.py use).
MAILBOX="$BOT"
[ -d "$BOT/mailbox" ] && MAILBOX="$BOT/mailbox"
if [ -f "$ENV_FILE" ]; then
  _mb=$(sed -e '1s/^\xEF\xBB\xBF//' "$ENV_FILE" | grep -E '^[[:space:]]*MAILBOX_DIR[[:space:]]*=' | head -1 | cut -d= -f2- | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')
  if [ -n "$_mb" ]; then
    case "$_mb" in /*) MAILBOX="$_mb" ;; *) MAILBOX="$BOT/$_mb" ;; esac
  fi
fi
OUTBOX="$MAILBOX/outbox.jsonl"
TTS_CURSOR="$MAILBOX/.tts-cursor"
RELAY_LOG="$BOT/relay.log"
TTS_LOG="$BOT/tts.log"

READY_TIMEOUT=180   # Kokoro's first-run graph compile is slow; be patient here.

if [ -t 1 ]; then
  R=$'\033[31m'; G=$'\033[32m'; Y=$'\033[33m'; B=$'\033[1m'; N=$'\033[0m'
else
  R=""; G=""; Y=""; B=""; N=""
fi

FAILED=0
ok()   { printf '  %s+%s %s\n' "$G" "$N" "$1"; }
warn() { printf '  %s!%s %s\n' "$Y" "$N" "$1"; }
bad()  { printf '  %sx%s %s\n' "$R" "$N" "$1"; FAILED=1; }
hdr()  { printf '\n%s%s%s\n' "$B" "$1" "$N"; }

# --- argument handling ------------------------------------------------------
MODE="run"
PASSTHRU=()
for arg in "$@"; do
  case "$arg" in
    --check) MODE="check" ;;
    --stop)  MODE="stop" ;;
    *)       PASSTHRU+=("$arg") ;;
  esac
done

# --- helpers ----------------------------------------------------------------

# Read one key out of .env. Tolerates the utf-8 BOM, same as relay.py does.
env_val() {
  [ -f "$ENV_FILE" ] || return 1
  sed -e '1s/^\xEF\xBB\xBF//' "$ENV_FILE" \
    | grep -E "^[[:space:]]*$1[[:space:]]*=" \
    | head -1 | cut -d= -f2- | sed 's/^[[:space:]]*//; s/[[:space:]]*$//'
}

stop_proc() {  # stop_proc <script name> <label>
  # Only this campaign's process: launched below by full path, so the pattern
  # names this bot/ folder and never touches another campaign's bot. A process
  # started the old way (bare script name, from a script before this one) is
  # matched only if its working directory is this bot/ folder.
  local pids p
  pids=$(pgrep -f "$BOT/$1" 2>/dev/null)
  for p in $(pgrep -f "[ ]$1" 2>/dev/null); do
    if [ "$(lsof -a -p "$p" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p')" = "$BOT" ]; then
      pids="$pids $p"
    fi
  done
  pids=$(echo $pids)
  if [ -n "$pids" ]; then
    # shellcheck disable=SC2086
    kill $pids 2>/dev/null
    sleep 1
    local left=""
    for p in $pids; do kill -0 "$p" 2>/dev/null && left="$left $p"; done
    # shellcheck disable=SC2086
    [ -n "$left" ] && { kill -9 $left 2>/dev/null; sleep 1; }
    ok "stopped $2"
  else
    ok "$2 not running"
  fi
}

# Poll a log until a success or failure pattern shows up, or we time out.
#
# `since` is the log's line count before this run started, and it matters:
# relay.log is an append-only history, so a naive grep matches a "connected to
# Gateway" line from a previous session and reports ready for a process that
# never started. Only ever read what this run wrote.
wait_for() {  # wait_for <logfile> <success-regex> <failure-regex> <label> <pid> <since-line>
  local log="$1" good="$2" bad_re="$3" label="$4" pid="$5" since="${6:-0}" waited=0 chunk
  while [ "$waited" -lt "$READY_TIMEOUT" ]; do
    chunk=$(tail -n "+$((since + 1))" "$log" 2>/dev/null)
    if printf '%s' "$chunk" | grep -qE "$good"; then ok "$label ready"; return 0; fi
    if printf '%s' "$chunk" | grep -qE "$bad_re"; then
      bad "$label failed; see $log"
      printf '%s\n' "$chunk" | grep -E -m1 -A4 "$bad_re" | sed 's/^/      /'
      return 1
    fi
    if ! kill -0 "$pid" 2>/dev/null; then
      bad "$label died during startup; see $log"
      printf '%s\n' "$chunk" | tail -5 | sed 's/^/      /'
      return 1
    fi
    sleep 2; waited=$((waited + 2))
  done
  bad "$label timed out after ${READY_TIMEOUT}s; see $log"
  return 1
}

# --- --stop -----------------------------------------------------------------
if [ "$MODE" = "stop" ]; then
  hdr "Stopping session"
  stop_proc "tts_bridge.py" "TTS bridge"
  stop_proc "relay.py" "Discord relay"
  exit 0
fi

# --- 1. interpreter ---------------------------------------------------------
hdr "1. Interpreter"
if [ -x "$PY" ]; then
  ok "venv python $("$PY" --version 2>&1 | awk '{print $2}')"
else
  bad "no venv at $PY  (create it: python3 -m venv bot/.venv && bot/.venv/bin/pip install -r bot/requirements.txt)"
  exit 1
fi

# --- 2. configuration -------------------------------------------------------
hdr "2. Configuration (bot/.env)"
if [ -f "$ENV_FILE" ]; then
  ok ".env present"
  for key in DISCORD_TOKEN ALLOWED_CHANNEL_ID TTS_VOICE_CHANNEL_ID; do
    val="$(env_val "$key")"
    if [ -z "$val" ]; then
      if [ "$key" = "TTS_VOICE_CHANNEL_ID" ]; then
        bad "$key is empty  (Discord: Developer Mode on, right-click the VOICE channel, Copy Channel ID)"
      else
        bad "$key is empty"
      fi
    else
      ok "$key set"
    fi
  done
  for key in OOC_CHANNEL_ID NARRATOR_VOICE CHARACTER_VOICES PLAYER_MAP; do
    [ -n "$(env_val "$key")" ] && ok "$key set" || warn "$key unset (optional)"
  done
else
  bad ".env missing  (copy bot/.env.example to bot/.env and fill it in)"
fi

# --- 3. dependencies --------------------------------------------------------
hdr "3. Dependencies"
# discord.py 2.7+ needs BOTH of these to join voice, and it does not fail at
# login, it fails at the moment of joining, which looks like the bot working
# right up until nobody can hear it.
for mod in discord nacl davey kokoro_onnx numpy; do
  if "$PY" -c "import $mod" 2>/dev/null; then
    ok "$mod"
  elif [ "$MODE" = "check" ]; then
    bad "$mod missing  (bot/.venv/bin/pip install -r bot/requirements.txt)"
  else
    warn "$mod missing, installing..."
    if "$PIP" install --quiet "$mod" 2>/dev/null && "$PY" -c "import $mod" 2>/dev/null; then
      ok "$mod installed"
    else
      bad "could not install $mod  (try: bot/.venv/bin/pip install -r bot/requirements.txt)"
    fi
  fi
done

if command -v ffmpeg >/dev/null 2>&1; then
  ok "ffmpeg (system)"
elif "$PY" -c "import imageio_ffmpeg" 2>/dev/null; then
  ok "ffmpeg (imageio-ffmpeg fallback)"
else
  bad "no ffmpeg and no imageio-ffmpeg fallback; TTS cannot stream audio"
fi

# --- 4. voice models --------------------------------------------------------
hdr "4. Voice models"
if [ -f "$BOT/voices/kokoro/kokoro-v1.0.onnx" ] && [ -f "$BOT/voices/kokoro/voices-v1.0.bin" ]; then
  ok "Kokoro model + voice pack present"
else
  bad "Kokoro model missing from bot/voices/kokoro/  (needs kokoro-v1.0.onnx and voices-v1.0.bin)"
fi

# --- preflight verdict ------------------------------------------------------
if [ "$FAILED" -ne 0 ]; then
  hdr "Preflight FAILED"
  echo "  Fix the items marked x above, then run again."
  exit 1
fi

if [ "$MODE" = "check" ]; then
  hdr "Preflight passed"
  echo "  Nothing was started. Run without --check to go live."
  exit 0
fi

# --- 5. clean slate ---------------------------------------------------------
# A dependency fix does nothing until the old process is actually gone, and a
# restart that quietly left the old one running is how we spent 2026-08-16
# reading the same error out of a stale process.
hdr "5. Clearing any running processes"
stop_proc "tts_bridge.py" "TTS bridge"
stop_proc "relay.py" "Discord relay"

# --- 6. cursor --------------------------------------------------------------
hdr "6. TTS cursor"
lines=0
[ -f "$OUTBOX" ] && lines=$(wc -l < "$OUTBOX" | tr -d ' ')
printf '%s' "$lines" > "$TTS_CURSOR"
ok "fast-forwarded to line $lines (previous sessions will not be re-read aloud)"

# --- 7. launch --------------------------------------------------------------
hdr "7. Starting processes"
# Both scripts resolve their own paths from their location, but they are
# launched by filename, so the working directory has to be bot/ or python
# cannot find them at all.
cd "$BOT" || exit 1
: > "$TTS_LOG"

# Where this run's output starts, so the health check cannot read history.
RELAY_LOG_START=0
[ -f "$RELAY_LOG" ] && RELAY_LOG_START=$(wc -l < "$RELAY_LOG" | tr -d ' ')

nohup "$PY" -u "$BOT/relay.py" >> "$RELAY_LOG" 2>&1 &
RELAY_PID=$!
ok "relay started (pid $RELAY_PID)"

# -u so the log tells us what happened instead of holding it in a buffer.
nohup "$PY" -u "$BOT/tts_bridge.py" "${PASSTHRU[@]+"${PASSTHRU[@]}"}" > "$TTS_LOG" 2>&1 &
TTS_PID=$!
ok "TTS bridge started (pid $TTS_PID)"

# --- 8. health check --------------------------------------------------------
hdr "8. Waiting for both to report ready"
echo "  (Kokoro warm-up on a cold start can take a couple of minutes)"
wait_for "$RELAY_LOG" "has connected to Gateway" \
         "LoginFailure|Traceback|can't open file|No such file" \
         "relay" "$RELAY_PID" "$RELAY_LOG_START"
wait_for "$TTS_LOG" "Connected to voice channel" \
         "Traceback|No TTS_VOICE_CHANNEL_ID|not found or not visible|can't open file" \
         "TTS bridge" "$TTS_PID" 0

if [ "$FAILED" -ne 0 ]; then
  hdr "Startup FAILED"
  echo "  Logs: $RELAY_LOG · $TTS_LOG"
  echo "  Stop everything with: bot/start_session.sh --stop"
  exit 1
fi

CHANNEL=$(grep -m1 "Connected to voice channel" "$TTS_LOG" | sed 's/.*channel: //')
hdr "Session is live"
echo "  Voice channel : ${CHANNEL:-unknown}"
echo "  Narrator      : $(env_val NARRATOR_VOICE)"
echo "  Cast          : $(env_val CHARACTER_VOICES)"
echo "  Logs          : $RELAY_LOG · $TTS_LOG"
echo "  Stop          : bot/start_session.sh --stop"
echo
echo "  Now boot the DM: /dnd-dm"
