#!/usr/bin/env python3
"""The dice engine for the v5 master prompt family.

Law 4 requires every DM roll to be produced by a real code execution rather
than a number the model wrote from its head, and §2 requires a generative
chain to resolve in ONE call. This script is that call.

Usage:
    python3 roll.py LABEL:SPEC [LABEL:SPEC ...]

SPEC forms:
    d20            one d20
    d20+5          one d20, +5 modifier
    2d6+3          two d6, +3 modifier
    d20adv+7       d20 with advantage (roll two, keep higher), +7
    d20dis         d20 with disadvantage (roll two, keep lower)
    d100           percentile

Examples:
    python3 roll.py attack:d20+5 damage:2d6+3
    python3 roll.py disturbance:d6 content:d100 quest-link:d6 intersection:d20
    python3 roll.py morale:d20+2 nemesis-reroll:d20+5

Output is a single line, already in the shape the DM ROLLS line wants, showing
every individual die so the result is auditable rather than merely asserted.

Randomness: every die is drawn from the OS entropy pool via `secrets`, not from
`random`. See `die()` below for why that distinction matters here.
"""
import re
import secrets
import sys

SPEC = re.compile(r"^(\d*)d(\d+)(adv|dis)?([+-]\d+)?$", re.I)


def die(sides):
    """One die, drawn from the OS entropy pool.

    Uses `secrets`, not `random`. `random` is a Mersenne Twister seeded once at
    import: it is reproducible, and an observer who learns the seed or enough
    consecutive outputs can predict the rest. `secrets.randbelow` draws from the
    operating system's CSPRNG, which is continuously reseeded from hardware
    entropy, and it rejects out-of-range draws rather than taking a modulo, so
    there is no bias toward the low faces.
    """
    return secrets.randbelow(sides) + 1


def roll_one(spec):
    m = SPEC.match(spec.strip())
    if not m:
        raise ValueError(f"unparseable dice spec: {spec!r}")
    count = int(m.group(1) or 1)
    sides = int(m.group(2))
    mode = (m.group(3) or "").lower()
    mod = int(m.group(4) or 0)

    if mode and (count != 1 or sides != 20):
        raise ValueError(f"advantage/disadvantage applies to a single d20: {spec!r}")

    if mode:
        pair = [die(20), die(20)]
        kept = max(pair) if mode == "adv" else min(pair)
        dice, shown = [kept], f"[{pair[0]},{pair[1]} {mode}]"
    else:
        dice = [die(sides) for _ in range(count)]
        shown = f"({','.join(str(d) for d in dice)})" if count > 1 else ""

    total = sum(dice) + mod
    detail = shown
    if mod:
        detail = f"{detail}{'+' if mod > 0 else ''}{mod}" if detail else f"({dice[0]}{'+' if mod > 0 else ''}{mod})"
    return total, detail


def main(argv):
    if not argv:
        print(__doc__.strip())
        return 2
    parts = []
    for arg in argv:
        label, sep, spec = arg.partition(":")
        if not sep:
            label, spec = "roll", arg
        try:
            total, detail = roll_one(spec)
        except ValueError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1
        parts.append(f"{label} {spec}={total}{detail}")
    print(" · ".join(parts))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
