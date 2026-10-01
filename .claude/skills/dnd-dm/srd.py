#!/usr/bin/env python3
"""srd.py: the SRD 5.2.1 library (rules text, spells, magic items, hazards).

Read-only. It never rolls a die. It finds and prints exact SRD text, so no
rule, spell, or item is recalled from memory, and it lists what legally fits
a loot or hazard roll and prints a ready weighted `pick[...]` for the dice
engine, which does the rolling and keeps the record.

The library lives in srd/ beside this file (built from the SRD 5.2.1 PDF by
tools/build_srd.py in the engine repo). Never read it end to end: look the
part up here, then read only that part. Creatures stay in bestiary.py.

USAGE
  Navigate the whole SRD:
  srd.py toc [CHAPTER]             chapters and sections (a chapter: its files and headings)
  srd.py find TEXT                 headings first, then text matches, with file and line
  srd.py entry NAME                one entry anywhere: a rule, condition, feat, trap, class feature
  srd.py read FILE [--from N] [--lines N]   one section file (path as `toc` prints it)

  Spells (master prompt §2: never approximate a spell):
  srd.py spell NAME                exact spell text
  srd.py spells [--class Wizard] [--level 3] [--school Evocation] [--ritual] [--concentration]

  Magic items and loot (§7-bis LOOT PROCEDURE):
  srd.py item NAME                 exact item text
  srd.py loot --rarity uncommon[,rare] [--category potion,ring] [--no-attunement]
              [--consumable | --permanent]

  Hazards (§7-bis HAZARD PROCEDURE):
  srd.py hazard NAME               exact trap, poison, contagion, or environmental effect
  srd.py hazards --env dungeon --levels 3,3,3 [--kind trap,environment,contagion,poison]
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRD = HERE / "srd"
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True  # no __pycache__ inside the skill folder
from bestiary import ACTIVE, env_keys, norm, token  # noqa: E402

RARITIES = ["Common", "Uncommon", "Rare", "Very Rare", "Legendary", "Artifact"]


def fail(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    return 1


def data(name):
    return json.loads((SRD / name).read_text())


def sections():
    return data("sections.json")["sections"]


# ---------------------------------------------------------------- navigation

def cmd_toc(a):
    secs = sections()
    if not a.chapter:
        chapter = None
        for s in secs:
            if s["chapter"] != chapter:
                chapter = s["chapter"]
                group = [x for x in secs if x["chapter"] == chapter]
                print(f"\n{chapter} ({len(group)} files)")
                shown = set()
                for x in group:
                    base = re.sub(r" \([A-Z]\)$", "", x["title"])
                    if base in shown:
                        continue
                    shown.add(base)
                    n = sum(1 for y in group if re.sub(r" \([A-Z]\)$", "", y["title"]) == base)
                    print(f"  {base}" + (f"  [{n} files, A-Z]" if n > 1 else "") + f"  p.{x['page']}")
        print("\n`srd.py toc <chapter>` lists one chapter's files and headings.")
        return 0
    q = norm(a.chapter)
    group = [s for s in secs if q in norm(s["chapter"])]
    if not group:
        return fail(f"no chapter matches {a.chapter}; run `toc` for the list")
    for s in group:
        heads = s["headings"]
        print(f"{s['file']}  ({s['title']}, p.{s['page']}, {s['lines']} lines)")
        if heads:
            print("    " + (", ".join(heads) if len(heads) <= 30 else
                         ", ".join(heads[:30]) + f", ... ({len(heads)} headings)"))
    return 0


def section_text(rel):
    return (SRD / rel).read_text().splitlines()


def cmd_find(a):
    q = a.text.lower()
    heads, body = [], []
    for s in sections():
        for i, line in enumerate(section_text(s["file"]), 1):
            if line.startswith("#") and q in line.lower():
                heads.append((s["file"], i, line))
            elif q in line.lower() and not line.startswith("<!--"):
                body.append((s["file"], i, line))
    for f, i, line in heads[:25]:
        print(f"HEADING {f}:{i}  {line}")
    if len(heads) > 25:
        print(f"  ... {len(heads) - 25} more headings")
    for f, i, line in body[:a.max]:
        j = line.lower().find(q)
        snip = line[max(0, j - 70):j + 90].replace("\n", " ")
        print(f"TEXT    {f}:{i}  ...{snip}...")
    if len(body) > a.max:
        print(f"  ... {len(body) - a.max} more text matches (narrow the search, or --max)")
    if not heads and not body:
        print("no match")
    else:
        print("Next: `srd.py entry <heading>` prints one entry; `srd.py read <file> --from <line>` reads on.")
    return 0


def block(lines, start):
    """Lines from a heading to the next heading of the same or higher level."""
    lv = len(lines[start]) - len(lines[start].lstrip("#"))
    end = len(lines)
    for j in range(start + 1, len(lines)):
        m = re.match(r"^(#+) ", lines[j])
        if m and len(m[1]) <= lv:
            end = j
            break
    return lines[start:end]


def find_entries(name, chapter=None):
    q = norm(name)
    exact, partial = [], []
    for s in sections():
        if chapter and norm(chapter) not in norm(s["chapter"]):
            continue
        lines = section_text(s["file"])
        for i, line in enumerate(lines):
            if not line.startswith("#"):
                continue
            h = norm(re.sub(r"[([].*?[)\]]", "", line.lstrip("#")))
            full = norm(line.lstrip("#"))
            if q in (h, full):
                exact.append((s, i, lines))
            elif q in full:
                partial.append((s, i, lines))
    return exact, partial


def print_entry(name, chapter=None):
    exact, partial = find_entries(name, chapter)
    hits = exact or partial
    if not hits:
        return fail(f"no heading matches {name}; try `srd.py find {name}`")
    if len(hits) > 1 and not exact:
        print(f"{len(hits)} headings contain '{name}':")
        for s, i, lines in hits[:30]:
            print(f"  {lines[i]}  ({s['file']}:{i + 1})")
        return 0
    for s, i, lines in hits[:3]:
        print(f"[{s['file']}:{i + 1}, SRD 5.2.1 p.{s['page']}+]")
        print("\n".join(block(lines, i)).strip())
        print()
    if len(hits) > 3:
        print(f"... {len(hits) - 3} more entries share that name")
    return 0


def cmd_entry(a):
    return print_entry(a.name, a.chapter)


def cmd_read(a):
    rel = a.file
    if not (SRD / rel).exists():
        cands = [s["file"] for s in sections() if norm(a.file) in norm(s["file"])]
        if len(cands) != 1:
            return fail(f"no single file matches {a.file}" + (f": {', '.join(cands[:8])}" if cands else ""))
        rel = cands[0]
    lines = section_text(rel)
    start = max(1, a.start) - 1
    end = start + a.lines if a.lines else len(lines)
    print("\n".join(lines[start:end]))
    if end < len(lines):
        print(f"\n[{rel}: lines {start + 1}-{end} of {len(lines)}; --from {end + 1} reads on]")
    return 0


# ---------------------------------------------------------------- spells

def cmd_spell(a):
    spells = data("spells.json")["spells"]
    q = norm(a.name)
    sp = next((s for s in spells if norm(s["name"]) == q), None)
    if not sp:
        near = [s["name"] for s in spells if q in norm(s["name"])]
        return fail(f"no spell named {a.name}" + (f"; did you mean: {', '.join(near[:8])}" if near else ""))
    lvl = "Cantrip" if sp["level"] == 0 else f"Level {sp['level']}"
    print(f"{sp['name']} · {lvl} {sp['school']} ({', '.join(sp['classes'])}) · SRD 5.2.1 p.{sp['page']}")
    print(f"Casting Time: {sp.get('casting_time', '?')} · Range: {sp.get('range', '?')} · "
          f"Components: {sp.get('components', '?')} · Duration: {sp.get('duration', '?')}")
    print(sp["text"])
    return 0


def cmd_spells(a):
    spells = data("spells.json")["spells"]
    out = []
    for s in spells:
        if a.cls and a.cls.lower() not in [c.lower() for c in s["classes"]]:
            continue
        if a.level is not None and s["level"] != a.level:
            continue
        if a.school and a.school.lower() != s["school"].lower():
            continue
        if a.ritual and not s["ritual"]:
            continue
        if a.concentration and not s["concentration"]:
            continue
        out.append(s)
    for s in sorted(out, key=lambda s: (s["level"], s["name"])):
        tags = "".join([" R" if s["ritual"] else "", " C" if s["concentration"] else ""])
        print(f"  {s['level']} {s['name']} ({s['school']}){tags}")
    print(f"{len(out)} spells (R ritual, C concentration). `srd.py spell <name>` for the text.")
    return 0


# ---------------------------------------------------------------- items and loot

def recent_picks(prefix, limit=30):
    """Results of `<prefix>...` picks in this campaign's ledger, newest first."""
    try:
        act = json.loads(ACTIVE.read_text())
        path = Path(act["campaign"]) / "dice" / "ledger.jsonl"
        rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    except Exception:
        return []
    names = [r.get("result") for r in rows
             if r.get("kind") == "pick" and str(r.get("label", "")).startswith(prefix)]
    return [norm(n) for n in reversed(names)][:limit]


def weight(name, recent):
    n = norm(name)
    if n in recent[:10]:
        return 1
    if n in recent:
        return 2
    return 3


def find_item(name):
    items = data("magic_items.json")["items"]
    q = norm(name)
    for it in items:
        if norm(it["name"]) == q or any(norm(v["name"]) == q for v in it["variants"]):
            return it
    for it in items:  # "Weapon, +2" or a token from a pick
        if any(norm(v["name"]) == q or norm(token(v["name"])) == q for v in it["variants"]):
            return it
    return None


def cmd_item(a):
    it = find_item(a.name)
    if not it:
        near = [i["name"] for i in data("magic_items.json")["items"] if norm(a.name) in norm(i["name"])]
        return fail(f"no magic item named {a.name}" + (f"; did you mean: {', '.join(near[:8])}" if near else ""))
    print(f"{it['name']} · {it['detail']} · SRD 5.2.1 p.{it['page']}")
    if len(it["variants"]) > 1:
        print("Versions: " + "; ".join(f"{v['name']} ({v['rarity']})" for v in it["variants"]))
    print(it["text"])
    return 0


def cmd_loot(a):
    want = []
    for r in (a.rarity or "").split(","):
        m = next((x for x in RARITIES if norm(x) == norm(r)), None)
        if r.strip() and not m:
            return fail(f"unknown rarity {r}; use {', '.join(RARITIES)}")
        if m:
            want.append(m)
    if not want:
        return fail("--rarity is required (a loaded world roll picks it first, §7-bis LOOT PROCEDURE)")
    cats = {c.strip().lower() for c in (a.category or "").split(",") if c.strip()}
    recent = recent_picks("loot")
    rows = []
    for it in data("magic_items.json")["items"]:
        if it["category"].lower() == "wondrous item":
            cat = "wondrous"
        else:
            cat = it["category"].lower()
        if cats and cat not in cats and it["category"].lower() not in cats:
            continue
        if a.no_attunement and it["attunement"]:
            continue
        if a.consumable and not it["consumable"]:
            continue
        if a.permanent and it["consumable"]:
            continue
        if "Artifact" in it["rarity"] and "Artifact" not in want:
            continue
        for v in it["variants"]:
            if v["rarity"] in want:
                rows.append((v["name"], v["rarity"], it))
    rows.sort(key=lambda r: (RARITIES.index(r[1]), r[0]))
    print(f"LOOT · rarity {'/'.join(want)}" + (f" · category {'/'.join(sorted(cats))}" if cats else ""))
    if not a.quiet:
        for name, rar, it in rows:
            tags = ", ".join(t for t in [it["category"], "attunement" if it["attunement"] else "",
                                         "consumable" if it["consumable"] else ""] if t)
            print(f"  {rar:<9} {name}  ({tags})")
    if len(rows) >= 2:
        pick = "|".join(f"{token(n)}={weight(n, recent)}" for n, _, _ in rows)
        print(f"{len(rows)} candidates. Roll it through the engine (weights may be loaded to fit the fiction, §1-sexies):")
        print(f"loot:pick[{pick}]")
        print("Then `srd.py item <result>` for the exact text. A weapon or armor result names the base "
              "item in the fiction (a +1 Longsword); a Spell Scroll result rolls its spell from `srd.py spells --level N`.")
    elif len(rows) == 1:
        print(f"Only one candidate ({rows[0][0]}): widen the category or rarity; a one-outcome table is not a roll.")
    else:
        print("No candidates. Widen the category or rarity.")
    return 0


# ---------------------------------------------------------------- hazards

KINDS = {"trap": "traps", "environment": "environmental_effects", "contagion": "contagions",
         "poison": "poisons"}


def all_hazards():
    tb = data("toolbox.json")
    for kind, key in KINDS.items():
        for h in tb[key]:
            yield kind, h


def trap_reading(h, level):
    """What a trap is at this level: its own tier, or the row of its scaling table."""
    for t in h["tiers"]:
        if t["levels"][0] <= level <= t["levels"][1]:
            return f"{t['severity']} at levels {t['levels'][0]}-{t['levels'][1]}"
    header = None
    for line in h["text"].splitlines():
        if line.startswith("| Levels"):
            header = [c.strip() for c in line.strip("|").split("|")][1:]
        m = re.match(r"^\| (\d+)[–-](\d+) \|(.*)$", line)
        if m and int(m[1]) <= level <= int(m[2]):
            cells = [c.strip() for c in m[3].strip(" |").split("|")]
            if header and len(header) == len(cells):
                cells = [f"{k} {v}" for k, v in zip(header, cells)]
            return f"scaled for levels {m[1]}-{m[2]}: {' · '.join(cells)}"
    return None


def cmd_hazard(a):
    q = norm(a.name)
    for kind, h in all_hazards():
        if norm(h["name"]) == q or norm(token(h["name"])) == q:
            head = f"{h['name']} · {kind} · SRD 5.2.1 p.{h['page']}"
            if kind == "trap":
                head += " · " + h["detail"]
            if kind == "poison":
                head += f" · {h['kind']} poison" + (f", {h['price_gp']} GP a dose" if h["price_gp"] else "")
            if h.get("environments"):
                head += f" · found in {', '.join(h['environments'])} ({h['env_source']} tags)"
            print(head)
            print(h["text"])
            return 0
    return fail(f"no hazard named {a.name}; `srd.py hazards --env <tag>` lists them, or try `srd.py entry`")


def cmd_hazards(a):
    kinds = [k.strip() for k in (a.kind or "trap,environment,contagion").split(",") if k.strip()]
    bad = [k for k in kinds if k not in KINDS]
    if bad:
        return fail(f"unknown kind {', '.join(bad)}; use {', '.join(KINDS)}")
    envs = env_keys(a.env) if a.env else set()
    if a.env and not envs:
        return fail("unknown environment; run `bestiary.py envs` for the tags and keys")
    levels = [int(x) for x in (a.levels or "").split(",") if x.strip()]
    avg = round(sum(levels) / len(levels)) if levels else None
    recent = recent_picks("hazard")
    rows = []
    for kind, h in all_hazards():
        if kind not in kinds:
            continue
        if kind != "poison":
            if not envs:
                return fail("--env is required for traps, environmental effects, and contagions")
            if not envs & set(h["environments"]):
                continue
        note = ""
        if kind == "trap" and avg is not None:
            note = trap_reading(h, avg) or ""
            if not note:
                continue  # no tier or scaling row for this level
        if kind == "poison":
            note = f"{h['kind']}, {h['price_gp']} GP" if h["price_gp"] else h["kind"]
        rows.append((kind, h, note))
    print(f"HAZARDS · {'/'.join(kinds)}" + (f" · env {'/'.join(sorted(envs))}" if envs else "")
          + (f" · party avg L{avg}" if avg is not None else ""))
    if "trap" in kinds and avg is None:
        print("  note: give --levels so each trap is read at the party's level")
    if not a.quiet:
        for kind, h, note in rows:
            print(f"  {kind:<11} {h['name']}" + (f"  ({note})" if note else ""))
    if len(rows) >= 2:
        pick = "|".join(f"{token(h['name'])}={weight(h['name'], recent)}" for _, h, _ in rows)
        print(f"{len(rows)} candidates. Roll it through the engine (weights may be loaded to fit the fiction, §1-sexies):")
        print(f"hazard:pick[{pick}]")
        print("Then `srd.py hazard <result>` for the exact text. Environment tags on hazards are hand tags.")
    elif len(rows) == 1:
        print(f"Only one candidate ({rows[0][1]['name']}): widen the environment or kinds; "
              "a one-outcome table is not a roll.")
    else:
        print("No candidates. Widen the environment or the kinds.")
    return 0


# ---------------------------------------------------------------- main

def main(argv):
    ap = argparse.ArgumentParser(prog="srd.py", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd")
    t = sub.add_parser("toc")
    t.add_argument("chapter", nargs="?")
    f = sub.add_parser("find")
    f.add_argument("text")
    f.add_argument("--max", type=int, default=15)
    e = sub.add_parser("entry")
    e.add_argument("name")
    e.add_argument("--chapter")
    r = sub.add_parser("read")
    r.add_argument("file")
    r.add_argument("--from", dest="start", type=int, default=1)
    r.add_argument("--lines", type=int)
    s = sub.add_parser("spell")
    s.add_argument("name")
    ss = sub.add_parser("spells")
    ss.add_argument("--class", dest="cls")
    ss.add_argument("--level", type=int)
    ss.add_argument("--school")
    ss.add_argument("--ritual", action="store_true")
    ss.add_argument("--concentration", action="store_true")
    i = sub.add_parser("item")
    i.add_argument("name")
    lo = sub.add_parser("loot")
    lo.add_argument("--rarity")
    lo.add_argument("--category", help="armor, potion, ring, rod, scroll, staff, wand, weapon, wondrous")
    lo.add_argument("--no-attunement", action="store_true")
    g = lo.add_mutually_exclusive_group()
    g.add_argument("--consumable", action="store_true")
    g.add_argument("--permanent", action="store_true")
    lo.add_argument("--quiet", action="store_true")
    h = sub.add_parser("hazard")
    h.add_argument("name")
    hz = sub.add_parser("hazards")
    hz.add_argument("--env")
    hz.add_argument("--levels")
    hz.add_argument("--kind")
    hz.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    cmds = {"toc": cmd_toc, "find": cmd_find, "entry": cmd_entry, "read": cmd_read,
            "spell": cmd_spell, "spells": cmd_spells, "item": cmd_item, "loot": cmd_loot,
            "hazard": cmd_hazard, "hazards": cmd_hazards}
    if a.cmd not in cmds:
        ap.print_help()
        return 1
    return cmds[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
