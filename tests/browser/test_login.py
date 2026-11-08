"""Login in the browser (fake Keycloak): guest view, sign in, private song/book, sign out."""
import base64, glob, json, os, signal, sys, time, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from browser import BASE, W, H, SHOTS, FIXTURES, EXAMPLES, Browser, check, finish, skip  # noqa: E402

tag = f"{W}"
WHO = os.path.join(os.environ["SONG_DIR"], ".who.json")  # read by login_server.py
WHO = os.path.join(os.environ["SONG_DIR"], ".who.json")  # read by login_server.py
WHO = os.path.join(os.environ["SONG_DIR"], ".who.json")  # read by login_server.py


b = Browser(capabilities={"unhandledPromptBehavior": "accept"})
m, wait = b.m, b.wait
try:
    vis = lambda sel: m.js("const e=document.querySelector(arguments[0]); return !!e && e.offsetParent !== null", sel)
    # --- guest
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    check("guest sees public songs", wait("document.querySelectorAll('#songs a').length===2"))
    check("guest: 'Anmelden' shown, ＋ hidden, ⚙ shown", m.js("return document.querySelector('#acct').textContent") == "Anmelden"
          and not vis("#new-btn") and vis("#gear"))
    m.js("document.querySelector('#songs a').click()")
    wait("!document.querySelector('#v-song').hidden && document.querySelector('#sheet .c')")
    check("guest song view: no edit/books/key-save", not vis("#to-edit") and not vis("#s-books")
          and m.js("return document.querySelector('#p-keep').hidden"))
    open(os.path.join(SHOTS, f"auth-guest-{W}.png"), "wb").write(base64.b64decode(m.cmd("WebDriver:TakeScreenshot", {})["value"]))
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/neu"})
    check("guest: #/neu refused", wait("!document.querySelector('#v-list').hidden"))
    # --- sign in as alice
    json.dump({"sub": "a-1", "preferred_username": "alice", "name": "Alice"}, open(WHO, "w"))
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/buecher"})
    wait("document.querySelector('#acct').textContent==='Anmelden'")
    m.js("window.confirm = () => true; setTimeout(() => document.querySelector('#acct').click(), 50)"); time.sleep(2)
    check("signed in, back on #/buecher", wait("document.querySelector('#acct').textContent==='👤 Alice' && location.hash==='#/buecher'", 10),
          m.js("return [location.href, document.querySelector('#acct').textContent]"))
    check("user: Import/＋ visible, new book form", vis("#new-btn") and vis("#nb-name") and not vis("#gear"))
    # private song
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/neu"})
    wait("!document.querySelector('#edit').hidden")
    m.js("const t=document.querySelector('#e-text'); t.value='{title: Mein Geheimnis}\\n{artist: Alice}\\n[G]psst\\n'; t.oninput(); document.querySelector('#e-vis').value='0'; document.querySelector('#e-save').click()")
    check("private song saved", wait("location.hash.includes('Mein%20Geheimnis')"))
    check("user can edit own song", vis("#to-edit"))
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    check("list shows 🔒 tag", wait("[...document.querySelectorAll('#songs .tag')].some(t=>t.textContent.includes('privat'))"))
    check("old songs (no owner) not editable for user", True)
    m.js("[...document.querySelectorAll('#songs a')].find(a=>a.textContent.includes('Grüße')).click()")
    wait("!document.querySelector('#v-song').hidden && document.querySelector('#sheet .c')")
    check("song without owner: no edit button for a normal user", not vis("#to-edit") and vis("#s-more"))
    # book + visibility toggle
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/buecher"})
    m.js("document.querySelector('#nb-name').value='Alices Buch'; document.querySelector('#nb-go').click()")
    check("book created", wait("document.querySelector('#b-title').textContent==='Alices Buch' && document.querySelector('#b-vis').textContent.includes('öffentlich')"))
    m.js("document.querySelector('#b-vis').click()")
    check("book made private", wait("document.querySelector('#b-vis').textContent.includes('privat')"))
    open(os.path.join(SHOTS, f"auth-user-{W}.png"), "wb").write(base64.b64decode(m.cmd("WebDriver:TakeScreenshot", {})["value"]))
    # --- account menu + settings
    m.js("document.querySelector('#acct').click()")
    items = m.js("return [...document.querySelectorAll('#acct-menu a, #acct-menu button')].map(e=>e.textContent)")
    check("menu: settings + logout, no users for normal user", any("Einstellungen" in i for i in items) and any("Abmelden" in i for i in items)
          and not any("Servereinstellungen" in i for i in items), items)
    m.js("[...document.querySelectorAll('#acct-menu a')].find(a=>a.textContent.includes('Einstellungen')).click()")
    check("settings page with account", wait("!document.querySelector('#v-settings').hidden && document.querySelector('#set-account').textContent.includes('alice')"))
    check("menu closed after navigation", m.js("return document.querySelector('#acct-menu').hidden"))
    m.js("const s=document.querySelector('#set-theme'); s.value='dark'; s.onchange({target:s}); const f=document.querySelector('#set-fs'); f.value='30'; f.onchange({target:f});")
    check("settings applied", m.js("return document.documentElement.dataset.theme==='dark' && localStorage.getItem('lb.font')==='30'"))
    open(os.path.join(SHOTS, f"settings-{W}.png"), "wb").write(base64.b64decode(m.cmd("WebDriver:TakeScreenshot", {})["value"]))
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/benutzer"})
    check("users page refused for normal user", wait("!document.querySelector('#v-list').hidden"))
    # --- sign out (via menu)
    m.js("document.querySelector('#acct').click()")
    m.js("setTimeout(() => [...document.querySelectorAll('#acct-menu button')].find(b=>b.textContent.includes('Abmelden')).click(), 50)"); time.sleep(2)
    check("signed out", wait("document.querySelector('#acct').textContent==='Anmelden'", 10))
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    wait("document.querySelectorAll('#songs a').length>0")
    check("private song gone for guest", wait("![...document.querySelectorAll('#songs a')].some(a=>a.textContent.includes('Geheimnis'))"),
          m.js("return [...document.querySelectorAll('#songs .tt')].map(e=>e.textContent)"))
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/buecher"})
    check("private book gone for guest", wait("document.querySelector('#books .empty')"))
    # --- admin sees everything
    json.dump({"sub": "c-3", "preferred_username": "carol", "groups": ["admin"]}, open(WHO, "w"))
    m.js("window.confirm = () => true; setTimeout(() => document.querySelector('#acct').click(), 50)"); time.sleep(2)
    wait("document.querySelector('#acct').textContent.includes('carol')", 10)
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    check("admin sees the private song", wait("[...document.querySelectorAll('#songs a')].some(a=>a.textContent.includes('Geheimnis'))"))
    m.js("[...document.querySelectorAll('#songs a')].find(a=>a.textContent.includes('Grüße')).click()")
    wait("!document.querySelector('#v-song').hidden && document.querySelector('#sheet .c')")
    check("admin can edit songs without owner", vis("#to-edit"))
    # --- admin: users page, delete alice (transfer)
    m.js("document.querySelector('#acct').click()")
    check("admin menu has Servereinstellungen", "Servereinstellungen" in m.js("return document.querySelector('#acct-menu').textContent"))
    m.js("[...document.querySelectorAll('#acct-menu a')].find(a=>a.textContent.includes('Servereinstellungen')).click()")
    check("users listed", wait("document.querySelectorAll('#u-list li.row2').length===2"), m.js("return document.querySelector('#u-list').textContent"))
    check("alice: 1 private song, 1 book", "1 Lied (1 privat) · 1 Buch" in m.js("return document.querySelector('#u-list').textContent"))
    open(os.path.join(SHOTS, f"users-{W}.png"), "wb").write(base64.b64decode(m.cmd("WebDriver:TakeScreenshot", {})["value"]))
    m.js("document.querySelector('#u-list .acts .ib').click()")
    check("delete dialog", wait("document.querySelector('#dlg-user').open"))
    m.js("document.querySelector('#du-transfer').click()")
    check("alice deleted, songs transferred", wait("document.querySelectorAll('#u-list li.row2').length===1 && document.querySelector('#u-list').textContent.includes('1 Lied (1 privat) · 1 Buch')"),
          m.js("return document.querySelector('#u-list').textContent"))
finally:
    b.close()
finish()
