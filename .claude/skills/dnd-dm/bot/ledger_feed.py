"""ledger_feed.py -- posts the DM's world dice to Discord straight from the ledger.

The DM (Claude Code) rolls every world die through the dice engine, which
writes each roll to dice/ledger.jsonl in this repo. This module reads that
file directly and hands the relay ready-to-post lines. The AI never touches
this path: what players see here comes from the engine's own record, not from
the DM's prose, so a hallucinated roll in the narration has nothing to match.

Every entry is also checked here, independently of the DM:
  - its signature, using the engine's key (~/.dnd-dice/key), and
  - its link to the entry before it.
A failed check is posted to the table as a warning, loudly.

No LLM calls, no game rules. Read-only on the ledger.
"""

import hashlib
import hmac
import json
import os

KEY_PATH = os.path.expanduser("~/.dnd-dice/key")
UNLOCK_FLAG = os.path.expanduser("~/.dnd-dice/UNLOCKED")


def guard_is_off():
    """True while Joe's switch has the dice guard unlocked."""
    return os.path.exists(UNLOCK_FLAG)


def guard_notice(off):
    if off:
        return ("⚠️ **DICE GUARD IS OFF.** The AI can currently edit the dice engine and ledger. "
                "This should only happen during engine maintenance, never during play.")
    return "✅ **Dice guard is back ON.** Only the dice engine can write the ledger."


def _sign(entry, key):
    body = json.dumps({k: entry[k] for k in entry if k != "sig"},
                      sort_keys=True, separators=(",", ":"))
    return hmac.new(key, body.encode(), hashlib.sha256).hexdigest()


def _load_key():
    try:
        with open(KEY_PATH, "rb") as f:
            return f.read().strip()
    except OSError:
        return None


def read_state(cursor_path):
    try:
        with open(cursor_path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def write_state(cursor_path, state):
    with open(cursor_path, "w") as f:
        json.dump(state, f)


def _last_sig_before(ledger_path, offset):
    """The sig of the last complete entry that ends at or before offset."""
    last = "GENESIS"
    with open(ledger_path, "rb") as f:
        data = f.read(offset)
    for line in data.decode("utf-8", "replace").splitlines():
        if line.strip():
            try:
                last = json.loads(line).get("sig", last)
            except ValueError:
                pass
    return last


def read_new_entries(ledger_path, cursor_path):
    """Entries appended since the cursor.

    Returns (entries, warnings, new_state). On the very first run (no cursor)
    it starts at the current end of the ledger, so old history is not dumped
    into the channel. Only complete lines are consumed.
    """
    if not os.path.exists(ledger_path):
        return [], [], read_state(cursor_path)
    size = os.path.getsize(ledger_path)
    state = read_state(cursor_path)
    if state is None or state.get("path") != os.path.abspath(ledger_path):
        state = {"path": os.path.abspath(ledger_path), "offset": size,
                 "prev": _last_sig_before(ledger_path, size)}
        return [], [], state
    offset = state["offset"]
    if size < offset:
        warn = ("**LEDGER WARNING:** the dice ledger got shorter since the last check. "
                "Rolls were removed from it. Nothing the engine does removes rolls.")
        state = {"path": state["path"], "offset": size, "prev": _last_sig_before(ledger_path, size)}
        return [], [warn], state
    with open(ledger_path, "rb") as f:
        f.seek(offset)
        chunk = f.read()
    end = chunk.rfind(b"\n")
    if end < 0:
        return [], [], state
    lines = chunk[: end + 1].decode("utf-8", "replace").splitlines()
    key = _load_key()
    prev = state.get("prev", "GENESIS")
    entries, warnings = [], []
    for line in lines:
        if not line.strip():
            continue
        try:
            e = json.loads(line)
        except ValueError:
            warnings.append("**LEDGER WARNING:** a line in the dice ledger is not valid JSON. "
                            "The engine did not write it.")
            continue
        problems = []
        if e.get("prev") != prev:
            problems.append("its link to the previous roll is broken")
        if key is None:
            e["_unverified"] = True
        elif not hmac.compare_digest(_sign(e, key), e.get("sig", "")):
            problems.append("its signature does not match")
        if problems:
            warnings.append(f"**LEDGER WARNING at {e.get('id', '?')}:** " + " and ".join(problems)
                            + ". This roll was not made by the dice engine.")
        else:
            entries.append(e)
        prev = e.get("sig", prev)
    state = {"path": state["path"], "offset": offset + end + 1, "prev": prev}
    return entries, warnings, state


def _detail(e):
    if e.get("kind") == "pick":
        table = " · ".join(f"{t['outcome']} {t['weight']}" for t in e.get("table", []))
        return f"**{e['result']}**  (table: {table}; rolled {e.get('draw', '?')})"
    faces = e.get("faces", [])
    mod = e.get("mod", 0)
    spec = e.get("spec", "")
    shown = ",".join(str(x) for x in faces)
    if "adv" in spec or "dis" in spec:
        shown = f"{shown} {'adv' if 'adv' in spec else 'dis'}"
    if mod:
        shown = f"{shown}{'+' if mod > 0 else ''}{mod}"
    return f"**{e['result']}**  ({shown})"


def format_entries(entries, bot_ids=frozenset()):
    """Discord text for a batch of ledger entries (one message).

    `bot_ids` are the ledger IDs this bot rolled itself for %roll/%rollgo;
    those were already posted where the player rolled, so they are skipped.
    Any other entry labelled `player-` was not made by the bot, so it is
    posted with a warning: only the bot may use that label.
    """
    if not entries:
        return None
    rows = []
    for e in entries:
        if e.get("id") in bot_ids:
            continue
        if str(e.get("label", "")).startswith("player-"):
            rows.append(f"`{e['id']}` ⚠️ **labelled as a player roll, but the bot did not roll it:** "
                        f"{e.get('label')} {e.get('spec', '')} → {_detail(e)}")
            continue
        if e.get("kind") == "event":
            ev = e.get("event", "")
            if ev == "GUARD_OFF":
                rows.append(f"`{e['id']}` ⚠️ **dice guard switched OFF**")
            elif ev == "GUARD_ON":
                rows.append(f"`{e['id']}` ✅ dice guard switched back ON")
            else:
                rows.append(f"`{e['id']}` dice engine: {ev.replace('_', ' ').lower()}")
            continue
        spec = "" if e.get("kind") == "pick" else f" {e.get('spec', '')}"
        line = f"`{e['id']}` {e.get('label', 'roll')}{spec} → {_detail(e)}"
        if e.get("kind") == "pick" and any(t.get("weight", 1) != 1 for t in e.get("table", [])):
            line += "  · ⚠️ **WEIGHTED: the DM set the odds, which the fair dice rules forbid**"
        if e.get("reroll_of"):
            line += f"  · reroll of `{e['reroll_of']}` ({e.get('reason', '')})"
        if e.get("_unverified"):
            line += "  · (not signature-checked: no engine key on this machine)"
        rows.append(line)
    if not rows:
        return None
    head = "🎲 **World dice** (straight from the engine ledger, not from the DM)"
    return head + "\n" + "\n".join(rows)
