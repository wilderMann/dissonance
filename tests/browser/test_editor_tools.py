"""Editor insert buttons: syntax snippets and chord buttons."""
import base64, glob, json, os, signal, sys, time, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from browser import BASE, W, H, SHOTS, FIXTURES, EXAMPLES, Browser, check, finish, skip  # noqa: E402

tag = f"{W}"


b = Browser(capabilities={"unhandledPromptBehavior": "accept"})
m, wait = b.m, b.wait
try:
    btn = lambda grp, label: m.js("[...document.querySelectorAll('#%s .ib')].find(b=>b.textContent===arguments[0]).click()" % grp, label)
    val = lambda: m.js("return document.querySelector('#e-text').value")
    sel = lambda: m.js("const t=document.querySelector('#e-text'); return [t.selectionStart, t.selectionEnd]")
    setv = lambda v, a, b=None: m.js("const t=document.querySelector('#e-text'); t.value=arguments[0]; t.dispatchEvent(new Event('input')); t.focus(); t.setSelectionRange(arguments[1], arguments[2]);", v, a, a if b is None else b)
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/bearbeiten/" + urllib.request.quote("Die Testband - Grüße aus Wien.cho")})
    check("editor + buttons", wait("!document.querySelector('#edit').hidden && document.querySelectorAll('#e-syntax .ib').length===10"))
    chords = m.js("return [...document.querySelectorAll('#e-chords .chord')].map(b=>b.textContent)")
    check("chord buttons = chords of the song, in order", chords[:4] == ["Em", "D", "G", "B"], chords)
    b.shot(f"editor-tools-{W}")
    # chord at cursor + undo
    setv("[G]Hallo Welt\n", 9)
    btn("e-chords", "Em")
    check("chord inserted at cursor", val() == "[G]Hallo [Em]Welt\n" and sel() == [13, 13], [val(), sel()])
    m.js("document.querySelector('#e-text').focus(); document.execCommand('undo')")
    check("undo works", val() == "[G]Hallo Welt\n", val())
    check("chord list follows the text", wait("[...document.querySelectorAll('#e-chords .chord')].map(b=>b.textContent).join()==='G'"))
    # section around selected lines
    setv("Zeile 1\nZeile 2\n", 0, 15)
    btn("e-syntax", "Refrain")
    check("refrain wraps selection", val() == "{start_of_chorus: Refrain}\nZeile 1\nZeile 2\n{end_of_chorus}\n", val())
    # empty section in the middle of a line -> own lines, cursor inside
    setv("Text davor", 10)
    btn("e-syntax", "Strophe")
    v, s = val(), sel()
    check("verse on own lines, cursor inside", v == "Text davor\n{start_of_verse: Strophe}\n\n{end_of_verse}\n" and v[:s[0]].endswith("Strophe}\n"), [v, s])
    # header: title at the top, artist after it, jump to existing one
    setv("{key: G}\n[G]la\n", 14)
    btn("e-syntax", "Titel")
    check("title at top, cursor in value", val().startswith("{title: }\n{key: G}") and sel() == [8, 8], [val(), sel()])
    m.js("document.execCommand('insertText', false, 'Mein Lied')")
    btn("e-syntax", "Interpret")
    check("artist after header block", val() == "{title: Mein Lied}\n{key: G}\n{artist: }\n[G]la\n", val())
    btn("e-syntax", "Titel")
    check("existing title selected instead of a second one", val().count("{title") == 1 and sel() == [8, 17], sel())
    # comment wraps selection; new chord via prompt
    setv("Langsam\n", 0, 7)
    btn("e-syntax", "Kommentar")
    check("comment around selection", val() == "{comment: Langsam}\n", val())
    m.js("window.prompt = () => 'Cadd9'"); setv("x", 1)
    btn("e-chords", "＋ Akkord")
    check("new chord via +", val() == "x[Cadd9]" and wait("[...document.querySelectorAll('#e-chords .chord')].some(b=>b.textContent==='Cadd9')"), val())
    check("preview + dirty updated", m.js("return document.querySelector('#e-preview').textContent.includes('Cadd9')"))
    check("no horizontal overflow", m.js("return document.documentElement.scrollWidth <= innerWidth"))
finally:
    b.close()
finish()
