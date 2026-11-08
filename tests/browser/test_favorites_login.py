"""Favorites with login: guests keep them in the browser, they move to the account on sign-in, each user has their own."""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from browser import BASE, W, Browser, check, finish  # noqa: E402

WHO = os.path.join(os.environ["SONG_DIR"], ".who.json")  # read by login_server.py
ROW = "[...document.querySelectorAll('#songs li.row2')].find(li=>li.textContent.includes(arguments[0]))"


def login(m, who):
    json.dump(who, open(WHO, "w"))
    m.js("setTimeout(() => document.querySelector('#acct').click(), 50)")
    time.sleep(2)


def logout(m):
    m.js("document.querySelector('#acct').click()")
    m.js("setTimeout(() => [...document.querySelectorAll('#acct-menu button')].find(b=>b.textContent.includes('Abmelden')).click(), 50)")
    time.sleep(2)


def fav_titles(m):
    return m.js("return [...document.querySelectorAll('#songs li.row2')].filter(li=>li.querySelector('.favb.on')).map(li=>li.querySelector('.tt').textContent)")


b = Browser()
m, wait = b.m, b.wait
try:
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    wait("document.querySelectorAll('#songs .favb').length===2")
    m.js(ROW + ".querySelector('.favb').click()", "Grüße")
    check("guest: heart stored in the browser", wait("JSON.parse(localStorage.getItem('lb.favs')||'[]').length===1"))
    m.cmd("WebDriver:Navigate", {"url": "about:blank"})
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    wait("document.querySelectorAll('#songs .favb').length===2")
    check("guest: still there after reload", fav_titles(m) == ["Grüße aus Wien"], fav_titles(m))
    # sign in: the guest's heart moves to the account
    login(m, {"sub": "a-1", "preferred_username": "alice", "name": "Alice"})
    wait("document.querySelector('#acct').textContent.includes('Alice')", 10)
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    check("after sign-in: favorite moved to the account", wait("document.querySelectorAll('#songs .favb.on').length===1")
          and m.js("return JSON.parse(localStorage.getItem('lb.favs')||'[]').length") == 0, fav_titles(m))
    m.js(ROW + ".querySelector('.favb').click()", "Abendlied")
    check("alice: two favorites", wait("document.querySelectorAll('#songs .favb.on').length===2"))
    logout(m)
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    wait("document.querySelectorAll('#songs .favb').length===2")
    check("signed out: guest list is empty again", fav_titles(m) == [], fav_titles(m))
    # another user has their own list
    login(m, {"sub": "b-2", "preferred_username": "bob"})
    wait("document.querySelector('#acct').textContent.includes('bob')", 10)
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    wait("document.querySelectorAll('#songs .favb').length===2")
    check("bob: no favorites of alice", fav_titles(m) == [], fav_titles(m))
    logout(m)
    login(m, {"sub": "a-1", "preferred_username": "alice", "name": "Alice"})
    wait("document.querySelector('#acct').textContent.includes('Alice')", 10)
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    check("alice again: her two favorites", wait("document.querySelectorAll('#songs .favb.on').length===2"), fav_titles(m))
finally:
    b.close()
finish()
