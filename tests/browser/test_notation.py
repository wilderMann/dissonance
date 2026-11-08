"""German chord names (H, B = Bb): display setting (browser for guests), files stay international, import detects
German sheets and converts them."""
import os, sys, tempfile, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from browser import BASE, W, Browser, check, finish  # noqa: E402

API = ("const done=arguments[arguments.length-1]; fetch(arguments[0], {method: arguments[1], headers: {'Content-Type': 'application/json'},"
       " body: arguments[2] ? JSON.stringify(arguments[2]) : undefined}).then(r => r.json().then(j => done([r.status, j])))")


def api(method, path, body=None):
    return m.cmd("WebDriver:ExecuteAsyncScript", {"script": API, "args": [path, method, body]})["value"]


b = Browser(capabilities={"unhandledPromptBehavior": "accept"})
m, wait = b.m, b.wait
txt = lambda sel: m.js("return [...document.querySelectorAll(arguments[0])].map(e=>e.textContent)", sel)
try:
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    wait("document.querySelectorAll('#songs a').length>0")
    st, r = api("POST", "api/songs", {"content": "{title: Notation}\n{key: B}\n[B]eins [Bb]zwei [Bm7]drei [F#/Bb]vier [H7]fünf\n"})
    song = BASE + "/#/lied/" + urllib.parse.quote(r["file"])
    m.cmd("WebDriver:Navigate", {"url": song})
    wait("document.querySelector('#sheet .c')")
    check("default: international (an H in the file shows as B)", txt("#sheet .c") == ["B", "Bb", "Bm7", "F#/Bb", "B7"], txt("#sheet .c"))
    # switch to German in the settings (guest / no login: stored in this browser)
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/einstellungen"})
    check("setting offered", wait("document.querySelector('#set-notation') && document.querySelector('#set-notation').offsetParent"))
    check("hint: this browser", "diesem Browser" in m.js("return document.querySelector('#set-notation-hint').textContent"))
    m.js("const s=document.querySelector('#set-notation'); s.value='german'; s.dispatchEvent(new Event('change'))")
    m.cmd("WebDriver:Navigate", {"url": song})
    wait("!document.querySelector('#v-song').hidden && document.querySelector('#sheet .c') && document.querySelector('#sheet .c').textContent==='H'")
    check("German: H, B, Hm7, F#/B, H7", txt("#sheet .c") == ["H", "B", "Hm7", "F#/B", "H7"], txt("#sheet .c"))
    check("key in German", "Tonart H" in " ".join(txt("#sheet .meta")), txt("#sheet .meta"))
    m.js("document.querySelector('#p-tr-up').click()")
    check("transposed +1: C, H, Cm7, G/H", wait("document.querySelector('#sheet .c').textContent==='C'") and txt("#sheet .c")[:4] == ["C", "H", "Cm7", "G/H"], txt("#sheet .c"))
    m.js("document.querySelector('#p-tr-down').click()")
    for _ in range(3):
        if m.js("return !!document.querySelector('#sheet .diag')"):
            break
        m.js("document.querySelector('#p-diag').click()")
    names = txt("#sheet .diag .dn")
    check("diagram labels German, shapes right (H = B major)", "H" in names and "B" in names, names)
    frets = m.js("const w = window.wrappedJSObject || window; return Array.from(w.chordShape('B', 'guitar').frets)")
    check("B (international) is still B natural internally", frets == [-1, 2, 4, 4, 4, 2], frets)
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    check("song list key in German", wait("[...document.querySelectorAll('#songs a')].some(a => a.textContent.includes('Notation') && a.querySelector('.ky').textContent==='H')"))
    content = api("GET", "api/songs/" + urllib.parse.quote(r["file"]))[1]["content"]
    check("file unchanged (international)", "[B]eins [Bb]zwei" in content, content)
    b.shot(f"notation-german-{W}")

    # import a German chord sheet: detected, converted to international names; switchable before saving
    tmp = tempfile.mkdtemp(prefix="diss-de-")
    path = os.path.join(tmp, "Volk - Deutsches Lied.cho")
    with open(path, "w") as f:
        f.write("{title: Deutsches Lied}\n{key: H}\n[H]Hier [B]ist [E]ein [Fis]Lied [D/H]da\n")
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/import"})
    m.js("document.querySelector('[data-src=cho]').click()")
    eid = list(m.cmd("WebDriver:FindElement", {"using": "css selector", "value": "#chofiles"})["value"].values())[0]
    m.cmd("WebDriver:ElementSendKeys", {"id": eid, "text": path})
    m.js("document.querySelector('#go').click()")
    wait("document.querySelectorAll('#out .result').length===1")
    check("German detected", m.js("return document.querySelector('#out .result .imp-not select').value") == "german")
    ta = lambda: m.js("return document.querySelector('#out .result textarea').value")
    check("converted to international for the file", "{key: B}" in ta() and "[B]Hier [Bb]ist [E]ein" in ta() and "[D/B]da" in ta(), ta())
    m.js("const s=document.querySelector('#out .result .imp-not select'); s.value='intl'; s.dispatchEvent(new Event('change'))")
    check("switch back: as written", "[H]Hier [B]ist" in ta(), ta())
    m.js("const s=document.querySelector('#out .result .imp-not select'); s.value='german'; s.dispatchEvent(new Event('change'))")
    m.js("document.querySelector('#out .result h2 .ib.pri').click()")
    check("saved", wait("document.querySelector('#out .result a.ib')"))
    href = m.js("return document.querySelector('#out .result a.ib').getAttribute('href')")
    st, saved = api("GET", "api/songs/" + href.rsplit("/", 1)[1])
    check("file has international names", "[B]Hier [Bb]ist" in saved["content"], saved.get("content"))
    # an international sheet without B/H chords: no switch shown
    with open(path, "w") as f:
        f.write("{title: Anders}\n[C]ohne [G]Frage\n")
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/import"})
    m.js("document.querySelector('[data-src=cho]').click()")
    m.js("document.querySelector('#chofiles').value=''")
    eid = list(m.cmd("WebDriver:FindElement", {"using": "css selector", "value": "#chofiles"})["value"].values())[0]
    m.cmd("WebDriver:ElementSendKeys", {"id": eid, "text": path})
    m.js("document.querySelector('#go').click()")
    wait("document.querySelectorAll('#out .result').length===1 && !document.querySelector('#go').disabled")
    check("no B/H chords: no notation switch", m.js("return document.querySelector('#out .result .imp-not').hidden"))
    # tuner in German shows H
    check("tuner note names German", m.js("const w = window.wrappedJSObject || window; return [w.noteName(71), w.noteName(70)]") == ["H", "B"])
finally:
    b.close()
finish()
