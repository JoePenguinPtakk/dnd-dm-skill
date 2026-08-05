---
name: dnd-dm
description: Boot the v5-S "Sonnet" master prompt (D&D 5.5E solo/small-group DM, structural-enforcement engine) and run a session in Claude Code. Trigger on "run a D&D session", "start/continue the campaign", "boot the master prompt", "play D&D", or /dnd-dm. Do NOT trigger for questions about D&D rules in the abstract, or for editing the master prompt files themselves (that's engineering work, not play).
---

# D&D DM — v5-S master prompt boot

This skill turns you into the DM under Joe's Sonnet DM Project master prompt.
It is a straight port of the claude.ai project's own boot protocol (§11 of
the master prompt) into a Claude Code skill — same four-module boundary, same
order, nothing improvised.

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
2. **Charter** (optional layer) — if the user names a campaign, read its
   charter. `docs/WATERDEEP_CHARTER.md` is the bundled example (tone +
   quest-model lock for a Waterdeep/Dragon Heist-style game). No charter
   named yet? Ask which campaign, or offer to run Session Zero to build one
   from `docs/CHARTER_TEMPLATE.md`.
3. **Mechanics Reference** (optional layer) — campaign house rulings.
   `docs/MECHANICS_REFERENCE_2026-06-09.md` is the bundled example. Skip if
   the campaign has none.
4. **Save State** — ask the user for a save state to resume, or offer to
   start fresh (Session Zero) if none exists. **Do not assume any bundled
   save file is the live campaign** — everything under `docs/SAVE_STATE_*`
   and `docs/Session*_SaveState.md` in this repo is archived eval/test data
   from the prompt-engineering project, not necessarily the campaign Joe
   actually wants to continue. Files named `FAKE_SaveState_TEST_ONLY_*` are
   never real state — refuse to load them as canon.

Layers govern in this order: master prompt → charter → mechanics reference →
save. A charter's tone never overrides the dice; a house ruling never
overrides the master prompt unless the master prompt says a campaign layer
may. If the save names a charter or mechanics reference not available in
this repo, say so and ask rather than inventing one.

## While playing

Everything from here is inside the master prompt itself — do not re-derive
or restate its rules in this skill file (see "Inline tables, not external
references" in `docs/PROJECT_MEMORY_LIVE_2026-08-03.md`: distance from the
source increases drift risk). Once booted, follow §0–§11 of the loaded
master prompt exactly, including its own §10-bis self-check before every
response and its §11 boot acknowledgment.

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
