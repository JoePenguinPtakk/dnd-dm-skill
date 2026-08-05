# dnd-dm skill

Installable Claude Code skill: boots the v5 D&D 5.5E master prompt family
and runs a session. This repo is the install target, nothing else, no
engineering history, no archive, no CHANGELOG.

**To install:** copy `.claude/skills/dnd-dm/` into any project's own
`.claude/skills/`, or into `~/.claude/skills/` to make it available from
every project. Either way, keep `docs/MASTER_PROMPT_v5-*_HEAD.md` (and the
charter/mechanics-reference files, if you want the bundled example) at the
same relative path alongside it — `SKILL.md` reads them by relative path.

**This repo is a mirror, not the source of truth.** Design lineage, the
CHANGELOG, the full engineering history, and all in-progress work happen in
[JoePenguinPtakk/Building-a-Better-Prompt](https://github.com/JoePenguinPtakk/Building-a-Better-Prompt).
Whenever a HEAD file changes there, the same file gets copied here and
pushed, same commit session, so this repo always reflects current canon
with none of the archive weight.
