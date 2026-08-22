#!/usr/bin/env python3
"""Live content table: the module-driven, forward-looking replacement for a
hand-built campaign d100.

The old WATERDEEP_URBAN_D100 was authored backward from played sessions, so its
entries were NPCs and threads the party had already met; forward, it surfaced no
unplayed module content. This tool regenerates a rollable table from the LIVE
horizon each stage, so a triggered, quest-linked disturbance (master prompt §5)
rolls straight onto the module's actual live content, in story order, and
advancing it marks coverage and can trip the spine.

It is the quest-linked source. Ambient disturbances still use the generic §6
live-tables (world texture). See MASTER_PROMPT_supplement_chartered-module.md.

The band split mirrors the master prompt's own content engine intent:
  1-8   advance the arc     (spine_hooks: the story-moving results)
  9-16  flesh out the beat  (content hooks for untouched, in-scope live areas)
  17-19 someone surfaces    (a live NPC of this stage the party has not met)
  20    wild card           (defer to the generic §6 wildcard intersection)

Usage:
  python3 content_table.py --manifest out/dragon_heist.manifest.json \
      --spine dragon_heist.spine.json --hooks dragon_heist.hooks.json \
      --stage s2-fireball-gralhund [--ledger live_ledger.json] [--met met.json]
"""
import argparse
import json
from horizon import load, resolve_live_groups


def band(rows, lo, hi):
    """Distribute `rows` across die faces lo..hi inclusive, evenly."""
    faces = list(range(lo, hi + 1))
    if not rows:
        return [(f, None) for f in faces]
    out = []
    for i, f in enumerate(faces):
        out.append((f, rows[i * len(rows) // len(faces)]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--spine", required=True)
    ap.add_argument("--hooks", required=True)
    ap.add_argument("--stage", required=True)
    ap.add_argument("--ledger", help="JSON map {area_key: status}; absent = all untouched")
    ap.add_argument("--met", help="JSON list of NPC names already met; absent = none met")
    args = ap.parse_args()

    manifest = load(args.manifest)
    spine = load(args.spine)
    hooks = load(args.hooks).get("by_area", {})
    ledger = load(args.ledger) if args.ledger else {}
    met = set(load(args.met)) if args.met else set()

    villain = manifest["config"]["villain"]
    stage = next(s for s in spine["stages"] if s["id"] == args.stage)
    live_groups = resolve_live_groups(stage, manifest, villain)

    # untouched, in-scope areas in the live horizon that carry an authored hook
    live_areas = [a for a in manifest["areas"]
                  if a["in_scope"] and a["location_group"] in live_groups
                  and ledger.get(a["key"], "untouched") in ("untouched", "glimpsed")]
    content_rows = []
    for a in sorted(live_areas, key=lambda x: x["key"]):
        for h in hooks.get(a["key"], []):
            content_rows.append(f"**{a['name'].title()}** ({a['key']}, {h['trigger']}). {h['hook']}")

    # spine hooks: the story-moving results
    spine_rows = list(stage["spine_hooks"])

    # live NPCs of this stage not yet met
    stage_npcs = [n for n in stage.get("npcs", []) if n != "__chosen_villain__"]
    if "__chosen_villain__" in stage.get("npcs", []):
        vn = next((x["name"] for x in manifest["npcs"]
                   if x["scope_tag"] == f"villain:{villain}" and x.get("audit_footprint")), villain.title())
        stage_npcs.append(vn)
    npc_rows = [f"**{n}** crosses the party's path, or their agent does, on business tied to this beat."
                for n in stage_npcs if n not in met]

    out = []
    out.append(f"# Live content table (d20): {manifest['module']}")
    out.append(f"### Stage {stage['order']}: {stage['title']} ({args.stage}) · "
               f"villain={villain}, season={manifest['config']['season']}")
    out.append("")
    out.append("> Roll on a **quest-linked** disturbance (master prompt §5). Ambient disturbances use the "
               "generic §6 live-tables instead. This table is regenerated when the stage advances. "
               "A result is a situation with an implication, not a script: surface it, then yield. "
               "Marking the area rendered / advancing the spine is an engine write.")
    out.append("")
    out.append("| d20 | Band | What surfaces |")
    out.append("|---|---|---|")
    for f, r in band(spine_rows, 1, 8):
        out.append(f"| {f} | advance the arc | {r or '(reroll: no spine hook)'} |")
    for f, r in band(content_rows, 9, 16):
        out.append(f"| {f} | flesh out the beat | {r or '(no untouched hook left in horizon — reroll or roll ambient §6)'} |")
    for f, r in band(npc_rows, 17, 19):
        out.append(f"| {f} | someone surfaces | {r or '(all stage NPCs met — reroll)'} |")
    out.append("| 20 | wild card | Defer to the generic §6 wildcard intersection (d20). Let the dice be genuinely off-pattern. |")
    out.append("")
    out.append(f"_Horizon: {len(content_rows)} content hooks, {len(spine_rows)} spine hooks, "
               f"{len(npc_rows)} unmet NPCs. Regenerate when the stage changes or the ledger moves._")
    print("\n".join(out))


if __name__ == "__main__":
    main()
