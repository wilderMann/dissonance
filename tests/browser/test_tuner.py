"""Tuner: pitch detection on synthetic string sounds, and the dialog with a fake microphone (Firefox fake stream)."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from browser import BASE, W, Browser, check, finish  # noqa: E402

b = Browser(prefs={"media.navigator.streams.fake": True, "media.navigator.permission.disabled": True,
                   "media.autoplay.default": 0, "media.autoplay.block-webaudio": False})
m, wait = b.m, b.wait
try:
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    wait("document.querySelectorAll('#songs a').length===2")
    # plucked-string-like signal: fundamental + harmonics, decaying, a little noise; at the rates the tuner uses
    errs = m.js("""
      const out = [];
      const sig = (f, sr, n, phase) => { const b = new Float32Array(n);
        for (let i = 0; i < n; i++) { const t = i / sr;
          b[i] = Math.exp(-t * 2) * (0.5 * Math.sin(2*Math.PI*f*t + phase) + 0.35 * Math.sin(4*Math.PI*f*t) + 0.2 * Math.sin(6*Math.PI*f*t + 1) + 0.1 * Math.sin(8*Math.PI*f*t))
                 + (Math.random() - 0.5) * 0.01; }
        return b; };
      for (const midi of [38, 40, 45, 50, 55, 59, 64, 55, 60, 64, 67, 69, 76])
        for (const det of [0, -23, 17])
          for (const [sr, n] of [[24000, 2048], [22050, 2048], [48000, 4096]]) {
            const f = 440 * Math.pow(2, (midi - 69) / 12 + det / 1200), hz = detectPitch(sig(f, sr, n, midi), sr);
            out.push([midi, det, sr, hz ? 1200 * Math.log2(hz / f) : null]);
          }
      return out;""")
    bad = [e for e in errs if e[3] is None or abs(e[3]) > 2]
    check(f"detects {len(errs)} string sounds within ±2 cents", not bad, bad[:5])
    check("silence -> no pitch", m.js("return detectPitch(new Float32Array(2048), 24000)") == 0)
    check("noise -> no pitch", m.js("const b=new Float32Array(2048); for(let i=0;i<b.length;i++) b[i]=Math.random()-.5; return detectPitch(b, 24000)") == 0)
    # dialog with the (fake) microphone
    m.js("document.querySelector('#gear').click(); [...document.querySelectorAll('#acct-menu button')].find(b=>b.textContent.includes('Stimmgerät')).click()")
    check("tuner dialog opens", wait("document.querySelector('#dlg-tuner').open"))
    check("guitar: 6 strings E A D G B E (international chord names = default)", m.js("return [...document.querySelectorAll('#tu-strings .ib')].map(b=>b.firstChild.textContent).join(' ')") == "E A D G B E")
    check("tuning name follows the notation", "(E A D G B E)" in m.js("return document.querySelector('#tu-tuning').selectedOptions[0].textContent"))
    got = wait("document.querySelector('#dlg-tuner').dataset.mic==='on' && /Hz/.test(document.querySelector('#tu-info').textContent)", 10)
    check("fake microphone: a pitch is shown", got, m.js("return [document.querySelector('#tu-info').textContent, document.querySelector('#tu-msg').textContent, document.querySelector('#tu-note').textContent]"))
    m.js("const s=document.querySelector('#tu-tuning'); s.value='ukulele'; s.onchange({target:s})")
    check("ukulele: 4 strings G C E A", m.js("return [...document.querySelectorAll('#tu-strings .ib')].map(b=>b.firstChild.textContent).join(' ')") == "G C E A")
    m.js("document.querySelectorAll('#tu-strings .ib')[1].click()")
    check("tap locks a string", m.js("return document.querySelectorAll('#tu-strings .ib')[1].classList.contains('on') && document.querySelector('#tu-hint').textContent.includes('C')"))
    b.shot(f"tuner-{W}")
    m.js("document.querySelector('#tu-close').click()")
    check("closing stops the microphone", wait("!document.querySelector('#dlg-tuner').open && document.querySelector('#dlg-tuner').dataset.mic==='off'"))
    # from a song: the ⚙ menu opens the tuner for the song's instrument
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/lied/Beispiel%20Chor%20-%20Abendlied.cho"})
    wait("document.querySelector('#sheet .c')")
    m.js("document.querySelector('#p-more').click(); document.querySelector('#p-inst').click(); document.querySelector('#p-inst').click()")
    inst = m.js("return document.querySelector('#p-inst').textContent")
    m.js("document.querySelector('#gear').click(); [...document.querySelectorAll('#acct-menu button')].find(b=>b.textContent.includes('Stimmgerät')).click()")
    n = 4 if inst == "Ukulele" else 6
    check("from the song: tuner for the song's instrument", wait("document.querySelector('#dlg-tuner').open")
          and m.js("return document.querySelectorAll('#tu-strings .ib').length") == n, (inst, n))
    y = m.js("return scrollY")
    m.js("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'PageDown'}))")
    time.sleep(0.5)
    check("page keys do nothing while the tuner is open", m.js("return scrollY") == y)
    m.js("document.querySelector('#dlg-tuner').close()")
finally:
    b.close()
finish()
