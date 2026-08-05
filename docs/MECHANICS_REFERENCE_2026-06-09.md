# CAMPAIGN MECHANICS REFERENCE
### Durable house-ruling layer · load AFTER the charter, BEFORE the save state
### `MECHANICS_REFERENCE_2026-06-08.md` · adds §1.3 (land fatigue), §2.1 (fishing), §11 (dream), §12 (oath), §13 (XP scaling), §14 (dice ownership), §15 (sanctuary), §16 (combat discipline), §17 (name gen), §18 (HP + crit conventions)

> **What this document is.** The campaign's accumulated **house rulings and rules clarifications** —
> durable mechanics that are neither in the master prompt (general engine) nor tone (charter) nor
> volatile state (save). They change *how dice resolve* in this specific campaign, and they change
> rarely. One stable home means they stop drifting or getting re-derived each session.
>
> **PRECEDENCE (binding):** Master prompt (any v5 tier) + 5.5E RAW first → charter tone second →
> **this mechanics reference third** → save state (volatile values) last. If anything here ever
> conflicts with the master prompt or charter, they win and this yields. This doc records *campaign
> rulings*, not new core rules.
>
> **Boot order:** master prompt (v5-{O/S/H/U}) → charter → **this doc** → save state.
> The save's HOUSE RULINGS section references this doc by name (`MECHANICS_REFERENCE_YYYY-MM-DD.md`);
> only genuinely new, not-yet-consolidated rulings appear in the save until folded in here at the
> next consolidation.
>
> **Version pins removed by design.** This doc references the master prompt by NAME, never by version
> string, so a tier change or renumber can't break it.

---

## SECTION INDEX

| § | Title | Source |
|---|---|---|
| 1.1 | Disturbance DC by civilization-proximity | S2 |
| 1.2 | Travel-fatigue clock (sea) | S2 |
| 1.3 | Travel-fatigue clock (land) | S1-Heresy |
| 2 | Ration economy | S1 / S2 |
| 2.1 | Fishing subsystem | S1 / S1-Heresy rev. |
| 3.1 | Bosun tier — Cobb | S1 |
| 3.2 | The hands — crew as resource | S1 |
| 3.3 | Crew morale & the "pattern" principle | S2 |
| 4.1 | Mob unit — physical co-op | S1 |
| 4.2 | Underwater rules | S1 |
| 4.3 | Beast Master — Romp's Croc | 2024 RAW |
| 4.4 | Capture vs. HP-grind ruling | S2 |
| 5.1 | Gunpowder weapons | S1 |
| 6.1 | Owlin culture — Waygonging | S1 |
| 6.2 | Anosmia — Sorin & Dav | S1 |
| 7 | Standing reminders (tone-mechanics) | ongoing |
| 8.1 | Grid-toggle default (§4.2-bis) | S5 consolidated |
| 8.2 | JSON truth contract | S5 consolidated |
| 8.3 | Air-clock math (dive) | standing |
| 8.4 | Combat State token obligation | 2026-06-07 |
| 8.5 | Crew mob / named NPC initiative split | S4 / S5 |
| 9 | Fire spread subsystem | S5 |
| 10 | Initiative gap — unrolled PC/crew numbers | S5 |
| 11 | Dream protocol | S1-Heresy |
| 12 | Player oath subsystem | S7 |
| 13 | XP threshold scaling (party-size) | S7 |
| 14 | Dice ownership | S7 |
| 15 | Sanctuary / home base rest | S7 |
| 16 | Combat discipline ⚑ (turn structure, RANGE codewords, death saves, dice sovereign) · §16.5 hood convention (permanent) | S2-Heresy |
| 17 | Name generation — full five-roll sequence ⚑ | S2-Heresy |
| 18 | HP level-up convention ⚑ | S2-Heresy |

*⚑ = staged here, pending promotion to master prompt family (all four tiers). Not campaign-specific.*

---

## 1. WORLD & TRAVEL

### 1.1 Disturbance DC by civilization-proximity (player-established S2)
Replaces the master prompt's flat terrain DCs for both sea and land travel. **DC = proximity base +
travel-fatigue clock (§1.2 / §1.3).** The danger scales with *where* you travel (how far from people
who keep order), not by terrain type alone.

| Civilization proximity (base) | DC |
|---|---|
| In/at a settlement, anchored at port | — (safe; no rolls) |
| Patrolled / trafficked terrain near a settlement (~1 day's travel) | 8 |
| Open road or coastal water, no settlement near | 11 |
| Remote / uninhabited terrain, uncharted, lawless reach | 15 |
| Deep wilderness / storm / cursed terrain | 18 |

Storm or cursed conditions can push a remote-but-not-deep location toward 18. Set the DC once before
the phase's disturbance roll, lock it.

### 1.2 Travel-fatigue clock — sea (player-established S2)
Each full day at sea **beyond the first** WITHOUT a sheltered-port night raises that day's Disturbance
DC by **+1**, cumulative. **Resets on a port night.** This is the at-sea attrition lever — NOT
disadvantage on the disturbance die (which would invert the logic).

> Example: a remote island on day 3 of an unbroken voyage = base 15 + 2 fatigue = DC 17. Secure Rest
> (master prompt §5-bis) runs independently (exhaustion from no safe rest). The two stack.

### 1.3 Travel-fatigue clock — land (S1-Heresy; mirrors §1.2)
Identical logic applied to overland travel: each full day in the wilderness **beyond the first**
WITHOUT a sheltered-settlement night raises that day's Disturbance DC by **+1**, cumulative.
**Resets on a settlement night** (inn, walled camp, safe house — somewhere with walls, a door, and
people who keep watch).

> Example: Day 3 on remote moors without returning to town = base 15 + 2 fatigue = DC 17. A night
> in a shepherd's ruin counts as adequate shelter for rest purposes (no exhaustion) but does NOT reset
> the fatigue clock — it is not a settlement. The DM rules borderline cases; rule of thumb: does
> someone keep watch here by profession?

---

## 2. RATION ECONOMY (player-established S1, finalized S2)

Rations are tracked in **UNITS** (1 unit = 1 person-day of food). Pools are campaign-defined.

- **Party rations** — feed PCs + party NPCs. Decrement by party size at the night phase. Stocked at
  settlement; supplemented by fishing (§2.1) or foraging (RAW Survival check, DM adjudicates yield).
- **NPC-provided meals** (tavern, host's table, festival) draw from no pool.
- **Prisoners / passengers** eat from the relevant pool at **1 unit/day each**.
- **The pools never combine** where multiple pools exist. A party out of rations suffers RAW exhaustion
  regardless of how full any other pool is.

*Sea-campaign addition:* **Crew stores** feed the hands separately. Managed by the bosun. Spearfishing
yield adds to the party pool; the captain may transfer surplus to crew stores by ruling.

### 2.1 Fishing subsystem (ruling — replaces spearfishing pointer to master prompt §5-quater)

Fishing requires **water access and appropriate gear** (spear, rod, net, or bare hands for shallow
water). Resolve once per fishing attempt. The DM sets the scene (river, tidal pool, open water).

**Step 1 — Spot (×6 Perception checks)**
Each fishing character rolls **6 Perception checks** against a DM-set DC (default DC 12; adjust for
water clarity, depth, time of day). Each **success** = one fish spotted. Record the count. A character
who spots 0 fish catches nothing and skips Steps 2–3. Passive Perception does not substitute — active
attention is required.

**Step 2 — Strike (d20 attack per fish spotted)**
For each fish spotted, the character makes an **attack roll** appropriate to the method:
- Spear / hand → melee attack (STR or DEX, character's choice)
- Rod / line → contested DEX check vs. fish DEX 10
- Other tools: DM adjudicates

Apply proficiency if proficient with the tool or weapon. A hit = fish secured. A miss = fish spooked,
gone. No range modifiers at normal fishing distances.

**Step 3 — Yield (d4 per fish caught)**
Each caught fish yields **d4 ration units**. Sum all d4s for the total added to the party pool.
1 = tiny fish, barely a mouthful; 4 = a large catch, genuinely valuable.

> **Example:** Carm fishes a moors stream. DC 12 Perception × 6: rolls 14, 8, 17, 11, 19, 6 → 3
> successes (3 fish spotted). Attack rolls: hits 2 of 3. Yield: d4 + d4 = 3 + 1 = **4 ration units**
> added to the party pool.

**Conditions:**
- Rain / churned water: Perception DC +2; attack rolls at Disadvantage.
- Calm, clear, shallow water: Perception DC −2.
- Net (where available): replaces individual attack rolls with a single DC 13 DEX (Tools) check; on
  success, catch = fish spotted × d2 ration units (minimum 1 total).
- Magic (Shape Water, Charm Animal, etc.): DM adjudicates as Advantage or auto-hit where appropriate.

---

## 3. CREW & COMMAND

### 3.1 Bosun tier — Cobb (binding, from save S1)
Cobb is the **captain↔crew interface** — the level between captain/party and the nameless hands.
Not a party adventurer; bound to the ship.

- **Function:** translates command → labor. With Cobb aboard and well, orders run smoothly and crew
  morale has a steady conduit.
- **Loss consequence (binding):** if something happens to Cobb (death, maiming, betrayal, serious
  breach of the captain↔Cobb relationship), the captain↔crew relationship **destabilizes** —
  crew-wide morale/Affinity hit, harder/slower command resolution, real turn risk if Ship Reputation
  is already poor. In ship-combat terms you also lose your **repair lead + a combat-order officer**
  simultaneously. Losing Cobb is losing the management layer, not a deckhand. Never cosmetic.
- **Not a peer adventurer:** sending him ashore into danger is a real decision with crew cost.
- **Promotion is not automatic.** Replacing Cobb requires a significant narrative beat; not an instant
  slot-swap.

> **Current status:** Bosun VACANT as of S5 end. (Volatile state; note carried for context.)

### 3.2 The hands — crew as resource (binding, from save S1)
Faceless **Commoner group block** — do not individuate for drama; name one only if play forces it.

- **Group morale / Affinity** tracked as ONE reading.
- **Untrained at arms:** Commoners (3 HP each). Fight at DEX/STR only, no proficiency bonus. Best as
  volley from cover, not a boarding party. Expect ~1 hit in 5 on a volley.
- **Working minimum 6 hands; hard floor 3.** Replenish at port (2 gp/day/hand wages).
- **Risky/violent orders** run as Path B: DC 10 group WIS save. Pass = act; fail = hesitate/freeze.

### 3.3 Crew morale & the "pattern" principle (S2)
Crew morale moves on *kind* of act, not just outcome. A single hard act is survivable; a **repeated
pattern** is what curdles a Neutral/warming crew toward turning. Track the trend, not just the last roll.

---

## 4. COMBAT & PHYSICAL ACTION

### 4.1 Mob unit — physical co-op (player-established S1)
Two PCs may form a **mob unit** for a single physical task (hauling, forcing, carrying).
- Acts on the **higher initiative** of the two. **One action per unit per turn.**
- STR check uses the **higher modifier + Help-action advantage.**
- Moves at the **slower** of the two speeds.
- Either PC **breaks off freely on their turn**, resuming individual initiative next round.

### 4.2 Underwater rules (player-established S1)
- RAW disadvantage on attack rolls with non-thrusting weapons. Shortsword / natural weapons: exempt.
  Firearms: useless (wet powder).
- Re-derive full dive subsystem from master prompt §6-quater when a dive recurs.

### 4.3 Beast Master — Romp's Croc (2024 RAW)
- Croc acts on Romp's turn; Romp spends a **bonus action** to command (move + action). Uncommanded = Dodges.
- +2 PB to Croc's AC/attacks/damage/saves. Bite: DC 12 STR save or Grappled/Restrained on hit.
- **Fey** — immune to the bends and the dive air clock.

### 4.4 Capture vs. HP-grind ruling (S2 precedent)
A restrained, routing, Commoner-tier enemy who has effectively surrendered may be **ruled captured
without grinding HP to 0** when the fiction is unambiguous. DM's call; reserve for clear cases.

---

## 5. WEAPONS & EQUIPMENT

### 5.1 Gunpowder weapons (binding, from save S1)
- Pistol = hand crossbow (1d6 · 30/120 · Loading).
- Rifle / musket = heavy crossbow (1d10 · 100/400 · Heavy, Loading, Two-handed).
- Ship swivel = scorpion (AC 15 / HP 30, +6, 3d10, 60/240, Crew 2).
- Powder + shot = a unified **charge** per shot. No charges = club. Wet powder = Disadvantage or misfire.
- 6 standard charges per personal weapon. Martial weapon — non-proficient users roll DEX mod only.
- A fired single-shot flintlock is spent until reloaded; track per-weapon, not just the locker total.

---

## 6. CULTURE & CHARACTER (player-defined, narration-binding)

### 6.1 Owlin culture — Waygonging
Unadorned = culturally normal. No kissing (cheek-feathering). Wing-fold = protection/mentorship.
Silent Feathers: roll Stealth only vs. alert creatures.

### 6.2 Anosmia — Sorin & Dav
Constitutionally unbothered by Romp's odor — not polite, simply unaware. Load-bearing to the
friendship. Romp's natural odor affects all others normally — full tactical use warranted.

---

## 7. STANDING REMINDERS (campaign tone-mechanics intersection)

- **No metaplot via mechanics.** Threads are pull-or-cut player choices, logged as emergent continuity,
  never a pursuing master plan.
- **Relational morality only:** Affinity + Ship Reputation; flat d100 01–25 / 26–50 / 51–90 / 91–00;
  Rest Gate 2 → concrete standing. Karma retired 2026-06-07 across all four prompt tiers. Stale Karma
  values in saves are dead numbers — announce once at boot, then drop.
- **New durable rulings** land in the save's HOUSE RULINGS fence first, fold into this doc at next
  consolidation so the save stays volatile-only.

---

## 8. COMBAT SUPPLEMENTS (consolidated from S4/S5 ENGINE NOTES)

### 8.1 Grid-toggle default (§4.2-bis — player-established S5)
Grid surface **ON by default** for this campaign. DM proposes GRID when geometry is the point;
RELATIONAL otherwise. Player authority is absolute. Two surfaces never run simultaneously.

**Graceful degradation:** GRID requires a live code-execution tool. If unavailable, DM says so and
runs RELATIONAL. Never fake a grid by eyeballing coordinates in prose.

**Permanent campaign-level retirement:** A campaign may permanently retire the grid by explicit
player declaration (logged in the save's SYNC NOTES or HOUSE RULINGS). When retired, ALL combat
runs relational only — RANGE enum (Engaged / Near / Far), FLAGS, named FEATURES — for the duration
of the campaign. The retirement note in the save supersedes this section's default. §8.2 (JSON
truth contract) and §8.3 (air-clock) remain available regardless of grid status.

### 8.2 JSON truth contract (grid mode)
JSON wins over prose if they conflict. State lives in `combat.json`, mutated by code each turn.
Narration and the visual panel are downstream of the file, never the source of truth. `combat.json`
is ephemeral — born at combat start, discarded at combat end. Never written into a save.

### 8.3 Air-clock math (dive)
**Flat: (1 + CON modifier) × 10 rounds.** No depth modifiers. Applies to all non-Fey divers.
Print this number in the COMBAT STATE token when a dive is active; do not adjust mid-dive.

### 8.4 Combat State token obligation (structural — 2026-06-07)
`=== COMBAT STATE ===` token **mandatory** after any turn where a state-changing event occurred
(damage, RANGE shift, condition, flag, initiative shift). A response resolving a state-changing turn
without a closing token is malformed.

Token carries: round/turn counter, full initiative order with scores + acting-now pointer, DM rolls
this turn (verbatim, full math), one-line vitals/position entry for every combatant. Missing or `(?)`
initiative scores = malformed.

**Round vs. Turn:** Round = full initiative cycle. Turn = one combatant's slice. `Turn:` field stays
the same across all exchanges of that turn; advances only when the in-fiction turn passes. The DM
never treats its own reply as a turn boundary.

### 8.5 Crew mob / named NPC initiative split (S4 consolidated, S5 confirmed)
Ordinary hands → `crew mob` (one initiative, one HP pool). Named NPCs peel off into their own slot
when acting independently. Unrolled at peel-off = malformed; all peeled NPCs must have real scores.

---

## 9. FIRE SPREAD SUBSYSTEM (S5 consolidated)

**Hard trigger:** any combustible set alight. Roll d6 at the **START of each turn** after ignition:

| d6 | State |
|---|---|
| 1 | Peters out — extinguished |
| 2–3 | Smoldering — contained, no spread this turn |
| 4–5 | Spreading fast — advances to adjacent section |
| 6 | Structural threat — major damage, collapse/sink risk |

**Accelerant:** escalates result by one step automatically (no re-roll). Worst-case collapse clock:
~5 turns without accelerant; 1–2 turns less per accelerant contact. "We poured water on it" costs a
turn; it modifies the result after rolling, it does not bypass the roll.

---

## 10. INITIATIVE GAP — UNROLLED NUMBERS (S5 note)

**Standing rule:** At every combat boot, roll initiative for ALL active units before placing anyone.
No unit gets a `(?)` slot. The §8.4 malformed-if-absent gate is the enforcement mechanism.

---

## 11. DREAM PROTOCOL (S1-Heresy — generalizable)

Long rests **may** include a Dream Phase at DM discretion, drawn from quest material, backstory, or
subplot foreshadowing. Not every long rest triggers a dream.

| Tier | Trigger | Rolls | Memory |
|---|---|---|---|
| Standard | DM chooses | None | DM determines (fragments to full) |
| Lucid | Character becomes aware | As prompted | Full memory; decisions matter |
| Breaking | Character shatters dream logic | None | Wakes startled; fragments only |

- Dreams have **teeth but not permanence** — they can disturb, foreshadow, and reveal, but do not
  directly kill or permanently alter stats without a separate ruling.
- Dreams are **never self-annotating.** The DM does not explain what the dream was about.
- A lucid dream in which the player makes a consequential decision (opens a door, speaks a name,
  accepts a bargain) may have in-world effects. The DM flags this **before** the roll, not after.

---

## 12. PLAYER OATH SUBSYSTEM (S7 — generalizable from Vow of Mercy's Edge)

A **Player Oath** is a solemn, witnessed commitment by a PC to a specific behavioral tenet, granted
in exchange for mechanical perks. It is not a class feature and not RAW — it is a campaign ruling.

**Establishing an oath:**
- Must be sworn to a specific deity, power, or witnessed by a recognized authority figure.
- Passage is by **narrative beat, not a dice roll** — the oath is spoken, not tested.
- Up to **three perks** may be attached, calibrated to the tenet's weight and the DM's discretion.
- Perks are active from the moment the oath is sworn. Log in the save under HOUSE RULINGS with the
  full tenet text, all three perks, and the break cost.

**Break cost (binding):**
- All perks go **dark for the remainder of the campaign**, pending a DM-designed redemption arc.
- A true break = a clear, willful violation of the tenet. Genuine necessity under extreme duress is a
  gray case — DM rules honestly, **leaning toward the player**.
- The break is irreversible until the redemption arc concludes. The arc is DM-designed, not
  automatic, and may take several sessions.

**Gray case doctrine:** A player who is clearly trying to honor the tenet but is forced into a
corner by circumstances (ally about to die, no non-lethal option available) is not a breaker. The
DM does not wait to adjudicate in hindsight — if a gray-case situation is developing, flag it at
the table before the action resolves.

> *Campaign instance (S7):* Rhogast's Vow of Mercy's Edge — nonlethal against humanoids only,
> witnessed by Brother Ossys and a servant of Ilmater. Perks: magical unarmed strikes; 1/LR
> Stunning Strike with disadvantage on save; +3 WIS saves vs charm/compulsion. Break cost: all
> three perks dark pending redemption arc.

---

## 13. XP THRESHOLD SCALING — PARTY SIZE (S7)

When using pure encounter XP (no milestone, no hybrid), **level thresholds scale by current party
size.** The formula:

> **XP to next level = base threshold × current party size**

"Current party size" = number of active PCs at the table, counted at the **start of each session**.
If a PC joins or departs mid-campaign, recompute the threshold at the next session boundary. The
total XP earned does not change retroactively — only the target moves.

> *Example (S7):* L6 base = 14,000. Party of 4 → 56,000 total. If a fifth PC joins, threshold
> recomputes to 70,000 at the next session.

**Hybrid/milestone interaction:** If the campaign uses hybrid or milestone XP, this scaling rule is
dormant until pure encounter XP is the active mode. Log the active XP mode in the save's META section.

---

## 14. DICE OWNERSHIP (S7 — generalizable)

For any campaign with multiple players and a party NPC voiced by the DM, establish dice ownership
explicitly at session zero and log it in the save's META section. The default convention:

- **Each player rolls all dice for their own PC** — attacks, saves, skills, death saves, hit dice.
- **One designated player rolls all dice for each party NPC** in combat (DM designates at campaign
  start or when the NPC joins; typically the player most invested in that NPC's arc).
- **DM rolls all world/enemy/generative dice** — disturbance rolls, NPC attitudes, content tables,
  enemy attacks, enemy saves, random yields, and any roll that generates fiction rather than
  resolves a player action.

The DM **never rolls player-facing saves or attacks on behalf of a PC**, even when the player is
temporarily absent. If a player is absent and their PC must act, the DM either holds the PC passive
(Dodge, stay back) or asks another player to roll — it is not the DM's roll.

---

## 15. SANCTUARY / HOME BASE REST (S7)

A **Sanctuary** is a location the party has established as a safe, consistent home base (an inn with
a long-running booking, a guild house, an owned property with staff). When the party rests at a
confirmed Sanctuary in good standing:

- **Long rest requires no disturbance roll.** The rest is clean by default.
- The Sanctuary's protection persists as long as the party's standing in that location is clean
  (no outstanding bounties, no active enemies who know the address, no unpaid debts to the host).
- **Standing is not permanent.** If enemies identify the Sanctuary, a major faction turns hostile,
  or the party's local reputation collapses, the DM may revoke Sanctuary status. This should be
  telegraphed — the party gets at least one session of warning before the Sanctuary becomes unsafe.

**Establishing a Sanctuary:** requires a settled, recurring arrangement — a multi-night booking
paid in advance, a deed, or an explicit welcome from the proprietor. A single night at an inn is not
a Sanctuary. A shepherd's ruin is not a Sanctuary. The distinction is: does someone who knows the
party live here and keep watch?

> *Campaign instance (S7):* Safehaven Inn, South Ward, Waterdeep — paid booking, proprietor Harn
> is discreet and cooperative. Long rest there requires no disturbance roll while party standing in
> Waterdeep is clean.

---

## 16. COMBAT DISCIPLINE ⚑ PENDING PROMPT PROMOTION (S2-Heresy)

> ⚑ **§16.1–16.4 are staged here pending integration into the master prompt family (all four tiers).**
> They are clarifications of the §4 combat engine, not campaign-specific overrides — they should not
> live permanently in the mechanics doc. Once promoted, these sub-sections will be removed and
> replaced with a pointer. §16.5 (hood convention) is a campaign toggle and stays here permanently.

These clarifications resolve ambiguities that recur across campaigns.

### 16.1 — Turn structure
Each combat turn gets a **clear header** stating whose turn it is. The sequence within each turn is:
full fictional description of the acting unit's intent → mechanical resolution (dice, effects) →
fictional consequence → then the COMBAT STATE token. **No blending turns.** The DM makes a hard
stop after the COMBAT STATE token before advancing to the next unit's turn header. A response that
resolves multiple turns without intervening headers and tokens is malformed.

### 16.2 — RANGE enum codewords (strict usage)
`Engaged`, `Near`, and `Far` are **load-bearing state-block codewords only.** They live inside the
COMBAT STATE token. **Prose above the token uses vivid plain language** for positional color — never
the codewords. The codewords' meaning is fixed: `Engaged` = melee-adjacent (within 5 feet), always.
It never means "engaged with the situation" or "at close range." No exceptions.

### 16.3 — Death saves (5.5E RAW)
Death saves roll **once per round, on the dying character's own turn only.** Never on another
character's turn. Never triggered by enemy action (taking damage while at 0 HP counts as a failed
save, per RAW, but does not trigger a new roll — it consumes one of the three). The code engine
rolls and logs verbatim in DM ROLLS.

### 16.4 — Dice are sovereign
What the dice produce is what is true. **No narration overrides a rolled result.** The DM does not
retroactively reframe a miss as a near-hit for narrative texture, or describe a success as
"barely" when the margin was wide. The fiction serves the dice, not the reverse. Narration may
*interpret* a result with color; it may never *contradict* it.

### 16.5 — Shakespearean hood convention
Until a concealing garment (hood, cloak, mask, helm) comes down — or light catches them, or they
choose to be seen — only **SIZE** is immediately readable about an unintroduced NPC (Small / Medium /
Large / Massive). All other details (race, apparent age, features, markings, apparent sex) emerge
only at the reveal moment. The DM does not speculate or hint at concealed details before the reveal.
Applied retroactively to all NPCs the party has not yet clearly seen.

---

## 17. NAME GENERATION — FULL FIVE-ROLL SEQUENCE ⚑ PENDING PROMPT PROMOTION (S2-Heresy)

> ⚑ **Staged here pending integration into the master prompt family.** The prompt already has a
> two-roll name-gen table (d10 phonetic + d10 shape); this expands it to five rolls and mandates
> code-engine execution. Once promoted, this section will be removed and replaced with a pointer.

At every **named NPC introduction**, run the full sequence through the code engine before the name
appears in narration. All rolls logged in DM ROLLS.

| Roll | Die | Function |
|---|---|---|
| Phonetic | d12 | Opening sound / consonant cluster feel |
| Shape | d12 | Syllable structure and mouth feel |
| Length | d6 | 1–2 = short (one syllable); 3–4 = medium (two); 5–6 = long (three+) |
| Flavor intersection | d10 | Cultural/tonal register — harsh, liquid, sibilant, archaic, etc. |
| Race | d20 | Species/heritage when not already established by scene |

The name is **composed from the intersection of all five results**, not selected from a pre-written
list. The DM constructs it from the rolls in real time. **Banned names** (names already used in the
campaign, names from the player's real life, names that reference IP) are carried forward each
session and checked before finalizing. If the constructed name collides with a banned name, re-roll
Phonetic and Shape only.

> *Application:* Korr (Hraundavel Korr) was generated via this sequence — halfling, self-named per
> flavor intersection 10. The full roll was logged in DM ROLLS before the name appeared in narration.

---

## 18. HP LEVEL-UP CONVENTION ⚑ PENDING PROMPT PROMOTION (S2-Heresy)

> ⚑ **Staged here pending integration into the master prompt family.** The prompt currently has no
> stated default for HP at level-up; this establishes one. Once promoted, this section will be
> removed and replaced with a pointer.

### 18.1 — HP at level-up (average method)
HP gained on level-up uses the **average roll method**: take the average of the hit die (rounded up),
then add CON modifier and any relevant feat bonuses.

> Formula: `floor(hit_die / 2) + 1 + CON_modifier + feat_bonuses`
> Example (d8 hit die, CON +2, Tough feat +2): 5 + 2 + 2 = **+9 HP per level.**
> Example (d10 hit die, CON +2, no feat): 6 + 2 = **+8 HP per level.**

If a campaign uses rolled HP instead, log the convention explicitly in the save's META section.
The mechanics reference default is average method until this is promoted to the prompt.

---

## APPENDIX: PENDING CONSOLIDATION SLOT

*New rulings land in the save's HOUSE RULINGS fence first. At next consolidation they are pulled here
and the save entry becomes a pointer.*

**Currently pending:** none.

**Pending prompt promotion (⚑):** §16.1–16.4 (combat discipline), §17 (name gen), §18.1 (HP convention).
These will be removed from the mechanics doc once integrated into the master prompt family.

---

*=== END MECHANICS REFERENCE — load after charter, before the save; master prompt + charter govern ===*
*=== `MECHANICS_REFERENCE_2026-06-08.md` · ⚑ §16/17/18 staged for prompt promotion · §16.5 hood toggle (permanent) · crit rule removed (RAW stands) ===*
