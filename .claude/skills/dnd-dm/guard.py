#!/usr/bin/env python3
"""PreToolUse guard for the world-dice ledger.

Claude Code runs this before every tool call. It blocks any tool call that
could write the ledger, the signing key, the engine, this guard, the guard
switch, or the Claude Code settings that install this guard. So the only way
a ledger entry comes into being is `roll.py` rolling a real die, and the model
cannot switch the guard off by editing settings.

Rules:
  - Nothing may touch ~/.dnd-dice (the key, head records, and the guard switch).
  - Read, Grep, and Glob may read the ledger, the engine, and settings (reading
    proves nothing and harms nothing), but never ~/.dnd-dice.
  - Bash may run roll.py. With every roll.py invocation removed, the rest of
    the command may not mention the ledger, the engine, the guard, the switch,
    ~/.dnd-dice, or a Claude Code settings file.
  - Every other tool (Write, Edit, MultiEdit, NotebookEdit, any MCP tool) may
    not touch any of those paths at all.

Unlocking is Joe's alone, from his own Terminal:
    python3 ~/.dnd-dice/dice-guard off     (and `on` to lock again)
While unlocked, every call that would have been blocked goes through with a
visible warning, the switch logs the change to the ledger, and the Discord
relay announces it to the table.

Exit code 2 blocks the tool call and shows the reason to the model.
"""
import json
import os
import re
import sys

UNLOCK_FLAG = os.path.expanduser("~/.dnd-dice/UNLOCKED")
READ_ONLY = {"Read", "Grep", "Glob"}
INVOKE = re.compile(r"""python3?\s+(?:"[^"]*roll\.py"|'[^']*roll\.py'|\S*roll\.py)""")
PROTECTED = re.compile(
    r"ledger\.jsonl|roll\.py|guard\.py|dice-guard|\.dnd-dice|\.claude/settings[^/\s]*\.json", re.I)
KEY_DIR = re.compile(r"\.dnd-dice", re.I)


def paths(obj, key=""):
    """Every string under a key that names a location (path, file, dir, cwd).

    Content fields (a file's new text, an edit's replacement) are not checked:
    writing the words "roll.py" into a document is harmless.
    """
    if isinstance(obj, str):
        if re.search(r"path|file|dir|cwd|target|dest", key, re.I):
            yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from paths(v, k)
    elif isinstance(obj, list):
        for v in obj:
            yield from paths(v, key)


def verdict(tool, inp):
    """None if allowed, else the reason it would be blocked."""
    home = os.path.expanduser("~")
    if tool == "Bash":
        rest = INVOKE.sub(" ", inp.get("command", "")).replace(home, "~")
        if PROTECTED.search(rest):
            return ("this shell command touches the ledger, the key, the engine, the guard, "
                    "or Claude Code's settings outside a roll.py call.")
        return None
    text = "\n".join(paths(inp)).replace(home, "~")
    if KEY_DIR.search(text):
        return "~/.dnd-dice holds the signing key, head records, and the guard switch."
    if tool in READ_ONLY:
        return None
    if PROTECTED.search(text):
        return f"{tool} may not touch the ledger, the engine, the guard, or Claude Code's settings."
    return None


def main():
    try:
        call = json.load(sys.stdin)
    except Exception:
        return 0
    why = verdict(call.get("tool_name", ""), call.get("tool_input", {}) or {})
    if why is None:
        return 0
    if os.path.exists(UNLOCK_FLAG):
        print(json.dumps({"systemMessage": f"DICE GUARD IS OFF (Joe unlocked it). Normally blocked, allowed now: {why}"}))
        return 0
    print(f"BLOCKED by the dice-ledger guard: {why} Only roll.py writes the ledger. "
          f"Roll the die through the engine instead.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
