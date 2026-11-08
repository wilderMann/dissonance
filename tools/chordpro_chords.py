#!/usr/bin/env python3
"""Chord diagrams from ChordPro (https://www.chordpro.org, Artistic License 2.0) -> chords.json for Dissonance.

    python3 tools/chordpro_chords.py              # latest ChordPro release
    python3 tools/chordpro_chords.py --ref R6.101.0
    python3 tools/chordpro_chords.py --check      # only say whether a newer release has different chords

Reads ChordPro's instrument configs (guitar.json is JSON, the ukulele files are ChordPro's "relaxed JSON") straight
from its GitHub repository at a release tag and writes chords.json next to app.py:

    {"source": {...}, "guitar": {"C": [1, [-1,3,2,0,1,0], [0,3,2,0,1,0]], "Db": "C#", ...}, "ukulele": {...}}

Each chord is [base fret, frets relative to the base (-1 muted, 0 open), fingers (0 = none)]; a string is an alias.
The result is committed, so the app needs no network access and every change shows up in the diff.
"""
import argparse
import json
import os
import re
import sys
import urllib.request

REPO = "ChordPro/chordpro"
RAW = "https://raw.githubusercontent.com/" + REPO + "/{ref}/lib/ChordPro/res/config/{file}"
# per instrument: files in order of preference (later ones only add chords the earlier ones lack)
FILES = {"guitar": ["guitar.json"], "ukulele": ["ukulele-ly.json", "ukulele.json"]}
TUNINGS = {"guitar": ["E2", "A2", "D3", "G3", "B3", "E4"], "ukulele": ["G4", "C4", "E4", "A4"]}
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "chords.json")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "dissonance-chord-import"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def latest_release():
    return json.loads(fetch(f"https://api.github.com/repos/{REPO}/releases/latest"))["tag_name"]


# ---------------------------------------------------------------- relaxed JSON (ChordPro's config format)
# objects without commas ({ key : value key : value }), bare words, // and # comments, dotted keys (a.b.c : 1).
TOKEN = re.compile(r'\s+|//[^\n]*|#[^\n]*|/\*.*?\*/|"(?:[^"\\]|\\.)*"|[{}\[\]:,]|[^\s{}\[\]:,"]+', re.S)


def rjson(text):
    toks = [t for t in TOKEN.findall(text) if t.strip() and not t.startswith(("//", "#", "/*"))]
    pos = 0

    def value():
        nonlocal pos
        t = toks[pos]
        pos += 1
        if t == "{":
            return obj("}")
        if t == "[":
            out = []
            while toks[pos] != "]":
                if toks[pos] == ",":
                    pos += 1
                    continue
                out.append(value())
            pos += 1
            return out
        if t.startswith('"'):
            return json.loads(t)
        if re.fullmatch(r"-?\d+", t):
            return int(t)
        if re.fullmatch(r"-?\d+\.\d+", t):
            return float(t)
        return {"true": True, "false": False, "null": None}.get(t, t)

    def obj(end):
        nonlocal pos
        out = {}
        while pos < len(toks) and toks[pos] != end:
            if toks[pos] == ",":
                pos += 1
                continue
            key = toks[pos]
            key = json.loads(key) if key.startswith('"') else key
            pos += 1
            if toks[pos] == ":":
                pos += 1
            elif toks[pos] not in ("{", "["):  # "key { ... }" needs no colon
                raise ValueError(f"':' expected after {key!r}, got {toks[pos]!r}")
            node, *path = key.split(".")
            if path:  # a.b.c : v
                d = out.setdefault(node, {})
                for p in path[:-1]:
                    d = d.setdefault(p, {})
                d[path[-1]] = value()
            else:
                out[key] = value()
        pos += 1
        return out

    return obj(None)


def parse(text, name):
    return json.loads(text) if name.endswith(".json") and text.lstrip().startswith("{") else rjson(text)


# ---------------------------------------------------------------- conversion

def frets_of(v):
    return [-1 if f in ("x", "X", "N", "n", -1) else int(f) for f in v]


def convert(cfgs, inst):
    """ChordPro chord entries -> {name: [base, frets, fingers] | alias}."""
    n = len(TUNINGS[inst])
    out = {}
    for cfg in cfgs:
        if cfg.get("tuning") and [str(x) for x in cfg["tuning"]] != TUNINGS[inst]:
            raise ValueError(f"{inst}: unexpected tuning {cfg['tuning']}")
        for c in cfg.get("chords", []):
            name = str(c.get("name", "")).strip()
            if not name or name in out:
                continue
            if "copy" in c:
                out[name] = str(c["copy"])
                continue
            if "frets" not in c:
                continue
            frets = frets_of(c["frets"])
            if len(frets) != n:
                continue
            # 0 = no finger, 1-4, "T" = thumb
            fingers = [0 if f in ("x", "X", "-", "N", None) else f if f == "T" else int(f) for f in c.get("fingers", [])]
            entry = [int(c.get("base", 1)), frets]
            if len(fingers) == n and any(fingers):
                entry.append(fingers)
            out[name] = entry
    # aliases must end at a real chord (follow chains; drop broken or circular ones)
    def target(name, seen=()):
        v = out.get(name)
        if isinstance(v, str):
            return None if v in seen else target(v, seen + (name,))
        return name if v is not None else None
    for name, v in list(out.items()):
        if isinstance(v, str):
            out[name] = target(v, (name,))
    return {k: v for k, v in out.items() if v is not None}


def build(ref):
    data = {"source": {"name": "ChordPro", "url": "https://www.chordpro.org", "repository": f"https://github.com/{REPO}",
                       "ref": ref, "license": "Artistic-2.0",
                       "note": "Chord diagrams taken from the ChordPro reference implementation by Johan Vromans "
                               "(lib/ChordPro/res/config). Generated by tools/chordpro_chords.py - do not edit."}}
    for inst, files in FILES.items():
        cfgs = []
        for f in files:
            cfgs.append(parse(fetch(RAW.format(ref=ref, file=f)), f))
        data["source"][inst] = files
        data[inst] = convert(cfgs, inst)
    return data


def dump(data):
    # one chord per line: small diffs when ChordPro changes something
    lines = ["{", '"source": ' + json.dumps(data["source"], ensure_ascii=False) + ","]
    insts = [k for k in data if k != "source"]
    for i, inst in enumerate(insts):
        lines.append(json.dumps(inst) + ": {")
        items = list(data[inst].items())
        for j, (k, v) in enumerate(items):
            lines.append(json.dumps(k, ensure_ascii=False) + ":" + json.dumps(v, separators=(",", ":")) + ("," if j < len(items) - 1 else ""))
        lines.append("}" + ("," if i < len(insts) - 1 else ""))
    lines.append("}")
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ref", help="ChordPro git tag or branch (default: latest release)")
    ap.add_argument("--check", action="store_true", help="exit 1 if chords.json differs from that release")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args(argv)
    ref = a.ref or latest_release()
    text = dump(build(ref))
    old = open(a.out, encoding="utf-8").read() if os.path.exists(a.out) else ""
    if a.check:
        print(f"chords.json is {'up to date with' if old == text else 'different from'} ChordPro {ref}")
        return 0 if old == text else 1
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(text)
    d = json.loads(text)
    print(f"ChordPro {ref}: " + ", ".join(f"{k} {sum(isinstance(v, list) for v in d[k].values())} shapes / {len(d[k])} names"
                                          for k in d if k != "source") + (" (unchanged)" if old == text else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
