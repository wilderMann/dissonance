"""Offline: the service worker keeps the list and songs readable when the server is gone."""
import os, signal, sys, time, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from browser import BASE, W, Browser, check, finish  # noqa: E402

b = Browser(width=W)
m, wait = b.m, b.wait
try:
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    wait("navigator.serviceWorker.controller")
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})   # reload so the service worker controls the page
    check("service worker controls the page", wait("navigator.serviceWorker.controller"))
    wait("document.querySelectorAll('#songs a').length===2")
    m.js("document.querySelector('#offline-all').click()")
    check("all songs stored on the device", wait("document.querySelector('#toast').textContent.includes('gespeichert')"))
    os.kill(int(os.environ["SERVER_PID"]), signal.SIGTERM)  # run.py passes the app's pid
    time.sleep(1)
    try:
        urllib.request.urlopen(BASE + "/healthz", timeout=2)
        check("server is down", False)
    except OSError:
        check("server is down", True)
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/lied/" + urllib.parse.quote("Beispiel Chor - Abendlied.cho")})
    check("song renders offline", wait("document.querySelectorAll('#sheet .c').length>20", 12))
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    check("list offline", wait("document.querySelectorAll('#songs a').length===2", 12))
finally:
    b.close()
finish()
