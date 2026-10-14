#!/usr/bin/env python3
"""dm_post.py: post a full DM response to Discord, split by who should see which part.

The master prompt is unchanged: you still generate every field of the response, and the terminal shows the
whole thing. This only decides what goes to Discord, and where:

  game room (the players):   the narration, the VITALS strip (or COMBAT STATE), the roll gate / NEEDED lines,
                             a simplified LOOP (open questions and the situation, no opposition, counts or
                             cause trace), the CHOICE line and the numbered options.
  dm room (Joe only):        everything else, in order: the DM ROLLS block, the collapsed block (location,
                             NPCs present with Affinity, roster, pending rolls), the full LOOP, CONSEQUENCE and
                             SITUATION with their traces, EXPOSITION tags, and any notes after the narration.
  dice room:                 posted by the relay straight from the dice ledger (DICE_CHANNEL_ID). Not this tool.

Anything the splitter does not positively recognise as a players' block goes to the dm room, so a parsing
miss hides information instead of leaking it. A final filter also pulls any line that looks like a spoiler
(ledger ids, ENC/OPP lines, DM ROLLS) out of the game post.

  dm_post.py [--file F] [--outbox PATH] [--room game] [--dm-room dm] [--dry-run] [--raw]
Reads the response from stdin (or --file). Rooms other than game (ooc, a PC bubble) are posted whole.
"""
import argparse
import json
import os
import re
import sys

LEAK = re.compile(r"\[R\d{4}\]|DM ROLLS|\bOPP:|\bENC:|=== (END )?LOOP|\bE\d+ (OPEN|HOOK|RESOLVED|LAPSED)\b|^\s*FORK:|^\s*STEP:")


def split(text):
    lines = text.replace("\r\n", "\n").split("\n")
    narr, state, gate, choice = [], [], [], []
    dm = []
    loop_qs, situation = [], ""
    mode = "narr"            # narr | after | choice
    i = 0
    n = len(lines)

    def take_block(start, stop_pred):
        j = start
        blk = []
        while j < n and not stop_pred(lines[j]):
            blk.append(lines[j])
            j += 1
        return blk, j

    while i < n:
        ln = lines[i]
        s = ln.strip()
        # fenced block: roll logs, spell lines, notes. Never for players.
        if s.startswith("```"):
            blk = [ln]
            j = i + 1
            while j < n and not lines[j].strip().startswith("```"):
                blk.append(lines[j])
                j += 1
            if j < n:
                blk.append(lines[j])
                j += 1
            dm.append("\n".join(blk))
            if mode == "narr":
                mode = "after"
            i = j
            continue
        if s == "---":
            if mode == "narr":
                mode = "after"
            i += 1
            continue
        if re.match(r"^=+\s*LOOP\s*=+", s):
            blk = [ln]
            j = i + 1
            while j < n:
                blk.append(lines[j])
                if re.match(r"^=+\s*END LOOP\s*=+", lines[j].strip()):
                    j += 1
                    break
                j += 1
            for b in blk:
                m = re.search(r"\bQ:\s*(.+?)(?:\s+·\s+OPP:|$)", b)
                if b.strip().startswith("ENC:") and m:
                    loop_qs.append(m.group(1).strip().rstrip("."))
            dm.append("\n".join(blk))
            mode = "after"
            i = j
            continue
        if re.match(r"^\*{0,2}VITALS\*{0,2}\b", s):
            state.append(ln)
            mode = "after" if mode == "narr" else mode
            i += 1
            continue
        if re.match(r"^\*{0,2}COMBAT STATE", s):
            blk = [ln]
            j = i + 1
            while j < n:
                if lines[j].strip() != "":
                    blk.append(lines[j])
                    j += 1
                elif j + 1 < n and lines[j + 1].lstrip().startswith(("|", "Turn:", "Round")):
                    blk.append(lines[j])
                    j += 1
                else:
                    break
            state.append("\n".join(blk))
            mode = "after" if mode == "narr" else mode
            i = j
            continue
        if re.match(r"^\*{0,2}SPLIT\b", s):
            state.append(ln)
            i += 1
            continue
        if re.match(r"^\*{0,2}(Location|NPCs present|SESSION ROSTER|PENDING ROLLS|DUNGEON|Quest)\b", s):
            dm.append(ln)
            if mode == "narr":
                mode = "after"
            i += 1
            continue
        if re.match(r"^\*{0,2}(CONSEQUENCE|SITUATION)\b", s):
            dm.append(ln)
            if s.lstrip("*").startswith("SITUATION"):
                situation = re.sub(r"\s*←.*$", "", re.sub(r"^\*{0,2}SITUATION:?\*{0,2}\s*", "", s)).strip()
            if mode == "narr":
                mode = "after"
            i += 1
            continue
        if re.match(r"^\*{0,2}EXPOSITION", s):
            dm.append(ln)
            i += 1
            continue
        if re.match(r"^\*{0,2}(ROLL GATE|NEEDED)", s):
            blk, j = take_block(i, lambda l: l.strip() == "")
            gate.append("\n".join(blk))
            if mode == "narr":
                mode = "after"
            i = j
            continue
        if re.match(r"^\*{0,2}DM ROLLS", s):
            blk, j = take_block(i, lambda l: l.strip() == "")
            dm.append("\n".join(blk))
            if mode == "narr":
                mode = "after"
            i = j
            continue
        if re.match(r"^\*{0,2}CHOICE\b", s):
            mode = "choice"
            choice.append(ln)
            i += 1
            continue
        if mode == "choice":
            choice.append(ln)
            i += 1
            continue
        if mode == "narr":
            narr.append(ln)
        else:
            if s:
                dm.append(ln)      # unknown block after the narration: not for the players
        i += 1

    simple = []
    if loop_qs:
        simple.append("**Open now:** " + " · ".join(loop_qs))
    if situation:
        simple.append("**Now:** " + situation)
    parts = []
    nt = "\n".join(narr).strip()
    if nt:
        parts.append(nt)
    if gate:
        parts.append("\n\n".join(gate))
    if state:
        parts.append("\n".join(state))
    if simple:
        parts.append("\n".join(simple))
    ct = "\n".join(choice).strip()
    if ct:
        parts.append(ct)
    game = "\n\n".join(parts)
    # final spoiler filter on the game post
    kept, pulled = [], []
    for l in game.split("\n"):
        (pulled if LEAK.search(l) else kept).append(l)
    if pulled:
        dm.append("[pulled out of the game post by the spoiler filter]\n" + "\n".join(pulled))
    game = re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()
    dmt = "\n".join(x for x in dm if x.strip()).strip()
    return game, dmt


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file")
    ap.add_argument("--outbox", default=os.environ.get("OUTBOX_PATH", "bot/mailbox/outbox.jsonl"))
    ap.add_argument("--room", default="game")
    ap.add_argument("--dm-room", default="dm")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--raw", action="store_true", help="post everything to the room, no split")
    a = ap.parse_args()
    text = open(a.file).read() if a.file else sys.stdin.read()
    rows = []
    if a.raw or a.room != "game":
        rows.append({"channel": a.room, "content": text.strip()})
    else:
        game, dmt = split(text)
        if game:
            rows.append({"channel": "game", "content": game})
        if dmt:
            rows.append({"channel": a.dm_room, "content": dmt})
    if a.dry_run:
        for r in rows:
            print(f"----- {r['channel']} ({len(r['content'])} chars) -----\n{r['content']}\n")
        return
    os.makedirs(os.path.dirname(os.path.abspath(a.outbox)), exist_ok=True)
    with open(a.outbox, "a") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print("POSTED " + ", ".join(f"{r['channel']}:{len(r['content'])}" for r in rows))


if __name__ == "__main__":
    main()
