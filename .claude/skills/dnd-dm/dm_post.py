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

THE HIDDEN GATE (master prompt §2-bis SECRETS). Every game-room response carries one HIDDEN line, wherever
in the response it sits:
    HIDDEN: <secret words> = <DM note> | <secret words> = <DM note> | ...
    HIDDEN: none
<secret words> is a comma-separated list of the words the players must not read yet (a creature kind no PC
has seen, a name, a count, a place). The note after "=" is for the DM only and is never scanned. The
HIDDEN line and the PARTY line always go to the dm room. Then the game post is scanned. The post is
REFUSED (nothing is written, exit code 3, a `MALFORMED (dm_post gate)` report on stderr) when:
  - the response has no HIDDEN line;
  - the game post uses any secret word (whole word, any case, plural or possessive too);
  - something is hidden and the game post gives a count of more unseen things ("the other three",
    "two more", "the remaining one").
The DM rewrites the named lines and posts again. Posts to other rooms (ooc, a PC bubble) are scanned
against the last HIDDEN line the game room accepted (kept in .hidden.json beside the outbox).

Two more checks on a game-room post (build 20261019a), refused the same way:
  - NO EARLY COMBAT END: a HIDDEN entry whose note says "hostile" is a hidden enemy still in the fight, so a post
    with "COMBAT ENDS" or "XP AWARD" is refused while one is listed (master prompt §4.0 End).
  - THE CLOCK ONLY GOES FORWARD: the last "Day N · HH:MM" the game room accepted is kept in .clock.json; a post
    showing an earlier day and time is refused (master prompt §3-ter). --allow-earlier lets one post through
    when Joe has ruled a rewind.

ROLL CALL (master prompt §3-quater), out of combat only (no COMBAT STATE in the response), refused the same way:
  - E1: no PARTY line.  E2: a PLAYER_MAP character missing from it (mark one who is not here `absent` or `Vessel`).
  - E3: a present PC quiet while the other players posted 3 or more times (SPOTLIGHT) is not named in the CHOICE line.
  - E4: when E3 applies, the numbered options do not name every present PC.
  - E5: `dm_post.py --new-session` (run at boot) starts the counts fresh for the session.

SPOTLIGHT. After every accepted game-room post the tool prints one line, for the PARTY line (master prompt
§3-quater): for each player's character, how many game-room posts the OTHER players made since that player last
posted this session, read from the mailbox (inbox.jsonl) and PLAYER_MAP in bot/.env. `dm_post.py --spotlight` prints it alone.

  dm_post.py [--file F] [--outbox PATH] [--room game] [--dm-room dm] [--dry-run] [--raw]
Reads the response from stdin (or --file). Rooms other than game (ooc, a PC bubble) are posted whole.
"""
import argparse
import json
import os
import re
import sys
import time

HIDDEN_RE = re.compile(r"^\s*\*{0,2}HIDDEN\*{0,2}\s*:\s*\*{0,2}\s*(.*)$", re.I)
PARTY_RE = re.compile(r"^\s*\*{0,2}PARTY\*{0,2}\s*:", re.I)
NUM = r"(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|a\s+dozen|\d+)"
CLOCK_RE = re.compile(r"\bDay\s+(\d+)\s*\W{0,3}\s*(\d{1,2}):(\d{2})\b")
ENDS_RE = re.compile(r"COMBAT ENDS|XP AWARD", re.I)
COUNT_LEAK = re.compile(
    r"\b(?:the\s+)?(?:other|remaining)\s+" + NUM + r"\b"
    r"|\bthe\s+rest\s+of\s+(?:the\s+|them|those)"
    r"|\b" + NUM + r"\s+(?:more|others)\b", re.I)

LEAK = re.compile(r"\[R\d{4}\]|DM ROLLS|\bOPP:|\bENC:|=== (END )?LOOP|\bE\d+ (OPEN|HOOK|RESOLVED|LAPSED)\b|^\s*FORK:|^\s*STEP:")


def split(text):
    lines = text.replace("\r\n", "\n").split("\n")
    narr, state, gate, choice = [], [], [], []
    dm = []
    loop_qs, situation = [], ""
    hidden = []              # the HIDDEN line bodies found in this response
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
        # HIDDEN and PARTY lines: DM-only wherever they sit, and they never change the mode.
        mh = HIDDEN_RE.match(ln)
        if mh:
            body = mh.group(1).strip().strip("*").strip()
            blk = [ln]
            j = i + 1
            if not body:   # block form: "HIDDEN:" then "- item" lines
                while j < n and re.match(r"^\s*[-•*]\s+\S", lines[j]):
                    blk.append(lines[j])
                    body += " | " + re.sub(r"^\s*[-•*]\s+", "", lines[j]).strip()
                    j += 1
            hidden.append(body)
            dm.append("\n".join(blk))
            i = j
            continue
        if PARTY_RE.match(ln):
            dm.append(ln)
            i += 1
            continue
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
    return game, dmt, hidden


def parse_hidden(bodies):
    """Secret words from HIDDEN line bodies. Returns (entries, terms): entries are the raw items (an empty list
    means "none"), terms the lower-case secret words to scan for."""
    entries, terms = [], []
    for body in bodies:
        for item in body.split("|"):
            item = item.strip().strip("*").strip()
            if not item or re.fullmatch(r"(?i)none\.?|nothing\.?|-", item):
                continue
            entries.append(item)
            words = item.split("=", 1)[0]
            for t in words.split(","):
                t = re.sub(r"[*_`\"']", "", t).strip().lower()
                t = re.sub(r"^(?:a|an|the)\s+", "", t)
                if len(t) >= 3:
                    terms.append(t)
    return entries, sorted(set(terms), key=len, reverse=True)


def term_re(t):
    words = [re.escape(w) for w in t.split()]
    words[-1] += r"(?:s|es)?(?:'s|s')?"
    return re.compile(r"(?<![\w-])" + r"[\s-]+".join(words) + r"(?![\w-])", re.I)


def scan(text, entries, terms):
    """Every leak in text: a list of (line, reason)."""
    bad = []
    pats = [(t, term_re(t)) for t in terms]
    for line in text.split("\n"):
        plain = re.sub(r"[*_`]", "", line)
        for t, p in pats:
            if p.search(plain):
                bad.append((line.strip(), f'names hidden "{t}"'))
                break
        else:
            if entries:
                m = COUNT_LEAK.search(plain)
                if m:
                    bad.append((line.strip(), f'gives a count of unseen things ("{m.group(0)}")'))
    return bad


def refuse(problems):
    sys.stderr.write("MALFORMED (dm_post gate). Nothing was posted.\n")
    for line, why in problems:
        sys.stderr.write(f"  - {why}: {line}\n" if line else f"  - {why}\n")
    sys.stderr.write("Fix exactly what is listed (players read only what their characters have perceived; combat "
                     "ends only when no hostile can fight; time only moves forward; the quiet player gets the scene), keep the "
                     "HIDDEN line, and post "
                     "again.\n")
    sys.exit(3)


def clock_of(text):
    """The latest (day, minutes) a post shows, or None."""
    best = None
    for m in CLOCK_RE.finditer(re.sub(r"[*_`]", "", text)):
        v = (int(m.group(1)), int(m.group(2)) * 60 + int(m.group(3)))
        best = v if best is None or v > best else best
    return best


def load_env(outbox):
    """bot/.env for the campaign whose mailbox this is: next to the outbox, or one folder up."""
    d = os.path.dirname(os.path.abspath(outbox))
    for cand in (os.path.join(d, ".env"), os.path.join(os.path.dirname(d), ".env")):
        if os.path.exists(cand):
            env = {}
            for line in open(cand, encoding="utf-8-sig"):
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
            return env
    return {}


def spotlight_counts(outbox):
    """({PC: count or None}, mapped PC names, unmapped authors). count = how many game-room posts the OTHER players
    made since this PC's player last posted (or since the session started, --new-session, if they have not posted
    since). It counts the other players' turns, not the DM's posts, so a DM who answers one message with several
    short posts (master prompt §2-ter 7-bis) makes nobody look quiet. None = no post and no session start on record."""
    d = os.path.dirname(os.path.abspath(outbox))
    try:
        start = float(json.load(open(os.path.join(d, ".session.json")))["ts"])
    except (OSError, ValueError, KeyError, TypeError):
        start = 0.0
    pmap = {}
    for pair in load_env(outbox).get("PLAYER_MAP", "").split(","):
        if ":" in pair:
            k, v = pair.split(":", 1)
            pmap[k.strip().lower()] = v.strip()
    posts = []          # (ts, PC) for every game-room player post this session
    try:
        for line in open(os.path.join(d, "inbox.jsonl")):
            r = json.loads(line)
            if r.get("channel", "game") != "game" or r.get("ts", 0) <= start:
                continue
            who = pmap.get(str(r.get("author", "")).lower(), str(r.get("author", "")))
            posts.append((r.get("ts", 0), who))
    except (OSError, ValueError):
        pass
    last = {}
    for t, who in posts:
        last[who] = max(last.get(who, 0), t)
    names = list(dict.fromkeys(list(pmap.values()) + list(last)))
    counts = {}
    for n in names:
        since = max(last.get(n, 0), start)
        counts[n] = sum(1 for t, who in posts if t > since and who != n) if since else None
    unmapped = [n for n in last if n not in pmap.values()]
    return counts, list(dict.fromkeys(pmap.values())), unmapped


def spotlight(outbox):
    """'Rhogast 0 · Oliver 3 · Roy 1': the SPOTLIGHT line for the PARTY line."""
    counts, mapped, unmapped = spotlight_counts(outbox)
    if not counts:
        return "SPOTLIGHT: no PLAYER_MAP and no player posts yet"
    parts = [f"{n} {c}" if c is not None else f"{n} no post yet" for n, c in counts.items()]
    note = f" (not in PLAYER_MAP: {', '.join(unmapped)})" if unmapped and mapped else ""
    return "SPOTLIGHT (other players' posts since each one last posted this session): " + " · ".join(parts) + note


def roll_call(text, outbox):
    """E1-E4 (master prompt §3-quater): problems with an out-of-combat game post's PARTY line and CHOICE block."""
    bad = []
    party = [l for l in text.split("\n") if PARTY_RE.match(l)]
    if not party:
        return [("", "no PARTY line in an out-of-combat response (master prompt §3-quater ROLL CALL): one entry per "
                     "present PC, where they are, what they are doing or waiting on, and the SPOTLIGHT count")]
    counts, mapped, _ = spotlight_counts(outbox)
    if not mapped:
        return bad
    pline = re.sub(r"[*_`]", "", " ".join(party))
    body = re.sub(r"^\s*PARTY\s*:", "", pline, flags=re.I)
    entries = [e.strip() for e in re.split(r"\s+·\s+|\s*\|\s*|;\s*(?=[A-Z][a-z]+\s*\()", body) if e.strip()]
    exempt = set()
    for pc in mapped:
        if not re.search(r"\b" + re.escape(pc) + r"\b", pline, re.I):
            bad.append((party[0].strip(), f"the PARTY line leaves out {pc} (every PC in PLAYER_MAP is listed; mark one "
                                           f"who is not here `absent` or `Vessel`)"))
            continue
        for e in entries:
            if re.match(r"\W*" + re.escape(pc) + r"\b", e, re.I) and re.search(r"\b(absent|vessel)\b", e, re.I):
                exempt.add(pc)
    lines = text.split("\n")
    ci = next((i for i, l in enumerate(lines) if re.match(r"^\s*\*{0,2}CHOICE\b", l.strip())), None)
    if ci is None:
        return bad
    choice = re.sub(r"[*_`]", "", lines[ci])
    opts = " ".join(re.sub(r"[*_`]", "", l) for l in lines[ci + 1:] if re.match(r"^\s*\d+[.)]", l))
    quiet = [pc for pc in mapped if pc not in exempt and (counts.get(pc) or 0) >= 3]
    for pc in quiet:
        if not re.search(r"\b" + re.escape(pc) + r"\b", choice, re.I):
            bad.append((lines[ci].strip(), f"{pc} has been quiet while the others posted {counts[pc]} times; the CHOICE line speaks to "
                                           f"{pc} by name (master prompt §3-quater)"))
    if quiet:
        for pc in mapped:
            if pc not in exempt and not re.search(r"\b" + re.escape(pc) + r"\b", opts, re.I):
                bad.append(("", f"a PC is quiet, so the options name every present PC with a suggested action; none "
                                f"names {pc} (master prompt §3-quater)"))
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file")
    ap.add_argument("--outbox", default=os.environ.get("OUTBOX_PATH", "bot/mailbox/outbox.jsonl"))
    ap.add_argument("--room", default="game")
    ap.add_argument("--dm-room", default="dm")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--raw", action="store_true", help="post everything to the room, no split")
    ap.add_argument("--allow-earlier", action="store_true", help="let one post show an earlier clock (a rewind Joe ruled)")
    ap.add_argument("--spotlight", action="store_true", help="print the spotlight counts and exit")
    ap.add_argument("--new-session", action="store_true", help="start the session's spotlight counts (run at boot)")
    a = ap.parse_args()
    if a.new_session:
        path = os.path.join(os.path.dirname(os.path.abspath(a.outbox)), ".session.json")
        with open(path, "w") as f:
            json.dump({"ts": time.time()}, f)
        print("SESSION STARTED for the spotlight counts. " + spotlight(a.outbox))
        return
    if a.spotlight:
        print(spotlight(a.outbox))
        return
    text = open(a.file).read() if a.file else sys.stdin.read()
    rows = []
    hidden_path = os.path.join(os.path.dirname(os.path.abspath(a.outbox)), ".hidden.json")
    clock_path = os.path.join(os.path.dirname(os.path.abspath(a.outbox)), ".clock.json")
    new_hidden = None
    new_clock = None
    if a.raw or a.room != "game":
        body = text.strip()
        if a.room != a.dm_room:
            # scan against this text's own HIDDEN line, else the last one the game room accepted
            own = [HIDDEN_RE.match(l).group(1) for l in body.split("\n") if HIDDEN_RE.match(l)]
            if own:
                entries, terms = parse_hidden(own)
                body = "\n".join(l for l in body.split("\n") if not HIDDEN_RE.match(l)).strip()
            else:
                try:
                    saved = json.load(open(hidden_path))
                    entries, terms = saved.get("entries", []), saved.get("terms", [])
                except (OSError, ValueError):
                    entries, terms = [], []
            bad = scan(body, entries, terms)
            if bad:
                refuse(bad)
        rows.append({"channel": a.room, "content": body})
    else:
        game, dmt, hidden = split(text)
        if not hidden:
            refuse([("", 'no HIDDEN line. Every game-room response carries one; write "HIDDEN: none" if '
                          'nothing is hidden')])
        entries, terms = parse_hidden(hidden)
        bad = scan(game, entries, terms)
        hostile = [e for e in entries if "=" in e and re.search(r"\bhostile\b", e.split("=", 1)[1], re.I)]
        if hostile:
            for line in text.split("\n"):
                if HIDDEN_RE.match(line):
                    continue
                if ENDS_RE.search(line):
                    bad.append((line.strip(), "ends combat or awards XP while a hidden hostile is listed ("
                                + hostile[0].split("=", 1)[0].strip() + "); combat ends only when no hostile can "
                                "still fight (master prompt §4.0)"))
        new_clock = clock_of(game)
        if new_clock and not a.allow_earlier:
            try:
                old = tuple(json.load(open(clock_path)))
            except (OSError, ValueError, TypeError):
                old = None
            if old and new_clock < old:
                bad.append(("", f"the clock runs backward: Day {new_clock[0]} {new_clock[1] // 60:02d}:{new_clock[1] % 60:02d} "
                                f"is earlier than the last time shown, Day {old[0]} {old[1] // 60:02d}:{old[1] % 60:02d} "
                                "(master prompt §3-ter: time only moves forward)"))
        if not re.search(r"(?m)^\s*\*{0,2}COMBAT STATE", text):
            bad += roll_call(text, a.outbox)
        if bad:
            refuse(bad)
        new_hidden = {"entries": entries, "terms": terms}
        now = time.time()
        if game:
            rows.append({"channel": "game", "content": game, "ts": now})
        if dmt:
            rows.append({"channel": a.dm_room, "content": dmt, "ts": now})
    if a.dry_run:
        for r in rows:
            print(f"----- {r['channel']} ({len(r['content'])} chars) -----\n{r['content']}\n")
        return
    os.makedirs(os.path.dirname(os.path.abspath(a.outbox)), exist_ok=True)
    with open(a.outbox, "a") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    if new_hidden is not None:
        with open(hidden_path, "w") as f:
            json.dump(new_hidden, f)
    if new_clock is not None:
        old = None
        try:
            old = tuple(json.load(open(clock_path)))
        except (OSError, ValueError, TypeError):
            pass
        if a.allow_earlier or old is None or new_clock > old:
            with open(clock_path, "w") as f:
                json.dump(list(new_clock), f)
    print("POSTED " + ", ".join(f"{r['channel']}:{len(r['content'])}" for r in rows))
    if new_hidden is not None:
        print(spotlight(a.outbox))


if __name__ == "__main__":
    main()
