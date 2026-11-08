"""Helpers for the browser tests: headless Firefox driven over Marionette (no packages needed), checks.

The tests are plain scripts; run.py starts the app (fresh copy of fixtures/songs) and runs them.
Environment: BASE (app URL), W/H (window size), LANG_PREF (Firefox accept-languages, default "de"),
SHOTS (screenshot folder, default tests/browser/out).
"""
import base64
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("BASE", "http://localhost:18081")
W, H = int(os.environ.get("W", "1400")), int(os.environ.get("H", "900"))
SHOTS = os.environ.get("SHOTS", os.path.join(HERE, "out"))
FIXTURES = os.path.join(HERE, "fixtures")
EXAMPLES = os.path.join(HERE, "..", "..", "examples")  # local only (other people's songs), tests skip without it
os.makedirs(SHOTS, exist_ok=True)


class Marionette:
    """Minimal Marionette client: length-prefixed JSON over TCP."""

    def __init__(self, port):
        for _ in range(150):
            try:
                self.s = socket.create_connection(("127.0.0.1", port), timeout=60)
                break
            except OSError:
                time.sleep(0.2)
        else:
            raise RuntimeError("Firefox/Marionette did not start")
        self.buf = b""
        self.recv()  # handshake
        self.id = 0

    def recv(self):
        while b":" not in self.buf:
            self.buf += self.s.recv(65536)
        n, rest = self.buf.split(b":", 1)
        n = int(n)
        while len(rest) < n:
            rest += self.s.recv(65536)
        self.buf = rest[n:]
        return json.loads(rest[:n])

    def cmd(self, name, params=None):
        self.id += 1
        msg = json.dumps([0, self.id, name, params or {}]).encode()
        self.s.sendall(str(len(msg)).encode() + b":" + msg)
        while True:
            r = self.recv()
            if r[0] == 1 and r[1] == self.id:
                if r[2]:
                    raise RuntimeError(r[2])
                return r[3]

    def js(self, script, *args):
        return self.cmd("WebDriver:ExecuteScript", {"script": script, "args": list(args)}).get("value")

    def js_async(self, script):
        return self.cmd("WebDriver:ExecuteAsyncScript", {"script": script, "args": []}).get("value")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Browser:
    """Headless Firefox with its own profile; prefs: dict of extra Firefox preferences."""

    def __init__(self, width=W, height=H, lang=None, prefs=None, capabilities=None):
        self.port = free_port()
        self.prof = tempfile.mkdtemp(prefix="diss-ff-")
        # headless Firefox windows are at least ~500 px wide: narrower (phone) widths are simulated with a higher
        # pixel density, so the page really gets `width` CSS pixels (like a phone)
        # headless Firefox windows are at least 500 CSS px wide: narrower (phone) widths are simulated with browser zoom
        # on a 500 px window, so the page really gets `width` CSS pixels (like a phone)
        zoom = 1.0
        if width < 500:
            zoom, height = 500 / width, int(height * 500 / width)
            width = 500
        p = {"marionette.port": self.port, "browser.shell.checkDefaultBrowser": False, "dom.disable_beforeunload": True,
             "intl.accept_languages": lang or os.environ.get("LANG_PREF", "de"), "browser.zoom.siteSpecific": False,
             **(prefs or {})}
        with open(os.path.join(self.prof, "user.js"), "w") as f:
            for k, v in p.items():
                f.write(f"user_pref({json.dumps(k)}, {json.dumps(v)});\n")
        self.ff = subprocess.Popen(["firefox", "--headless", "--marionette", "--no-remote", "--profile", self.prof,
                                    *(["-remote-allow-system-access"] if zoom != 1.0 else []),
                                    f"--window-size={width},{height}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.m = Marionette(self.port)
        self.m.cmd("WebDriver:NewSession", {"capabilities": capabilities or {}})
        self.m.cmd("WebDriver:SetWindowRect", {"width": width, "height": height})
        if zoom != 1.0:  # (re)applied after every navigation – a new document starts unzoomed
            plain = self.m.cmd

            def zoomed(name, params=None):
                r = plain(name, params)
                if name == "WebDriver:Navigate":
                    plain("Marionette:SetContext", {"value": "chrome"})
                    plain("WebDriver:ExecuteScript", {"script": "gBrowser.selectedBrowser.browsingContext.fullZoom = arguments[0];", "args": [zoom]})
                    plain("Marionette:SetContext", {"value": "content"})
                return r
            self.m.cmd = zoomed

    def wait(self, cond, t=8):
        """Poll a JavaScript condition in the page until true (or t seconds)."""
        return self.m.js_async(
            "const done=arguments[arguments.length-1]; const t0=Date.now();"
            "(function f(){ try{ if(%s) return done(true);}catch(e){} if(Date.now()-t0>%d) return done(false); setTimeout(f,100);})()"
            % (cond, t * 1000))

    def shot(self, name):
        with open(os.path.join(SHOTS, name + ".png"), "wb") as f:
            f.write(base64.b64decode(self.m.cmd("WebDriver:TakeScreenshot", {})["value"]))

    def close(self):
        try:
            self.m.cmd("Marionette:Quit")
        except Exception:
            self.ff.kill()
        try:
            self.ff.wait(timeout=20)
        except subprocess.TimeoutExpired:
            self.ff.kill()
        shutil.rmtree(self.prof, ignore_errors=True)


_ok = True


def check(name, cond, detail=""):
    global _ok
    _ok &= bool(cond)
    print(("PASS " if cond else "FAIL ") + name + (" – " + str(detail) if detail else ""), flush=True)


def finish():
    print("ALL OK" if _ok else "SOME FAILED", flush=True)
    sys.exit(0 if _ok else 1)


def skip(why):
    print("SKIP " + why, flush=True)
    sys.exit(0)
