"""Editor whitespace markers: alignment with the textarea, toggle, persistence."""
import base64, glob, json, os, signal, sys, time, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from browser import BASE, W, H, SHOTS, FIXTURES, EXAMPLES, Browser, check, finish, skip  # noqa: E402

tag = f"{W}"


b = Browser(capabilities={"unhandledPromptBehavior": "accept"})
m, wait = b.m, b.wait
try:
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/bearbeiten/" + urllib.request.quote("Die Testband - Grüße aus Wien.cho")})
    check("markers shown by default", wait("document.querySelectorAll('#e-back .sp').length>100"))
    stats = m.js("""const ta=document.querySelector('#e-text'), b=document.querySelector('#e-back');
      return { spaces: (ta.value.match(/ /g)||[]).length, sp: b.querySelectorAll('.sp').length,
               lines: ta.value.split('\\n').length - 1, nl: b.querySelectorAll('.nl').length,
               taH: ta.scrollHeight, bH: b.scrollHeight, w: [ta.clientWidth, b.clientWidth], on: document.querySelector('#e-ws').classList.contains('on') }""")
    check("one dot per space, one ¶ per line end", stats["spaces"] == stats["sp"] and stats["lines"] == stats["nl"], stats)
    check("same wrapping (content heights equal)", abs(stats["taH"] - stats["bH"]) <= 22, stats)  # back has 1 extra line
    # long line + tab: check the marker of the last space sits where the textarea text is (via a mirrored caret test)
    m.js("""const ta=document.querySelector('#e-text'); ta.value = 'Ein\\tTab und eine sehr lange Zeile '.repeat(6) + '\\n' + ta.value;
            ta.dispatchEvent(new Event('input'));""")
    wait("document.querySelector('#e-back .tb')")
    m.js("const ta=document.querySelector('#e-text'); ta.scrollTop = 300; ta.dispatchEvent(new Event('scroll'));")
    st2 = m.js("""const ta=document.querySelector('#e-text'), b=document.querySelector('#e-back');
      return { taH: ta.scrollHeight, bH: b.scrollHeight, top: [ta.scrollTop, b.scrollTop], tabs: b.querySelectorAll('.tb').length }""")
    check("long wrapped line: heights still equal", abs(st2["taH"] - st2["bH"]) <= 22, st2)
    check("scroll synced", st2["top"][0] == st2["top"][1], st2)
    m.js("const ta=document.querySelector('#e-text'); ta.scrollTop = 0; ta.dispatchEvent(new Event('scroll'));")
    b.shot(f"ws-{W}")
    m.js("document.querySelector('#e-ws').click()")
    check("toggle hides", m.js("return getComputedStyle(document.querySelector('#e-back')).display") == "none")
    m.cmd("WebDriver:Navigate", {"url": "about:blank"})
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/bearbeiten/" + urllib.request.quote("Die Testband - Grüße aus Wien.cho")})
    wait("document.querySelector('#e-text').value.length>100")
    check("hidden state remembered", m.js("return getComputedStyle(document.querySelector('#e-back')).display") == "none"
          and not m.js("return document.querySelector('#e-ws').classList.contains('on')"))
    m.js("document.querySelector('#e-ws').click()")
    check("no horizontal overflow", m.js("return document.documentElement.scrollWidth <= innerWidth"))
finally:
    b.close()
finish()
