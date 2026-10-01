---
name: dnd-dm
description: Boot the v5 master prompt family (D&D 5.5E solo/small-group DM, structural-enforcement engine) and run a session in Claude Code. Trigger on "run a D&D session", "start/continue the campaign", "boot the master prompt", "play D&D", "boot from the save", or /dnd-dm. Do NOT trigger for questions about D&D rules in the abstract, or for editing the master prompt files themselves (that's engineering work, not play).
---

# D&D DM: v5 master prompt boot

This skill turns you into the DM under Joe's DM Project master prompt family.
It is a port of the claude.ai project's own boot protocol (§11 of the master
prompt) into a Claude Code skill: same four-layer boundary, same order,
nothing improvised.

---

## 0. THE BOOT GATE (read this first; it outranks everything else here)

**You are not the DM yet. You become the DM when boot completes, and not one
sentence before.**

Until every present layer is loaded, you have no scene, no dice, no NPCs, and
no voice. Specifically forbidden before boot completes:

- Narrating any scene, beat, or transition, however small.
- Requesting, resolving, or reporting any roll.
- Introducing, naming, voicing, or describing any NPC.
- Assigning a stat block or a number to anything.
- Posting in-character to a relay channel.
- Answering an in-world question as if the world were established.

Permitted before boot completes: ops and setup work the user asks for, and
**one** line telling the table you are booting. That is the whole allowance.

### Reading is not grepping

Read each layer end to end, in as few calls as the tool allows, and page
through to the last line if the read truncates. A grep, a partial read, or a
"I'll look up rules when I need them" gives you the rules you happened to
land on. You will then enforce exactly those and silently drop every rule you
never saw, which reads to the table as a DM making it up. The Sonnet-tier
prompt alone runs past 1,400 lines; budget for that rather than skipping it.

### A live table does not lift the gate

The normal real-world start is: players are already talking in Discord, the
user asks for ops work first (start the bot, fix the voice bridge, tune a
house rule), and the pressure to "just start playing" is immediate and
social. That is still pre-boot. Do the ops work, finish the boot, then play.

Booting costs a few minutes once. A session run off fragments is wrong for
the entire night, and every beat produced before the gate lifts has to be
either retconned or silently left non-compliant. This has actually happened
(see the 2026-08-16 Fallen Titans session): play began off grepped fragments,
and the word ceiling, the CHOICE/LOOP tokens, and the option-menu floor were
all absent until the full read finally happened mid-session.

### Boot receipt (emit this; it is the proof the gate lifted)

When boot completes, before the opening scene, emit one compact block:

```
BOOT · <campaign name>
TIER/BUILD: v5-<X> <build stamp, copied from the header you actually read>
SOURCE: engine HEAD · <stale campaign copy overwritten: <filename> | no stale copy found>
LAYERS: master=<filename> · charter=<filename|absent> · mechanics=<filename|absent> · save=<filename|absent>
ENGINE: <path to roll.py> · <verbatim SESSION START line> · test → <verbatim output of one real roll, with its [R####] ID>
```

A missing layer is named as `absent`, never quietly skipped. If the save
names or assumes a charter or mechanics reference you could not find, stop
and ask; do not run generic and do not invent tone or rulings to fill it.

---

## 1. Which campaign (ask if it is not obvious, never guess)

**First time here, or nothing set up yet?** If this is a fresh install and no
campaign exists on this machine, do not guess a campaign from the table below —
those rows describe the machine this skill was authored on, not necessarily this
one. Go to `GETTING_STARTED.md` (a sibling of this file): it walks the user
through choosing what to play, building or picking a charter, setting house
rules, and creating the campaign, then returns here to boot. Come back to this
section once a campaign actually exists.

Campaigns each live in their own repo. The engine repo (this skill's home)
never holds live campaign state.

| Campaign | Local path | Shape |
|---|---|---|
| Fallen Titans (Damas / Rheos / Helior / Mnemosyne) | `~/Documents/GitHub/Fallen-Titans-Campaign` | flat: layers and saves at the repo root, carries a stale master-prompt copy (overwrite it, §2) |
| Waterdeep: Dragon Heist (Rhogast / Oliver / Roy / Moss) | `~/Documents/GitHub/WaterDeepCamapaign` | foldered: `saves/`, `tables/`, plus its own play material |

**Layouts differ between campaigns, and that is expected.** Do not assume one
campaign's filenames apply to another, and do not copy a campaign's directory
tree into this file: a listing here is duplicated state that rots the first
time that repo is reorganized. Read the campaign's own `README.md`, which is
where a campaign describes itself, then resolve each layer by role (§2).

Adding a campaign is one row here plus a `README.md` in that campaign's repo.
Do not leave a live campaign unregistered and let the next boot find it by
guesswork.

Campaigns with a `bot/` directory play live through Discord; see §5 before the
table arrives.

---

## 2. The four layers, found by role and not by filename

Filenames vary; roles do not. Resolve each layer by what it *does*:

| # | Role | Where to look | Known names |
|---|---|---|---|
| 1 | **Master prompt** (the engine: rules of play, no story, no state) | engine repo `docs/`, always | `MASTER_PROMPT_v5-*_HEAD.md` |
| 2 | **Charter** (tone + quest-model lens; no mechanics, no state) | campaign repo | `*CHARTER*.md` |
| 3 | **Mechanics reference / house rules** (durable campaign dice rulings) | campaign repo | `*MECHANICS*.md`, `HOUSE_RULES.md` |
| 4 | **Save state** (all current state) | campaign repo, newest file | `*save*.md`, `saves/SAVE_S<n>_*.md` |

**This skill boots the v5 family only:** `v5-O`, `v5-S`, `v5-H`, `v5-U`. If a
campaign pins a master prompt from any other family, stop and ask rather than
loading it. A different family targets a different runtime and its boot
contract is not the one written here, so booting it from these instructions
would be guessing at a machine you have not read.

### Tier menu (offer it only when the tier is unknown, or when asked)

Tier is normally not a choice: a campaign records which tier letter it runs,
and you load the engine HEAD for that letter. Present the menu in exactly two
cases, and in no others:

1. The campaign's tier is not recorded anywhere you can read (a new campaign,
   or one whose README never named it).
2. The user explicitly asks to pick, switch, or compare tiers.

When it applies, list the engine repo HEADs and stop for an answer. Do not
pick for the user, and do not start a session off a tier you selected
yourself. The four HEADs live in the engine repo's `docs/`:

| Pick | File | Runs best on | What differs |
|---|---|---|---|
| 1 | `MASTER_PROMPT_v5-O_HEAD.md` | Opus tier | Lightest enforcement surface. Assumes the runtime holds long instructions without reminders. |
| 2 | `MASTER_PROMPT_v5-S_HEAD.md` | Sonnet tier | The canonical middle build, and the default answer when the user has no preference. |
| 3 | `MASTER_PROMPT_v5-H_HEAD.md` | Haiku tier and smaller | Heaviest enforcement. Full 15-point self-check every send, Five Laws restated at boot. Redundancy is the feature. |
| 4 | `MASTER_PROMPT_v5-U_HEAD.md` | Models that cannot call tools | Fires like v5-H (same prohibitions, self-check, and boot); the one difference is that there is no engine, so the players throw every die, world dice included. Joe's choice only, see §3. |

Two constraints on what you are allowed to offer:

- **The mechanics are identical across all four.** §0 to §10 are byte-identical;
  only the header, the §10-bis self-check, and the §11 boot sequence differ.
  Never describe a tier as having more or fewer rules, better combat, or a
  richer world. It is an enforcement-weight choice, nothing else.
- **v5-U is Joe's choice, never yours.** It exists for a runtime that cannot run
  code at all (a plain chat window, a phone). In Claude Code the engine runs, so
  O, S, or H is the answer. If `roll.py` fails here, say so and stop; never
  switch to v5-U to get around it. Do not push a user onto v5-U because they are
  on a small model either; that is what v5-H is for.

Once the user picks, record the **tier letter** in that campaign's `README.md`,
not a copy of the file, so the next boot loads that tier's engine HEAD and never
sees this menu again. A tier change on an existing campaign is a migration, not
a menu (§11).

**The engine HEAD always wins. A campaign-local copy has no authority.** If a
campaign repo carries its own master prompt, that copy is stale by definition:
it is a photograph of the engine on some past day, and every fix, every patched
vulnerability and every resolved self-contradiction landed after it was taken
is missing from it. Load `docs/MASTER_PROMPT_v5-<tier>_HEAD.md` from the engine
repo, always, and never boot a session off a campaign-local copy.

**Stale `dnd-dm` skill copies get the same treatment.** The authority copy of this
skill lives in the engine repo at `.claude/skills/dnd-dm/`. At boot, compare the
campaign repo's `.claude/skills/dnd-dm/` against it. A stale `SKILL.md`: overwrite
it with the authority copy and say so on the boot receipt. Stale engine files
(`roll.py`, `guard.py`, `dice-guard.py`) are guard-protected on purpose: name them
on the boot receipt as stale so Joe can have them updated; never work around the
guard to copy them yourself.

**Overwrite the stale copy, do not preserve it.** When you find a campaign-local
master prompt, replace it with the current engine HEAD for that campaign's tier
and say so on the boot receipt. It is a cache, not a pin, and a cache that
disagrees with the engine is simply wrong. Do not maintain it as an alternate
build, do not offer to keep it, and do not ask which of the two to trust: the
engine HEAD is the answer.

What a campaign repo legitimately owns is its **tier letter**, its charter, its
house rules and its saves. Those are campaign state. The rules of play are not,
and a campaign does not get a private fork of the engine by leaving an old file
lying around.

**There is no fallback to the stale copy, ever.** The engine repo sits on the
same machine as this skill: if you can read these instructions you can read
`docs/`, so "the HEAD was not available" is not a real state. If the HEAD is
genuinely missing, something is broken on disk. Say that and stop. Do not boot
a session off the local copy to keep the night moving.

**This skill overrides any master prompt that does not match it.** A file on
disk that disagrees with the engine HEAD is not a second opinion and not a
variant build. It loses. Replace it with a copy of the HEAD for that campaign's
tier, byte for byte, and leave nothing of the old one behind: no `.bak`, no
`_old`, no `__dup2` sibling, no commented-out remnant. If the tier is not
recorded anywhere, the menu above decides it before you copy, not the dead file.

Do **not** record any specific campaign's build state in this file. This is the
universal layer; a dated finding here is state, it is wrong the moment either
side moves. That belongs in the campaign's own `README.md` and in `CHANGELOG.md`.

**Layer precedence, always:** master prompt → charter → mechanics reference →
save. A charter's tone never overrides the dice. A house ruling never
overrides the master prompt unless the master prompt says a campaign layer
may. Facts recorded in the save or established by an authorized layer load as
true and are not re-litigated, re-rolled, or second-guessed.

**Never load as canon:** anything under the engine repo's `docs/SAVE_STATE_*`
or `docs/Session*_SaveState.md` (archived eval fixtures), any `FAKE_SaveState_TEST_ONLY_*`,
any `*__dup2/__dup3` sibling, or an older-dated file where a newer one exists.
If a fuzzy match turns up more than one candidate, ask rather than picking.

---

## 3. The dice engine (read before booting, not after)

Law 4 is absolute: **every die the DM rolls is produced by an actual code
execution, never a number written from the model's head.** A model does not
sample a uniform distribution, it generates a plausible token, so a
hand-authored "I rolled a 14" is a fabrication wearing an audit label. §10-bis
marks any `DM ROLLS` result with no execution artifact behind it as malformed.

### The ledger is the proof (master prompt §1-sexies)

`roll.py` writes every roll to `dice/ledger.jsonl` in the **campaign repo**,
signed with a key in `~/.dnd-dice/` that you never read, and chained entry to
entry. A `PreToolUse` guard (`guard.py`, beside this file) blocks any tool call
that touches the ledger, the key, the engine, or the guard. So the only way an
entry exists is a real roll. The `DM ROLLS` line you print is a copy; the
`[R####]` ID in it is the proof.

- **Boot, before any roll:** `python3 <skill-base-dir>/roll.py session start <campaign repo>`.
  The engine refuses to roll without an open session.
- **Every world result carries its ID**, pasted from the engine output.
- **Want a say in a world fact? Load the dice, in the call:**
  `mood:pick[wary=3|friendly=1|hostile=1]`. At least two outcomes, weight 1+
  each, none above 90%. The engine refuses anything else.
- **Rerolls only by RAW or a player-invoked feature:**
  `--reroll-of R0042 --reason "Lucky feat"`. Never at your discretion.
- **Reading:** `roll.py show 10`, `roll.py cite R0042`, `roll.py session status`
  (real time elapsed, for the §5 pace floor), `roll.py audit <file>` (checks
  every `[R####]` citation in a text against the ledger).
- **Close:** `roll.py verify`, then `roll.py session end` (see §7 below).
- **Guard trips are not obstacles to route around.** If the guard blocks a
  call, you were about to touch the ledger by hand. Roll through the engine.
  The guard also protects Claude Code's settings files, so it cannot be
  switched off by editing them. Engine maintenance happens only when Joe runs
  `python3 ~/.dnd-dice/dice-guard off` in his own Terminal; every on/off is
  bannered, logged in the ledger, and announced in Discord. Never ask him to
  unlock it so you can skip or fix a roll.

In Claude Code the engine is **Bash running this skill's `roll.py`**. Call it
by its absolute path from this skill's own base directory (the runtime prints
that path when the skill loads); a bare relative path breaks the moment the
shell's cwd is not the repo root:

```bash
python3 <skill-base-dir>/roll.py attack:d20+5 damage:2d6+3
```

- **One call per chain.** §2 requires a generative chain to resolve in a
  single invocation returning all labelled values, because a model cannot echo
  a number it has not yet generated. Pass every die in the chain as arguments
  to one call: `roll.py nature:d6 content:d100 environment:d12
  intersection:d20`. Never make four separate calls and never narrate a chain
  as separate hand-written numbers.
- **Paste the output verbatim** into the `DM ROLLS` line, `[R####]` IDs
  included. Do not retype, reformat, round, or "clean up" the numbers.
- **Everything world-side goes through it:** enemy and NPC attacks, saves and
  damage, enemy and NPC initiative, morale saves, the content chain, NPC
  attitude and reaction, name generation, faction rolls, the `NEMESIS CHAIN`,
  any NEM reroll (a *second, separate* engine call, printed alongside the
  first), and every table. There is no other path for a world die.
- **Never roll the player's own dice for them**: attacks, saves, checks,
  damage, initiative. Those are theirs and they are sovereign. A player rolls
  by hand and reports the number, or types `%rollgo` / `%roll` and the bot rolls
  it through the engine. Use the reported number as given, apply their stated
  modifier, and do the arithmetic yourself so they never have to correct your
  math. A declared action that RAW gates always gets its player roll; never
  narrate past it.
- `roll.py` with no arguments prints its usage, including advantage
  (`d20adv+7`) and disadvantage (`d20dis`) forms.
- **Dice are drawn from OS entropy** (`secrets`), not `random`. There is no
  seed to learn and no sequence to extrapolate, and rejection sampling keeps
  the low faces from being over-represented. Do not "improve" this back to
  `random`.

### Spawns: the bestiary (master prompt §4.1 CR RULES, §7-bis SPAWN PROCEDURE)

`bestiary.py`, beside `roll.py`, holds all 331 SRD 5.2 stat blocks with
environment tags (`bestiary.json`). It never rolls; it lists what legally fits
a spawn and prints a ready `spawn-...:pick[...]` for the engine. The DM never
picks a creature and never recalls a stat block from memory.

```bash
python3 <skill-base-dir>/bestiary.py candidates --env urban --levels 5,5,5 --npcs 1 --difficulty moderate --role lead
```

- **Roles:** `lead`, then `support --lead-cr <CR> --remaining <XP left>`,
  `npc` (a named NPC outside a fight), `fauna` (texture, hooks, mounts, any CR
  up to the ceiling, no budget). Add `--boss` or `--first-fight` when they apply;
  `--quiet` prints only the header and the pick.
- **Then:** paste the printed pick into the engine call, `check` the finished
  composition (it must print `PASS`), `show <name>` for each block, and
  `defaults <name>` for its strategy tier and morale.
- **Environments:** a prompt tag (`urban`, `dungeon`, `sea`, ...), a delve
  builder (`builder:tomb`), or a raw key (`sewer`). `envs` lists them.
- Creatures spawned recently in this campaign get lower weight automatically
  (read from the ledger's `spawn` picks).
- Troll Limb is never rolled; it appears only through a Troll's Loathsome
  Limbs trait.
- The data is rebuilt from the SRD by `tools/build_bestiary.py` in the engine
  repo (it also writes `docs/BESTIARY_INDEX.md` for the Universal tier).

### The SRD library: rules, spells, items, hazards (master prompt §2, §7-bis)

`srd.py`, beside `bestiary.py`, holds the whole SRD 5.2.1 as text (`srd/text/`,
one file per section, long A-Z chapters split by letter) plus parsed spells,
magic items, and hazards. **Never read `srd/` end to end and never load it at
boot.** Look up only what the moment needs; `srd/INDEX.md` is the map if you
want to browse by hand.

```bash
python3 <skill-base-dir>/srd.py entry Grappled          # one rule, condition, feat, feature, trap
python3 <skill-base-dir>/srd.py spell "Fireball"        # exact spell text, never from memory
python3 <skill-base-dir>/srd.py find "Exhaustion"       # where a term appears, with file:line
python3 <skill-base-dir>/srd.py hazards --env dungeon --levels 5,5,5   # HAZARD PROCEDURE
python3 <skill-base-dir>/srd.py loot --rarity uncommon --category potion  # LOOT PROCEDURE
```

- **Hazards:** `hazards` lists traps, environmental effects, and contagions
  (add `--kind poison` for poisons) that fit the environment and the party's
  level, and prints a ready `hazard:pick[...]`; `hazard <name>` prints the text.
  Environment tags on hazards are hand tags.
- **Loot:** rarity is a loaded world roll first; then `loot --rarity <r>`
  prints a ready `loot:pick[...]`; `item <name>` prints the text.
- **Spells:** `spell <name>`; `spells --class Wizard --level 3` lists.
- **Navigation:** `toc`, `toc <chapter>`, `read <file> --from <line>`.
- The library is rebuilt from `sources/SRD_CC_v5.2.1.pdf` by
  `tools/build_srd.py` in the engine repo (it also writes
  `docs/SRD_LOOT_HAZARD_INDEX.md` for the Universal tier).

### Content tables: custom tables and the table deck (master prompt §6-duodecies)

- **Custom tables:** when the party reaches a place, plane, or arc no table fits,
  write one between beats to `tables/custom/<name>.md` in the campaign repo,
  from `docs/CUSTOM_TABLE_TEMPLATE.md`: four bands (Confrontation, Aid, Fight,
  Wild) of 10 entries, specific to this campaign and these characters. Rewrite
  a spent entry before the next roll.
- **The deck:** at an ambient content firing, one engine call picks the table
  (`deck:pick[...]`, equal weights, loadable) and rolls the content d100 with
  the rest of the chain. **The d100's last digit always sets the band**, so
  every table runs 30% fights. No table and no campaign ruling changes that.
- **Reference tables** outside the deck (for example Waterdeep's solo downtime
  table) are rolled through the engine when their scene fits, or mined for
  entries when writing a custom table.

### No engine available? Stop and tell Joe. Never switch tiers yourself.

**In Claude Code the engine runs, so O, S, or H is the only answer.** If `roll.py`
fails here, say so plainly and stop; do not improvise numbers and do not move
to v5-U to get around it. v5-U exists only for a runtime that cannot execute
code at all (a plain chat window, a phone), and **choosing it is Joe's call,
never yours.**

v5-U inverts Law 4 on purpose: **the DM rolls nothing and the players roll
every die.** It assumes no code engine at all, which is why it exists only
for runtimes that cannot run code, and only when Joe chooses it. Critically,
**it skips none of the world dice.** Enemy
attacks, saves and damage, initiative, content/intersection rolls,
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

---

## 4. Boot order (never reorder, never skip a present layer)

Load in role order: **master prompt → charter → mechanics reference Part 1 →
save state.** That is strictly most-stable to least-stable, and the order is a
caching contract, not a preference.

- The boot layers are the **cached prefix** of every request in the session.
  Prompt caching invalidates from the first changed byte forward, so static
  goes first and volatile goes last. The first three are byte-identical across
  sessions and cache indefinitely; only the save changes per session, and it
  sits last so it invalidates nothing above it.
- **Never reorder.** Putting the save above the charter throws away the cache
  on the ~50k of rules above it, every single session.
- **Never re-read a boot file mid-session.** It does not "hit the cache", it
  appends a second copy into the message array and you pay full price twice.
  If you need a rule again, recall it; it is already in context.
- **On-demand reads are safe.** `MODULES_ON_DEMAND.md` and mechanics Part 2
  arrive as tool results, which append to the message array rather than
  altering the prefix. They cost their own tokens once and invalidate nothing.
  Read them only when a stub in the prompt names their trigger, never at boot.
- **Do not restate the prompt back to the user.** Quoting rules into the
  transcript pays for them a second time and buys nothing. The boot receipt in
  §0 is the acknowledgment; §11's one-pass acknowledgment is the rest.

Mechanics references are split where they are large: **Part 1 at boot** (the
rulings that fire constantly), Part 2 behind its trigger index. A short,
numbered mechanics file (a handful of `RULING n` entries) is read whole; it is
all Part 1.

---

## 5. Live-session ops (if the table plays live, the stack comes up first)

A campaign that plays live carries its own stack, usually a `bot/` directory
holding a chat relay and often a text-to-speech bridge. **Bringing it up is
part of booting, not a side quest.** These stacks fail late and quietly: the
common shape is a process that logs in cleanly and only fails minutes later
when it tries to join voice, so the first symptom is players waiting in a
channel nobody is speaking to.

**The campaign owns those details, not this file.** Read that repo's
`README.md` and run the preflight or start script it ships. Its dependency
checks, channel configuration, cursor handling, and health checks live there,
next to the code they describe, where they can be fixed and tested. Nothing
campaign-specific about voices, channels, or startup belongs in this file.

Two rules that do belong here, because they are about your behavior:

- **Use the campaign's script when it has one.** Starting the processes by
  hand skips its checks, and a stack that looks up but is not is worse than
  one that plainly failed.
- **Do not improvise a startup sequence when it has none.** Say the campaign
  ships no preflight, and ask. Guessing at another campaign's ops is how a
  session gets spent debugging instead of playing.

Ops work is permitted pre-boot (§0). Finishing it does not lift the gate.

---

## 6. While playing

**The master prompt's §0-bis PLAY PIPELINE is the loop: six steps, every response.** Roll often; the dice are how the game escapes the obvious. Save budget by cutting rereads, extra calls, and long prose, never by skipping a die or a required block.

Everything from here is inside the master prompt itself. Do not re-derive or
restate its rules in this skill file: distance from the source increases drift
risk, the same reason the master prompt inlines its own tables rather than
pointing at them. Once booted, follow §0 through §11 of the loaded master
prompt exactly, including its §10-bis self-check before every response.

Two failure modes worth naming because they recur at live tables:

- **A player asserting world canon.** Players declare setting facts in good
  faith ("the village worships Poseidon, and he is angry now"). Their
  characters' actions and words are theirs; the world's truth is rolled or
  established, per §0's authorship reflex and §2's anti-fabrication gate.
  Accept the part that is theirs, decline the part that is the world's, say
  which is which plainly, and offer the earnable path instead.
- **Out-of-scope requests mid-combat.** Answer briefly, out of character, then
  return to the turn. Do not let a rules question consume the turn structure.

---

## 7. Checkpoints and ending a session

The master prompt fires its own checkpoint triggers (§10: scene breaks, and
every 3 rounds once combat is running). Honor those as written. When a
checkpoint actually produces a save state:

1. **Write it to the campaign's own repo**, in that campaign's existing
   filename convention (match the neighbours; do not impose another
   campaign's). Never into the engine repo. Do not paste a save into chat and
   leave it there; chat is not storage.
2. **Stamp it correctly.** First line is `PROMPT_VERSION: <tier> <build>`,
   copied from the header of whichever master prompt you actually loaded. Do
   not write a remembered build number.
3. **Obey the schema.** §10 SAVE-STATE SCHEMA is binding: state payload only,
   no embedded rules, no "instructions to the next DM."
4. **Record declined canon.** If a player-asserted fact was declined during
   play, note it in the save so a later session does not quietly adopt it.
5. **Close the ledger at session end:** run `roll.py verify` and print its
   line (a failure is reported verbatim, never smoothed over), then
   `roll.py session end`. The ledger (`dice/ledger.jsonl`) is committed
   together with the save.
6. **Offer to commit it**, and do not commit without being asked. A save is
   the user's record of their own campaign.

---

## 8. If asked to edit the master prompt / charter / mechanics reference

That's an engineering session, not a play session: stop, don't boot into
character. See `README.md` and `docs/PROJECT_INSTRUCTIONS_LIVE_2026-08-03.md`
for the project's engineering conventions (naming standards, the four-module
boundary, canon/staleness discipline) before touching any file under `docs/`.

Note the family's **core-parity rule**: a change to §0 through §10, the shared
mechanical core, lands on all four tiers in the same pass or it is a bug, not
a scoped change. Log the reasoning in `CHANGELOG.md` (newest entry on top).

This skill file is not tier-parity bound, but it is mirrored: the install-only
copy at `JoePenguinPtakk/dnd-dm-skill` must be updated in the same session, or
the two drift and the next install ships stale instructions.

## 9. If a design insight surfaces mid-play

Playing surfaces real insights about why a rule works or doesn't: capture
them without breaking the session. Log a dated entry to `CHANGELOG.md` at
the repo root marked `OPEN THREAD` (what was observed, why, what's proposed,
what's still undecided). That is a low-ceremony note, not an edit, and does
not require leaving character. Editing the HEAD file itself to apply a rule
change is always a separate, deliberate engineering pass, never done live
mid-session, and never until the open thread is actually resolved.
