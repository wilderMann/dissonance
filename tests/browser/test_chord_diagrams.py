"""Chord diagrams: verify generated fingerings (all chord tones, bass) and the UI modes."""
import base64, glob, json, os, signal, sys, time, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from browser import BASE, W, H, SHOTS, FIXTURES, EXAMPLES, Browser, check, finish, skip  # noqa: E402

tag = f"{W}"
CHORDS = ["C", "Cm", "C7", "Cmaj7", "Cm7", "Csus4", "Csus2", "Cadd9", "C6", "Cdim", "Cdim7", "Cm7b5", "Caug", "C9", "C/E", "C/G",
          "D", "Dm", "D7", "D/F#", "Eb", "Ebm", "E", "Em", "E7", "F", "Fm", "Fmaj7", "F#", "F#m", "F#7", "Gb", "G", "Gm", "G7",
          "G/B", "Ab", "Abm", "A", "Am", "A7", "Am7", "Bb", "Bbm", "Bb7", "B", "Bm", "B7", "Bm7", "C#m", "C#", "Hm", "H7",
          "Am/G", "Em/B", "Dsus4", "Asus2", "E5", "A7sus4", "Gm6", "Fmaj9", "D9", "Bbmaj7", "C#m7b5", "Ab7", "Dbmaj7", "Ebdim7",
          "Am(maj7)", "G2", "Fadd9", "Esus", "Bo", "Cø", "E7#9", "A13"]

b = Browser(capabilities={"unhandledPromptBehavior": "accept"})
m, wait = b.m, b.wait
try:
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    wait("document.querySelectorAll('#songs a').length>0")
    check("ChordPro chord tables loaded", wait("(window.wrappedJSObject || window).chordDbLoaded()"))
    res = m.js("""const w = window.wrappedJSObject || window; const out = {};
      for (const inst of ['guitar','ukulele']) for (const c of arguments[0]) {
        const t0 = performance.now(); const s = w.chordShape(c, inst);
        out[inst + ' ' + c] = s ? { frets: Array.from(s.frets), base: s.base, src: s.src || '', ms: performance.now() - t0 } : null; }
      return out;""", CHORDS)
    TUN = {"guitar": [4, 9, 2, 7, 11, 4], "ukulele": [7, 0, 4, 9]}
    IDX = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11, "H": 11}
    QUAL = {"": [0, 4, 7], "m": [0, 3, 7], "7": [0, 4, 7, 10], "maj7": [0, 4, 7, 11], "m7": [0, 3, 7, 10], "sus4": [0, 5, 7], "sus2": [0, 2, 7],
            "add9": [0, 4, 7, 2], "6": [0, 4, 7, 9], "dim": [0, 3, 6], "dim7": [0, 3, 6, 9], "m7b5": [0, 3, 6, 10], "aug": [0, 4, 8],
            "9": [0, 4, 7, 10, 2], "5": [0, 7], "7sus4": [0, 5, 7, 10], "m6": [0, 3, 7, 9], "maj9": [0, 4, 7, 11, 2], "m(maj7)": [0, 3, 7, 11],
            "2": [0, 2, 7], "sus": [0, 5, 7], "o": [0, 3, 6], "ø": [0, 3, 6, 10], "7#9": [0, 4, 7, 10, 3], "13": [0, 4, 7, 10, 9]}
    import re
    bad, slow = [], []
    for key, s in res.items():
        inst, c = key.split(" ")
        mm = re.match(r"^([A-H])([#b]?)(.*?)(?:/([A-H][#b]?))?$", c)
        root = (IDX[mm[1]] + {"#": 1, "b": -1, "": 0}[mm[2]]) % 12
        ivs = QUAL[mm[3]]
        bass = None
        if mm[4]:
            bass = (IDX[mm[4][0]] + {"#": 1, "b": -1, "": 0}[mm[4][1:]]) % 12
        if s is None:
            bad.append((key, "none")); continue
        fr = s["frets"]
        pcs = [(TUN[inst][i] + f) % 12 for i, f in enumerate(fr) if f >= 0]
        tones = {(root + i) % 12 for i in ivs}
        need = {(root + i) % 12 for i in ivs if not (i == 7 and len(ivs) > 2)}
        if len(need) > len(TUN[inst]):
            need = set(list(need)[:len(TUN[inst])])
        problems = []
        if s["src"] == "chordpro":  # ChordPro's own choice: inversions, dim7 for dim, 9ths without root are fine
            foreign = [p for p in set(pcs) if p not in tones and p != bass]
            missing = [i for i in ivs if i != 7 and (root + i) % 12 not in pcs]
            if len(foreign) > 1 or len(missing) > 1: bad.append((key, fr, ["chordpro: foreign " + str(foreign) + " missing " + str(missing)]))
            continue
        if not need <= set(pcs) and not (bass is not None and inst == "guitar"): problems.append("missing " + str(sorted(need - set(pcs))))
        if any(p not in tones and p != bass for p in pcs): problems.append("foreign note")
        if inst == "guitar" and pcs[0] != (bass if bass is not None else root) and not (bass is not None): problems.append("bass")
        if inst == "guitar" and bass is not None and pcs[0] not in (bass, root): problems.append("slash bass")
        played = [f for f in fr if f > 0]
        if played and max(played) - min(played) > 3: problems.append("span")
        if problems: bad.append((key, fr, problems))
        if s["ms"] > 300: slow.append((key, round(s["ms"])))
    check("all generated fingerings valid", not bad, bad)
    src = {k: v["src"] for k, v in res.items() if v}
    check("most diagrams come from ChordPro", sum(v == "chordpro" for v in src.values()) > 0.8 * len(src),
          [k for k, v in src.items() if v != "chordpro"])
    rej = m.js("return (window.wrappedJSObject || window).chordDbRejected()")
    print("  ChordPro shapes skipped as implausible:", len(rej), rej[:12])
    check("only a few ChordPro shapes skipped", len(rej) < 40, rej)
    check("generation fast enough (<300 ms each)", not slow, slow)
    for k in ["guitar C", "guitar F", "guitar Bm", "guitar F#m", "guitar Bb", "guitar C#m", "guitar Eb", "ukulele C", "ukulele E", "ukulele Bb", "ukulele F#m", "ukulele Ebm", "guitar Gm6", "guitar E7#9"]:
        print(" ", k, res[k]["frets"], "base", res[k]["base"])
    print("  slowest:", max((v["ms"], k) for k, v in res.items() if v))

    # --- UI: song with a {define}
    req = urllib.request.Request(BASE + "/api/songs", json.dumps({"content": "{title: Griffe}\n{artist: Test}\n{define: Am base-fret 5 frets x 1 3 3 2 1}\n\n[C]Eins [Am]zwei [F]drei [G7]vier\n[Dm]fünf [E7]sechs\n", "overwrite": True}).encode(), {"Content-Type": "application/json"})
    f = json.loads(urllib.request.urlopen(req).read())["file"]
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/lied/" + urllib.request.quote(f)})
    wait("document.querySelectorAll('#sheet .c').length>3")
    check("default: no diagrams", m.js("return document.querySelectorAll('#sheet .dg').length") == 0)
    m.js("document.querySelector('#p-more').click(); document.querySelector('#p-diag').click()")
    check("top: 6 diagrams before the song", m.js("return document.querySelectorAll('#sheet > .diag.d-top .dg').length") == 6
          and m.js("return document.querySelector('#p-diag').textContent") == "Griffe oben")
    check("{define} used for Am (base fret 5)", m.js("return [...document.querySelectorAll('#sheet .dg')].find(s=>s.getAttribute('aria-label')==='Am').textContent.includes('5')"))
    m.js("document.querySelector('#p-diag').click()")
    side = W >= 640
    check("right: sticky side column (wide) / above (narrow)", (not side and m.js("return !!document.querySelector('#sheet > .diag.d-top')")) or m.js("return !!document.querySelector('#sheet .sidewrap > .diag.d-side') && getComputedStyle(document.querySelector('.diag.d-side')).position==='sticky'"))
    m.js("document.querySelector('#p-more').click()")
    open(os.path.join(SHOTS, f"diag-right-{W}.png"), "wb").write(base64.b64decode(m.cmd("WebDriver:TakeScreenshot", {"full": False})["value"]))
    m.js("document.querySelector('#p-more').click(); document.querySelector('#p-inst').click()")
    check("ukulele: 4 strings", m.js("return document.querySelectorAll('#sheet .dg')[0].querySelectorAll('line').length") == 4 + 5
          and m.js("return document.querySelector('#p-inst').textContent") == "Ukulele")
    m.js("document.querySelector('#p-tr-up').click(); document.querySelector('#p-tr-up').click()")
    check("transposed diagrams follow (D first)", m.js("return document.querySelector('#sheet .dg').getAttribute('aria-label')") == "D")
    m.js("document.querySelector('#p-tr-down').click(); document.querySelector('#p-tr-down').click()")
    m.cmd("WebDriver:Navigate", {"url": "about:blank"})
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/lied/" + urllib.request.quote(f)})
    wait("document.querySelectorAll('#sheet .dg').length>3")
    check("setting remembered after reload (right, ukulele)", m.js("return !!document.querySelector(arguments[0]) && document.querySelectorAll('#sheet .dg')[0].querySelectorAll('line').length===9 && document.querySelector('#p-diag').textContent==='Griffe rechts'", "#sheet .diag.d-side" if side else "#sheet .diag.d-top"))
    open(os.path.join(SHOTS, f"diag-uke-{W}.png"), "wb").write(base64.b64decode(m.cmd("WebDriver:TakeScreenshot", {"full": False})["value"]))
    m.js("document.querySelector('#p-more').click(); document.querySelector('#p-inst').click()")  # back to guitar
    check("no horizontal overflow", m.js("return document.documentElement.scrollWidth <= innerWidth"), m.js("return [document.documentElement.scrollWidth, innerWidth]"))
finally:
    b.close()
finish()
