"""relay.py -- Discord <-> mailbox relay for a dnd-dm campaign (campaign-agnostic; ships with the skill).
No LLM calls, no game-engine calls: only moves messages between the campaign's
Discord channels and the mailbox (inbox.jsonl + outbox.jsonl).
Everything campaign-specific lives in bot/.env (see .env.example); the code is the
same in every campaign. Copy this file into the campaign's bot/ folder.
Run: python bot/relay.py   (or bot/start_session.sh)
"""

import os
import sys
import json
import time

RELAY_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(RELAY_DIR, ".env")


def mailbox_dir():
    """Where inbox.jsonl and outbox.jsonl live: MAILBOX_DIR in .env if set, else bot/mailbox/ when that folder
    exists, else bot/ itself. Campaigns set up either way keep working unchanged."""
    raw = ""
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, encoding="utf-8-sig") as fh:
            for line in fh:
                if line.strip().startswith("MAILBOX_DIR="):
                    raw = line.split("=", 1)[1].strip()
    if raw:
        return raw if os.path.isabs(raw) else os.path.join(RELAY_DIR, raw)
    sub = os.path.join(RELAY_DIR, "mailbox")
    return sub if os.path.isdir(sub) else RELAY_DIR


MAILBOX = mailbox_dir()
INBOX_PATH = os.path.join(MAILBOX, "inbox.jsonl")
OUTBOX_PATH = os.path.join(MAILBOX, "outbox.jsonl")
CURSOR_PATH = os.path.join(MAILBOX, ".outbox-cursor")
# The dice engine's ledger (world dice), posted independently of the DM.
LEDGER_DEFAULT = os.path.join(RELAY_DIR, "..", "dice", "ledger" + ".jsonl")
LEDGER_CURSOR_PATH = os.path.join(MAILBOX, ".ledger-cursor")

POLL_SECONDS = 2
CHUNK_LIMIT = 1900


def load_env(path):
    """Minimal .env parser, utf-8-sig tolerant. Returns a dict of KEY=VALUE."""
    values = {}
    if not os.path.exists(path):
        return values
    with open(path, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            values[key.strip()] = val.strip()
    return values


def chunk_text(text, limit=CHUNK_LIMIT):
    """Split text into chunks <= limit chars, breaking at line breaks. Pure."""
    if len(text) <= limit:
        return [text]
    chunks = []
    remaining = text
    while len(remaining) > limit:
        split_at = remaining.rfind("\n", 0, limit)
        if split_at <= 0:
            split_at = limit
        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:].lstrip("\n")
    if remaining:
        chunks.append(remaining)
    return chunks


def read_new_outbox_messages(outbox_path, cursor_path):
    """Read lines appended to outbox_path since the offset in cursor_path.
    Returns (messages, new_offset); messages is a list of chunk-lists, one
    per outbox line. Does not write anything -- caller persists new_offset.
    """
    if not os.path.exists(outbox_path):
        return [], _read_cursor(cursor_path)

    offset = _read_cursor(cursor_path)
    with open(outbox_path, "rb") as f:
        f.seek(offset)
        new_data = f.read()
        new_offset = f.tell()

    messages = []
    for raw_line in new_data.decode("utf-8").splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            obj = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        content = obj.get("content", "")
        file_path = obj.get("file")
        channel_name = obj.get("channel", "game")
        if content or file_path:
            # channel: "game" (default), "ooc", or a bubble PC name ("Rhogast", "Oliver", "Roy")
            # file: optional local path uploaded as a Discord attachment
            chunks = chunk_text(content) if content else []
            messages.append((channel_name, chunks, file_path))

    return messages, new_offset


def _read_cursor(cursor_path):
    if not os.path.exists(cursor_path):
        return 0
    try:
        with open(cursor_path, "r", encoding="utf-8") as f:
            return int(f.read().strip() or 0)
    except (ValueError, OSError):
        return 0


def write_cursor(cursor_path, offset):
    with open(cursor_path, "w", encoding="utf-8") as f:
        f.write(str(offset))


def append_inbox_message(inbox_path, author, content, ts=None, channel="game",
                          attachments=None):
    """Append one player message to the inbox as a JSON line.

    attachments, if given, is a list of {"filename": str, "url": str} dicts.
    The relay can't read file/image contents, only note that something was
    attached and where to fetch it, so the DM can flag it instead of the
    message silently looking text-only.
    """
    record = {"ts": ts if ts is not None else time.time(), "author": author,
              "content": content, "channel": channel}
    if attachments:
        record["attachments"] = attachments
    with open(inbox_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def main():
    env = load_env(ENV_PATH)
    token = env.get("DISCORD_TOKEN", "")
    channel_id_raw = env.get("ALLOWED_CHANNEL_ID", "")
    ooc_id_raw = env.get("OOC_CHANNEL_ID", "")
    bubble_raw = env.get("BUBBLE_CHANNELS", "")
    player_raw = env.get("PLAYER_MAP", "")

    import dice
    import ledger_feed
    ledger_path = env.get("LEDGER_PATH", "") or LEDGER_DEFAULT
    dice_id_raw = env.get("DICE_CHANNEL_ID", "")
    dice_channel_id = int(dice_id_raw) if dice_id_raw.strip().isdigit() else None
    guard_state = {"off": None}  # None until the first poll reads it
    player_map = {}
    for pair in player_raw.split(","):
        if ":" in pair:
            k, v = pair.split(":", 1)
            player_map[k.strip().lower()] = v.strip()
    # Outstanding **NEEDED:** requests from the DM's most recent post, which is
    # what %rollgo answers. Cleared when the DM posts again with no request.
    pending_rolls = []

    if not token or not channel_id_raw:
        print("relay.py: DISCORD_TOKEN or ALLOWED_CHANNEL_ID missing from bot/.env")
        sys.exit(1)

    try:
        channel_id = int(channel_id_raw)
    except ValueError:
        print("relay.py: ALLOWED_CHANNEL_ID is not a valid integer")
        sys.exit(1)

    # OOC channel (the DM's office) is optional — relay runs game-only without it
    ooc_channel_id = None
    if ooc_id_raw:
        try:
            ooc_channel_id = int(ooc_id_raw)
        except ValueError:
            print("relay.py: OOC_CHANNEL_ID is not a valid integer (ignoring)")

    # DM room (Joe only): the roll logs, collapsed block, full LOOP and notes that dm_post.py
    # keeps out of the game channel. Never falls through to the game channel.
    dm_channel_id = None
    dm_id_raw = env.get("DM_CHANNEL_ID", "")
    if dm_id_raw.strip().isdigit():
        dm_channel_id = int(dm_id_raw)
    else:
        print("relay.py: DM_CHANNEL_ID is not set. Rows for the dm room will be dropped, never posted to the game channel.")
    if not (dice_channel_id):
        print("relay.py: DICE_CHANNEL_ID is not set. Dice reports will land in the game channel.")

    # Bubble channels: "Rhogast:123,Oliver:456,Roy:789"
    bubble_channel_ids = {}
    if bubble_raw:
        for pair in bubble_raw.split(","):
            pair = pair.strip()
            if ":" in pair:
                name, cid = pair.split(":", 1)
                try:
                    bubble_channel_ids[name.strip()] = int(cid.strip())
                except ValueError:
                    print(f"relay.py: invalid bubble channel ID for {name}")

    import asyncio

    import discord
    from discord.ext import tasks

    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    # Typing indicator: when a prompt lands, the bot "types" until the DM's
    # reply posts to that room, so players know the message was received.
    # pending[room] holds the timestamp of the oldest unanswered prompt
    # (0 = nothing pending); typing_tasks holds the live keepalive task.
    TYPING_MAX_SECONDS = 600
    pending = {"game": 0.0, "ooc": 0.0}
    for _name in bubble_channel_ids:
        pending[_name] = 0.0
    typing_tasks = {}

    # Reverse map: Discord channel id -> bubble room name (the PC's name)
    bubble_rooms = {cid: name for name, cid in bubble_channel_ids.items()}

    def wants_typing(room, content):
        """A game prompt is a %dm turn or %rollgo; office and bubble messages all count."""
        if room != "game":
            return True
        stripped = content.lstrip()
        return stripped.startswith("%dm") or stripped.startswith("%rollgo")

    async def keep_typing(channel, room):
        """Hold the typing indicator until the room's pending flag clears."""
        started = time.time()
        try:
            async with channel.typing():
                while pending[room] and (time.time() - started) < TYPING_MAX_SECONDS:
                    await asyncio.sleep(2)
        except Exception:
            pass
        finally:
            typing_tasks.pop(room, None)

    @client.event
    async def on_ready():
        print(f"relay.py: logged in as {client.user} (watching channel {channel_id})")
        if not outbox_poll.is_running():
            outbox_poll.start()

    @client.event
    async def on_message(message):
        if message.author.id == client.user.id:
            return
        if message.channel.id == channel_id:
            room = "game"
        elif ooc_channel_id is not None and message.channel.id == ooc_channel_id:
            room = "ooc"
        elif message.channel.id in bubble_rooms:
            # A player's private bubble channel: the room IS the PC's name.
            room = bubble_rooms[message.channel.id]
        else:
            return
        raw = (message.content or "").strip()
        if raw.startswith("%"):
            cmd, _, cmd_args = raw[1:].partition(" ")
            cmd = cmd.lower()
            if cmd in ("roll", "rollgo", "dice", "help"):
                pc = dice.resolve_pc(str(message.author.display_name), player_map)
                if cmd == "roll":
                    for_dm, public = dice.cmd_roll(pc, cmd_args)
                elif cmd == "rollgo":
                    for_dm, public = dice.cmd_rollgo(pc, pending_rolls)
                else:
                    for_dm, public = None, dice.HELP
                await message.channel.send(public)
                if for_dm:
                    # The DM sees the number as a normal inbound line, so the
                    # roll lands in the transcript the same way speech does.
                    append_inbox_message(INBOX_PATH, pc, for_dm, channel=room)
                    if cmd == "rollgo":
                        pending_rolls.clear()
                return

        attachments = [{"filename": a.filename, "url": a.url}
                       for a in message.attachments] or None
        append_inbox_message(INBOX_PATH, str(message.author.display_name),
                             message.content, channel=room,
                             attachments=attachments)
        if wants_typing(room, message.content):
            pending[room] = time.time()
            if room not in typing_tasks:
                typing_tasks[room] = asyncio.create_task(
                    keep_typing(message.channel, room))

    @tasks.loop(seconds=POLL_SECONDS)
    async def outbox_poll():
        game_channel = client.get_channel(channel_id)
        ooc_channel = client.get_channel(ooc_channel_id) if ooc_channel_id else None
        dm_channel = client.get_channel(dm_channel_id) if dm_channel_id else None
        # Resolve bubble channels lazily each poll (they may not be cached yet)
        bubble_channels = {}
        for name, cid in bubble_channel_ids.items():
            ch = client.get_channel(cid)
            if ch:
                bubble_channels[name] = ch
        if game_channel is None:
            return
        # World dice first, straight from the engine ledger, so the table sees
        # the real rolls before the DM's narration of them lands.
        entries, warnings, ledger_state = ledger_feed.read_new_entries(
            ledger_path, LEDGER_CURSOR_PATH)
        dice_target = (client.get_channel(dice_channel_id) if dice_channel_id else None) or game_channel
        # Flag every change in the dice guard's state (and an OFF guard at startup).
        guard_off = ledger_feed.guard_is_off()
        if guard_state["off"] != guard_off:
            if guard_off or guard_state["off"] is not None:
                await dice_target.send(ledger_feed.guard_notice(guard_off))
            guard_state["off"] = guard_off
        for warning in warnings:
            await dice_target.send(warning)
        feed = ledger_feed.format_entries(entries, dice.BOT_IDS)
        if feed:
            for chunk in chunk_text(feed):
                await dice_target.send(chunk)
        if ledger_state is not None:
            ledger_feed.write_state(LEDGER_CURSOR_PATH, ledger_state)
        messages, new_offset = read_new_outbox_messages(OUTBOX_PATH, CURSOR_PATH)
        if messages:
            # Refresh the roll gate from what the DM just posted. A post with
            # no **NEEDED:** line clears it, so %rollgo can never answer a
            # request that has already been resolved.
            gate = []
            for _room, _chunks, _fp in messages:
                gate.extend(dice.parse_needed("\n".join(_chunks)))
            pending_rolls.clear()
            pending_rolls.extend(gate)
            for room, chunks, file_path in messages:
                if room == "dm":
                    if not dm_channel:
                        print("relay.py: dm room row dropped (DM_CHANNEL_ID unset or not visible to the bot)")
                        continue
                    target = dm_channel
                elif room == "ooc" and ooc_channel:
                    target = ooc_channel
                elif room in bubble_channels:
                    target = bubble_channels[room]
                elif room in bubble_channel_ids:
                    # Named bubble whose channel would not resolve. Never fall
                    # through to the public game channel: private content stays
                    # private, even at the cost of dropping the message.
                    print(f"relay.py: bubble channel for {room} did not resolve, message dropped")
                    continue
                else:
                    target = game_channel
                for i, chunk in enumerate(chunks):
                    # attach the file to the last text chunk so caption and
                    # image land as one Discord message
                    if file_path and i == len(chunks) - 1:
                        await _send_with_file(target, chunk, file_path)
                        file_path = None
                    else:
                        await target.send(chunk)
                if file_path:  # file-only entry, or attach failed over to here
                    await _send_with_file(target, None, file_path)
                # The DM has spoken in this room: stop the typing indicator.
                if target is ooc_channel:
                    pending["ooc"] = 0
                elif target is game_channel:
                    pending["game"] = 0
                elif room in pending:
                    pending[room] = 0
            write_cursor(CURSOR_PATH, new_offset)

    async def _send_with_file(target, content, file_path):
        if os.path.exists(file_path):
            await target.send(content, file=discord.File(file_path))
        else:
            note = f"(attachment missing on disk: {os.path.basename(file_path)})"
            await target.send(f"{content}\n{note}" if content else note)

    client.run(token)


if __name__ == "__main__":
    main()
