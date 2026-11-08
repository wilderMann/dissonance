"""GUEST_ACCESS=off: guests only see the login page, a share link still works without an account, robots noindex."""
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
vis = lambda sel: m.js("const e=document.querySelector(arguments[0]); return !!e && e.offsetParent !== null", sel)
try:
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    check("guest: login page instead of the song list", wait("!document.querySelector('#v-login').hidden") and not vis("#songs"))
    check("guest: no songs from the API", api("GET", "api/songs")[1]["songs"] == [])
    check("meta robots noindex", m.js("return document.querySelector('meta[name=robots]').content") == "noindex, nofollow")
    b.shot(f"guest-off-login-{W}")
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/lied/Irgendwas.cho"})
    check("guest: deep link also shows the login page", wait("!document.querySelector('#v-login').hidden"))
    check("login button returns to the link", "r=%23%2Flied%2FIrgendwas.cho" in m.js("return document.querySelector('#login-go').getAttribute('href')"))
    # sign in, share a book
    json.dump({"sub": "a-1", "preferred_username": "alice", "name": "Alice"}, open(WHO, "w"))
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    m.js("setTimeout(() => document.querySelector('#login-go').click(), 50)"); time.sleep(2)
    check("signed in: list instead of the login page", wait("document.querySelector('#acct').textContent==='👤 Alice' && document.querySelector('#v-login').hidden", 10))
    st, song = api("POST", "api/songs", {"content": "{title: Für Gäste}\n{artist: Alice}\n[C]Hallo\n"})
    st, bk = api("POST", "api/books", {"name": "Gästebuch"})
    api("POST", f"api/books/{bk['id']}/lied", {"song": song["id"], "add": True})
    tok = api("POST", f"api/books/{bk['id']}/share", {"on": True})[1]["share"]
    check("signed in: songs visible", any(s["title"] == "Für Gäste" for s in api("GET", "api/songs")[1]["songs"]))
    # sign out -> share link works, everything else is closed
    m.js("document.querySelector('#acct').click()")
    m.js("setTimeout(() => [...document.querySelectorAll('#acct-menu button')].find(b=>b.textContent.includes('Abmelden')).click(), 50)")
    time.sleep(2)
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/teilen/" + tok})
    check("guest: share link opens the book", wait("document.querySelector('#b-title').textContent==='Gästebuch'"))
    m.js("document.querySelector('#b-songs a').click()")
    check("guest: song from the share link plays", wait("document.querySelector('#sheet .c') && document.querySelector('#sheet').textContent.includes('Hallo')"))
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    check("guest: back to the list -> login page", wait("!document.querySelector('#v-login').hidden"))
finally:
    b.close()
finish()
