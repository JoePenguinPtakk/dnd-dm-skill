# dnd-dm skill

Installable Claude Code skill: boots the v5 D&D 5.5E master prompt family
and runs a session. This repo is the install target, nothing else, no
engineering history, no archive, no CHANGELOG.

**To install:** copy `.claude/skills/dnd-dm/` into any project's own
`.claude/skills/`, or into `~/.claude/skills/` to make it available from
every project. Either way, keep `docs/MASTER_PROMPT_v5-*_HEAD.md` (and the
charter/mechanics-reference files, if you want the bundled example) at the
same relative path alongside it — `SKILL.md` reads them by relative path.

**First run / new campaign:** start at
`.claude/skills/dnd-dm/GETTING_STARTED.md`. It is the setup interview an LLM
runs the first time — deciding what to play (a published module or an emergent
campaign), building or picking a charter, setting house rules, choosing a tier,
and creating the campaign — before `SKILL.md` boots the master prompt and play
begins. To turn a published module into a campaign, use the skill's `module_build.py`, `map.py` and
`book.py` (master prompt §6-septies; design notes in
`docs/MASTER_PROMPT_supplement_chartered-module.md`). `charter-generator/` is the superseded
first attempt, kept for reference.

**Every tool is campaign-agnostic.** The dice engine, the lore, holdings, module and book tools, and the
live-table Discord bot (`.claude/skills/dnd-dm/bot/`) carry no campaign's data. A campaign keeps its own
data (its `lore/`, `holdings/`, `module/`, saves, and its bot's `.env` and voices) in its own repo.

**This repo is a mirror, not the source of truth.** Design lineage, the
CHANGELOG, the full engineering history, and all in-progress work happen in
[JoePenguinPtakk/Building-a-Better-Prompt](https://github.com/JoePenguinPtakk/Building-a-Better-Prompt).
Whenever a HEAD file changes there, the same file gets copied here and
pushed, same commit session, so this repo always reflects current canon
with none of the archive weight.
