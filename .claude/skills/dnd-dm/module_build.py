#!/usr/bin/env python3
"""module_build.py: turn a published module into the data map.py and book.py read (master prompt §6-septies).

Dev-time tooling, run between sessions, never at the table. It reads the book's text (a plain-text extract with
`=== PAGE n ===` markers) and a hand-written source file, and writes module/manifest.json: every keyed area
(found in the text, OCR-aware: "Zl." is Z1, "Ql0" is Q10) and every unkeyed event the source lists.

The source file (module/source.json) is the judgment, written by hand:
  {
    "module": "Title (year)", "system": "...", "plan": "...", "pages": "how page numbers read",
    "groups": {"G": {"name": "Gralhund Villa", "chapter": "3", "max_key": 19},      keyed: has max_key
               "YP": {"name": "The Yawning Portal", "chapter": "1"}},               unkeyed: events only
    "area_names": {"G1": "Locked Gates", ...},    optional: fixes or fills names the OCR misreads
    "area_pages": {"O1": 78, ...},                optional: fixes or fills pages
    "events": [{"id": "ch3-fireball", "title": "...", "group": "T", "pages": [44, 45],
                "heading": "WHAT'S HAPPENING HERE", "summary": ""}]
  }
spine.json (the campaign plan's stages) is also written by hand; see map.py's header for its fields.

  module_build.py --book books/<text>.md --source module/source.json --out module/manifest.json
  module_build.py ... --report        list the areas whose name or page the text did not give

Then check every unit with `book.py unit <ID>`, fix misses in source.json, rebuild, and run `map.py init`.
"""
import argparse
import json
import re
import sys
from pathlib import Path

HEAD = re.compile(r"^\s*_?([A-Z])\s?([0-9lI]{1,2})\s?([0-9lI]?)\s*[\.,]\s+([A-Z][A-Z'’ \-,&]{2,})")


def tidy(s):
    s = re.sub(r"\s+", " ", s).strip(" .-|,")
    return s.title().replace("'S", "'s")


def scan(book, groups):
    """Keyed headings in the text: {key: (name, page)}, first sighting wins."""
    found, page = {}, 0
    for line in open(book, encoding="utf-8-sig"):
        m = re.match(r"^=== PAGE (\d+) ===$", line.strip())
        if m:
            page = int(m.group(1))
            continue
        m = HEAD.match(line)
        if not m or m.group(1) not in groups:
            continue
        num = (m.group(2) + m.group(3)).replace("l", "1").replace("I", "1")
        mx = groups[m.group(1)].get("max_key")
        if not num.isdigit() or not mx or not 1 <= int(num) <= mx:
            continue
        key = m.group(1) + str(int(num))
        found.setdefault(key, (tidy(m.group(4)), page))
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--book", required=True)
    ap.add_argument("--source", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    src = json.loads(Path(a.source).read_text())
    groups = src["groups"]
    found = scan(a.book, groups)
    names, pages = src.get("area_names", {}), src.get("area_pages", {})
    areas, missing = [], []
    for g, d in groups.items():
        last = None
        for n in range(1, (d.get("max_key") or 0) + 1):
            k = f"{g}{n}"
            nm = names.get(k) or (found[k][0] if k in found else None)
            pg = pages.get(k) or (found[k][1] if k in found else None) or last
            if not nm or not pg:
                missing.append(f"{k}: {'name' if not nm else ''} {'page' if not pg else ''}".strip())
            areas.append({"id": k, "key": k, "title": nm or "(name unread in the OCR: see the book)", "group": g,
                          "chapter": d.get("chapter", ""), "pages": [pg] if pg else []})
            last = pg or last
    events = []
    for e in src.get("events", []):
        if e["group"] not in groups:
            sys.exit(f"event {e['id']}: unknown group {e['group']}")
        events.append(dict({"chapter": groups[e["group"]].get("chapter", ""), "summary": ""}, **e))
    ids = [x["id"] for x in areas + events]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        sys.exit(f"duplicate unit ids: {sorted(dup)}")
    bad = [i for i in ids if re.search(r"[\s|\]]", i)]
    if bad:
        sys.exit(f"unit ids cannot hold spaces, | or ]: {bad}")
    manifest = {k: src[k] for k in ("module", "system", "plan", "pages") if k in src}
    manifest.update({"groups": {g: {"name": d["name"], "chapter": d.get("chapter", "")} for g, d in groups.items()},
                     "areas": areas, "events": events})
    Path(a.out).write_text(json.dumps(manifest, indent=1) + "\n")
    print(f"MODULE BUILD: {len(areas)} areas ({len(found)} headings found in the text), {len(events)} events, "
          f"{len(missing)} areas missing a name or page -> {a.out}")
    if a.report and missing:
        print("  " + "\n  ".join(missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
