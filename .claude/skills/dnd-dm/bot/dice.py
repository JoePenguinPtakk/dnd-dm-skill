"""dice.py -- the %roll and %rollgo commands, and the gate they answer.

Player-side dice only. House ruling #2 (dice ownership) says players roll
their own PC dice and the DM rolls the world's; this module is the players'
half. A dice command is still the player rolling, the same way a physical die
on a table is: the bot is the die, not the roller.

House ruling #20 governs when these fire. The DM must present a **NEEDED:**
gate every single time a player die is open, then stop. `%rollgo` is the
player's per-roll CONSENT for the engine to answer that one gate; it is not a
standing delegation, and the next gate needs the next command. Nothing here may
roll a player's die that the player did not ask for.

The DM's own world dice go through the master prompt's engine
(Building-a-Better-Prompt `.claude/skills/dnd-dm/roll.py`), never through here.

Every roll these commands make goes through that same dice engine, so it
lands in the ledger tagged `player-<PC>`. There is no local roller here on
purpose: a second random source would be a path around the ledger. If the
engine cannot roll, the command says so and the player rolls their own die.
"""

import os
import re
import subprocess

# The prompt marks a request for a player roll with a bolded NEEDED tag, e.g.
#   **NEEDED:** Rhogast attack roll (staff) vs Cartomancer AC13
NEEDED = re.compile(r"\*\*NEEDED:\*\*\s*(.+?)\s*$", re.M | re.I)


ENGINE = os.environ.get("DICE_ENGINE", os.path.expanduser("~/.claude/skills/dnd-dm/" + "roll.py"))
# Ledger IDs of rolls this bot made itself (%roll / %rollgo). The world-dice
# feed skips these, since they were already posted where the player rolled,
# and flags any other `player-` entry as not made by the bot.
BOT_IDS = set()
ENGINE_LINE = re.compile(r"^\*\*\[(R\d+)\] [^*]+\*\* \S+?=(-?\d+)(.*)$")


def engine_roll(pc, spec, label=""):
    """Roll one player die through the dice engine, so it lands in the ledger.

    Returns (total, detail, ledger_id). Raises ValueError with a table-ready
    message if the engine refuses the spec or is not running a session. The
    label is tagged `player-<PC>` so the ledger shows whose die it was.
    """
    tag = re.sub(r"[^A-Za-z0-9-]+", "-", f"player-{pc}-{label}".strip("-")).strip("-")[:60]
    try:
        out = subprocess.run(["python3", ENGINE, f"{tag}:{spec}"],
                             capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError("the dice engine is not reachable on this machine")
    if out.returncode != 0:
        why = (out.stderr or out.stdout).strip().replace("ERROR: ", "")
        if "no active session" in why:
            why = "the dice engine has no session open (the DM starts one at boot)"
        raise ValueError(why)
    for line in out.stdout.splitlines():
        m = ENGINE_LINE.match(line.strip())
        if m:
            BOT_IDS.add(m.group(1))
            return int(m.group(2)), m.group(3).strip(), m.group(1)
    raise ValueError("the dice engine answered in a form this bot cannot read")


def resolve_pc(display_name, player_map):
    """Discord display name to PC name.

    A display name is not a PC name. Getting this wrong once produced the
    bow-as-club incident, where an unmatched name fell back to a generic melee
    profile. Falls back to the display name unchanged rather than guessing.
    """
    return player_map.get(display_name.lower(), display_name)


def parse_needed(text):
    """Every **NEEDED:** request in a DM post, in order."""
    return [m.group(1).strip() for m in NEEDED.finditer(text or "")]


def pending_for(pending, pc):
    """The outstanding requests naming this PC, plus any unaddressed ones."""
    low = pc.lower()
    mine = [r for r in pending if low in r.lower()]
    return mine if mine else list(pending)


def cmd_roll(pc, args):
    """`%roll 1d20+5 attack` -> a line for Discord and a line for the DM."""
    if not args:
        return None, ("Usage: `%roll 1d20+5 [label]`. "
                      "Also `%roll d20adv+7`, `%roll 2d6+3`, `%roll d100`.")
    spec, _, label = args.strip().partition(" ")
    label = label.strip()
    try:
        total, detail, rid = engine_roll(pc, spec, label)
    except ValueError as e:
        return None, f"Could not roll: {e}. Roll your own die and type the result."
    tail = f" for {label}" if label else ""
    public = f"**{pc}** rolls `{spec}`{tail}: **{total}** {detail} `{rid}`".rstrip()
    for_dm = f"{pc} rolled {spec}={total}{detail} [{rid}]" + (f" [{label}]" if label else "")
    return for_dm, public


def cmd_rollgo(pc, pending):
    """`%rollgo` -> roll whatever the DM last asked this PC for.

    The request text is free prose, so any dice specs inside it are rolled and
    the request is echoed alongside. If the DM named no dice, this says so
    rather than inventing a spec.
    """
    mine = pending_for(pending, pc)
    if not mine:
        return None, ("Nothing pending for you. The DM has not posted a "
                      "**NEEDED:** request since the last roll.")
    lines, dm_lines = [], []
    for req in mine:
        specs = [s for s in re.findall(r"\b\d*d\d+(?:adv|dis)?(?:[+-]\d+)?\b", req, re.I)]
        if not specs:
            specs = ["d20"]
            note = " (no die named in the request, rolled a plain d20)"
        else:
            note = ""
        parts = []
        for spec in specs:
            try:
                total, detail, rid = engine_roll(pc, spec, "gate")
            except ValueError as e:
                parts.append(f"could not roll `{spec}`: {e}. Roll your own die and type the result.")
                continue
            parts.append(f"`{spec}` = **{total}** {detail} `{rid}`".rstrip())
            dm_lines.append(f"{pc} rolled {spec}={total}{detail} [{rid}] [{req}]")
        lines.append(f"__{req}__{note}\n" + " · ".join(parts))
    public = f"**{pc}** answers the gate:\n" + "\n".join(lines)
    return "\n".join(dm_lines), public


HELP = """**Dice commands**
`%roll <dice> [label]` roll your own dice. `1d20+5`, `2d6+3`, `d20adv+7`, `d20dis`, `d100`
`%rollgo` roll whatever the DM's last **NEEDED:** line asked you for
Both roll through the dice engine, record the roll in the ledger, post it here, and hand the number to the DM.
Rolling a physical die? Just type the result.
The DM's own world dice are rolled separately and are not these commands."""
