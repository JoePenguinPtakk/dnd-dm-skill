#!/usr/bin/env python3
"""book.py: read a published module's own text, a unit or a page at a time, so the DM runs it as written.

"Run the module as it directs" (master prompt §4.1 PUBLISHED-MODULE EXCEPTION, §6-septies) is only possible if
the DM reads the module instead of recalling it. Reading the whole book costs ~250,000 tokens; this prints the
part a scene needs, usually a few hundred.

The text is a plain-text extract of the book with `=== PAGE n ===` markers (PDF page numbers). It is the
campaign's private copy and is never committed: module/module.json names its path under "book".
Units come from module/manifest.json (map.py's file): an area or event carries its pages and, for a keyed area,
its heading, so `unit` can cut the area's own text out of the page.

  book.py [--dir module] unit ID            the unit's own text (a keyed area from its heading to the next)
  book.py [--dir module] page N [M]         page N (to M), verbatim
  book.py [--dir module] find WORDS         every page where the words appear, with the line
  book.py [--dir module] around WORDS       the first match and the 60 lines after it

Absence is never proof: `find` scans every page before it says a name is not in the book. A thing that is not
in the module is [UNESTABLISHED], never filled from memory.
"""
import argparse
import json
import re
import sys
from pathlib import Path


def load(d):
    root = Path(d)
    cfg = json.loads((root / "module.json").read_text()) if (root / "module.json").exists() else {}
    book = cfg.get("book")
    if not book:
        sys.exit("BOOK: module/module.json names no \"book\" text file. Nothing to read.")
    path = (root.parent / book) if not Path(book).is_absolute() else Path(book)
    if not path.exists():
        sys.exit(f"BOOK: the text file {path} is missing on this machine. It is private and never committed: "
                 f"copy it there (see the campaign README). Until then, say [UNESTABLISHED] rather than recall.")
    pages, cur = {}, None
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        m = re.match(r"^=== PAGE (\d+) ===$", line)
        if m:
            cur = int(m.group(1))
            pages[cur] = []
        elif cur is not None:
            pages[cur].append(line)
    man = json.loads((root / "manifest.json").read_text()) if (root / "manifest.json").exists() else {}
    return pages, man, cfg


def norm(s):
    return re.sub(r"[^A-Z0-9]", "", s.upper())


def key_re(key):
    """An area key as the OCR prints it: 'Z1' may read 'Zl.' or 'Z 1,'; 'Q10' may read 'Ql0'."""
    digits = "".join({"1": "[1lI]", "0": "[0O]"}.get(c, c) + r"\s?" for c in key[1:])
    return re.compile(r"^\s*_?" + re.escape(key[0]) + r"\s?" + digits + r"\s*[\.,]")


def cut_area(lines, key, title, next_key):
    """From the area's heading to the next keyed heading."""
    pat = key_re(key)
    start = next((i for i, ln in enumerate(lines) if pat.match(ln)), None)
    if start is None:
        return None
    stop = len(lines)
    if next_key:
        npat = key_re(next_key)
        stop = next((j for j in range(start + 1, len(lines)) if npat.match(lines[j])), len(lines))
    return lines[start:stop]


def from_heading(lines, heading):
    h = norm(heading)
    return next((i for i, ln in enumerate(lines) if h and h in norm(ln)), None)


def cmd_unit(pages, man, a):
    units = {u["id"]: u for u in man.get("areas", []) + man.get("events", [])}
    u = units.get(a.id)
    if not u:
        print(f"BOOK: no unit '{a.id}' in the manifest. Try `book.py find`.")
        return 1
    pg = u.get("pages") or []
    if not pg:
        print(f"BOOK: {a.id} has no page reference. Try `book.py find \"{u.get('title', a.id)}\"`.")
        return 1
    span = list(range(pg[0], pg[-1] + 1))
    lines = [ln for p in span for ln in pages.get(p, [])]
    if u.get("key"):
        group = [x for x in man.get("areas", []) if x.get("group") == u.get("group")]
        group.sort(key=lambda x: (int(re.sub(r"\D", "", x["key"]) or 0), x["key"]))
        idx = next(i for i, x in enumerate(group) if x["id"] == u["id"])
        nxt = group[idx + 1]["key"] if idx + 1 < len(group) else None
        more = [ln for p in range(pg[-1] + 1, pg[-1] + 3) for ln in pages.get(p, [])]
        part = cut_area(lines + more, u["key"], u.get("title", ""), nxt)
        if part:
            text = "\n".join(part).strip()
            print(f"BOOK {u['id']} {u.get('title', '')} (from p{pg[0]}; OCR text, check numbers in the PDF)\n")
            print(text[:a.max])
            if len(text) > a.max:
                print(f"\n[... cut at {a.max} characters; `book.py page {pg[0]}` for the rest]")
            return 0
        print(f"(heading for {u['key']} not found in the OCR; printing its page{'s' if len(span) > 1 else ''})\n")
    found = None
    if u.get("heading"):
        found = from_heading(lines, u["heading"])
        if found is not None:
            lines = lines[found:]
    text = "\n".join(lines).strip()
    print(f"BOOK {u['id']} {u.get('title', '')} pp{span[0]}-{span[-1]}"
          + (f" from '{u['heading']}'" if found is not None else " (whole pages)") + "\n")
    print(text[:a.max])
    if len(text) > a.max:
        print(f"\n[... cut at {a.max} characters; read further with `book.py page N`]")
    return 0


def cmd_page(pages, man, a):
    last = a.to or a.n
    for p in range(a.n, last + 1):
        print(f"=== PAGE {p} ===")
        print("\n".join(pages.get(p, ["(no such page)"])))
    return 0


def pattern(words):
    q = words.strip()
    if q[:1].isupper():
        return re.compile(r"\b" + r"\s+".join(map(re.escape, q.split())) + r"\b")
    return re.compile(r"\b" + r"\s+".join(map(re.escape, q.split())) + r"\b", re.I)


def cmd_find(pages, man, a):
    pat = pattern(a.words)
    n = 0
    for p in sorted(pages):
        for ln in pages[p]:
            if pat.search(ln):
                print(f"  p{p}: {ln.strip()[:110]}")
                n += 1
                if n >= a.limit:
                    print(f"  ... more; narrow the words or raise --limit")
                    return 0
    if n == 0:
        print(f"BOOK: '{a.words}' appears on no page (case-sensitive for a capitalized name). Not in the module: "
              f"[UNESTABLISHED] unless a campaign file establishes it.")
    return 0


def cmd_around(pages, man, a):
    pat = pattern(a.words)
    flat = [(p, ln) for p in sorted(pages) for ln in pages[p]]
    for i, (p, ln) in enumerate(flat):
        if pat.search(ln):
            print(f"BOOK around '{a.words}' (p{p})\n")
            print("\n".join(x for _, x in flat[i:i + a.lines]))
            return 0
    print(f"BOOK: '{a.words}' not found.")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default="module")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("unit"); p.add_argument("id"); p.add_argument("--max", type=int, default=6000); p.set_defaults(f=cmd_unit)
    p = sub.add_parser("page"); p.add_argument("n", type=int); p.add_argument("to", type=int, nargs="?"); p.set_defaults(f=cmd_page)
    p = sub.add_parser("find"); p.add_argument("words"); p.add_argument("--limit", type=int, default=25); p.set_defaults(f=cmd_find)
    p = sub.add_parser("around"); p.add_argument("words"); p.add_argument("--lines", type=int, default=60); p.set_defaults(f=cmd_around)
    a = ap.parse_args()
    pages, man, cfg = load(a.dir)
    sys.exit(a.f(pages, man, a) or 0)


if __name__ == "__main__":
    main()
