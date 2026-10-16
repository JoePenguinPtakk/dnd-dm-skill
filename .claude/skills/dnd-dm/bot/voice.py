#!/usr/bin/env python3
"""Voice casting for the DM: find a voice for an NPC, or mint a new one.

The problem this solves. The cast list used to be a human judgement call over
53 vetted names, which meant a DM at the table either remembered the pool or
picked badly. Names carry no information: nothing about "bm_fable" says whether
it suits a dockhand or a duchess.

So every voice is measured once into a catalogue of acoustic attributes, and
the DM searches those attributes in plain words:

    voice.py find "old gravelly man, deep"
    voice.py find "young bright woman"
    voice.py describe bm_george
    voice.py say "Who goes there?" --voice fit:joe

When nothing in the pool fits, mint one. Kokoro's style vectors form a
continuous space, so a blend of stock voices is itself a valid voice, and the
same search that fits a recording can instead aim at requested attributes with
no reference audio at all:

    voice.py mint --pitch 90 --rough --name grimtusk

Attributes measured, all from the audio itself rather than from the name:

    pitch       median F0 in Hz
    range       F0 spread, so a flat delivery is distinguishable from a lively one
    brightness  spectral centroid; dark and chesty against thin and forward
    rough       frame-to-frame F0 jitter, which is what reads as gravel
    breathy     spectral flatness, which is what reads as whisper or air
"""

import argparse
import json
import os
import sys

import numpy as np

BOT = os.path.dirname(os.path.abspath(__file__))  # voice.py lives in the campaign's bot/ folder
KOKORO_DIR = os.path.join(BOT, "voices", "kokoro")
FITTED_DIR = os.path.join(BOT, "voices", "fitted")
CATALOGUE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "voice_catalogue.json")
SR = 24000

# Long enough for stable statistics, short enough to measure 28 voices quickly.
PROBE = ("The gate is shut and the watch has doubled. "
         "Speak your business, and speak it plainly.")

_engine = None


def engine():
    global _engine
    if _engine is None:
        from kokoro_onnx import Kokoro
        _engine = Kokoro(os.path.join(KOKORO_DIR, "kokoro-v1.0.onnx"),
                         os.path.join(KOKORO_DIR, "voices-v1.0.bin"))
    return _engine


def stock_names():
    z = np.load(os.path.join(KOKORO_DIR, "voices-v1.0.bin"), allow_pickle=True)
    return sorted(n for n in z.files if n[0] in "ab")


def fitted_names():
    if not os.path.isdir(FITTED_DIR):
        return []
    return sorted(f[:-4] for f in os.listdir(FITTED_DIR) if f.endswith(".npy"))


def resolve(spec):
    """A stock name, or 'fit:NAME' for a fitted vector."""
    if str(spec).startswith("fit:"):
        v = np.load(os.path.join(FITTED_DIR, f"{spec[4:]}.npy")).astype(np.float32)
        return v.reshape(510, 1, 256) if v.shape == (510, 256) else v
    return spec


def render(spec, text=PROBE):
    samples, sr = engine().create(text, voice=resolve(spec), speed=1.0,
                                  lang="en-us")
    return np.asarray(samples, dtype=np.float64), sr


# ----------------------------------------------------------- measurement

def _frames(x, n, hop):
    if len(x) < n:
        x = np.pad(x, (0, n - len(x)))
    count = 1 + (len(x) - n) // hop
    idx = np.arange(n)[None, :] + hop * np.arange(count)[:, None]
    return x[idx] * np.hanning(n)[None, :]


def _f0_track(x):
    """Per-frame F0 by FFT autocorrelation. Batched, because doing this frame
    by frame is the slowest step in anything that measures many voices."""
    f = _frames(x, 2048, 512)
    energy = (f ** 2).mean(axis=1)
    voiced = f[energy > energy.mean() * 0.35]
    if len(voiced) < 3:
        return np.array([])
    v = voiced - voiced.mean(axis=1, keepdims=True)
    n_fft = 1 << (2 * v.shape[1] - 1).bit_length()
    spec = np.fft.rfft(v, n=n_fft, axis=1)
    ac = np.fft.irfft(spec * np.conj(spec), n=n_fft, axis=1)[:, :v.shape[1]]
    lo, hi = int(SR / 350), int(SR / 60)
    seg = ac[:, lo:hi]
    lags = lo + seg.argmax(axis=1)
    good = (ac[:, 0] > 0) & (seg.max(axis=1) / np.maximum(ac[:, 0], 1e-12) > 0.3)
    return SR / lags[good]


def measure(x):
    x = x - x.mean()
    x = x / (np.sqrt(np.mean(x ** 2)) + 1e-12) * 0.1
    f = _frames(x, 1024, 256)
    mag = np.abs(np.fft.rfft(f, axis=1))
    power = (mag ** 2).mean(axis=0)
    freqs = np.fft.rfftfreq(1024, 1 / SR)

    centroid = float((freqs * power).sum() / (power.sum() + 1e-12))
    flatness = float(np.exp(np.log(power + 1e-12).mean()) / (power.mean() + 1e-12))
    band = (freqs > 100) & (freqs < 8000)
    tilt = float(np.polyfit(np.log(freqs[band]),
                            10 * np.log10(power[band] + 1e-12), 1)[0])

    f0 = _f0_track(x)
    if len(f0) < 3:
        return None
    jitter = float(np.mean(np.abs(np.diff(f0)) / f0[:-1]))
    return {
        "pitch": float(np.median(f0)),
        "range": float(np.percentile(f0, 90) - np.percentile(f0, 10)),
        "brightness": centroid,
        "tilt": tilt,
        "rough": jitter,
        "breathy": flatness,
    }


# ----------------------------------------------------------- catalogue

# Kokoro publishes a per-voice grade on its model card. Worth carrying, because
# a D grade voice that matches a query on paper still sounds bad at the table.
GRADES = {
    "af_heart": "A", "af_bella": "A-", "af_nicole": "B-", "bf_emma": "B-",
    "am_michael": "C+", "am_fenrir": "C+", "am_puck": "C+", "af_kore": "C+",
    "af_sarah": "C+", "af_aoede": "C+", "bm_george": "C", "bm_fable": "C",
    "af_alloy": "C", "af_nova": "C", "bf_isabella": "C", "am_onyx": "D",
    "am_echo": "D", "af_jessica": "D", "af_river": "D", "bf_alice": "D",
    "bf_lily": "D", "bm_daniel": "D", "am_adam": "F+",
}
# af_nicole is B- but reads as a deliberately breathy bedroom voice. Joe's
# ruling: not for general NPCs, so it stays out of search results.
EXCLUDED = {"af_nicole"}


def build(verbose=True):
    entries = []
    specs = [(n, n) for n in stock_names()]
    specs += [(f"fit:{n}", n) for n in fitted_names()]
    for spec, name in specs:
        audio, _ = render(spec)
        m = measure(audio)
        if m is None:
            if verbose:
                print(f"  {spec}: unmeasurable, skipped")
            continue
        m["voice"] = spec
        m["sex"] = "female" if name[1] == "f" else "male"
        m["accent"] = {"a": "American", "b": "British"}.get(name[0], "fitted")
        m["grade"] = GRADES.get(name, "?")
        m["source"] = "fitted" if spec.startswith("fit:") else "stock"
        entries.append(m)
        if verbose:
            print(f"  {spec:<16} {m['pitch']:5.0f} Hz  bright {m['brightness']:5.0f}  "
                  f"rough {m['rough']:.3f}  {m['grade']}")
    with open(CATALOGUE, "w") as fh:
        json.dump(entries, fh, indent=1)
    return entries


def load():
    if not os.path.exists(CATALOGUE):
        print("No catalogue yet. Run: voice.py build", file=sys.stderr)
        sys.exit(1)
    with open(CATALOGUE) as fh:
        return json.load(fh)


# ----------------------------------------------------------- search

# Plain words a DM would actually type, mapped onto measured quantities. Each
# entry is (field, direction, weight); direction -1 means lower is better.
WORDS = {
    "deep": ("pitch", -1, 2.0), "low": ("pitch", -1, 2.0),
    "gravelly": ("rough", +1, 2.0), "rough": ("rough", +1, 2.0),
    "gruff": ("rough", +1, 1.5), "harsh": ("rough", +1, 1.5),
    "smooth": ("rough", -1, 1.5), "clean": ("rough", -1, 1.0),
    "high": ("pitch", +1, 2.0), "shrill": ("pitch", +1, 1.5),
    "bright": ("brightness", +1, 1.5), "thin": ("brightness", +1, 1.0),
    "dark": ("brightness", -1, 1.5), "warm": ("brightness", -1, 1.5),
    "chesty": ("brightness", -1, 1.5), "rich": ("brightness", -1, 1.0),
    "breathy": ("breathy", +1, 1.5), "airy": ("breathy", +1, 1.5),
    "clear": ("breathy", -1, 1.0),
    "lively": ("range", +1, 1.5), "expressive": ("range", +1, 1.5),
    "flat": ("range", -1, 1.5), "monotone": ("range", -1, 2.0),
    "old": ("rough", +1, 1.0), "young": ("rough", -1, 1.0),
}
SEX_WORDS = {"man": "male", "male": "male", "men": "male", "he": "male",
             "woman": "female", "female": "female", "women": "female",
             "she": "female", "lady": "female", "girl": "female",
             "boy": "male"}
ACCENT_WORDS = {"british": "British", "english": "British",
                "american": "American"}


def zscores(entries):
    fields = ["pitch", "range", "brightness", "rough", "breathy"]
    stats = {}
    for f in fields:
        vals = np.array([e[f] for e in entries], dtype=float)
        stats[f] = (vals.mean(), vals.std() + 1e-9)
    return stats


def search(entries, query, limit=6, include_low_grade=False):
    words = [w.strip(",.!?'\"").lower() for w in query.split()]
    stats = zscores(entries)

    want_sex = next((SEX_WORDS[w] for w in words if w in SEX_WORDS), None)
    want_accent = next((ACCENT_WORDS[w] for w in words if w in ACCENT_WORDS), None)
    terms = [WORDS[w] for w in words if w in WORDS]
    unknown = [w for w in words if w not in WORDS and w not in SEX_WORDS
               and w not in ACCENT_WORDS and len(w) > 2]

    pool = [e for e in entries if e["voice"] not in EXCLUDED]
    if want_sex:
        pool = [e for e in pool if e["sex"] == want_sex]
    if want_accent:
        pool = [e for e in pool if e["accent"] == want_accent]
    if not include_low_grade:
        keep = [e for e in pool if e["grade"] in
                ("A", "A-", "B-", "C+", "C", "?")]
        pool = keep or pool

    scored = []
    for e in pool:
        s = 0.0
        for field, direction, weight in terms:
            mean, std = stats[field]
            s += weight * direction * (e[field] - mean) / std
        scored.append((-s, e))
    scored.sort(key=lambda t: t[0])
    return [e for _, e in scored[:limit]], terms, unknown


ADJECTIVES = {
    "pitch": ("deep", "mid", "high"),
    "brightness": ("dark", "warm", "bright"),
    "rough": ("smooth", "some gravel", "gravelly"),
    "range": ("flat", "measured", "lively"),
}
_bands = None


def bands(entries):
    """Cut each attribute at the pool's own terciles.

    Fixed thresholds were guesswork and read as nonsense: every Kokoro voice
    has more jitter than the number I first guessed for "gravelly", so the whole
    cast came back gravelly and the word stopped distinguishing anything. These
    adjectives are comparisons within the cast, so the cast has to define them.
    """
    global _bands
    if _bands is None:
        _bands = {}
        for field in ADJECTIVES:
            vals = np.array([e[field] for e in entries], dtype=float)
            _bands[field] = (np.percentile(vals, 33), np.percentile(vals, 67))
    return _bands


def describe(e, entries=None):
    b = bands(entries or load())
    out = []
    for field, names in ADJECTIVES.items():
        lo, hi = b[field]
        v = e[field]
        out.append(names[0] if v < lo else (names[1] if v < hi else names[2]))
    return ", ".join(out)


def show(entries, note="", pool=None):
    pool = pool or entries
    for e in entries:
        print(f"  {e['voice']:<16} {e['pitch']:5.0f} Hz  {e['sex']:<6} "
              f"{e['accent']:<9} {e['grade']:<3} {describe(e, pool)}")
    if note:
        print(note)


# ----------------------------------------------------------- minting

def mint(entries, target, name, iters=60, pool_size=8, verbose=True):
    """Search stock blends for one matching requested attributes.

    No reference recording is involved: the objective is the requested numbers
    themselves, which is what lets a DM conjure a voice that does not exist yet.
    Candidates stay blends of real voices, so every one is speakable.
    """
    from kokoro_onnx import Kokoro                      # noqa: F401
    z = np.load(os.path.join(KOKORO_DIR, "voices-v1.0.bin"), allow_pickle=True)
    stats = zscores(entries)

    def error(m):
        s = 0.0
        for field, want in target.items():
            mean, std = stats[field]
            s += ((m[field] - want) / std) ** 2
        return float(np.sqrt(s))

    stock = [e for e in entries if e["source"] == "stock"]

    # A blend is a weighted average, so it can never leave the range spanned by
    # its members: no combination of voices is deeper than the deepest one.
    # Asking for 85 Hz when the floor is 91 silently returns the nearest voice
    # and looks like a failed search, so say it instead.
    for field, want in target.items():
        lo = min(e[field] for e in stock)
        hi = max(e[field] for e in stock)
        if not lo <= want <= hi:
            edge = min(stock, key=lambda e: abs(e[field] - want))
            print(f"  {field} {want:g} is outside what blending can reach "
                  f"({lo:.4g} to {hi:.4g}).")
            print(f"  Closest possible is {edge['voice']} at {edge[field]:.4g}. "
                  f"Aiming there instead.")
            target[field] = lo if want < lo else hi

    # Start from the stock voices that already score best, so the search begins
    # somewhere sane instead of at the centre of the space.
    ranked = sorted(stock, key=lambda e: error(e))
    members = [e["voice"] for e in ranked[:pool_size]]
    mats = np.stack([z[m].reshape(510, 256) for m in members])
    if verbose:
        print(f"  seeding from: {', '.join(members[:4])}")

    def evaluate(weights):
        w = np.clip(weights, 0, None)
        w = w / (w.sum() + 1e-12)
        mat = np.tensordot(w, mats, axes=(0, 0)).astype(np.float32)
        audio, _ = engine().create(PROBE, voice=mat.reshape(510, 1, 256),
                                   speed=1.0, lang="en-us")
        m = measure(np.asarray(audio, dtype=np.float64))
        return (1e9, mat) if m is None else (error(m), mat)

    # Seed on the three best rather than one, and shrink the step as it goes.
    # A one-hot seed with a fixed large step spends most of its evaluations
    # proposing wild blends that lose to the seed, so the search never moves.
    best_w = np.zeros(len(members))
    best_w[:3] = [0.6, 0.25, 0.15]
    best_e, best_mat = evaluate(best_w)
    rng = np.random.default_rng(0)
    for i in range(iters):
        step = 0.30 * (1.0 - 0.8 * i / max(iters - 1, 1))
        cand = np.clip(best_w + rng.normal(0, step, len(members)), 0, None)
        if cand.sum() <= 0:
            continue
        e, mat = evaluate(cand)
        if e < best_e:
            best_e, best_w, best_mat = e, cand, mat
            if verbose:
                print(f"    iter {i:3d}  error {e:.3f}")

    os.makedirs(FITTED_DIR, exist_ok=True)
    np.save(os.path.join(FITTED_DIR, f"{name}.npy"), best_mat)
    w = best_w / best_w.sum()
    recipe = ", ".join(f"{m} {wi:.0%}" for m, wi in
                       sorted(zip(members, w), key=lambda t: -t[1]) if wi > 0.02)
    return best_e, recipe


def main():
    ap = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=__doc__)
    sub = ap.add_subparsers(dest="cmd")

    sub.add_parser("build", help="measure every voice into the catalogue")
    sub.add_parser("list", help="the whole catalogue")

    f = sub.add_parser("find", help="find a voice in plain words")
    f.add_argument("query", nargs="+")
    f.add_argument("-n", type=int, default=6)
    f.add_argument("--any-grade", action="store_true")

    d = sub.add_parser("describe", help="attributes of one voice")
    d.add_argument("voice")

    s = sub.add_parser("say", help="audition a voice")
    s.add_argument("text", nargs="+")
    s.add_argument("--voice", required=True)
    s.add_argument("--out", default="/tmp/voice-audition.wav")

    m = sub.add_parser("mint", help="make a new voice to order")
    m.add_argument("--name", required=True)
    m.add_argument("--pitch", type=float, help="target median F0 in Hz")
    m.add_argument("--brightness", type=float, help="target centroid in Hz")
    m.add_argument("--rough", type=float, help="target jitter, e.g. 0.04")
    m.add_argument("--iters", type=int, default=60)

    args = ap.parse_args()

    if args.cmd == "build":
        entries = build()
        print(f"\ncatalogued {len(entries)} voices -> {CATALOGUE}")
        return

    if args.cmd == "list":
        show(sorted(load(), key=lambda e: e["pitch"]))
        return

    if args.cmd == "find":
        entries = load()
        hits, terms, unknown = search(entries, " ".join(args.query),
                                      args.n, args.any_grade)
        if not terms:
            print("No usable descriptors. Try: deep, gravelly, bright, warm, "
                  "breathy, lively, flat, high, smooth.")
        if unknown:
            print(f"(ignored: {', '.join(unknown)})")
        show(hits, pool=entries)
        if hits:
            print(f"\naudition: voice.py say \"Who goes there?\" "
                  f"--voice {hits[0]['voice']}")
        return

    if args.cmd == "describe":
        e = next((x for x in load() if x["voice"] == args.voice), None)
        if not e:
            print(f"{args.voice}: not in the catalogue")
            return
        show([e], pool=load())
        return

    if args.cmd == "say":
        import soundfile as sf
        audio, sr = render(args.voice, " ".join(args.text))
        sf.write(args.out, audio, sr)
        print(f"wrote {args.out}")
        return

    if args.cmd == "mint":
        target = {k: v for k, v in (("pitch", args.pitch),
                                    ("brightness", args.brightness),
                                    ("rough", args.rough)) if v is not None}
        if not target:
            print("Give at least one target, e.g. --pitch 95")
            return
        entries = load()
        err, recipe = mint(entries, target, args.name, iters=args.iters)
        print(f"\nminted fit:{args.name}  error {err:.3f}")
        print(f"  {recipe}")
        print(f"  audition: voice.py say \"Who goes there?\" --voice fit:{args.name}")
        return

    ap.print_help()


if __name__ == "__main__":
    main()
