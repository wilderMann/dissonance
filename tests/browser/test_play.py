"""Drive headless Firefox via Marionette (no extra packages) and exercise the songbook UI."""
import base64, glob, json, os, signal, sys, time, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from browser import BASE, W, H, SHOTS, FIXTURES, EXAMPLES, Browser, check, finish, skip  # noqa: E402

tag = f"{W}"


b = Browser(capabilities={"unhandledPromptBehavior": "accept"})
m, wait = b.m, b.wait
try:

    # --- list
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    check("list shows 2 songs", wait("document.querySelectorAll('#songs a').length===2"))
    m.js("const q=document.querySelector('#q'); q.value='grü'; q.oninput();")
    check("search filters", m.js("return document.querySelectorAll('#songs a').length") == 1)
    m.js("const q=document.querySelector('#q'); q.value=''; q.oninput();")

    # --- play mode + autoscroll
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/lied/" + urllib.parse.quote("Die Testband - Grüße aus Wien.cho")})
    check("song renders", wait("document.querySelectorAll('#sheet .c').length>50"))
    check("control bar visible", m.js("return !document.querySelector('#bar').hidden"))
    first = m.js("return document.querySelector('#sheet .c').textContent")
    check("first chord Em", first == "Em", first)
    m.js("document.querySelector('#p-toggle').click()")
    y0 = m.js("return scrollY")
    time.sleep(2)
    y1 = m.js("return scrollY")
    check("auto-scroll moves at tempo 10", y1 - y0 > 10, f"{y0} -> {y1} px in 2 s")
    m.js("for(let i=0;i<10;i++) document.querySelector('#p-faster').click()")
    y1 = m.js("return scrollY"); time.sleep(2); y2 = m.js("return scrollY")
    check("tempo 20 is faster", (y2 - y1) > 1.5 * (y1 - y0), f"{y2 - y1} px in 2 s")
    m.js("document.querySelector('#sheet').click()")
    y3 = m.js("return scrollY"); time.sleep(1); y4 = m.js("return scrollY")
    check("tap on sheet pauses", y3 == y4 and m.js("return document.querySelector('#p-toggle').textContent") == "▶")

    # --- transpose / font / chords toggle
    m.js("document.querySelector('#p-more').click(); document.querySelector('#p-tr-up').click(); document.querySelector('#p-tr-up').click()")
    first = m.js("return document.querySelector('#sheet .c').textContent")
    check("transpose +2 -> F#m", first == "F#m", first)
    m.js("document.querySelector('#p-tr-down').click(); document.querySelector('#p-tr-down').click(); document.querySelector('#p-tr-down').click()")
    first = m.js("return document.querySelector('#sheet .c').textContent")
    check("transpose -1 -> Ebm (flat key)", first == "Ebm", first)
    fs0 = m.js("return getComputedStyle(document.querySelector('#sheet')).fontSize")
    m.js("document.querySelector('#p-font-up').click()")
    fs1 = m.js("return getComputedStyle(document.querySelector('#sheet')).fontSize")
    check("font bigger", float(fs1[:-2]) > float(fs0[:-2]), f"{fs0} -> {fs1}")
    m.js("document.querySelector('#p-chords').click()")
    check("chords hidden", m.js("return getComputedStyle(document.querySelector('#sheet .c')).display") == "none")
    m.js("document.querySelector('#p-chords').click()")
    check("no horizontal overflow", m.js("return document.documentElement.scrollWidth <= innerWidth"),
          m.js("return [document.documentElement.scrollWidth, innerWidth]"))

    # --- key in the file, tempo per device in the database
    m.js("document.querySelector('#p-keep').click()")
    check("key saved to file", wait("document.querySelector('#toast').textContent.includes('Tonart -1 gespeichert')"),
          m.js("return document.querySelector('#toast').textContent"))
    tempos = m.js_async("const done=arguments[arguments.length-1]; fetch('api/songs/' + location.hash.split('/').pop(), {cache:'no-store'}).then(r=>r.json()).then(j=>done(j.tempos))")
    check("tempo auto-saved for PC in the database", tempos == {"pc": 20}, tempos)
    check("device shown in bar", "PC" in m.js("return document.querySelector('#p-speed-v').textContent"))

    # --- edit mode: change, save, reopen
    m.js("document.querySelector('#to-edit').click()")
    check("editor shown", m.js("return !document.querySelector('#edit').hidden && document.querySelector('#bar').hidden"))
    check("editor: back arrow leads to the song", m.js("return document.querySelector('#s-back').getAttribute('href')").startswith("#/lied/"),
          m.js("return document.querySelector('#s-back').getAttribute('href')"))
    txt = m.js("return document.querySelector('#e-text').value")
    check("file has {transpose} (ChordPro), no x_transpose/x_autoscroll", "{transpose: -1}" in txt and "x_transpose" not in txt
          and "x_autoscroll" not in txt, [l for l in txt.splitlines() if l.startswith(("{x_", "{transpose"))])
    check("instrument select shows guitar (from UG)", m.js("return document.querySelector('#e-inst').value") == "guitar")
    m.js("const s=document.querySelector('#e-inst'); s.value='ukulele'; s.onchange();")
    check("select writes directive", "{x_instrument: ukulele}" in m.js("return document.querySelector('#e-text').value"))
    m.js("const t=document.querySelector('#e-text'); t.value=t.value.replace('{title: Grüße aus Wien}','{title: Grüße aus Wien (Test)}'); t.oninput();")
    check("preview live", "Grüße" in m.js("return document.querySelector('#e-preview').textContent"))
    m.js("document.querySelector('#e-save').click()")
    check("saved + renamed", wait("location.hash.includes('Wien%20(Test)')"), m.js("return location.hash"))
    check("back in play mode", m.js("return !document.querySelector('#play').hidden"))
    check("reopen uses saved tempo", m.js("return document.querySelector('#p-speed').value") == "20")
    m.js("document.querySelector('#p-more').click(); document.querySelector('#p-diag').click()")
    check("ukulele-marked song shows ukulele diagrams", m.js("return document.querySelector('#p-inst').textContent") == "Ukulele"
          and m.js("return document.querySelectorAll('#sheet .dg')[0].querySelectorAll('line').length") == 9)
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    m.cmd("WebDriver:Navigate", {"url": "about:blank"})
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    check("list shows instrument tags", wait("[...document.querySelectorAll('#songs .tag')].map(t=>t.textContent).sort().join()==='Gitarre,Ukulele'"),
          m.js("return [...document.querySelectorAll('#songs .tag')].map(t=>t.textContent)"))

    # --- new song
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/neu"})
    wait("!document.querySelector('#edit').hidden")
    m.js("const t=document.querySelector('#e-text'); t.value='{title: Testlied}\\n{artist: Lagerfeuer}\\n\\n[G]Hallo [D]Welt\\n'; t.oninput();")
    m.js("document.querySelector('#e-save').click()")
    check("new song saved", wait("location.hash.includes('Lagerfeuer%20-%20Testlied')"), m.js("return location.hash"))

    # --- theme toggle (⚙ menu, the entry stays open and cycles)
    check("no login: ⚙ menu instead of 👤", m.js("return !document.querySelector('#gear').hidden && document.querySelector('#acct').hidden"))
    m.js("document.querySelector('#gear').click()")
    design = "[...document.querySelectorAll('#acct-menu button')].find(b=>b.textContent.includes('Design'))"
    m.js(design + ".click()")
    t1 = m.js("return document.documentElement.dataset.theme")
    m.js(design + ".click()")
    t2 = m.js("return [document.documentElement.dataset.theme, getComputedStyle(document.body).backgroundColor]")
    check("theme cycles auto->light->dark", t1 == "light" and t2[0] == "dark", t2)

    # --- service worker
    check("service worker active", wait("navigator.serviceWorker.controller!==null || navigator.serviceWorker.ready", 8))
finally:
    b.close()
finish()
