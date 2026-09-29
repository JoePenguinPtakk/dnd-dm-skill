#!/usr/bin/env python3
"""The dice engine and world-dice ledger for the v5 master prompt family.

Law 4 requires every world die to come from a real code execution, never a
number the model wrote. This script is that execution, and it is also the ONLY
writer of the ledger that proves it happened.

The ledger is a JSON-lines file (one JSON object per line) in the campaign
repo at `dice/ledger.jsonl`. Each entry is signed with an HMAC key the model
never sees (`~/.dnd-dice/key`) and chained to the entry before it, so a line
written by anything other than this script fails `verify`. The `DM ROLLS` line
in the DM's prose is a copy for the table to read. It is not the ledger and
proves nothing on its own; the ledger ID `[R0042]` it carries is the proof.

USAGE
  Session (run at boot, before any roll):
    roll.py session start <campaign-dir>   open a session; logs real start time
    roll.py session status                 real time elapsed, rolls this session
    roll.py session end                    close the session

  Rolling (every world die, every world-side random pick):
    roll.py LABEL:SPEC [LABEL:SPEC ...]    one call per chain; all logged
      The output IS the response's DM ROLLS section. Paste it verbatim.
      SPEC dice:  d20  d20+5  2d6+3  d20adv+7  d20dis  d100
      SPEC pick:  pick[a|b|c]              uniform pick, declared before draw
                  pick[a=3|b=1|c=1]        weighted ("loaded") pick
    Optional flags (apply to every die in the call):
      --reroll-of R0042 --reason "Lucky feat"   a RAW or player-invoked reroll

  Reading and proving:
    roll.py show [N]                       last N entries (default 10)
    roll.py cite R0042 [R0043 ...]         print those entries exactly
    roll.py verify                         check signatures and chain
    roll.py audit FILE                     check every [R####] cited in a text

PICK RULES (enforced here, not by trust)
  A pick needs at least 2 outcomes, every weight a whole number >= 1, and no
  single outcome above 90% of the total weight. The DM may load the dice; the
  dice must still be able to say no. Weights are recorded before the draw.

Randomness: every die and pick is drawn from the OS entropy pool via
`secrets`, not `random`. See `die()` for why.
"""
import datetime as dt
import fcntl
import hashlib
import hmac
import json
import os
import re
import secrets
import sys
from pathlib import Path

HOME = Path.home() / ".dnd-dice"
KEY = HOME / "key"
ACTIVE = HOME / "active.json"
MAX_SHARE = 0.90

SPEC = re.compile(r"^(\d*)d(\d+)(adv|dis)?([+-]\d+)?$", re.I)
PICK = re.compile(r"^pick\[(.+)\]$", re.I | re.S)
CITE = re.compile(r"\[(R\d{4,})\]\s*(\S+)\s+(pick\[[^\]]*\]|[^\s=]+)=([^\s(·]+)")


def die(sides):
    """One die, drawn from the OS entropy pool.

    Uses `secrets`, not `random`. `random` is a Mersenne Twister seeded once at
    import: reproducible, and predictable from enough outputs. `secrets.randbelow`
    draws from the OS CSPRNG and rejects out-of-range draws rather than taking a
    modulo, so there is no bias toward the low faces.
    """
    return secrets.randbelow(sides) + 1


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def fail(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    return 1


# ---------- key, session, ledger plumbing ----------

def key():
    HOME.mkdir(mode=0o700, exist_ok=True)
    if not KEY.exists():
        fd = os.open(KEY, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.write(fd, secrets.token_hex(32).encode())
        os.close(fd)
    return KEY.read_bytes().strip()


def sign(entry, k):
    body = json.dumps({x: entry[x] for x in entry if x != "sig"}, sort_keys=True, separators=(",", ":"))
    return hmac.new(k, body.encode(), hashlib.sha256).hexdigest()


def engine_hash():
    return hashlib.sha256(Path(__file__).resolve().read_bytes()).hexdigest()[:16]


def head_path(ledger):
    """Where the engine records the ledger's last entry, outside the campaign repo."""
    tag = hashlib.sha256(str(Path(ledger).resolve()).encode()).hexdigest()[:16]
    return HOME / f"head-{tag}.json"


def active():
    if not ACTIVE.exists():
        return None
    return json.loads(ACTIVE.read_text())


def ledger_path(act):
    return Path(act["campaign"]) / "dice" / "ledger.jsonl"


def read_all(path):
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def append(path, records):
    """Append signed, chained records under an exclusive lock. Returns them."""
    k = key()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        lines = [l for l in f.read().splitlines() if l.strip()]
        last = json.loads(lines[-1]) if lines else None
        seq = (int(last["id"][1:]) if last else 0)
        prev = last["sig"] if last else "GENESIS"
        out = []
        for r in records:
            seq += 1
            r = {"id": f"R{seq:04d}", "ts": now(), "prev": prev, "engine": engine_hash(), **r}
            r["sig"] = sign(r, k)
            prev = r["sig"]
            out.append(r)
        f.seek(0, 2)
        for r in out:
            f.write(json.dumps(r, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())
        head_path(path).write_text(json.dumps({"id": out[-1]["id"], "sig": out[-1]["sig"]}))
        fcntl.flock(f, fcntl.LOCK_UN)
    return out


# ---------- dice ----------

def roll_dice(spec):
    m = SPEC.match(spec.strip())
    if not m:
        raise ValueError(f"unparseable dice spec: {spec!r}")
    count, sides = int(m.group(1) or 1), int(m.group(2))
    mode, mod = (m.group(3) or "").lower(), int(m.group(4) or 0)
    if count < 1 or count > 100 or sides < 2 or sides > 1000:
        raise ValueError(f"dice out of range: {spec!r}")
    if mode and (count != 1 or sides != 20):
        raise ValueError(f"advantage/disadvantage applies to a single d20: {spec!r}")
    if mode:
        pair = [die(20), die(20)]
        kept = max(pair) if mode == "adv" else min(pair)
        faces, shown = pair, f"[{pair[0]},{pair[1]} {mode}]"
        total = kept + mod
    else:
        faces = [die(sides) for _ in range(count)]
        shown = f"({','.join(map(str, faces))})" if count > 1 else ""
        total = sum(faces) + mod
    if mod:
        sign_ = "+" if mod > 0 else ""
        shown = f"{shown}{sign_}{mod}" if shown else f"({faces[0]}{sign_}{mod})"
    return {"kind": "dice", "spec": spec, "faces": faces, "mod": mod, "result": total}, shown


def parse_pick(body):
    opts = []
    for part in body.split("|"):
        name, eq, w = part.rpartition("=") if "=" in part else (part, "", "1")
        name = name.strip()
        if not name:
            raise ValueError(f"empty outcome in pick[{body}]")
        if re.search(r"\s", name):
            raise ValueError(f"outcome {name!r} has a space; use hyphens (old-man) so citations stay checkable")
        if not re.fullmatch(r"\d+", w.strip()):
            raise ValueError(f"weight must be a whole number: {part!r}")
        opts.append((name, int(w)))
    if len(opts) < 2:
        raise ValueError("a pick needs at least 2 outcomes; one outcome is a decision, not a roll")
    if any(w < 1 for _, w in opts):
        raise ValueError("every weight must be >= 1; an outcome the dice cannot reach is not on the table")
    if len({n for n, _ in opts}) != len(opts):
        raise ValueError("duplicate outcome names; merge them into one weight")
    total = sum(w for _, w in opts)
    top = max(w for _, w in opts)
    if top / total > MAX_SHARE:
        raise ValueError(f"loaded past the limit: one outcome holds {top}/{total} "
                         f"({top/total:.0%}); max is {MAX_SHARE:.0%}. The dice must be able to say no.")
    return opts, total


def roll_pick(spec):
    opts, total = parse_pick(PICK.match(spec.strip()).group(1))
    draw = die(total)
    acc = 0
    for name, w in opts:
        acc += w
        if draw <= acc:
            chosen = name
            break
    table = [{"outcome": n, "weight": w} for n, w in opts]
    return {"kind": "pick", "spec": spec, "table": table, "draw": f"d{total}={draw}", "result": chosen}, f"(d{total}={draw})"


# ---------- commands ----------

def cmd_session(args):
    if not args:
        return fail("session needs start <campaign-dir> | status | end")
    sub = args[0]
    if sub == "start":
        if len(args) < 2:
            return fail("session start needs the campaign repo directory")
        camp = Path(args[1]).expanduser().resolve()
        if not camp.is_dir():
            return fail(f"not a directory: {camp}")
        HOME.mkdir(mode=0o700, exist_ok=True)
        key()
        sid = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        act = {"campaign": str(camp), "session": sid, "start": now()}
        ACTIVE.write_text(json.dumps(act))
        [r] = append(ledger_path(act), [{"kind": "event", "event": "SESSION_START", "session": sid, "label": "session", "result": act["start"]}])
        print(f"SESSION START: {act['start']} · session {sid} · ledger {ledger_path(act)} · [{r['id']}]")
        return 0
    act = active()
    if not act:
        return fail("no active session; run: roll.py session start <campaign-dir>")
    if sub == "status":
        start = dt.datetime.fromisoformat(act["start"])
        el = dt.datetime.now(dt.timezone.utc) - start
        h, m = divmod(int(el.total_seconds()) // 60, 60)
        n = sum(1 for e in read_all(ledger_path(act)) if e.get("session") == act["session"] and e["kind"] != "event")
        print(f"REAL: {h}h{m:02d}m elapsed · session {act['session']} · {n} world rolls logged")
        return 0
    if sub == "end":
        [r] = append(ledger_path(act), [{"kind": "event", "event": "SESSION_END", "session": act["session"], "label": "session", "result": now()}])
        ACTIVE.unlink()
        print(f"SESSION END: session {act['session']} closed · [{r['id']}]")
        return 0
    return fail(f"unknown session command: {sub}")


def cmd_roll(argv):
    act = active()
    if not act:
        return fail("no active session, so nothing can be logged; run: roll.py session start <campaign-dir>")
    reroll_of = reason = None
    items = []
    it = iter(argv)
    for a in it:
        if a == "--reroll-of":
            reroll_of = next(it, None)
        elif a == "--reason":
            reason = next(it, None)
        else:
            items.append(a)
    if reroll_of and not reason:
        return fail("a reroll must name its RAW or player-invoked reason (--reason \"Lucky feat\")")
    if reroll_of:
        if not any(e["id"] == reroll_of for e in read_all(ledger_path(act))):
            return fail(f"--reroll-of {reroll_of}: no such entry in the ledger")
    if not items:
        return fail("nothing to roll")
    records, shown = [], []
    try:
        for arg in items:
            label, sep, spec = arg.partition(":")
            if not sep:
                label, spec = "roll", arg
            rec, detail = roll_pick(spec) if PICK.match(spec.strip()) else roll_dice(spec)
            rec.update({"label": label, "session": act["session"]})
            if reroll_of:
                rec.update({"reroll_of": reroll_of, "reason": reason})
            records.append(rec)
            shown.append(detail)
    except ValueError as e:
        return fail(str(e))
    out = append(ledger_path(act), records)
    # This output IS the response's DM ROLLS section: paste it verbatim.
    # One bolded line per die (§1-quinquies), each carrying its ledger ID.
    tail = f" · REROLL of {reroll_of} ({reason})" if reroll_of else ""
    span = out[0]["id"] + (f"–{out[-1]['id']}" if len(out) > 1 else "")
    print(f"**DM ROLLS THIS RESPONSE** · engine ledger {span}")
    for r, d in zip(out, shown):
        print(f"**[{r['id']}] {r['label']}** {r['spec']}={r['result']}{d}{tail}")
    return 0


def cmd_show(args, ids=None):
    act = active()
    path = ledger_path(act) if act else None
    if not path or not path.exists():
        return fail("no active ledger")
    rows = read_all(path)
    if ids:
        want = set(ids)
        rows = [r for r in rows if r["id"] in want]
        missing = want - {r["id"] for r in rows}
        for m in sorted(missing):
            print(f"{m}: NOT IN LEDGER")
    else:
        rows = rows[-(int(args[0]) if args else 10):]
    for r in rows:
        print(json.dumps({x: r[x] for x in r if x not in ("sig", "prev")}, sort_keys=True))
    return 0 if not ids or not missing else 1


def cmd_verify(args):
    act = active()
    path = Path(args[0]).expanduser() if args else (ledger_path(act) if act else None)
    if not path or not path.exists():
        return fail("no ledger to verify")
    k = key()
    prev = "GENESIS"
    rows = read_all(path)
    for i, r in enumerate(rows, 1):
        if r.get("prev") != prev:
            print(f"BROKEN CHAIN at line {i} ({r.get('id')}): an entry was inserted, removed, or reordered")
            return 1
        if not hmac.compare_digest(sign(r, k), r.get("sig", "")):
            print(f"BAD SIGNATURE at line {i} ({r.get('id')}): not written by this engine, or edited after")
            return 1
        if r.get("id") != f"R{i:04d}":
            print(f"BAD SEQUENCE at line {i} ({r.get('id')})")
            return 1
        prev = r["sig"]
    hp = head_path(path)
    if hp.exists():
        head = json.loads(hp.read_text())
        last = rows[-1] if rows else {}
        if (last.get("id"), last.get("sig")) != (head["id"], head["sig"]):
            print(f"TRUNCATED: the engine last wrote {head['id']}, but the ledger ends at {last.get('id')}")
            return 1
    else:
        print("WARNING: no head record for this ledger; tail truncation cannot be checked")
    engines = sorted({r["engine"] for r in rows})
    print(f"LEDGER OK · {len(rows)} entries · chain and signatures intact · engine versions {', '.join(engines)}")
    return 0


def cmd_audit(args):
    """Check every '[R0042] label spec=result' citation in a text against the ledger."""
    if not args:
        return fail("audit needs a text file")
    act = active()
    if not act:
        return fail("no active session")
    text = Path(args[0]).read_text().replace("**", "")
    rows = {r["id"]: r for r in read_all(ledger_path(act))}
    bad = 0
    found = CITE.findall(text)
    for rid, label, spec, result in found:
        r = rows.get(rid)
        if not r:
            print(f"{rid}: CITED BUT NOT IN LEDGER (fabricated)")
            bad += 1
        elif (r.get("label"), r.get("spec"), str(r.get("result"))) != (label, spec, result):
            print(f"{rid}: TEXT SAYS {label} {spec}={result} · LEDGER SAYS {r.get('label')} {r.get('spec')}={r.get('result')}")
            bad += 1
    print(f"AUDIT: {len(found)} citations checked · {bad} bad")
    return 1 if bad else 0


def main(argv):
    if not argv:
        print(__doc__.strip())
        return 2
    cmd = argv[0]
    if cmd == "session":
        return cmd_session(argv[1:])
    if cmd == "show":
        return cmd_show(argv[1:])
    if cmd == "cite":
        return cmd_show([], ids=argv[1:])
    if cmd == "verify":
        return cmd_verify(argv[1:])
    if cmd == "audit":
        return cmd_audit(argv[1:])
    return cmd_roll(argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
