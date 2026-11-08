"""PWA manifest/icons + keep-awake (wake lock and video fallback)."""
import base64, glob, json, os, signal, sys, time, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from browser import BASE, W, H, SHOTS, FIXTURES, EXAMPLES, Browser, check, finish, skip  # noqa: E402

tag = f"{W}"
# manifest + icons served correctly
man = json.loads(urllib.request.urlopen(BASE + "/manifest.webmanifest").read())
for ic in man["icons"]:
    r = urllib.request.urlopen(BASE + "/" + ic["src"])
    body = r.read()
    if ic["type"] == "image/png":
        w, h = int.from_bytes(body[16:20], "big"), int.from_bytes(body[20:24], "big")
        check(f"icon {ic['src']} {ic['sizes']}", r.headers["Content-Type"] == "image/png" and f"{w}x{h}" == ic["sizes"], (w, h))
check("manifest: installable fields", man["display"] == "standalone" and man["start_url"] and man["name"]
      and any(i["sizes"] == "192x192" for i in man["icons"]) and any(i["sizes"] == "512x512" for i in man["icons"])
      and any(i.get("purpose") == "maskable" for i in man["icons"]))
for v in ("nosleep.mp4", "nosleep.webm"):
    r = urllib.request.urlopen(BASE + "/" + v)
    check(f"{v} served", r.status == 200 and r.headers["Content-Type"].startswith("video/") and len(r.read()) > 1000)

b = Browser(capabilities={"unhandledPromptBehavior": "accept"})
m, wait = b.m, b.wait
try:
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    wait("document.querySelectorAll('#songs a').length>0")
    check("apple-touch-icon + manifest linked", m.js("return !!document.querySelector('link[rel=apple-touch-icon]') && !!document.querySelector('link[rel=manifest]')"))
    print("  wakeLock in navigator:", m.js("return 'wakeLock' in navigator"))
    m.js("document.querySelector('#songs a').click()")
    check("play mode: screen kept on (☀)", wait("document.querySelector('#p-speed-v').textContent.includes('☀')"), m.js("return document.querySelector('#p-speed-v').textContent"))
    m.js("history.back()")
    check("list: wake released", wait("!document.querySelector('#v-list').hidden") and m.js("return document.querySelector('#p-speed-v').textContent.includes('☀')") is False)
    # fallback: wake lock refused -> invisible video
    m.js("const w = window.wrappedJSObject || window; Object.defineProperty(w.navigator.wakeLock, 'request', {value: () => w.Promise.reject(new w.Error('nope'))})")
    m.js("document.querySelector('#songs a').click()")
    wait("!document.querySelector('#bar').hidden")
    m.js("document.querySelector('#sheet').dispatchEvent(new PointerEvent('pointerdown', {bubbles:true}))")
    check("fallback video plays when wake lock is refused", wait("document.querySelector('video') && !document.querySelector('video').paused"),
          m.js("const v=document.querySelector('video'); return v && [v.paused, v.currentSrc, v.error && v.error.code]"))
    check("☀ shown with fallback", wait("document.querySelector('#p-speed-v').textContent.includes('☀')"))
    m.js("history.back()")
    check("fallback video paused after leaving", wait("document.querySelector('video').paused"))
finally:
    b.close()
finish()
