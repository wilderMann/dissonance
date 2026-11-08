"""English UI: walk through the views and dialogs and look for German left in buttons, labels, tooltips, placeholders
(song content – titles, lyrics, editor text – is excluded)."""
import os, sys, time, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from browser import BASE, W, Browser, check, finish  # noqa: E402

SONG = urllib.parse.quote("Die Testband - Grüße aus Wien.cho")
API = ("const done=arguments[arguments.length-1]; fetch(arguments[0], {method: arguments[1], headers: {'Content-Type': 'application/json'},"
       " body: arguments[2] ? JSON.stringify(arguments[2]) : undefined}).then(r => r.json().then(j => done([r.status, j])))")
SCAN = r"""
const GERMAN = /[äöüÄÖÜß]|\b(der|die|das|und|nicht|ein|eine|einen|Lied|Lieder|Liederbuch|mit|für|auf|von|wird|wer|nur|bitte|Bitte|alle|noch|kein|keine|Speichern|Löschen|Zurück|Anmelden|Abbrechen|Schließen|Teilen|Drucken|Stimmen|Akkorde|Tonart|Verlauf|Bearbeiten|Spielen|Sortieren|Mehr|neu|öffentlich|privat)\b/;
const skip = e => e.closest('.sheet, textarea, #e-text, #e-back, .tt, .ar, #s-title, #b-title, #h-title, .diff, .lbl, .cm, .ttl, .meta, .dn, .gm, .tu-strings, .selb, .grip');
const vis = e => !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length) && getComputedStyle(e).visibility !== 'hidden';
const hits = new Set();
const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
for (let n; (n = walk.nextNode());) {
  const t = n.textContent.trim(), p = n.parentElement;
  if (t && p && vis(p) && !skip(p) && GERMAN.test(t)) hits.add('text: ' + t.slice(0, 80));
}
for (const e of document.querySelectorAll('[title], [placeholder], [aria-label]')) {
  if (skip(e) || !vis(e)) continue;
  for (const a of ['title', 'placeholder', 'aria-label']) { const v = e.getAttribute(a); if (v && GERMAN.test(v)) hits.add(a + ': ' + v.slice(0, 80)); }
}
return [...hits];
"""


def api(method, path, body=None):
    return m.cmd("WebDriver:ExecuteAsyncScript", {"script": API, "args": [path, method, body]})["value"]


b = Browser(lang="en-US,en", capabilities={"unhandledPromptBehavior": "accept"})
m, wait = b.m, b.wait
found = {}
scan = lambda where: found.__setitem__(where, m.js(SCAN))
try:
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    wait("document.querySelectorAll('#songs a').length>0")
    scan("song list")
    m.js("document.querySelector('#sel-mode').click()"); scan("song list, selection mode")
    m.js("document.querySelector('#sel-all').click(); document.querySelector('#sel-edit').click()")
    wait("document.querySelector('#dlg-bulk').open"); scan("bulk edit dialog")
    m.js("document.querySelector('#bk-cancel').click(); document.querySelector('#sel-done').click()")
    st, bk = api("POST", "api/books", {"name": "Test book"})
    songs = api("GET", "api/songs")[1]["songs"]
    api("POST", f"api/books/{bk['id']}/lied", {"song": songs[0]["id"], "add": True})
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/buecher"}); wait("document.querySelectorAll('#books a').length>0"); scan("songbook list")
    m.cmd("WebDriver:Navigate", {"url": BASE + f"/#/buch/{bk['id']}"}); wait("document.querySelector('#b-title').textContent==='Test book'")
    scan("songbook")
    m.js("document.querySelector('#b-more').click()"); scan("songbook ⋯ menu")
    m.js("document.querySelector('#b-export').click()"); wait("document.querySelector('#dlg-export').open"); scan("print/download dialog")
    m.js("document.querySelector('#ex-close').click()")
    m.js("document.querySelector('#b-campfire').click()"); wait("document.querySelector('#dlg-campfire').open"); scan("campfire dialog")
    m.js("document.querySelector('#cf2-close').click()")
    m.js("document.querySelector('#b-share').click()"); wait("document.querySelector('#dlg-share').open"); scan("share dialog")
    m.js("document.querySelector('#sh-close').click()")
    m.js("document.querySelector('#b-order').click()"); scan("songbook sort mode")
    m.js("document.querySelector('#b-order-done').click()")
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/lied/" + SONG}); wait("document.querySelector('#sheet .c')")
    scan("song")
    m.js("document.querySelector('#s-more').click()"); scan("song ⋯ menu"); m.js("document.querySelector('#s-more').click()")
    m.js("document.querySelector('#p-more') && document.querySelector('#p-more').click()"); scan("song ⋯ panel")
    m.js("document.querySelector('#to-edit').click()"); wait("!document.querySelector('#edit').hidden"); scan("editor")
    m.js("document.querySelector('#e-more').click()"); scan("editor ⋯ menu")
    m.js("document.querySelector('#e-history').click()"); wait("document.querySelectorAll('#h-list li').length")
    m.js("document.querySelector('#h-list .pick').click()"); scan("history")
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/import"}); wait("!document.querySelector('#v-import').hidden"); scan("import")
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/einstellungen"}); wait("!document.querySelector('#v-settings').hidden"); scan("settings")
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/geloescht"}); wait("!document.querySelector('#v-deleted').hidden"); scan("deleted songs")
    m.js("document.querySelector('#new-btn').click()"); scan("＋ menu")
    m.js("document.querySelector('#gear').click()"); scan("⚙ menu")
    m.js("[...document.querySelectorAll('#acct-menu button')].find(b=>b.textContent.includes('Tuner')).click()"); wait("document.querySelector('#dlg-tuner').open"); scan("tuner")
    for where, hits in found.items():
        check(f"no German in the English UI: {where}", not hits, hits)
finally:
    b.close()
finish()
