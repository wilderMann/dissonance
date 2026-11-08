"""Campfire mode (GUEST_ACCESS=off): owner opens a songbook to everybody for some days via the ⋯ menu; guests land in it
at the plain address, can play it, can't edit; ending it closes it again. Admin sets the default lifetime."""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from browser import BASE, W, Browser, check, finish  # noqa: E402

WHO = os.path.join(os.environ["SONG_DIR"], ".who.json")
API = ("const done=arguments[arguments.length-1]; fetch(arguments[0], {method: arguments[1], headers: {'Content-Type': 'application/json'},"
       " body: arguments[2] ? JSON.stringify(arguments[2]) : undefined}).then(r => r.json().then(j => done([r.status, j])))")


def api(method, path, body=None):
    return m.cmd("WebDriver:ExecuteAsyncScript", {"script": API, "args": [path, method, body]})["value"]


def logout():
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/einstellungen"})
    if m.js("return document.querySelector('#acct').textContent==='Anmelden'"):
        return
    m.js("document.querySelector('#acct').click()")
    m.js("setTimeout(() => [...document.querySelectorAll('#acct-menu button')].find(b=>b.textContent.includes('Abmelden')).click(), 50)")
    time.sleep(2)


def login(who):
    logout()
    json.dump(who, open(WHO, "w"))
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/einstellungen"})
    m.js("setTimeout(() => document.querySelector('#acct').click(), 50)"); time.sleep(2)
    wait(f"document.querySelector('#acct').textContent==='👤 {who['name']}'", 10)


b = Browser(capabilities={"unhandledPromptBehavior": "accept"})
m, wait = b.m, b.wait
vis = lambda sel: m.js("const e=document.querySelector(arguments[0]); return !!e && e.offsetParent !== null", sel)
try:
    # admin sets the default to 5 days
    login({"sub": "c-1", "preferred_username": "carol", "name": "Carol", "groups": ["admin"]})
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/server"})
    check("server settings page", wait("document.querySelector('#v-users h1').textContent==='Servereinstellungen'"))
    check("admin: campfire default select (7 days)", wait("document.querySelector('#set-campfire-default').value==='7'"))
    m.js("const s=document.querySelector('#set-campfire-default'); s.value='5'; s.dispatchEvent(new Event('change'))")
    check("admin: saved", wait("document.querySelector('#toast').textContent.includes('gespeichert')"))
    # owner: private book with a private song, campfire on via the ⋯ menu
    login({"sub": "a-1", "preferred_username": "alice", "name": "Alice"})
    st, song = api("POST", "api/songs", {"content": "{title: Lagerfeuerlied}\n{artist: Alice}\n[G]Funken [D]fliegen\n", "public": False})
    st, bk = api("POST", "api/books", {"name": "Sommerlager", "public": False})
    api("POST", f"api/books/{bk['id']}/lied", {"song": song["id"], "add": True})
    m.cmd("WebDriver:Navigate", {"url": BASE + f"/#/buch/{bk['id']}"})
    wait("document.querySelector('#b-title').textContent==='Sommerlager'")
    check("toolbar: play + random + sort + ⋯ only", vis("#b-play") and vis("#b-random") and vis("#b-order") and vis("#b-more")
          and not vis("#b-print") and not vis("#b-delete"))
    check("songbook rows show the owner", m.js("return document.querySelector('#b-songs .own').textContent") == "👤 alice")
    m.js("document.querySelector('#b-more').click()")
    check("⋯ menu: print/download, share, campfire, visibility, collaboration, rename, delete",
          wait("!document.querySelector('#b-menu').hidden") and all(vis(x) for x in ("#b-export", "#b-share", "#b-campfire", "#b-vis", "#b-rename", "#b-delete")))
    m.js("document.querySelector('#b-export').click()")
    check("print/download dialog: three choices", wait("document.querySelector('#dlg-export').open") and all(vis(x) for x in ("#b-print", "#b-cho", "#b-zip"))
          and m.js("return document.querySelector('#b-zip').getAttribute('href')").endswith("/export.zip"))
    b.shot(f"book-export-{W}")
    m.js("document.querySelector('#ex-close').click()")
    m.js("document.querySelector('#b-more').click()")
    check("campfire icon drawn", m.js("return !!document.querySelector('#b-campfire .ico-fire svg')"))
    b.shot(f"book-menu-{W}")
    m.js("document.querySelector('#b-campfire').click()")
    check("menu closes, campfire dialog opens with the admin default", wait("document.querySelector('#dlg-campfire').open && document.querySelector('#b-menu').hidden")
          and m.js("return document.querySelector('#cf2-days').value") == "5")
    m.js("const s=document.querySelector('#cf2-days'); s.value='3'; s.dispatchEvent(new Event('change'))")
    b.shot(f"campfire-dialog-{W}")
    m.js("document.querySelector('#cf2-go').click()")
    check("badge in the book", wait("!document.querySelector('#b-fire-badge').hidden && document.querySelector('#b-fire-badge').textContent.includes('Lagerfeuer bis')"))
    until = api("GET", f"api/books/{bk['id']}")[1]["campfire_until"]
    check("3 days", abs(until / 1000 - time.time() - 3 * 86400) < 120, until)
    m.js("document.querySelector('#b-random').click()")
    check("🎲 in the songbook opens a random song of it (with the book as context)",
          wait("location.hash.startsWith('#/buch/%d/lied/') && document.querySelector('#sheet').textContent.includes('Funken')" % bk["id"]))
    check("song view shows the owner", wait("document.querySelector('#s-title').textContent.includes('von alice')"))
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/buecher"})
    check("book list: campfire tag", wait("[...document.querySelectorAll('#books a')].some(a => a.textContent.includes('Sommerlager') && a.textContent.includes('Lagerfeuer'))"))
    # guest: plain address -> straight into the campfire songbook
    logout()
    m.cmd("WebDriver:Navigate", {"url": "about:blank"}); m.cmd("WebDriver:Navigate", {"url": BASE + "/"})
    check("guest at the plain address lands in the songbook", wait("location.hash==='#/buch/%d' && document.querySelector('#b-title').textContent==='Sommerlager'" % bk["id"]))
    check("guest: read only (no sort, rename, delete, campfire)", not vis("#b-order") and not m.js("return [...document.querySelectorAll('#b-menu .needs-edit, #b-menu .needs-manage')].some(e => getComputedStyle(e).display !== 'none')"))
    b.shot(f"campfire-guest-{W}")
    m.js("document.querySelector('#b-songs a').click()")
    check("guest: song plays", wait("document.querySelector('#sheet').textContent.includes('Funken')"))
    check("guest: other pages still closed", api("GET", "api/songs")[1]["songs"] == [])
    # a second campfire book -> landing list
    login({"sub": "a-1", "preferred_username": "alice", "name": "Alice"})
    st, bk2 = api("POST", "api/books", {"name": "Herbstlager"})
    api("POST", f"api/books/{bk2['id']}/campfire", {"days": 1})
    logout()
    m.cmd("WebDriver:Navigate", {"url": "about:blank"}); m.cmd("WebDriver:Navigate", {"url": BASE + "/"})
    check("two campfires: landing list + login", wait("!document.querySelector('#v-login').hidden && document.querySelectorAll('#login-fire-list a').length===2"))
    b.shot(f"campfire-landing-{W}")
    # owner ends it -> guests are out again
    login({"sub": "a-1", "preferred_username": "alice", "name": "Alice"})
    for x in (bk, bk2):
        api("POST", f"api/books/{x['id']}/campfire", {"days": 0})
    logout()
    m.cmd("WebDriver:Navigate", {"url": "about:blank"}); m.cmd("WebDriver:Navigate", {"url": BASE + f"/#/buch/{bk['id']}"})
    check("after the end: login page only", wait("!document.querySelector('#v-login').hidden && document.querySelector('#login-fires').hidden"))
finally:
    b.close()
finish()
