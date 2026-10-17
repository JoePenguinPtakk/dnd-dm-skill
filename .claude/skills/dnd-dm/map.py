#!/usr/bin/env python3
"""map.py: where the party is in a published module, and what of it they have actually experienced.

The master prompt's §6-septies (CHARTERED-MODULE CONTENT BRIDGE) says what to do; this tool keeps the record so
the DM never decides from memory, or from a visit, that the party "already did" something. It rolls no dice.
Every pick it prints is flat (§1-sexies rule 3) and goes into one roll.py call exactly as written.

THE RULE IT ENFORCES: being somewhere is not experiencing it. A unit of the module (a keyed area such as G8, or
an event such as ch3-fireball) is UNTOUCHED until a `mark` says otherwise, with evidence of what happened at
the table. "No record" means the party has not experienced it, whatever the save, the summary or the DM's
memory suggests.

Statuses (forward only; `--correct` moves one back, with a reason, and is logged):
  untouched  the default; nothing is written
  seen       the party saw it or heard of it without engaging its content (looked in, heard a rumor)
  played     its content ran at the table as the book directs (box text, occupants met, the event happened)
  done       nothing of it is left to resolve (the fight ended, the business finished, the clue found)
  closed     it can no longer happen (destroyed, its NPC dead elsewhere); the evidence is the reason.
             Closing a REQUIRED unit also needs --approved-by (Joe's word, never the DM's own).

Files, in <campaign repo>/module/ :
  module.json     name, book text path, drift threshold          (authored once)
  manifest.json   every unit: keyed areas and events, by group   (generated, then corrected by hand)
  spine.json      stages in order, plus branches that open        (authored: the campaign plan)
  progress.json   current stage, location, coverage, clock, day   (this tool writes it; never by hand)
  coverage.jsonl  every write, appended                           (this tool writes it)
  calendar.json   optional: the campaign's calendar and start     (`map.py day init` writes it)

A stage (spine.json "stages", in order) has: id, title, objective, live (groups or unit ids live while it is
current), opens (groups or unit ids live from then on, for good), required (unit ids that must be done or
closed before `advance`), needs (stage or branch ids that must be complete first), milestone (text printed
when it completes), ready (false = not authored yet: `advance` refuses to enter it). A branch (spine.json
"branches") has the same fields plus opens_after (a stage id) and optional (true/false); it is live from the
moment its opens_after stage completes until its required units are done.

DRIFT (keeps the DM on module): minutes of play since a live unit was last marked played or done, carried
across sessions. At or over module.json "drift_minutes" the card says DRIFT, and the master prompt sends the
next content firing straight to `map.py table`.

  map.py [--dir DIR] init                    validate the files, start at the first stage
  map.py session N                           a session starts (carries the drift clock)
  map.py card                                the boot card: stage, what's left, location, drift
  map.py stage                               the current stage and open branches in full
  map.py here PLACE                          set the location (group letter, unit id or name); lists what is
                                             here and what of it the party has experienced. Marks nothing.
  map.py mark UNIT STATUS --evidence TEXT [--approved-by WHO] [--correct REASON]
  map.py check QUERY                         has the party experienced it? (id or words)
  map.py advance                             move to the next stage, if its gates are met
  map.py table                               the live content table for a quest-linked firing
  map.py drift                               the drift clock
  map.py log [N]                             the last N coverage writes
  map.py verify [--expect STAMP]             the MAP stamp for the save
  map.py settings                            the charter's settings (master prompt §6-septies rule 7), read from
                                             the fenced block under the charter's SETTINGS heading
  map.py day                                 the campaign date (needs module/calendar.json)
  map.py day init --calendar harptos|gregorian [--start "Kythorn 1"] [--day N]
  map.py day add N --why TEXT                the calendar moves N days (also `day +N --why TEXT`)
  map.py day set N --why TEXT [--correct]    set the day number (backwards only with --correct)
  map.py day on N                            the date of Day N (changes nothing)
  map.py day when "Midsummer"                the next Day that date falls on, and how far off it is

CHARTER SETTINGS (rule 7). The charter holds a heading containing SETTINGS and, under it, one fenced block of
exact `key: value` lines. Only these keys and values count; anything else prints as IGNORED:
  time: pinned|off   leveling: milestone|xp   weather: module|roll   absent: queued|off   encounters: budgeted|printed
plus, under `encounters: budgeted`, one `boss: <creature name>` line per boss (repeatable; any name; `bestiary.py fit`
reads them). A setting the charter does not name is off. No charter file, or no block, means every setting is off.

THE CALENDAR. `day` keeps one number, the campaign day (Day 1 is the start date), and turns it into a date from
calendar.json, so month arithmetic is never done by hand. It moves only when told, with a reason: the running
clock, a TIME SKIP, or downtime the players declared (master prompt §6-septies rule 8). Real time never moves it.
"""
import argparse
import datetime
import hashlib
import json
import re
import sys
from pathlib import Path

ORDER = {"untouched": 0, "seen": 1, "played": 2, "done": 3}
STATUSES = ["seen", "played", "done", "closed"]
FINAL = ("done", "closed")


def now():
    return datetime.datetime.now().astimezone()


def iso(t):
    return t.isoformat(timespec="seconds")


def parse(s):
    return datetime.datetime.fromisoformat(s)


class Module:
    def __init__(self, root):
        self.root = Path(root)
        if not (self.root / "manifest.json").exists():
            print(f"MAP INERT: no module/manifest.json under {self.root}. This campaign is not chartered on a "
                  f"published module, so §6-septies does not apply. Nothing to do.")
            sys.exit(0)
        self.cfg = self._load("module.json", {})
        self.man = self._load("manifest.json", None)
        self.spine = self._load("spine.json", None)
        if self.spine is None:
            sys.exit("MAP ERROR: module/spine.json is missing.")
        self.prog = self._load("progress.json", None)
        self.units = {}
        for a in self.man.get("areas", []):
            self.units[a["id"]] = dict(a, kind="area")
        for e in self.man.get("events", []):
            self.units[e["id"]] = dict(e, kind="event")
        self.groups = self.man.get("groups", {})
        self.stages = sorted(self.spine["stages"], key=lambda s: s["order"])
        self.branches = self.spine.get("branches", [])
        self.parts = {s["id"]: s for s in self.stages + self.branches}

    def _load(self, name, default):
        p = self.root / name
        return json.loads(p.read_text()) if p.exists() else default

    def save(self):
        self.prog["clock"]["last_activity"] = iso(now())
        (self.root / "progress.json").write_text(json.dumps(self.prog, indent=1, sort_keys=True) + "\n")

    def append(self, rec):
        with (self.root / "coverage.jsonl").open("a") as f:
            f.write(json.dumps(rec, sort_keys=True) + "\n")

    # ---- state helpers
    def status(self, uid):
        return self.prog["coverage"].get(uid, {}).get("status", "untouched")

    def expand(self, refs):
        """Group letters and unit ids -> unit ids."""
        out = []
        for r in refs:
            if r in self.units:
                out.append(r)
            else:
                out.extend(u for u, d in self.units.items() if d.get("group") == r)
        return list(dict.fromkeys(out))

    def complete(self, part):
        return all(self.status(u) in FINAL for u in part.get("required", []))

    def stage(self):
        return self.parts[self.prog["stage"]]

    def stage_index(self, sid):
        return next(i for i, s in enumerate(self.stages) if s["id"] == sid)

    def done_stages(self):
        cur = self.stage_index(self.prog["stage"])
        return [s["id"] for s in self.stages[:cur]]

    def open_branches(self):
        done = set(self.done_stages())
        return [b for b in self.branches if b["opens_after"] in done]

    def part_done(self, pid):
        if pid in [s["id"] for s in self.stages]:
            return pid in self.done_stages() or (pid == self.prog["stage"] and self.complete(self.parts[pid]))
        b = self.parts[pid]
        return b["opens_after"] in self.done_stages() and self.complete(b)

    def live_units(self):
        """Units whose content is in play now: the current stage's live and required units, everything opened
        by a completed stage, and every open branch's units until it is complete."""
        refs = []
        cur = self.stage()
        refs += cur.get("live", []) + cur.get("required", [])
        for s in self.stages[:self.stage_index(cur["id"]) + 1]:
            refs += s.get("opens", [])
        for b in self.open_branches():
            if not self.complete(b):
                refs += b.get("live", []) + b.get("required", [])
            refs += b.get("opens", [])
        return set(self.expand(refs))

    def owner(self, uid):
        """The stage or branch whose content this unit is, for the dormant message."""
        for p in self.stages + self.branches:
            if uid in self.expand(p.get("live", []) + p.get("required", []) + p.get("opens", [])):
                return p
        return None

    # ---- drift
    def drift_minutes(self):
        c = self.prog["clock"]
        return c.get("carried_min", 0.0) + max(0.0, (now() - parse(c["since"])).total_seconds() / 60)

    def drift_line(self):
        lim = self.cfg.get("drift_minutes", 60)
        m = self.drift_minutes()
        flag = (f"DRIFT {m:.0f}/{lim} min: the next content firing skips the nature die and rolls `map.py table` "
                f"(§6-septies)") if m >= lim else f"drift {m:.0f}/{lim} min"
        return flag


def label(u):
    pages = u.get("pages") or []
    pg = f"p{pages[0]}" if len(pages) == 1 else (f"pp{pages[0]}-{pages[-1]}" if pages else "p?")
    return f"{u['id']} {u.get('title', '')} [{pg}]"


def find(M, query):
    q = query.strip()
    if q in M.units:
        return [q]
    if q in M.groups:
        return M.expand([q])
    words = [re.compile(r"\b" + re.escape(w) + r"\b", re.I) for w in re.findall(r"[\w']+", q)]
    hits = []
    for uid, u in M.units.items():
        hay = " ".join([uid, u.get("title", ""), u.get("group", ""), M.groups.get(u.get("group", ""), {}).get("name", ""),
                        u.get("summary", "")])
        if all(w.search(hay) for w in words):
            hits.append(uid)
    return hits



# ---------------------------------------------------------------- charter settings

SETTING_VALUES = {"time": ("pinned", "off"), "leveling": ("milestone", "xp"), "weather": ("module", "roll"),
                  "absent": ("queued", "off"), "encounters": ("budgeted", "printed")}
SETTING_DEFAULTS = {"time": "off", "leveling": "xp", "weather": "roll", "absent": "off", "encounters": "printed"}


def charter_file(M):
    """The campaign charter: module.json "charter" (a path from the repo root), else the one *.md at the repo root
    whose name has 'charter' in it (CHARTER.md wins a tie)."""
    repo = M.root.resolve().parent
    named = M.cfg.get("charter")
    if named:
        p = repo / named
        return (p if p.exists() else None), (None if p.exists() else f"module.json names charter '{named}': not found")
    c = sorted(f for f in repo.glob("*.md") if "charter" in f.name.lower())
    if len(c) == 1:
        return c[0], None
    exact = [f for f in c if f.name.upper() == "CHARTER.MD"]
    if exact:
        return exact[0], None
    if not c:
        return None, None
    return None, f"{len(c)} charter files at the repo root; name one in module.json \"charter\""


def read_settings(M):
    """-> (settings dict, ignored list, source note)."""
    got = dict(SETTING_DEFAULTS)
    got["bosses"] = []
    ignored = []
    path, err = charter_file(M)
    if err:
        return got, ignored, err + ": all settings off"
    if path is None:
        return got, ignored, "no charter file found: all settings off"
    lines = path.read_text().splitlines()
    head = next((i for i, ln in enumerate(lines) if ln.lstrip().startswith("#") and "settings" in ln.lower()), None)
    if head is None:
        return got, ignored, f"{path.name} has no SETTINGS heading: all settings off"
    i = head + 1
    while i < len(lines) and not lines[i].lstrip().startswith(("```", "#")):
        i += 1
    if i >= len(lines) or lines[i].lstrip().startswith("#"):
        return got, ignored, f"{path.name} SETTINGS heading has no fenced block: all settings off"
    i += 1
    while i < len(lines) and not lines[i].lstrip().startswith("```"):
        ln = lines[i].strip()
        i += 1
        if not ln or ln.startswith("#"):
            continue
        b = re.fullmatch(r"boss\s*:\s*(\S.*)", ln)
        if b:
            got["bosses"].append(b.group(1).strip())
            continue
        m = re.fullmatch(r"([A-Za-z_-]+)\s*:\s*([A-Za-z_-]+)", ln)
        if not m:
            ignored.append(ln)
            continue
        k, v = m.group(1), m.group(2)
        if k in SETTING_VALUES and v in SETTING_VALUES[k]:
            got[k] = v
        else:
            ignored.append(f"{k}: {v}")
    return got, ignored, path.name


def settings_line(M):
    got, ignored, src = read_settings(M)
    line = "SETTINGS: " + " · ".join(f"{k}={got[k]}" for k in SETTING_DEFAULTS)
    if got["encounters"] == "budgeted":
        line += " · BOSSES: " + ("; ".join(got["bosses"]) or "none named")
    if ignored:
        line += " · IGNORED: " + "; ".join(ignored)
    return line + f" ({src})"


# ---------------------------------------------------------------- the module calendar

CALENDARS = {
    "harptos": {"name": "Calendar of Harptos", "segments": [
        {"name": "Hammer", "days": 30, "season": "winter"},
        {"name": "Midwinter", "days": 1, "season": "winter", "holiday": True},
        {"name": "Alturiak", "days": 30, "season": "winter"},
        {"name": "Ches", "days": 30, "season": "spring"},
        {"name": "Tarsakh", "days": 30, "season": "spring"},
        {"name": "Greengrass", "days": 1, "season": "spring", "holiday": True},
        {"name": "Mirtul", "days": 30, "season": "spring"},
        {"name": "Kythorn", "days": 30, "season": "summer"},
        {"name": "Flamerule", "days": 30, "season": "summer"},
        {"name": "Midsummer", "days": 1, "season": "summer", "holiday": True},
        {"name": "Eleasis", "days": 30, "season": "summer"},
        {"name": "Eleint", "days": 30, "season": "autumn"},
        {"name": "Highharvestide", "days": 1, "season": "autumn", "holiday": True},
        {"name": "Marpenoth", "days": 30, "season": "autumn"},
        {"name": "Uktar", "days": 30, "season": "autumn"},
        {"name": "Feast of the Moon", "days": 1, "season": "autumn", "holiday": True},
        {"name": "Nightal", "days": 30, "season": "winter"}]},
    "gregorian": {"name": "Gregorian calendar (no leap day)", "segments": [
        {"name": n, "days": d, "season": s} for n, d, s in [
            ("January", 31, "winter"), ("February", 28, "winter"), ("March", 31, "spring"), ("April", 30, "spring"),
            ("May", 31, "spring"), ("June", 30, "summer"), ("July", 31, "summer"), ("August", 31, "summer"),
            ("September", 30, "autumn"), ("October", 31, "autumn"), ("November", 30, "autumn"),
            ("December", 31, "winter")]]},
}


class Calendar:
    def __init__(self, cfg):
        self.cfg = cfg
        self.seg = cfg["segments"]
        self.year = sum(g["days"] for g in self.seg)
        self.start = self.index(cfg["start"])

    def index(self, text):
        """'Kythorn 1' or 'Midsummer' -> 0-based day of the year."""
        m = re.fullmatch(r"\s*(.+?)\s*(\d+)?\s*", text)
        name, d = m.group(1), int(m.group(2) or 1)
        base = 0
        for g in self.seg:
            if g["name"].lower() == name.lower():
                if not 1 <= d <= g["days"]:
                    raise ValueError(f"'{text}': {g['name']} has {g['days']} day(s)")
                return base + d - 1
            base += g["days"]
        raise ValueError(f"'{text}': no month or holiday named '{name}'")

    def date(self, day):
        """Day N (1 = start) -> (year offset, segment, day in segment)."""
        off = self.start + day - 1
        y, pos = divmod(off, self.year)
        for g in self.seg:
            if pos < g["days"]:
                return y, g, pos + 1
            pos -= g["days"]
        raise AssertionError

    def text(self, day):
        y, g, d = self.date(day)
        name = g["name"] if g["days"] == 1 else f"{g['name']} {d}"
        return name + (f" (year +{y})" if y else "")

    def line(self, day):
        y, g, d = self.date(day)
        out = f"DAY {day} · {self.text(day)} · {g['season']}"
        if g.get("holiday"):
            out += " · a holiday, in no month"
        elif g["days"] == 30:
            ten, k = divmod(d - 1, 10)
            out += f" · tenday {ten + 1} of 3, day {k + 1} of 10" + (" (first day)" if k == 0 else
                                                                      " (last day)" if k == 9 else "")
        return out

    def when(self, day, text):
        """The first Day >= `day` that falls on `text`."""
        target = self.index(text)
        cur = (self.start + day - 1) % self.year
        return day + (target - cur) % self.year


def get_calendar(M):
    p = M.root / "calendar.json"
    if not p.exists():
        return None
    return Calendar(json.loads(p.read_text()))


def need_cal(M):
    need_prog(M)
    cal = get_calendar(M)
    if cal is None:
        sys.exit("DAY: this campaign has no module/calendar.json. `map.py day init --calendar harptos|gregorian "
                 "--start \"<date>\"` creates it; until then the date is the DM's to keep, as before.")
    if "day" not in M.prog:
        sys.exit("DAY: calendar.json exists but no day is set. `map.py day init --force` sets Day 1 (or --day N).")
    return cal

# ---------------------------------------------------------------- commands

def cmd_init(M, a):
    if M.prog and not a.force:
        print("MAP already initialised (progress.json exists). Use --force only to start the module over.")
        return 1
    errors = []
    for p in M.stages + M.branches:
        for r in p.get("live", []) + p.get("required", []) + p.get("opens", []):
            if r not in M.units and r not in M.groups:
                errors.append(f"{p['id']}: '{r}' is neither a unit nor a group")
        for n in p.get("needs", []):
            if n not in M.parts:
                errors.append(f"{p['id']}: needs unknown part '{n}'")
    for b in M.branches:
        if b.get("opens_after") not in [s["id"] for s in M.stages]:
            errors.append(f"{b['id']}: opens_after '{b.get('opens_after')}' is not a stage")
    for uid in M.units:
        if "|" in uid or "]" in uid or " " in uid:
            errors.append(f"unit id '{uid}' cannot go in a pick")
    if errors:
        print("MAP INIT REFUSED:\n  " + "\n  ".join(errors))
        return 1
    t = iso(now())
    M.prog = {"stage": M.stages[0]["id"], "location": None, "session": a.session or 0, "coverage": {},
              "clock": {"since": t, "carried_min": 0.0, "last_activity": t}}
    M.save()
    M.append({"at": t, "op": "init", "stage": M.prog["stage"]})
    print(f"MAP INIT: {len(M.units)} units in {len(M.groups)} groups; {len(M.stages)} stages, "
          f"{len(M.branches)} branches. Stage: {M.stages[0]['id']}.")
    return 0


def need_prog(M):
    if not M.prog:
        sys.exit("MAP: not initialised. Run `map.py init` once at the campaign's first boot.")


def cmd_session(M, a):
    need_prog(M)
    c = M.prog["clock"]
    tail = max(0.0, (parse(c["last_activity"]) - parse(c["since"])).total_seconds() / 60)
    c["carried_min"] = c.get("carried_min", 0.0) + tail
    c["since"] = iso(now())
    M.prog["session"] = a.n
    M.save()
    M.append({"at": iso(now()), "op": "session", "session": a.n, "carried_min": round(c["carried_min"], 1)})
    print(f"MAP SESSION {a.n}. {M.drift_line()}")
    return 0


def remaining(M, part):
    return [u for u in part.get("required", []) if M.status(u) not in FINAL]


def cmd_card(M, a):
    need_prog(M)
    s = M.stage()
    i = M.stage_index(s["id"])
    print(f"MAP CARD · {M.cfg.get('name', M.man.get('module', 'module'))} · session {M.prog.get('session')}")
    print(f"STAGE {i + 1}/{len(M.stages)}: {s['id']}: {s['title']}")
    print(f"  objective: {s.get('objective', '')}")
    rem = remaining(M, s)
    print(f"  required left ({len(rem)}): " + ("; ".join(label(M.units[u]) + f" ({M.status(u)})" for u in rem)
                                              if rem else "none: `map.py advance` when the table reaches it"))
    for b in M.open_branches():
        state = "complete" if M.complete(b) else f"{len(remaining(M, b))} required left"
        print(f"  branch {b['id']} ({'optional' if b.get('optional') else 'required'}): {b['title']}: {state}")
    loc = M.prog.get("location")
    if loc:
        here = M.expand([loc]) if loc in M.groups else [loc]
        live = M.live_units()
        todo = [u for u in here if u in live and M.status(u) in ("untouched", "seen")]
        print(f"LOCATION {loc} {M.groups.get(loc, {}).get('name', M.units.get(loc, {}).get('title', ''))}: "
              f"{len(todo)} live unit(s) here not yet experienced")
    else:
        print("LOCATION unset (`map.py here PLACE`)")
    cov = M.prog["coverage"]
    n = {k: sum(1 for v in cov.values() if v["status"] == k) for k in STATUSES}
    print(f"COVERAGE {len(cov)}/{len(M.units)} touched: " + " · ".join(f"{k} {v}" for k, v in n.items()))
    cal = get_calendar(M)
    if cal is not None and "day" in M.prog:
        print(cal.line(M.prog["day"]))
    print(settings_line(M))
    print(M.drift_line())
    M.save()
    return 0


def cmd_stage(M, a):
    need_prog(M)
    s = M.stage()
    print(f"STAGE {s['id']}: {s['title']} (chapter {s.get('chapter', '?')})")
    print(f"  objective: {s.get('objective', '')}")
    for u in s.get("required", []):
        print(f"  required: {label(M.units[u])}: {M.status(u)}")
    nxt = M.stage_index(s["id"]) + 1
    if nxt < len(M.stages):
        n = M.stages[nxt]
        gate = [x for x in n.get("needs", []) if not M.part_done(x)]
        print(f"  next: {n['id']}: {n['title']}" + ("" if n.get("ready", True) else " · NOT AUTHORED (advance refuses)")
              + (f" · also needs {', '.join(gate)}" if gate else ""))
        if s.get("milestone"):
            print(f"  milestone on completion: {s['milestone']}")
    for note in s.get("notes", []):
        print(f"  note: {note}")
    for b in M.open_branches():
        print(f"BRANCH {b['id']}: {b['title']} ({'optional' if b.get('optional') else 'required'})"
              + (f" · milestone: {b['milestone']}" if b.get("milestone") else ""))
        for u in b.get("required", []):
            print(f"  required: {label(M.units[u])}: {M.status(u)}")
    M.save()
    return 0


def cmd_here(M, a):
    need_prog(M)
    q = a.place
    if q in M.groups or q in M.units:
        loc = q
    else:
        hits = [g for g, d in M.groups.items() if all(w in d.get("name", "").lower() for w in q.lower().split())]
        if len(hits) != 1:
            print(f"HERE: '{q}' matches {len(hits)} groups {hits[:8]}; give the group letter or a unit id.")
            return 1
        loc = hits[0]
    M.prog["location"] = loc
    M.save()
    M.append({"at": iso(now()), "op": "here", "location": loc, "session": M.prog.get("session")})
    units = M.expand([loc]) if loc in M.groups else [loc]
    live = M.live_units()
    name = M.groups.get(loc, {}).get("name") or M.units[loc].get("title", "")
    print(f"HERE {loc}: {name}. Visiting marks nothing: each unit below stays as recorded until a `mark`.")
    dormant = []
    for u in units:
        st = M.status(u)
        if u in live or st != "untouched":
            ev = M.prog["coverage"].get(u, {}).get("evidence", "")
            print(f"  {label(M.units[u])}: {st.upper()}" + (f" · {ev}" if ev else ""))
        else:
            dormant.append(u)
    if dormant:
        owners = sorted({(M.owner(u) or {}).get("id", "?") for u in dormant})
        print(f"  DORMANT ({len(dormant)}): {', '.join(dormant)}. Their module content is not in play until "
              f"{', '.join(owners)}: describe the place as it stands, without that content.")
    book = M.cfg.get("book_tool_hint")
    if book:
        print(f"  read before running a unit: {book}")
    return 0


def cmd_mark(M, a):
    need_prog(M)
    uid = a.unit
    if uid not in M.units:
        print(f"MARK REFUSED: '{uid}' is not a unit. `map.py check {uid}` to search.")
        return 1
    if not a.evidence or len(a.evidence.strip()) < 8:
        print("MARK REFUSED: --evidence must say what happened at the table (who, what, and a ledger id or "
              "session if there is one).")
        return 1
    cur = M.status(uid)
    new = a.status
    live = M.live_units()
    if new in ("played", "done") and uid not in live and not a.correct:
        o = M.owner(uid)
        print(f"MARK REFUSED: {uid} is DORMANT; its content belongs to {o['id'] if o else 'no stage'} "
              f"({o['title'] if o else ''}), which is not live. The party can be at the place, but this content "
              f"is not in play yet.")
        return 1
    required_somewhere = any(uid in p.get("required", []) for p in M.stages + M.branches)
    if new == "closed" and required_somewhere and not a.approved_by:
        print(f"MARK REFUSED: {uid} is REQUIRED by the plan. Closing it needs --approved-by (Joe's word in chat, "
              f"quoted), never the DM's own judgment.")
        return 1
    if new != "closed" and cur != "closed" and ORDER[new] <= ORDER[cur] and not a.correct:
        print(f"MARK REFUSED: {uid} is already {cur}; statuses only move forward. A real mistake: --correct REASON.")
        return 1
    if cur == "closed" and not a.correct:
        print(f"MARK REFUSED: {uid} is closed. Reopening it needs --correct REASON.")
        return 1
    t = iso(now())
    rec = {"status": new, "evidence": a.evidence.strip(), "session": M.prog.get("session"), "at": t}
    if a.approved_by:
        rec["approved_by"] = a.approved_by
    if a.correct:
        rec["corrected_from"] = cur
        rec["correct_reason"] = a.correct
    M.prog["coverage"][uid] = rec
    beat = new in ("played", "done") and uid in live and not a.correct
    if beat:
        M.prog["clock"]["since"] = t
        M.prog["clock"]["carried_min"] = 0.0
    M.save()
    M.append(dict(rec, op="mark", unit=uid, previous=cur))
    print(f"MARKED {label(M.units[uid])}: {cur} -> {new}" + (" · drift clock reset" if beat else ""))
    s = M.stage()
    if uid in s.get("required", []) and M.complete(s):
        print(f"STAGE {s['id']} has every required unit resolved. `map.py advance` when the scene closes.")
    for b in M.open_branches():
        if uid in b.get("required", []) and M.complete(b):
            print(f"BRANCH {b['id']} COMPLETE." + (f" MILESTONE: {b['milestone']}" if b.get("milestone") else ""))
            M.append({"at": t, "op": "branch-complete", "branch": b["id"], "milestone": b.get("milestone")})
    return 0


def cmd_check(M, a):
    need_prog(M)
    hits = find(M, a.query)
    if not hits:
        print(f"CHECK '{a.query}': no unit matches. If the module has it, search the book (book.py find); "
              f"if it is not in the module, it is not module content.")
        return 0
    live = M.live_units()
    for u in hits[:20]:
        rec = M.prog["coverage"].get(u)
        if rec:
            print(f"  {label(M.units[u])}: {rec['status'].upper()} (session {rec.get('session')}) · {rec['evidence']}")
        else:
            print(f"  {label(M.units[u])}: NO RECORD. The party has NOT experienced this"
                  + ("" if u in live else " (and it is dormant)") + ".")
    if len(hits) > 20:
        print(f"  ... {len(hits) - 20} more; narrow the query.")
    M.save()
    return 0


def cmd_advance(M, a):
    need_prog(M)
    s = M.stage()
    rem = remaining(M, s)
    if rem:
        print("ADVANCE REFUSED: required units not resolved: " + "; ".join(f"{label(M.units[u])} ({M.status(u)})"
                                                                         for u in rem))
        return 1
    i = M.stage_index(s["id"])
    if i + 1 >= len(M.stages):
        print("ADVANCE: this is the last stage. The module's plan is complete.")
        return 0
    n = M.stages[i + 1]
    if not n.get("ready", True):
        print(f"ADVANCE REFUSED: the next stage {n['id']} ({n['title']}) is NOT AUTHORED: {n.get('todo', '')} "
              f"Stop and tell Joe; never improvise it.")
        return 1
    gate = [x for x in n.get("needs", []) if not M.part_done(x)]
    if gate:
        print(f"ADVANCE REFUSED: {n['id']} also needs {', '.join(gate)} complete first.")
        return 1
    t = iso(now())
    M.prog["stage"] = n["id"]
    M.save()
    M.append({"at": t, "op": "advance", "from": s["id"], "to": n["id"], "milestone": s.get("milestone")})
    print(f"ADVANCED {s['id']} -> {n['id']}: {n['title']}")
    if s.get("milestone"):
        print(f"MILESTONE: {s['milestone']} (run the §6-decies LEVEL UP gate)")
    for b in M.branches:
        if b["opens_after"] == s["id"]:
            print(f"BRANCH OPEN: {b['id']}: {b['title']} ({'optional' if b.get('optional') else 'required'})")
    return 0


def cmd_table(M, a):
    need_prog(M)
    s = M.stage()
    live = M.live_units()
    open_ = ("untouched", "seen")
    arc = [u for u in s.get("required", []) if M.status(u) in open_]

    def options(refs, skip):
        """Events one by one; keyed areas folded into their place (a group letter), so a firing surfaces a place
        or a happening, never a single room."""
        out = []
        for u in M.expand(refs):
            if u in skip or M.status(u) not in open_:
                continue
            d = M.units[u]
            out.append(d["group"] if d["kind"] == "area" else u)
        return sorted(set(out))

    beat = options(s.get("live", []) + s.get("required", []), set(arc))
    side = sorted({o for b in M.open_branches() if not M.complete(b)
                   for o in options(b.get("live", []) + b.get("required", []), set())})
    bands = [("1-8", "advance the arc", arc), ("9-16", "flesh out the stage", beat),
             ("17-19", "an open branch surfaces", side)]
    print(f"LIVE TABLE · stage {s['id']} · read the band, then that band's pick. A band with nothing left reads as "
          f"1-8; if that is empty too, as 20.")
    call = ["band:d20"]
    for rng, name, rows in bands:
        if len(rows) >= 2:
            tag = {"1-8": "arc", "9-16": "beat", "17-19": "side"}[rng]
            call.append(f"{tag}:pick[{'|'.join(rows)}]")
            print(f"  {rng} {name}: {len(rows)} options (pick `{tag}`)")
        elif len(rows) == 1:
            r = rows[0]
            print(f"  {rng} {name}: only " + (label(M.units[r]) if r in M.units else f"{r} {M.groups[r]['name']}"))
        else:
            print(f"  {rng} {name}: none left")
    print("  20 wild card: the generic §6 wildcard intersection")
    print("ENGINE CALL (paste whole): roll.py " + " ".join(call))
    print("A group letter means a place with module content the party has not experienced: bring them a reason "
          "to go there (`map.py here <letter>` when they do).")
    print("The result is a situation with a way in, never a script: surface it, yield to the players, and `mark` "
          "only what then happens at the table.")
    M.save()
    return 0


def cmd_drift(M, a):
    need_prog(M)
    print(M.drift_line())
    M.save()
    return 0


def cmd_log(M, a):
    p = M.root / "coverage.jsonl"
    lines = p.read_text().splitlines() if p.exists() else []
    for ln in lines[-a.n:]:
        r = json.loads(ln)
        print(f"  {r.get('at', '')[:16]} {r.get('op')} " + " ".join(
            f"{k}={r[k]}" for k in ("unit", "previous", "status", "from", "to", "frm", "date", "location", "session", "evidence", "why")
            if k in r))
    return 0


def cmd_settings(M, a):
    got, ignored, src = read_settings(M)
    print(settings_line(M))
    for k, vals in SETTING_VALUES.items():
        print(f"  {k}: {got[k]}" + ("" if got[k] != SETTING_DEFAULTS[k] else "  (default)") + f"   [allowed: {', '.join(vals)}]")
    if got["bosses"]:
        print("  bosses: " + "; ".join(got["bosses"]) + ("" if got["encounters"] == "budgeted" else
                                                          "  (inert: encounters is not budgeted)"))
    if ignored:
        print("  IGNORED (not a setting or not an allowed value; they change nothing): " + "; ".join(ignored))
    return 0


def day_log(M, op, **kw):
    M.append(dict({"at": iso(now()), "op": op, "session": M.prog.get("session")}, **kw))


def cmd_day(M, a):
    args = list(a.args)
    if args and re.fullmatch(r"\+\d+", args[0]):
        args = ["add", args[0][1:]] + args[1:]
    verb = args[0] if args else "show"
    rest = args[1:]
    if verb == "init":
        need_prog(M)
        if (M.root / "calendar.json").exists() and not a.force:
            print("DAY INIT REFUSED: module/calendar.json already exists. --force only to start the count over.")
            return 1
        if not (M.root / "calendar.json").exists() or a.calendar:
            if a.calendar not in CALENDARS:
                print(f"DAY INIT REFUSED: --calendar {sorted(CALENDARS)} (or write module/calendar.json by hand).")
                return 1
            base = CALENDARS[a.calendar]
            cfg = {"kind": a.calendar, "name": base["name"], "start": a.start or base["segments"][0]["name"] + " 1",
                   "segments": base["segments"]}
            try:
                Calendar(cfg)
            except ValueError as e:
                print(f"DAY INIT REFUSED: {e}")
                return 1
            (M.root / "calendar.json").write_text(json.dumps(cfg, indent=1) + "\n")
        cal = get_calendar(M)
        M.prog["day"] = a.day or 1
        M.save()
        day_log(M, "day-init", day=M.prog["day"], date=cal.text(M.prog["day"]))
        print(f"DAY INIT: {cal.cfg.get('name', 'calendar')}, start {cal.cfg['start']}. {cal.line(M.prog['day'])}")
        return 0
    cal = need_cal(M)
    cur = M.prog["day"]
    if verb == "show":
        print(cal.line(cur))
    elif verb == "add":
        if not rest or not rest[0].isdigit() or int(rest[0]) < 1:
            print("DAY ADD REFUSED: give a whole number of days, 1 or more (`map.py day add 1 --why \"...\"`).")
            return 1
        if not a.why or len(a.why.strip()) < 4:
            print("DAY ADD REFUSED: --why must name what moved the calendar (the running clock, a TIME SKIP, or a "
                  "downtime the players declared). Real time never does.")
            return 1
        n = int(rest[0])
        M.prog["day"] = cur + n
        M.save()
        day_log(M, "day", frm=cur, to=cur + n, why=a.why.strip(), date=cal.text(cur + n))
        print(cal.line(cur + n) + f" (+{n} from Day {cur}: {a.why.strip()})")
        if n > 14:
            print("NOTE: more than 14 days in one move. Only a TIME SKIP block (§5) or Fast Travel (§5-ter) carries "
                  "that, and each has its own cap.")
    elif verb == "set":
        if not rest or not rest[0].isdigit() or int(rest[0]) < 1:
            print("DAY SET REFUSED: give a day number, 1 or more.")
            return 1
        n = int(rest[0])
        if not a.why or len(a.why.strip()) < 4:
            print("DAY SET REFUSED: --why must say why the number changes.")
            return 1
        if n < cur and not a.correct:
            print(f"DAY SET REFUSED: Day {n} is before Day {cur}. The calendar only moves forward; a real mistake "
                  f"needs --correct.")
            return 1
        M.prog["day"] = n
        M.save()
        day_log(M, "day", frm=cur, to=n, why=a.why.strip(), date=cal.text(n), corrected=bool(a.correct))
        print(cal.line(n) + f" (set from Day {cur}: {a.why.strip()})")
    elif verb == "on":
        if not rest or not rest[0].isdigit() or int(rest[0]) < 1:
            print("DAY ON: give a day number.")
            return 1
        print(cal.line(int(rest[0])))
    elif verb == "when":
        if not rest:
            print("DAY WHEN: give a date, for example \"Midsummer\" or \"Eleasis 10\".")
            return 1
        try:
            d = cal.when(cur, " ".join(rest))
        except ValueError as e:
            print(f"DAY WHEN: {e}")
            return 1
        print(f"{' '.join(rest)}: " + cal.line(d) + (" (today)" if d == cur else f" (in {d - cur} days)"))
    else:
        print(f"DAY: unknown verb '{verb}' (init, add, set, on, when; none shows the date).")
        return 1
    return 0


def stamp(M):
    body = {"stage": M.prog["stage"], "coverage": M.prog["coverage"]}
    if "day" in M.prog:
        body["day"] = M.prog["day"]
    blob = json.dumps(body, sort_keys=True)
    day = f" day={M.prog['day']}" if "day" in M.prog else ""
    return (f"stage={M.prog['stage']} units={len(M.prog['coverage'])}{day} "
            f"hash={hashlib.sha256(blob.encode()).hexdigest()[:12]}")


def cmd_verify(M, a):
    need_prog(M)
    st = stamp(M)
    if a.expect:
        want = re.search(r"hash=([0-9a-f]+)", a.expect)
        got = re.search(r"hash=([0-9a-f]+)", st).group(1)
        if want and want.group(1) != got:
            print(f"MAP MISMATCH: save expects {a.expect}, found {st}. STOP and reconcile before play.")
            return 1
    M.save()
    print(f"MAP OK {st}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default="module", help="the campaign's module/ directory (default ./module)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init"); p.add_argument("--session", type=int); p.add_argument("--force", action="store_true")
    p.set_defaults(f=cmd_init)
    p = sub.add_parser("session"); p.add_argument("n", type=int); p.set_defaults(f=cmd_session)
    sub.add_parser("card").set_defaults(f=cmd_card)
    sub.add_parser("stage").set_defaults(f=cmd_stage)
    p = sub.add_parser("here"); p.add_argument("place"); p.set_defaults(f=cmd_here)
    p = sub.add_parser("mark"); p.add_argument("unit"); p.add_argument("status", choices=STATUSES)
    p.add_argument("--evidence", required=True); p.add_argument("--approved-by"); p.add_argument("--correct")
    p.set_defaults(f=cmd_mark)
    p = sub.add_parser("check"); p.add_argument("query"); p.set_defaults(f=cmd_check)
    sub.add_parser("advance").set_defaults(f=cmd_advance)
    sub.add_parser("table").set_defaults(f=cmd_table)
    sub.add_parser("drift").set_defaults(f=cmd_drift)
    p = sub.add_parser("log"); p.add_argument("n", nargs="?", type=int, default=10); p.set_defaults(f=cmd_log)
    p = sub.add_parser("verify"); p.add_argument("--expect"); p.set_defaults(f=cmd_verify)
    sub.add_parser("settings").set_defaults(f=cmd_settings)
    p = sub.add_parser("day"); p.add_argument("args", nargs="*"); p.add_argument("--why")
    p.add_argument("--calendar"); p.add_argument("--start"); p.add_argument("--day", type=int)
    p.add_argument("--force", action="store_true"); p.add_argument("--correct", action="store_true")
    p.set_defaults(f=cmd_day)
    a = ap.parse_args()
    M = Module(a.dir)
    sys.exit(a.f(M, a) or 0)


if __name__ == "__main__":
    main()
