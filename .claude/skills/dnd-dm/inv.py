#!/usr/bin/env python3
"""inv.py: coin holdings by container, with carrying capacity. The DM never estimates a weight or a total.

State: <campaign repo>/holdings/holdings.json  (containers)  and  holdings/transfers.jsonl  (every move, appended).
A container is a person (carries coin, has Strength) or a stash or wallet (sits at a place).
Rules used (SRD 5.2.1): carry maximum = Strength x 15 lb (Medium); fifty coins weigh one pound.
Over the carry maximum a creature can only drag or push, Speed 5 ft: this tool refuses to put more than
the carry maximum on a person. Hauls between places are cart work: it prints the carts needed under House
Rule 11 (10,000 gp per standard cart) and under RAW (draft horse, five times its capacity, cart 200 lb).

  inv.py [--dir DIR] show [container]
  inv.py load                         every person's load against capacity
  inv.py move FROM TO AMOUNT [DENOM] [--note TEXT] [--haul]
  inv.py verify
  inv.py init                         empty file
  inv.py items [container]            what each container holds, with weights
  inv.py add-item CONTAINER NAME [--qty N] (--lb EACH | --srd NAME | --negligible | --unweighed) [--note T] [--lore SLUG]
  inv.py drop-item CONTAINER NAME [--qty N] [--note T]
  inv.py move-item FROM TO NAME [--qty N] [--haul]
  inv.py weight NAME                  look up an SRD weight (weapons, armor, gear, tools)

Items: every item has a weight each. The SRD gives it where the item exists. A magic or homebrew item has no
SRD weight: it is either `--negligible` (rings, keys, letters, scrolls: counts 0, flagged) or `--unweighed`
(counts 0 and is listed as UNWEIGHED until Joe sets a weight with `set-lb`). The tool never invents a weight.
  inv.py set-lb CONTAINER NAME EACH   fix a weight later
"""
import argparse, datetime, hashlib, json, os, sys
from pathlib import Path

VAL = {"cp": 0.01, "sp": 0.1, "ep": 0.5, "gp": 1, "pp": 10}
DENOMS = ["pp", "gp", "ep", "sp", "cp"]
HR11_GP_PER_CART = 10000
RAW_CART_LB = 2700 - 200          # draft horse 540 lb x5, minus the cart's own 200 lb


def load(d):
    p = Path(d) / "holdings.json"
    return json.loads(p.read_text()) if p.exists() else {"containers": {}}


def save(d, h):
    (Path(d) / "holdings.json").write_text(json.dumps(h, indent=1) + "\n")


def coins(c):
    return sum(c.get("coin", {}).get(k, 0) for k in DENOMS)


def gp_value(c):
    return sum(c.get("coin", {}).get(k, 0) * VAL[k] for k in DENOMS)


def lb(c):
    return coins(c) / 50.0 + items_lb(c)


def capacity(c):
    return c.get("str", 0) * 15 if c["kind"] == "person" else None


SRD_DIR = Path(__file__).resolve().parent / "srd" / "text" / "07-equipment"


def _num(txt):
    t = txt.replace("½", ".5").replace("¼", ".25").replace("¾", ".75").strip()
    import re
    m = re.match(r"^(\d+(?:\.\d+)?)(?:\s*/\s*(\d+))?\s*lb", t)
    if not m:
        return None
    v = float(m.group(1))
    return v / float(m.group(2)) if m.group(2) else v


def srd_weight(name):
    """Weight in lb of one item named exactly NAME in the SRD equipment tables, else None."""
    q = name.strip().lower().replace("\u2019", "'")
    for f in sorted(SRD_DIR.glob("*.md")):
        for ln in f.read_text().splitlines():
            if not ln.startswith("|"):
                continue
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            lbs = [(_num(c), i) for i, c in enumerate(cells) if _num(c) is not None]
            if not lbs:
                continue
            names = ["" if ("to don" in c.lower() or "minute" in c.lower()) else c.lower().replace("\u2019", "'").split(" (")[0] for c in cells]
            if q in names:
                return lbs[0][0]
    # tools are headed "#### Name (cost)" with a "Weight: N lb." line below
    import re
    for ln_i, f in [(0, SRD_DIR / "04-tools.md")]:
        lines = f.read_text().splitlines()
        for i, ln in enumerate(lines):
            if ln.startswith("####") and ln[4:].strip().lower().replace("\u2019", "'").split(" (")[0] == q:
                for nxt in lines[i + 1:i + 7]:
                    m = re.search(r"Weight:\**\s*([\d½¼¾\./ ]+)\s*lb", nxt)
                    if m:
                        return _num(m.group(1) + " lb")
    return None


def items_lb(c):
    return sum((i.get("lb") or 0) * i.get("qty", 1) for i in c.get("items", []))


def unweighed(c):
    return [i["name"] for i in c.get("items", []) if i.get("lb") is None]


def fmt(c):
    parts = [f"{c['coin'][k]:,g} {k}" for k in DENOMS if c.get("coin", {}).get(k)]
    return ", ".join(parts) or "no coin"


def show_one(name, c):
    cap = capacity(c)
    n_items = sum(i.get("qty", 1) for i in c.get("items", []))
    line = f"{name} [{c['kind']}, {c.get('place', '?')}]: {fmt(c)} = {gp_value(c):,.1f} gp, {coins(c):,g} coins" + (f", {n_items} items" if n_items else "") + f", {lb(c):,.1f} lb"
    if cap:
        line += f" | carries {lb(c):.1f} of {cap} lb (STR {c['str']})" + ("  OVER CAPACITY" if lb(c) > cap else "")
    print(line)


def cmd_show(a, h):
    cs = h["containers"]
    if a.container:
        if a.container not in cs:
            print("NO SUCH CONTAINER", a.container); return 1
        show_one(a.container, cs[a.container]); return 0
    for n, c in cs.items():
        show_one(n, c)
    tot = sum(gp_value(c) for c in cs.values())
    print(f"TOTAL {tot:,.1f} gp, {sum(lb(c) for c in cs.values()):,.0f} lb of coin")
    return 0


def cmd_load(a, h):
    bad = 0
    for n, c in h["containers"].items():
        if c["kind"] == "person":
            cap = capacity(c)
            over = lb(c) > cap
            bad += over
            uw = unweighed(c)
            print(f"{c['owner']}: {lb(c):.1f} lb ({coins(c) / 50.0:.1f} coin + {items_lb(c):.1f} gear) / {cap} lb carry (STR {c['str']}), {cap - lb(c):.1f} lb free"
                  + ("  OVER" if over else "") + (f"  [UNWEIGHED: {len(uw)} items]" if uw else ""))
    return 1 if bad else 0


def parse_amount(amount, denom):
    return float(amount), denom or "gp"


def cmd_move(a, h):
    cs = h["containers"]
    for n in (a.src, a.dst):
        if n not in cs:
            print("NO SUCH CONTAINER", n); return 1
    amt, denom = parse_amount(a.amount, a.denom)
    if denom not in VAL:
        print("BAD DENOMINATION", denom); return 1
    src, dst = cs[a.src], cs[a.dst]
    # same-place rule: a person can fill from a stash only by being there (the move IS the visit)
    diff_place = src.get("place") != dst.get("place") and src["kind"] != "person" and dst["kind"] != "person"
    weight = amt / 50.0
    if dst["kind"] == "person":
        cap = capacity(dst)
        if lb(dst) + weight > cap + 1e-9:
            print(f"REFUSED: {dst['owner']} would carry {lb(dst) + weight:.1f} lb of coin; the carry maximum is {cap} lb (STR {dst['str']}). "
                  f"Most that fits: {max(0, cap - lb(dst)) * 50:,.0f} coins.")
            return 1
    if diff_place and not a.haul:
        gp = amt * VAL[denom]
        print(f"REFUSED: {a.src} is at '{src.get('place')}', {a.dst} is at '{dst.get('place')}'. Moving coin between places is a haul. "
              f"{weight:,.0f} lb = {-(-gp // HR11_GP_PER_CART):.0f} carts under House Rule 11, {-(-weight // RAW_CART_LB):.0f} under RAW. "
              f"Play the haul (route, guards, days), then rerun with --haul.")
        return 1
    if src.get("coin", {}).get(denom, 0) < amt:
        print(f"REFUSED: {a.src} holds {src.get('coin', {}).get(denom, 0):,g} {denom}, not {amt:,g}. Exact coins only; change is made in play.")
        return 1
    src["coin"][denom] -= amt
    dc = dst.setdefault("coin", {})
    dc[denom] = dc.get(denom, 0) + amt
    save(a.dir, h)
    rec = {"ts": datetime.datetime.now().isoformat(timespec="seconds"), "from": a.src, "to": a.dst,
           "amount": amt, "denom": denom, "lb": round(weight, 2), "haul": bool(a.haul), "note": a.note or ""}
    with (Path(a.dir) / "transfers.jsonl").open("a") as f:
        f.write(json.dumps(rec) + "\n")
    print(f"MOVED {amt:,g} {denom} ({weight:,.1f} lb) {a.src} -> {a.dst}")
    show_one(a.src, src); show_one(a.dst, dst)
    return 0


def cmd_verify(a, h):
    tot = sum(gp_value(c) for c in h["containers"].values())
    sig = hashlib.sha256(json.dumps(h, sort_keys=True).encode()).hexdigest()[:8]
    over = [c["owner"] for c in h["containers"].values() if c["kind"] == "person" and lb(c) > capacity(c)]
    uw = sum(len(unweighed(c)) for c in h["containers"].values())
    ni = sum(sum(i.get("qty", 1) for i in c.get("items", [])) for c in h["containers"].values())
    print(f"HOLDINGS OK containers={len(h['containers'])} total={tot:,.1f} gp items={ni} unweighed={uw} hash={sig}" if not over else f"HOLDINGS OVER CAPACITY: {over}")
    return 1 if over else 0


def find_item(c, name):
    for i in c.get("items", []):
        if i["name"].lower() == name.lower():
            return i
    return None


def cmd_items(a, h):
    for n, c in h["containers"].items():
        if a.container and n != a.container:
            continue
        its = c.get("items", [])
        if not its and a.container is None:
            continue
        print(f"{n} ({c['kind']}, {c.get('place')}): {lb(c):,.1f} lb total, {items_lb(c):,.1f} lb gear")
        for i in its:
            w = "UNWEIGHED" if i.get("lb") is None else f"{i['lb']:g} lb each = {i['lb'] * i.get('qty', 1):g} lb"
            tag = " [negligible]" if i.get("negligible") else ""
            print(f"   {i.get('qty', 1)} x {i['name']}: {w}{tag}" + (f"  ({i['note']})" if i.get("note") else "") + (f"  lore:{i['lore']}" if i.get("lore") else ""))
    return 0


def cmd_additem(a, h):
    cs = h["containers"]
    if a.container not in cs:
        print("NO SUCH CONTAINER", a.container); return 1
    c = cs[a.container]
    w, note = None, a.note or ""
    if a.lb is not None:
        w = a.lb
    elif a.srd:
        w = srd_weight(a.srd)
        if w is None:
            print(f"REFUSED: no SRD weight for '{a.srd}'. Use --lb, --negligible or --unweighed."); return 1
        note = (note + " " if note else "") + f"SRD: {a.srd}"
    elif a.negligible:
        w = 0.0
    elif not a.unweighed:
        found = srd_weight(a.name)
        if found is None:
            print(f"REFUSED: '{a.name}' has no SRD weight. Give --lb, --srd NAME, --negligible or --unweighed."); return 1
        w = found; note = (note + " " if note else "") + "SRD"
    add_lb = (w or 0) * a.qty
    if c["kind"] == "person" and capacity(c) and lb(c) + add_lb > capacity(c) + 1e-9:
        print(f"REFUSED: {c['owner']} carries {lb(c):.1f} lb; adding {add_lb:g} lb passes the carry maximum of {capacity(c)} lb (STR {c['str']}). "
              f"Drop something, or put it in a stash, a cart or a pack animal.")
        return 1
    item = find_item(c, a.name)
    if item and item.get("lb") == w:
        item["qty"] = item.get("qty", 1) + a.qty
    else:
        item = {"name": a.name, "qty": a.qty, "lb": w}
        if a.negligible:
            item["negligible"] = True
        if note:
            item["note"] = note
        if a.lore:
            item["lore"] = a.lore
        c.setdefault("items", []).append(item)
    save(a.dir, h)
    log(a.dir, {"op": "add-item", "to": a.container, "item": a.name, "qty": a.qty, "lb": w, "note": a.note or ""})
    print(f"ADDED {a.qty} x {a.name} to {a.container} ({'UNWEIGHED' if w is None else f'{w:g} lb each'})")
    return 0


def cmd_dropitem(a, h):
    cs = h["containers"]
    if a.container not in cs:
        print("NO SUCH CONTAINER", a.container); return 1
    c = cs[a.container]; i = find_item(c, a.name)
    if not i or i.get("qty", 1) < a.qty:
        print(f"REFUSED: {a.container} does not hold {a.qty} x {a.name}."); return 1
    i["qty"] -= a.qty
    if i["qty"] == 0:
        c["items"].remove(i)
    save(a.dir, h)
    log(a.dir, {"op": "drop-item", "from": a.container, "item": a.name, "qty": a.qty, "note": a.note or ""})
    print(f"REMOVED {a.qty} x {a.name} from {a.container}")
    return 0


def cmd_moveitem(a, h):
    cs = h["containers"]
    for n in (a.src, a.dst):
        if n not in cs:
            print("NO SUCH CONTAINER", n); return 1
    src, dst = cs[a.src], cs[a.dst]; i = find_item(src, a.name)
    if not i or i.get("qty", 1) < a.qty:
        print(f"REFUSED: {a.src} does not hold {a.qty} x {a.name}."); return 1
    w = (i.get("lb") or 0) * a.qty
    if dst["kind"] == "person" and capacity(dst) and lb(dst) + w > capacity(dst) + 1e-9:
        print(f"REFUSED: {dst['owner']} would carry {lb(dst) + w:.1f} lb; the carry maximum is {capacity(dst)} lb (STR {dst['str']})."); return 1
    if src["kind"] != "person" and dst["kind"] != "person" and src.get("place") != dst.get("place") and not a.haul:
        print(f"REFUSED: {a.src} is at '{src.get('place')}', {a.dst} is at '{dst.get('place')}'. Moving items between places is a haul ({w:g} lb). Play it, then rerun with --haul."); return 1
    i["qty"] -= a.qty
    if i["qty"] == 0:
        src["items"].remove(i)
    j = find_item(dst, a.name)
    if j and j.get("lb") == i.get("lb"):
        j["qty"] = j.get("qty", 1) + a.qty
    else:
        n = dict(i); n["qty"] = a.qty; dst.setdefault("items", []).append(n)
    save(a.dir, h)
    log(a.dir, {"op": "move-item", "from": a.src, "to": a.dst, "item": a.name, "qty": a.qty, "lb": w})
    print(f"MOVED {a.qty} x {a.name} ({w:g} lb) {a.src} -> {a.dst}")
    return 0


def cmd_setlb(a, h):
    c = h["containers"].get(a.container)
    i = find_item(c, a.name) if c else None
    if not i:
        print("NO SUCH ITEM"); return 1
    i["lb"] = a.each
    save(a.dir, h)
    log(a.dir, {"op": "set-lb", "container": a.container, "item": a.name, "lb": a.each})
    print(f"SET {a.name} in {a.container}: {a.each:g} lb each")
    return 0


def cmd_weight(a, h):
    w = srd_weight(a.name)
    print(f"{a.name}: {w:g} lb (SRD 5.2.1)" if w is not None else f"{a.name}: no SRD weight found")
    return 0 if w is not None else 1


def log(d, rec):
    rec = {"ts": datetime.datetime.now().isoformat(timespec="seconds"), **rec}
    with (Path(d) / "transfers.jsonl").open("a") as f:
        f.write(json.dumps(rec) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=os.environ.get("HOLDINGS_DIR", "holdings"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("show"); p.add_argument("container", nargs="?"); p.set_defaults(f=cmd_show)
    p = sub.add_parser("load"); p.set_defaults(f=cmd_load)
    p = sub.add_parser("verify"); p.set_defaults(f=cmd_verify)
    p = sub.add_parser("init"); p.set_defaults(f=lambda a, h: (Path(a.dir).mkdir(parents=True, exist_ok=True), save(a.dir, h), print("INIT", a.dir))[2] or 0)
    p = sub.add_parser("items"); p.add_argument("container", nargs="?"); p.set_defaults(f=cmd_items)
    p = sub.add_parser("add-item"); p.add_argument("container"); p.add_argument("name"); p.add_argument("--qty", type=int, default=1)
    p.add_argument("--lb", type=float); p.add_argument("--srd"); p.add_argument("--negligible", action="store_true"); p.add_argument("--unweighed", action="store_true")
    p.add_argument("--note"); p.add_argument("--lore"); p.set_defaults(f=cmd_additem)
    p = sub.add_parser("drop-item"); p.add_argument("container"); p.add_argument("name"); p.add_argument("--qty", type=int, default=1); p.add_argument("--note"); p.set_defaults(f=cmd_dropitem)
    p = sub.add_parser("move-item"); p.add_argument("src"); p.add_argument("dst"); p.add_argument("name"); p.add_argument("--qty", type=int, default=1); p.add_argument("--haul", action="store_true"); p.set_defaults(f=cmd_moveitem)
    p = sub.add_parser("set-lb"); p.add_argument("container"); p.add_argument("name"); p.add_argument("each", type=float); p.set_defaults(f=cmd_setlb)
    p = sub.add_parser("weight"); p.add_argument("name"); p.set_defaults(f=cmd_weight)
    p = sub.add_parser("move"); p.add_argument("src"); p.add_argument("dst"); p.add_argument("amount"); p.add_argument("denom", nargs="?")
    p.add_argument("--note"); p.add_argument("--haul", action="store_true"); p.set_defaults(f=cmd_move)
    a = ap.parse_args()
    sys.exit(a.f(a, load(a.dir)) or 0)


if __name__ == "__main__":
    main()
