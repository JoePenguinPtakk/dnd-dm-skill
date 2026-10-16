"""TTS bridge: DM narration, spoken live in the Discord voice channel.

Campaign-agnostic; ships with the dnd-dm skill. Every campaign-specific
setting is in bot/.env (see .env.example): the voice channel, the narrator
(NARRATOR_VOICE), the cast (CHARACTER_VOICES), pronunciations.

Joins TTS_VOICE_CHANNEL_ID and watches the mailbox's outbox.jsonl for new DM
posts on the "game" and "ooc" channels. Speaks the narration prose only
(strips VITALS, roll log, NEEDED, CHOICE, LOOP) -- the NEEDED roll-gate
line reads as a non-sequitur stitched onto the narration in spoken
prose; it needs its own phrasing to flow naturally, not just
concatenation, so it's left out until that's built. Runs the result
through Piper TTS and streams it into the voice channel via ffmpeg.

Setup (one-time):  python bot/tts_bridge.py --download
Usage:              python bot/tts_bridge.py [--voice NAME] [--rate N] [--speed N]
"""

import asyncio
import io
import json
import re
import subprocess
import sys
from pathlib import Path

import discord
from discord.ext import tasks

BOT = Path(__file__).resolve().parent
ENV_PATH = BOT / ".env"


def _mailbox() -> Path:
    """Same rule as relay.py: MAILBOX_DIR in .env, else bot/mailbox/ if it exists, else bot/ itself. A wrong
    path fails silently (nothing to poll, no speech, no error), so both scripts share this one rule."""
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8-sig").splitlines():
            if line.strip().startswith("MAILBOX_DIR="):
                raw = line.split("=", 1)[1].strip()
                if raw:
                    p = Path(raw)
                    return p if p.is_absolute() else BOT / p
    return BOT / "mailbox" if (BOT / "mailbox").is_dir() else BOT


OUTBOX = _mailbox() / "outbox.jsonl"
CURSOR = _mailbox() / ".tts-cursor"
VOICES_DIR = BOT / "voices"

DEFAULT_VOICE = str(VOICES_DIR / "en_US-lessac-high.onnx")
DEFAULT_RATE = 22050
DEFAULT_SPEED = 0.9  # fraction of normal speed; piper's length-scale is 1/speed
POLL_SECONDS = 2




def _piper_cmd() -> list:
    """How to invoke Piper on this machine.

    `pip install --user piper-tts` puts the console script in
    ~/Library/Python/3.11/bin, which is not on PATH in a GUI-launched
    process, so the bare name fails with FileNotFoundError. Prefer PATH, then
    the user script, then the module form, which always works when the
    package imports at all.
    """
    import shutil, sys
    from pathlib import Path as _P
    found = shutil.which("piper")
    if found:
        return [found]
    user_bin = _P.home() / "Library" / "Python" / f"{sys.version_info.major}.{sys.version_info.minor}" / "bin" / "piper"
    if user_bin.exists():
        return [str(user_bin)]
    return [sys.executable, "-m", "piper"]


def _ffmpeg_exe() -> str:
    """Path to an ffmpeg binary, preferring one already on PATH.

    `brew install ffmpeg` failed on this Mac 2026-08-02 on a directory
    ownership problem under /usr/local/share/man that needs sudo, so the
    bridge falls back to the static binary imageio-ffmpeg ships. That needs
    no admin rights and no PATH changes. If a system ffmpeg is installed
    later this prefers it automatically and the fallback stops being used.
    """
    import shutil
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"   # let discord.py raise its own clear error


def apply_pronunciation(text: str, overrides: dict) -> str:
    """Swap a name for a phonetic respelling before synthesis only.

    The written record (Discord text, saves, the transcript) never sees this
    -- it's a pure audio-side substitution, applied after speaker parsing so
    it can't collide with the "Name:" prefix voice lookup.
    """
    for name, phonetic in overrides.items():
        text = re.sub(re.escape(name), phonetic, text, flags=re.I)
    return text


def load_env(path):
    """Minimal .env parser, utf-8-sig tolerant. Mirrors relay/relay.py."""
    values = {}
    if not path.exists():
        return values
    with open(path, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            values[key.strip()] = val.strip()
    return values


# ── Text extraction ──────────────────────────────────────────────────

# Tagged mechanics lines the DM emits alongside prose. None of these are
# narration and none of them read aloud as speech: a roll gate stitched onto a
# sentence is a non-sequitur, and a VITALS strip is a table read as a list of
# numbers. Matched after bold markers are stripped, so both "**NEEDED:**" and
# a bare "NEEDED:" are caught.
# The turn always ends in a numbered option menu. It reads as prose to a
# stripper but is a control surface, not story, and speaking it aloud turns
# every scene into a phone tree.
OPTION_LINE = re.compile(r"^\s*\d{1,2}[.)]\s+\S")

MECH_LINE = re.compile(
    r"^\s*(NEEDED|VITALS|DM ROLLS(?: THIS (?:TURN|RESPONSE))?|ROLL GATE|PENDING ROLLS"
    r"|CHOICE|LOOP|COMBAT STATE|COMBAT SETUP|STAT BLOCKS|INITIATIVE|RANGE"
    r"|FEATURES|FLAGS|ZONE-ANCHORS|MODE|DIFFICULTY|BUDGET|THREATS|MORALE"
    r"|WIN|FAILURE|CHAIN|NEMESIS CHAIN|LOCATION CHAIN|NIGHT CHAIN|BASTION TURN|SPLIT"
    r"|CLOCK|THREAT-STATUS|NEM|UNESTABLISHED|TURN CLOSE|SPELL CAST|XP AWARD"
    r"|LEVEL UP|SESSION ROSTER|SESSION BOUNDARY|GRUDGE|ENC|DUNGEON|TIME SKIP|REAL)\b\s*[:\u2014-]"
    # The dice engine's own block (\u00a71-sexies): its header and every "[R0042] label ..." line.
    r"|^\s*DM ROLLS THIS RESPONSE\b|^\s*\[R\d{4,}\]"
    # Per-roll tags (\u00a71-quinquies) never take a trailing colon -- "**ATK** 13+5=18...",
    # "**ATK 1** 16+3=19..." -- so this branch matches on the tag alone, line-initial.
    r"|^\s*(?:ATK|DMG|SAVE|CHECK|INIT)(?:\s*\d+)?\b",
    re.I,
)


def extract_narration(text: str) -> str:
    """Pull the DM's prose out of a scaffold-composed post.

    The scaffold builds: narration --- surface (VITALS, roll log, etc).
    We want only the narration -- the story, not the mechanics.
    """
    if not text:
        return ""
    parts = re.split(r'\n---\n', text, maxsplit=1)
    prose = parts[0]
    fence = re.search(r'===\s*DM\s*===.*?===\s*END\s*===', prose, re.DOTALL)
    if fence:
        prose = prose[:fence.start()]
    if not prose.strip():
        return ""
    prose = re.sub(r'\*{1,2}([^*]+?)\*{1,2}', r'\1', prose)
    prose = re.sub(r'\[SCENE:.*?\]', '', prose)

    # Drop mechanics lines wherever they sit. The old scaffold fenced the
    # surface behind a --- separator; the v5 master prompt emits tagged lines
    # inline, so splitting alone let NEEDED and VITALS through to be read out.
    kept = []
    in_fence = False
    for line in prose.splitlines():
        s = line.strip()
        if s.startswith("```"):
            # Toggle rather than skip-and-continue-past: a fenced block (the
            # combat-state grid, most often) is dropped whole, not just its
            # delimiter lines -- the plain-text rows inside it aren't prefixed
            # with "|" and were sailing straight through to be read aloud.
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if not s:
            continue
        if MECH_LINE.match(s) or s.startswith(("|", "> ")):
            continue
        if OPTION_LINE.match(s):
            continue
        if set(s) <= set("-=_ "):        # rules and separators
            continue
        kept.append(line)
    prose = "\n".join(kept)

    prose = re.sub(r'\n{2,}', '\n', prose)
    prose = re.sub(r'[ \t]{2,}', ' ', prose)
    return prose.strip()


# A voice spec is one of three things:
#
#   "am_michael"                    a stock Kokoro voice
#   "piper:en_US-libritts-high#707" one speaker of a multi-speaker Piper model
#   "fit:joe"                       a style vector fitted to a real recording
#
# The Piper form is what makes the ~1,040 speakers in the multi-speaker models
# addressable; without it those models are on disk but uncastable. The fit form
# is what lifts the cast past Kokoro's 28 English voices: tools/fit_voice.py
# solves for the blend of stock voices closest to a recording, and any spec
# accepting a Kokoro name accepts a fitted one, so an NPC in character_voices
# can use it exactly like a stock voice.
PIPER_SPEC = re.compile(r"^piper:([A-Za-z0-9_\-]+)#(\d+)$")
FIT_SPEC = re.compile(r"^fit:([A-Za-z0-9_\-]+)$")
_piper_models = {}


def _piper_voice(model_name):
    """Load and cache a Piper model. Loading costs ~2s, so never per chunk."""
    if model_name not in _piper_models:
        from piper import PiperVoice
        path = BOT / "voices" / f"{model_name}.onnx"
        if not path.exists():
            raise FileNotFoundError(f"piper model not found: {path}")
        _piper_models[model_name] = PiperVoice.load(str(path))
    return _piper_models[model_name]


def synthesize_piper_sid(text, model_name, speaker_id):
    """One speaker of a multi-speaker Piper model. Returns (pcm, sample_rate)."""
    from piper import SynthesisConfig
    v = _piper_voice(model_name)
    chunks = list(v.synthesize(text, SynthesisConfig(speaker_id=int(speaker_id))))
    if not chunks:
        return b"", 22050
    pcm = b"".join(c.audio_int16_bytes for c in chunks)
    return pcm, chunks[0].sample_rate


KOKORO_DIR = BOT / "voices" / "kokoro"
KOKORO_RATE = 24000
_kokoro = None


def _kokoro_engine():
    """Load Kokoro once per process. ~4s on this Mac, so never per sentence."""
    global _kokoro
    if _kokoro is None:
        from kokoro_onnx import Kokoro
        _kokoro = Kokoro(str(KOKORO_DIR / "kokoro-v1.0.onnx"),
                         str(KOKORO_DIR / "voices-v1.0.bin"))
    return _kokoro


FITTED_DIR = KOKORO_DIR.parent / "fitted"
_fitted = {}


def _fitted_voice(name):
    """Load a fitted style vector, cached.

    These are campaign assets, not downloads: each one is a solve against a
    recording that cannot be reproduced without the original clip, which is why
    voices/fitted/ is deliberately not gitignored the way voices/kokoro/ is.

    Kokoro wants (510, 1, 256); fit_voice.py writes (510, 256).
    """
    if name not in _fitted:
        import numpy as np
        path = FITTED_DIR / f"{name}.npy"
        if not path.exists():
            raise FileNotFoundError(
                f"fitted voice not found: {path}\n"
                f"    build one with: python3 tools/fit_voice.py REF.wav --name {name}")
        v = np.load(path).astype(np.float32)
        if v.shape == (510, 256):
            v = v.reshape(510, 1, 256)
        if v.shape != (510, 1, 256):
            raise ValueError(f"{path}: expected (510, 256), got {v.shape}")
        _fitted[name] = v
    return _fitted[name]


def resolve_kokoro_voice(voice):
    """A stock name passes through; 'fit:NAME' becomes its style vector."""
    spec = FIT_SPEC.match(str(voice))
    return _fitted_voice(spec.group(1)) if spec else voice


def synthesize_kokoro(text: str, voice: str, speed: float) -> bytes:
    """Kokoro to raw S16LE PCM mono at KOKORO_RATE.

    Better prose than Piper, and about thirty times slower: roughly 1x real
    time on this Intel CPU against Piper's 0.03x. That cost is why speak()
    streams sentence by sentence instead of synthesising a whole post first.
    """
    import numpy as np
    samples, sr = _kokoro_engine().create(text, voice=resolve_kokoro_voice(voice),
                                          speed=speed, lang="en-us")
    if sr != KOKORO_RATE:
        raise RuntimeError(f"unexpected Kokoro sample rate {sr}")
    return (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2").tobytes()


# A dialogue line is "Name: what they said" at the start of a line. Anything
# without a prefix is narration and stays in the narrator's voice.
_SPEAKER = re.compile(r"^\s*\*{0,2}([A-Z][A-Za-z0-9'\- ]{0,24})\*{0,2}\s*:\s+(.*)$")


def parse_speakers(text, character_voices, narrator):
    """Split prose into (voice, line) segments by speaker prefix.

    Consecutive lines from the same speaker merge, so a paragraph of one
    character talking is still synthesised as one pass. An unknown name falls
    back to the narrator rather than being guessed at, and the prefix is kept
    in that case so the listener still hears who is speaking.
    """
    segments = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = _SPEAKER.match(line)
        if m and m.group(1).strip() in character_voices:
            voice, said = character_voices[m.group(1).strip()], m.group(2).strip()
        elif m and m.group(1).strip().lower() in ("dm", "narrator"):
            voice, said = narrator, m.group(2).strip()
        else:
            voice, said = narrator, line
        if segments and segments[-1][0] == voice:
            segments[-1] = (voice, f"{segments[-1][1]} {said}")
        else:
            segments.append((voice, said))
    return segments


# Sentence splitting for speech, which is stricter than for text: every split
# becomes an audible pause, so a false positive is heard as a stumble
# mid-sentence ("toward Mr. / Tomm's old shop").
#
# Never break after: a known abbreviation, a single capital initial ("V."), or
# a digit (so "98,514.5 gp." and "gp. approximately" stay intact). Only break
# when the next character starts something that looks like a new sentence.
_ABBREV = (r"Mr|Mrs|Ms|Dr|Prof|St|Sgt|Capt|Lt|Rev|Hon|Jr|Sr|vs|etc|"
           r"e\.g|i\.e|cf|approx|no|vol|pp|gp|sp|cp|pp|ft|lb|DC|HP|AC")
_SENT = re.compile(
    r"(?<=[.!?])[\"\u201d\')\]]*\s+(?=[\"\u201c\'(\[]*[A-Z0-9])"
)
_NOSPLIT = re.compile(r"(?:\b(?:" + _ABBREV + r")|\b[A-Z]|\d)\.$", re.I)


def _sentences(text):
    """Split into sentences, refusing breaks that are not real terminators."""
    out, start = [], 0
    for m in _SENT.finditer(text):
        head = text[start:m.start()]
        if _NOSPLIT.search(head.rstrip()):
            continue                      # abbreviation or initial, not an end
        out.append(head)
        start = m.end()
    tail = text[start:]
    if tail.strip():
        out.append(tail)
    return out


def split_sentences(text: str, min_len: int = 40):
    """Group prose into chunks of at least min_len chars, split on sentences.

    Chunking is what makes a ~1x real-time engine usable live: the first
    sentence starts playing while the rest is still being generated, so the
    listener waits seconds rather than the length of the whole passage.
    """
    out, buf = [], ""
    for part in _sentences(text.strip()):
        buf = f"{buf} {part}".strip() if buf else part
        if len(buf) >= min_len:
            out.append(buf); buf = ""
    if buf:
        if out:
            out[-1] = f"{out[-1]} {buf}"
        else:
            out.append(buf)
    return out


def synthesize(text: str, voice: str, rate: int, speed: float) -> bytes:
    """Run text through Piper, return raw S16LE PCM bytes at `rate` Hz mono.

    `speed` is a fraction of normal pace (0.9 = 90% speed); piper's
    length-scale scales phoneme duration, so it's the inverse of speed.
    """
    length_scale = 1.0 / speed
    piper = subprocess.run(
        _piper_cmd() + ["--model", voice, "--output-raw",
                        "--length-scale", str(length_scale)],
        input=text.encode(),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    return piper.stdout


# ── Voice download ────────────────────────────────────────────────────

_VOICE_LIST = [
    ("en_US-lessac-high", "neutral, high quality, most natural in the Piper catalog"),
    ("en_US-amy-medium", "female, neural quality"),
    ("en_US-danny-low", "male, lower quality"),
]
_VOICE_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US"


def download_voices():
    import urllib.request
    VOICES_DIR.mkdir(parents=True, exist_ok=True)
    for name, desc in _VOICE_LIST:
        model_file = VOICES_DIR / f"{name}.onnx"
        config_file = VOICES_DIR / f"{name}.onnx.json"
        voice_dir = name.split("-")[1]
        quality = name.split("-")[2]
        base = f"{_VOICE_BASE}/{voice_dir}/{quality}"
        if not model_file.exists():
            print(f"[TTS] Downloading {name} ({desc})...")
            urllib.request.urlretrieve(f"{base}/{name}.onnx", str(model_file))
            urllib.request.urlretrieve(f"{base}/{name}.onnx.json", str(config_file))
            print(f"[TTS]   Done: {model_file}")
        else:
            print(f"[TTS] {name} already downloaded.")
    print("[TTS] All voices ready.")


# ── Discord voice client ────────────────────────────────────────────

class TTSClient(discord.Client):
    def __init__(self, *, voice_channel_id, voice_model, rate, speed,
                 engine="piper", kokoro_voice="af_heart",
                 character_voices=None, pronunciation_overrides=None, **kwargs):
        super().__init__(**kwargs)
        self.voice_channel_id = voice_channel_id
        self.voice_model = voice_model
        self.rate = rate
        self.speed = speed
        self.engine = engine
        self.kokoro_voice = kokoro_voice
        self.character_voices = character_voices or {}
        self.pronunciation_overrides = pronunciation_overrides or {}
        self._announced = set()
        self.voice_client = None
        self.cursor = self._read_cursor()
        self.last_spoken = ""

    def _read_cursor(self):
        if CURSOR.exists():
            try:
                return int(CURSOR.read_text().strip())
            except ValueError:
                return 0
        return 0

    def _write_cursor(self, cursor):
        CURSOR.write_text(str(cursor))

    async def on_ready(self):
        if self.engine == "kokoro":
            # Load before the first line of the session, not during it. The
            # model costs ~4s to load and that would otherwise land as dead
            # air on the opening narration.
            print("[TTS] warming Kokoro...")
            await asyncio.to_thread(_kokoro_engine)
            # Resolve every fitted voice now. A typo in a cast list would
            # otherwise surface as a stack trace mid-session, on the line where
            # that NPC first speaks.
            for spec in [self.kokoro_voice, *self.character_voices.values()]:
                if FIT_SPEC.match(str(spec)):
                    _fitted_voice(FIT_SPEC.match(str(spec)).group(1))
                    print(f"[TTS]   fitted voice loaded: {spec}")
            # Loading the model is still not enough: the first synthesis of the
            # process pays a one-off graph compile that measured at ~85s on
            # this Mac, against ~1.4s for every call after it. Spend it here,
            # on a throwaway line nobody hears, instead of on the opening
            # narration while the table waits.
            await asyncio.to_thread(synthesize_kokoro, "Warming up.",
                                    self.kokoro_voice, self.speed)
            print(f"[TTS] Kokoro ready, voice {self.kokoro_voice}")
        print(f"[TTS] Logged in as {self.user}")
        channel = self.get_channel(self.voice_channel_id)
        if channel is None:
            print(f"[TTS] Voice channel {self.voice_channel_id} not found or not visible to the bot.")
            return
        self.voice_client = await channel.connect()
        print(f"[TTS] Connected to voice channel: {channel.name}")
        if not self.poll_outbox.is_running():
            self.poll_outbox.start()

    async def speak(self, text: str):
        if not text or len(text) < 10 or self.voice_client is None:
            return
        rate = KOKORO_RATE if self.engine == "kokoro" else self.rate
        if self.engine == "kokoro":
            # Map speakers to voices first, then chunk inside each speaker's
            # run, so a voice change never happens mid-sentence.
            plan = []
            for voice, said in parse_speakers(text, self.character_voices,
                                              self.kokoro_voice):
                said = apply_pronunciation(said, self.pronunciation_overrides)
                plan += [(voice, c) for c in split_sentences(said)]
        else:
            plan = [(self.voice_model, apply_pronunciation(text, self.pronunciation_overrides))]
        for chunk_voice, chunk in plan:
            spec = PIPER_SPEC.match(str(chunk_voice))
            if spec:
                # Piper multi-speaker: its own model and its own sample rate.
                pcm, chunk_rate = await asyncio.to_thread(
                    synthesize_piper_sid, chunk, spec.group(1), spec.group(2))
            elif self.engine == "kokoro":
                pcm = await asyncio.to_thread(
                    synthesize_kokoro, chunk, chunk_voice, self.speed)
                chunk_rate = KOKORO_RATE
            else:
                pcm = await asyncio.to_thread(
                    synthesize, chunk, self.voice_model, self.rate, self.speed)
                chunk_rate = self.rate
            if not pcm:
                print(f"[TTS] no audio for a chunk ({chunk_voice}), skipping.")
                continue
            if chunk_voice not in self._announced:
                self._announced.add(chunk_voice)
                print(f"[TTS]   voice in use: {chunk_voice}")
            source = discord.FFmpegPCMAudio(
                io.BytesIO(pcm),
                pipe=True,
                executable=_ffmpeg_exe(),
                before_options=f"-f s16le -ar {chunk_rate} -ac 1",
                options="-loglevel warning",
            )
            while self.voice_client.is_playing():
                await asyncio.sleep(0.05)
            self.voice_client.play(source)
        while self.voice_client.is_playing():
            await asyncio.sleep(0.2)

    @tasks.loop(seconds=POLL_SECONDS)
    async def poll_outbox(self):
        if not OUTBOX.exists():
            return
        lines = OUTBOX.read_text().strip().splitlines()
        new_lines = lines[self.cursor:]
        if not new_lines:
            return
        for line in new_lines:
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            channel = msg.get("channel", "game")
            if channel not in ("game", "ooc"):
                continue
            spoken = extract_narration(msg.get("content", ""))
            if spoken and spoken != self.last_spoken:
                print(f"[TTS] speaking ({channel}): {spoken[:100]}...")
                await self.speak(spoken)
                self.last_spoken = spoken
        self.cursor = len(lines)
        self._write_cursor(self.cursor)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--voice", default=DEFAULT_VOICE)
    parser.add_argument("--rate", type=int, default=DEFAULT_RATE)
    parser.add_argument("--speed", type=float, default=DEFAULT_SPEED,
                        help="fraction of normal speaking pace (0.9 = 90%% speed)")
    parser.add_argument("--engine", choices=("piper", "kokoro"), default="kokoro",
                        help="kokoro sounds better, piper is ~30x faster on CPU")
    parser.add_argument("--kokoro-voice", default=None,
                        help="narrator voice; overrides NARRATOR_VOICE in .env "
                             "(af_heart is the default; am_michael, bm_george, and others)")
    parser.add_argument("--download", action="store_true",
                        help="Download Piper voice models (one-time setup)")
    args = parser.parse_args()

    if args.download:
        download_voices()
        return 0

    if not Path(args.voice).exists():
        print(f"[TTS] Voice model not found: {args.voice}")
        return 1

    env = load_env(ENV_PATH)
    token = env.get("DISCORD_TOKEN")
    if not token:
        print("[TTS] No DISCORD_TOKEN in bot/.env")
        return 1
    channel_id = env.get("TTS_VOICE_CHANNEL_ID")
    if not channel_id:
        print("[TTS] No TTS_VOICE_CHANNEL_ID in bot/.env")
        return 1

    intents = discord.Intents.default()
    character_voices = {}
    for pair in env.get("CHARACTER_VOICES", "").split(","):
        if ":" in pair:
            name, voice = pair.split(":", 1)
            character_voices[name.strip()] = voice.strip()
    if character_voices:
        print(f"[TTS] character voices: {character_voices}")

    pronunciation_overrides = {}
    for pair in env.get("PRONUNCIATION_OVERRIDES", "").split(","):
        if ":" in pair:
            name, phonetic = pair.split(":", 1)
            pronunciation_overrides[name.strip()] = phonetic.strip()
    if pronunciation_overrides:
        print(f"[TTS] pronunciation overrides: {pronunciation_overrides}")

    # The cast belongs in .env with the rest of the campaign's config, so a
    # session starts with no arguments. An explicit flag still wins.
    narrator = args.kokoro_voice or env.get("NARRATOR_VOICE") or "af_heart"

    client = TTSClient(
        voice_channel_id=int(channel_id),
        voice_model=args.voice,
        rate=args.rate,
        speed=args.speed,
        engine=args.engine,
        kokoro_voice=narrator,
        character_voices=character_voices,
        pronunciation_overrides=pronunciation_overrides,
        intents=intents,
    )
    client.run(token)
    return 0


if __name__ == "__main__":
    sys.exit(main())
