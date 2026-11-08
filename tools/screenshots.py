"""Regenerate the README screenshots (docs/screenshots/) from the invented test songs, in English.

usage: python3 tools/screenshots.py      (needs Firefox, like the browser tests)
The booklet screenshot (booklet.png) is not made here: it shows the print view, which changes rarely.
"""
import base64
import json
import os
import shutil
import sys
import tempfile
import time
import urllib.parse

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "tests", "browser"))
from browser import Browser, free_port  # noqa: E402
from run import start_server  # noqa: E402

OUT = os.path.join(ROOT, "docs", "screenshots")
SONG = "Die Testband - Grüße aus Wien.cho"
API = ("const done=arguments[arguments.length-1]; fetch(arguments[0], {method: arguments[1], headers: {'Content-Type': 'application/json'},"
       " body: arguments[2] ? JSON.stringify(arguments[2]) : undefined}).then(r => r.json()).then(done)")


def main():
    songs = tempfile.mkdtemp(prefix="diss-shots-")
    shutil.copytree(os.path.join(ROOT, "tests", "browser", "fixtures", "songs"), songs, dirs_exist_ok=True)
    port = free_port()
    server = start_server("app", songs, port)
    base = f"http://localhost:{port}"
    try:
        desktop, book = Browser(1280, 674, lang="en"), None
        m = desktop.m
        api = lambda method, path, body=None: m.cmd("WebDriver:ExecuteAsyncScript", {"script": API, "args": [path, method, body]})["value"]

        def go(b, hash_, theme, wait):
            b.m.cmd("WebDriver:Navigate", {"url": "about:blank"})
            b.m.cmd("WebDriver:Navigate", {"url": base + "/"})
            b.m.js(f"localStorage.setItem('lb.theme', {json.dumps(json.dumps(theme))}); localStorage.setItem('lb.diagDefault', '\"right\"')")
            b.m.cmd("WebDriver:Navigate", {"url": "about:blank"})
            b.m.cmd("WebDriver:Navigate", {"url": base + "/#" + hash_})
            b.wait(wait); time.sleep(0.8)

        def shot(b, name):
            with open(os.path.join(OUT, name + ".png"), "wb") as f:
                f.write(base64.b64decode(b.m.cmd("WebDriver:TakeScreenshot", {"full": False})["value"]))
            print("wrote", os.path.relpath(os.path.join(OUT, name + ".png"), ROOT))

        m.cmd("WebDriver:Navigate", {"url": base + "/"})
        ids = [s["id"] for s in sorted(api("GET", "api/songs")["songs"], key=lambda s: s["title"])]
        book = api("POST", "api/books", {"name": "Campfire"})["id"]
        for i in ids:
            api("POST", f"api/books/{book}/lied", {"song": i, "add": True})
        song = "/lied/" + urllib.parse.quote(SONG)

        go(desktop, song, "dark", "document.querySelector('#sheet .c') && document.querySelector('.dg')")
        m.js("document.querySelector('#p-more').click()"); time.sleep(0.4)
        shot(desktop, "play-desktop-dark")
        go(desktop, "/bearbeiten/" + urllib.parse.quote(SONG), "dark", "!document.querySelector('#edit').hidden")
        shot(desktop, "editor-dark")
        go(desktop, f"/buch/{book}", "light", "document.querySelectorAll('#b-songs li').length === 2")
        shot(desktop, "songbook")
        desktop.close()

        phone = Browser(390, 780, lang="en")
        go(phone, "/", "light", "document.querySelectorAll('#songs li.row2').length === 2")
        shot(phone, "phone-list")
        go(phone, song, "light", "document.querySelector('#sheet .c')")
        shot(phone, "phone-play")
        phone.close()
    finally:
        server.terminate()
        server.wait(timeout=10)
        shutil.rmtree(songs, ignore_errors=True)


if __name__ == "__main__":
    main()
