"""Tablet widths (iPad portrait/landscape): nothing may stick out on the left or make the page wider than the screen –
header with a long account name, song list, songbook, song, editor."""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from browser import BASE, W, Browser, check, finish  # noqa: E402

WHO = os.path.join(os.environ["SONG_DIR"], ".who.json")
PROBE = r"""
const vw = document.documentElement.clientWidth, out = [];
for (const e of document.querySelectorAll('body *')) {
  if (!(e.offsetWidth || e.offsetHeight) || e.closest('dialog:not([open]), [hidden]')) continue;
  let sc = false;  // inside a sideways-scrolling toolbar (editor on phones): meant to be wider
  for (let a = e.parentElement; a && a !== document.body; a = a.parentElement) if (a.tagName !== 'NAV' && /auto|scroll/.test(getComputedStyle(a).overflowX)) { sc = true; break; }
  if (sc) continue;
  const r = e.getBoundingClientRect();
  const nm = x => x.id ? '#' + x.id : x.tagName.toLowerCase() + '.' + [...x.classList].join('.');
  if (r.width && (r.left < -1 || r.right > vw + 1)) out.push(nm(e) + (e.parentElement ? ' in ' + nm(e.parentElement) : '') + ' "' + (e.textContent || '').trim().slice(0, 14) + '" ' + Math.round(r.left) + '..' + Math.round(r.right));
}
const nav = document.querySelector('.top nav');
if (nav.scrollWidth > nav.clientWidth + 1) out.push('header nav needs scrolling: ' + nav.scrollWidth + ' > ' + nav.clientWidth);
return [vw, document.documentElement.scrollWidth, out.slice(0, 8)];
"""
b = Browser(capabilities={"unhandledPromptBehavior": "accept"})
m, wait = b.m, b.wait
try:
    json.dump({"sub": "a-1", "preferred_username": "maximiliane.mustermann", "name": "Maximiliane Mustermann-Langername"}, open(WHO, "w"))
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    m.js("setTimeout(() => document.querySelector('#acct').click(), 50)"); time.sleep(2)
    wait("document.querySelector('#acct').textContent.includes('Maximiliane')", 10)
    # rows with everything at once: long title, artist, private, instrument, key, owner (like a real collection)
    API = ("const done=arguments[arguments.length-1]; fetch(arguments[0], {method: 'POST', headers: {'Content-Type': 'application/json'},"
           " body: JSON.stringify(arguments[1])}).then(r => r.json().then(done))")
    for t in ("Ein ziemlich langer Liedtitel ohne Ende", "Supercalifragilisticexpialidocious", "Kurz"):
        m.cmd("WebDriver:ExecuteAsyncScript", {"script": API, "args": ["api/songs", {"content": "{title: %s}\n{artist: Eine sehr lange Interpretenbezeichnung}\n{key: F#m}\n{x_instrument: ukulele}\n[C]x\n" % t, "public": False}]})
    views = [("song list", "/#/"), ("songbooks", "/#/buecher"), ("song", "/#/lied/Die%20Testband%20-%20Gr%C3%BC%C3%9Fe%20aus%20Wien.cho"),
             ("editor", "/#/bearbeiten/Die%20Testband%20-%20Gr%C3%BC%C3%9Fe%20aus%20Wien.cho"), ("import", "/#/import"), ("settings", "/#/einstellungen")]
    for name, url in views:
        m.cmd("WebDriver:Navigate", {"url": BASE + url}); time.sleep(0.8)
        vw, sw, out = m.js(PROBE)
        check(f"{name} @{W}: nothing cut off left/right, no horizontal scroll", sw <= vw + 1 and not out, (vw, sw, out))
    b.shot(f"tablet-{W}")
finally:
    b.close()
finish()
