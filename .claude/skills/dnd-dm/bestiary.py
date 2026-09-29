#!/usr/bin/env python3
"""bestiary.py: creature lookup for spawns (master prompt §4.1 and §7-bis).

Read-only. It never rolls a die: it lists the creatures that legally fit a
spawn and prints a ready weighted `pick[...]` for the dice engine, which does
the rolling and keeps the record. It also prints exact stat blocks, so no
block is ever recalled from memory.

Data: bestiary.json beside this file (SRD 5.2 stat blocks, CC-BY-4.0, with SRD
5.1 environment tags via Open5e; rebuilt by tools/build_bestiary.py).

USAGE
  bestiary.py candidates --env urban --levels 5,5,5 [--npcs 1] --difficulty moderate
                         [--role lead|support|npc|fauna] [--remaining XP --lead-cr CR]
                         [--boss] [--first-fight] [--type humanoid,undead]
                         [--no-magic] [--no-ranged] [--quiet]
  bestiary.py check      --levels 5,5,5 [--npcs 1] --difficulty moderate [--boss] [--first-fight]
                         "Mage" "Spy x2"
  bestiary.py show NAME            exact stat block (spaces or hyphens both work)
  bestiary.py defaults NAME        default strategy tier and morale disposition
  bestiary.py find TEXT            search creature names
  bestiary.py envs                 environment keys and the prompt's tag mapping

THE CR RULES (enforced here)
  Ceiling for any one creature: levels 1-4, CR <= average PC level; level 5+,
  CR <= 1.5 x average level (rounded down to a rung). Small party (under 4
  character-equivalents): one rung lower. --boss (dungeon heart, nemesis, an
  authorized module's villain) may go up to two rungs above, only on a high
  difficulty and never on a first fight.
  Floor for combatants: CR 1/8 at levels 1-4; from level 5, a quarter of the
  average level rounded down to a rung. CR 0 is never a combatant here.
  Lead: from the ceiling down to four rungs below it. Support: from the floor
  up to two rungs below the lead (or up to the lead's own CR, so packs are
  possible, when that window is empty). Support count: the most that fits the
  remaining XP, capped at 2 per PC. At most three distinct stat blocks.
  Never rolled: Troll Limb (only through a Troll's Loathsome Limbs trait).
  Fauna (--role fauna): creatures met as texture, a hook, or a mount rather
  than as the fight (a giant fly out of a sewer, a herd of elk, a cat on a
  wall). Any CR from 0 up to the ceiling, no budget. If a fauna creature turns
  hostile, the fight is budgeted like any other.
  Benchmark (second opinion): total CR over a quarter of total PC levels
  (average level 1-4) or half (5+) fails unless the difficulty is high.
"""
import argparse
import json
import math
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "bestiary.json"
ACTIVE = Path.home() / ".dnd-dice" / "active.json"

# 2024 DMG XP budget per character: level -> (low, moderate, high). Same as §4.1.
BUDGET = {
    1: (50, 75, 100), 2: (100, 150, 200), 3: (150, 225, 400), 4: (250, 375, 500),
    5: (500, 750, 1100), 6: (600, 1000, 1400), 7: (750, 1300, 1700), 8: (1000, 1700, 2100),
    9: (1300, 2000, 2600), 10: (1600, 2300, 3100), 11: (1900, 2900, 4100), 12: (2200, 3700, 4700),
    13: (2600, 4200, 5400), 14: (2900, 4900, 6200), 15: (3300, 5400, 7800), 16: (3800, 6100, 9800),
    17: (4500, 7200, 11700), 18: (5000, 8700, 14200), 19: (5500, 10700, 17200), 20: (6400, 13200, 22000),
}
DIFF = {"low": 0, "moderate": 1, "high": 2}
LADDER = [0, 0.125, 0.25, 0.5] + [float(n) for n in range(1, 31)]

# The master prompt's environment tags (§6-nonies, §6-ter Sea) -> bestiary keys.
TAG_MAP = {
    "urban": ["urban"],
    "suburban": ["urban", "grassland"],
    "rural": ["grassland", "hills", "forest"],
    "deep-wilderness": ["forest", "mountain", "hills", "swamp", "arctic", "desert", "grassland"],
    "forest": ["forest"],
    "plains": ["grassland"],
    "dungeon": ["caves", "ruins", "tomb", "underworld", "sewer", "laboratory", "temple"],
    "sea": ["ocean", "coast"],
}
# §6-undecies delve builders -> bestiary keys (use as --env builder:tomb, etc.).
BUILDER_MAP = {
    "tomb": ["tomb", "ruins"], "temple": ["temple", "ruins"], "fortress": ["ruins", "hills", "mountain"],
    "mine": ["caves", "underworld"], "cistern-or-sewer": ["sewer"], "natural-cave": ["caves", "underworld"],
    "sanctum": ["laboratory", "ruins"], "vault-or-prison": ["ruins", "tomb", "underworld"],
}
# §7-quinquies default tiers for the blocks it names; everything else by rule.
STRAT_NAMED = {
    "Commoner": 1, "Guard": 1, "Cultist": 1, "Bandit": 1, "Priest Acolyte": 1, "Berserker": 1,
    "Warrior Infantry": 1, "Scout": 2, "Tough": 2, "Priest": 2, "Bandit Captain": 2,
    "Scout Captain": 2, "Warrior Veteran": 2, "Guard Captain": 3, "Pirate Captain": 3,
    "Assassin": 3, "Mage": 3,
}
STRAT_NAMES = {0: "STRAT-0 Rote", 1: "STRAT-1 Artless", 2: "STRAT-2 Drilled", 3: "STRAT-3 Shrewd", 4: "STRAT-4 Peerless"}


def fail(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    return 1


def load():
    return json.loads(DATA.read_text())["creatures"]


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def token(name):
    return re.sub(r"-+", "-", re.sub(r"[^A-Za-z0-9]", "-", name)).strip("-")


def crs(cr):
    return {0.125: "1/8", 0.25: "1/4", 0.5: "1/2"}.get(cr, str(int(cr)) if cr == int(cr) else str(cr))


def rung_at_or_below(x):
    return max(i for i, c in enumerate(LADDER) if c <= x + 1e-9)


def parse_cr(s):
    s = str(s).strip()
    return float(eval(s)) if re.fullmatch(r"\d+(/\d+)?", s) else float(s)


def party(a):
    levels = [int(x) for x in str(a.levels).split(",") if x.strip()]
    if not levels or any(l < 1 or l > 20 for l in levels):
        raise ValueError("--levels needs PC levels 1-20, comma separated")
    avg = sum(levels) / len(levels)
    size = len(levels) + 0.5 * a.npcs
    d = DIFF[a.difficulty]
    budget = sum(BUDGET[l][d] for l in levels) + int(0.5 * a.npcs * BUDGET[max(1, round(avg))][d])
    base = avg if avg < 5 else 1.5 * avg
    ceil_i = rung_at_or_below(base)
    notes = []
    if size < 4:
        ceil_i = max(1, ceil_i - 1)
        notes.append("small party: ceiling one rung lower")
    base_ceil_i = ceil_i
    if a.boss:
        if a.difficulty == "high" and not a.first_fight:
            ceil_i = min(len(LADDER) - 1, ceil_i + 2)
            notes.append("boss: up to two rungs above; mark COMBAT SETUP `DEADLY`, `FAILURE: hard`")
        else:
            notes.append("boss ignored: only on a high difficulty and never on a first fight")
    floor_i = 1 if avg < 5 else max(1, rung_at_or_below(avg / 4))
    return {"levels": levels, "avg": avg, "size": size, "budget": budget, "ceil_i": ceil_i, "base_ceil_i": base_ceil_i,
            "floor_i": floor_i, "notes": notes, "pcs": len(levels)}


def env_keys(spec):
    out = set()
    for part in str(spec).split(","):
        p = part.strip().lower().replace(" ", "-")
        if not p:
            continue
        if p.startswith("builder:"):
            out.update(BUILDER_MAP.get(p.split(":", 1)[1], []))
        elif p in TAG_MAP:
            out.update(TAG_MAP[p])
        else:
            out.add(p)
    return out


def flags(c):
    f = []
    bps = {"bludgeoning", "piercing", "slashing"}
    if bps <= set(c["damage_immunities"]):
        f.append("IMMUNE-WEAPONS")
    elif bps <= set(c["damage_resistances"]):
        f.append("RESIST-WEAPONS")
    if any("incorporeal" in t["name"].lower() for t in c["traits"]):
        f.append("INCORPOREAL")
    if c["speed"].get("fly"):
        f.append("FLIES")
    if any(a["type"] == "LEGENDARY_ACTION" for a in c["actions"]) or any("legendary resistance" in t["name"].lower() for t in c["traits"]):
        f.append("LEGENDARY")
    return f


def recent_spawns(limit=30):
    """Creature names picked by `spawn...` rolls in this campaign's ledger, newest first."""
    try:
        act = json.loads(ACTIVE.read_text())
        path = Path(act["campaign"]) / "dice" / "ledger.jsonl"
        rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    except Exception:
        return []
    names = [r.get("result") for r in rows if r.get("kind") == "pick" and str(r.get("label", "")).startswith("spawn")]
    return [norm(n) for n in reversed(names)][:limit]


def weight(c, recent):
    n = norm(c["name"])
    if n in recent[:10]:
        return 1
    if n in recent:
        return 2
    return 3


def cmd_candidates(a):
    creatures = load()
    try:
        p = party(a)
    except ValueError as e:
        return fail(str(e))
    envs = env_keys(a.env)
    if not envs:
        return fail("--env is required (a prompt tag like urban or dungeon, builder:tomb, or a raw key; see `envs`)")
    known = {e for c in creatures for e in c["environments"]}
    unknown = envs - known
    if unknown:
        return fail(f"unknown environment {', '.join(sorted(unknown))}; run `envs` for the list")
    types = {t.strip().lower() for t in (a.type or "").split(",") if t.strip()}
    recent = recent_spawns()
    ceil_i, floor_i = p["ceil_i"], p["floor_i"]
    remaining = a.remaining if a.remaining is not None else p["budget"]
    cap = 2 * p["pcs"]
    role = a.role
    if role == "lead":
        lo_i, hi_i = max(floor_i, p["base_ceil_i"] - 4), ceil_i
    elif role == "support":
        if a.lead_cr is None:
            return fail("--role support needs --lead-cr (the lead's CR) and --remaining (XP left)")
        lead_i = rung_at_or_below(parse_cr(a.lead_cr))
        lo_i, hi_i = floor_i, min(ceil_i, lead_i - 2)
        if hi_i < lo_i:
            hi_i = min(ceil_i, lead_i)
    else:  # npc or fauna: met outside a budgeted fight; fiction sets scope
        lo_i, hi_i = 0, ceil_i
    lo, hi = LADDER[lo_i], LADDER[hi_i]
    rows = []
    for c in creatures:
        if not c["spawnable"] or not (envs & set(c["environments"])):
            continue
        if types and c["type"] not in types:
            continue
        if not (lo - 1e-9 <= c["cr"] <= hi + 1e-9):
            continue
        if role in ("lead", "support") and c["cr"] == 0:
            continue
        f = flags(c)
        if a.no_magic and "IMMUNE-WEAPONS" in f:
            continue
        if a.no_ranged and "FLIES" in f:
            continue
        if role == "lead":
            if c["xp"] > remaining:
                continue
            count = 1
        elif role == "support":
            if c["xp"] <= 0 or c["xp"] > remaining:
                continue
            count = min(remaining // c["xp"], cap)
        else:
            count = 1
        rows.append((c, count, f))
    if role == "support":
        good = [r for r in rows if r[0]["xp"] * r[1] >= 0.5 * remaining]
        if good:
            rows = good
    rows.sort(key=lambda r: (r[0]["cr"], r[0]["name"]))
    label = {"lead": "spawn-lead", "support": "spawn-support", "npc": "spawn-npc", "fauna": "spawn-fauna"}[role]
    head = (f"BESTIARY · {role} · env {'/'.join(sorted(envs))} · party avg L{p['avg']:.1f} size {p['size']:g} · "
            f"{a.difficulty} budget {p['budget']} XP" + (f" · remaining {remaining}" if role == 'support' else "") +
            f" · CR window {crs(lo)}-{crs(hi)} (ceiling {crs(LADDER[ceil_i])}, floor {crs(LADDER[floor_i])})")
    print(head)
    for n in p["notes"]:
        print(f"  note: {n}")
    if not a.quiet:
        for c, count, f in rows:
            spend = f" ×{count} = {c['xp'] * count} XP" if role == "support" else f" {c['xp']} XP"
            fl = f"  [{', '.join(f)}]" if f else ""
            print(f"  CR {crs(c['cr']):>4} {c['name']} ({c['type']}){spend}{fl}")
    if len(rows) >= 2:
        pick = "|".join(f"{token(c['name'])}={weight(c, recent)}" for c, _, _ in rows)
        print(f"{len(rows)} candidates. Roll it through the engine (weights may be loaded to fit the fiction, §1-sexies):")
        print(f"{label}:pick[{pick}]")
    elif len(rows) == 1:
        print(f"Only one candidate ({rows[0][0]['name']}): a one-outcome table is a decision, not a roll. "
              f"Widen the environment or check the CR window, or treat the creature as established fact.")
    else:
        print("No candidates. Widen the environment (another tag or builder), or the budget cannot buy this role.")
    if role == "support" and rows:
        print(f"Count is the most that fits the remaining XP, capped at {cap} (2 per PC). Leftover XP may buy a third block (at most three).")
    if any(r[2] for r in rows):
        print("Flags: check IMMUNE-WEAPONS / RESIST-WEAPONS / INCORPOREAL / FLIES against what the party can actually do; "
              "a creature the party provably cannot hurt comes off the table before the roll.")
    return 0


def find_creature(name, creatures):
    n = norm(name)
    for c in creatures:
        if norm(c["name"]) == n:
            return c
    return None


def cmd_check(a):
    creatures = load()
    try:
        p = party(a)
    except ValueError as e:
        return fail(str(e))
    total_xp, total_cr, units, blocks, problems = 0, 0.0, 0, [], []
    for item in a.creatures:
        m = re.fullmatch(r"(.+?)\s*[x×]\s*(\d+)", item.strip(), re.I)
        name, count = (m.group(1), int(m.group(2))) if m else (item, 1)
        c = find_creature(name, creatures)
        if not c:
            return fail(f"not in the bestiary: {name}")
        blocks.append(c["name"])
        total_xp += c["xp"] * count
        total_cr += c["cr"] * count
        units += 1
        if c["cr"] > LADDER[p["ceil_i"]] + 1e-9:
            problems.append(f"{c['name']} CR {crs(c['cr'])} is above the ceiling CR {crs(LADDER[p['ceil_i']])}")
        if c["cr"] < LADDER[p["floor_i"]] - 1e-9:
            problems.append(f"{c['name']} CR {crs(c['cr'])} is below the combatant floor CR {crs(LADDER[p['floor_i']])}")
        if count > 2 * p["pcs"]:
            problems.append(f"{count} {c['name']} is over the cap of {2 * p['pcs']} (2 per PC)")
    if len(set(blocks)) > 3:
        problems.append(f"{len(set(blocks))} distinct stat blocks; the most is three")
    if total_xp > p["budget"]:
        problems.append(f"{total_xp} XP is over the {a.difficulty} budget of {p['budget']}")
    total_levels = sum(p["levels"])
    line = total_levels / 4 if p["avg"] < 5 else total_levels / 2
    bench = f"benchmark: total CR {total_cr:g} vs line {line:g}"
    if total_cr > line + 1e-9:
        if a.difficulty == "high":
            bench += " (over; allowed only because the difficulty is high)"
        else:
            problems.append(f"total CR {total_cr:g} is over the benchmark line {line:g} (allowed only on high)")
    print(f"CHECK · {a.difficulty} budget {p['budget']} XP · spent {total_xp} XP · {len(set(blocks))} blocks · {bench}")
    for n in p["notes"]:
        print(f"  note: {n}")
    if problems:
        for pr in problems:
            print(f"  FAIL: {pr}")
        return 1
    print("  PASS")
    return 0


def cmd_show(a):
    c = find_creature(a.name, load())
    if not c:
        return fail(f"not in the bestiary: {a.name} (try `find`)")
    sp = ", ".join(f"{k} {v} ft" for k, v in c["speed"].items()) + (" (hover)" if c["hover"] else "")
    ab = "  ".join(f"{k[:3].upper()} {v}" for k, v in c["abilities"].items())
    print(f"{c['name']} · {c['size']} {c['type']}, {c['alignment']} · CR {crs(c['cr'])} ({c['xp']} XP)")
    print(f"AC {c['ac']}{' (' + c['ac_detail'] + ')' if c['ac_detail'] else ''} · HP {c['hp']} ({c['hit_dice']}) · Speed {sp} · Initiative {c['initiative']:+d}" if c["initiative"] is not None else
          f"AC {c['ac']} · HP {c['hp']} ({c['hit_dice']}) · Speed {sp}")
    print(ab)
    extras = []
    if c["saves"]:
        extras.append("Saves " + ", ".join(f"{k[:3].upper()} {v:+d}" for k, v in c["saves"].items() if v))
    if c["skills"]:
        extras.append("Skills " + ", ".join(f"{k.replace('_', ' ')} {v:+d}" for k, v in c["skills"].items()))
    for label, key in (("Vulnerable", "damage_vulnerabilities"), ("Resist", "damage_resistances"),
                       ("Immune", "damage_immunities"), ("Condition immune", "condition_immunities")):
        if c[key]:
            extras.append(f"{label} {', '.join(c[key])}")
    if c["senses"]:
        extras.append("Senses " + ", ".join(f"{k.replace('_range', '')} {v} ft" for k, v in c["senses"].items()))
    extras.append(f"Passive Perception {c['passive_perception']}")
    if c["languages"]:
        extras.append(f"Languages {c['languages']}")
    print(" · ".join(extras))
    for t in c["traits"]:
        print(f"TRAIT {t['name']}: {t['desc']}")
    order = ["ACTION", "BONUS_ACTION", "REACTION", "LEGENDARY_ACTION"]
    for kind in order:
        for x in c["actions"]:
            if x["type"] == kind:
                lim = x.get("limit")
                lim_s = f" ({lim['type'].replace('_', ' ').lower()} {lim.get('param')})" if lim else ""
                print(f"{kind.replace('_', ' ')} {x['name']}{lim_s}: {x['desc']}")
    print(f"Environments: {', '.join(c['environments']) or 'none'} ({c['env_source']})")
    if c.get("only_via"):
        print(f"NEVER ROLLED AS A SPAWN. Enters play only through {c['only_via']}.")
    return 0


def strat_default(c):
    if c["name"] in STRAT_NAMED:
        return STRAT_NAMED[c["name"]], "§7-quinquies named default"
    if c["type"] in ("ooze", "construct") or (c["type"] == "undead" and c["abilities"].get("intelligence", 10) <= 4):
        return 0, "mindless type"
    if c["type"] == "beast":
        return 1, "beast"
    if c["cr"] <= 0.5:
        return 1, "CR 1/2 or lower"
    if c["cr"] <= 3:
        return 2, "CR 1-3"
    return 3, "CR 4+ (STRAT-4 only by charter, dungeon heart, or nemesis)"


def cmd_defaults(a):
    c = find_creature(a.name, load())
    if not c:
        return fail(f"not in the bestiary: {a.name}")
    tier, why = strat_default(c)
    if tier == 0:
        morale = "no morale (mindless, §4.3)"
    elif c["type"] == "beast":
        morale = "Cowardly/Disorderly (~25% losses) unless the fiction says it is defending young or territory"
    elif c["type"] == "humanoid":
        morale = "trained/duty (~50%) for soldiers and guards; Cowardly for rabble; set by role"
    else:
        morale = "Brave/Orderly (~65%); Fanatical only if the fiction makes it zealous or sworn"
    print(f"{c['name']} · default {STRAT_NAMES[tier]} ({why}) · morale default: {morale}")
    print("Defaults, not ceilings: a charter, a grudge (§7-sexies), or the dungeon heart can move them.")
    return 0


def cmd_find(a):
    q = norm(a.text)
    hits = [c for c in load() if q in norm(c["name"])]
    for c in hits:
        print(f"CR {crs(c['cr']):>4} {c['name']} ({c['type']}) · envs {', '.join(c['environments']) or 'none'}")
    if not hits:
        print("no match")
    return 0


def cmd_envs(a):
    from collections import Counter
    cnt = Counter(e for c in load() if c["spawnable"] for e in c["environments"])
    print("Bestiary environment keys (creature counts):")
    print("  " + ", ".join(f"{k} {v}" for k, v in sorted(cnt.items())))
    print("Prompt tags -> keys:")
    for k, v in TAG_MAP.items():
        print(f"  {k}: {', '.join(v)}")
    print("Delve builders (use builder:<name>):")
    for k, v in BUILDER_MAP.items():
        print(f"  {k}: {', '.join(v)}")
    return 0


def main(argv):
    ap = argparse.ArgumentParser(prog="bestiary.py", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd")

    def party_args(p):
        p.add_argument("--levels", required=True, help="PC levels, comma separated")
        p.add_argument("--npcs", type=int, default=0, help="party NPCs (count half)")
        p.add_argument("--difficulty", choices=list(DIFF), default="moderate")
        p.add_argument("--boss", action="store_true")
        p.add_argument("--first-fight", action="store_true")

    c = sub.add_parser("candidates")
    party_args(c)
    c.add_argument("--env", required=True)
    c.add_argument("--role", choices=["lead", "support", "npc", "fauna"], default="lead")
    c.add_argument("--remaining", type=int)
    c.add_argument("--lead-cr")
    c.add_argument("--type")
    c.add_argument("--no-magic", action="store_true")
    c.add_argument("--no-ranged", action="store_true")
    c.add_argument("--quiet", action="store_true")
    k = sub.add_parser("check")
    party_args(k)
    k.add_argument("creatures", nargs="+")
    for name in ("show", "defaults"):
        s = sub.add_parser(name)
        s.add_argument("name")
    f = sub.add_parser("find")
    f.add_argument("text")
    sub.add_parser("envs")
    a = ap.parse_args(argv)
    if not a.cmd:
        print(__doc__.strip())
        return 2
    return {"candidates": cmd_candidates, "check": cmd_check, "show": cmd_show, "defaults": cmd_defaults,
            "find": cmd_find, "envs": cmd_envs}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
