# Getting Started — first-run setup (read this before booting anything)

**Who this is for.** You are an LLM. This D&D DM skill was just installed, the user wants to play,
and no campaign exists here yet. This document is the setup interview you run **before** `SKILL.md`
boots you into the DM. `SKILL.md` boots an *existing* campaign; this builds one first.

**The one rule that governs setup, same as boot (`SKILL.md` §0): you are not the DM yet.** Do not
narrate, roll, name an NPC, or open a scene until the stage is fully set and you have booted the
master prompt at the end of this flow. Setup is ordinary out-of-character work: interview the user,
one decision at a time, and confirm each before moving on. A user in a hurry to "just start" still
gets set up first; a session run off a half-built stage is wrong for the whole night.

Walk the user through the steps below in order. Each step is a decision that narrows the next.

---

## Step 1 — Existing campaign, or new?

Ask, or check the machine:

- **A campaign already exists here** (a folder with a save state, a charter, a README naming a
  tier). → You do not need this document. Go straight to `SKILL.md` and boot it.
- **Nothing is set up yet** (fresh install, no campaign). → Continue here. You are building the
  first one.

Do not guess a campaign from any example table in `SKILL.md §1`; those rows describe the machine the
skill was authored on, not this one. A fresh install starts empty.

---

## Step 2 — Capability check (this decides which master prompt you can run)

Can you execute code here? Test the dice engine now, before anything depends on it:

```
python3 <skill-dir>/roll.py d20
```

- **It runs** → you have a code engine. Tiers **v5-O / v5-S / v5-H** are available (the choice among
  them is enforcement weight, decided in Step 6).
- **It cannot run** (no shell, plain chat window, a phone) → you must use **v5-U**, where the players
  roll every die. This is not a downgrade and skips no dice; it is the correct build with no engine.
  Record this now: Step 6's tier choice is already made.

Do not improvise a third path where you write dice numbers yourself. Engine or players, never the DM.

---

## Step 3 — What are you going to play? (the defining fork)

Ask the user which kind of campaign this is. Explain the two plainly, then let them choose:

- **A. A published module** (a bought adventure with an authored main quest — e.g. a WotC hardback).
  You will build a **charter plus content artifacts** from it with the `charter-generator/` tools, so
  you know the module's whole content, track what the party has actually played, and surface the rest
  in story order. Choose this when the user wants an authored story with a spine and doesn't want the
  published content quietly skipped.
- **B. An emergent / homebrew campaign** (no module; a sandbox the world fills as you play). You will
  write a charter from `docs/CHARTER_TEMPLATE.md` and let the content engine generate beats. Choose
  this for open-ended, player-driven play with no pre-authored plot.

The difference is whether there is a **spine** (an authored throughline). A module has one; an
emergent campaign does not, and does not pretend to.

→ Module: do **Step 4A**. → Emergent: do **Step 4B**. Then both continue at Step 5.

---

## Step 4A — Build a charter from a published module

Full workflow and templates are in `charter-generator/README.md`. In brief, interview and assemble:

1. **Section index.** Get or build the module's section-index JSON (a flat list of records with the
   module's own area `key`s). If the user already has generated artifacts for this module (manifest,
   spine, hooks), skip to step 5 of this list and just confirm the config.
2. **Scope map** (`charter-generator/templates/scopemap.template.json`). Author the location groups,
   the module's pick-one rules (which villain, which branch), and the named cast. This is judgment
   work; do it with the user, not from a guess. Getting scope wrong is the expensive error.
3. **Spine** (`spine.template.json`). Express the main quest as ordered, gated stages.
4. **Hooks** (`hooks.template.json`). Natural entry paths, high-value and easily-skipped areas first.
5. **Choose the configuration.** Interview the user for the pick-one choices (e.g. which main villain,
   which chapter branch). These lock scope and season.
6. **Generate.** Run `module_manifest.py`, then `horizon.py` and `content_table.py` to produce the
   manifest, the coverage-ledger seed, and the per-stage content table.
7. **Write the charter.** From the manifest and spine: pitch, hard tone rules, the locked-facts block
   (each locked fact names the save field it reconciles against at boot), the job board, the three
   channels. A worked charter ships as the Dragon Heist example if one is bundled; mirror its shape.

At play time the **§6-septies bridge** (`docs/MASTER_PROMPT_supplement_chartered-module.md`) makes
quest-linked content firings roll onto this module's live content, in story order.

---

## Step 4B — Write a charter for an emergent campaign

Copy `docs/CHARTER_TEMPLATE.md` and interview the user through every `‹slot›`:

1. **The pitch** — register (cozy / pulpy / grim / heroic / comedic), the core loop (the repeating
   unit of play), what episodes stack into, and what it is explicitly NOT.
2. **Hard tone rules** — keep the fixed first bullet (register is tone, not outcome); tune the scope
   ceiling, the antagonist-class rule, the stakes-size rule, the pacing rule.
3. **The objective board** — the closed menu of episode shapes the campaign generates.
4. **The three channels** (Sought / Spontaneous / Free roam) — keep all three; only the flavor changes.
5. **Emergent continuity** — the only plot allowed is player-made; no secret master plan.

There is no spine and no coverage ledger here, because there is no authored content to cover. Content
comes from the generic engine (`§6`), the live-tables, and — for a city — the urban-beats table.

---

## Step 5 — House rules and setting flavor

Ask the user about each, and record the answers in the campaign's mechanics-reference / house-rules
file (Step 7). Do not enable anything unasked:

- **Setting flavor.** Is this an urban campaign? If so, the campaign-agnostic urban beats
  (`docs/MASTER_PROMPT_supplement_urban-beats.md`, §6-octies) become the ambient source; a module may
  also carry its own city table. Other settings use the generic content engine and live-tables.
- **Optional master-prompt modules.** Maritime, dive, grid combat, spearfishing, encumbrance,
  bastions and property — all off by default, each behind a trigger. Ask which the campaign expects
  (a sea campaign wants maritime; a city caper wants bastions/property). They load on demand, not at
  boot.
- **Content and safety opt-ins.** Grim-tone tables (mental strain, lasting injury) are opt-in only.
  Discuss tone and hard lines with the table; skip freely.
- **Any campaign-specific rulings** the user wants (a house price rule, a rest variant). Record them
  as durable mechanics, separate from the charter's tone and the save's state.

---

## Step 6 — Choose the tier (the master prompt build)

If Step 2 found no engine, the tier is **v5-U** and this step is already done. Otherwise present the
menu (this is `SKILL.md §2`'s tier menu) and let the user pick — do not pick for them:

| Pick | File | Best on | Difference |
|---|---|---|---|
| v5-O | `docs/MASTER_PROMPT_v5-O_HEAD.md` | Opus tier | Lightest enforcement surface. |
| v5-S | `docs/MASTER_PROMPT_v5-S_HEAD.md` | Sonnet tier | Canonical middle build; the default with no preference. |
| v5-H | `docs/MASTER_PROMPT_v5-H_HEAD.md` | Haiku and smaller | Heaviest enforcement; redundancy is the feature. |
| v5-U | `docs/MASTER_PROMPT_v5-U_HEAD.md` | Models that cannot call tools | Fires like v5-H; players throw every die, world dice included. **Joe's choice only**; never picked by the DM, and not used where the dice engine can run. |

The mechanics are identical across all four; only enforcement weight, the self-check, and the boot
sequence differ. Never describe a tier as having more or fewer rules. Record the chosen **tier letter**
in the campaign's README so a later boot never sees this menu again.

---

## Step 7 — Create the campaign's home and characters

- **Make the campaign its own folder or repo.** It holds the charter, the mechanics/house-rules file,
  the module artifacts (manifest, spine, ledger, hooks — module campaigns only), an empty/initial save
  state, and a `README.md` that names the tier letter and lists the layer files. Keep it separate from
  the skill; the skill never holds live campaign state. (A private git repo per campaign is the durable
  choice — it is the campaign's memory across machines.)
- **Characters.** New party → make PCs now (or at the first scene, per the master prompt's character
  handling), and record the sheets in the campaign's save state. Existing sheets → import them.

---

## Step 8 — Set the stage, then boot

The stage is set when all of these exist and the user has confirmed them:

- [ ] Capability known, tier chosen (Steps 2, 6)
- [ ] Module-or-emergent decided, and the charter written (Steps 3, 4A/4B)
- [ ] House rules and flavor recorded (Step 5)
- [ ] Module artifacts generated, if a module (Step 4A)
- [ ] Campaign folder created with charter, mechanics, artifacts, initial save, README (Step 7)
- [ ] Characters made or imported (Step 7)

Now hand off to **`SKILL.md`** and boot. It assembles the layer stack in order, most-stable to
least-stable:

> **master prompt (chosen HEAD) → charter → mechanics / house rules → module artifacts → save state**

Read each present layer end to end (`SKILL.md §0`, §4), test `roll.py` with one real roll, emit the
boot receipt, and only then — the gate lifts — open the first scene. That is the moment you wrap
yourself in the master prompt and become the DM. Not one sentence before.

---

## Quick map of what you have

| Need | File |
|---|---|
| Boot an existing campaign | `SKILL.md` |
| The master prompt builds | `docs/MASTER_PROMPT_v5-{O,S,H,U}_HEAD.md` |
| Write an emergent charter | `docs/CHARTER_TEMPLATE.md` |
| Build a charter from a module | `charter-generator/` (README, templates, scripts, SPEC) |
| City ambient content (any campaign) | `docs/MASTER_PROMPT_supplement_urban-beats.md` |
| Module content surfacing at play | `docs/MASTER_PROMPT_supplement_chartered-module.md` |
| The dice engine | `roll.py` |
