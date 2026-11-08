"""Share link for a private songbook: owner creates it, a guest opens book, song and print view, owner stops sharing."""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from browser import BASE, W, Browser, check, finish  # noqa: E402

WHO = os.path.join(os.environ["SONG_DIR"], ".who.json")  # read by login_server.py
API = ("const done=arguments[arguments.length-1]; fetch(arguments[0], {method: arguments[1], headers: {'Content-Type': 'application/json'},"
       " body: arguments[2] ? JSON.stringify(arguments[2]) : undefined}).then(r => r.json().then(j => done([r.status, j])))")


def api(method, path, body=None):
    return m.cmd("WebDriver:ExecuteAsyncScript", {"script": API, "args": [path, method, body]})["value"]


b = Browser(capabilities={"unhandledPromptBehavior": "accept"})
m, wait = b.m, b.wait
try:
    vis = lambda sel: m.js("const e=document.querySelector(arguments[0]); return !!e && e.offsetParent !== null", sel)
    json.dump({"sub": "a-1", "preferred_username": "alice", "name": "Alice"}, open(WHO, "w"))
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/buecher"})
    wait("document.querySelector('#acct').textContent==='Anmelden'")
    m.js("setTimeout(() => document.querySelector('#acct').click(), 50)"); time.sleep(2)
    wait("document.querySelector('#acct').textContent==='👤 Alice'", 10)
    st, song = api("POST", "api/songs", {"content": "{title: Nur für Freunde}\n{artist: Alice}\n[G]geheim [D]Lied\n", "public": False})
    st, bk = api("POST", "api/books", {"name": "Lagerfeuer", "public": False})
    api("POST", f"api/books/{bk['id']}/lied", {"song": song["id"], "add": True})
    m.cmd("WebDriver:Navigate", {"url": BASE + f"/#/buch/{bk['id']}"})
    wait("document.querySelector('#b-title').textContent==='Lagerfeuer'")
    m.js("document.querySelector('#b-more').click()")
    check("share in the ⋯ menu of a private book", wait("!document.querySelector('#b-menu').hidden") and vis("#b-share"))
    m.js("document.querySelector('#b-share').click()")
    check("share dialog with link", wait("document.querySelector('#dlg-share').open && document.querySelector('#sh-link').value.includes('#/teilen/')"))
    link = m.js("return document.querySelector('#sh-link').value")
    check("lifetime: default 30 days, date shown", m.js("return document.querySelector('#sh-days').value") == "30"
          and vis("#sh-days") and m.js("return document.querySelector('#sh-exp').textContent").startswith("bis "))
    b.shot(f"share-dialog-{W}")
    m.js("const s=document.querySelector('#sh-days'); s.value='0'; s.dispatchEvent(new Event('change'))")
    check("lifetime: unlimited", wait("document.querySelector('#sh-exp').textContent==='läuft nicht ab'"))
    check("lifetime: stored", api("GET", f"api/books/{bk['id']}")[1]["share_expires"] is None)
    m.js("const s=document.querySelector('#sh-days'); s.value='7'; s.dispatchEvent(new Event('change'))")
    check("lifetime: 7 days", wait("document.querySelector('#sh-exp').textContent.startsWith('bis ')")
          and abs(api("GET", f"api/books/{bk['id']}")[1]["share_expires"] / 1000 - time.time() - 7 * 86400) < 120)
    check("link unchanged by the lifetime", m.js("return document.querySelector('#sh-link').value") == link)
    m.js("document.querySelector('#sh-close').click()")
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/buecher"})
    check("book list marks it as shared", wait("[...document.querySelectorAll('#books .tag')].some(t => t.textContent.includes('geteilt'))"))
    # sign out -> guest opens the link
    m.js("document.querySelector('#acct').click()")
    m.js("setTimeout(() => [...document.querySelectorAll('#acct-menu button')].find(b=>b.textContent.includes('Abmelden')).click(), 50)")
    time.sleep(2)
    wait("document.querySelector('#acct').textContent==='Anmelden'")
    check("guest: private book not in the list", m.js("return fetch('api/books').then(r=>r.json()).then(j=>j.books.length)") == 0)
    m.cmd("WebDriver:Navigate", {"url": link})
    check("guest: shared book opens", wait("document.querySelector('#b-title').textContent==='Lagerfeuer'"))
    check("guest: private song listed, read-only", m.js("return document.querySelector('#b-songs .tt').textContent") == "Nur für Freunde"
          and not vis("#b-delete") and not vis("#b-rename") and not vis("#b-add") and not vis("#b-order"))
    m.js("document.querySelector('#b-songs a').click()")
    check("guest: song plays from the link", wait("document.querySelector('#sheet .c') && location.hash.includes('/teilen/') && location.hash.includes('/lied/')"))
    check("guest: back goes to the shared book, no heart/books", m.js("return document.querySelector('#s-back').getAttribute('href')") == link[link.index("#"):]
          and not vis("#s-fav") and not vis("#s-books"))
    m.cmd("WebDriver:Navigate", {"url": link + "/druck"})
    check("guest: print view of the shared book", wait("document.querySelector('#pbook').textContent.includes('Nur für Freunde')"))
    tok = link.rsplit("/", 1)[1]
    check("guest: download of the shared book", m.js("return fetch(arguments[0]).then(r => r.text())", f"api/shared/{tok}/export.cho").count("Nur für Freunde") == 1)
    # owner stops sharing
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    m.js("setTimeout(() => document.querySelector('#acct').click(), 50)"); time.sleep(2)
    wait("document.querySelector('#acct').textContent==='👤 Alice'", 10)
    m.cmd("WebDriver:Navigate", {"url": BASE + f"/#/buch/{bk['id']}"})
    wait("document.querySelector('#b-title').textContent==='Lagerfeuer'")
    m.js("window.confirm = () => true; document.querySelector('#b-share').click()")
    wait("document.querySelector('#dlg-share').open")
    m.js("document.querySelector('#sh-off').click()")
    check("sharing switched off", wait("!document.querySelector('#dlg-share').open && !document.querySelector('#b-share').classList.contains('on')"))
    st, r = api("GET", f"api/shared/{tok}")
    check("old link no longer works", st == 404, (st, r))
    m.cmd("WebDriver:Navigate", {"url": link})
    check("old link shows a message", wait("document.querySelector('#b-title').textContent.includes('Link')"),
          m.js("return document.querySelector('#b-title').textContent"))
    # admin sets the default to 90 days; then a new link gets 90 days
    json.dump({"sub": "c-1", "preferred_username": "carol", "name": "Carol", "groups": ["admin"]}, open(WHO, "w"))
    m.js("document.querySelector('#acct').click()")
    m.js("setTimeout(() => [...document.querySelectorAll('#acct-menu button')].find(b=>b.textContent.includes('Abmelden')).click(), 50)")
    time.sleep(2)
    wait("document.querySelector('#acct').textContent==='Anmelden'")
    m.js("setTimeout(() => document.querySelector('#acct').click(), 50)"); time.sleep(2)
    wait("document.querySelector('#acct').textContent==='👤 Carol'", 10)
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/benutzer"})
    check("admin page: default lifetime select", wait("document.querySelector('#set-share-days').value==='30'"))
    m.js("const s=document.querySelector('#set-share-days'); s.value='90'; s.dispatchEvent(new Event('change'))")
    check("admin: default saved", wait("document.querySelector('#toast') && document.querySelector('#toast').textContent.includes('Standard gespeichert')")
          or api("GET", "api/admin/settings")[1]["share_days"] == 90)
    check("admin: default is 90", api("GET", "api/admin/settings")[1]["share_days"] == 90)
    st, bk2 = api("POST", "api/books", {"name": "Neues Buch"})
    m.cmd("WebDriver:Navigate", {"url": BASE + f"/#/buch/{bk2['id']}"})
    wait("document.querySelector('#b-title').textContent==='Neues Buch'")
    m.js("document.querySelector('#b-share').click()")
    check("new link uses the admin default", wait("document.querySelector('#dlg-share').open && document.querySelector('#sh-days').value==='90'"))
    m.js("document.querySelector('#sh-close').click()")
finally:
    b.close()
finish()
