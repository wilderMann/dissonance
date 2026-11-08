"""UI test for songbooks, print view, version history (headless Firefox via Marionette)."""
import base64, glob, json, os, signal, sys, time, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from browser import BASE, W, H, SHOTS, FIXTURES, EXAMPLES, Browser, check, finish, skip  # noqa: E402

tag = f"{W}"


b = Browser(capabilities={"unhandledPromptBehavior": "accept"})
m, wait = b.m, b.wait
try:
    shot = lambda name: open(os.path.join(SHOTS, f"{name}-{tag}.png"), "wb").write(
        base64.b64decode(m.cmd("WebDriver:TakeScreenshot", {"full": False})["value"]))
    nooverflow = lambda what: check(f"no horizontal overflow ({what})", m.js("return document.documentElement.scrollWidth <= innerWidth"),
                                    m.js("return [document.documentElement.scrollWidth, innerWidth]"))
    # stub dialogs: prompt/confirm answers controlled from the test
    stub = "window.confirm = () => true; window.prompt = (q, d) => window.__prompt || d;"

    # --- create a book
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/buecher"})
    m.js(stub)
    check("books view empty", wait("document.querySelector('#books .empty')"))
    m.js("document.querySelector('#nb-name').value='Lagerfeuer'; document.querySelector('#nb-go').click()")
    check("book created + opened", wait("location.hash.startsWith('#/buch/') && document.querySelector('#b-title').textContent==='Lagerfeuer'"))
    check("empty book: add box open", wait("!document.querySelector('#b-addbox').hidden"))
    check("add list shows 2 songs", wait("document.querySelectorAll('#b-add .pick').length===2"))
    m.js("document.querySelector('#b-add .pick').click()")
    check("first song added", wait("document.querySelectorAll('#b-songs li.row2').length===1"))
    m.js("document.querySelector('#b-add .pick').click()")
    check("second song added", wait("document.querySelectorAll('#b-songs li.row2').length===2"))
    order0 = m.js("return [...document.querySelectorAll('#b-songs .tt')].map(e=>e.textContent)")
    titles = lambda: m.js("return [...document.querySelectorAll('#b-songs .tt')].map(e=>e.textContent)")
    check("no reorder controls outside sort mode", not m.js("return !!document.querySelector('#b-songs .grip, #b-songs .acts')"))
    m.js("document.querySelector('#b-order').click()")
    check("sort mode: handles + sort buttons", wait("document.querySelectorAll('#b-songs .grip').length===2 && !document.querySelector('#b-orderbar').hidden"))
    # keyboard: arrow down on the first handle
    m.js("const g=document.querySelector('#b-songs .grip'); g.focus(); g.dispatchEvent(new KeyboardEvent('keydown', {key:'ArrowDown', bubbles:true}))")
    check("reorder by keyboard", wait("document.querySelector('#b-songs .tt').textContent===%r" % order0[1]), titles())
    # drag & drop with a real pointer: second row's handle above the first row
    grips = m.cmd("WebDriver:FindElements", {"using": "css selector", "value": "#b-songs .grip"})
    grips = grips["value"] if isinstance(grips, dict) else grips
    g2 = list(grips[1].values())[0]
    h = m.js("return document.querySelector('#b-songs li.row2').getBoundingClientRect().height")
    m.cmd("WebDriver:PerformActions", {"actions": [{"type": "pointer", "id": "mouse", "parameters": {"pointerType": "mouse"}, "actions": [
        {"type": "pointerMove", "origin": {"element-6066-11e4-a52e-4f735466cecf": g2}, "x": 0, "y": 0},
        {"type": "pointerDown", "button": 0},
        {"type": "pointerMove", "origin": "pointer", "x": 0, "y": -int(h * 0.4), "duration": 150},
        {"type": "pointerMove", "origin": "pointer", "x": 0, "y": -int(h * 0.8), "duration": 150},
        {"type": "pointerUp", "button": 0}]}]})
    m.cmd("WebDriver:ReleaseActions", {})
    check("reorder by drag & drop", wait("document.querySelector('#b-songs .tt').textContent===%r" % order0[0]), titles())
    m.js("document.querySelector('#b-orderbar [data-sort=title]').click()")
    check("sort by title", wait("JSON.stringify([...document.querySelectorAll('#b-songs .tt')].map(e=>e.textContent))===%r" % __import__('json').dumps(sorted(order0, key=str.casefold), ensure_ascii=False).replace(', ', ',')), titles())
    shot("book-sort")
    m.js("document.querySelector('#b-order-done').click()")
    check("sort mode off", wait("!document.querySelector('#b-songs .grip') && document.querySelector('#b-orderbar').hidden"))
    nooverflow("book"); shot("book")
    # reopening a book with songs: the add box is closed; the toggle opens it
    bid = m.js("return location.hash.split('/')[2]")
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/buecher"}); m.cmd("WebDriver:Navigate", {"url": BASE + "/#/buch/" + bid})
    check("book with songs: add box closed behind the toggle", wait("document.querySelector('#b-title').textContent.length && document.querySelector('#b-addbox').hidden")
          and m.js("return document.querySelector('#b-addtoggle').offsetParent !== null"))
    m.js("document.querySelector('#b-addtoggle').click()")
    check("toggle opens it", wait("!document.querySelector('#b-addbox').hidden && document.querySelector('#b-addtoggle').getAttribute('aria-expanded')==='true'"))
    m.js("document.querySelector('#b-addtoggle').click()")

    # --- play from the book: next/prev
    m.js("document.querySelector('#b-play').click()")
    check("plays first song of book", wait("document.querySelector('#s-title small:last-child') && document.querySelector('#s-title').textContent.includes('Lagerfeuer · 1/2')"),
          m.js("return document.querySelector('#s-title').textContent"))
    check("next visible, prev hidden", m.js("return !document.querySelector('#s-next').hidden && document.querySelector('#s-prev').hidden && !document.querySelector('#s-next-big').hidden"))
    check("back goes to book", m.js("return document.querySelector('#s-back').getAttribute('href').startsWith('#/buch/')"))
    nooverflow("song in book"); shot("song-in-book")
    m.js("document.querySelector('#s-next-big').click()")
    check("next song", wait("document.querySelector('#s-title').textContent.includes('2/2')"))
    check("prev visible, next hidden", m.js("return !document.querySelector('#s-prev').hidden && document.querySelector('#s-next').hidden"))
    song2 = m.js("return decodeURIComponent(location.hash.split('/').pop())")

    # --- books dialog in song view
    m.js("document.querySelector('#s-books').click()")
    check("dialog open with Lagerfeuer checked", wait("document.querySelector('#dlg-books').open && document.querySelector('#dlg-list input').checked"))
    m.js("document.querySelector('#dlg-new').value='Zweites Buch'; document.querySelector('#dlg-new-go').click()")
    check("new book from dialog, checked", wait("document.querySelectorAll('#dlg-list input:checked').length===2"))
    shot("dialog")
    m.js("document.querySelector('#dlg-close').click()")

    # --- edit twice -> history -> restore
    m.js("document.querySelector('#to-edit').click()")
    orig = m.js("return document.querySelector('#e-text').value")
    m.js("const t=document.querySelector('#e-text'); t.value=t.value.replace(/\\n/, '\\n{comment: Testkommentar}\\n'); t.oninput(); document.querySelector('#e-save').click()")
    check("saved v2", wait("!document.querySelector('#play').hidden && document.querySelector('#sheet').textContent.includes('Testkommentar')"))
    m.js("document.querySelector('#to-edit').click()")
    m.js("document.querySelector('#e-history').click()")
    check("history shows 2 versions", wait("document.querySelectorAll('#h-list > li').length===2"),
          m.js("return [...document.querySelectorAll('#h-list .ar')].map(e=>e.textContent)"))
    m.js("document.querySelector('#h-list > li .pick').click()")
    check("diff shows added line", wait("document.querySelector('#h-list .diff .add') && document.querySelector('#h-list .diff .add').textContent.includes('Testkommentar')"))
    nooverflow("history"); shot("history")
    m.js("document.querySelectorAll('#h-list > li .pick')[1].click()")
    check("restore button on older version", wait("document.querySelectorAll('#h-list .vbody')[1].querySelector('.ib.pri')"))
    m.js("document.querySelectorAll('#h-list .vbody')[1].querySelector('.tabs .ib:nth-child(2)').click()")
    check("diff to now", "Testkommentar" in m.js("return document.querySelectorAll('#h-list .vbody')[1].querySelector('.diff').textContent"))
    m.js(stub + "document.querySelectorAll('#h-list .vbody')[1].querySelector('.ib.pri').click()")
    check("restored -> song view", wait("!document.querySelector('#v-song').hidden && !document.querySelector('#play').hidden && document.querySelector('#sheet .c') && !document.querySelector('#sheet').textContent.includes('Testkommentar')"))
    m.js("document.querySelector('#to-edit').click()")
    check("restored content equals original", m.js("return document.querySelector('#e-text').value") == orig)
    m.js("document.querySelector('#e-cancel').click()")

    # --- delete + restore from deleted list
    m.js("document.querySelector('#to-edit').click()")
    m.js(stub + "document.querySelector('#e-delete').click()")
    check("deleted -> list", wait("location.hash==='#/' && document.querySelectorAll('#songs a').length===1"))
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/geloescht"})
    m.js(stub)
    check("deleted list has song", wait("document.querySelectorAll('#d-list li.row2').length===1"))
    nooverflow("deleted"); shot("deleted")
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/buecher"})
    m.js(stub)
    wait("document.querySelectorAll('#books a').length===2")
    m.js("document.querySelector('#books a').click()")
    check("book shows deleted song struck", wait("document.querySelector('#b-songs li.gone')"))
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/geloescht"})
    m.js(stub)
    wait("document.querySelectorAll('#d-list li.row2').length===1")
    m.js("document.querySelector('#d-list .acts .ib').click()")
    check("restored deleted song", wait("!document.querySelector('#v-song').hidden && decodeURIComponent(location.hash).endsWith(%r)" % song2), m.js("return location.hash"))

    # --- print view
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/buecher"})
    wait("document.querySelectorAll('#books a').length===2")
    bid = m.js("return [...document.querySelectorAll('#books a')].find(a=>a.textContent.includes('Lagerfeuer')).getAttribute('href').split('/')[2]")
    m.cmd("WebDriver:Navigate", {"url": BASE + f"/#/buch/{bid}/druck"})
    check("print view: 2 songs + toc", wait("document.querySelectorAll('#pbook .psong').length===2 && document.querySelectorAll('#pbook .toc li').length===2"))
    check("numbered titles", m.js("return document.querySelector('#pbook .psong .ttl').textContent.startsWith('1. ')"))
    check("document title = book name (PDF name)", m.js("return document.title") == "Lagerfeuer")
    nooverflow("print"); shot("print")
    pdf = base64.b64decode(m.cmd("WebDriver:Print", {"background": True})["value"])
    open(os.path.join(SHOTS, f"book-{tag}.pdf"), "wb").write(pdf)
    m.js("document.querySelector('#pr-cols').click()")
    check("two columns", wait("document.querySelector('#pbook').classList.contains('cols2')"))
    pdf = base64.b64decode(m.cmd("WebDriver:Print", {"background": True})["value"])
    open(os.path.join(SHOTS, f"book-cols-{tag}.pdf"), "wb").write(pdf)
    m.js("document.querySelector('#pr-cols').click()")
    # export links
    check("export links", m.js("return document.querySelector('#b-cho').getAttribute('href')").endswith("/export.cho"))
finally:
    b.close()
finish()
