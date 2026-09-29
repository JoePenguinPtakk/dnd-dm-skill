#!/usr/bin/env python3
"""Joe's switch for the dice-ledger guard. Run it from your own Terminal.

    python3 ~/.dnd-dice/dice-guard off      unlock (for engine work only)
    python3 ~/.dnd-dice/dice-guard on       lock again
    python3 ~/.dnd-dice/dice-guard status   show which it is

Every change is flagged three ways:
  1. This script prints a banner.
  2. If a game session is open, the change is written into the dice ledger as
     a signed event, so the unlocked stretch shows in the record.
  3. The Discord relay notices and announces it to the table.

The guard itself blocks the AI from running or touching this file.
"""
import datetime as dt
import importlib.util
import json
import os
import sys

HOME = os.path.expanduser("~/.dnd-dice")
FLAG = os.path.join(HOME, "UNLOCKED")
ENGINE = os.path.expanduser("~/.claude/skills/dnd-dm/roll.py")


def log_event(event):
    """Write the change into the open session's ledger, if there is one."""
    try:
        spec = importlib.util.spec_from_file_location("roll", ENGINE)
        roll = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(roll)
        act = roll.active()
        if not act:
            return "no game session open, so nothing was written to a ledger"
        [r] = roll.append(roll.ledger_path(act), [{
            "kind": "event", "event": event, "session": act["session"],
            "label": "guard", "result": roll.now()}])
        return f"logged in the ledger as {r['id']}"
    except Exception as e:  # the flag still flips; say why the log did not
        return f"could not write to the ledger ({e})"


def banner(lines):
    width = max(len(l) for l in lines) + 4
    print("#" * width)
    for l in lines:
        print(f"# {l.ljust(width - 4)} #")
    print("#" * width)


def main(argv):
    cmd = argv[0] if argv else "status"
    os.makedirs(HOME, mode=0o700, exist_ok=True)
    unlocked = os.path.exists(FLAG)
    if cmd == "status":
        banner(["DICE GUARD IS OFF (unlocked)" if unlocked else "DICE GUARD IS ON (locked)"])
        return 0
    if cmd == "off":
        if unlocked:
            banner(["DICE GUARD WAS ALREADY OFF"])
            return 0
        with open(FLAG, "w") as f:
            f.write(json.dumps({"unlocked_at": dt.datetime.now().isoformat(timespec="seconds")}))
        note = log_event("GUARD_OFF")
        banner(["DICE GUARD IS NOW OFF", "The AI can edit the engine and the ledger.",
                "Turn it back on when the work is done:", "python3 ~/.dnd-dice/dice-guard on", note])
        return 0
    if cmd == "on":
        if not unlocked:
            banner(["DICE GUARD WAS ALREADY ON"])
            return 0
        os.remove(FLAG)
        note = log_event("GUARD_ON")
        banner(["DICE GUARD IS NOW ON", note])
        return 0
    print(__doc__.strip())
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
