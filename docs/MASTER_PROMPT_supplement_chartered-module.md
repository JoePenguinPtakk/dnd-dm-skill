# SUPPLEMENT — §6-septies · CHARTERED-MODULE CONTENT BRIDGE

*Drop-in addition to the v5 master prompts. Campaign-agnostic. Active only when the
campaign is chartered on a published module that ships the four generated artifacts
(manifest, spine, coverage ledger, hooks) from the module-to-charter generator. When those
are absent, this supplement is inert and the §5/§6 content engine runs exactly as written.*

---

## 0. WHAT THIS IS, AND WHAT IT DOES NOT CHANGE

The §5/§6 content engine already decides **when** content fires (automatic per-phase cadence,
§5 — no gate roll, guaranteed) and **what kind** of beat it is (interleaved d100 → band →
environment cast → intersection). This supplement changes **one thing**: where the
**quest-linked** result draws its content from.

Without a chartered module, a quest-linked firing routes into "an active quest's Stage
beat" (§5) that the DM frames. That works, but it surfaces nothing from a published module's
unplayed content on its own; a hand-built campaign table can only hold what has already been
played. This bridge makes a quest-linked firing roll onto the module's **live** content,
in story order, so playing the ordinary phase cadence introduces the module itself.

Everything else is untouched. The content cadence, the ambient branch, the interleaved-d100
bands, Law 3 dice ownership, the intersection tables, the loop gates: all as written.

---

## 1. THE HORIZON (what "live" means)

Four artifacts sit in the campaign layer, loaded at boot alongside the charter:

- **manifest** — every keyed area and named NPC of the module, each with a scope tag; what
  exists.
- **spine** — the module's main quest as ordered, gated stages; exactly one is live at a time.
- **coverage ledger** — per in-scope area, a status: untouched / glimpsed / rendered /
  resolved / skipped; what the party has experienced.
- **hooks** — natural entry paths per area, plus each stage's spine_hooks; how content enters.

The **horizon** is the live stage's `live_content` intersected with the in-scope, not-yet-
rendered manifest. It is the only content this bridge will surface. Content outside the live
stage stays dormant until its gate opens, so the party is never handed a beat the story has
not reached.

---

## 2. THE BRIDGE (three fire points)

**A. Quest-linked content firing (§5).** When a content firing occurs and the nature roll (d6)
reads **quest-linked**, roll the **live content table** for the current stage instead of
free-framing a beat. The table is regenerated per stage from the horizon (`content_table.py`),
banded to match the engine's intent:

- **advance the arc** — a stage spine_hook; the story-moving result.
- **flesh out the beat** — an untouched in-scope area's content hook.
- **someone surfaces** — a live stage NPC the party has not met.
- **wild card** — defer to the generic §6 wildcard intersection.

The **ambient** branch is unchanged: it runs the generic §6 content roll for world texture, no
module obligation. For a **city** setting, its source is the campaign-agnostic Urban Beats
supplement (§6-octies, if loaded — otherwise §6-nonies's generic Urban table); a campaign may
also carry its **own** city cast table in its module material (names, factions, threads), which
supersedes the generic one for that campaign only — the same more-specific-beats-generic
principle §6-nonies's charter-overlay precedence rule already runs for any environment tag, not
a special case, just applied here to a module-supplied table instead of a charter-supplied one.
So a day still yields the three-way mix (arc beats, ambient color, quiet-leaning bands): the arc
beats drawn from real module content, the ambient color from Urban Beats or the campaign-specific
table. **Three table tiers, kept separate:** the generic live-tables module and the generic
§6-octies Urban Beats table are campaign-agnostic (public engine); a campaign's own
city cast table and its quest-linked live content table are campaign-specific (private module
material, or charter-layer per PROJECT_ORIENTATION.md's tone/mechanics split).

**B. Location arrival (occupancy chain).** The occupancy chain's **hook d6** (campaign
mechanics-reference: 5-6 connects to a live thread) reads against the **horizon** when a
chartered module is active. On a 5 or 6, the location's scene ties to the live stage's
content or spine_hooks, not an invented thread. On 1-4 it connects to nothing, as before.

**C. Explicit pull.** When the DM needs to move the story and the dice have been quiet (§5's
anti-lull rule), the DM may consult the horizon directly and reach for a spine_hook. This is
the sanctioned, non-random path to advance a stalled arc, distinct from the random fire points
above.

---

## 3. TWO NEW ENGINE WRITES (state, not memory)

Like every number in this engine, coverage and progression are **written**, never trusted to
recall (§2 anti-fabrication; the same discipline that routes dice through code):

- **Render.** When an area's box text is read or paraphrased at the table (the book's own
  definition of a visited room), mark that area `rendered` in the ledger. A resolved objective
  marks `resolved`. A deliberate pass marks `skipped`. Nothing is left silently `untouched`
  after the party was there.
- **Advance.** When a stage's `exit_condition` resolves, advance the spine's current-stage
  pointer. This opens the next stage's gate and regenerates the live content table. Advancing
  is a deliberate write, surfaced on the turn's `DM ROLLS THIS RESPONSE` line, never an
  ambient drift.

Both ride the §5 save-write, so they survive compression the way QUESTS and NPC REGISTRY do.

---

## 4. BOOT (tier 2)

At boot, after the master prompt and charter, read three things — all single-location reads,
which is what keeps a cross-document contradiction from hiding:

1. The **live spine stage** (the current-stage pointer) and its objective.
2. The **coverage ledger rollup** (rendered/total per location group in the live horizon).
3. The **charter's locked-facts block**, reconciled against the save. Each locked fact names
   the save field it must match; a mismatch is surfaced on the boot receipt, never silently
   carried. (This is the guard against the locked-fact drift that ran unchecked for ten
   sessions in the prior campaign.)

---

## 5. THE TWO ANTI-FABRICATION GUARANTEES

- **The DM never invents module content.** Areas, NPCs, and their entries come from the
  manifest and hooks, surfaced by the dice; the DM does not free-invent a room the book keyed.
  This is §2 applied to a published module: the content already exists, so reach for it, do
  not fabricate a parallel one.
- **The DM never invents metaplot beyond the spine.** The spine is authored canon — the
  publisher's throughline, not a DM invention — and is the **one sanctioned exception** to the
  charter's no-metaplot rule. Nothing beyond it may be promoted into a hidden master plan. The
  charter's emergent-continuity rule still governs everything the spine does not: consequences
  of play, logged as they happen, never a secret connection revealed after the fact.

---

## 6. COMPLETION GUARD

The signal is **stage-gated then proximity-gated, never a global completion meter.** There is
no "you are N% through the module, push harder." Surfacing is optional; a stage may exit with
in-scope content left untouched, logged `skipped`. The spine sets the pace; the ledger keeps
the honest record of what that pace cost. This directs the sandbox without railroading it and
without turning coverage into a checklist.

---

## 7. ONE-LINE SUMMARY FOR THE DM

> On a quest-linked content firing under a chartered module, roll the live content table for the
> current stage — real module content, in story order — instead of inventing a beat. Render
> what the party experiences, advance the spine when a stage resolves, and never invent content
> the manifest already holds or metaplot the spine does not. Ambient stays generic; the guard
> stays no-completion-meter.
