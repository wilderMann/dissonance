"""Admin: a user's page in the server settings (songs, songbooks, activity) and a new owner in bulk edit –
also for the songs from before the login (fixtures have no owner)."""
import json, os, sys, time, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from browser import BASE, W, Browser, check, finish  # noqa: E402

WHO = os.path.join(os.environ["SONG_DIR"], ".who.json")
API = ("const done=arguments[arguments.length-1]; fetch(arguments[0], {method: arguments[1], headers: {'Content-Type': 'application/json'},"
       " body: arguments[2] ? JSON.stringify(arguments[2]) : undefined}).then(r => r.json().then(j => done([r.status, j])))")
shown = lambda sel: f"(e => !!e && e.offsetParent !== null && getComputedStyle(e).display !== 'none')(document.querySelector('{sel}'))"

b = Browser(capabilities={"unhandledPromptBehavior": "accept"})
m, wait = b.m, b.wait
api = lambda method, path, body=None: m.cmd("WebDriver:ExecuteAsyncScript", {"script": API, "args": [path, method, body]})["value"]
rows = "[...document.querySelectorAll('#songs li.row2')]"
row = lambda t: f"{rows}.find(li => li.querySelector('.tt').textContent === '{t}')"


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


try:
    login({"sub": "a-1", "preferred_username": "alice", "name": "Alice Wonder"})
    api("POST", "api/songs", {"content": "{title: Alices Lied}\n{artist: Alice}\n[C]x\n"})
    st, bk = api("POST", "api/books", {"name": "Alices Buch"})
    api("PUT", f"api/books/{bk['id']}", {"name": "Alices Liederbuch"})
    # a normal user gets no owner field
    m.cmd("WebDriver:Navigate", {"url": "about:blank"}); m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    wait(row("Alices Lied"))
    m.js("document.querySelector('#sel-mode').click()"); wait("document.querySelectorAll('#songs .selb').length > 2")
    m.js(f"{row('Alices Lied')}.querySelector('a').click()")
    m.js("document.querySelector('#sel-edit').click()"); wait("document.querySelector('#dlg-bulk').open"); time.sleep(0.8)
    check("users: no owner field in bulk edit", not m.js(f"return {shown('#bk-owner')}") and m.js(f"return {shown('#bk-vis')}"))
    m.js("document.querySelector('#bk-cancel').click()")
    login({"sub": "c-3", "preferred_username": "carol", "name": "Carol Admin", "groups": ["/admin"]})
    # bulk: give the legacy song (no owner) to alice
    m.cmd("WebDriver:Navigate", {"url": "about:blank"}); m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    wait(row("Abendlied"))
    check("legacy song has no owner", not m.js(f"return !!{row('Abendlied')}.querySelector('.own')"))
    m.js("document.querySelector('#sel-mode').click()"); wait("document.querySelectorAll('#songs .selb').length > 2")
    m.js(f"{row('Abendlied')}.querySelector('a').click()")
    m.js("document.querySelector('#sel-edit').click()"); wait("document.querySelector('#dlg-bulk').open")
    check("admins: owner field lists the users", wait(f"{shown('#bk-owner')} && [...document.querySelector('#bk-owner').options].some(o => o.textContent==='alice')"))
    m.js("const s=document.querySelector('#bk-owner'); s.value=[...s.options].find(o=>o.textContent==='alice').value")
    m.js("document.querySelector('#bk-apply').click()")
    check("new owner shown in the list", wait(f"{row('Abendlied')}.querySelector('.own') && {row('Abendlied')}.querySelector('.own').textContent==='👤 alice'"))
    m.js("document.querySelector('#sel-done').click()")
    # server settings -> alice
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/server"})
    wait("[...document.querySelectorAll('#u-list a')].some(a => a.textContent.includes('alice'))")
    m.js("[...document.querySelectorAll('#u-list a')].find(a => a.textContent.includes('alice')).click()")
    check("user page opens", wait("!document.querySelector('#v-user').hidden && document.querySelector('#ud-name').textContent==='Alice Wonder'"))
    songs = m.js("return [...document.querySelectorAll('#ud-songs .tt')].map(e=>e.textContent)")
    check("their songs incl. the reassigned one", sorted(songs) == ["Abendlied", "Alices Lied"], songs)
    check("their songbooks", m.js("return [...document.querySelectorAll('#ud-books .tt')].map(e=>e.textContent)") == ["Alices Liederbuch"])
    acts = m.js("return [...document.querySelectorAll('#ud-acts .tt')].map(e=>e.textContent)")
    check("activity: login, new song, songbook created/renamed", all(a in acts for a in ("angemeldet", "neu", "Liederbuch angelegt", "Liederbuch umbenannt")), acts)
    check("activity links to the song", m.js("return [...document.querySelectorAll('#ud-acts a')].some(a => a.getAttribute('href').includes('Alices%20Lied'))"))
    b.shot(f"user-page-{W}")
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/server/benutzer/c-3"})
    check("admin's own activity shows the owner change",
          wait("[...document.querySelectorAll('#ud-acts li')].some(li => li.textContent.includes('Besitzer geändert') && li.textContent.includes('Abendlied → alice'))"))
    check("no horizontal overflow", m.js("return document.documentElement.scrollWidth <= innerWidth"))
finally:
    b.close()
finish()
