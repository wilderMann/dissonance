"""Play mode layout: with "⋯" open the end of the song is not hidden behind the bar; back arrow + title stay visible."""
import os, sys, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from browser import BASE, W, Browser, check, finish  # noqa: E402

b = Browser(capabilities={"unhandledPromptBehavior": "accept"})
m, wait = b.m, b.wait
LAST = "[...document.querySelectorAll('#sheet .ln')].pop().getBoundingClientRect().bottom"
try:
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/lied/" + urllib.parse.quote("Die Testband - Grüße aus Wien.cho")})
    wait("document.querySelectorAll('#sheet .c').length>50")
    m.js("document.querySelector('#p-more').click()")
    check("extra controls open", m.js("return !document.querySelector('#p-extra').hidden"))
    wait("parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--barh')) === document.querySelector('#bar').offsetHeight")
    m.js("scrollTo(0, 1e6)")
    wait("scrollY > 100")
    last, bar = m.js(f"return [{LAST}, document.querySelector('#bar').getBoundingClientRect().top]")
    check("last line above the open bar", last <= bar, f"last line bottom {last:.0f}, bar top {bar:.0f}")
    head = m.js("const r=document.querySelector('#v-song .play-head').getBoundingClientRect(); return [r.top, r.bottom]")
    back = m.js("const r=document.querySelector('#s-back').getBoundingClientRect(); return [r.top, r.bottom, r.width]")
    title = m.js("const r=document.querySelector('#s-title').getBoundingClientRect(); return [r.top, r.width]")
    check("header sticks at the top while scrolled", -1 <= head[0] <= 1 and head[1] > 30, head)
    check("back arrow and title visible", back[0] >= 0 and back[2] > 20 and title[0] >= 0 and title[1] > 20, (back, title))
    hit = m.js("const r=document.querySelector('#s-back').getBoundingClientRect(); return document.elementFromPoint(r.left + r.width/2, r.top + r.height/2) === document.querySelector('#s-back')")
    check("back arrow is on top (not covered by the song)", hit)
    # closing the extras: the padding shrinks again, still nothing hidden
    m.js("document.querySelector('#p-more').click()")
    wait("parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--barh')) === document.querySelector('#bar').offsetHeight")
    m.js("scrollTo(0, 1e6)")
    last, bar = m.js(f"return [{LAST}, document.querySelector('#bar').getBoundingClientRect().top]")
    check("last line above the closed bar", last <= bar, f"{last:.0f} / {bar:.0f}")
    # edit mode: the top bar is visible, the sticky header sits right below it
    m.js("document.querySelector('#to-edit').click()")
    wait("!document.querySelector('#edit').hidden")
    m.js("scrollTo(0, 400)")
    top, head = m.js("return [document.querySelector('.top').getBoundingClientRect().bottom, document.querySelector('#v-song .play-head').getBoundingClientRect().top]")
    check("edit mode: header below the top bar", abs(top - head) <= 1.5 or m.js("return scrollY") == 0, (top, head))
    b.shot(f"play-layout-{W}")
finally:
    b.close()
finish()
