#!/usr/bin/env python3
"""book.py: read a published module (and its bestiary) from the books themselves, so the DM runs them as written.

"Run the module as it directs" (master prompt §4.1 PUBLISHED-MODULE EXCEPTION, §6-septies) is only possible if
the DM reads the module instead of recalling it. Reading a whole book costs ~250,000 tokens; this prints the part
a scene needs, usually a few hundred.

The books are the campaign's private copies, never committed. module/module.json names them:
    "books": {"module": {"text": "books/<module>.md", "pdf": "books/<module>.pdf"},
              "mm":     {"text": "books/<monster manual>.md", "pdf": "books/<monster manual>.pdf"}}
(an older "book": "<text path>" key still works, as the module). A text is a page-marked extract
(`=== PAGE n ===`, PDF page numbers); `extract` builds one from a PDF, column by column.

OCR WARNING. Scanned books carry an OCR text layer that misreads characters ("Tnoll" for Troll, "2d5" for 2d6,
"l5" for 15). Text is fine for finding things and for prose; a NUMBER that decides an outcome (a DC, a hit
bonus, damage dice, hit points) that looks odd is checked against the page image: `book.py image N --book mm`
writes a PNG and prints its path, and you read the image.

  book.py unit ID                     the unit's own text (a keyed area from its heading to the next; an event
                                      from its heading)
  book.py creature NAME               a creature's stat block, in the campaign's order (below)
  book.py page N [M] [--book mm]      page N (to M), verbatim
  book.py find WORDS [--book mm]      every page where the words appear, with the line
  book.py around WORDS [--book mm]    the first match and the 60 lines after it
  book.py image N [--book mm]         render page N to a PNG to read (books/cache/), for numbers OCR garbles
  book.py extract --pdf P --out T     build a page-marked, column-ordered text from a PDF (once, between sessions)

CREATURE ORDER (master prompt §4.1 PUBLISHED-MODULE EXCEPTION): 1. the module's own stat block, when the module
prints one; 2. the 2024 SRD block (bestiary.py show NAME), when the creature is in the 2024 SRD: clean text, no
OCR; 3. the 2024 Monster Manual, by OCR text with its page image for the numbers. A creature in none of them is
[UNESTABLISHED]: never a remembered block.

Absence is never proof: `find` scans every page before it says a name is not in the book.
"""
import argparse
import difflib
import json
import re
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent
SIZE_LINE = re.compile(r"^\W{0,4}(Tiny|Small|Medium|Large|Huge|Gargantuan)\b[\w ,()'\-]*,\s*[A-Za-z]", re.I)
SIZE_SQUEEZED = re.compile(r"^\W{0,4}(Tiny|Small|Medium|Large|Huge|Gargantuan)[A-Za-z(),'\-]*,[A-Za-z]", re.I)


# ---------------------------------------------------------------- loading

def config(d):
    root = Path(d)
    # --dir given as the campaign folder instead of its module/ folder: use module/ (a common slip).
    if not (root / "module.json").exists() and (root / "module" / "module.json").exists():
        root = root / "module"
    cfg = json.loads((root / "module.json").read_text()) if (root / "module.json").exists() else {}
    books = dict(cfg.get("books", {}))
    if "module" not in books and cfg.get("book"):
        books["module"] = {"text": cfg["book"]}
    return root, cfg, books


def resolve(root, rel):
    p = Path(rel)
    return p if p.is_absolute() else root.parent / p


def read_pages(path):
    pages, cur = {}, None
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        m = re.match(r"^=== PAGE (\d+) ===$", line)
        if m:
            cur = int(m.group(1))
            pages[cur] = []
        elif cur is not None:
            pages[cur].append(line)
    return pages


def load_text(root, books, which):
    b = books.get(which)
    if not b or not b.get("text"):
        sys.exit(f"BOOK: module/module.json names no '{which}' text. Nothing to read.")
    path = resolve(root, b["text"])
    if not path.exists():
        sys.exit(f"BOOK: the text {path} is missing on this machine. It is private and never committed: copy it "
                 f"there (see the campaign README). Until then, say [UNESTABLISHED] rather than recall.")
    return read_pages(path)


def manifest(root):
    p = root / "manifest.json"
    return json.loads(p.read_text()) if p.exists() else {}


# ---------------------------------------------------------------- module units

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


def cmd_unit(a):
    root, cfg, books = config(a.dir)
    pages, man = load_text(root, books, "module"), manifest(root)
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
            print(f"BOOK {u['id']} {u.get('title', '')} (from p{pg[0]}; OCR text: check a number that decides an "
                  f"outcome with `book.py image {pg[0]}`)\n")
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


# ---------------------------------------------------------------- creatures

def squeeze(s):
    """OCR-tolerant comparison key: lowercase letters only, with the commonest scanner swaps folded."""
    s = s.lower()
    for a, b in (("rn", "m"), ("cl", "d"), ("vv", "w")):
        s = s.replace(a, b)
    s = re.sub(r"[^a-z]", "", s)
    return s.replace("c", "g").replace("n", "r").replace("l", "i")


def stat_blocks(pages):
    """Every stat block in a book: (name line, page, start index, lines). A block starts at the line before a
    'Size Type, Alignment' line and runs to the next block's start (or 90 lines)."""
    flat = [(p, ln) for p in sorted(pages) for ln in pages[p]]
    starts = []
    for i, (p, ln) in enumerate(flat):
        # The OCR sometimes spaces letters out ("M ed i u m M o nstrosity"), so test the line squeezed of
        # spaces, and confirm with an armor-class line just below so prose that starts "Large ..." can't pass.
        squeezed = re.sub(r"\s+", "", ln.strip())
        if (i > 0 and SIZE_LINE.match(ln.strip()) or SIZE_SQUEEZED.match(squeezed)) and any(
                re.match(r"^\W{0,3}(AC|ArmorClass|Armor Class)\b", re.sub(r"\s+", " ", x[1].strip()).replace("Armor Class", "AC"))
                for x in flat[i + 1:i + 4]):
            j = i - 1
            while j > 0 and len(flat[j][1].strip()) < 3:
                j -= 1
            starts.append(j)
    out = []
    for k, s in enumerate(starts):
        end = min(starts[k + 1] if k + 1 < len(starts) else len(flat), s + 90)
        out.append((flat[s][1].strip(), flat[s][0], [x for _, x in flat[s:end]]))
    return out


def best(blocks, name):
    want = squeeze(name)
    scored = []
    for nm, p, lines in blocks:
        r = difflib.SequenceMatcher(None, want, squeeze(nm)).ratio()
        scored.append((r, nm, p, lines))
    scored.sort(key=lambda x: -x[0])
    return scored


INDEX_LINE = re.compile(r"^([A-Z0-9][A-Za-z0-9 ,'\-()]{2,40}?)\s?[\.,]{3,}[\s\.,\-]*([0-9lIOoS ]{1,5})\s*$")


def book_index(pages):
    """A bestiary's contents list ('Troll Limb......310'): name -> printed page. The list is set in plain type,
    so its names survive OCR far better than the decorative headings on the entries themselves."""
    idx = {}
    for p in sorted(pages)[:20]:
        for ln in pages[p]:
            m = INDEX_LINE.match(ln.strip())
            if not m:
                continue
            num = m.group(2).replace(" ", "").translate(str.maketrans("lIOoS", "11005"))
            name = m.group(1).replace("1", "l").replace("8", "B").replace("9", "g").strip()
            if num.isdigit():
                idx[name] = int(num)
    return idx


def page_offset(idx, blocks):
    """PDF page minus printed page, by majority over entries whose name matches a block near that page."""
    votes = {}
    for name, printed in idx.items():
        for nm, p, _ in blocks:
            if 0 <= p - printed <= 8 and difflib.SequenceMatcher(None, squeeze(name), squeeze(nm)).ratio() > 0.85:
                votes[p - printed] = votes.get(p - printed, 0) + 1
    return max(votes, key=votes.get) if votes else 0


def mm_lookup(pages, name):
    """Score every stat block on three signals, because the OCR garbles each one somewhere: the heading (set in a
    decorative font, often mangled), how often the block's own body text names the creature (body text OCRs well:
    'The beholder randomly shoots...'), and closeness to the page the contents list gives (whose numbers can be
    misread too). Returns the best block and up to two runners-up."""
    blocks = stat_blocks(pages)
    words = [w for w in re.findall(r"[a-z]+", name.lower()) if len(w) > 2] or [name.lower()]
    idx = book_index(pages)
    target = None
    if idx:
        close = difflib.get_close_matches(name.lower(), [n.lower() for n in idx], n=1, cutoff=0.85)
        if close:
            entry = next(n for n in idx if n.lower() == close[0])
            target = idx[entry] + page_offset(idx, blocks)
    scored = []
    for nm, p, lines in blocks:
        body = " ".join(lines[2:]).lower()
        hits = min(sum(len(re.findall(r"\b" + re.escape(w) + r"s?\b", body)) for w in words), 6)
        head = difflib.SequenceMatcher(None, squeeze(name), squeeze(nm)).ratio()
        near = 0.3 if target is not None and 0 <= p - target <= 2 else 0.0
        scored.append((head + 0.12 * hits + near, head, hits, nm, p, lines))
    scored.sort(key=lambda x: -x[0])
    good = [s for s in scored if (s[1] >= 0.8 or s[2] >= 2) and s[0] >= 0.75]
    if not good:
        return None, "", []
    s = good[0]
    how = f"heading {s[1]:.2f}, named {s[2]}x in its own text" + (f", contents-list page {target}" if target else "")
    return (s[3], s[4], s[5]), how, [(x[3], x[4]) for x in good[1:3]]


def srd_has(name):
    p = SKILL / "bestiary.json"
    if not p.exists():
        return None
    for c in json.loads(p.read_text())["creatures"]:
        if c["name"].lower() == name.lower():
            return c["name"]
    return None


def cmd_creature(a):
    root, cfg, books = config(a.dir)
    name = a.name
    # 1. the module's own block
    if "module" in books:
        mod = best(stat_blocks(load_text(root, books, "module")), name)
        if mod and mod[0][0] >= 0.85:
            r, nm, p, lines = mod[0]
            print(f"CREATURE {name}: 1. THE MODULE'S OWN BLOCK ('{nm}', module p{p}). Use this one. OCR text: check "
                  f"any number that looks odd with `book.py image {p}`.\n")
            print("\n".join(lines).strip()[:a.max])
            return 0
    # 2. the 2024 SRD
    hit = srd_has(name)
    if hit:
        print(f"CREATURE {name}: 2. THE 2024 SRD BLOCK. The module prints none. Run `bestiary.py show \"{hit}\"` "
              f"(clean text, the 2024 Monster Manual's block). Use it over any OCR copy.")
        return 0
    # 3. the 2024 Monster Manual
    if "mm" in books:
        hit, how, alts = mm_lookup(load_text(root, books, "mm"), name)
        if hit:
            nm, p, lines = hit
            alt = "; other candidates: " + ", ".join(f"'{x[0]}' p{x[1]}" for x in alts) if alts else ""
            print(f"CREATURE {name}: 3. THE 2024 MONSTER MANUAL (block headed '{nm}', PDF p{p}; {how}{alt}). "
                  f"OCR TEXT: confirm it is the right creature and read every number from the page image first: "
                  f"`book.py image {p} --book mm`.\n")
            print("\n".join(lines).strip()[:a.max])
            return 0
    print(f"CREATURE {name}: in none of the module, the 2024 SRD or the Monster Manual text. [UNESTABLISHED]: never "
          f"a remembered block. Try another spelling, or `book.py find \"{name}\" --book mm`.")
    return 1


# ---------------------------------------------------------------- pages and search

def cmd_page(a):
    root, cfg, books = config(a.dir)
    pages = load_text(root, books, a.book)
    for p in range(a.n, (a.to or a.n) + 1):
        print(f"=== PAGE {p} ===")
        print("\n".join(pages.get(p, ["(no such page)"])))
    return 0


def pattern(words):
    q = words.strip()
    flags = 0 if q[:1].isupper() else re.I
    return re.compile(r"\b" + r"\s+".join(map(re.escape, q.split())) + r"\b", flags)


def cmd_find(a):
    root, cfg, books = config(a.dir)
    pages, pat, n = load_text(root, books, a.book), pattern(a.words), 0
    for p in sorted(pages):
        for ln in pages[p]:
            if pat.search(ln):
                print(f"  p{p}: {ln.strip()[:110]}")
                n += 1
                if n >= a.limit:
                    print("  ... more; narrow the words or raise --limit")
                    return 0
    if n == 0:
        print(f"BOOK: '{a.words}' appears on no page of '{a.book}' (case-sensitive for a capitalized name; the OCR "
              f"may also have misspelled it). Not found is not proof: try a shorter word before [UNESTABLISHED].")
    return 0


def cmd_around(a):
    root, cfg, books = config(a.dir)
    pages, pat = load_text(root, books, a.book), pattern(a.words)
    flat = [(p, ln) for p in sorted(pages) for ln in pages[p]]
    for i, (p, ln) in enumerate(flat):
        if pat.search(ln):
            print(f"BOOK around '{a.words}' (p{p})\n")
            print("\n".join(x for _, x in flat[i:i + a.lines]))
            return 0
    print(f"BOOK: '{a.words}' not found.")
    return 0


def cmd_image(a):
    root, cfg, books = config(a.dir)
    b = books.get(a.book, {})
    if not b.get("pdf"):
        print(f"BOOK: module/module.json names no PDF for '{a.book}'.")
        return 1
    pdf = resolve(root, b["pdf"])
    if not pdf.exists():
        print(f"BOOK: the PDF {pdf} is missing on this machine (private, never committed).")
        return 1
    import pymupdf
    out = root.parent / "books" / "cache" / f"{a.book}-p{a.n:03d}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.exists():
        doc = pymupdf.open(pdf)
        doc[a.n - 1].get_pixmap(dpi=a.dpi).save(out)
    print(f"IMAGE {out}  (page {a.n} of '{a.book}'; read it with your image reader, numbers from the image win)")
    return 0


def cmd_extract(a):
    """Page-marked text from a PDF, each page read column by column (a two-column page's left column, then its
    right), so a stat block or a paragraph is not interleaved with its neighbour across the gutter."""
    import pymupdf
    doc = pymupdf.open(a.pdf)
    out = [f"# {Path(a.pdf).stem} (text extract, column-ordered)", "",
           "OCR text from a scan: names and numbers can be misread. Check a number against the page image "
           "(`book.py image N`).", ""]
    for i, page in enumerate(doc):
        w = page.rect.width
        blocks = [b for b in page.get_text("blocks") if len(b[4].strip()) > 2]
        full = [b for b in blocks if b[0] < w * 0.35 and b[2] > w * 0.65]
        left = [b for b in blocks if b not in full and b[0] < w / 2 - 10]
        right = [b for b in blocks if b not in full and b[0] >= w / 2 - 10]
        out.append(f"=== PAGE {i + 1} ===")
        for col in (sorted(full, key=lambda b: b[1]), sorted(left, key=lambda b: (round(b[1]), b[0])),
                    sorted(right, key=lambda b: (round(b[1]), b[0]))):
            for b in col:
                out.append(b[4].rstrip())
    Path(a.out).write_text("\n".join(out) + "\n")
    print(f"EXTRACT {doc.page_count} pages -> {a.out}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default="module")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("unit"); p.add_argument("id"); p.add_argument("--max", type=int, default=6000); p.set_defaults(f=cmd_unit)
    p = sub.add_parser("creature"); p.add_argument("name"); p.add_argument("--max", type=int, default=5000); p.set_defaults(f=cmd_creature)
    for nm, fn in (("page", cmd_page), ("find", cmd_find), ("around", cmd_around), ("image", cmd_image)):
        p = sub.add_parser(nm)
        if nm in ("page", "image"):
            p.add_argument("n", type=int)
        if nm == "page":
            p.add_argument("to", type=int, nargs="?")
        if nm in ("find", "around"):
            p.add_argument("words")
        p.add_argument("--book", default="module")
        p.add_argument("--limit", type=int, default=25)
        p.add_argument("--lines", type=int, default=60)
        p.add_argument("--dpi", type=int, default=110)
        p.set_defaults(f=fn)
    p = sub.add_parser("extract"); p.add_argument("--pdf", required=True); p.add_argument("--out", required=True)
    p.set_defaults(f=cmd_extract)
    a = ap.parse_args()
    sys.exit(a.f(a) or 0)


if __name__ == "__main__":
    main()
