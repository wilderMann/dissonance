"""Booklet (A5 heft) print test: setup via API, check page flow, imposition order, TOC numbers, PDF."""
import base64, glob, json, os, signal, sys, time, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from browser import BASE, W, H, SHOTS, FIXTURES, EXAMPLES, Browser, check, finish, skip  # noqa: E402

tag = f"{W}"
def call(method, path, obj=None):
    req = urllib.request.Request(BASE + path, json.dumps(obj).encode() if obj is not None else None,
                                 {"Content-Type": "application/json"}, method=method)
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def gen(title, verses):
    out = [f"{{title: {title}}}", "{artist: Generator}", "{key: G}", ""]
    for v in range(verses):
        kind = "chorus" if v % 2 else "verse"
        out.append(f"{{start_of_{kind}: {'Refrain' if v % 2 else 'Strophe ' + str(v // 2 + 1)}}}")
        for l in range(6):
            out.append(f"[G]Zeile {l + 1} von Teil {v + 1}, [D]ein bisschen [Em]Text zum [C]Singen")
        out.append(f"{{end_of_{kind}}}")
        out.append("")
    return "\n".join(out)


songs = call("GET", "/api/songs")["songs"]
ids = [s["id"] for s in songs]
for t, v in [("Kurz", 2), ("Sehr lang", 18), ("Mittel", 5), ("Lang", 9), ("Noch eins", 3)]:
    ids.append(call("POST", "/api/songs", {"content": gen(t, v), "overwrite": True})["id"])
bid = call("POST", "/api/books", {"name": "Heft-Test"})["id"]
call("PUT", f"/api/books/{bid}", {"songs": ids})

b = Browser(capabilities={"unhandledPromptBehavior": "accept"})
m, wait = b.m, b.wait
try:
    if os.environ.get("DIAG"):
        m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
        m.js("localStorage.setItem('lb.diagDefault', JSON.stringify(arguments[0]))", os.environ["DIAG"])
        m.cmd("WebDriver:Navigate", {"url": "about:blank"})
    m.cmd("WebDriver:Navigate", {"url": BASE + f"/#/buch/{bid}/druck"})
    wait("document.querySelectorAll('#pbook .psong').length===7")
    if os.environ.get("DIAG"):
        check("diagrams in print", m.js("return document.querySelectorAll('#pbook .diag .dg').length") > 10)
    m.js("const s=document.querySelector('#pr-format'); s.value='heft'; s.onchange();")
    check("booklet drawn", wait("document.querySelectorAll('#pbook .bsheet').length>0"))
    info = m.js("""
      const sheets=[...document.querySelectorAll('#pbook .bsheet')];
      const num = p => p.classList.contains('bcover') ? 1 : (p.querySelector('.pno') ? +p.querySelector('.pno').textContent : null);
      return {
        sheets: sheets.map(s => [...s.children].map(p => [num(p), p.classList.contains('left') ? 'L' : 'R', p.classList.contains('bblank')])),
        overflow: [...document.querySelectorAll('#pbook .bbody')].filter(b => b.scrollHeight > b.clientHeight + 1).map(b => [b.scrollHeight, b.clientHeight, document.querySelector('.bsheets').style.zoom]),
        toc: [...document.querySelectorAll('#pbook .tocl')].map(r => [r.querySelector('.tt').textContent, +r.querySelector('.tp').textContent]),
        titles: [...document.querySelectorAll('#pbook .bpage .ttl')].map(t => [t.textContent, +(t.closest('.bpage').querySelector('.pno')||{textContent:0}).textContent]),
        forts: [...document.querySelectorAll('#pbook .lbl')].filter(l => l.textContent.includes('Forts.')).length,
        pagestyle: document.querySelector('#pstyle') && document.querySelector('#pstyle').textContent,
        label: document.querySelector('#pbook .blabel').textContent,
      };""")
    sheets = info["sheets"]
    N = len(sheets) * 2
    print("pages:", len(sheets) * 2)
    check("page count multiple of 4", N % 4 == 0, N)
    # expected imposition; blank pages have no number -> compare by position via index map
    exp = []
    for s in range(N // 4):
        exp += [[N - 2 * s, 2 * s + 1], [2 * s + 2, N - 2 * s - 1]]
    got = [[p[0] for p in side] for side in sheets]
    check("imposition order", all(g == e or (g[0] in (None, e[0]) and g[1] in (None, e[1])) for g, e in zip(got, exp)), got)
    check("left/right per side", all(side[0][1] == "L" and side[1][1] == "R" for side in sheets[1:]) and sheets[0][1][1] == "R")
    check("no page overflows", not info["overflow"], info["overflow"])
    tmap = {t.split(". ", 1)[1]: p for t, p in info["titles"]}
    check("TOC page numbers match", all(tmap[t.split(" – ")[0]] == p for t, p in info["toc"]), (info["toc"], info["titles"]))
    starts = {t.split(". ", 1)[1]: p for t, p in info["titles"]}
    check("long songs start on a left (even) page", starts["Sehr lang"] % 2 == 0 and starts["Lang"] % 2 == 0, starts)
    check("split sections marked (Forts.)", info["forts"] > 0, info["forts"])
    check("@page A4 landscape active", "A4 landscape" in (info["pagestyle"] or ""))
    print("label:", info["label"])
    open(os.path.join(SHOTS, "booklet.png"), "wb").write(base64.b64decode(m.cmd("WebDriver:TakeScreenshot", {"full": False})["value"]))
    pdf = base64.b64decode(m.cmd("WebDriver:Print", {"background": True, "orientation": "landscape", "shrinkToFit": False,
        "page": {"width": 21.0, "height": 29.7}, "margin": {"top": 0, "bottom": 0, "left": 0, "right": 0}})["value"])
    open(os.path.join(SHOTS, "booklet%s.pdf" % os.environ.get("DIAG", "")), "wb").write(pdf)
    m.js("const s=document.querySelector('#pr-flip'); s.value='long'; s.onchange();")
    check("long-edge: back sides rotated", m.js("return document.querySelectorAll('#pbook .bsheet.flip').length") == N // 4)
    m.js("const s=document.querySelector('#pr-flip'); s.value='short'; s.onchange(); const p=document.querySelector('#pr-page'); p.checked=false; p.onchange();")
    check("flowing mode (no new page per song) fits", m.js("return [...document.querySelectorAll('#pbook .bbody')].every(b => b.scrollHeight <= b.clientHeight + 1)"))
    print("flow pages:", m.js("return document.querySelectorAll('#pbook .bpage').length"))
    m.js("const p=document.querySelector('#pr-page'); p.checked=true; p.onchange(); const s=document.querySelector('#pr-format'); s.value='a4'; s.onchange();")
    check("back to A4: page style removed", m.js("return !document.querySelector('#pstyle') && document.querySelectorAll('#pbook .psong').length===7"))
finally:
    b.close()
finish()
