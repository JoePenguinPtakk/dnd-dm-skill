#!/usr/bin/env python3
"""Module-to-manifest generator.

Reads a published module's section index plus a hand-authored scope map, joins
them, and emits the canonical content manifest and a coverage-ledger seed for a
chosen campaign configuration (which villain, which chapter-1 branch).

Generic in shape: any module with a section-index JSON in the same format and a
scope map in the SPEC schema works here. The Dragon Heist scope map is the first
instance. See SPEC_module-charter-generator_2026-08-22.md.

Usage:
  python3 module_manifest.py \
      --sections inputs/dragon_heist_sections.json \
      --scopemap dragon_heist.scopemap.json \
      --villain xanathar --ch1 zhent \
      --out-dir out --slug dragon_heist
"""
import argparse
import json
import os
import re
from collections import defaultdict

AREA_KEY = re.compile(r"^([A-Za-z]+)\d")  # letter prefix + at least one digit


def group_of(key):
    m = AREA_KEY.match(str(key))
    return m.group(1) if m else None


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def resolve_in_scope(scope_tag, chosen_villain, chosen_ch1, scopemap):
    """Is content with this scope_tag in scope for the chosen configuration?"""
    if scope_tag in scopemap["always_in_scope_tags"]:
        return True
    vc = scopemap["scope_rules"]["villain_choice"]["options"]
    if scope_tag.startswith("villain:"):
        chosen_tag = vc[chosen_villain]["in_scope_tag"]
        return scope_tag == chosen_tag
    b = scopemap["scope_rules"]["ch1_branch"]["options"]
    if scope_tag.startswith("branch:"):
        chosen_tag = b[chosen_ch1]["in_scope_tag"]
        return scope_tag == chosen_tag
    return False  # unknown tag: out of scope until classified


def build_areas(sections, scopemap, chosen_villain, chosen_ch1):
    groups = scopemap["location_groups"]
    areas = []
    unknown_groups = set()
    for s in sections:
        key = s.get("key")
        if not key:
            continue
        g = group_of(key)
        if g is None:
            continue  # pure-numeric key: front-matter table / appendix, not an area
        meta = groups.get(g)
        if meta is None:
            unknown_groups.add(g)
            continue
        scope_tag = meta["scope_tag"]
        areas.append({
            "key": str(key),
            "name": s.get("title", "").strip(),
            "location_group": g,
            "location_name": meta["name"],
            "chapter": meta["chapter"],
            "scope_tag": scope_tag,
            "box_text_present": True,  # book convention: every keyed area carries box text (PROTOCOL_AUDIT #4)
            "in_scope": resolve_in_scope(scope_tag, chosen_villain, chosen_ch1, scopemap),
            "summary": (s.get("gist") or "").strip()[:200],
            "source_ref": {"page": s.get("page"), "section_id": s.get("id")},
        })
    return areas, unknown_groups


def build_npcs(scopemap, chosen_villain, chosen_ch1):
    out = []
    for n in scopemap.get("npcs", []):
        out.append({
            "name": n["name"],
            "scope_tag": n["scope"],
            "location_group": n.get("location_group"),
            "in_scope": resolve_in_scope(n["scope"], chosen_villain, chosen_ch1, scopemap),
            "audit_footprint": n.get("audit_footprint"),
        })
    return out


def ledger_seed(areas, module, villain, ch1):
    """Rollup markdown: one block per in-scope location_group, all areas untouched."""
    in_scope = [a for a in areas if a["in_scope"]]
    by_group = defaultdict(list)
    for a in in_scope:
        by_group[a["location_group"]].append(a)
    lines = [
        f"# Coverage ledger seed: {module}",
        "",
        f"Configuration: villain={villain}, ch1-branch={ch1}. In-scope areas only.",
        "Status enum: untouched / glimpsed / rendered / resolved / skipped.",
        "`rendered` = box text read or paraphrased (the book's definition of visited).",
        "Seeded all-untouched; the DM advances rows in play and at save-write.",
        "",
        "| Group | Location | Chapter | Rendered/Total | Areas (status) |",
        "|---|---|---|---|---|",
    ]
    for g in sorted(by_group):
        rows = sorted(by_group[g], key=lambda a: a["key"])
        loc = rows[0]["location_name"]
        ch = rows[0]["chapter"]
        cells = " ".join(f"{r['key']}:untouched" for r in rows)
        lines.append(f"| {g} | {loc} | {ch} | 0/{len(rows)} | {cells} |")
    lines.append("")
    lines.append(f"In-scope total: {len(in_scope)} areas across {len(by_group)} locations.")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sections", required=True)
    ap.add_argument("--scopemap", required=True)
    ap.add_argument("--villain", required=True)
    ap.add_argument("--ch1", required=True)
    ap.add_argument("--out-dir", default="out")
    ap.add_argument("--slug", required=True)
    args = ap.parse_args()

    sections = load(args.sections)
    scopemap = load(args.scopemap)

    areas, unknown = build_areas(sections, scopemap, args.villain, args.ch1)
    npcs = build_npcs(scopemap, args.villain, args.ch1)

    manifest = {
        "module": scopemap["module"],
        "system": scopemap.get("system"),
        "config": {"villain": args.villain, "ch1_branch": args.ch1,
                   "season": scopemap["scope_rules"]["villain_choice"]["options"][args.villain]["season"]},
        "generated": "module_manifest.py",
        "scope_rules": scopemap["scope_rules"],
        "areas": areas,
        "npcs": npcs,
    }

    os.makedirs(args.out_dir, exist_ok=True)
    mpath = os.path.join(args.out_dir, f"{args.slug}.manifest.json")
    lpath = os.path.join(args.out_dir, f"{args.slug}.ledger_seed.md")
    with open(mpath, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)
    with open(lpath, "w", encoding="utf-8") as fh:
        fh.write(ledger_seed(areas, scopemap["module"], args.villain, args.ch1))

    total = len(areas)
    ins = sum(1 for a in areas if a["in_scope"])
    print(f"areas: {total} keyed, {ins} in-scope, {total - ins} backdrop")
    print(f"npcs: {len(npcs)} ({sum(1 for n in npcs if n['in_scope'])} in-scope)")
    if unknown:
        print(f"WARNING unmapped location groups: {sorted(unknown)}")
    print(f"wrote {mpath}")
    print(f"wrote {lpath}")


if __name__ == "__main__":
    main()
