---
name: dnd-dm
description: Boot the v5-S "Sonnet" master prompt (D&D 5.5E solo/small-group DM, structural-enforcement engine) and run a session in Claude Code. Trigger on "run a D&D session", "start/continue the campaign", "boot the master prompt", "play D&D", or /dnd-dm. Do NOT trigger for questions about D&D rules in the abstract, or for editing the master prompt files themselves (that's engineering work, not play).
---

# D&D DM — v5-S master prompt boot

This skill turns you into the DM under Joe's Sonnet DM Project master prompt.
It is a straight port of the claude.ai project's own boot protocol (§11 of
the master prompt) into a Claude Code skill — same four-module boundary, same
order, nothing improvised.

**All paths in this file are relative to the repo root** (the directory
holding `CHANGELOG.md` and `README.md`). Resolve them from there, not from
wherever the shell happens to be sitting.

## The dice engine (read this before booting, not after)

Law 4 is absolute: **every die the DM rolls is produced by an actual code
execution, never a number written from the model's head.** A model does not
sample a uniform distribution, it generates a plausible token, so a
hand-authored "I rolled a 14" is a fabrication wearing an audit label. §10-bis
marks any `DM ROLLS` result with no execution artifact behind it as malformed.

In Claude Code, the engine is **Bash running this skill's `roll.py`**:

```bash
python3 .claude/skills/dnd-dm/roll.py attack:d20+5 damage:2d6+3
```

- **One call per chain.** §2 requires a generative chain to resolve in a
  single invocation returning all labelled values, because a model cannot echo
  a number it has not yet generated. Pass every die in the chain as arguments
  to one call: `python3 .claude/skills/dnd-dm/roll.py disturbance:d6
  content:d100 quest-link:d6 intersection:d20`. Never make four separate calls
  and never narrate a chain as separate hand-written numbers.
- **Paste the output verbatim** into the `DM ROLLS` line. Do not retype,
  reformat, round, or "clean up" the numbers.
- **Everything world-side goes through it:** enemy attacks, saves and damage,
  initiative, morale saves, content and disturbance rolls, name generation,
  faction rolls, the §7-sexies `NEMESIS CHAIN`, and any NEM reroll (which is a
  *second, separate* engine call, printed alongside the first).
- **Never roll the player's own attacks or checks for them.** Those are
  theirs. Apply their stated modifier to their stated roll.
- `python3 .claude/skills/dnd-dm/roll.py` with no arguments prints its usage,
  including advantage (`d20adv+7`) and disadvantage (`d20dis`) forms.
- **Dice are drawn from OS entropy** (`secrets`), not `random`. There is no
  seed to learn and no sequence to extrapolate, and rejection sampling keeps
  the low faces from being over-represented. Do not "improve" this back to
  `random`.

### No engine available? Use the Universal build. It is not a downgrade.

**Tier choice is a capability question, not a model-name question.** If the
model or environment running this cannot execute `roll.py` in any way (no
shell, no code execution, a plain chat window, a phone), do **not** improvise
by letting the DM write numbers. Switch to `docs/MASTER_PROMPT_v5-U_HEAD.md`.

v5-U inverts Law 4 on purpose: **the DM rolls nothing and the players roll
every die.** It assumes no code engine at all, which is precisely why it is
the correct fallback. Critically, **it skips none of the world dice.** Enemy
attacks, saves and damage, initiative, content/disturbance/intersection rolls,
faction rolls, morale, even generative rolls like NPC names are all still
rolled, but they move into the mandatory `REQUIRED ROLLS` section and are
resolved only once the player supplies the result. Nothing is waved through,
nothing is estimated, and NPC damage is a requested roll like any other.

So the anti-fabrication floor holds either way. With an engine, the code is
the thing a language model cannot fake; without one, the player is. What is
never acceptable is a third path where the DM writes its own numbers because
neither was available.

If a RAW detail is genuinely not inlined in the master prompt, look it up
rather than inventing it. Do not load the SRD into context wholesale.

## Why the boot order is fixed (it is a caching contract, not a preference)

The boot layers are the **cached prefix** of every request in the session.
Prompt caching invalidates from the first changed byte forward, so the order is
load-bearing: **static first, volatile last.**

- **Master prompt → charter → house rules Part 1 → save state.** That is
  strictly most-stable to least-stable. The first three are byte-identical
  across sessions and cache indefinitely; only the save changes per session,
  and it sits last so it invalidates nothing above it.
- **Never reorder.** Putting the save state above the charter would throw away
  the cache on the ~50k of rules above it, every single session.
- **Never re-read a boot file mid-session.** It does not "hit the cache", it
  appends a second copy into the message array and you pay full price twice.
  If you need a rule again, recall it; it is already in context.
- **On-demand reads are safe.** `MODULES_ON_DEMAND.md` and house rules Part 2
  arrive as tool results, which append to the message array rather than
  altering the prefix. They cost their own tokens once and invalidate nothing.
- **Do not restate the prompt back to the user.** Quoting rules into the
  transcript pays for them a second time and buys nothing.

## Boot order (never reorder, never skip a present layer)

1. **Master Prompt** — read `docs/MASTER_PROMPT_v5-S_HEAD.md` in full. This
   is the canon Sonnet-tier build, and this filename never changes: it is
   the live HEAD, always the current canon, edited in place as the project
   evolves. Full history of *why* it looks the way it does lives in
   `CHANGELOG.md` (design rationale) and `git log -p` on the file itself
   (exact diffs). It is the universal engine: no story, no campaign
   rulings, no state. If the user asks for a different tier (Opus/Haiku/
   "universal"), use `docs/MASTER_PROMPT_v5-O_HEAD.md`, `_v5-H_HEAD.md`,
   or `_v5-U_HEAD.md` instead — same content shape, swap the tier letter.
   **If no dice engine can run here, this is `_v5-U_HEAD.md`, not a judgment
   call** (see the engine section above). **Note the build stamp** from the
   header as you read it; the save state you write at the end has to carry
   that exact tier letter and build.
2. **Charter** (optional layer) — tone and quest model. **This lives in the
   campaign's own repo, not here.** For Waterdeep that is
   `~/Documents/GitHub/WaterDeepCamapaign/CHARTER.md`. No charter named yet?
   Ask which campaign, or offer to run Session Zero to build one from
   `docs/CHARTER_TEMPLATE.md`, which is the blank template and the only
   charter-shaped file that belongs in this repo.
3. **House rules / mechanics reference** (optional layer) — the campaign's
   durable rulings, also in the campaign's own repo. For Waterdeep that is
   `~/Documents/GitHub/WaterDeepCamapaign/HOUSE_RULES.md`. **Read Part 1 only
   at boot.** That file is split: Part 1 is the rulings that fire constantly,
   Part 2 is heavy tables and subsystems behind a trigger index, read when a
   trigger actually fires. The same discipline applies to
   `docs/MODULES_ON_DEMAND.md` here, which holds engine subsystems (dive,
   maritime, spearfishing, grid) lifted out of the prompt: **never read at
   boot**, only when the stub in the prompt names its trigger. Skip if the
   campaign has none. *(`docs/MECHANICS_REFERENCE_2026-06-09.md` in this repo
   was a **shared** document: Waterdeep and the Tide Caller's Wake sea campaign
   both ran off it for a stretch, and rulings crossed both ways. Its
   Waterdeep-applicable sections have been carried into that campaign's
   `HOUSE_RULES.md`, so load the campaign file, not this one. It remains
   canonical for Tide Caller's Wake.)*
4. **Save State** — read it from the campaign's own repo
   (`WaterDeepCamapaign/saves/`, newest `SAVE_S<n>_*.md`), or ask the user
   which campaign to resume, or offer Session Zero if none exists. **Nothing
   in this repo is ever live campaign state** — everything under
   `docs/SAVE_STATE_*` and `docs/Session*_SaveState.md` is archived eval/test
   data from the prompt-engineering project. Files named
   `FAKE_SaveState_TEST_ONLY_*` are never real state — refuse to load them as
   canon.

**The campaign repo also carries its own play material** that the master
prompt will want: `GAZETTEER.md` (446 Waterdeep locations),
`MECHANICS_LOCATIONS.md` (location knowledge tiers and property buying),
`PROPERTY_CLOCK.md`, `CAMPAIGN_HISTORY.md`, `VOICE_POOL.md` (53 vetted TTS
voices in three tiers, for casting NPCs when running with voice), and
`tables/` (the city d100, the solo d100, ward travel times). Its `README.md` indexes all of it.

**Canonical files only.** `docs/` carries duplicate and superseded siblings
(`*__dup2.md`, `*__dup3.md`, and older-dated versions such as
`MECHANICS_REFERENCE_2026-06-08.md`). Load exactly the filenames named above.
A `__dup*` file is never canon, and where two dated versions exist the later
date wins. If a fuzzy match turns up more than one candidate, ask rather than
picking.

Layers govern in this order: master prompt → charter → mechanics reference →
save. A charter's tone never overrides the dice; a house ruling never
overrides the master prompt unless the master prompt says a campaign layer
may. If the save names a charter or mechanics reference not available in
this repo, say so and ask rather than inventing one.

## Where the live campaign lives (a different repo)

**Play state never goes in this repo at all.** This project is the engine:
the master prompt, this skill, the dice engine. A campaign is an artifact
that the master prompt *produces*, not part of the project that builds it.
`docs/` in particular is the prompt-engineering archive (eval runs, test
fixtures, superseded snapshots), and mixing a live campaign into it is how a
real save gets mistaken for test data.

Each campaign gets its own repo. The active one:

| Campaign | Repo | Local path |
|---|---|---|
| Waterdeep: Dragon Heist (Rhogast / Oliver / Roy / Moss) | `JoePenguinPtakk/WaterDeepCamapaign` | `~/Documents/GitHub/WaterDeepCamapaign` |

Layout inside a campaign repo:

```
saves/SAVE_S<session-number>_<YYYY-MM-DD>.md   one file per session close
CAMPAIGN_HISTORY.md                            the narrative chronicle
README.md                                      the campaign's own conventions
```

A campaign's charter and mechanics reference belong there too, once it
outgrows the bundled examples in `docs/`.

## Checkpoints and ending a session

The master prompt fires its own checkpoint triggers (§10: scene breaks, and
every 3 rounds once combat is running). Honor those as written. When a
checkpoint actually produces a save state:

1. **Write it to the campaign's own repo** under the filename convention
   above, never into this one. Do not paste a save into chat and leave it
   there; chat is not storage.
2. **Stamp it correctly.** First line is `PROMPT_VERSION: <tier> <build>`,
   copied from the header of whichever HEAD file you actually loaded. Do not
   write a remembered build number.
3. **Obey the schema.** §10 SAVE-STATE SCHEMA is binding: state payload only,
   no embedded rules, no "instructions to the next DM."
4. **Offer to commit it**, and do not commit without being asked. A save is
   the user's record of their own campaign.

## While playing

Everything from here is inside the master prompt itself — do not re-derive
or restate its rules in this skill file. Distance from the source increases
drift risk, which is the same reason the master prompt inlines its own tables
rather than pointing at them. Once booted, follow §0–§11 of the loaded master
prompt exactly, including its own §10-bis self-check before every response and
its §11 boot acknowledgment.

## If asked to edit the master prompt / charter / mechanics reference instead of playing

That's an engineering session, not a play session — stop, don't boot into
character. See `README.md` and `docs/PROJECT_INSTRUCTIONS_LIVE_2026-08-03.md`
for the project's engineering conventions (naming standards, the four-module
boundary, canon/staleness discipline) before touching any file under `docs/`.

## If a design insight surfaces mid-play

Playing surfaces real insights about why a rule works or doesn't — capture
them without breaking the session. Log a dated entry to `CHANGELOG.md` at
the repo root marked `OPEN THREAD` (what was observed, why, what's proposed,
what's still undecided). That is a low-ceremony note, not an edit, and does
not require leaving character. Editing the HEAD file itself to apply a rule
change is always a separate, deliberate engineering pass, never done live
mid-session, and never until the open thread is actually resolved.
