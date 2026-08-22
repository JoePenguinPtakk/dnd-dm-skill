#!/usr/bin/env python3
"""Horizon: the runtime glue that ties the system into a master-prompt turn.

Given the manifest (what exists), the spine (the arc, what is live now), the
ledger (what is done), and the hooks (how content enters play), compute the
current live surface: the option-menu candidates the master prompt offers this
turn, and the coverage rollup the DM sees at a glance.

This is stage-gated then proximity-aware, never a global completion meter, per
SPEC_module-charter-generator_2026-08-22.md. It surfaces only content the live
stage has made live, so the story stays in order and the party is never nudged
toward content the arc has not reached.

Usage:
  python3 horizon.py --manifest out/dragon_heist.manifest.json \
      --spine dragon_heist.spine.json --hooks dragon_heist.hooks.json \
      --stage s2-fireball-gralhund [--ledger live_ledger.json]
"""
import argparse
import json
from collections import defaultdict


def load(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def villain_groups(manifest, villain):
    """Location groups whose scope_tag is this campaign's chosen villain."""
    tag = f"villain:{villain}"
    return sorted({a["location_group"] for a in manifest["areas"] if a["scope_tag"] == tag})


def resolve_live_groups(stage, manifest, villain):
    groups = []
    for g in stage["live_content"]:
        if g == "villain":
            groups.extend(villain_groups(manifest, villain))
        else:
            groups.append(g)
    return groups


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--spine", required=True)
    ap.add_argument("--hooks", required=True)
    ap.add_argument("--stage", required=True)
    ap.add_argument("--ledger", help="JSON map {area_key: status}; absent = all untouched")
    args = ap.parse_args()

    manifest = load(args.manifest)
    spine = load(args.spine)
    hooks = load(args.hooks).get("by_area", {})
    ledger = load(args.ledger) if args.ledger else {}

    villain = manifest["config"]["villain"]
    season = manifest["config"]["season"]

    stages = spine["stages"]
    stage = next((s for s in stages if s["id"] == args.stage), None)
    if stage is None:
        raise SystemExit(f"no such stage: {args.stage}. have: {[s['id'] for s in stages]}")

    live_groups = resolve_live_groups(stage, manifest, villain)
    # in-scope areas within the live groups
    live_areas = [a for a in manifest["areas"]
                  if a["in_scope"] and a["location_group"] in live_groups]

    def status(a):
        return ledger.get(a["key"], "untouched")

    # rollup by location group
    by_group = defaultdict(list)
    for a in live_areas:
        by_group[a["location_group"]].append(a)

    npcs = [n if n != "__chosen_villain__"
            else next((x["name"] for x in manifest["npcs"]
                       if x["scope_tag"] == f"villain:{villain}" and x.get("audit_footprint")), villain.title())
            for n in stage.get("npcs", [])]

    # ---- render the horizon card ----
    out = []
    out.append(f"# Horizon: {manifest['module']}")
    out.append(f"Config: villain={villain}, season={season}. "
               f"Live stage {stage['order']}: **{stage['title']}** ({args.stage})")
    out.append("")
    out.append(f"**Objective.** {stage['objective']}")
    out.append(f"**Exit when.** {stage['exit_condition']}")
    out.append("")

    out.append("## Coverage in the live horizon (this stage only)")
    out.append("| Group | Location | Rendered/Total | Untouched areas |")
    out.append("|---|---|---|---|")
    total_u = 0
    for g in sorted(by_group):
        rows = by_group[g]
        rendered = sum(1 for a in rows if status(a) in ("rendered", "resolved"))
        untouched = [a for a in rows if status(a) in ("untouched", "glimpsed")]
        total_u += len(untouched)
        keys = " ".join(f"{a['key']}({a['name'].title()[:22]})" for a in untouched) or "-- all rendered --"
        loc = rows[0]["location_name"]
        out.append(f"| {g} | {loc} | {rendered}/{len(rows)} | {keys} |")
    out.append("")

    out.append("## Turn menu candidates (feed the master prompt option list)")
    out.append("Spine hooks advance the story; content hooks flesh out the live beat. "
               "The DM chooses, composes the prose, and logs what the party engaged.")
    out.append("")
    out.append("**Advance the arc (spine hooks):**")
    for h in stage["spine_hooks"]:
        out.append(f"- {h}")
    out.append("")
    out.append("**Flesh out the beat (content hooks for untouched, live areas):**")
    any_content = False
    for g in sorted(by_group):
        for a in sorted(by_group[g], key=lambda x: x["key"]):
            if status(a) not in ("untouched", "glimpsed"):
                continue
            for h in hooks.get(a["key"], []):
                any_content = True
                out.append(f"- [{a['key']} {a['name'].title()}] ({h['trigger']}) {h['hook']}")
    if not any_content:
        out.append("- (no authored content hooks for untouched live areas; DM improvises from the manifest summaries)")
    out.append("")
    if npcs:
        out.append(f"**NPCs live this stage:** {', '.join(npcs)}")
        out.append("")

    out.append(f"_Completion guard: {total_u} untouched areas in this horizon. "
               f"No global meter, no push to 100%. Advancing the spine with areas left "
               f"untouched logs them `skipped`, deliberately._")

    print("\n".join(out))


if __name__ == "__main__":
    main()
