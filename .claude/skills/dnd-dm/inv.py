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
    return coins(c) / 50.0


def capacity(c):
    return c.get("str", 0) * 15 if c["kind"] == "person" else None


def fmt(c):
    parts = [f"{c['coin'][k]:,g} {k}" for k in DENOMS if c.get("coin", {}).get(k)]
    return ", ".join(parts) or "no coin"


def show_one(name, c):
    cap = capacity(c)
    line = f"{name} [{c['kind']}, {c.get('place', '?')}]: {fmt(c)} = {gp_value(c):,.1f} gp, {coins(c):,g} coins, {lb(c):,.1f} lb"
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
            print(f"{c['owner']}: {lb(c):.1f} lb of coin / {cap} lb carry (STR {c['str']}), {cap - lb(c):.1f} lb free" + ("  OVER" if over else ""))
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
    print(f"HOLDINGS OK containers={len(h['containers'])} total={tot:,.1f} gp hash={sig}" if not over else f"HOLDINGS OVER CAPACITY: {over}")
    return 1 if over else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=os.environ.get("HOLDINGS_DIR", "holdings"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("show"); p.add_argument("container", nargs="?"); p.set_defaults(f=cmd_show)
    p = sub.add_parser("load"); p.set_defaults(f=cmd_load)
    p = sub.add_parser("verify"); p.set_defaults(f=cmd_verify)
    p = sub.add_parser("init"); p.set_defaults(f=lambda a, h: (Path(a.dir).mkdir(parents=True, exist_ok=True), save(a.dir, h), print("INIT", a.dir))[2] or 0)
    p = sub.add_parser("move"); p.add_argument("src"); p.add_argument("dst"); p.add_argument("amount"); p.add_argument("denom", nargs="?")
    p.add_argument("--note"); p.add_argument("--haul", action="store_true"); p.set_defaults(f=cmd_move)
    a = ap.parse_args()
    sys.exit(a.f(a, load(a.dir)) or 0)


if __name__ == "__main__":
    main()
