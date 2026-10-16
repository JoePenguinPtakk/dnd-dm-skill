# SUPPLEMENT: §6-septies · CHARTERED-MODULE CONTENT BRIDGE (design notes)

*Design notes for the v5 master prompts' §6-septies, rewritten 2026-10-16 (build 20261016c). The binding rules
are in §6-septies itself. This file explains why they exist and how the data is shaped, for whoever builds the
next module campaign. Nothing here is loaded at boot.*

---

## 0. The problem it solves

The first attempt to run *Waterdeep: Dragon Heist* under AI DMs failed in ways no single rule fixed:

- **A free-play campaign was steered into the module partway.** The module was never the spine.
- **A DM read the save, saw the party had been somewhere, and assumed they had experienced it.** Box text,
  occupants, clues and set pieces were treated as done because the location appeared in a summary.
- **The party reached the vault in a few sessions,** because nothing mechanical gated the Stone or the keys.
- **Module content was run from memory,** paraphrased, rescaled and reordered by the DM.
- **Each new DM instance knew only what the last one remembered to write at the end.**

## 1. The two tools

- **`map.py`** (skill) keeps where the party is in the module and what of it they have actually experienced. A
  unit (a keyed area such as `G8`, or an event such as `ch3-fireball`) is untouched until a `mark` with evidence
  says otherwise. Statuses only move forward: seen, played, done, or closed with a reason.
- **`book.py`** (skill) prints a unit's own text from the campaign's private book extract, so the DM reads before
  it runs. A whole module costs ~250,000 tokens; a unit costs a few hundred.

Both are inert in a campaign without a `module/` folder.

## 2. The data (`<campaign>/module/`)

| File | Written by | What it holds |
|---|---|---|
| `module.json` | hand, once | name, the book text's path (private, never committed), the drift threshold |
| `manifest.json` | a build script, then corrected by hand | groups (places), areas (keyed rooms), events (unkeyed set pieces), each with pages and, for events, the heading the text starts at |
| `spine.json` | hand: the campaign plan | ordered stages (live, opens, required, needs, milestone, ready) and branches that open after a stage |
| `progress.json` | `map.py` only | current stage, location, coverage, the drift clock |
| `coverage.jsonl` | `map.py` only | every write, appended: the audit trail |

**Live vs dormant.** A stage's `live` units are in play only while it is current. Its `opens` units are in play
from then on, for good (a home base, a recurring neighbor). A branch's units are live from the moment its
`opens_after` stage completes until its own required units are done. Everything else is dormant: the place
exists, its module content does not happen yet.

**Unauthored stages.** A stage with `ready: false` cannot be entered. This is how a plan admits it isn't finished
without letting the DM fill the gap at the table (Dragon Heist's merged Grand Chain steps).

## 3. Drift

The card measures play minutes since a live unit was last played or done, carried across sessions (the tail of
the last session is added to the next one at `session`). At the threshold (60 minutes by default), the next
content firing goes straight to the live table. This keeps the module moving without railroading: the table
offers a way in, and the players still choose.

## 4. The live table

`map.py table` prints a fixed band die and flat picks: 1–8 advance the arc (the stage's required units not yet
done); 9–16 flesh out the stage (its live events, and its places with unexperienced areas); 17–19 an open
branch; 20 the generic wildcard. An empty band reads as 1–8, and if that is empty too, as 20. Keyed areas
are folded into their place, so a firing surfaces somewhere to go or something happening, never a single room.

## 5. Saves

The save carries the `MAP:` stamp (`map.py verify`) and commits `module/` with it. Boot checks the stamp, and a
mismatch stops play. The save does not copy the coverage into prose: the record is the files, and the save
points at them.

## 6. Building the next module

1. Get a page-marked text extract of the book (`=== PAGE n ===`).
2. Build the manifest from it: keyed-area headings, plus a hand list of the unkeyed set pieces, with pages and
   headings. Dragon Heist's builder is `dragon-heist/module/build_module.py`. Check every unit with `book.py
   unit`, and fix the OCR misses by hand.
3. Write the spine from the campaign's plan. Mark any stage the plan leaves vague as `ready: false`.
4. Write a charter that names the plan's amendments and the module's "DM decides" points as rolls.
5. `map.py init`.
