# The live-table bot (campaign-agnostic)

Ships with the dnd-dm skill. Every campaign's `bot/` folder holds a copy of this code plus its own data.
**Never edit a campaign's copy:** fix it here and sync it out, so every campaign plays by the same code.

| File | What it does |
|---|---|
| `relay.py` | Moves messages between Discord and the mailbox (`inbox.jsonl`, `outbox.jsonl`). It posts the DM's response split into rooms by `dm_post.py`: the game room, the private DM room, the bubbles, and the dice room fed from the dice ledger. |
| `ledger_feed.py` | Reads the dice ledger for the dice room and checks every entry's signature and chain itself. |
| `dice.py` | The players' `%roll` and `%rollgo` commands. |
| `tts_bridge.py` | Speaks the narration into the voice channel (Kokoro, or Piper as a fallback), with a voice per character and pronunciation fixes. |
| `voice.py` + `voice_catalogue.json` | Voice casting: find a Kokoro voice by description ("old gravelly man"), or mint a blend. |
| `start_session.sh` | Preflight checks (config, dependencies, voice models), a clean restart of only this campaign's processes, a cursor fast-forward so last session isn't read aloud, then launch and health check. `--check` checks only; `--stop` stops. |
| `start_bot.sh`, `start_tts.sh` | Start one process by hand. |
| `requirements.txt`, `.env.example` | Dependencies, and the template for `bot/.env`. |

## What stays the campaign's own (never overwritten by a sync)

- `bot/.env`: the token, channels, cast and narrator.
- `bot/voices/`: the voice models and fitted voices.
- The mailbox: `bot/mailbox/` or `bot/` itself, holding `inbox.jsonl`, `outbox.jsonl` and the cursors.
- Logs, and `bot/.venv/`.

## Setting up a new campaign

```bash
mkdir -p bot && cp ~/.claude/skills/dnd-dm/bot/* ~/.claude/skills/dnd-dm/bot/.env.example bot/
python3 -m venv bot/.venv && bot/.venv/bin/pip install -r bot/requirements.txt
cp bot/.env.example bot/.env
```

Then fill in `bot/.env`, put the Kokoro model in `bot/voices/kokoro/` (`kokoro-v1.0.onnx` and `voices-v1.0.bin`),
and run `bot/start_session.sh --check`.
