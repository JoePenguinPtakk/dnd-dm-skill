# Charter generator (campaign-agnostic tooling)

Tools for building a campaign charter and its content artifacts from a **published module**, so a
DM knows the module's full content, tracks how much has reached the table, and surfaces the rest
through natural play. Built in response to a coverage post-mortem where a run reached the objective
of most chapters while playing only a small fraction of the module's actual keyed content.

**This is dev-time tooling, not boot content.** None of it is loaded into a play session. The
master prompt (the "hook") stays lean; these tools run *before* play to produce the artifacts a
chartered campaign then boots from. The runtime behavior that consumes those artifacts lives in the
two content supplements (`../docs/MASTER_PROMPT_supplement_chartered-module.md` §6-septies and
`../docs/MASTER_PROMPT_supplement_urban-beats.md` §6-octies).

## What it produces

| Artifact | Campaign-agnostic? | Where it lives |
|---|---|---|
| `manifest.json` | generated | the campaign's private module material |
| coverage ledger seed | generated | the campaign's private module material |
| live content table (per stage) | generated | the campaign's private module material |
| `CHARTER.md` | campaign-specific | the campaign's private module material |
| the scope map, spine, hooks (inputs you author) | campaign-specific | the campaign's private module material |

**Only the tools and templates here are campaign-agnostic.** A specific module's scope map, spine,
hooks, and every generated output are campaign material and belong in that campaign's own repo, not
in this public skill.

## The pieces

- `module_manifest.py` — generic. Joins a module's section-index JSON to a hand-authored scope map,
  resolves what is in scope for a chosen configuration (which villain, which branch), emits the
  manifest and a coverage-ledger seed.
- `horizon.py` — generic. Computes the live surface for a spine stage (untouched, in-scope content
  in the current horizon) as an at-a-glance rollup.
- `content_table.py` — generic. Regenerates a rollable d20 per stage from the live horizon: the
  forward-looking, module-driven table a quest-linked disturbance rolls onto (§6-septies).
- `templates/` — annotated empty schemas for the three files you author per module: `scopemap`,
  `spine`, `hooks`.
- `SPEC_module-charter-generator.md` — the full design, and every failure mode it defeats.

## Workflow (module to charter)

1. **Section index.** Obtain or build a section-index JSON for the module: a flat list of records,
   each `{id, key, title, page, chapter, gist, ...}`, where `key` is the module's own area key
   (e.g. `"G11"`) and is `null` for non-keyed prose. Keyed areas are `<letter-prefix><number>`.
2. **Author the scope map** (`templates/scopemap.template.json`). Map each key prefix to a location
   group with a `scope_tag`, encode the module's pick-one rules (villain, branch) in `scope_rules`,
   and list the named cast. This is the judgment step; do it by hand.
3. **Author the spine** (`templates/spine.template.json`). Express the module's main quest as
   ordered, gated stages, each binding location groups to a story beat.
4. **Author hooks** (`templates/hooks.template.json`). Natural entry paths for the high-value and
   easily-skipped areas first.
5. **Generate.**
   ```
   python3 module_manifest.py --sections <sections.json> --scopemap <scopemap.json> \
       --villain <choice> --ch1 <branch> --out-dir out --slug <module>
   python3 horizon.py       --manifest out/<module>.manifest.json --spine <spine.json> \
       --hooks <hooks.json> --stage <stage-id>
   python3 content_table.py --manifest out/<module>.manifest.json --spine <spine.json> \
       --hooks <hooks.json> --stage <stage-id> [--ledger live_ledger.json]
   ```
6. **Write the charter** from the manifest and spine, and drop the four artifacts (manifest, ledger,
   spine, hooks) into the campaign's module material. The §6-septies bridge does the rest at play
   time.

Python 3 standard library only. No dependencies.
