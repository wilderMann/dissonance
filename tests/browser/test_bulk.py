"""Bulk edit: select songs in the list, change visibility + key, add to a songbook, delete; owner shown by nick."""
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


b = Browser(capabilities={"unhandledPromptBehavior": "accept"})
m, wait = b.m, b.wait
rows = "[...document.querySelectorAll('#songs li.row2')]"
row = lambda t: f"{rows}.find(li => li.querySelector('.tt').textContent === '{t}')"
try:
    login({"sub": "b-2", "preferred_username": "bob", "name": "Bob Builder"})
    api("POST", "api/songs", {"content": "{title: Bobs Lied}\n[C]x\n"})
    login({"sub": "a-1", "preferred_username": "alice", "name": "Alice Wonder"})
    for t in ("Sammel Eins", "Sammel Zwei", "Sammel Drei"):
        api("POST", "api/songs", {"content": "{title: %s}\n{artist: Alice}\n[C]Hallo [G]Welt\n" % t})
    st, bk = api("POST", "api/books", {"name": "Sammelbuch"})
    m.cmd("WebDriver:Navigate", {"url": "about:blank"}); m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    wait(f"{row('Sammel Eins')}")
    check("owner shown by nick (not full name)", m.js(f"return {row('Bobs Lied')}.querySelector('.own').textContent") == "👤 bob")
    check("own songs show the owner too", m.js(f"return {row('Sammel Eins')}.querySelector('.own').textContent") == "👤 alice")
    # selection mode
    m.js("document.querySelector('#sel-mode').click()")
    check("selection bar + checkboxes", wait("!document.querySelector('#selbar').hidden && document.querySelectorAll('#songs .selb').length > 3"))
    check("someone else's song not selectable", m.js(f"return {row('Bobs Lied')}.querySelector('.selb').disabled"))
    for t in ("Sammel Eins", "Sammel Zwei"):
        m.js(f"{row(t)}.querySelector('a').click()")
    check("2 selected, no navigation", m.js("return document.querySelector('#sel-count').textContent").startswith("2 ") and m.js("return location.hash") in ("#/", ""))
    b.shot(f"bulk-select-{W}")
    m.js("document.querySelector('#sel-edit').click()")
    check("dialog opens", wait("document.querySelector('#dlg-bulk').open && document.querySelector('#bk-book').options.length > 0"))
    m.js("""const set=(id,v)=>{const e=document.querySelector(id); e.value=v; e.dispatchEvent(new Event('change'))};
      set('#bk-vis','0'); set('#bk-keymode','set'); document.querySelector('#bk-key').value='G';
      set('#bk-bookmode','add'); set('#bk-book', String(arguments[0])); set('#bk-tr','2');""", bk["id"])
    b.shot(f"bulk-dialog-{W}")
    m.js("document.querySelector('#bk-apply').click()")
    check("applied", wait("!document.querySelector('#dlg-bulk').open && document.querySelector('#toast').textContent.includes('2 Lieder geändert')"),
          m.js("return document.querySelector('#bk-result').textContent"))
    songs = {s["title"]: s for s in api("GET", "api/songs")[1]["songs"]}
    check("private + key G", all(not songs[t]["public"] and songs[t]["key"] == "G" for t in ("Sammel Eins", "Sammel Zwei")) and songs["Sammel Drei"]["public"])
    f = songs["Sammel Eins"]["file"]
    txt = api("GET", "api/songs/" + f)[1]["content"]
    check("transpose written, chords unchanged", "{transpose: 2}" in txt and "[C]Hallo [G]Welt" in txt, txt)
    check("in the songbook", [s["title"] for s in api("GET", f"api/books/{bk['id']}")[1]["songs"]] == ["Sammel Eins", "Sammel Zwei"])
    check("list shows the private tag", wait(f"{row('Sammel Eins')}.textContent.includes('privat')"))
    # bulk delete
    m.js(f"{row('Sammel Drei')}.querySelector('a').click()")
    m.js("document.querySelector('#sel-none').click()")
    m.js(f"{row('Sammel Drei')}.querySelector('a').click()")
    m.js("window.confirm = () => true; document.querySelector('#sel-edit').click()")
    wait("document.querySelector('#dlg-bulk').open")
    m.js("document.querySelector('#bk-del').checked = true; document.querySelector('#bk-apply').click()")
    check("deleted", wait(f"!{row('Sammel Drei')} && !document.querySelector('#dlg-bulk').open"))
    check("in the trash", any(s["title"] == "Sammel Drei" for s in api("GET", "api/deleted")[1]["songs"]))
    m.js("document.querySelector('#sel-done').click()")
    check("selection mode off", wait("document.querySelector('#selbar').hidden && !document.querySelector('#songs .selb')"))
    # song view: owner by nick
    m.js(f"{row('Bobs Lied')}.querySelector('a').click()")
    check("song view: 'von bob'", wait("document.querySelector('#s-title').textContent.includes('von bob')"))
    # own version of bob's song
    m.js("document.querySelector('#s-more').click()")
    check("⧉ own version offered in the song's ⋯", m.js("return document.querySelector('#s-copy').offsetParent !== null"))
    m.js("document.querySelector('#s-copy').click()")
    check("copy opens in the editor as alice's own song", wait("!document.querySelector('#edit').hidden && location.hash.includes('Bobs%20Lied%20(alice)')"),
          m.js("return location.hash"))
    check("⧉ hidden in the editor", m.js("return document.querySelector('#s-copy').offsetParent === null"))
    m.js("const t=document.querySelector('#e-text'); t.value=t.value.replace('[C]x','[G]Alices Fassung'); t.dispatchEvent(new Event('input'))")
    m.js("document.querySelector('#e-save').click()")
    check("saved under the same name", wait("!document.querySelector('#play').hidden && location.hash.includes('Bobs%20Lied%20(alice)') && document.querySelector('#sheet').textContent.includes('Alices Fassung')"),
          m.js("return location.hash"))
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    wait("[...document.querySelectorAll('#songs li.row2 .tt')].filter(e => e.textContent==='Bobs Lied').length === 2")
    owners = m.js("return [...document.querySelectorAll('#songs li.row2')].filter(li => li.querySelector('.tt').textContent==='Bobs Lied').map(li => li.querySelector('.own').textContent)")
    check("list: the song twice, told apart by the owner", sorted(owners) == ["👤 alice", "👤 bob"], owners)
finally:
    b.close()
finish()
