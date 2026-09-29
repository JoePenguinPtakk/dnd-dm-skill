# Dice engine and ledger: setup from scratch (Mac or Linux)

This is how to make a machine able to run the AI DM with real, provable world
dice. It is part of the master prompt package: §1-sexies of every O/S/H HEAD
assumes this setup exists. Every command below is **for Joe to run by hand in
his own Terminal**, not for the AI. The AI is blocked from most of these files
on purpose.

Works on macOS and Linux. Not Windows (the engine uses Unix file locking).

---

## What the pieces are

| Piece | Where it lives | Job |
|---|---|---|
| `roll.py` (the engine) | `~/.claude/skills/dnd-dm/` | Rolls real dice, writes the ledger. Knows nothing about what a roll means. |
| The ledger | `<campaign repo>/dice/ledger.jsonl` | One line per roll: ID, time, label, dice, faces, total, signature. Committed with the saves. |
| The key | `~/.dnd-dice/key` | Signs every ledger line. **Whoever holds the key can sign rolls.** The AI never reads it. |
| Head records | `~/.dnd-dice/head-*.json` | The last line the engine wrote, so deleted lines are caught. |
| `guard.py` | `~/.claude/skills/dnd-dm/` | Claude Code hook. Blocks the AI from touching the ledger, key, engine, guard, switch, or Claude Code settings. |
| The switch | `~/.dnd-dice/dice-guard` | Joe's on/off for the guard. Every change is bannered, logged, and announced in Discord. |
| `SKILL.md` | `~/.claude/skills/dnd-dm/` | The `dnd-dm` skill: how the AI boots and plays. |

**The authority is the key.** A ledger line is real only if it verifies against
the key. So there is **one key per table**, made once, copied by hand to every
machine Joe DMs from, and backed up somewhere the AI cannot reach (a password
manager note is fine). Lose it and old ledgers can no longer be verified.

---

## 1. Prerequisites

```bash
python3 --version
```

Needs Python 3.8 or newer. Also needs `git` and the real Claude Code CLI
(`claude`). The hook does **not** run under other harnesses (for example
CCFPcore Pure), so the guard only protects real Claude Code sessions.

Clone the two repos (skip whichever is already there):

```bash
git clone https://github.com/JoePenguinPtakk/Building-a-Better-Prompt.git ~/Projects/Building-a-Better-Prompt
```

(Plus the campaign repo, for example Waterdeep, wherever it normally lives.)

## 2. Install the skill and engine

Replace the path with where the engine repo actually is on this machine:

```bash
mkdir -p ~/.claude/skills && cp -R ~/Projects/Building-a-Better-Prompt/.claude/skills/dnd-dm ~/.claude/skills/
```

```bash
chmod +x ~/.claude/skills/dnd-dm/*.py
```

## 3. The key

**First machine ever (this is already done on the Mac once a session has
started there):** the engine makes the key itself the first time a session
starts. Nothing to do.

**Every other machine:** copy the key from the machine that has it. Never make a
second key. On the new machine:

```bash
mkdir -p ~/.dnd-dice && chmod 700 ~/.dnd-dice
```

```bash
scp mac:~/.dnd-dice/key ~/.dnd-dice/key
```

(Replace `mac` with the Mac's SSH or Tailscale name.) Then lock it down:

```bash
chmod 600 ~/.dnd-dice/key
```

## 4. Install the switch

```bash
cp ~/.claude/skills/dnd-dm/dice-guard.py ~/.dnd-dice/dice-guard && chmod 700 ~/.dnd-dice/dice-guard
```

```bash
python3 ~/.dnd-dice/dice-guard status
```

It should print `DICE GUARD IS ON (locked)`.

## 5. Install the guard hook

This adds the guard to Claude Code's settings without disturbing anything else
in them:

```bash
python3 -c "import json,os;p=os.path.expanduser('~/.claude/settings.json');s=json.load(open(p)) if os.path.exists(p) else {};c='python3 \"\$HOME/.claude/skills/dnd-dm/guard.py\"';h=s.setdefault('hooks',{}).setdefault('PreToolUse',[]);h.append({'matcher':'*','hooks':[{'type':'command','command':c}]}) if c not in json.dumps(h) else None;json.dump(s,open(p,'w'),indent=2);print('guard hook installed')"
```

Restart Claude Code after this. From then on, the AI cannot edit the settings
file to remove the hook; only Joe can, by hand.

## 6. Check it works

Open a Claude Code session and ask it to run exactly these, one at a time:

1. `python3 ~/.claude/skills/dnd-dm/roll.py session start /tmp/dice-test` should print a `SESSION START` line.
2. `python3 ~/.claude/skills/dnd-dm/roll.py test:d20` should print a `DM ROLLS THIS RESPONSE` block with an `[R0002]` line.
3. `python3 ~/.claude/skills/dnd-dm/roll.py verify` should print `LEDGER OK`.
4. Ask it to write any text into `/tmp/dice-test/dice/ledger.jsonl`. It should be **blocked** by the dice-ledger guard.
5. `python3 ~/.claude/skills/dnd-dm/roll.py session end`.

If step 4 is not blocked, the hook is not installed: redo step 5 and restart.

## 7. Discord bot (optional, per campaign)

The Waterdeep relay posts world dice straight from the ledger and runs `%roll`
/ `%rollgo` through the engine. It must run **on the same machine as the DM**,
because it reads the ledger file and the key directly. Optional `bot/.env`
lines:

```
DICE_CHANNEL_ID=123456789012345678
```

See the campaign's `bot/README.md`.

---

## Playing one campaign from more than one machine

- **One machine at a time.** Never run the same campaign on two machines at
  once. Two machines appending to one ledger fork its chain, and `verify` fails.
- **Close, commit, push, then switch.** At session close the DM runs `verify`
  and `session end`, and the ledger is committed with the save. Push it. On the
  other machine, pull before booting.
- **Same key everywhere** (step 3), or rolls made on one machine fail `verify`
  on the other, and the bot flags them as forged.
- Known quirk: right after pulling a ledger that the other machine extended,
  `verify` can report `TRUNCATED` until this machine's first roll of the session
  (its head record is behind). Boot's `session start` is a roll-log entry, so a
  normal boot clears it. A proper fix is queued for the next engine unlock.

## Engine maintenance

Engine files are locked by the guard. To let an engineering session change
them:

```bash
python3 ~/.dnd-dice/dice-guard off
```

and afterwards:

```bash
python3 ~/.dnd-dice/dice-guard on
```

Every change shows a banner, is logged in the open session's ledger, and is
announced in Discord. Never unlock during play.
