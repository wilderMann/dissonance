"""Collaboration: Alice invites Bob to a private song and songbook; Bob edits, the history says who; importing a song
that exists shows the differences and lets him take the new version or keep both."""
import json, os, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from browser import BASE, W, Browser, check, finish  # noqa: E402

WHO = os.path.join(os.environ["SONG_DIR"], ".who.json")  # read by login_server.py
API = ("const done=arguments[arguments.length-1]; fetch(arguments[0], {method: arguments[1], headers: {'Content-Type': 'application/json'},"
       " body: arguments[2] ? JSON.stringify(arguments[2]) : undefined}).then(r => r.json().then(j => done([r.status, j])))")
ALICE = {"sub": "a-1", "preferred_username": "alice", "name": "Alice"}
BOB = {"sub": "b-2", "preferred_username": "bob", "name": "Bob"}


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


b = Browser(capabilities={"unhandledPromptBehavior": "accept"})
m, wait = b.m, b.wait
vis = lambda sel: m.js("const e=document.querySelector(arguments[0]); return !!e && e.offsetParent !== null", sel)
try:
    login(BOB)  # Bob has signed in once, so Alice can pick him
    login(ALICE)
    st, song = api("POST", "api/songs", {"content": "{title: Gemeinsam}\n{artist: Band}\n[C]Erste [G]Zeile\n", "public": False})
    st, bk = api("POST", "api/books", {"name": "Proben", "public": False})
    api("POST", f"api/books/{bk['id']}/lied", {"song": song["id"], "add": True})
    # song: Alice opens the editor -> 👥 Mitarbeit -> picks Bob
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/bearbeiten/" + song["file"]})
    wait("!document.querySelector('#edit').hidden"); m.js("document.querySelector('#e-more').click()")
    check("owner sees 👥, visibility and delete in the editor's ⋯", vis("#e-collab") and vis("#e-vis") and vis("#e-delete"))
    m.js("document.querySelector('#e-collab').click()")
    check("collaboration dialog lists Bob", wait("document.querySelector('#dlg-collab').open && document.querySelector('#co-list').textContent.includes('Bob')"))
    check("not herself", "Alice" not in m.js("return document.querySelector('#co-list').textContent"))
    b.shot(f"collab-dialog-{W}")
    m.js("const cb=[...document.querySelectorAll('#co-list label')].find(l=>l.textContent.includes('Bob')).querySelector('input'); cb.click()")
    m.js("document.querySelector('#co-save').click()")
    check("saved", wait("!document.querySelector('#dlg-collab').open"))
    check("stored", [u["username"] for u in api("GET", f"api/collab/song/{song['id']}")[1]["users"]] == ["bob"])
    # book: Alice sees 👥 in the book, invites Bob through the API (same dialog)
    m.cmd("WebDriver:Navigate", {"url": BASE + f"/#/buch/{bk['id']}"})
    wait("document.querySelector('#b-title').textContent==='Proben'")
    m.js("document.querySelector('#b-more').click()")
    check("owner: 👥 and delete in the ⋯ menu", wait("!document.querySelector('#b-menu').hidden") and vis("#b-collab") and vis("#b-delete"))
    m.js("document.querySelector('#b-more').click()")
    api("PUT", f"api/collab/book/{bk['id']}", {"users": ["b-2"]})

    # Bob: sees the private song marked as shared work, may edit, may not delete or change visibility
    login(BOB)
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    check("Bob sees the song with 👥", wait("[...document.querySelectorAll('#songs a')].some(a => a.textContent.includes('Gemeinsam') && a.textContent.includes('gemeinsam'))"))
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/bearbeiten/" + song["file"]})
    check("Bob can edit", wait("!document.querySelector('#edit').hidden"))
    m.js("document.querySelector('#e-more').click()")
    check("…but no delete, visibility or 👥", not vis("#e-delete") and not vis("#e-vis") and not vis("#e-collab"))
    m.js("const t=document.querySelector('#e-text'); t.value=t.value.replace('Zeile', 'Zeile von Bob'); t.dispatchEvent(new Event('input'))")
    m.js("document.querySelector('#e-save').click()")
    check("saved by Bob", wait("!document.querySelector('#play').hidden && document.querySelector('#sheet').textContent.includes('von Bob')"))
    m.js("document.querySelector('#to-edit').click()")
    wait("!document.querySelector('#edit').hidden")
    m.js("document.querySelector('#e-history').click()")
    check("history from the editor, with names", wait("location.hash.startsWith('#/verlauf/') && document.querySelectorAll('#h-list li').length===2"))
    rows = m.js("return [...document.querySelectorAll('#h-list .ar')].map(e=>e.textContent)")
    check("who changed what (by nick)", "von bob" in rows[0] and "von alice" in rows[1], rows)
    m.js("document.querySelector('#h-list .pick').click()")
    check("diff of Bob's change", wait("[...document.querySelectorAll('#h-list .diff .add')].some(e=>e.textContent.includes('von Bob'))"))
    b.shot(f"collab-history-{W}")
    # the book: Bob may edit it, but not delete/share-manage it
    m.cmd("WebDriver:Navigate", {"url": BASE + f"/#/buch/{bk['id']}"})
    check("Bob sees the private book", wait("document.querySelector('#b-title').textContent==='Proben'"))
    m.js("document.querySelector('#b-more').click()")
    check("Bob: rename yes, delete/visibility/👥/campfire no", wait("!document.querySelector('#b-menu').hidden") and vis("#b-rename")
          and not vis("#b-delete") and not vis("#b-vis") and not vis("#b-collab") and not vis("#b-campfire"))
    m.js("document.querySelector('#b-more').click()")

    # import a song that exists: the difference, then "take the new version" -> next version of the same song
    tmp = tempfile.mkdtemp(prefix="diss-imp-")
    path = os.path.join(tmp, "Band - Gemeinsam.cho")
    with open(path, "w") as f:
        f.write("{title: Gemeinsam}\n{artist: Band}\n[C]Erste [G]Zeile von Bob\n[F]Neue zweite Zeile\n")
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/import"})
    m.js("document.querySelector('[data-src=cho]').click()")
    eid = list(m.cmd("WebDriver:FindElement", {"using": "css selector", "value": "#chofiles"})["value"].values())[0]
    m.cmd("WebDriver:ElementSendKeys", {"id": eid, "text": path})
    m.js("document.querySelector('#go').click()")
    wait("document.querySelectorAll('#out .result').length===1")
    m.js("document.querySelector('#out .result h2 .ib.pri').click()")
    check("conflict dialog with the difference", wait("document.querySelector('#dlg-conflict').open && document.querySelector('#cf-diff .add')"))
    check("diff shows the new line", "Neue zweite Zeile" in m.js("return document.querySelector('#cf-diff .add').textContent"))
    check("all four choices", all(vis(s) for s in ("#cf-new", "#cf-keep", "#cf-both", "#cf-rename")))
    b.shot(f"import-conflict-{W}")
    m.js("document.querySelector('#cf-new').click()")
    check("saved as new version", wait("document.querySelector('#out .result a.ib')"))
    st, h = api("GET", f"api/history/{song['id']}")
    check("history: imported, by bob", (h["versions"][0]["action"], h["versions"][0]["by"]) == ("importiert", "bob"), h["versions"][0])
    # again with other text -> keep both
    with open(path, "w") as f:
        f.write("{title: Gemeinsam}\n{artist: Band}\n[Am]Ganz anders\n")
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/import"})
    m.js("document.querySelector('[data-src=cho]').click()")
    eid = list(m.cmd("WebDriver:FindElement", {"using": "css selector", "value": "#chofiles"})["value"].values())[0]
    m.js("document.querySelector('#chofiles').value=''")
    m.cmd("WebDriver:ElementSendKeys", {"id": eid, "text": path})
    m.js("document.querySelector('#go').click()")
    wait("document.querySelectorAll('#out .result').length===1 && !document.querySelector('#go').disabled")
    m.js("document.querySelector('#out .result h2 .ib.pri').click()")
    wait("document.querySelector('#dlg-conflict').open")
    m.js("document.querySelector('#cf-both').click()")
    check("keep both -> (2)", wait("document.querySelector('#out .result a.ib') && document.querySelector('#out .result a.ib').getAttribute('href').includes('(2)')"),
          m.js("const a=document.querySelector('#out .result a.ib'); return a && a.getAttribute('href')"))
    check("original untouched", "Ganz anders" not in api("GET", "api/songs/" + song["file"])[1]["content"])
finally:
    b.close()
finish()
