"""Languages: English by default, German from the browser or the setting, server messages follow."""
import os, sys, time, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from browser import BASE, W, Browser, check, finish  # noqa: E402

SONG = urllib.parse.quote("Die Testband - Grüße aus Wien.cho")


def texts(m):
    return m.js("return [...document.querySelectorAll('[data-nav]')].map(a=>a.textContent.trim())")


# French browser -> not German -> English
b = Browser(lang="fr-FR,fr", capabilities={"unhandledPromptBehavior": "accept"})
m, wait = b.m, b.wait
try:
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
    wait("document.querySelectorAll('#songs a').length===2")
    check("fr browser: English UI", texts(m)[:2] == ["Songs", "Songbooks"] and m.js("return document.documentElement.lang") == "en", texts(m))
    check("placeholder translated", m.js("return document.querySelector('#q').placeholder") == "Search (title, artist)…")
    check("count line English", m.js("return document.querySelector('#count').textContent") == "2 songs")
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/neu"})
    wait("!document.querySelector('#edit').hidden")
    check("new-song template English", "{start_of_verse: Verse 1}" in m.js("return document.querySelector('#e-text').value"))
    check("insert buttons English", m.js("return [...document.querySelectorAll('#e-syntax .ib')].map(b=>b.textContent).slice(0,5).join()") == "Title,Artist,Key,Capo,Verse")
    # server message in English
    m.js("const t=document.querySelector('#e-text'); t.value='[C]no title'; t.oninput(); document.querySelector('#e-save').click()")
    check("server error in English", wait("document.querySelector('#e-msg').textContent.startsWith('Please add a title')"),
          m.js("return document.querySelector('#e-msg').textContent"))
    # play view texts (leaving the unsaved editor asks "Discard unsaved changes?" – answer yes)
    m.js("window.confirm = () => true")
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/lied/" + SONG})
    wait("document.querySelector('#sheet .c')")
    check("play bar English", "Tempo" in m.js("return document.querySelector('#p-speed-v').textContent")
          and "paused" in m.js("return document.querySelector('#p-speed-v').textContent"))
    check("chorus label kept from the song", "REFRAIN" in m.js("return document.querySelector('#sheet').innerText").upper())
    # switch to German in the settings
    m.js("window.confirm = () => true")
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/einstellungen"})
    wait("!document.querySelector('#v-settings').hidden")
    m.js("const s=document.querySelector('#set-lang'); s.value='de'; s.dispatchEvent(new Event('change'))")
    time.sleep(1.5)
    wait("document.querySelectorAll('[data-nav]').length")
    check("setting 'Deutsch' switches the UI", texts(m)[:2] == ["Lieder", "Bücher"] and m.js("return document.documentElement.lang") == "de", texts(m))
    check("setting remembered", m.js("return document.querySelector('#set-lang').value") == "de")
    m.cmd("WebDriver:Navigate", {"url": BASE + "/#/neu"})
    wait("!document.querySelector('#edit').hidden")
    m.js("const t=document.querySelector('#e-text'); t.value='[C]kein Titel'; t.oninput(); document.querySelector('#e-save').click()")
    check("server error in German after switching", wait("document.querySelector('#e-msg').textContent.startsWith('Bitte einen Titel')"),
          m.js("return document.querySelector('#e-msg').textContent"))
finally:
    b.close()

# German browser, no setting -> German; English browser -> English
for pref, want in (("de-AT,de", ["Lieder", "Bücher"]), ("en-US,en", ["Songs", "Songbooks"])):
    b = Browser(lang=pref)
    try:
        b.m.cmd("WebDriver:Navigate", {"url": BASE + "/#/"})
        b.wait("document.querySelectorAll('#songs a').length===2")
        check(f"browser {pref}: {want[0]}", texts(b.m)[:2] == want, texts(b.m))
    finally:
        b.close()
finish()
