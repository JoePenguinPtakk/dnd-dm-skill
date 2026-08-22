# Spec: module-to-charter generator

**Status:** design, not built. Written 2026-08-22, overseer (Opus 4.8).
**Origin:** the three Waterdeep audits of 2026-08-22 (`WaterDeepCamapaign/COVERAGE_AUDIT`,
`PROTOCOL_AUDIT`, `LLM_LOGIC_AUDIT`). Those measured a botched run: ~12-20% of the
in-scope module content ever reached the page after 17 sessions, driven by a set of
structural gaps, not one bad session. We are not saving that campaign. We are building
a repeatable way to generate campaign boot documents from a published module so the
next run does not repeat those gaps.

## What it is for

A pipeline that turns any published 5E module into the documents a campaign boots from,
such that the DM:

1. **Knows** the full content inventory of the module (every area, NPC, faction, quest,
   set-piece), and the module's own scope rules.
2. **Tracks** how much of that in-scope content has actually reached the table, session
   over session.
3. **Surfaces** uncovered content through natural play, via pre-authored hooks plus a
   proximity pressure signal.
4. Treats not engaging content as a **deliberate, logged choice**, never a silent omission,
   and never nags toward total completion.

The party is not expected to experience everything a module contains. The system's job is
awareness and tracking, not completionism.

## Failure modes it must defeat

Each is anchored to a finding in the three audits.

- **Loot-presence read as location-presence.** The Stone left the villa, so a later boot
  read the villa as "done"; its named owners never appeared. (Coverage audit.)
- **No spatial ledger in the save schema.** What has a table survives save-to-save
  compression; rooms had no table, so they vanished. (Protocol #2.)
- **Scope blindness.** The first audit counted 102 unreachable areas as gaps, because it
  read the index, not the book's own "pick one villain, the rest are backdrop" rule.
  (Protocol #0.)
- **Locked-fact drift.** A charter fact marked locked (Jarlaxle, autumn) silently
  contradicted every save (Xanathar, spring) for 10+ sessions; nothing rechecked it.
  (Protocol #1, logic #9.)
- **Recall optimized for correctness, not completeness.** The tier system answers "what is
  in this room" on demand; nothing prompts "what rooms here have we never asked about."
  (Protocol #3.)
- **The read-aloud contract went unenforced.** The book defines "visiting" a room as its
  box text being read or paraphrased; no project layer restated that. (Protocol #4.)
- **Tone rules only push forward.** Every pacing rule said "move past faster"; none said
  "linger, this room has content." (Protocol #5.)
- **No object permanence for ungenerated rooms.** A room never narrated does not sit
  anywhere as unfinished business; the model feels no gap. (Logic #1, #2.)
- **Cross-document distance hides contradictions.** Anything checkable in one place got
  caught; anything needing two distant sources compared did not. (Logic #9.)

## Outputs (generated once per module, overseer-audited)

All five live in the **campaign repo** and are self-contained there. The generator that
produces them lives in this engine repo.

### 1. `manifest.json` — canonical content inventory

The generalized, machine-built version of what `dragon_heist_sections.json` grew into by
hand. One record per unit of content:

- `areas[]`: `{key, name, location_group, chapter, box_text_present, scope_tag, summary,
  source_ref}`
- `npcs[]`: `{name, role, location_group, faction, scope_tag, source_ref}`
- `factions[]`, `objectives[]`, `set_pieces[]`: same shape.
- `scope_rules`: the module's own branching and exclusivity rules, machine-readable. This
  is the piece audit #0 proved is load-bearing: getting scope wrong is the expensive
  error. Each rule assigns a `scope_tag` to content:
  `core | branch:<id> | villain:<id> | season:<id> | backdrop | toolbox`.
  A campaign's chosen branches resolve which tags are in scope for that run.

`box_text_present` matters: it encodes the book's own definition of a visitable room, so
the ledger can hold the DM to it.

### 2. `COVERAGE_LEDGER` — the missing spatial schema

Seeded from `manifest.json`, filtered to in-scope units. One row per unit. Status enum:

- `untouched` — never referenced in play.
- `glimpsed` — named or passed near, box text not delivered.
- `rendered` — box text read or paraphrased. The book's definition of visited.
- `resolved` — its objective or content is spent.
- `skipped` — a deliberate, logged decision not to engage. First-class, not a gap.

Full fidelity at the area level (so the V3-V8 and per-Gralhund-room resolution the audits
needed is preserved), but the **boot-check reports rolled up by `location_group`** ("Gralhund
Villa: 1/17 rendered") with drill-down on demand, so the DM sees a compact signal, not 232
rows. The ledger is a table, so it survives compression the way QUESTS and NPC REGISTRY do.

### 3. `CHARTER.md` — generated from the manifest

Inherits completeness instead of being hand-authored and lossy. Adds a **locked-facts block
with verification hooks**: every locked fact names the exact save field it must reconcile
against at boot. That closes the drift that ran unchecked for ten sessions, by turning a
cross-document comparison into a single scheduled boot step.

### 4. `HOOKS.md` — natural entry paths

Per in-scope unit, one or two pre-authored ways the content can surface in play. Raw
material for the DM, never a script. Each hook tagged by trigger type: NPC mention,
proximity, faction move, downtime, rumor. This is the generator carrying the authoring
load so the live table does not have to improvise every entry cold.

### 5. `INDEX.md` + query tool — the recall layer

The generalized tier-2 index and tier-3 query tool, extracted from the shape
`DRAGON_HEIST_INDEX.md` and `heist.py` reached organically. Keeps the 200k-token source
affordable to consult without loading it whole.

### 6. `SPINE.json` — the arc, the ordered backbone

The piece that makes this a story and not a scavenger hunt. A published module already
carries a main quest; the spine expresses it as an ordered sequence of gated stages. Each
stage binds a slice of the manifest to a beat of the story, so content becomes live because
the arc reached it, not because the party wandered near it. Schema per stage:

- `id`, `order`, `title`
- `objective`: the dramatic goal that defines the stage.
- `entry_gate`: what makes this stage become live (a prior stage resolved, an item taken, an
  NPC met).
- `exit_condition`: what resolves the stage and advances the spine.
- `live_content`: the manifest location groups and keys that become surfaceable while this
  stage is live. Future stages' content stays dormant until their gate opens.
- `spine_hooks`: the hooks that pull toward the next beat (distinct from content hooks, which
  flesh out the current one).
- `season` / `villain` bindings where the module ties them to the arc.

## The arc spine: progression, not random sampling

The manifest, ledger, and hooks answer what exists, what is done, and how a thing could
enter play. None of them answer in what order, or why now. Left alone they produce a
sandbox: 115 in-scope areas all equally available, the party grazing content at random, no
throughline. That is the opposite of what a chartered main quest is for.

The spine is the answer. It is a horizon, not a rail. At any moment exactly one stage is
live (occasionally two, during a handoff). The party moves freely inside that stage's
`live_content`, and the coverage system tracks that movement. The story advances only when
an `exit_condition` resolves, which opens the next stage's gate and makes its content live.
So:

- **Content is surfaced within the current horizon, not globally.** The pressure engine below
  draws only from the live stage's `live_content` intersected with the ledger's untouched
  rows, plus that stage's `spine_hooks`. A party in the Gralhund stage is nudged toward the
  villa's rooms and the trail to the Stone, not toward the vault it has no reason to know
  about yet.
- **The arc emerges from progression, it is not narrated as a script.** The spine orders the
  beats and gates them; the DM still improvises the prose, the scenes, and the order of
  content inside a stage. What the spine prevents is the two failure poles: aimless wandering
  (no spine) and railroading (a fixed script). It is the middle path, a directed sandbox.
- **Skipping still counts as deliberate.** A stage can exit with in-scope content left
  untouched. Those rows are logged `skipped`, not silently dropped, and the story moves on.
  The spine decides pace; the ledger keeps the honest record of what that pace cost.

## The introduction engine (hooks + pressure)

The novel core, and the "natural gameplay" half of the ask. It runs inside the current
spine stage, never across the whole module.

Each scene, a `horizon` step computes the live surface:

1. Read the live spine stage. Take its `live_content` as the candidate pool. Nothing outside
   the current horizon is eligible, so the party is never nudged toward content the story has
   not reached.
2. Within that pool, derive the party's current `location_group`(s) and adjacent ones from
   the manifest, and cross-reference the ledger for units that are `untouched` or `glimpsed`.
3. Surface a compact line to the DM combining two kinds of candidate: **content hooks** (from
   `HOOKS.md`, flesh out the current beat) and the stage's **spine_hooks** (advance to the
   next beat).
4. The DM chooses whether to reach for one. Reaching in is optional. Choosing not to is
   logged as `skipped`, deliberately, not left as a silent `untouched`.

The signal is **stage-gated then proximity-gated, never a global completion meter.** There is
no "you are 18% done, push harder." That double gate is the guard against both completionism
and against surfacing content out of story order.

## Tie to the master prompt: the turn contract

The engine layer here does not narrate. It hands the master prompt (`MASTER_PROMPT_v5-*`)
structured candidates and records structured outcomes. The turn machinery the master prompt
already runs (scene header, VITALS, the option menu / LOOP line, sequential state writes) is
where this surfaces at the table:

- **Into the turn:** the `horizon` step's output feeds the option menu. The choices the DM
  offers each turn are drawn from the live stage's content hooks and spine_hooks, so the menu
  is always both in-story and coverage-aware. The DM composes the prose around them; the
  engine supplies the candidates, the same division of labor the whole project runs on
  (engine owns truth and memory, LLM owns judgment and voice).
- **Out of the turn:** two new structured writes join the existing ones. Marking an area
  `rendered` when its box text is delivered, and advancing the spine when an `exit_condition`
  resolves, are engine state writes, not prose the DM is trusted to remember. A tool call
  does them, the way `roll.py` owns dice, so they survive compression and cannot be
  fabricated or forgotten.
- **At boot:** a new tier-2 step reads the live spine stage plus the ledger rollup, and
  reconciles the charter's locked-facts block against the save. All single-location reads,
  which is what defeats the cross-document blindness that hid the season contradiction.

## Boot and save integration

- **Boot (tier 2):** live spine stage, ledger rollup, locked-facts reconciliation. See the
  turn contract above.
- **Save-write:** the ledger and the spine's current-stage pointer update every session, like
  QUESTS and THREADS. Because each now has a table or a tracked field, they survive
  compression instead of being dropped.

## Generation pipeline (who does what)

Per the standing order that bulk generation goes to the DeepSeek mule with the overseer
specifying and auditing:

- **Mule (DeepSeek) grinds** the module OCR into a draft `manifest.json` and a draft
  `HOOKS.md`. Volume work.
- **Overseer (Claude) owns the judgment:** writes the grind prompt and its self-audit
  rubric, hand-authors the `scope_rules` (audit #0 proved scope is where getting it wrong
  is costly), scaffolds `CHARTER.md` and `INDEX.md`, and audits the mule output against the
  manifest before adoption.

## Proving ground: Dragon Heist, fresh

We build and validate the generator against Dragon Heist first, in a clean campaign:

- We already hold `dragon_heist_sections.json` (a partial manifest) and the three audits as
  ground truth.
- Success test: the generator reproduces the known in-scope area set with correct
  `scope_tag`s (the 102 backdrop areas tagged out, not counted), and a replay check shows
  the ledger plus the pressure signal would have surfaced the rooms the botched run missed
  (Gralhund owners, V3-V8, the Trollskull neighbors).

Once proven on a module we can check against, the next validation is a module we have no
existing tooling for, to force the full parse-from-scratch path end to end.

## Out of scope, deliberately

- Does not force engagement with all content. Awareness, tracking, and optional surfacing
  only.
- Does not re-scope live. `scope_rules` are set once at generation, per the module's own
  design; a scope change is a deliberate migration, not an automatic behavior.
- Does not touch or try to rescue the botched Waterdeep run.
