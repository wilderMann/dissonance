"""Song list: sort by title / artist / date / owner, letter index on the right (jump, missing letters disabled)."""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from browser import BASE, W, Browser, check, finish  # noqa: E402

WHO = os.path.join(os.environ["SONG_DIR"], ".who.json")
API = ("const done=arguments[arguments.length-1]; fetch(arguments[0], {method: arguments[1], headers: {'Content-Type': 'application/json'},"
       " body: arguments[2] ? JSON.stringify(arguments[2]) : undefined}).then(r => r.json().then(j => done([r.status, j])))")


def api(method, path, body=None):
    return m.cmd("WebDriver:ExecuteAsyncScript", {"script": API, "args": [path, method, body]})["value"]


def login(who):
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    if not m.js("return document.querySelector('#acct').textContent==='Anmelden'"):
        m.js("document.querySelector('#acct').click()")
        m.js("setTimeout(() => [...document.querySelectorAll('#acct-menu button')].find(b=>b.textContent.includes('Abmelden')).click(), 50)")
        time.sleep(2)
        wait("document.querySelector('#acct').textContent==='Anmelden'")
    json.dump(who, open(WHO, "w"))
    m.js("setTimeout(() => document.querySelector('#acct').click(), 50)"); time.sleep(2)
    wait(f"document.querySelector('#acct').textContent==='👤 {who['name']}'", 10)


def sort(v):
    m.js("const s=document.querySelector('#sort'); s.value=arguments[0]; s.dispatchEvent(new Event('change'))", v)


b = Browser(capabilities={"unhandledPromptBehavior": "accept"})
m, wait = b.m, b.wait
heads = lambda: m.js("return [...document.querySelectorAll('#songs .letter')].map(e => e.textContent)")
try:
    login({"sub": "z-9", "preferred_username": "zora", "name": "Zora Z"})
    for t in ("Zebra Lied", "Yeti Song"):
        api("POST", "api/songs", {"content": "{title: %s}\n{artist: Zora}\n[C]x\n" % t})
    login({"sub": "a-1", "preferred_username": "alice", "name": "Alice A"})
    for i, t in enumerate(["Apfel", "Ameise", "Banane", "Birne", "Clown", "Dach", "Elch", "Eule", "Fisch", "Gans", "Hund", "Igel",
                           "Kuh", "Löwe", "Maus", "Nashorn", "Otter", "Pferd", "Quelle", "Rabe", "Schaf", "Tiger", "Uhu", "Wal", "Ödland", "1 Zahl"]):
        api("POST", "api/songs", {"content": "{title: %s}\n{artist: %s Band}\n[C]x\n" % (t, "ABCDEFG"[i % 7])})
    m.cmd("WebDriver:Navigate", {"url": "about:blank"}); m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    wait("document.querySelectorAll('#songs .letter').length > 5")
    sort("title")
    check("index shown for a long list", wait("!document.querySelector('#az').hidden"))
    letters = m.js("return [...document.querySelectorAll('#az button')].map(b => b.textContent + (b.disabled ? '-' : ''))")
    check("A–Z + #, missing letters disabled", letters[0] == "A" and letters[-1] == "#" and "V-" in letters and "X-" in letters and "Q" in letters, letters)
    check("Ö counts as O, digits as #", "O" in heads() and "#" in heads(), heads())
    b.shot(f"list-index-{W}")
    m.js("[...document.querySelectorAll('#az button')].find(b => b.textContent === 'T').click()")
    time.sleep(0.5)
    pos = m.js("const h=[...document.querySelectorAll('#songs .letter')].find(e=>e.textContent==='T').getBoundingClientRect(); return [h.top, innerHeight]")
    check("tap T: heading T at the top, below the header", 0 <= pos[0] < pos[1] * 0.4 and m.js("return scrollY") > 100, pos)
    check("current letter marked after the jump", wait("document.querySelector('#az button.cur') && document.querySelector('#az button.cur').dataset.l === 'T'"),
          m.js("const c=document.querySelector('#az button.cur'); return c && c.dataset.l"))
    spread = m.js("const a=document.querySelector('#az').getBoundingClientRect(), b=document.querySelector('#az button').getBoundingClientRect(); return [a.height, b.height, innerHeight]")
    check("letters spread over most of the screen height, tall enough to tap", spread[0] > spread[2] * 0.75 and spread[1] >= 18, spread)
    time.sleep(1.1); m.js("scrollTo(0, 0)"); time.sleep(0.3)
    check("back at the top: current letter is the first one", wait("document.querySelector('#az button.cur').dataset.l === '#'"))
    # artist sort: headings by artist letter
    sort("artist")
    check("artist sort: headings A..G + Z", wait("document.querySelector('#songs .letter')") and heads()[:3] == ["A", "B", "C"] and "Z" in heads(), heads())
    # owner sort: headings by nick, index = initials
    sort("owner")
    check("owner sort: headings are nicks", wait("document.querySelector('#songs .letter')") and heads()[:2] == ["alice", "zora"], heads())
    check("owner index: initials only", m.js("return [...document.querySelectorAll('#az button')].map(b => b.textContent)")[:2] == ["A", "Z"])
    # date sort and search: no headings, no index
    sort("new")
    check("date sort: newest first, no index", wait("document.querySelector('#az').hidden") and not heads()
          and m.js("return document.querySelector('#songs .tt').textContent") == "1 Zahl")
    sort("title")
    m.js("const q=document.querySelector('#q'); q.value='a'; q.dispatchEvent(new Event('input'))")
    check("search: no index", wait("document.querySelector('#az').hidden"))
    m.js("const q=document.querySelector('#q'); q.value=''; q.dispatchEvent(new Event('input'))")
    check("index back after clearing the search", wait("!document.querySelector('#az').hidden"))
    m.js("location.hash = '#/buecher'")
    check("index hidden outside the song list", wait("document.querySelector('#az').hidden"))
finally:
    b.close()
finish()
