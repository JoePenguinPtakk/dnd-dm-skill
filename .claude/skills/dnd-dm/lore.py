#!/usr/bin/env python3
"""lore.py: the campaign's cast register and the weights for the CAST ENGINE.

The master prompt's §6-terdecies (docs/MASTER_PROMPT_supplement_cast-engine.md)
says what to do. This tool does the bookkeeping and the arithmetic so the DM
never estimates a weight, a count, or a lookup. It rolls no dice. Every
`pick[...]` string it prints goes into one roll.py call, as written.

Lore lives in <campaign repo>/lore/ :
    INDEX.md         one line per entity (rebuilt by `index`)
    config.json      weights and caps (defaults below; a campaign may retune)
    state.json       session number, NEW-NPC counters, recent appearances
    npcs/ places/ items/ factions/ threads/   one markdown file per entity
    events/S<nn>.md  one line per event

Entity files start with a front-matter block (a small YAML subset):
    ---
    type: npc            npc | place | item | faction | thread | npc-group
    name: Dorra
    aliases: [Dorravel, the street-kid leader]
    roles: [scout leader, street kid]
    status: alive
    where: [trollskull-manor, dock-ward]
    affinity: 10
    want: free text, empty when none
    fear: free text
    ties:
      - leader-of: korva
    first_seen: 12
    last_seen: 15
    named: yes           (no = a role only, no name rolled yet)
    ---
    body text

Usage:  lore.py [--lore DIR] <command> ...      (python3, standard library only)
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import sys
from pathlib import Path

TYPES = {"npc": "npcs", "npc-group": "npcs", "place": "places", "item": "items",
         "faction": "factions", "thread": "threads"}
LIST_KEYS = {"aliases", "roles", "where", "ties", "members"}
DIRS = ["npcs", "places", "items", "factions", "threads", "events"]

DEFAULT_CONFIG = {
    # who-roll: known + unnamed + new. Rule: known >= new, always.
    "who_weights": {"known": 5, "unnamed": 3, "new": 2},
    "cap_session": 10,       # new named NPCs per session (Joe, 2026-10-13)
    "cap_encounter": 2,      # new named NPCs per encounter
    "neglect_sessions": 3,   # unseen this long earns a return bonus
    "recent_memory": 12,
    "max_share": 0.90,       # the dice engine refuses an outcome above 90%
    "ignore_speakers": [],   # audit: PC names and test posts, set per campaign
    # callbacks: people, threads and items from elsewhere (not the party's current region)
    "callback_max_session": 1,     # at most this many callbacks in one session
    "callback_gap_sessions": 2,    # at least this many sessions between callbacks
    "callback_npc_cooldown": 6,    # the same entity is not called back again for this long
    "near": {},                    # region -> [regions close enough for an in-person visit]
}

INVERSE = {"employs": "works-for", "works-for": "employs", "leader-of": "follows",
           "follows": "leader-of", "patron-of": "client-of", "client-of": "patron-of",
           "owes": "owed-by", "owed-by": "owes", "parent-of": "child-of",
           "child-of": "parent-of", "rival": "rival", "kin": "kin", "lover": "lover",
           "informant-for": "handler-of", "handler-of": "informant-for",
           "neighbor": "neighbor", "friend": "friend", "ally": "ally", "enemy": "enemy"}

# act table for a beat between two tied NPCs: kind of act -> base weight
ACTS = ["nothing_new", "aid", "trade", "gossip", "quarrel", "favor_asked",
        "betrayal", "courtship", "seeks_the_party"]
ACT_BASE = {"nothing_new": 3, "aid": 1, "trade": 1, "gossip": 2, "quarrel": 1,
            "favor_asked": 1, "betrayal": 1, "courtship": 1, "seeks_the_party": 1}
ACT_BY_TIE = {
    "rival": {"quarrel": 3, "betrayal": 2},
    "enemy": {"quarrel": 3, "betrayal": 2},
    "owes": {"favor_asked": 3},
    "owed-by": {"favor_asked": 2},
    "kin": {"aid": 2, "favor_asked": 1},
    "parent-of": {"aid": 2}, "child-of": {"aid": 2},
    "lover": {"courtship": 3, "quarrel": 1},
    "employs": {"trade": 2}, "works-for": {"trade": 2},
    "leader-of": {"trade": 1, "aid": 1}, "follows": {"aid": 1},
    "patron-of": {"favor_asked": 2}, "client-of": {"favor_asked": 2},
    "informant-for": {"gossip": 3}, "handler-of": {"gossip": 3},
    "friend": {"aid": 2, "gossip": 1}, "ally": {"aid": 2},
    "neighbor": {"gossip": 2, "trade": 1},
}
VIS_TEXT = "vis d6: 1-3 hidden until the party meets it | 4-5 a rumor or trace is available if they look | 6 openly known"

STOP_SPEAKERS = {"HP", "AC", "DM", "NEEDED", "CHOICE", "VITALS", "ROLL", "ROLL GATE", "EXPOSITION",
                 "FORK", "STEP", "ENC", "LOCATION", "QUEST", "NPCS PRESENT", "SESSION ROSTER",
                 "PENDING ROLLS", "NOTE", "OOC", "RAW", "DC", "CHECK", "CONSEQUENCE", "SITUATION",
                 "BASTION TURN", "TIME SKIP", "LEVEL UP", "XP AWARD", "SPELL CAST", "DUNGEON",
                 "DM ROLLS", "DM ROLLS THIS RESPONSE", "CHAIN", "NEMESIS CHAIN", "SAVED", "RESULT"}


STOP_PREFIX = {"CHECK", "Still", "Voice", "Voices", "Arc", "ROLL", "NEEDED", "LOOP", "XP", "Roy's"}


# ---------------------------------------------------------------- parsing

def split_list(s):
    """Split 'a, b (c, d), e' on commas outside parentheses."""
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def parse(text):
    if not text.startswith("---"):
        return {}, text
    lines = text.split("\n")
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text
    fm, key = {}, None
    for ln in lines[1:end]:
        if not ln.strip() or ln.lstrip().startswith("#"):
            continue
        if ln.lstrip().startswith("- ") and key is not None:
            if not isinstance(fm.get(key), list):
                fm[key] = []
            fm[key].append(ln.lstrip()[2:].strip())
            continue
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", ln)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if val == "":
            fm[key] = [] if key in LIST_KEYS else ""
        elif val.startswith("[") and val.endswith("]"):
            fm[key] = split_list(val[1:-1])
        else:
            fm[key] = val.strip("\"'")
    return fm, "\n".join(lines[end + 1:])


def dump(fm, body):
    out = ["---"]
    for k, v in fm.items():
        if isinstance(v, list):
            if k == "ties":
                out.append(f"{k}:")
                out += [f"  - {x}" for x in v]
            else:
                out.append(f"{k}: [{', '.join(v)}]")
        else:
            out.append(f"{k}: {v}")
    out.append("---")
    return "\n".join(out) + "\n" + body.lstrip("\n")


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


# ---------------------------------------------------------------- store

class Lore:
    def __init__(self, root):
        self.root = Path(root)
        self.cfg = dict(DEFAULT_CONFIG)
        p = self.root / "config.json"
        if p.exists():
            self.cfg.update(json.loads(p.read_text()))
        sp = self.root / "state.json"
        self.state = json.loads(sp.read_text()) if sp.exists() else \
            {"session": 0, "new_npc": 0, "encounter_new": 0, "recent": [],
             "region": "", "callbacks_this_session": 0, "last_callback_session": -99}

    def save_state(self):
        (self.root / "state.json").write_text(json.dumps(self.state, indent=1) + "\n")

    def files(self):
        for d in DIRS[:-1]:
            for p in sorted((self.root / d).glob("*.md")):
                yield p

    def load_all(self):
        ents = {}
        for p in self.files():
            fm, body = parse(p.read_text())
            fm.setdefault("type", "npc")
            ents[p.stem] = {"slug": p.stem, "path": p, "fm": fm, "body": body}
        return ents

    def num(self, fm, key, default=0):
        try:
            return int(str(fm.get(key, default)).strip())
        except ValueError:
            return default

    def ties_of(self, fm):
        out = []
        for t in fm.get("ties", []) or []:
            if ":" in t:
                k, v = t.split(":", 1)
                out.append((k.strip(), v.strip()))
        return out


def is_npc(e):
    return e["fm"].get("type") in ("npc",)


def alive(e):
    return str(e["fm"].get("status", "alive")).lower().startswith(("alive", "unknown", "active"))


def region_of(L):
    return str(L.state.get("region", "")).lower()


def is_sealed(e):
    return str(e["fm"].get("sealed", "")).lower() == "yes"


def is_local(L, e):
    """Local = the party's current region, or no home recorded."""
    r, home = region_of(L), str(e["fm"].get("home", "")).lower()
    return (not r) or (not home) or home == r


def callback_ok(e):
    return str(e["fm"].get("callback", "yes")).lower() != "no" and not is_sealed(e)


def where_of(e):
    return [w.strip().lower() for w in e["fm"].get("where", []) or []]


def terms_of(e):
    fm = e["fm"]
    return [fm.get("name", e["slug"])] + (fm.get("aliases", []) or [])


def role_match(e, roles):
    hay = " ".join((e["fm"].get("roles", []) or []) + (e["fm"].get("aliases", []) or [])).lower()
    return any(r.strip().lower() in hay for r in roles if r.strip())


def cap_share(weights, max_share):
    """Lower the heaviest weights until no outcome exceeds max_share. Weights stay >= 1."""
    w = dict(weights)
    for _ in range(200):
        tot = sum(w.values())
        top = max(w, key=w.get)
        if len(w) < 2 or w[top] / tot <= max_share or w[top] <= 1:
            break
        w[top] -= 1
    return w


def pick_str(label, weights):
    return f"{label}:pick[" + "|".join(f"{k}={v}" for k, v in weights.items()) + "]"


# ---------------------------------------------------------------- candidates

def candidate_weights(L, ents, places, roles, exclude, types=("npc",), region_any=False):
    sess = L.state.get("session", 0)
    recent = L.state.get("recent", [])
    recent_set = set(recent)
    last3 = recent[-3:]
    out, relaxed = {}, False
    pool = [e for e in ents.values() if e["fm"].get("type") in types and alive(e)
            and e["slug"] not in exclude and not is_sealed(e)
            and (region_any or is_local(L, e))]
    if places and "any" not in places:
        pool = [e for e in pool if set(where_of(e)) & set(places)]
    if roles:
        r = [e for e in pool if role_match(e, roles)]
        if r:
            pool = r
        else:
            relaxed = True
    for e in pool:
        fm = e["fm"]
        w = 2
        if str(fm.get("want", "")).strip() and not str(fm.get("want", "")).lower().startswith("resolved"):
            w += 2
        if any(t in recent_set for _, t in L.ties_of(fm)):
            w += 2                                   # a tie to someone in play this session
        last = L.num(fm, "last_seen", 0)
        if sess and last and sess - last >= L.cfg["neglect_sessions"]:
            w += 2                                   # unseen for a while: a return is due
        if roles and role_match(e, roles):
            w += 1
        if e["slug"] in last3:
            w = max(1, w - 1)                        # just appeared
        out[e["slug"]] = w
    return out, relaxed


def callback_pool(L, ents):
    """Far (not in the current region), unsealed, off cooldown. Weight 1, +2 want, +1 tie to a local NPC."""
    sess = L.state.get("session", 0)
    out = {}
    for e in ents.values():
        fm = e["fm"]
        if fm.get("type") not in ("npc", "thread", "item") or is_local(L, e) or not callback_ok(e):
            continue
        if not str(fm.get("status", "alive")).lower().startswith(("alive", "unknown", "active", "open", "missing")):
            continue
        last = L.num(fm, "last_callback", -99)
        if sess - last < L.cfg["callback_npc_cooldown"]:
            continue
        w = 1
        if str(fm.get("want", "")).strip():
            w += 2
        if any(t in ents and is_local(L, ents[t]) and alive(ents[t]) for _, t in L.ties_of(fm)):
            w += 1
        out[e["slug"]] = w
    return out


def callback_budget_ok(L):
    sess = L.state.get("session", 0)
    return (L.state.get("callbacks_this_session", 0) < L.cfg["callback_max_session"]
            and sess - L.state.get("last_callback_session", -99) >= L.cfg["callback_gap_sessions"])


# ---------------------------------------------------------------- commands

def cmd_init(L, a):
    for d in DIRS:
        (L.root / d).mkdir(parents=True, exist_ok=True)
    if not (L.root / "config.json").exists():
        (L.root / "config.json").write_text(json.dumps(DEFAULT_CONFIG, indent=1) + "\n")
    if a.session is not None:
        L.state["session"] = a.session
    L.save_state()
    cmd_index(L, a)
    print(f"LORE INIT {L.root}")


def cmd_session(L, a):
    L.state.update({"session": a.n, "new_npc": 0, "encounter_new": 0, "recent": [], "callbacks_this_session": 0})
    L.save_state()
    print(f"LORE SESSION {a.n} started. NEW-NPC 0/{L.cfg['cap_session']}")


def cmd_encounter(L, a):
    L.state["encounter_new"] = 0
    L.save_state()
    print(f"LORE ENCOUNTER reset. NEW-NPC session {L.state['new_npc']}/{L.cfg['cap_session']}, encounter 0/{L.cfg['cap_encounter']}")


def cmd_budget(L, a):
    s, c = L.cfg["cap_session"], L.cfg["cap_encounter"]
    print(f"NEW-NPC session {L.state['new_npc']}/{s} · encounter {L.state['encounter_new']}/{c} · "
          f"region: {region_of(L) or 'unset'} · callbacks {L.state.get('callbacks_this_session', 0)}/{L.cfg['callback_max_session']}")


def cmd_region(L, a):
    if a.slug:
        L.state["region"] = a.slug.lower()
        L.save_state()
        event(L, f"REGION now {a.slug.lower()}", [])
    print(f"REGION {region_of(L) or 'unset'}")


def cmd_find(L, a):
    ents = L.load_all()
    terms = [t.lower() for t in a.terms]
    hits = []
    for e in ents.values():
        fm = e["fm"]
        head = " ".join(terms_of(e) + (fm.get("roles", []) or []) + [e["slug"]]).lower()
        full = (head + " " + e["body"].lower() + " " + " ".join(str(v) for v in fm.values() if isinstance(v, str)).lower())
        score = 0
        where = []
        for t in terms:
            if t in head:
                score += 3
                where.append("name/alias/role")
            elif t in full:
                score += 1
                where.append("text")
        if score:
            hits.append((score, e, sorted(set(where))))
    hits.sort(key=lambda x: -x[0])
    if not hits:
        print(f"NO MATCH for: {' '.join(a.terms)} (searched names, aliases, roles and text of {len(ents)} entities)")
        return 1
    for score, e, where in hits[:a.limit]:
        fm = e["fm"]
        flags = (" SEALED (never drawn, never resurfaced)" if is_sealed(e) else "") + \
                (f" [far: home {fm.get('home')}]" if not is_local(L, e) else "")
        print(f"{e['slug']} | {fm.get('type')} | {fm.get('name', e['slug'])} | {fm.get('status', '')}{flags} | "
              f"roles: {', '.join(fm.get('roles', []) or [])} | matched in: {', '.join(where)} | {e['path'].relative_to(L.root.parent)}")
    if len(hits) > a.limit:
        print(f"... {len(hits) - a.limit} more")
    return 0


def cmd_show(L, a):
    ents = L.load_all()
    e = ents.get(a.slug)
    if not e:
        print(f"NO SUCH ENTITY: {a.slug}")
        return 1
    print(e["path"].read_text())
    return 0


def build_index(L, ents):
    lines = [f"# LORE INDEX", "", "type | name | aliases | roles | status | home | where | flags | file", "---|---|---|---|---|---|---|---|---"]
    for slug in sorted(ents, key=lambda s: (ents[s]["fm"].get("type", ""), ents[s]["fm"].get("name", s).lower())):
        e = ents[slug]
        fm = e["fm"]
        rel = e["path"].relative_to(L.root)
        lines.append(" | ".join([
            fm.get("type", ""), fm.get("name", slug), "; ".join(fm.get("aliases", []) or []),
            "; ".join(fm.get("roles", []) or []), str(fm.get("status", "")), str(fm.get("home", "")),
            "; ".join(fm.get("where", []) or []), "SEALED" if is_sealed(e) else "", str(rel)]))
    return "\n".join(lines) + "\n"


def index_hash(text):
    body = "\n".join(l for l in text.split("\n") if not l.startswith("#"))
    return hashlib.sha256(body.encode()).hexdigest()[:8]


def cmd_index(L, a):
    ents = L.load_all()
    txt = build_index(L, ents)
    (L.root / "INDEX.md").write_text(txt)
    print(f"LORE INDEX entities={len(ents)} hash={index_hash(txt)}")


def cmd_verify(L, a):
    ents = L.load_all()
    txt = build_index(L, ents)
    h = index_hash(txt)
    cur = (L.root / "INDEX.md").read_text() if (L.root / "INDEX.md").exists() else ""
    stale = index_hash(cur) != h if cur else True
    line = f"LORE OK entities={len(ents)} hash={h}"
    if stale:
        print(f"LORE STALE: INDEX.md does not match the files (run `lore.py index`). Would be: entities={len(ents)} hash={h}")
        return 1
    if a.expect:
        n, _, eh = a.expect.partition(":")
        if int(n) != len(ents) or (eh and eh != h):
            print(f"LORE MISMATCH: save expects {a.expect}, found entities={len(ents)} hash={h}. STOP and reconcile before play.")
            return 1
    print(line)
    return 0


def cmd_candidates(L, a):
    ents = L.load_all()
    places = [p.strip().lower() for p in (a.place or "any").split(",")]
    roles = [r for r in (a.role or "").split(",") if r.strip()]
    exclude = set((a.exclude or "").split(","))
    w, relaxed = candidate_weights(L, ents, places, roles, exclude, region_any=(a.region == "any"))
    if not w:
        print("NO CANDIDATES (alive known NPCs matching the place). who-roll: known weight 0.")
        return 1
    w = cap_share(w, L.cfg["max_share"]) if len(w) > 1 else w
    for slug, wt in sorted(w.items(), key=lambda x: -x[1])[:a.limit]:
        fm = ents[slug]["fm"]
        print(f"{wt:2d}  {slug}: {fm.get('name', slug)} ({'; '.join(fm.get('roles', []) or [])}) last_seen S{fm.get('last_seen', '?')}")
    if relaxed:
        print("(role filter matched nobody, so the list is by place alone)")
    if len(w) == 1:
        print("ONE CANDIDATE: no pick needed; the known branch is this NPC.")
    else:
        print(pick_str("cand", w))
    return 0


def cmd_who(L, a):
    ents = L.load_all()
    places = [p.strip().lower() for p in (a.place or "any").split(",")]
    roles = [r for r in (a.role or "").split(",") if r.strip()]
    w, relaxed = candidate_weights(L, ents, places, roles, set())
    ww = dict(L.cfg["who_weights"])
    cbw = ww.pop("callback", 1)
    notes = []
    cbpool = callback_pool(L, ents)
    if cbpool and callback_budget_ok(L):
        ww["callback"] = cbw
    elif cbpool:
        notes.append("callback budget spent or in cooldown: callback removed")
    if not w:
        ww["known"] = 0
        notes.append("no known candidate fits: known removed")
    capped = L.state["new_npc"] >= L.cfg["cap_session"] or L.state["encounter_new"] >= L.cfg["cap_encounter"]
    if capped:
        ww["new"] = 0
        notes.append(f"NEW-NPC cap reached ({L.state['new_npc']}/{L.cfg['cap_session']} session, "
                     f"{L.state['encounter_new']}/{L.cfg['cap_encounter']} encounter): new removed")
    if ww.get("known") and ww["known"] < ww.get("new", 0):
        ww["known"] = ww["new"]
        notes.append("known raised to equal new (rule: reuse is never rarer than new)")
    ww = {k: v for k, v in ww.items() if v > 0}
    if len(ww) < 2:
        only = next(iter(ww)) if ww else "unnamed"
        print(f"WHO: only one outcome is open ({only}); no roll needed. " + "; ".join(notes))
        return 0
    ww = cap_share(ww, L.cfg["max_share"])
    print(pick_str("who", ww))
    for n in notes:
        print("note:", n)
    print(f"known candidates here: {len(w)}" + (f" · far callbacks eligible: {len(cbpool)}" if "callback" in ww else ""))
    if "callback" in ww:
        print("if who=callback: lore.py callbacks")
    return 0


def cmd_callbacks(L, a):
    ents = L.load_all()
    if a.via:
        e = ents.get(a.via)
        if not e:
            print(f"NO SUCH ENTITY: {a.via}")
            return 1
        via = {"rumor": 4, "letter": 3, "traveler_with_news": 2}
        near = [x.lower() for x in L.cfg.get("near", {}).get(region_of(L), [])]
        mobile = str(e["fm"].get("mobile", "")).lower() == "yes"
        homeok = str(e["fm"].get("home", "")).lower() in near
        if mobile or homeok:
            via["in_person"] = 1
        print(pick_str("via", via))
        print("A far person arrives by a mechanism, never by teleporting." + ("" if "in_person" in via else " In person is off the table: not mobile, home not near."))
        return 0
    pool = callback_pool(L, ents)
    print(f"REGION {region_of(L) or 'unset'} · callbacks this session {L.state.get('callbacks_this_session', 0)}/{L.cfg['callback_max_session']}"
          f" · gap rule {L.cfg['callback_gap_sessions']} sessions")
    if not pool:
        print("NO CALLBACK CANDIDATES (everyone far is sealed, dead, on cooldown, or opted out).")
        return 1
    if not callback_budget_ok(L):
        print("BUDGET SPENT or in the gap: no callback now.")
        return 1
    w = cap_share(pool, L.cfg["max_share"]) if len(pool) > 1 else pool
    for slug, wt in sorted(w.items(), key=lambda x: -x[1])[:a.limit]:
        fm = ents[slug]["fm"]
        print(f"{wt:2d}  {slug}: {fm.get('name', slug)} ({'; '.join(fm.get('roles', []) or [])}) home {fm.get('home')} last_seen S{fm.get('last_seen', '?')}")
    print(pick_str("cb", w) if len(w) > 1 else "ONE CANDIDATE: no pick needed.")
    print("then, for the person drawn: lore.py callbacks --via <slug>   (how the callback reaches the party)")
    print("SIZE RULE: a callback is small (a letter, a name in conversation, news from a trader, an object arriving). It does not start a quest by itself; it may offer a hook the party is free to ignore.")
    print("After using it: lore.py callback-done <slug> --via <how>")
    return 0


def cmd_callbackdone(L, a):
    ents = L.load_all()
    e = ents.get(a.slug)
    if not e:
        print(f"NO SUCH ENTITY: {a.slug}")
        return 1
    sess = L.state.get("session", 0)
    e["fm"]["last_callback"] = str(sess)
    body = e["body"].rstrip("\n") + f"\n- S{sess}: CALLBACK ({a.via or 'unspecified'}). {a.note or ''}\n"
    write_entity(e, body=body)
    L.state["callbacks_this_session"] = L.state.get("callbacks_this_session", 0) + 1
    L.state["last_callback_session"] = sess
    L.save_state()
    event(L, f"CALLBACK {a.slug} via {a.via or 'unspecified'}", [a.slug])
    print(f"CALLBACK recorded. {L.state['callbacks_this_session']}/{L.cfg['callback_max_session']} this session.")
    return 0


def cmd_beat(L, a):
    ents = L.load_all()
    e = ents.get(a.slug)
    if not e:
        print(f"NO SUCH ENTITY: {a.slug}")
        return 1
    fm = e["fm"]
    aff = L.num(fm, "affinity", 0)
    w = {"ordinary": 6}
    if str(fm.get("want", "")).strip():
        w["own_want"] = 3
    if L.ties_of(fm):
        w["tie"] = 3
        w["gossip"] = 3
    else:
        w["gossip"] = 1
    w["asks_party"] = 2 + (1 if aff >= 0 else 0)
    w["offers_party"] = 2 + (3 if aff >= 11 else 1 if aff >= 1 else 0)
    w["friction"] = 1 + (3 if aff <= -5 else 0)
    w["trouble_at_their_door"] = 1
    w = cap_share(w, L.cfg["max_share"])
    print(pick_str("beat", w))
    ties = L.ties_of(fm)
    if ties:
        print("if beat=tie or gossip, pick which tie next:", pick_str("tie", {f"{k}:{t}": 1 for k, t in ties}) if len(ties) > 1 else f"only tie: {ties[0][0]}:{ties[0][1]}")
    return 0


def cmd_castbeat(L, a):
    ents = L.load_all()
    if not a.slug:
        w, _ = candidate_weights(L, ents, ["any"], [], set(a.exclude.split(",")) if a.exclude else set())
        w = {s: x for s, x in w.items() if L.ties_of(ents[s]["fm"])}
        if len(w) < 2:
            print("Fewer than two known NPCs with ties: no cast beat available.")
            return 1
        w = cap_share(w, L.cfg["max_share"])
        print(pick_str("npc", w))
        print("then: lore.py cast-beat <slug>")
        return 0
    e = ents.get(a.slug)
    if not e:
        print(f"NO SUCH ENTITY: {a.slug}")
        return 1
    ties = L.ties_of(e["fm"])
    if not ties:
        print(f"{a.slug} has no ties.")
        return 1
    if len(ties) > 1:
        print(pick_str("tie", {f"{k}:{t}": 1 for k, t in ties}))
    else:
        print(f"only tie: {ties[0][0]}:{ties[0][1]}")
    acts = dict(ACT_BASE)
    for k, _ in ties:
        for act, bonus in ACT_BY_TIE.get(k, {}).items():
            acts[act] += bonus
    acts = cap_share(acts, L.cfg["max_share"])
    print(pick_str("act", acts))
    print("vis:d6")
    print(VIS_TEXT)
    print("Bounds: local scale, the NPCs' own circle. The cause must trace to a recorded want, fear or tie. No multi-session arc yet.")
    return 0


def cmd_add(L, a):
    ents = L.load_all()
    slug = a.slug or slugify(a.name)
    typ = a.type
    named = not a.unnamed
    # structural lookup-before-create: an exact name or alias match refuses
    names = {t.lower(): e["slug"] for e in ents.values() for t in terms_of(e) if t}
    clash = [names[t.lower()] for t in [a.name] + (a.aliases.split(",") if a.aliases else []) if t.strip().lower() in names]
    if clash and not a.force:
        print(f"REFUSED: {a.name!r} already exists as {sorted(set(clash))}. Use `lore.py touch`. (--force only for a true namesake, and say why in the event.)")
        return 1
    dest = L.root / TYPES.get(typ, "npcs") / f"{slug}.md"
    if dest.exists():
        print(f"REFUSED: {dest} exists.")
        return 1
    counted = typ == "npc" and named and not a.seed
    if counted and not a.override:
        if L.state["new_npc"] >= L.cfg["cap_session"]:
            print(f"REFUSED: NEW-NPC session cap {L.state['new_npc']}/{L.cfg['cap_session']} reached. Use an unnamed role or a known NPC. (--override \"<reason>\" only on Joe's word.)")
            return 1
        if L.state["encounter_new"] >= L.cfg["cap_encounter"]:
            print(f"REFUSED: NEW-NPC encounter cap {L.state['encounter_new']}/{L.cfg['cap_encounter']} reached. Use an unnamed role or a known NPC.")
            return 1
    sess = L.state.get("session", 0)
    fm = {"type": typ, "name": a.name}
    fm["aliases"] = [x.strip() for x in a.aliases.split(",")] if a.aliases else []
    fm["roles"] = [x.strip() for x in a.roles.split(",")] if a.roles else []
    fm["status"] = "alive" if typ == "npc" else "active"
    fm["where"] = [x.strip().lower() for x in a.place.split(",")] if a.place else []
    if typ == "npc":
        fm["named"] = "yes" if named else "no"
        fm["affinity"] = str(a.affinity)
        fm["want"] = a.want or ""
        fm["fear"] = a.fear or ""
        fm["ties"] = []
    for kv in a.set or []:
        k, _, v = kv.partition("=")
        fm[k.strip()] = v.strip()
    fm["first_seen"] = str(a.first_seen if a.first_seen is not None else sess)
    fm["last_seen"] = str(a.last_seen if a.last_seen is not None else sess)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(dump(fm, (a.note or "") + "\n"))
    if counted:
        L.state["new_npc"] += 1
        L.state["encounter_new"] += 1
    if not a.seed:
        L.state["recent"] = (L.state.get("recent", []) + [slug])[-L.cfg["recent_memory"]:]
    L.save_state()
    event(L, f"{'SEEDED' if a.seed else 'NEW'} {typ} {slug}: {a.name}" + (f" (override: {a.override})" if a.override else ""), [slug])
    cmd_index(L, a)
    if counted:
        print(f"ADDED {slug}. NEW-NPC {L.state['new_npc']}/{L.cfg['cap_session']} · encounter {L.state['encounter_new']}/{L.cfg['cap_encounter']}")
    else:
        why = "seeded history" if a.seed else ("unnamed role" if typ == "npc" else typ)
        print(f"ADDED {slug} (not counted: {why}).")
    return 0


def write_entity(e, fm=None, body=None):
    fm = fm if fm is not None else e["fm"]
    body = body if body is not None else e["body"]
    e["path"].write_text(dump(fm, body))


def cmd_touch(L, a):
    ents = L.load_all()
    e = ents.get(a.slug)
    if not e:
        print(f"NO SUCH ENTITY: {a.slug}. Lookup first: lore.py find <name or role>.")
        return 1
    e["fm"]["last_seen"] = str(L.state.get("session", 0))
    body = e["body"]
    if a.note:
        body = body.rstrip("\n") + f"\n- S{L.state.get('session', 0)}: {a.note}\n"
    write_entity(e, body=body)
    L.state["recent"] = [s for s in L.state.get("recent", []) if s != a.slug] + [a.slug]
    L.state["recent"] = L.state["recent"][-L.cfg["recent_memory"]:]
    L.save_state()
    if a.note:
        event(L, f"{a.slug}: {a.note}", [a.slug])
    print(f"TOUCHED {a.slug} S{L.state.get('session', 0)}")
    return 0


def cmd_name(L, a):
    """Give an unnamed role its name (counts toward NEW-NPC)."""
    ents = L.load_all()
    e = ents.get(a.slug)
    if not e:
        print(f"NO SUCH ENTITY: {a.slug}")
        return 1
    if e["fm"].get("named") == "yes":
        print(f"{a.slug} already has a name.")
        return 1
    if not a.override and (L.state["new_npc"] >= L.cfg["cap_session"] or L.state["encounter_new"] >= L.cfg["cap_encounter"]):
        print("REFUSED: NEW-NPC cap reached. The role stays unnamed.")
        return 1
    old = e["fm"].get("name", a.slug)
    e["fm"]["name"] = a.name
    e["fm"]["named"] = "yes"
    e["fm"].setdefault("aliases", []).append(old)
    write_entity(e)
    L.state["new_npc"] += 1
    L.state["encounter_new"] += 1
    L.save_state()
    event(L, f"NAMED {a.slug}: {old} is {a.name}", [a.slug])
    cmd_index(L, a)
    print(f"NAMED {a.slug}. NEW-NPC {L.state['new_npc']}/{L.cfg['cap_session']}")
    return 0


def cmd_tie(L, a):
    ents = L.load_all()
    for s in (a.a, a.b):
        if s not in ents:
            print(f"NO SUCH ENTITY: {s}")
            return 1
    inv = INVERSE.get(a.kind, a.kind)
    for x, kind, y in ((a.a, a.kind, a.b), (a.b, inv, a.a)):
        fm = ents[x]["fm"]
        ties = fm.setdefault("ties", [])
        edge = f"{kind}: {y}"
        if edge not in ties:
            ties.append(edge)
        write_entity(ents[x], fm)
    event(L, f"TIE {a.a} {a.kind} {a.b}", [a.a, a.b])
    print(f"TIED {a.a} {a.kind} {a.b} (and {a.b} {inv} {a.a})")
    return 0


def cmd_status(L, a):
    ents = L.load_all()
    e = ents.get(a.slug)
    if not e:
        print(f"NO SUCH ENTITY: {a.slug}")
        return 1
    e["fm"]["status"] = a.value
    write_entity(e)
    event(L, f"STATUS {a.slug}: {a.value}", [a.slug])
    cmd_index(L, a)
    return 0


def event(L, text, who):
    d = L.root / "events"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"S{L.state.get('session', 0):02d}.md"
    if not p.exists():
        p.write_text(f"# Events, session {L.state.get('session', 0)}\n\n")
    with p.open("a") as f:
        f.write(f"- {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} | {text} | {', '.join(who)}\n")


def cmd_event(L, a):
    event(L, a.text, [x for x in (a.who or "").split(",") if x])
    for s in (a.who or "").split(","):
        if s:
            L.state["recent"] = [x for x in L.state.get("recent", []) if x != s] + [s]
    L.state["recent"] = L.state["recent"][-L.cfg["recent_memory"]:]
    L.save_state()
    print("EVENT logged.")
    return 0


def cmd_audit(L, a):
    ents = L.load_all()
    known = set()
    for e in ents.values():
        for t in terms_of(e):
            known.add(t.lower())
            known.add(t.lower().split()[0])
    ignore = {x.lower() for x in L.cfg.get("ignore_speakers", [])}   # PC names, test posts
    text = Path(a.logfile).read_text(errors="ignore")
    if a.logfile.endswith(".jsonl"):
        parts = []
        for ln in text.splitlines():
            try:
                parts.append(json.loads(ln).get("content", ""))
            except ValueError:
                pass
        text = "\n".join(parts)
    found, skipped = {}, 0
    for m in re.finditer(r"(?m)^\s*\**([A-Z][A-Za-z'’\-]+(?: [A-Za-z'’\-]+){0,2})\**:\s+\S", text):
        name = m.group(1).strip()
        first = name.split()[0]
        if (name.upper() in STOP_SPEAKERS or first in STOP_PREFIX or name.lower() in ignore
                or first.lower() in ignore or name.lower() in known or first.lower() in known
                or not all(w[0].isupper() for w in name.split()[:2])
                or re.match(r"^[A-Z]{2,}[a-z]", name) or name.upper() == name):
            skipped += 1                              # voice codes and ALL-CAPS labels
            continue
        found[name] = found.get(name, 0) + 1
    if not found:
        print(f"LORE AUDIT OK: every speaker in {a.logfile} has an entity.")
        return 0
    print(f"LORE AUDIT (heuristic: speaker prefixes; {skipped} codes/labels skipped). Review each: file it, or it is not a person.")
    for n, c in sorted(found.items(), key=lambda x: -x[1]):
        print(f"  {n} ({c} lines)")
    return 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lore", default=os.environ.get("LORE_DIR", "lore"))
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init"); p.add_argument("--session", type=int); p.set_defaults(f=cmd_init)
    p = sub.add_parser("session"); p.add_argument("n", type=int); p.set_defaults(f=cmd_session)
    p = sub.add_parser("encounter"); p.set_defaults(f=cmd_encounter)
    p = sub.add_parser("budget"); p.set_defaults(f=cmd_budget)
    p = sub.add_parser("find"); p.add_argument("terms", nargs="+"); p.add_argument("--limit", type=int, default=12); p.set_defaults(f=cmd_find)
    p = sub.add_parser("show"); p.add_argument("slug"); p.set_defaults(f=cmd_show)
    p = sub.add_parser("index"); p.set_defaults(f=cmd_index)
    p = sub.add_parser("verify"); p.add_argument("--expect"); p.set_defaults(f=cmd_verify)
    p = sub.add_parser("candidates"); p.add_argument("--place"); p.add_argument("--role"); p.add_argument("--exclude"); p.add_argument("--region"); p.add_argument("--limit", type=int, default=15); p.set_defaults(f=cmd_candidates)
    p = sub.add_parser("who"); p.add_argument("--place"); p.add_argument("--role"); p.set_defaults(f=cmd_who)
    p = sub.add_parser("beat"); p.add_argument("slug"); p.set_defaults(f=cmd_beat)
    p = sub.add_parser("region"); p.add_argument("slug", nargs="?"); p.set_defaults(f=cmd_region)
    p = sub.add_parser("callbacks"); p.add_argument("--limit", type=int, default=10); p.add_argument("--via"); p.set_defaults(f=cmd_callbacks)
    p = sub.add_parser("callback-done"); p.add_argument("slug"); p.add_argument("--via"); p.add_argument("--note"); p.set_defaults(f=cmd_callbackdone)
    p = sub.add_parser("cast-beat"); p.add_argument("slug", nargs="?"); p.add_argument("--exclude"); p.set_defaults(f=cmd_castbeat)
    p = sub.add_parser("add")
    p.add_argument("type", choices=sorted(TYPES)); p.add_argument("--name", required=True); p.add_argument("--slug")
    p.add_argument("--aliases"); p.add_argument("--roles"); p.add_argument("--place")
    p.add_argument("--unnamed", action="store_true"); p.add_argument("--affinity", type=int, default=0)
    p.add_argument("--want"); p.add_argument("--fear"); p.add_argument("--note")
    p.add_argument("--force", action="store_true"); p.add_argument("--override")
    p.add_argument("--seed", action="store_true", help="recovered history: not counted, not 'recent'")
    p.add_argument("--set", action="append", help="extra front-matter field, key=value (home, voice, block, tier, know, strat, sealed, callback, mobile, status)")
    p.add_argument("--first-seen", type=int, dest="first_seen"); p.add_argument("--last-seen", type=int, dest="last_seen")
    p.set_defaults(f=cmd_add)
    p = sub.add_parser("touch"); p.add_argument("slug"); p.add_argument("--note"); p.set_defaults(f=cmd_touch)
    p = sub.add_parser("name"); p.add_argument("slug"); p.add_argument("name"); p.add_argument("--override"); p.set_defaults(f=cmd_name)
    p = sub.add_parser("tie"); p.add_argument("a"); p.add_argument("kind"); p.add_argument("b"); p.set_defaults(f=cmd_tie)
    p = sub.add_parser("status"); p.add_argument("slug"); p.add_argument("value"); p.set_defaults(f=cmd_status)
    p = sub.add_parser("event"); p.add_argument("text"); p.add_argument("--who"); p.set_defaults(f=cmd_event)
    p = sub.add_parser("audit"); p.add_argument("logfile"); p.set_defaults(f=cmd_audit)

    a = ap.parse_args()
    L = Lore(a.lore)
    if a.cmd != "init" and not L.root.exists():
        print(f"No lore directory at {L.root}. Run `lore.py init` in the campaign repo.")
        sys.exit(2)
    sys.exit(a.f(L, a) or 0)


if __name__ == "__main__":
    main()
