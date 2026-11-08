"""Import: ChordPro files (multi-song, Windows-1252, plain text) and ukulele-tabs.com HTML."""
import base64, glob, json, os, signal, sys, time, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from browser import BASE, W, H, SHOTS, FIXTURES, EXAMPLES, Browser, check, finish, skip  # noqa: E402

tag = f"{W}"
D = os.path.join(FIXTURES, "import")
D = os.path.join(FIXTURES, "import")
D = os.path.join(FIXTURES, "import")


b = Browser(capabilities={"unhandledPromptBehavior": "accept"})
m, wait = b.m, b.wait
try:
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/import"})
    # target songbook: create a new one from the import page
    check("songbook select filled", wait("document.querySelector('#imp-book').options.length===2"))
    m.js("window.prompt = () => 'Import-Test'; const s=document.querySelector('#imp-book'); s.value='new'; s.onchange();")
    check("new songbook created + selected", wait("document.querySelector('#imp-book').selectedOptions[0].textContent==='Import-Test'"))
    m.js("document.querySelector('[data-src=cho]').click()")
    el = m.cmd("WebDriver:FindElement", {"using": "css selector", "value": "#chofiles"})["value"]
    eid = list(el.values())[0]
    for f in sorted(os.listdir(D)):
        m.cmd("WebDriver:ElementSendKeys", {"id": eid, "text": os.path.join(D, f)})
    m.js("document.querySelector('#go').click()")
    check("4 songs from 3 files", wait("document.querySelectorAll('#out .result').length===4"), m.js("return document.querySelector('#msg').textContent"))
    names = m.js("return [...document.querySelectorAll('#out .result h2 > span')].map(s=>s.firstChild.textContent.trim())")
    print("  ", names)
    texts = m.js("return [...document.querySelectorAll('#out .result textarea')].map(t=>t.value)")
    check("names", sorted(names) == ["Lagerfeuer - Am Feuer.cho", "Mehrfach - Lied Eins.cho", "Mehrfach - Lied Zwei.cho", "Testband - Gute Nacht.cho"], names)
    feuer = [t for t in texts if "Am Feuer" in t][0]
    check("cp1252 decoded + title/artist from file name", feuer.startswith("{title: Am Feuer}\n{artist: Lagerfeuer}\n") and "– Grüße" in feuer, feuer)
    nacht = [t for t in texts if "Gute Nacht" in t][0]
    check("plain text converted", "{start_of_chorus: Chorus}" in nacht and "[C]Gute Nacht [G]ihr alle" in nacht, nacht)
    check("ukulele tag from file", any("Ukulele" in n for n in names if "Zwei" in n) or m.js("return [...document.querySelectorAll('#out .result h2 .tag')].map(t=>t.textContent).join()") == "Ukulele")
    m.js("document.querySelector('#save-all').click()")
    check("all saved", wait("document.querySelectorAll('#out .result a.ib').length===4"))
    check("toast names the songbook", wait("document.querySelector('#toast').textContent.includes('Import-Test')"), m.js("return document.querySelector('#toast').textContent"))
    bid = m.js("return document.querySelector('#imp-book').value")
    book = m.js_async("const done=arguments[arguments.length-1]; fetch('api/books/' + arguments[0]).then(r=>r.json()).then(j=>done(j.songs.map(s=>s.title)))".replace("arguments[0]", repr(bid)))
    check("all 4 songs in the songbook, in import order", len(book) == 4, book)
    # ukulele-tabs.com HTML pages (saved pages are not in the repository: only when examples/ has them)
    pages = sorted(glob.glob(EXAMPLES + "/*Ukulele Tabs.html"))
    if not pages:
        print("SKIP ukulele-tabs.com part: no saved pages in examples/")
        m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
        check("list has 4 new songs", wait("document.querySelectorAll('#songs a').length===6"), m.js("return document.querySelectorAll('#songs a').length"))
        raise SystemExit
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    m.cmd("WebDriver:Navigate", {"url": "about:blank"})
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/import"})
    m.js("document.querySelector('[data-src=html]').click()")
    eid = list(m.cmd("WebDriver:FindElement", {"using": "css selector", "value": "#files"})["value"].values())[0]
    for f in pages:
        m.cmd("WebDriver:ElementSendKeys", {"id": eid, "text": f})
    m.js("document.querySelector('#go').click()")
    check("2 ukulele-tabs songs converted", wait("document.querySelectorAll('#out .result').length===2 && !document.querySelector('#go').disabled"))
    msg = m.js("return document.querySelector('#msg').textContent")
    check("album page explained with link", "Album-Seite" in msg and "bellyache-uke-tab-78428" in msg, msg)
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    check("list has 4 new songs", wait("document.querySelectorAll('#songs a').length===6"), m.js("return document.querySelectorAll('#songs a').length"))
except SystemExit:
    pass
finally:
    b.close()
finish()
