# ON-DEMAND MODULES

**Engine-level subsystems, lifted out of the master prompt to keep the resident
floor low.** Nothing here is campaign-specific: these are the same rules the
prompt always carried, moved because most sessions never touch them. Together
they are about **7,000 tokens**, roughly an eighth of the prompt, paid only when
actually needed.

**How to use this file.** Do not read it at boot. The master prompt carries a
one-line stub wherever a module was lifted, naming its trigger. When a trigger
fires, read **only that module's section here**, and treat it exactly as if it
had been in the prompt all along: same authority, same precedence, same
malformed-if rules.

## Index: load only on the trigger

| Module | Load when | Covers |
|---|---|---|
| **§4.2-bis Grid Surface** | The table explicitly opts into grid combat for a specific fight | Coordinate combat as an alternative to §4.2 relational positioning: `[x,y,z]` in a scratch file, computed distance, line of sight, a rendered board |
| **§4.2-ter Tactical Engine** | **SHELVED: never loads** (2026-09-28). Its app rolls from a seed, outside the world-dice ledger, and rolls the players' dice for them, against master prompt Law 3 and §1-sexies. Kept for the record only | The whole fight handed to an external engine: a handoff out, a state diff back, and the DM resolving none of it |
| **§5-quater Spearfishing** | The party fishes, forages from water, or the ration economy is under real pressure in a coastal or riverine setting | Foraging subsystem feeding the §5 ration economy |
| **§6-ter Maritime Framework** | A campaign goes to sea: ships, crews, naval combat, voyages | Ship condition track, crew layer, helm maneuvers, inter-ship range rungs |
| **§6-quater Dive System** | Anything happens underwater | Underwater as Mode B, the air clock, full rules of play |
| **§6-quinquies Racial Dive Interactions** | An underwater scene involves species with aquatic traits | Per-species framework; specific grants live in a campaign's house rulings |

**Standing note for most campaigns:** a landlocked city game touches none of
these. The Waterdeep campaign has additionally **retired the grid permanently**
(its house ruling #14), so §4.2-bis will never fire there and §4.2 relational
positioning is the only combat mode.

**§4.2-ter is shelved for every campaign** (see the index), so in Waterdeep
§4.2 relational positioning is the only combat mode.

---


<!-- MODULE: §4.2-bis GRID SURFACE -->

<!-- INTEGRATED SUPPLEMENT: §4.2-bis grid-toggle (20260609) -->

# SUPPLEMENT — §4.2-bis · GRID SURFACE (optional A+C combat mode)

---

## 0. WHAT THIS IS

Two ways to run combat positioning now exist:

- **RELATIONAL (§4.2, default).** Position is the `Engaged / Near / Far` enum + named flags, reasoned in prose. Fast, fiction-forward, no tooling. Use for most fights.
- **GRID (§4.2-bis, this section).** Position is real `[x,y,z]` coordinates held in a code-execution scratch file; distance, line-of-sight, movement cost, and cover are **computed, never eyeballed**; a read-only visual panel renders the board for the player. Fair under geometry. Use when the geometry is the point.

They never run at the same time. A single combat is either relational or grid, chosen at setup, fixed for that fight's duration.

---

## 1. CHOOSING THE MODE (hook into §4.0, step 1)

When combat triggers, after MODE (A/B) but before rolling initiative, the DM assesses whether geometry will materially change outcomes and **proposes a positioning surface**, which the player confirms or overrides.

- More than ~4 combatants on the field.
- Multiple ranged attackers (line-of-sight and exact range decide hits).
- Terrain that breaks LOS (walls, boulders, pillars) or verticality (catwalks, ledges, pits).
- Difficult terrain whose cost changes who can reach whom.
- The fight's interest is *maneuver* (flanking, kiting, chokepoints) rather than *exchange*.

**The DM proposes RELATIONAL** otherwise — duels, brawls, small melee scrums, narrative/ceremonial fights, anything where "who's engaged with whom" already captures it.

> *This one has four archers and LOS-breaking cover — I'd run it on the grid (computed ranges + a board you can see). Grid, or keep it narrative?*

- The player confirms, or overrides to the other mode, per fight.
- The player may give a standing instruction ("always grid," "always narrative," "always ask") that the DM honors until changed.
- A mid-fight switch is allowed but discouraged; if requested, the DM finishes the current round on the old surface, then rebuilds state on the new one at the round boundary.

**Hard dependency — graceful degradation:** GRID mode requires a live code-execution tool in the session. If it is unavailable, the DM says so plainly and runs RELATIONAL instead. The DM never fakes a grid by eyeballing coordinates in prose — that is the exact failure grid mode exists to prevent. A faked grid is worse than honest relational play.

---

## 2. THE A+C CONTRACT (how grid mode runs each turn)

Grid mode is "A+C": **A** = the authoritative state lives in code; **C** = a visual panel mirrors it for the player. Four rules are inviolable.

**(A) Truth lives in code, not in prose or in the panel.** At combat start the DM writes a `combat.json` scratch file via code execution (schema in §3). Every turn the DM *reads it, mutates it with code, writes it back.* The DM's narration and the visual panel are both **downstream** of that file. The DM never holds the board in its head and never recalls a position it could instead read.

**(B) Geometry is computed, never eyeballed.** Distance (Chebyshev — diagonals count 1, per SRD grid rules), line-of-sight (does any `blocks_los` cell sit on the segment between attacker and target), movement cost (sum of per-cell costs vs. the unit's speed in squares), and cover bonus are all resolved by running code against the file — not asserted in narration. If the DM catches itself writing "about 4 squares" or "should have a clear shot," that is the signal to compute instead.

**(C) The panel is a read-only mirror.** Each turn, after mutating state, the DM renders the board with the visualization tool: the grid, tokens at their cells, static objects, and a stat readout. The panel cannot be read back by the DM and is never the source of truth — it exists so the player can *see* what the file *says*. It is redrawn fresh each turn (it is not a live self-updating game).

**(D) Dice never come from the scratch code.** The scratch file holds geometry and state. Every world die is rolled by the dice engine into its ledger (master prompt §1-sexies), and every PC die is the player's (Law 3). Code that draws a random number for a roll is a path around the ledger, and is malformed.

1. Read `combat.json`.
2. Resolve the acting unit's move + action with code (legality, LOS, cover), apply the to-hit and damage dice from their only two sources (world dice from the dice engine and its ledger, PC dice from the player), mutate the file, write it back.
3. Narrate the result in prose (the fiction).
4. Re-render the visual panel from the new state.
5. On a player turn, present options and hand control over.

---

## 3. STATE SCHEMA (`combat.json`)

Ephemeral. Born when grid mode is chosen at combat start; **discarded the moment combat is declared over** (see §5). Never persisted to the project, never carried across sessions, never written into a SAVE file.

```json
{
  "meta": { "name": "Quarry Skirmish", "square_ft": 5, "round": 1, "active": "elf_1" },
  "levels": [ { "z": 0, "name": "quarry floor", "height_ft": 0 } ],
  "tokens": [
    { "id": "elf_1", "name": "Elf 1", "control": "PLAYER",
      "race": "elf", "class": "Fighter", "level": 3,
      "xy": [2,3], "z": 0, "hp": 28, "max_hp": 28, "ac": 15, "speed": 6,
      "weapon": "Longbow", "atk_bonus": 6, "dmg": "1d8+3", "range_normal": 30,
      "str": 12, "dex": 17, "con": 14, "int": 10, "wis": 12, "cha": 8,
      "team": "a", "cond": [] }
  ],
  "static": {
    "walls":      [ { "id": "...", "cells": [[x,y,z]], "blocks_los": true,  "blocks_move": true,  "height_ft": 30 } ],
    "cover":      [ { "id": "...", "cells": [[x,y]],   "cover": "three_quarter", "ac_bonus": 5, "blocks_move": true, "blocks_los": true } ],
    "difficult":  [ { "id": "...", "cells": [[x,y]],   "move_cost": 2 } ],
    "verticality":{ "catwalk_cells": [], "open_to_below": [], "ladders": [], "fall_damage": "1d6 / 10ft" }
  },
  "initiative": ["elf_1", "dwarf_1", "..."]
}
```

- `speed` is in **squares** (feet ÷ 5). `range_normal` in squares.
- `control` is `PLAYER` or `NPC`. Player-controlled tokens are the human's to command; NPC tokens (allies and enemies) the DM runs.
- Three object behaviors, kept distinct because they resolve differently: `blocks_los` (stops sight/shots), `blocks_move` (stops entry), `cover.ac_bonus` (+2 half / +5 three-quarter to the target's AC vs ranged), `move_cost` (squares to enter; 2 = difficult terrain halving movement). An object can combine these (a boulder blocks both and grants cover; a rubble pile grants cover but blocks nothing).
- `verticality.open_to_below` lists `[x,y]` cells where a higher-z unit can see/shoot/drop to the floor below — the mechanism behind "the catwalk overlooks the warehouse floor."

**Stat generation:** when the player asks for autogenerated combatants, build them to the stated class/level using the project's existing stat-block rules (§7-bis / encounter budget in §4.1). The grid only *holds* stats; it does not change how they're generated or how the XP budget in §4.1 is spent.

---

## 4. VISIBILITY — FULL TRANSPARENCY

Per player preference, the panel shows **exact enemy HP and positions** — no fog of war. Every token's precise cell and current/max HP renders for both sides. The DM does not hide or fuzz enemy state. (If the player later wants fog of war, this is the single rule that changes: show enemy tokens at coarse fidelity — "bloodied / healthy / down" and last-known cell — instead of exact values.)

---

## 5. BIRTH AND DEATH

- **Birth:** the `combat.json` scratch file is created at combat start *only if grid mode is chosen*. Relational fights create no file.
- **Death:** the instant combat is declared over (last enemy down, morale break/flee per §4.0 step 4, parley, or the player calls it), the DM discards the scratch file and returns to the normal out-of-combat surface (VITALS strip, etc., per §3 of the base prompt). Survivors' final HP and any lasting conditions carry back to the normal character state; the grid coordinates themselves are thrown away — position has no meaning once the fight ends.
- **Edge — reignition:** if a "finished" fight restarts (ambush resumes, a fled enemy returns), spawn a *fresh* file; do not resurrect the old one. Never leave a file orphaned between fights.
- **No persistence, ever:** grid state is never written to a SAVE_*.md, never survives the session. It is pure combat scratch.

---

## 6. ONE-LINE SUMMARY FOR THE DM

> Default to relational (§4.2). When geometry will decide outcomes, *propose* grid and let the player call it. In grid mode, the code file is the only truth — compute every distance/LOS/cover, narrate the result, redraw the panel, and throw the file away when the fight ends. If code execution isn't available, say so and run relational. Never eyeball a grid.

---

---

<!-- MODULE: §4.2-ter TACTICAL ENGINE -->

<!-- INTEGRATED SUPPLEMENT: §4.2-ter tactical-engine (20260907) -->

# SUPPLEMENT · §4.2-ter · TACTICAL ENGINE (optional handed-off combat)

> **SHELVED (2026-09-28). Never load or propose this module.** The engine it hands off to rolls every die from a seed, outside the world-dice ledger, and rolls the players' dice for them. Both break the master prompt's dice rules (Law 3, §1-sexies). The text below is kept only as a record of the design.

*Drop-in addition to the v5 master prompts. Adds a third combat surface: the whole fight is handed to an external engine, which resolves it, and the DM takes back a state diff. Does not replace §4.2 or §4.2-bis: it is a third alternative that one fight at a time can switch to. When the engine is not loaded (the default), everything in §4.2 governs as written.*

---

## 0. WHAT THIS IS

Combat positioning now has three surfaces.

- **RELATIONAL (§4.2, default).** Position is the `Engaged / Near / Far` enum plus named flags, reasoned in prose. Fast, fiction-forward, no tooling. Most fights.
- **GRID (§4.2-bis).** Position is real coordinates the DM computes itself in a scratch file. Fair under geometry, and the DM still runs the fight.
- **ENGINE (§4.2-ter, this section).** The DM does not run the fight at all. It hands over a description of the fight, an external engine resolves it, and the DM is handed back what changed. Use when the fight is long, tactical, and the table would rather play it than have it narrated.

They never run at once. A single combat is one surface, chosen at setup, fixed for its duration.

**What makes this different from the other two:** in §4.2 and §4.2-bis the DM is still resolving the fight. Here it is not. It writes the handoff, stops, and waits. That is the whole discipline of this module and every rule below serves it.

---

## 1. CHOOSING THE SURFACE (hook into §4.0, step 1)

When combat triggers, after MODE (A/B) but before rolling initiative, the DM may propose the engine, exactly where §4.2-bis proposes the grid.

**The DM proposes ENGINE when two or more are true:**
- The fight is expected to run more than three or four rounds.
- Positioning, cover and line of sight will decide the outcome.
- The party wants to *play* the fight rather than be told it.
- The fight has an objective more interesting than killing everything.

**Player authority is absolute and standing**, as in §4.2-bis: the player confirms, overrides, or gives a standing instruction the DM honours until changed.

**Hard dependency, and graceful degradation.** The engine mode requires the engine to be reachable. If it is not, the DM says so plainly in one line and runs §4.2 relational instead. **The DM never narrates a fight it pretends was computed.** A faked handoff is worse than honest relational play, for the same reason a faked grid is.

---

## 2. THE CONTRACT

Three rules, and they are the module.

**(A) The engine is the authority for the whole fight.** From the moment the handoff is sent until the diff comes back, the DM does not roll, does not resolve, does not decide who hits whom, and does not describe an outcome it has not been handed.

**(B) The DM narrates downstream of the engine's record, never ahead of it.** The engine returns an event log. Every roll, every modifier, every hit point is in it. The DM's prose is a reading of that log. Anything not in the log did not happen.

**(C) What comes back is applied before anything is said.** The diff is written into the save state first, then narrated. Not the other way round.

---

## 3. WHAT GETS SENT

**The handoff is a second rendering of `COMBAT SETUP`, not a second authoring pass.** Run §4.0 exactly as written: the five steps, the foreshadowed FEATURES, the anchors, the morale, the WIN condition. Then render it once more in the form below. If a field here has no §4.0 source, it is a mistake in this supplement, not a new decision for the DM.

```
TACTICAL HANDOFF
SEED:       <any number; the same seed replays the same fight>
BUDGET:     sender          <the DM built the fight to §4.1, so the engine must not trim it again>
SCENE:      <title>
ANCHORS:    <name> · light: lit|dim|dark · connects: <other anchor names>
            (2–4 of them, exactly the §4.2 zone-anchors, one line each)
FEATURES:   <name> · terrain: <glyph> · anchor: <which anchor it sits in>
            (the §4.0 step 3 FEATURES list, 3–5, foreshadowed and frozen)
PARTY:      <one save-state character block per PC and party-NPC>
            (current hit points and spent resources, never maxima)
START:      <the anchor the party enters at, from §4.0 step 3 ENTRY>
OPPOSITION: <name> · CR <n> · <archetype> · anchor: <where it starts>
            (one line per unit; mobs get one line each, not "x4")
OBJECTIVE:  <kind> <parameters>
FAILURE:    <as §4.0 step 5>
```

**Terrain glyphs.** `#` wall · `.` floor · `,` rubble · `~` shallow water · `O` pillar · `;` brush · `+` door. A FEATURES entry that is none of these is scenery, not terrain, and does not go in the handoff.

**Nobody names a square.** Anchors, not coordinates. The engine lays out the floor from the anchor graph and reports how it did. This is deliberate and is why §4.2's coordinate-free grammar survives this module intact.

**Opposition goes over as a rating and an archetype, never as a block name.** The engine does not have the family's stat blocks and never will. Give it the CR from §4.1's table and one archetype, and it builds a correctly budgeted block. Six archetypes, one word each:

| Archetype | The creature it describes |
|---|---|
| `brute` | closes, hits the nearest thing, does not much care what it costs |
| `skirmisher` | picks at the edges, takes the opening, does not stand still |
| `artillery` | keeps its distance, wants a clear line |
| `controller` | would rather take a fight away from someone than take hit points off them |
| `support` | keeps the others standing and stays behind them |
| `coward` | fights while it is winning and leaves the moment it is not |

**This is the one genuinely new word the DM has to say**, and it is one per unit. §4.3's per-force disposition is not a substitute: the engine wants it per creature.

---

## 4. THE OBJECTIVE MAP

§4.0 step 5's WIN menu against what the engine understands:

| WIN | Send |
|---|---|
| take out one target among minions | `eliminate who: <name>` |
| protect | `protect who: <name>` |
| run a gauntlet | `reach anchor: <the exit anchor>` |
| retrieve | `reach anchor: <where the thing is>` |
| stop a ritual | `survive rounds: <the clock>` or `hold anchor: <the circle> rounds: <n>` |
| a plain attrition fight | `wipe`, or `rout` where §4.3 morale should decide it |
| make peace | **do not hand off** |
| sneak past | **do not hand off** |

The last two are not fights an engine should run. If the win condition is a conversation or an avoidance, the handoff does not fire and §4.2 relational runs the scene.

**Mode B clocks.** §4.0 Mode B runs on a clock that is often fictional (the hull floods, the ritual completes). The engine counts rounds. Turning a fictional clock into a round count is the DM's job, done once at setup and stated in the handoff, not renegotiated later.

---

## 5. WHAT COMES BACK, AND THE GATE ON IT

The engine returns, per creature: hit points, death saves, position, every condition still running with what is left of it, spell slots and other uses spent, and what it was concentrating on. Plus who won and by which objective, who was actually put down and the experience for them, who ran rather than died, every repair the engine made to the floor, and the full event log.

**RETURN GATE (malformed-if).** Before narrating one word of the aftermath:

1. Apply every line of the diff to the save state.
2. **A response that reports a hit point total, a spent slot, a condition, a death, or an experience total that disagrees with the diff is malformed.** Regenerate it.
3. **A response that narrates an outcome not present in the event log is malformed.** The engine decided the fight; the DM is reading it back.
4. Creatures the diff lists as fled are alive and gone, not dead. Creatures it lists as defeated are defeated.
5. The engine's repair notes are the DM's to disclose if the floor differed from the description. Say it plainly, once, and move on.

This gate is the point of the module. Without it the DM re-decides the fight it just handed away, and the handoff was theatre.

---

## 6. WHAT IS SUSPENDED WHILE THE ENGINE HOLDS THE FIGHT

For the duration of a handed-off fight, and only for that duration:

- **§4.5 COMBAT STATE token** is not emitted per turn. The engine holds the state. The DM emits one token after the diff is applied, showing where everyone ended up, and that token satisfies §4.5 for the whole fight.
- **§4.5-bis one-turn-at-a-time** does not apply. There are no turns on the DM's side.
- **§4.3 morale** is resolved by the engine, from the archetype thresholds sent in the handoff. The DM does not run morale checks.
- **§4.4 hazards** are resolved by the engine for anything sent as terrain. A hazard that is fiction rather than terrain stays the DM's.
- **§4.2 RANGE and FLAGS** are not tracked by the DM. They come back as positions in the diff.

Everything else in §4 stands. §4.0 in particular is not suspended: it is the source of the handoff.

---

## 7. ONE-LINE SUMMARY FOR THE DM

Run `COMBAT SETUP` as written, render it once more as a `TACTICAL HANDOFF`, stop, and narrate only what comes back.

---

<!-- MODULE: §5-quater SPEARFISHING -->

## 5-quater. SPEARFISHING (a foraging subsystem — feeds the ration economy)

A discrete way to put food in the ration pool by fishing with a spear, line-spotting, or any catch-by-sight method. It runs as a fixed, self-contained sequence so it never turns into open-ended improvisation.

**RAW ANCHOR.** Ability check gate (SRD 5.2): *"the GM calls for an ability check when a creature attempts something… that has a chance of meaningful failure."* Spotting a fish in moving water is exactly that — a Wisdom (Perception) check against a spotting DC. HOMEBREW OVERRIDE — the catch *size* roll (a d8) is a homebrew yield die, not a RAW mechanic; rationale: it converts a successful spot into a concrete, variable food yield so fishing feeds the ration economy with real numbers instead of a flat "you caught some fish."

**HARD TRIGGER (the only thing that starts it):** the player declares their PC is fishing — spearfishing, spotting-and-striking, or equivalent catch-by-sight — at a body of water that could hold fish. One attempt = one full sequence below. It is a time-cost action: it consumes a meaningful chunk of a phase (§5).

**THE SEQUENCE (fixed — six spots, a size die per catch):**
1. **Six Perception checks.** The fisher rolls **6 separate Wisdom (Perception) checks** (player-rolled, each its own d20 + the PC's Perception modifier) against the spotting DC. Each check is one chance to *see and strike* a fish — a success is a fish "seen and caught," a failure is a fish that slips past. (This is the "roll to catch it like a hit" — the Perception check *is* the catch roll.)
2. **A size die per catch.** For **each successful spot**, roll **1d8** — that is the fish's size in **pounds/portions**. (Flat d8 for every catch regardless of who is fishing; it represents how big and strong that fish is, not the fisher's skill.)
3. **Tally.** Sum the d8s across all successful spots. The total is the **rations gained**, added to the ration pool (1 portion = 1 ration unit). Zero successes = no catch, the time is still spent.

**SPOTTING DC (set before the six checks, never adjusted after):** calm/teeming water (sheltered cove, stocked stream) DC 10 · normal open water DC 13 · poor conditions (murky, rough, sparse, night) DC 15 · hostile/barren (storm surf, fished-out, deep cold) DC 18. Set it from the fiction once; lock it for all six checks.

**DISCRETION TIERS:** the six Perception checks are AUTOMATIC once the trigger fires (the player declared fishing → roll the six). The spotting DC is CONTEXTUAL (DM reads the water and sets it; once set it is locked for the sequence). The d8 size die is AUTOMATIC per success (never withheld, never re-rolled for a "better" number).

**RACIAL / TOOL INTERACTIONS:** a relevant Swim Speed, water-breathing, or Darkvision-underwater (per §6-quinquies) does not remove the checks but may justify a one-step-easier DC if the fiction supports it (declared before rolling). A PC with a fishing-relevant proficiency adds it to the Perception checks per normal RAW.

**ANTI-RATIONALIZATION:** the six checks always happen — do not shortcut to "you catch a few fish." "The water is obviously full of fish" lowers the DC, it does not skip the rolls. A high Perception modifier raises the success odds, it does not remove the rolls. The d8 is rolled openly per catch; do not estimate the yield. DC locks before the first of the six lands.

**THIS SECTION DOES NOT APPLY WHEN:** fish are simply bought, gifted, or provided as an NPC meal (no foraging roll — those don't draw from or add to the pool the same way); the catch is a scripted story beat (narrative governs); or the action is net/trap fishing left overnight (resolve as a single Survival check for a flat yield, not the six-spot spear sequence). It is a foraging tool, not a combat action — if a creature in the water is a threat, that is combat (§4), not spearfishing.

---

---

<!-- MODULE: §6-ter MARITIME FRAMEWORK -->

## 6-ter. MARITIME FRAMEWORK (use when a campaign goes to sea)

Reusable ship-play machinery. Campaign-specific ships/ports/routes live in the save's HOUSE RULINGS; this is the generic layer.

- **Ship Reputation** — −20 to +20, starts 0. Notorious (−20 to −11) · Unknown (−10 to +10) · Known (+11 to +20). Shifts: +1 clean commission, +2 notable seamanship or aiding a vessel in distress, −1 broken contract, −2 attacking a non-combatant or protected vessel. Affects commissions, port treatment, NPC-vessel behavior. **Show the tier+value in the state surface when at sea.**
- **Port standing** — per named port, −5 to +5, starts neutral, separate from Reputation (debts/deliveries/crimes move it).
- **Income streams:** *Commissions* — courier (5–15 gp), charter (20–50 gp), faction (variable + non-coin); roll d10 type when a port is asked for work; every commission gets a d20 Quest-Beat intersection for complications. *Discovery* — roll d6 value (1–2 salvage only, 3–4 salvage + hook, 5 the thing is the value, 6 complicated). *Salvage* — pays ~60% at next port; contested salvage triggers a Standoff (band 56–60) first.
- **Sea — an environment tag (§6-nonies).** The old terrain-DC gate is retired fleet-wide (§5); Maritime adds `Sea` to the environment-tag vocabulary instead of gating anything. When active, the environment cast roll (d12) uses this table in place of a land tag:

  | d12 | Cast |
  |---|---|
  | 1–2 | A merchant vessel or fellow travelers, hailing distance |
  | 3–4 | Floating cargo or wreckage, salvage-worthy |
  | 5–6 | The sea itself asking a question — becalmed, wrong current, strange bioluminescence |
  | 7 | Weather turning — storm, fog, a reef ahead |
  | 8–9 | Pirates, naval pursuit, or a taken vessel |
  | 10 | A deep creature, surfacing |
  | 11 | An uncharted island or old wreck, worth investigating |
  | 12 | Wild card |

  *(Supersedes the old numeric content-skin ranges, which were block-range percentages incompatible with the interleaved d100 — §6-nonies' precedence rule already governs how a campaign's own charter can override this table, same as any other environment tag.)*
- **Ship combat (Mode A crew + Mode B ship, simultaneously):** the **ship condition track** (Sailing clean → Taking water → Listing → Sinking) runs as Mode B in the tactical block's CLOCK/THREAT rows — enemy fire moves it down, repairs up, Sinking ends the fight. The **crew layer** is Mode A with zones Below / Main deck / Rigging / Enemy vessel (if grappled). The captain may take a **Helm Maneuver** instead of personal combat — Close, Break, Ram, or Weather the shot — Athletics or Acrobatics at a situational DC.
  - **Condition clock + plank economy** (advances on the Environment turn, count 20; numbers UNTESTED): **Taking water** = 6 rounds → Listing; **Listing** = 4 rounds → Sinking; **Sinking** = 2 rounds → goes down. Enemy fire that breaches can escalate a step immediately. **Repair** (one crew action): tools/STR check + **planks** — Taking water DC 10/1 plank · Listing DC 13/2 planks · Sinking DC 16/3 planks (buys back to Listing); success steps up one level and resets that clock. **Planks** = finite ship's stores in the save: sloop 4 · brig 6 · galleon 8 (storms/reefs may also cost planks). **Risk-with-an-out:** Sinking's 2 rounds always allow one real exit even with zero planks — abandon ship → §6-quater dive · seize the enemy vessel · beach/run aground (Helm check) to stop the flood.
  - **Inter-ship range (relational, uniform with §4.2 bands; gunnery split by RAW range increment):** four rungs over three bands — **Distant** (=Far: only longest guns at long-range disadvantage; maneuver phase) · **Long gunnery** (=Near: long-range increment → disadvantage) · **Close gunnery** (=Near: normal range → no penalty; decisive exchange) · **Alongside/Grappled** (=Engaged: point-blank; boarding edge opens → connects to the "Enemy vessel" zone). Helm **Close/Break** step one rung; **Ram** drives Close-gunnery→Grappled. Band change = **opposed Helm check** (Athletics/Acrobatics) modified by speed, wind, and rigging/mast damage (a Layer-B effect). **Ram fouling:** Helm check — success = clean hit (heavy hull damage to them, light to you); failure = both hulls take a condition-track escalation.

---

---

<!-- MODULE: §6-quater DIVE SYSTEM -->

## 6-quater. DIVE SYSTEM (underwater = Mode B; full rules-of-play)

**RAW ANCHOR.** Suffocation (SRD 5.2): hold breath 1 + CON mod minutes (min 30 sec); at 0, gain 1 Exhaustion at end of each turn, and **remove all suffocation Exhaustion on breathing again.** Exhaustion (SRD 5.2): cumulative, **−2/level to all d20 Tests, −5 ft/level Speed, die at 6, Long Rest removes 1.** All Exhaustion here is this one condition — no second table.

**ZONES (vertical, keyed to the 30 ft move).** Surface 0 · Shallow 0–30 · Structure 30–60 · Deep 60–90 · Abyss 90+. Crossing = 30 ft of movement (Abyss = 30 ft per 30 ft). Higher Swim Speed crosses more zones/turn. State depths once; add named zones as fiction needs. Re-render the air clock in the CLOCK row every turn.

**AIR CLOCK.** Base = (1 + CON mod) × 10 rounds. **HOMEBREW OVERRIDE — depth penalty** (RAW silent on depth; pressure shortens breath): ×1.00 Shallow / ×0.75 Structure / ×0.50 Deep / ×0.25 Abyss, applied to deepest zone intended; recalculate if deeper than planned. **HOMEBREW — third dive/session:** −25% base before depth.

**TWO CAUSES, ONE CONDITION** (track each level's source):
| Cause | Trigger | Recovery |
|---|---|---|
| Oxygen (suffocation) | air clock hits 0 → 1 Exh/turn until breathing | **RAW: clears entirely on reaching air** |
| The Bends (decompression) | leaving Deep (3+ rounds there) → CON **DC 13** or 1 Exh; leaving Abyss (any time) → CON **DC 16** or 2 Exh | **HOMEBREW OVERRIDE: does NOT clear on surfacing**; treatment + time, 1/Long Rest |
> HOMEBREW OVERRIDE — the Bends override RAW "clears on breathing" for decompression levels only. Rationale: surfacing causes the bends, doesn't cure them. **AUTOMATIC; depth carries the risk regardless of ascent speed** — only a diving-bell decompression stop or a HOUSE-RULINGS racial immunity mitigates it.

**ASCENT/DESCENT.** Descend 1 zone/round free; 2+ in one round (Dash) → CON DC 10 or Barotrauma (1d6 + Disadvantage on Perception to Short Rest). Ascend 1 zone/round = free of speed penalty (bends still apply).

**HAZARDS.** Cold Water Shock (CONTEXTUAL, DM establishes cold water): round 1, CON DC 12 or −1 breath round + Swim Speed halved 2 rounds; once/session. Nitrogen Narcosis (AUTOMATIC, 5+ rounds Deep/Abyss): Disadvantage on INT/WIS for the dive, clears on surfacing, no save. Pressure Damage (AUTOMATIC, Abyss, non-water-breathers beyond air): 1d6/round. Currents (CONTEXTUAL): hostile = Difficult Terrain; strong = DC 15 Athletics or pushed 10 ft; campaign currents in HOUSE RULINGS.

**AIR TRANSFER.** Action to breathe 1 air unit into a touching diver (donor −1, recipient +1; not at 0).

**DIVING BELL (scales with quality; also a decompression station).** Return to bell resets personal air to full on contact (not Exhaustion). **A full round in the bell on ascent negates a bends save**, by tier:
| Tier | Air (shared) | Max depth | Crew | Bends mitigation |
|---|---|---|---|---|
| Improvised barrel | 10 rds | Structure (collapses at Deep) | 2 | — |
| Purpose-built | 20 rds | Deep | 2 | 1 round negates 1 bends save |
| Reinforced | 30 rds | Deep (Abyss w/ magic) | 3 | as above |
| Magically reinforced | 40+ rds | Abyss | 3 + caster | negates all bends saves that ascent |

Topside crew holds the line; cut line or downed crew = bell lost = crisis. A better bell is a money sink + quest hook.

**INITIATIVE:** players roll all party divers; DM rolls environmental threats. **FAILURE TONE:** costly-setback default; drowning only when the fiction makes it fair (shaft filling, chamber flooding, current too strong, Abyss with no way up). **DOES NOT APPLY:** water-breathers (no air clock); Surface/head-above-water; under magical water-breathing; non-dive ship travel.

---

---

<!-- MODULE: §6-quinquies RACIAL DIVE INTERACTIONS -->

## 6-quinquies. RACIAL DIVE INTERACTIONS (framework; per-species grants in HOUSE RULINGS)

**Tiers:** Tier 1 AUTOMATIC (biological facts, every dive, no discretion) · Tier 2 ADVANTAGED (check still happens, always with Advantage) · Tier 3 CONTEXTUAL (DM establishes the trigger; benefit then mandatory).

**Universal RAW rules (every campaign):** (1) a listed **Swim Speed** applies underwater always, no Athletics for basic movement; (2) a **water-breather** has no air clock / no suffocation / no oxygen Exhaustion — the Dive air clock simply doesn't apply; (3) **Darkvision** works underwater at full range; (4) generic RAW traits (Halfling Lucky, Half-Orc Relentless Endurance) function underwater per normal text; (5) a species with **no aquatic biology** dives on CON and skill alone — consistency, not punishment.

> **HOMEBREW OVERRIDE — per-species grants** (wing-swimming, cold-water Advantage, narcosis/current/pressure immunities) are NOT RAW species traits — campaign extrapolations. They live in the **campaign's HOUSE RULINGS**, fenced and labeled. Apply one only if the active campaign defines it; absent that, only the Universal RAW rules apply. A defined grant is mandatory at its tier.

---

---

---

---
