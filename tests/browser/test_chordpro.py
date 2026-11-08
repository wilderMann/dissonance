"""ChordPro compatibility: {transpose} (song + modulation), grids, info fields ({composer} …, {meta}), instrument
selectors, sort title, directives without colon, chord diagrams from ChordPro's tables (with fingers)."""
import os, sys, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from browser import BASE, W, Browser, check, finish  # noqa: E402

API = ("const done=arguments[arguments.length-1]; fetch(arguments[0], {method: arguments[1], headers: {'Content-Type': 'application/json'},"
       " body: arguments[2] ? JSON.stringify(arguments[2]) : undefined}).then(r => r.json().then(j => done([r.status, j])))")
SONG = """{title: Kompatibel}
{sorttitle: Aaa zuerst}
{artist: Testband}
{composer: Clara Musik}
{lyricist: Theo Text}
{meta: album Probenraum}
{year: 1999}
{time: 3/4}
{duration: 225}
{key: C}
{transpose: 2}
{x_instrument: guitar}
{copyright: 2024 Testverlag}

{start_of_verse: label="Strophe 1"}
[C]Eins [G]zwei
{end_of_verse}
{comment-guitar: nur Gitarre}
{comment-ukulele: nur Ukulele}
{transpose: 2}
[C]modu[F]liert
{transpose}
[C]zurück
{start_of_grid shape="1+4x2+1" label="Intro"}
A | C . . . | G~F . . . | x2
  |: Am . / . | % :|
|S dn up dn up |
{end_of_grid}
{c Kommentar ohne Doppelpunkt}
"""


def api(method, path, body=None):
    return m.cmd("WebDriver:ExecuteAsyncScript", {"script": API, "args": [path, method, body]})["value"]


b = Browser(capabilities={"unhandledPromptBehavior": "accept"})
m, wait = b.m, b.wait
txt = lambda sel: m.js("return [...document.querySelectorAll(arguments[0])].map(e=>e.textContent)", sel)
try:
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    wait("document.querySelectorAll('#songs a').length>0")
    st, r = api("POST", "api/songs", {"content": SONG})
    check("saved", st == 200, r)
    m.cmd("WebDriver:Navigate", {"url": "about:blank"})
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    check("sorttitle puts it first", wait("document.querySelector('#songs a .tt') && document.querySelector('#songs a .tt').textContent==='Kompatibel'"),
          txt("#songs a .tt")[:3])
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/lied/" + urllib.parse.quote(r["file"])})
    wait("document.querySelector('#sheet .c')")
    check("song transposition from {transpose: 2}", m.js("return document.querySelector('#p-tr-v').textContent").startswith("+2"),
          m.js("return document.querySelector('#p-tr-v').textContent"))
    lines = [l for l in txt("#sheet .ln") if l.strip()]
    chords = txt("#sheet .ln .c")
    check("verse transposed C G -> D A", chords[:2] == ["D", "A"], chords)
    check("modulation +2 more: C F -> E A", chords[2:4] == ["E", "A"], chords)
    check("{transpose} without value goes back: C -> D", chords[4] == "D", chords)
    check("label=\"…\" on sections", "Strophe 1" in txt("#sheet .sec.verse .lbl"), txt("#sheet .lbl"))
    cm = txt("#sheet .cm")
    check("instrument selector: guitar yes, ukulele no", "nur Gitarre" in cm and "nur Ukulele" not in cm, cm)
    check("directive without colon", "Kommentar ohne Doppelpunkt" in cm, cm)
    meta = " | ".join(txt("#sheet .meta"))
    for want in ("Tonart D", "Takt 3/4", "⏱ 3:45", "Musik: Clara Musik", "Text: Theo Text", "Album: Probenraum (1999)"):
        check("info: " + want, want in meta, meta)
    check("copyright at the end", txt("#sheet .copy") == ["© 2024 Testverlag"], txt("#sheet .copy"))
    # grid
    check("grid with label", txt("#sheet .sec.grid .lbl") == ["Intro"], txt("#sheet .lbl"))
    rows = m.js("return [...document.querySelectorAll('#sheet .grid .grow')].map(r => [...r.children].map(c => c.className + ':' + c.textContent))")
    check("3 grid rows", len(rows) == 3, rows)
    check("row 1: margins, bars, transposed chords, two chords in a cell, empty cells",
          rows[0][0] == "gm:A" and "gb:|" in rows[0] and "gc:D" in rows[0] and "gc:AG" in rows[0] and "gc:" in rows[0] and rows[0][-1] == "gm r:x2", rows[0])
    check("row 2: repeat bars, / and %", "gb:|:" in rows[1] and "gb::|" in rows[1] and "gc:Bm" in rows[1] and "gc:/" in rows[1] and "gc:𝄎" in rows[1], rows[1])
    check("row 3: strum arrows", [c for c in rows[2] if c.startswith("gc")] == ["gc:↓", "gc:↑", "gc:↓", "gc:↑"], rows[2])
    # diagrams (from ChordPro, with finger numbers) include grid chords
    m.js("document.querySelector('#p-more') && document.querySelector('#p-more').click()")
    for _ in range(3):
        if m.js("return !!document.querySelector('#sheet .diag')"):
            break
        m.js("document.querySelector('#p-diag').click()")
    check("diagrams shown", wait("document.querySelector('#sheet .diag svg')"))
    names = txt("#sheet .diag .dn")
    check("diagrams for grid chords too (Bm, G)", "Bm" in names and "G" in names, names)
    check("finger numbers from ChordPro", wait("document.querySelector('#sheet .diag text.fg')"))
    b.shot(f"chordpro-compat-{W}")
    # "Tonart merken" writes {transpose}, keeps the modulation
    m.js("document.querySelector('#p-tr-up').click()")
    m.js("document.querySelector('#p-keep').click()")
    wait("document.querySelector('#toast').textContent.includes('gespeichert')")
    content = api("GET", "api/songs/" + urllib.parse.quote(r["file"]))[1]["content"]
    check("song transposition written as {transpose: 3}", content.count("{transpose: 3}") == 1 and "{transpose: 2}\n[C]modu" in content
          and "x_transpose" not in content, [l for l in content.splitlines() if "transpose" in l])
    # an old song with x_transpose is read too, and saving converts it
    st, old = api("POST", "api/songs", {"content": "{title: Alt}\n{x_transpose: -2}\n[D]alt\n"})
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/lied/" + urllib.parse.quote(old["file"])})
    check("x_transpose still works", wait("document.querySelector('#sheet .c') && document.querySelector('#sheet .c').textContent==='C'"))
    m.js("document.querySelector('#p-keep').click()")
    wait("document.querySelector('#toast').textContent.includes('gespeichert')")
    content = api("GET", "api/songs/" + urllib.parse.quote(old["file"]))[1]["content"]
    check("…and becomes {transpose: -2}", "{transpose: -2}" in content and "x_transpose" not in content, content)
    # editor: ♯ transposes grid chords in the text as well
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/bearbeiten/" + urllib.parse.quote(r["file"])})
    wait("!document.querySelector('#edit').hidden")
    m.js("document.querySelector('#e-tr-up').click()")
    t = m.js("return document.querySelector('#e-text').value")
    check("editor ♯: grid chords move too, margins stay", "A | Db . . . | Ab~Gb . . . | x2" in t and "|: Bbm . / . |" in t,
          [l for l in t.splitlines() if "|" in l])
finally:
    b.close()
finish()
