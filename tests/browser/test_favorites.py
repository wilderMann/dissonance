"""Favorites without login: one list for the whole server, hearts in the list and in the song, favorites filter."""
import os, sys, time, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from browser import BASE, W, Browser, check, finish  # noqa: E402

ROW = "[...document.querySelectorAll('#songs li.row2')].find(li=>li.textContent.includes(arguments[0]))"
b = Browser()
m, wait = b.m, b.wait
try:
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    check("every song row has a heart", wait("document.querySelectorAll('#songs .favb').length===2"))
    m.js(ROW + ".querySelector('.favb').click()", "Abendlied")
    check("heart turns on, list stays", wait(ROW.replace("arguments[0]", "'Abendlied'") + ".querySelector('.favb').classList.contains('on')")
          and m.js("return !document.querySelector('#v-list').hidden"))
    m.cmd("WebDriver:Navigate", {"url": "about:blank"})
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    wait("document.querySelectorAll('#songs .favb').length===2")
    check("saved on the server (after reload)", m.js("return " + ROW + ".querySelector('.favb').textContent", "Abendlied") == "♥"
          and m.js("return localStorage.getItem('lb.favs')") in (None, "[]"))
    m.js("document.querySelector('#favonly').click()")
    check("filter: only favorites", wait("document.querySelectorAll('#songs li.row2').length===1")
          and "Abendlied" in m.js("return document.querySelector('#songs').textContent"))
    m.js("document.querySelector('#favonly').click()")
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/lied/" + urllib.parse.quote("Beispiel Chor - Abendlied.cho")})
    check("song view shows ♥", wait("document.querySelector('#s-fav').textContent==='♥'"))
    m.js("document.querySelector('#s-fav').click()")
    check("unlike in the song view", wait("document.querySelector('#s-fav').textContent==='♡'"))
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    wait("document.querySelectorAll('#songs .favb').length===2")
    m.js("document.querySelector('#favonly').click()")
    check("filter with no favorites explains", wait("document.querySelector('#songs .empty') && document.querySelector('#songs .empty').textContent.includes('♡')"))
    m.js("document.querySelector('#favonly').click()")
    check("no horizontal overflow", m.js("return document.documentElement.scrollWidth <= innerWidth"))
    b.shot(f"favorites-{W}")
finally:
    b.close()
finish()
