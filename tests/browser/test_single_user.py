"""Single-user server (no login): nothing that only makes sense with several people shows up – no visibility,
share links, campfire mode or collaborators; bulk edit offers no owner while no users exist."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from browser import BASE, W, Browser, check, finish  # noqa: E402

API = ("const done=arguments[arguments.length-1]; fetch(arguments[0], {method: arguments[1], headers: {'Content-Type': 'application/json'},"
       " body: arguments[2] ? JSON.stringify(arguments[2]) : undefined}).then(r => r.json().then(j => done([r.status, j])))")
shown = lambda sel: f"(e => !!e && e.offsetParent !== null && getComputedStyle(e).display !== 'none')(document.querySelector('{sel}'))"

b = Browser()
m, wait = b.m, b.wait
api = lambda method, path, body=None: m.cmd("WebDriver:ExecuteAsyncScript", {"script": API, "args": [path, method, body]})["value"]
try:
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    wait("document.querySelectorAll('#songs li.row2').length===2")
    check("no account button", m.js("return document.querySelector('#acct').hidden"))
    st, bk = api("POST", "api/books", {"name": "Mein Buch"})
    m.cmd("WebDriver:Navigate", {"url": BASE + f"/#/buch/{bk['id']}"})
    wait("document.querySelector('#b-title').textContent==='Mein Buch'")
    m.js("document.querySelector('#b-more').click()")
    wait("!document.querySelector('#b-menu').hidden")
    check("songbook menu: print, rename, delete", m.js(f"return {shown('#b-export')} && {shown('#b-rename')} && {shown('#b-delete')}"))
    check("songbook menu: no share, campfire, visibility, collaborators",
          not m.js(f"return {shown('#b-share')} || {shown('#b-campfire')} || {shown('#b-vis')} || {shown('#b-collab')}"))
    check("no campfire badge", not m.js(f"return {shown('#b-fire-badge')}"))
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/neu"})
    wait("!document.querySelector('#edit').hidden")
    check("editor: no visibility, no collaborators", not m.js(f"return {shown('#e-vis')} || {shown('#e-collab')}"))
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/import"})
    wait("!document.querySelector('#v-import').hidden")
    check("import: no visibility", not m.js("return [...document.querySelectorAll('#v-import label')].some(l => l.offsetParent && l.textContent.includes('Sichtbar'))"))
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    wait("document.querySelectorAll('#songs li.row2').length===2")
    m.js("document.querySelector('#sel-mode').click()")
    m.js("document.querySelector('#sel-all').click()")
    m.js("document.querySelector('#sel-edit').click()")
    wait("document.querySelector('#dlg-bulk').open")
    time.sleep(0.5)
    check("bulk edit: key, songbook, delete", m.js(f"return {shown('#bk-keymode')} && {shown('#bk-bookmode')}"))
    check("bulk edit: no visibility, collaborators or owner (no users)",
          not m.js(f"return {shown('#bk-vis')} || {shown('#bk-comode')} || {shown('#bk-owner')}"))
    b.shot(f"single-bulk-{W}")
    m.js("document.querySelector('#bk-cancel').click()")
    check("no private tags anywhere", "🔒" not in m.js("return document.body.innerText"))
    check("no horizontal overflow", m.js("return document.documentElement.scrollWidth <= innerWidth"))
finally:
    b.close()
finish()
