import glob
import io
import json
import os
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
import zipfile

import ug2chordpro as ug

HERE = os.path.dirname(os.path.abspath(__file__))


def example(word):
    """Saved song pages are not in the repository (other people's lyrics) – put them into examples/ to run these tests."""
    paths = [p for p in glob.glob(os.path.join(HERE, "examples", "*.html")) if word in p]
    if not paths:
        raise unittest.SkipTest(f"example page '{word}' not in examples/")
    (path,) = paths
    with open(path, encoding="utf-8") as f:
        return f.read()


class Examples(unittest.TestCase):
    def test_soldat(self):
        s, t = ug.convert_page(example("SOLDAT"))
        self.assertEqual(ug.filename(s["title"], s["artist"]), "ok.danke.tschüss - Soldat.cho")
        self.assertIn("{title: Soldat}\n{artist: ok.danke.tschüss}\n", t)
        self.assertIn("{comment: * = One strum}", t)
        self.assertIn("Ich [Em]weiß nicht was der Staat die [D]erzählt hat.", t)
        self.assertIn("{start_of_chorus: Chorus}\nSold[Em]at, leg die [B]Waffen nieder", t)
        self.assertIn("Glaubst du [C]blutgetränktest Land, [*N.C.]dass du eingenommen hast", t)
        # strum marker stays glued to its chord, words are not split
        self.assertIn("Sold[Em][**]at, leg die W[B][**]affen nieder", t)
        self.assertNotIn("[ch]", t)
        self.assertNotIn("[tab]", t)
        self.assertEqual(t.count("{start_of_"), t.count("{end_of_"))

    def test_liegen(self):
        s, t = ug.convert_page(example("LIEGEN"))
        self.assertIn("{start_of_verse: Intro}\n[C#m] [E] [B] [F#]\n{end_of_verse}", t)
        self.assertIn("([Am]  [C]  [G]  [D]  - Capo 4)", t)
        self.assertIn("Ich hör den [B]Vögeln zu, die sagen, schön, dass Du\nUns [F#]zuhörst", t)
        self.assertIn("[*n.C.]Nutze den Tag", t)
        self.assertIn("[E] [B] [F#] [C#m] [*(only once, than stop)]", t)
        self.assertIn("         (Aufstehen, rausgehen)", t)  # backing vocals kept as lyrics
        self.assertIn("{start_of_bridge: Bridge}", t)

    def test_transpose_capo(self):
        _, t = ug.convert_page(example("LIEGEN"), steps=-4)
        self.assertIn("{start_of_verse: Intro}\n[Am] [C] [G] [D]", t)
        _, t = ug.convert_page(example("SOLDAT"), steps=3)  # Em -> Gm = flat key
        self.assertIn("Ich [Gm]weiß nicht was der Staat die [F]erzählt hat.", t)
        _, t = ug.convert_page(example("SOLDAT"), steps=2)  # Em -> F#m = sharp key
        self.assertIn("Aber [A]das ist auch [C#]egal.", t)
        _, t = ug.convert_page(example("SOLDAT"), steps=1, flats=True)
        self.assertIn("Ich [Fm]weiß nicht was der Staat die [Eb]erzählt hat.", t)


class UkuleleTabs(unittest.TestCase):
    def test_bubbly(self):
        s, t = ug.convert_page(example("Bubbly"))
        self.assertEqual(ug.filename(s["title"], s["artist"]), "Colbie Caillat - Bubbly.cho")
        self.assertTrue(t.startswith("{title: Bubbly}\n{artist: Colbie Caillat}\n{key: A}\n{x_instrument: ukulele}\n"
                                     "# Source: https://www.ukulele-tabs.com/uke-songs/colbie-caillat/bubbly-uke-tab-1455.html\n"))
        s, t = ug.convert_page(example("Bubbly"), lang="de")
        self.assertIn("# Quelle: https://www.ukulele-tabs.com/", t)
        self.assertIn("[A]I've been awake for a [Amaj7]while now\n[D]you've got me feelin like a [A]child now\n", t)
        self.assertNotIn("<", t)

    def test_death_of_a_bachelor(self):
        s, t = ug.convert_page(example("Bachelor"))
        self.assertEqual((s["title"], s["artist"], s["instrument"]), ("Death Of A Bachelor", "Panic! At The Disco", "ukulele"))
        self.assertIn("{comment: Hey guys! This is my first tab, so I might mess up.}", t)
        self.assertIn("I'm walking the [F]long road[Fm], watching the [C]sky fall", t)  # &#039; unescaped
        self.assertIn("Interlude: [Am] [C] [Dm] [G]", t)

    def test_album_page(self):
        with self.assertRaises(ug.AlbumPage) as cm:
            ug.convert_page(example("Bellyache"))
        self.assertEqual(cm.exception.url, "https://www.ukulele-tabs.com/uke-songs/billie-eilish/bellyache-uke-tab-78428.html")

    def test_unknown_page(self):
        with self.assertRaises(ValueError):
            ug.convert_page("<html><body>nix</body></html>")


class Chords(unittest.TestCase):
    def test_transpose(self):
        self.assertEqual(ug.transpose_chord("Em", 2, False), "F#m")
        self.assertEqual(ug.transpose_chord("C#m7b5/G#", 1, False), "Dm7b5/A")
        self.assertEqual(ug.transpose_chord("Bb", 2, False), "C")
        self.assertEqual(ug.transpose_chord("A", 1, True), "Bb")
        self.assertEqual(ug.transpose_chord("Hm", 1, False), "Cm")

    def test_is_chord(self):
        for c in ["C", "Am7", "F#m", "Bbmaj7", "Dsus4", "Cadd9", "G/B", "E7(#9)", "Asus2", "C#m"]:
            self.assertTrue(ug.is_chord(c), c)
        for w in ["Dad", "Bad", "Cab", "Ebbe", "Gold", "And", "Am Ende"]:
            self.assertFalse(ug.is_chord(w), w)


class PlainText(unittest.TestCase):
    def test_plain_without_sections(self):
        t = ug.convert("Am         G\nHier steht der Text\nNoch eine Zeile\n")
        self.assertEqual(t, "[Am]Hier steht [G]der Text\nNoch eine Zeile\n")

    def test_plain_sections_and_tab(self):
        src = "[Intro]\ne|---0---|\nB|---1---|\n\n[Chorus]\nC   G\nLa la la\n"
        t = ug.convert(src, "T", "A")
        self.assertIn("{start_of_verse: Intro}\n{start_of_tab}\ne|---0---|\nB|---1---|\n{end_of_tab}\n{end_of_verse}", t)
        self.assertIn("{start_of_chorus: Chorus}\n[C]La l[G]a la\n{end_of_chorus}", t)

    def test_chordpro_passthrough(self):
        self.assertEqual(ug.convert("[Am]Hallo [G]Welt"), "[Am]Hallo [G]Welt\n")
        self.assertEqual(ug.convert("[C]Hi", steps=2), "[D]Hi\n")

    def test_lyric_brackets(self):
        self.assertEqual(ug.convert("Text [laut]"), "Text (laut)\n")

    def test_lyric_shorter_than_chords(self):
        self.assertEqual(ug.convert("C     G     Am\nOh no\n"), "[C]Oh no [G]      [Am]\n")


class Instrument(unittest.TestCase):
    def test_detect(self):
        self.assertEqual(ug.instrument_of("Ukulele Chords", "", ""), "ukulele")
        self.assertEqual(ug.instrument_of("Chords", "https://tabs.ultimate-guitar.com/tab/x/y-ukulele-123", ""), "ukulele")
        self.assertEqual(ug.instrument_of("Chords", "", "G C E A"), "ukulele")
        self.assertEqual(ug.instrument_of("Chords", "https://tabs.ultimate-guitar.com/tab/x/y-chords-1", "E A D G B E"), "guitar")
        self.assertEqual(ug.instrument_of("Bass Tabs", "", ""), "")

    def test_marked_in_output(self):
        s, t = ug.convert_page(example("SOLDAT"))
        self.assertEqual(s["instrument"], "guitar")
        self.assertIn("{x_instrument: guitar}", t)
        s, t = ug.convert_page(example("SOLDAT"), instrument="ukulele")
        self.assertIn("{x_instrument: ukulele}", t)
        self.assertNotIn("x_instrument", ug.convert("[C]x", "T"))


class Languages(unittest.TestCase):
    def test_pick(self):
        import i18n
        self.assertEqual(i18n.pick(), "en")
        self.assertEqual(i18n.pick(accept="de-AT,de;q=0.9,en;q=0.8"), "de")
        self.assertEqual(i18n.pick(accept="fr-FR,fr;q=0.9"), "en")
        self.assertEqual(i18n.pick(accept="fr,de;q=0.5"), "de")
        self.assertEqual(i18n.pick("en", "de", "de"), "en")          # the app's choice wins
        self.assertEqual(i18n.pick(None, "de", "en-US"), "de")       # then the cookie

    def test_messages(self):
        import i18n
        self.assertEqual(i18n.tr("en", "„{name}“ gibt es schon.", name="x.cho"), "“x.cho” already exists.")
        self.assertEqual(i18n.tr("de", "„{name}“ gibt es schon.", name="x.cho"), "„x.cho“ gibt es schon.")
        self.assertEqual(i18n.tr("en", "Bitte einen Titel angeben: {{title: …}}"), "Please add a title: {title: …}")
        e = ug.ConvertError("Dieser Tab ({kind}) enthält keinen Text – Pro-/Official-Tabs werden nicht unterstützt.", kind="Pro")
        self.assertIn("This tab (Pro)", e.localized("en"))
        self.assertIn("Dieser Tab (Pro)", str(e))
        # every German text in the code has an English translation
        import re
        for f in ("app.py", "auth.py", "ug2chordpro.py"):
            src = open(os.path.join(HERE, f), encoding="utf-8").read()
            for m in re.finditer(r'(?:HttpError\(\d+, |ConvertError\(|AuthError\(|Message\()"([^"]+)"', src):
                self.assertIn(m.group(1), i18n.EN, f"{f}: {m.group(1)}")

    def test_converter_labels(self):
        t = ug.convert("C\nla", "T", tuning="D A D G B E", url="https://x", lang="de")
        self.assertIn("{comment: Stimmung: D A D G B E}", t)
        self.assertIn("# Quelle: https://x", ug.convert("C\nla", "T", url="https://x", lang="de"))
        self.assertIn("{comment: Tuning: D A D G B E}", ug.convert("C\nla", "T", tuning="D A D G B E"))


class Urls(unittest.TestCase):
    def test_check_url(self):
        ug.check_url("https://tabs.ultimate-guitar.com/tab/4211443")
        ug.check_url("https://www.ukulele-tabs.com/uke-songs/colbie-caillat/bubbly-uke-tab-1455.html")
        for bad in ["http://tabs.ultimate-guitar.com/tab/1", "https://ultimate-guitar.com.evil.net/x",
                    "https://evil.net/?u=ultimate-guitar.com", "file:///etc/passwd", "https://10.0.0.1/"]:
            with self.assertRaises(ValueError, msg=bad):
                ug.check_url(bad)



class ChordProChords(unittest.TestCase):
    """tools/chordpro_chords.py (ChordPro's chord tables -> chords.json) without network, and the committed file."""

    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("cpc", os.path.join(os.path.dirname(__file__), "tools", "chordpro_chords.py"))
        self.cpc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.cpc)

    def test_relaxed_json(self):
        cfg = self.cpc.rjson("""// ChordPro Configuration.
config {
  type : instrument   # comment
  title : "Ukulele with Fingering"
}
tuning : [ G4 C4 E4 A4 ]
chords : [
  { name : "A"  base : 1  frets : [ 2 1 0 0 ]  fingers : [ 2 1 0 0 ] }
  { name : Bb7  base : 1  frets : [ 1 2 1 1 ] fingers : [ 1 2 1 1 ] }
  { name : A#7  copy : Bb7 }
  { name : Cx   frets : [ x 0 0 3 ] }
]
pdf.diagrams.vcells : 5
""")
        self.assertEqual(cfg["config"]["title"], "Ukulele with Fingering")
        self.assertEqual(cfg["pdf"], {"diagrams": {"vcells": 5}})
        out = self.cpc.convert([cfg], "ukulele")
        self.assertEqual(out["A"], [1, [2, 1, 0, 0], [2, 1, 0, 0]])
        self.assertEqual(out["A#7"], "Bb7")
        self.assertEqual(out["Cx"], [1, [-1, 0, 0, 3]])
        with self.assertRaises(ValueError):
            self.cpc.convert([{"tuning": ["D4", "G4", "B4", "E5"], "chords": []}], "ukulele")

    def test_aliases_resolve(self):
        out = self.cpc.convert([{"chords": [{"name": "X", "copy": "Y"}, {"name": "Y", "copy": "Z"},
                                            {"name": "Z", "base": 1, "frets": [0, 0, 0, 3]},
                                            {"name": "L1", "copy": "L2"}, {"name": "L2", "copy": "L1"}, {"name": "B", "copy": "nope"}]}], "ukulele")
        self.assertEqual((out["X"], out["Y"]), ("Z", "Z"))
        self.assertNotIn("L1", out)
        self.assertNotIn("B", out)

    def test_committed_chords_json(self):
        with open(os.path.join(os.path.dirname(__file__), "chords.json"), encoding="utf-8") as f:
            d = json.load(f)
        self.assertEqual(d["source"]["license"], "Artistic-2.0")
        for inst, n in (("guitar", 6), ("ukulele", 4)):
            shapes = {k: v for k, v in d[inst].items() if isinstance(v, list)}
            self.assertGreater(len(shapes), 150, inst)
            for k, v in d[inst].items():
                if isinstance(v, str):
                    self.assertIsInstance(d[inst][v], list, (inst, k))
                else:
                    self.assertEqual(len(v[1]), n, (inst, k))
        self.assertEqual(d["guitar"]["C"][1], [-1, 3, 2, 0, 1, 0])
        self.assertEqual(d["ukulele"]["C"][1], [0, 0, 0, 3])

class AppServer:
    """The app on a free port: Waitress when installed (as in production), else the built-in server;
    TEST_SERVER=builtin forces the built-in one."""

    def __init__(self, app):
        try:
            if os.environ.get("TEST_SERVER") == "builtin":
                raise ImportError
            import waitress.server
        except ImportError:
            self.srv = app.ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
            self.port, run, self.stop = self.srv.server_address[1], self.srv.serve_forever, self.srv.shutdown
            self.kind = "builtin"
        else:
            self.srv = waitress.server.create_server(app.wsgi_app, host="127.0.0.1", port=0, threads=4,
                                                     max_request_body_size=app.MAX_BODY)
            self.port, run, self.stop = int(self.srv.effective_port), self.srv.run, self.srv.close
            self.kind = "waitress"
        threading.Thread(target=run, daemon=True).start()

    def shutdown(self):
        self.stop()


class Server(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import tempfile
        from pathlib import Path
        import app
        cls.tmp = tempfile.TemporaryDirectory()
        app.SONG_DIR, app._db = Path(cls.tmp.name), None
        cls.app = app
        cls.srv = AppServer(app)
        cls.base = "http://127.0.0.1:%d" % cls.srv.port

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.tmp.cleanup()

    def post(self, path, obj):
        req = urllib.request.Request(self.base + path, json.dumps(obj).encode(), {"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as r:
            return r.read()

    def call(self, method, path, obj=None):
        data = json.dumps(obj).encode() if obj is not None else None
        req = urllib.request.Request(self.base + path, data, {"Content-Type": "application/json"}, method=method)
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_single_user_has_no_sharing_or_visibility(self):
        """Without login: no visibility, share links, campfire mode or collaborators; new things are always public;
        the owner of legacy songs can be set in bulk edit once users exist (e.g. before switching on the login)."""
        st, song = self.call("POST", "/api/songs", {"content": "{title: Einzel}\n[C]x\n", "public": False})
        self.assertEqual(st, 200)
        st, book = self.call("POST", "/api/books", {"name": "Einzelbuch", "public": False})
        listed = {s["title"]: s for s in self.call("GET", "/api/songs")[1]["songs"]}
        self.assertTrue(listed["Einzel"]["public"])  # "public": false is ignored
        self.assertTrue(self.call("GET", f"/api/books/{book['id']}")[1]["public"])
        for path, body in ((f"/api/books/{book['id']}/share", {"on": True}), (f"/api/books/{book['id']}/campfire", {"days": 2}),
                           ("/api/visibility", {"song": song["id"], "public": False}),
                           (f"/api/collab/song/{song['id']}", {"users": [], "all": True})):
            self.assertEqual(self.call("POST" if "collab" not in path else "PUT", path, body)[0], 404, path)
        self.assertEqual(self.call("GET", "/api/shared/" + "x" * 24)[0], 404)
        self.assertEqual(self.call("GET", "/api/me")[1]["campfire"], [])
        self.assertEqual(self.call("POST", "/api/songs/bulk", {"ids": [song["id"]], "changes": {"public": False}})[0], 400)
        # owner in bulk edit: only known users
        self.assertEqual(self.call("POST", "/api/songs/bulk", {"ids": [song["id"]], "changes": {"owner": "nobody"}})[0], 404)
        with self.app.tx() as c:
            c.execute("INSERT INTO users (sub, username, name, admin) VALUES ('s-1', 'sam', 'Sam', 0)")
        self.assertEqual([u["username"] for u in self.call("GET", "/api/users")[1]["users"]], ["sam"])
        st, r = self.call("POST", "/api/songs/bulk", {"ids": [song["id"]], "changes": {"owner": "s-1"}})
        self.assertEqual((st, r["changed"]), (200, 1))
        with self.app.tx() as c:
            self.assertEqual(c.execute("SELECT owner FROM songs WHERE id=?", (song["id"],)).fetchone()[0], "s-1")
            self.assertEqual(c.execute("SELECT count(*) FROM activity").fetchone()[0], 0)  # nobody to record it for
            c.execute("DELETE FROM users")
        self.call("DELETE", "/api/songs/Einzel.cho")
        self.call("DELETE", f"/api/books/{book['id']}")

    def test_http_layer(self):
        """Behaviour both servers (Waitress and the built-in fallback) must share."""
        def req(method, path, body=None, headers=None):
            r = urllib.request.Request(self.base + path, data=body, method=method, headers=headers or {})
            try:
                with urllib.request.urlopen(r) as resp:
                    return resp.status, dict(resp.headers), resp.read()
            except urllib.error.HTTPError as e:
                return e.code, dict(e.headers), e.read()
        st, h, body = req("GET", "/")
        self.assertEqual(st, 200)
        self.assertIn("default-src 'self'", h["Content-Security-Policy"])
        self.assertEqual((h["X-Content-Type-Options"], h["Content-Length"]), ("nosniff", str(len(body))))
        self.assertEqual(h["X-Robots-Tag"], "noindex, nofollow")
        st, h, body = req("GET", "/robots.txt")
        self.assertEqual((st, body), (200, b"User-agent: *\nDisallow: /\n"))
        st, h, body = req("HEAD", "/healthz")
        self.assertEqual((st, body, h["Content-Length"]), (200, b"", "3"))
        st, h, body = req("PATCH", "/api/songs", b"{}")
        self.assertIn(st, (405, 501))
        st, h, body = req("POST", "/api/convert", b"not json", {"Content-Type": "application/json"})
        self.assertEqual(st, 400)
        st, h, body = req("GET", "/api/songs/" + urllib.parse.quote("../app.py"))
        self.assertEqual(st, 400)
        st, h, body = req("GET", "/api/songs/%2e%2e%2Fapp.cho")
        self.assertEqual(st, 400)
        st, h, body = req("POST", "/api/songs", b"{}", {"Origin": "https://evil.example"})
        self.assertEqual(st, 403)
        # a song with spaces and umlauts in its name round-trips through the URL
        st, h, body = req("POST", "/api/songs", json.dumps({"content": "{title: Über Brücken}\n{artist: Ä Ö}\n[C]x\n"}).encode())
        f = json.loads(body)["file"]
        st, h, body = req("GET", "/api/songs/" + urllib.parse.quote(f))
        self.assertEqual((st, json.loads(body)["file"]), (200, f))
        req("DELETE", "/api/songs/" + urllib.parse.quote(f))

    def test_body_limit(self):
        import socket
        with socket.create_connection(("127.0.0.1", int(self.base.rsplit(":", 1)[1]))) as sock:
            sock.sendall(b"POST /api/songs HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\n"
                         b"Content-Length: %d\r\nConnection: close\r\n\r\n" % (self.app.MAX_BODY + 1))
            sock.settimeout(10)
            head = sock.recv(200)
        self.assertRegex(head, rb"^HTTP/1\.[01] 413")

    def test_language_of_errors(self):
        st, r = self.call("POST", "/api/songs", {"content": "[C]no title"})
        self.assertEqual(r["error"], "Please add a title: {title: …}")  # no language info: English
        req = urllib.request.Request(self.base + "/api/songs", json.dumps({"content": "[C]x"}).encode(),
                                     {"Content-Type": "application/json", "Accept-Language": "de-AT,de"}, method="POST")
        try:
            urllib.request.urlopen(req)
        except urllib.error.HTTPError as e:
            self.assertEqual(json.loads(e.read())["error"], "Bitte einen Titel angeben: {title: …}")
        req.add_header("X-Lang", "en")
        try:
            urllib.request.urlopen(req)
        except urllib.error.HTTPError as e:
            self.assertIn("Please add a title", json.loads(e.read())["error"])

    def test_static(self):
        for p in ("/sw.js", "/manifest.webmanifest", "/icon.svg"):
            with urllib.request.urlopen(self.base + p) as r:
                self.assertEqual(r.status, 200, p)

    def test_version(self):
        version = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "VERSION")).read().strip()
        self.assertRegex(version, r"^\d+\.\d+\.\d+$")
        with urllib.request.urlopen(self.base + "/sw.js") as r:
            self.assertIn(f'"dissonance-{version}"', r.read().decode())  # offline cache per release
        self.assertEqual(self.call("GET", "/api/me")[1]["version"], version)

    def test_songbook(self):
        song = "{title: Über den Wolken}\n{artist: Reinhard Mey}\n{key: G}\n\n[G]Wind Nord-Ost\n"
        st, r = self.call("POST", "/api/songs", {"content": song})
        self.assertEqual((st, r["file"]), (200, "Reinhard Mey - Über den Wolken.cho"))
        f, mt = r["file"], r["mtime"]
        # same name again without overwrite -> 409, with -> ok
        st, r = self.call("POST", "/api/songs", {"content": song})
        self.assertEqual((st, r["conflict"]), (409, "exists"))
        st, r = self.call("GET", "/api/songs")
        self.assertEqual([(s["title"], s["artist"], s["key"]) for s in r["songs"]], [("Über den Wolken", "Reinhard Mey", "G")])
        st, r = self.call("GET", "/api/songs/" + urllib.parse.quote(f))
        self.assertEqual(r["content"], song)
        # edit with a stale mtime -> conflict; with the right one -> ok
        st, r = self.call("POST", "/api/songs", {"content": song + "x\n", "old": f, "base_mtime": mt - 5})
        self.assertEqual((st, r["conflict"]), (409, "changed"))
        st, r = self.call("POST", "/api/songs", {"content": song + "x\n", "old": f, "base_mtime": mt})
        self.assertEqual(st, 200)
        # rename via title -> old file goes to the trash
        st, r = self.call("POST", "/api/songs", {"content": song.replace("Über den Wolken", "Wolken"), "old": f})
        self.assertEqual(r["file"], "Reinhard Mey - Wolken.cho")
        names = sorted(p.name for p in self.app.SONG_DIR.iterdir() if not p.name.startswith(".liederbuch.db"))
        self.assertEqual(names, [".papierkorb", "Reinhard Mey - Wolken.cho"])
        st, r = self.call("DELETE", "/api/songs/" + urllib.parse.quote("Reinhard Mey - Wolken.cho"))
        self.assertEqual(st, 200)
        trash = [p.name for p in (self.app.SONG_DIR / ".papierkorb").iterdir() if "Reinhard Mey" in p.name]
        self.assertEqual(len(trash), 2)
        self.assertEqual(self.call("GET", "/api/songs")[1]["songs"], [])

    def test_history_and_restore(self):
        song = "{title: Verlauf}\n{artist: Test}\n\n[C]eins\n"
        st, r = self.call("POST", "/api/songs", {"content": song})
        sid, f = r["id"], r["file"]
        self.call("POST", "/api/songs", {"content": song.replace("eins", "zwei"), "old": f})
        self.call("POST", "/api/songs", {"content": song.replace("eins", "zwei"), "old": f})  # unchanged: no version
        # edit outside the app (SMB) shows up as its own version
        p = self.app.SONG_DIR / f
        p.write_text(song.replace("eins", "drei"), encoding="utf-8")
        os.utime(p, ns=(p.stat().st_mtime_ns + 10**9,) * 2)
        st, h = self.call("GET", f"/api/history/{sid}")
        self.assertEqual([v["action"] for v in h["versions"]], ["außerhalb geändert", "geändert", "neu"])
        first = h["versions"][-1]
        st, r = self.call("POST", "/api/restore", {"version": first["id"]})
        self.assertEqual((st, r["id"]), (200, sid))
        self.assertEqual(p.read_text(encoding="utf-8"), song)
        # rename keeps the history, delete + restore brings the song back under its id
        st, r = self.call("POST", "/api/songs", {"content": song.replace("Verlauf", "Verlauf 2"), "old": f})
        self.assertEqual((r["id"], r["file"]), (sid, "Test - Verlauf 2.cho"))
        self.call("DELETE", "/api/songs/" + urllib.parse.quote(r["file"]))
        st, d = self.call("GET", "/api/deleted")
        (gone,) = [s for s in d["songs"] if s["id"] == sid]
        self.assertEqual(gone["title"], "Verlauf 2")
        st, h = self.call("GET", f"/api/history/{sid}")
        acts = [v["action"] for v in h["versions"]]
        self.assertEqual(acts[:2], ["gelöscht", "umbenannt"])
        self.assertTrue(acts[2].startswith("wiederhergestellt (Stand "), acts[2])
        older = [v for v in h["versions"] if "drei" in v["content"]][0]
        st, r = self.call("POST", "/api/restore", {"version": older["id"]})
        self.assertEqual((st, r["id"], r["file"]), (200, sid, f))
        self.assertIn("drei", p.read_text(encoding="utf-8"))
        # restoring onto a name that another song uses -> 409, with overwrite the other one is retired
        st, other = self.call("POST", "/api/songs", {"content": song.replace("Verlauf", "Verlauf 2")})
        st, r = self.call("POST", "/api/restore", {"version": h["versions"][1]["id"]})  # "Verlauf 2"
        self.assertEqual((st, r["conflict"]), (409, "exists"))
        st, r = self.call("POST", "/api/restore", {"version": h["versions"][1]["id"], "overwrite": True})
        self.assertEqual((st, r["id"], r["file"]), (200, sid, "Test - Verlauf 2.cho"))
        self.assertFalse(p.exists())
        st, h2 = self.call("GET", f"/api/history/{other['id']}")
        self.assertEqual((h2["file"], h2["versions"][0]["action"]), (None, "überschrieben"))
        self.call("DELETE", "/api/songs/" + urllib.parse.quote("Test - Verlauf 2.cho"))

    def test_books(self):
        ids = []
        for t in ("Alpha", "Beta", "Gamma"):
            st, r = self.call("POST", "/api/songs", {"content": f"{{title: {t}}}\n{{artist: Buch}}\n[G]{t}\n"})
            ids.append(r["id"])
        st, r = self.call("POST", "/api/books", {"name": "  Lagerfeuer  2026 "})
        bid = r["id"]
        st, b = self.call("GET", f"/api/books/{bid}")
        self.assertEqual((b["name"], b["songs"]), ("Lagerfeuer 2026", []))
        st, r = self.call("PUT", f"/api/books/{bid}", {"songs": [ids[2], ids[0], ids[2], 99999], "base_updated": b["updated"]})
        self.assertEqual(st, 200)
        st, r2 = self.call("PUT", f"/api/books/{bid}", {"name": "x", "base_updated": b["updated"]})
        self.assertEqual((st, r2["conflict"]), (409, "changed"))
        self.call("POST", f"/api/books/{bid}/lied", {"song": ids[1], "add": True})
        st, b = self.call("GET", f"/api/books/{bid}/inhalt")
        self.assertEqual([s["title"] for s in b["songs"]], ["Gamma", "Alpha", "Beta"])
        self.assertIn("[G]Gamma", b["songs"][0]["content"])
        st, s = self.call("GET", "/api/songs/" + urllib.parse.quote("Buch - Beta.cho"))
        self.assertEqual(s["books"], [bid])
        # renaming a song keeps it in the book
        self.call("POST", "/api/songs", {"content": "{title: Alpha neu}\n{artist: Buch}\n", "old": "Buch - Alpha.cho"})
        with urllib.request.urlopen(self.base + f"/api/books/{bid}/export.cho") as r:
            self.assertIn("filename*=UTF-8''Lagerfeuer%202026.cho", r.headers["Content-Disposition"])
            text = r.read().decode()
        self.assertEqual(text.count("{new_song}"), 2)
        self.assertLess(text.index("Gamma"), text.index("Alpha neu"))
        with urllib.request.urlopen(self.base + f"/api/books/{bid}/export.zip") as r:
            self.assertEqual(zipfile.ZipFile(io.BytesIO(r.read())).namelist(),
                             ["1 Buch - Gamma.cho", "2 Buch - Alpha neu.cho", "3 Buch - Beta.cho"])
        # a deleted song stays listed (marked) but is not exported
        self.call("DELETE", "/api/songs/" + urllib.parse.quote("Buch - Beta.cho"))
        st, b = self.call("GET", f"/api/books/{bid}")
        self.assertEqual([(s["title"], bool(s.get("deleted"))) for s in b["songs"]],
                         [("Gamma", False), ("Alpha neu", False), ("Beta", True)])
        st, lst = self.call("GET", "/api/books")
        self.assertEqual([(x["name"], x["count"]) for x in lst["books"]], [("Lagerfeuer 2026", 2)])
        self.call("DELETE", f"/api/books/{bid}")
        self.assertEqual(self.call("GET", f"/api/books/{bid}")[0], 404)
        for f in ("Buch - Gamma.cho", "Buch - Alpha neu.cho"):
            self.call("DELETE", "/api/songs/" + urllib.parse.quote(f))

    def test_tempo_per_device(self):
        st, r = self.call("POST", "/api/songs", {"content": "{title: Tempo}\n{x_instrument: ukulele}\n[C]x\n"})
        sid, f = r["id"], r["file"]
        self.assertEqual(self.call("POST", "/api/tempo", {"song": sid, "device": "phone", "speed": 12})[0], 200)
        self.call("POST", "/api/tempo", {"song": sid, "device": "pc", "speed": 7})
        self.call("POST", "/api/tempo", {"song": sid, "device": "phone", "speed": 14})
        st, s = self.call("GET", "/api/songs/" + urllib.parse.quote(f))
        self.assertEqual(s["tempos"], {"phone": 14, "pc": 7})
        for bad in ({"song": sid, "device": "watch", "speed": 5}, {"song": sid, "device": "pc", "speed": 99}):
            self.assertEqual(self.call("POST", "/api/tempo", bad)[0], 400)
        self.assertEqual(self.call("POST", "/api/tempo", {"song": 99999, "device": "pc", "speed": 5})[0], 404)
        st, lst = self.call("GET", "/api/songs")
        self.assertEqual([x["instrument"] for x in lst["songs"] if x["id"] == sid], ["ukulele"])
        # renaming keeps the tempos (same song id)
        st, r = self.call("POST", "/api/songs", {"content": "{title: Tempo 2}\n[C]x\n", "old": f})
        st, s = self.call("GET", "/api/songs/" + urllib.parse.quote(r["file"]))
        self.assertEqual(s["tempos"]["phone"], 14)
        self.call("DELETE", "/api/songs/" + urllib.parse.quote(r["file"]))

    def test_favorites_server_wide(self):
        st, a = self.call("POST", "/api/songs", {"content": "{title: Fav A}\n[C]x\n"})
        st, b = self.call("POST", "/api/songs", {"content": "{title: Fav B}\n[C]x\n"})
        self.assertEqual(self.call("POST", "/api/favorite", {"song": a["id"], "fav": True})[0], 200)
        favs = {s["title"]: s["fav"] for s in self.call("GET", "/api/songs")[1]["songs"]}
        self.assertEqual((favs["Fav A"], favs["Fav B"]), (True, False))
        self.assertTrue(self.call("GET", "/api/songs/" + urllib.parse.quote(a["file"]))[1]["fav"])
        self.call("POST", "/api/favorite", {"song": a["id"], "fav": False})
        self.assertFalse(self.call("GET", "/api/songs/" + urllib.parse.quote(a["file"]))[1]["fav"])
        self.assertEqual(self.call("POST", "/api/favorite", {"song": 99999, "fav": True})[0], 404)
        for f in (a, b):
            self.call("DELETE", "/api/songs/" + urllib.parse.quote(f["file"]))

    def test_song_names(self):
        for bad in ["..%2Fapp.py", "%2Fetc%2Fpasswd.cho", ".papierkorb", "x.txt", "..%2F..%2Fx.cho"]:
            st, r = self.call("GET", "/api/songs/" + bad)
            self.assertIn(st, (400, 404), bad)
        st, r = self.call("POST", "/api/songs", {"content": "[C]no title"})
        self.assertEqual(st, 400)
        st, r = self.call("POST", "/api/songs", {"content": "{title: ../../evil}"})
        self.assertEqual((st, r["file"]), (200, "evil.cho"))
        self.call("DELETE", "/api/songs/evil.cho")

    def test_index(self):
        with urllib.request.urlopen(self.base + "/") as r:
            self.assertIn(b"ChordPro", r.read())

    def test_convert_html_and_zip(self):
        r = json.loads(self.post("/api/convert", {"source": "html", "value": example("SOLDAT"), "transpose": 2}))
        self.assertTrue(r["ok"])
        self.assertIn("Ich [F#m]weiß", r["chordpro"])
        z = zipfile.ZipFile(io.BytesIO(self.post("/api/zip", {"files": [
            {"name": r["filename"], "content": r["chordpro"]}, {"name": r["filename"], "content": "x"}]})))
        self.assertEqual(z.namelist(), ["ok.danke.tschüss - Soldat.cho", "ok.danke.tschüss - Soldat (2).cho"])

    def test_errors(self):
        r = json.loads(self.post("/api/convert", {"source": "url", "value": "https://evil.net/"}))
        self.assertFalse(r["ok"])
        r = json.loads(self.post("/api/convert", {"source": "html", "value": "<html></html>"}))
        self.assertFalse(r["ok"])
        self.assertIn("js-store", r["error"])



class FakeKeycloak:
    """Minimal OIDC provider: /auth logs in whoever is in `self.next` and redirects straight back."""

    def __init__(self):
        import base64
        import hashlib
        import http.server
        import urllib.parse as up
        fake = self
        self.next, self.codes, self.logouts, self.public_ok, self.userinfo, self.tokens = None, {}, 0, False, {}, {}

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def reply(self, code, body=b"", headers=()):
                self.send_response(code)
                for k, v in headers:
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                u = up.urlsplit(self.path)
                q = dict(up.parse_qsl(u.query))
                if u.path == "/realm/.well-known/openid-configuration":
                    b = fake.base
                    cfg = {"issuer": b, "authorization_endpoint": b + "/auth", "token_endpoint": b + "/token",
                           "end_session_endpoint": b + "/logout", "userinfo_endpoint": b + "/userinfo"}
                    return self.reply(200, json.dumps(cfg).encode(), [("Content-Type", "application/json")])
                if u.path == "/realm/auth":
                    code = "c" + str(len(fake.codes))
                    fake.codes[code] = (q, fake.next)
                    return self.reply(302, headers=[("Location", q["redirect_uri"] + "?" + up.urlencode({"code": code, "state": q["state"]}))])
                if u.path == "/realm/userinfo":
                    who = fake.tokens.get(self.headers.get("Authorization", "")[7:])
                    if not who:
                        return self.reply(401)
                    return self.reply(200, json.dumps({"sub": who["sub"], **fake.userinfo}).encode(), [("Content-Type", "application/json")])
                if u.path == "/realm/logout":
                    fake.logouts += 1
                    return self.reply(302, headers=[("Location", q["post_logout_redirect_uri"])])
                self.reply(404)

            def do_POST(self):
                form = dict(up.parse_qsl(self.rfile.read(int(self.headers["Content-Length"])).decode()))
                q, who = fake.codes.pop(form.get("code"), (None, None))
                challenge = base64.urlsafe_b64encode(hashlib.sha256(form.get("code_verifier", "").encode()).digest()).rstrip(b"=").decode()
                basic = self.headers.get("Authorization", "")
                secret_ok = form.get("client_secret") == "geheim" or basic == "Basic " + base64.b64encode(b"dissonance:geheim").decode()
                if not q or not (secret_ok or fake.public_ok) or challenge != q.get("code_challenge"):
                    return self.reply(400, b'{"error":"invalid_grant"}')
                claims = {"iss": fake.base, "aud": "dissonance", "azp": "dissonance", "exp": time.time() + 300,
                          "nonce": q["nonce"], **who}
                seg = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
                access = "at" + str(len(fake.tokens))
                fake.tokens[access] = who
                tok = {"id_token": seg({"alg": "RS256"}) + "." + seg(claims) + ".sig", "access_token": access}
                self.reply(200, json.dumps(tok).encode(), [("Content-Type", "application/json")])

        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.base = "http://127.0.0.1:%d/realm" % self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()


class Users(unittest.TestCase):
    """Login via (fake) Keycloak, public/private songs and songbooks, roles."""

    @classmethod
    def setUpClass(cls):
        import tempfile
        from pathlib import Path
        import app
        import auth
        cls.tmp = tempfile.TemporaryDirectory()
        app.SONG_DIR, app._db = Path(cls.tmp.name), None
        (app.SONG_DIR / "Alt - Altes Lied.cho").write_text("{title: Altes Lied}\n{artist: Alt}\n[C]x\n", encoding="utf-8")
        cls.kc = FakeKeycloak()
        cls.srv = AppServer(app)
        cls.base = "http://127.0.0.1:%d" % cls.srv.port
        app.PUBLIC_URL = cls.base
        app.OIDC = auth.OIDC(auth.Config(issuer=cls.kc.base, client_id="dissonance", client_secret="geheim"), cls.base + "/auth/callback")
        cls.app = app

    @classmethod
    def tearDownClass(cls):
        cls.app.OIDC, cls.app.PUBLIC_URL, cls.app._db = None, "", None
        cls.srv.shutdown()
        cls.kc.srv.shutdown()
        cls.tmp.cleanup()

    def client(self, who=None):
        import http.cookiejar
        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        if who:
            self.kc.next = who
            with opener.open(self.base + "/auth/login?r=" + urllib.parse.quote("#/buecher")) as r:
                self.assertTrue(r.url.endswith("/#/buecher"), r.url)
        return opener

    def call(self, opener, method, path, obj=None, headers=None):
        data = json.dumps(obj).encode() if obj is not None else None
        req = urllib.request.Request(self.base + path, data, {"Content-Type": "application/json", **(headers or {})}, method=method)
        try:
            with opener.open(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_owner_change_and_activity(self):
        """Admins give songs a new owner in bulk edit (also legacy songs without owner); the admin page shows a user
        with their songs, songbooks and activity record."""
        dave = self.client({"sub": "d-4", "preferred_username": "dave", "name": "Dave", "groups": []})
        admin = self.client({"sub": "c-3", "preferred_username": "carol", "name": "Carol", "groups": ["/admin"]})
        st, song = self.call(dave, "POST", "/api/songs", {"content": "{title: Daves Lied}\n[C]x\n"})
        st, book = self.call(dave, "POST", "/api/books", {"name": "Daves Buch"})
        self.call(dave, "POST", f"/api/books/{book['id']}/lied", {"song": song["id"], "add": True})
        self.call(dave, "PUT", f"/api/books/{book['id']}", {"name": "Daves Liederbuch"})
        self.call(dave, "POST", "/api/visibility", {"book": book["id"], "public": False})
        self.call(dave, "POST", f"/api/books/{book['id']}/share", {"on": True})
        legacy = next(s for s in self.call(admin, "GET", "/api/songs")[1]["songs"] if s["title"] == "Altes Lied")
        # only admins may change the owner
        self.assertEqual(self.call(dave, "POST", "/api/songs/bulk", {"ids": [song["id"]], "changes": {"owner": "c-3"}})[0], 403)
        st, r = self.call(admin, "POST", "/api/songs/bulk", {"ids": [legacy["id"]], "changes": {"owner": "d-4"}})
        self.assertEqual((st, r["changed"]), (200, 1))
        mine = {s["title"]: s for s in self.call(dave, "GET", "/api/songs")[1]["songs"]}
        self.assertTrue(mine["Altes Lied"]["mine"] and mine["Altes Lied"]["editable"])
        # admin page: the user
        self.assertEqual(self.call(dave, "GET", "/api/admin/users/d-4")[0], 403)
        self.assertEqual(self.call(admin, "GET", "/api/admin/users/nobody")[0], 404)
        st, u = self.call(admin, "GET", "/api/admin/users/d-4")
        self.assertEqual((st, u["user"]["username"]), (200, "dave"))
        self.assertEqual(sorted(s["title"] for s in u["songs"]), ["Altes Lied", "Daves Lied"])
        self.assertEqual([(b["name"], b["public"], b["songs"]) for b in u["books"]], [("Daves Liederbuch", False, 1)])
        acts = [a["action"] for a in u["activity"]]
        for a in ("angemeldet", "neu", "Liederbuch angelegt", "Lied hinzugefügt", "Liederbuch umbenannt", "privat gemacht",
                  "Teilen-Link erstellt"):
            self.assertIn(a, acts)
        self.assertEqual(acts[0], "Teilen-Link erstellt")  # newest first
        st, carol = self.call(admin, "GET", "/api/admin/users/c-3")
        self.assertIn(("Besitzer geändert", "Altes Lied → dave"), [(a["action"], a["detail"]) for a in carol["activity"]])
        # clean up: songs back, book gone
        self.call(admin, "DELETE", f"/api/books/{book['id']}")
        self.assertIsNone(next(a for a in self.call(admin, "GET", "/api/admin/users/d-4")[1]["activity"]
                               if a["action"] == "Liederbuch angelegt")["id"])  # deleted book: no link
        with self.app.tx() as c:
            c.execute("UPDATE songs SET owner=NULL WHERE id=?", (legacy["id"],))
        self.call(dave, "DELETE", "/api/songs/Daves%20Lied.cho")

    def test_roles_and_visibility(self):
        alice = self.client({"sub": "a-1", "preferred_username": "alice", "name": "Alice", "groups": ["users"]})
        bob = self.client({"sub": "b-2", "preferred_username": "bob", "groups": []})
        admin = self.client({"sub": "c-3", "preferred_username": "carol", "name": "Carol", "groups": ["/admin"]})
        guest = self.client()
        self.assertEqual(self.call(alice, "GET", "/api/me")[1]["user"], {"name": "Alice", "username": "alice", "admin": False})
        self.assertTrue(self.call(admin, "GET", "/api/me")[1]["user"]["admin"])
        self.assertEqual(self.call(guest, "GET", "/api/me")[1], {"ok": True, "auth": True, "user": None, "provider": "", "account_url": "",
                                                              "notation": None, "notation_default": "intl", "guest_access": True, "version": self.app.VERSION,
                                                              "campfire": []})
        # guests can't change anything
        self.assertEqual(self.call(guest, "POST", "/api/songs", {"content": "{title: G}\n"})[0], 401)
        self.assertEqual(self.call(guest, "POST", "/api/convert", {"source": "text", "value": "C\nx"})[0], 401)
        # alice: public (default) + private song, private book
        st, pub = self.call(alice, "POST", "/api/songs", {"content": "{title: Offen}\n{artist: A}\n[C]x\n"})
        st, priv = self.call(alice, "POST", "/api/songs", {"content": "{title: Geheim}\n{artist: A}\n[D]y\n", "public": False})
        st, book = self.call(alice, "POST", "/api/books", {"name": "Alices Buch", "public": False})
        self.call(alice, "POST", f"/api/books/{book['id']}/lied", {"song": priv["id"], "add": True})
        self.call(alice, "POST", f"/api/books/{book['id']}/lied", {"song": pub["id"], "add": True})
        titles = lambda o: sorted(s["title"] for s in self.call(o, "GET", "/api/songs")[1]["songs"])
        self.assertEqual(titles(guest), ["Altes Lied", "Offen"])
        self.assertEqual(titles(bob), ["Altes Lied", "Offen"])
        self.assertEqual(titles(alice), ["Altes Lied", "Geheim", "Offen"])
        self.assertEqual(titles(admin), ["Altes Lied", "Geheim", "Offen"])
        mine = {s["title"]: s for s in self.call(alice, "GET", "/api/songs")[1]["songs"]}
        self.assertEqual((mine["Geheim"]["public"], mine["Geheim"]["mine"], mine["Geheim"]["editable"], mine["Geheim"]["owner"]),
                         (False, True, True, "alice"))  # by nick (username), not the full name
        self.assertEqual((mine["Altes Lied"]["editable"], mine["Altes Lied"]["owner"]), (False, ""))  # from before: admins only
        # owners: shown by nick to signed-in users, never to guests; never the full name
        self.assertEqual({s["owner"] for s in self.call(guest, "GET", "/api/songs")[1]["songs"]}, {""})
        self.assertIn("alice", {s["owner"] for s in self.call(bob, "GET", "/api/songs")[1]["songs"]})
        self.assertIn("alice", {s["owner"] for s in self.call(admin, "GET", "/api/songs")[1]["songs"]})
        self.assertNotIn("Alice", {s["owner"] for s in self.call(bob, "GET", "/api/songs")[1]["songs"]})
        q = lambda f: "/api/songs/" + urllib.parse.quote(f)
        self.assertEqual(self.call(bob, "GET", q(priv["file"]))[0], 404)
        self.assertEqual(self.call(guest, "GET", q(priv["file"]))[0], 404)
        self.assertEqual(self.call(admin, "GET", q(priv["file"]))[0], 200)
        # bob can't edit/delete alice's song; the same song by bob simply becomes his own version "… (bob)"
        self.assertEqual(self.call(bob, "POST", "/api/songs", {"content": "{title: Offen}\n{artist: A}\n[G]z\n", "old": pub["file"]})[0], 403)
        self.assertEqual(self.call(bob, "DELETE", q(pub["file"]))[0], 403)
        st, copy = self.call(bob, "POST", "/api/songs", {"content": "{title: Offen}\n{artist: A}\n[G]z\n"})
        self.assertEqual((st, copy["file"]), (200, "A - Offen (bob).cho"))
        st, again = self.call(bob, "POST", "/api/songs", {"content": "{title: Offen}\n{artist: A}\n[G]z2\n", "overwrite": True})
        self.assertEqual((st, again["file"]), (200, "A - Offen (bob 2).cho"))  # never touches alice's song
        self.assertIn("[C]x", self.call(alice, "GET", q(pub["file"]))[1]["content"])
        titles_b = [s["title"] for s in self.call(bob, "GET", "/api/songs")[1]["songs"] if s["title"] == "Offen"]
        self.assertEqual(len(titles_b), 3)  # same title three times, told apart by the owner
        self.assertEqual(self.call(bob, "POST", "/api/songs", {"content": "{title: Altes Lied}\n{artist: Alt}\n[G]z\n", "old": "Alt - Altes Lied.cho"})[0], 403)
        self.assertEqual(self.call(admin, "POST", "/api/songs", {"content": "{title: Altes Lied}\n{artist: Alt}\n[G]z\n", "old": "Alt - Altes Lied.cho"})[0], 200)
        # books: private book invisible, bob's book may hold alice's public song but not the private one
        self.assertEqual(self.call(bob, "GET", f"/api/books/{book['id']}")[0], 404)
        with self.assertRaises(urllib.error.HTTPError) as cm:
            guest.open(self.base + f"/api/books/{book['id']}/export.zip")
        self.assertEqual(cm.exception.code, 404)
        st, bb = self.call(bob, "POST", "/api/books", {"name": "Bobs Buch"})
        self.assertEqual(self.call(bob, "POST", f"/api/books/{bb['id']}/lied", {"song": pub["id"], "add": True})[0], 200)
        self.assertEqual(self.call(bob, "POST", f"/api/books/{bb['id']}/lied", {"song": priv["id"], "add": True})[0], 404)
        self.assertEqual(self.call(bob, "POST", f"/api/books/{book['id']}/lied", {"song": pub["id"], "add": False})[0], 404)
        self.assertEqual(self.call(alice, "POST", f"/api/books/{bb['id']}/lied", {"song": pub["id"], "add": False})[0], 403)
        self.assertEqual([b["name"] for b in self.call(guest, "GET", "/api/books")[1]["books"]], ["Bobs Buch"])
        # alice makes her book public: guests see it, but only the public song in it
        self.assertEqual(self.call(bob, "POST", "/api/visibility", {"book": book["id"], "public": True})[0], 404)
        self.assertEqual(self.call(alice, "POST", "/api/visibility", {"book": book["id"], "public": True})[0], 200)
        st, gb = self.call(guest, "GET", f"/api/books/{book['id']}")
        self.assertEqual(([s["title"] for s in gb["songs"]], gb["editable"]), (["Offen"], False))
        self.assertEqual([s["title"] for s in self.call(alice, "GET", f"/api/books/{book['id']}")[1]["songs"]], ["Geheim", "Offen"])
        with guest.open(self.base + f"/api/books/{book['id']}/export.cho") as r:
            text = r.read().decode()
        self.assertIn("Offen", text)
        self.assertNotIn("Geheim", text)
        # reordering by alice keeps songs she can see; an admin-added private song of someone else stays in the book
        st, carols = self.call(admin, "POST", "/api/songs", {"content": "{title: Carols}\n[E]e\n", "public": False})
        self.call(admin, "POST", f"/api/books/{book['id']}/lied", {"song": carols["id"], "add": True})
        st, ab = self.call(alice, "GET", f"/api/books/{book['id']}")
        self.call(alice, "PUT", f"/api/books/{book['id']}", {"songs": [pub["id"], priv["id"]], "base_updated": ab["updated"]})
        self.assertEqual([s["title"] for s in self.call(admin, "GET", f"/api/books/{book['id']}")[1]["songs"]], ["Offen", "Geheim", "Carols"])
        # tempos per user: bob sees alice's (owner) tempo until he sets his own
        self.call(alice, "POST", "/api/tempo", {"song": pub["id"], "device": "phone", "speed": 12})
        self.assertEqual(self.call(bob, "GET", q(pub["file"]))[1]["tempos"], {"phone": 12})
        self.call(bob, "POST", "/api/tempo", {"song": pub["id"], "device": "phone", "speed": 20})
        self.assertEqual(self.call(bob, "GET", q(pub["file"]))[1]["tempos"], {"phone": 20})
        self.assertEqual(self.call(alice, "GET", q(pub["file"]))[1]["tempos"], {"phone": 12})
        self.assertEqual(self.call(guest, "POST", "/api/tempo", {"song": pub["id"], "device": "phone", "speed": 5})[0], 401)
        # history / deleted list respect ownership
        self.assertEqual(self.call(bob, "GET", f"/api/history/{priv['id']}")[0], 404)
        self.assertFalse(self.call(bob, "GET", f"/api/history/{pub['id']}")[1]["editable"])
        self.call(alice, "DELETE", q(priv["file"]))
        self.assertEqual([s["title"] for s in self.call(alice, "GET", "/api/deleted")[1]["songs"]], ["Geheim"])
        self.assertEqual(self.call(bob, "GET", "/api/deleted")[1]["songs"], [])
        st, h = self.call(alice, "GET", f"/api/history/{priv['id']}")
        self.assertEqual(self.call(bob, "POST", "/api/restore", {"version": h["versions"][0]["id"]})[0], 404)
        self.assertEqual(self.call(alice, "POST", "/api/restore", {"version": h["versions"][0]["id"]})[0], 200)
        # logout ends the session (and the Keycloak session)
        before = self.kc.logouts
        alice.open(self.base + "/auth/logout").read()
        self.assertEqual((self.kc.logouts, self.call(alice, "GET", "/api/me")[1]["user"]), (before + 1, None))

    def login_status(self, who):
        try:
            self.client(who)
            return 200
        except urllib.error.HTTPError as e:
            return e.code

    def test_generic_provider_options(self):
        import auth
        cfg, saved = self.app.OIDC.cfg, dict(vars(self.app.OIDC.cfg))
        try:
            # roles in a nested claim (e.g. Keycloak realm roles), admin by role
            cfg.groups_claim, cfg.admin_groups = "realm_access.roles", ["dissonance-admin"]
            self.assertEqual(self.login_status({"sub": "r-1", "preferred_username": "rita", "realm_access": {"roles": ["dissonance-admin"]}}), 200)
            # groups only in userinfo (some providers), allowed_groups gate
            cfg.groups_claim, cfg.admin_groups, cfg.allowed_groups = "groups", ["admin"], ["band"]
            self.kc.userinfo = {"groups": ["band"], "email": "Uwe@Example.org"}
            self.assertEqual(self.login_status({"sub": "u-1", "preferred_username": "uwe"}), 200)
            self.kc.userinfo = {"groups": ["other"]}
            self.assertEqual(self.login_status({"sub": "u-2", "preferred_username": "olga"}), 403)
            # allowed domains / users
            cfg.allowed_groups, cfg.allowed_domains = [], ["example.org"]
            self.kc.userinfo = {}
            self.assertEqual(self.login_status({"sub": "d-1", "preferred_username": "dora", "email": "dora@example.org"}), 200)
            self.assertEqual(self.login_status({"sub": "d-2", "preferred_username": "evil", "email": "evil@example.com"}), 403)
            cfg.allowed_domains, cfg.allowed_users = [], ["dora@example.org"]
            self.assertEqual(self.login_status({"sub": "d-1", "preferred_username": "dora", "email": "dora@example.org"}), 200)
            self.assertEqual(self.login_status({"sub": "d-3", "preferred_username": "x", "email": "x@example.org"}), 403)
            # secret via POST body instead of Basic auth; public client (no secret, PKCE only)
            cfg.allowed_users, cfg.token_auth = [], "post"
            self.assertEqual(self.login_status({"sub": "p-1", "preferred_username": "paul"}), 200)
            cfg.client_secret, self.kc.public_ok = "", True
            self.assertEqual(self.login_status({"sub": "p-2", "preferred_username": "pia"}), 200)
        finally:
            vars(cfg).update(saved)
            self.kc.public_ok, self.kc.userinfo = False, {}
        st, me = self.call(self.client({"sub": "r-1", "preferred_username": "rita", "realm_access": {"roles": ["dissonance-admin"]}}), "GET", "/api/me")
        self.assertFalse(me["user"]["admin"])  # back to the default "groups" claim

    def test_config_from_env(self):
        import auth
        import tempfile
        self.assertIsNone(auth.Config.from_env({}))
        with tempfile.NamedTemporaryFile("w", suffix=".secret", delete=False) as f:
            f.write("s3cr3t\n")
        c = auth.Config.from_env({"OIDC_ISSUER": "https://idp.example/realms/x", "OIDC_CLIENT_ID": "songs",
                                  "OIDC_CLIENT_SECRET_PATH": f.name, "OIDC_SCOPE": "profile email groups",
                                  "OIDC_ADMIN_GROUPS": "admins, /music-admins", "OIDC_ALLOWED_GROUPS": "band",
                                  "OIDC_EXTRA_PARAMS": "prompt=login&kc_idp_hint=google", "OIDC_TOKEN_AUTH": "post",
                                  "OIDC_GROUPS_CLAIM": "roles", "OIDC_PROVIDER_NAME": "Authentik"})
        os.unlink(f.name)
        self.assertEqual((c.client_id, c.client_secret, c.scope, c.admin_groups, c.allowed_groups, c.token_auth, c.groups_claim),
                         ("songs", "s3cr3t", ["openid", "profile", "email", "groups"], ["admins", "/music-admins"], ["band"], "post", "roles"))
        self.assertEqual(c.extra_params, {"prompt": "login", "kc_idp_hint": "google"})
        with self.assertRaises(ValueError):
            auth.Config.from_env({"OIDC_ISSUER": "https://idp.example", "OIDC_PKCE": "off"})  # public client needs PKCE

    def test_admin_users(self):
        dora = self.client({"sub": "d-9", "preferred_username": "dora9", "name": "Dora"})
        eve = self.client({"sub": "e-9", "preferred_username": "eve9"})
        admin = self.client({"sub": "c-3", "preferred_username": "carol", "groups": ["admin"]})
        st, ds = self.call(dora, "POST", "/api/songs", {"content": "{title: Doras Lied}\n[C]x\n", "public": False})
        st, db = self.call(dora, "POST", "/api/books", {"name": "Doras Buch"})
        st, es = self.call(eve, "POST", "/api/songs", {"content": "{title: Eves Lied}\n[C]x\n"})
        self.assertEqual(self.call(dora, "GET", "/api/admin/users")[0], 403)
        st, r = self.call(admin, "GET", "/api/admin/users")
        users = {x["username"]: x for x in r["users"]}
        self.assertEqual((users["dora9"]["songs"], users["dora9"]["private"], users["dora9"]["books"]), (1, 1, 1))
        self.assertTrue(users["carol"]["me"])
        self.assertEqual(self.call(admin, "DELETE", "/api/admin/users/c-3?mode=transfer")[0], 400)  # not yourself
        self.assertEqual(self.call(dora, "DELETE", "/api/admin/users/e-9?mode=delete")[0], 403)
        self.assertEqual(self.call(admin, "DELETE", "/api/admin/users/d-9")[0], 400)  # mode missing
        # transfer: dora's song + book now belong to the admin, dora is logged out
        st, r = self.call(admin, "DELETE", "/api/admin/users/d-9?mode=transfer")
        self.assertEqual((st, r["songs"], r["books"]), (200, 1, 1))
        self.assertIsNone(self.call(dora, "GET", "/api/me")[1]["user"])
        mine = {x["title"]: x for x in self.call(admin, "GET", "/api/songs")[1]["songs"]}
        self.assertTrue(mine["Doras Lied"]["mine"])
        # delete: eve's song goes to the trash folder and the deleted list, restorable by the admin
        st, r = self.call(admin, "DELETE", "/api/admin/users/e-9?mode=delete")
        self.assertEqual((st, r["songs"]), (200, 1))
        self.assertNotIn("Eves Lied", [x["title"] for x in self.call(admin, "GET", "/api/songs")[1]["songs"]])
        self.assertIn("Eves Lied", [x["title"] for x in self.call(admin, "GET", "/api/deleted")[1]["songs"]])
        self.assertEqual(self.call(admin, "DELETE", "/api/admin/users/e-9?mode=delete")[0], 404)
        self.call(admin, "DELETE", "/api/songs/" + urllib.parse.quote(ds["file"]))  # leave nothing for other tests
        self.call(admin, "DELETE", f"/api/books/{db['id']}")

    def test_favorites_per_user(self):
        fred = self.client({"sub": "f-1", "preferred_username": "fred"})
        gina = self.client({"sub": "g-1", "preferred_username": "gina"})
        guest = self.client()
        st, pub = self.call(fred, "POST", "/api/songs", {"content": "{title: Herzlied}\n[C]x\n"})
        st, priv = self.call(gina, "POST", "/api/songs", {"content": "{title: Ginas Geheimnis}\n[C]x\n", "public": False})
        self.assertEqual(self.call(guest, "POST", "/api/favorite", {"song": pub["id"], "fav": True})[0], 401)  # guests: browser
        self.call(fred, "POST", "/api/favorite", {"song": pub["id"], "fav": True})
        fav = lambda o: {s["title"] for s in self.call(o, "GET", "/api/songs")[1]["songs"] if s["fav"]}
        self.assertEqual((fav(fred), fav(gina), fav(guest)), ({"Herzlied"}, set(), set()))
        self.assertEqual(self.call(fred, "POST", "/api/favorite", {"song": priv["id"], "fav": True})[0], 404)  # private of others
        # merging a guest's browser favorites after login: unknown/private ids are skipped
        st, r = self.call(gina, "POST", "/api/favorite", {"songs": [pub["id"], priv["id"], 99999], "fav": True})
        self.assertEqual((st, fav(gina)), (200, {"Herzlied", "Ginas Geheimnis"}))
        admin = self.client({"sub": "c-3", "preferred_username": "carol", "groups": ["admin"]})
        self.call(admin, "DELETE", "/api/admin/users/f-1?mode=transfer")
        with self.app.tx() as c:
            self.assertEqual(c.execute("SELECT count(*) FROM favorites WHERE user='f-1'").fetchone()[0], 0)
        for f in (pub, priv):
            self.call(admin, "DELETE", "/api/songs/" + urllib.parse.quote(f["file"]))

    def test_share_links(self):
        hans = self.client({"sub": "h-1", "preferred_username": "hans"})
        ida = self.client({"sub": "i-1", "preferred_username": "ida"})
        admin = self.client({"sub": "c-3", "preferred_username": "carol", "groups": ["admin"]})
        guest = self.client()
        st, mine = self.call(hans, "POST", "/api/songs", {"content": "{title: Hans privat}\n[C]x\n", "public": False})
        st, pub = self.call(hans, "POST", "/api/songs", {"content": "{title: Hans offen}\n[C]x\n"})
        st, other = self.call(ida, "POST", "/api/songs", {"content": "{title: Idas Geheimnis}\n[C]x\n", "public": False})
        st, book = self.call(hans, "POST", "/api/books", {"name": "Hans Buch", "public": False})
        bid = book["id"]
        for s in (mine, pub):
            self.call(hans, "POST", f"/api/books/{bid}/lied", {"song": s["id"], "add": True})
        self.call(admin, "POST", f"/api/books/{bid}/lied", {"song": other["id"], "add": True})  # someone else's private song
        self.assertIsNone(self.call(hans, "GET", f"/api/books/{bid}")[1]["share"])
        # only who may edit the book can share it
        self.assertEqual(self.call(ida, "POST", f"/api/books/{bid}/share", {"on": True})[0], 404)
        self.assertEqual(self.call(guest, "POST", f"/api/books/{bid}/share", {"on": True})[0], 404)
        st, r = self.call(hans, "POST", f"/api/books/{bid}/share", {"on": True})
        tok = r["share"]
        self.assertTrue(st == 200 and len(tok) >= 20, r)
        self.assertEqual(self.call(hans, "POST", f"/api/books/{bid}/share", {"on": True})[1]["share"], tok)  # stays the same
        self.assertEqual(self.call(hans, "GET", f"/api/books/{bid}")[1]["share"], tok)
        self.assertTrue([b for b in self.call(hans, "GET", "/api/books")[1]["books"] if b["id"] == bid][0]["shared"])
        # with the link a guest sees the private book, read-only, with the owner's songs but not ida's private one
        st, gb = self.call(guest, "GET", f"/api/shared/{tok}")
        self.assertEqual((st, gb["name"], gb["editable"], gb["share"], gb["via_share"]), (200, "Hans Buch", False, None, True))
        self.assertEqual([s["title"] for s in gb["songs"]], ["Hans privat", "Hans offen"])
        q = lambda f: "/api/shared/" + tok + "/songs/" + urllib.parse.quote(f)
        st, s = self.call(guest, "GET", q(mine["file"]))
        self.assertEqual((st, s["via_share"], s["editable"]), (200, True, False))
        self.assertEqual(self.call(guest, "GET", q(other["file"]))[0], 404)
        self.assertEqual(self.call(guest, "GET", "/api/songs/" + urllib.parse.quote(mine["file"]))[0], 404)  # without the link
        st, iv = self.call(ida, "GET", q(other["file"]))  # her own song: visible to her anyway
        self.assertEqual((st, iv["via_share"]), (200, False))
        st, s = self.call(ida, "GET", q(pub["file"]))
        self.assertEqual((st, s["via_share"]), (200, False))
        self.assertEqual(self.call(guest, "GET", f"/api/shared/{tok}/inhalt")[1]["songs"][0]["content"], "{title: Hans privat}\n[C]x\n")
        with guest.open(self.base + f"/api/shared/{tok}/export.cho") as r:
            text = r.read().decode()
        self.assertIn("Hans privat", text)
        self.assertNotIn("Idas Geheimnis", text)
        # a private song that is not in the book can't be read through the link
        st, lone = self.call(hans, "POST", "/api/songs", {"content": "{title: Hans allein}\n[C]x\n", "public": False})
        self.assertEqual(self.call(guest, "GET", q(lone["file"]))[0], 404)
        # new link: the old one stops working; switching off: no link at all
        st, r = self.call(hans, "POST", f"/api/books/{bid}/share", {"on": True, "renew": True})
        self.assertNotEqual(r["share"], tok)
        self.assertEqual(self.call(guest, "GET", f"/api/shared/{tok}")[0], 404)
        tok = r["share"]
        self.assertEqual(self.call(hans, "POST", f"/api/books/{bid}/share", {"on": False})[1]["share"], None)
        self.assertEqual(self.call(guest, "GET", f"/api/shared/{tok}")[0], 404)
        self.assertEqual(self.call(guest, "GET", "/api/shared/short")[0], 404)
        for f in (mine, pub, lone):
            self.call(admin, "DELETE", "/api/songs/" + urllib.parse.quote(f["file"]))
        self.call(admin, "DELETE", "/api/songs/" + urllib.parse.quote(other["file"]))
        self.call(admin, "DELETE", f"/api/books/{bid}")

    def test_share_lifetime(self):
        hans = self.client({"sub": "h-1", "preferred_username": "hans"})
        admin = self.client({"sub": "c-3", "preferred_username": "carol", "groups": ["admin"]})
        guest = self.client()
        st, book = self.call(hans, "POST", "/api/books", {"name": "Ablaufbuch", "public": False})
        bid, day = book["id"], 86_400_000
        # the default lifetime is an admin setting (built-in 30 days); only admins read or change it
        self.assertEqual(self.call(hans, "GET", "/api/admin/settings")[0], 403)
        self.assertEqual(self.call(hans, "PUT", "/api/admin/settings", {"share_days": 0})[0], 403)
        self.assertEqual(self.call(guest, "GET", "/api/admin/settings")[0], 403)
        self.assertEqual(self.call(admin, "GET", "/api/admin/settings")[1]["share_days"], 30)
        now = time.time() * 1000
        st, r = self.call(hans, "POST", f"/api/books/{bid}/share", {"on": True})
        self.assertAlmostEqual(r["share_expires"], now + 30 * day, delta=60_000)
        self.assertEqual(self.call(hans, "GET", f"/api/books/{bid}")[1]["share_days"], 30)
        for bad in (-1, 3651, "7", True, 1.5):
            self.assertEqual(self.call(admin, "PUT", "/api/admin/settings", {"share_days": bad})[0], 400, bad)
            self.assertEqual(self.call(hans, "POST", f"/api/books/{bid}/share", {"on": True, "days": bad})[0], 400, bad)
        self.assertEqual(self.call(admin, "PUT", "/api/admin/settings", {"share_days": 7})[1]["share_days"], 7)
        # existing links keep their date; new links get the new default; an explicit choice wins
        self.assertAlmostEqual(self.call(hans, "POST", f"/api/books/{bid}/share", {"on": True})[1]["share_expires"],
                               now + 30 * day, delta=60_000)
        st, r = self.call(hans, "POST", f"/api/books/{bid}/share", {"on": True, "renew": True})
        self.assertAlmostEqual(r["share_expires"], now + 7 * day, delta=60_000)
        st, r = self.call(hans, "POST", f"/api/books/{bid}/share", {"on": True, "renew": True, "days": 1})
        self.assertAlmostEqual(r["share_expires"], now + day, delta=60_000)
        tok = r["share"]
        # extend without a new token; 0 = no expiry
        st, r = self.call(hans, "POST", f"/api/books/{bid}/share", {"on": True, "days": 0})
        self.assertEqual((r["share"], r["share_expires"]), (tok, None))
        self.assertEqual(self.call(guest, "GET", f"/api/shared/{tok}")[0], 200)
        # expired: the link stops working, the book list no longer says "shared"; extending revives the same link
        self.call(hans, "POST", f"/api/books/{bid}/share", {"on": True, "days": 1})
        with self.app.tx() as c:
            c.execute("UPDATE books SET share_expires=? WHERE id=?", (int(now) - 1000, bid))
        st, err = self.call(guest, "GET", f"/api/shared/{tok}")
        self.assertEqual((st, err["error"]), (404, "This link has expired."))
        self.assertEqual(self.call(guest, "GET", f"/api/shared/{tok}/inhalt")[0], 404)
        self.assertFalse([b for b in self.call(hans, "GET", "/api/books")[1]["books"] if b["id"] == bid][0]["shared"])
        self.assertEqual(self.call(hans, "GET", f"/api/books/{bid}")[1]["share"], tok)  # the owner still sees it
        self.assertEqual(self.call(hans, "POST", f"/api/books/{bid}/share", {"on": True, "days": 90})[1]["share"], tok)
        self.assertEqual(self.call(guest, "GET", f"/api/shared/{tok}")[0], 200)
        # switching off clears the date too
        self.assertEqual(self.call(hans, "POST", f"/api/books/{bid}/share", {"on": False})[1]["share_expires"], None)
        self.call(admin, "PUT", "/api/admin/settings", {"share_days": 30})
        self.call(admin, "DELETE", f"/api/books/{bid}")

    def test_collaboration(self):
        ann = self.client({"sub": "n-1", "preferred_username": "ann", "name": "Ann"})
        ben = self.client({"sub": "b-9", "preferred_username": "ben", "name": "Ben"})
        cat = self.client({"sub": "k-7", "preferred_username": "cat", "name": "Cat"})
        admin = self.client({"sub": "c-3", "preferred_username": "carol", "groups": ["admin"]})
        guest = self.client()
        q = lambda f: "/api/songs/" + urllib.parse.quote(f)
        st, song = self.call(ann, "POST", "/api/songs", {"content": "{title: Zusammen}\n{artist: Ann}\n[C]eins\n", "public": False})
        sid, f = song["id"], song["file"]
        # the user directory is for signed-in users only
        self.assertEqual(self.call(guest, "GET", "/api/users")[0], 401)
        names = [x["username"] for x in self.call(ben, "GET", "/api/users")[1]["users"]]
        self.assertTrue({"ann", "ben", "cat"} <= set(names), names)
        # nobody but ann (and admins) sees/edits the private song yet
        self.assertEqual(self.call(ben, "GET", q(f))[0], 404)
        self.assertEqual(self.call(ben, "GET", f"/api/collab/song/{sid}")[0], 404)
        self.assertEqual(self.call(ben, "PUT", f"/api/collab/song/{sid}", {"users": ["b-9"]})[0], 404)
        # ann invites ben (unknown ids and herself are ignored)
        st, co = self.call(ann, "PUT", f"/api/collab/song/{sid}", {"users": ["b-9", "n-1", "nobody"]})
        self.assertEqual((st, co["all"], [x["username"] for x in co["users"]]), (200, False, ["ben"]))
        st, s = self.call(ben, "GET", q(f))
        self.assertEqual((st, s["editable"], s["manage"], s["collab"], s["owner"]), (200, True, False, True, "ann"))  # owner by nick, not full name
        self.assertTrue([x for x in self.call(ben, "GET", "/api/songs")[1]["songs"] if x["id"] == sid][0]["collab"])
        self.assertEqual(self.call(cat, "GET", q(f))[0], 404)
        # ben edits; the history says who did what (only to people working on the song)
        st, r = self.call(ben, "POST", "/api/songs", {"content": "{title: Zusammen}\n{artist: Ann}\n[C]eins [G]zwei\n",
                                                      "old": f, "base_mtime": s["mtime"], "public": True})
        self.assertEqual(st, 200, r)
        self.assertEqual(self.call(ann, "GET", q(f))[1]["public"], False)  # collaborators can't change visibility
        st, h = self.call(ann, "GET", f"/api/history/{sid}")
        self.assertEqual([(v["action"], v["by"]) for v in h["versions"]], [("geändert", "ben"), ("neu", "ann")])
        # but not delete it, change visibility or the collaborators
        self.assertEqual(self.call(ben, "DELETE", q(f))[0], 403)
        self.assertEqual(self.call(ben, "POST", "/api/visibility", {"song": sid, "public": True})[0], 403)
        self.assertEqual(self.call(ben, "PUT", f"/api/collab/song/{sid}", {"users": ["b-9", "k-7"]})[0], 403)
        self.assertEqual(self.call(ben, "GET", f"/api/collab/song/{sid}")[1]["manage"], False)
        # he may restore an older version
        st, r = self.call(ben, "POST", "/api/restore", {"version": h["versions"][1]["id"]})
        self.assertEqual(st, 200, r)
        # "all signed-in users": cat may edit now, guests still see nothing (the song is private)
        self.call(ann, "PUT", f"/api/collab/song/{sid}", {"all": True, "users": ["b-9"]})
        self.assertEqual(self.call(cat, "GET", q(f))[1]["editable"], True)
        self.assertEqual(self.call(guest, "GET", q(f))[0], 404)
        self.assertEqual(self.call(guest, "GET", f"/api/history/{sid}")[0], 404)
        # taking it back
        self.call(ann, "PUT", f"/api/collab/song/{sid}", {"all": False, "users": []})
        self.assertEqual(self.call(ben, "GET", q(f))[0], 404)
        self.assertEqual(self.call(cat, "POST", "/api/songs", {"content": "{title: Zusammen}\n{artist: Ann}\nx\n", "old": f})[0], 404)

        # songbook collaboration: ben may change the book's songs and edit ann's songs in it – not other people's
        st, own2 = self.call(ann, "POST", "/api/songs", {"content": "{title: Annas Zweites}\n[D]x\n", "public": False})
        st, catsong = self.call(cat, "POST", "/api/songs", {"content": "{title: Cats Lied}\n[E]x\n"})
        st, bk = self.call(ann, "POST", "/api/books", {"name": "Bandbuch", "public": False})
        bid = bk["id"]
        for x in (song, own2):
            self.call(ann, "POST", f"/api/books/{bid}/lied", {"song": x["id"], "add": True})
        self.call(ann, "POST", f"/api/books/{bid}/lied", {"song": catsong["id"], "add": True})
        self.assertEqual(self.call(ben, "GET", f"/api/books/{bid}")[0], 404)
        self.call(ann, "PUT", f"/api/collab/book/{bid}", {"users": ["b-9"]})
        st, b = self.call(ben, "GET", f"/api/books/{bid}")
        self.assertEqual((st, b["editable"], b["manage"], b["share"]), (200, True, False, None))
        self.assertEqual([x["title"] for x in b["songs"]], ["Zusammen", "Annas Zweites", "Cats Lied"])
        lst = [x for x in self.call(ben, "GET", "/api/books")[1]["books"] if x["id"] == bid][0]
        self.assertEqual((lst["together"], lst["collab"], lst["count"]), (True, True, 3))
        self.assertEqual(self.call(ben, "GET", q(own2["file"]))[1]["editable"], True)
        self.assertEqual(self.call(ben, "GET", q(catsong["file"]))[1]["editable"], False)  # cat's song: read only
        self.assertEqual(self.call(ben, "POST", "/api/songs", {"content": "{title: Cats Lied}\n[E]y\n", "old": catsong["file"]})[0], 403)
        self.assertEqual(self.call(ben, "PUT", f"/api/books/{bid}", {"name": "Bandbuch 2"})[0], 200)
        self.assertIn(bid, self.call(ben, "GET", q(own2["file"]))[1]["books"])  # shows in his 📚 dialog
        self.assertEqual(self.call(ben, "POST", f"/api/books/{bid}/lied", {"song": own2["id"], "add": False})[0], 200)
        self.assertEqual(self.call(ben, "GET", q(own2["file"]))[0], 404)  # out of the book: private again for him
        for path, body in ((f"/api/books/{bid}/share", {"on": True}), ("/api/visibility", {"book": bid, "public": True})):
            self.assertEqual(self.call(ben, "POST", path, body)[0], 403, path)
        self.assertEqual(self.call(ben, "DELETE", f"/api/books/{bid}")[0], 403)
        self.assertEqual(self.call(ben, "PUT", f"/api/collab/book/{bid}", {"users": []})[0], 403)
        # deleting the user removes the collaboration
        self.call(admin, "DELETE", "/api/admin/users/b-9?mode=transfer")
        with self.app.tx() as c:
            self.assertEqual(c.execute("SELECT count(*) FROM collab WHERE who='b-9'").fetchone()[0], 0)
        self.call(ann, "DELETE", f"/api/books/{bid}")
        with self.app.tx() as c:
            self.assertEqual(c.execute("SELECT count(*) FROM collab WHERE kind='book' AND rid=?", (bid,)).fetchone()[0], 0)
        for x in (song, own2):
            self.call(ann, "DELETE", q(x["file"]))
        self.call(cat, "DELETE", q(catsong["file"]))

    def test_import_over_existing_song(self):
        """Importing a song that exists: conflict with the file name; overwrite = next version of that song."""
        ann = self.client({"sub": "n-1", "preferred_username": "ann", "name": "Ann"})
        q = lambda f: "/api/songs/" + urllib.parse.quote(f)
        st, a = self.call(ann, "POST", "/api/songs", {"content": "{title: Doppelt}\n[C]alt\n"})
        st, err = self.call(ann, "POST", "/api/songs", {"content": "{title: Doppelt}\n[C]neu\n"})
        self.assertEqual((st, err["conflict"], err["file"], err["editable"]), (409, "exists", a["file"], True))
        st, b = self.call(ann, "POST", "/api/songs", {"content": "{title: Doppelt}\n[C]neu\n", "overwrite": True})
        self.assertEqual((st, b["id"], b["file"]), (200, a["id"], a["file"]))  # same song, history kept
        st, h = self.call(ann, "GET", f"/api/history/{a['id']}")
        self.assertEqual([v["action"] for v in h["versions"]], ["importiert", "neu"])
        st, c2 = self.call(ann, "POST", "/api/songs", {"content": "{title: Doppelt}\n[C]drei\n", "copy": True})
        self.assertEqual((st, c2["file"]), (200, "Doppelt (2).cho"))
        # the same text again: no extra version
        self.call(ann, "POST", "/api/songs", {"content": "{title: Doppelt}\n[C]neu\n", "overwrite": True})
        self.assertEqual(len(self.call(ann, "GET", f"/api/history/{a['id']}")[1]["versions"]), 2)
        for f in (a["file"], c2["file"]):
            self.call(ann, "DELETE", q(f))

    def test_chord_notation_setting(self):
        """Chord names on screen: per user (intl/german), default for everybody set by admins."""
        ann = self.client({"sub": "n-1", "preferred_username": "ann", "name": "Ann"})
        admin = self.client({"sub": "c-3", "preferred_username": "carol", "groups": ["admin"]})
        guest = self.client()
        me = lambda o: {k: v for k, v in self.call(o, "GET", "/api/me")[1].items() if k.startswith("notation")}
        self.assertEqual(me(ann), {"notation": None, "notation_default": "intl"})
        self.assertEqual(self.call(guest, "PUT", "/api/me/notation", {"notation": "german"})[0], 401)
        self.assertEqual(self.call(ann, "PUT", "/api/me/notation", {"notation": "deutsch"})[0], 400)
        self.assertEqual(self.call(ann, "PUT", "/api/me/notation", {"notation": "german"})[1]["notation"], "german")
        self.assertEqual(me(ann), {"notation": "german", "notation_default": "intl"})
        # admin default: only admins; applies to users without their own choice and to guests
        self.assertEqual(self.call(ann, "PUT", "/api/admin/settings", {"notation": "german"})[0], 403)
        self.assertEqual(self.call(admin, "PUT", "/api/admin/settings", {"notation": "x"})[0], 400)
        self.assertEqual(self.call(admin, "PUT", "/api/admin/settings", {"notation": "german"})[1]["notation"], "german")
        self.assertEqual(me(guest), {"notation": None, "notation_default": "german"})
        self.assertEqual(self.call(ann, "PUT", "/api/me/notation", {"notation": None})[1]["notation"], None)  # back to default
        self.assertEqual(me(ann), {"notation": None, "notation_default": "german"})
        self.assertEqual(self.call(admin, "GET", "/api/admin/settings")[1]["notation"], "german")
        self.call(admin, "PUT", "/api/admin/settings", {"notation": "intl"})

    def test_guest_access_off(self):
        """GUEST_ACCESS=off: guests see nothing but share links; signed-in users see public things as before."""
        ann = self.client({"sub": "n-1", "preferred_username": "ann", "name": "Ann"})
        guest = self.client()
        q = lambda f: "/api/songs/" + urllib.parse.quote(f)
        st, song = self.call(ann, "POST", "/api/songs", {"content": "{title: Offenes Lied}\n[C]x\n"})
        st, book = self.call(ann, "POST", "/api/books", {"name": "Offenes Buch"})
        self.call(ann, "POST", f"/api/books/{book['id']}/lied", {"song": song["id"], "add": True})
        tok = self.call(ann, "POST", f"/api/books/{book['id']}/share", {"on": True})[1]["share"]
        self.assertEqual(self.call(guest, "GET", q(song["file"]))[0], 200)  # default: guests read public songs
        self.app.GUEST_ACCESS = False
        try:
            self.assertEqual(self.call(guest, "GET", "/api/me")[1]["guest_access"], False)
            self.assertEqual(self.call(guest, "GET", "/api/songs")[1]["songs"], [])
            self.assertEqual(self.call(guest, "GET", "/api/books")[1]["books"], [])
            self.assertEqual(self.call(guest, "GET", q(song["file"]))[0], 404)
            self.assertEqual(self.call(guest, "GET", f"/api/books/{book['id']}")[0], 404)
            self.assertEqual(self.call(guest, "GET", f"/api/history/{song['id']}")[0], 404)
            # the share link still works, song included
            st, b = self.call(guest, "GET", f"/api/shared/{tok}")
            self.assertEqual((st, [x["title"] for x in b["songs"]]), (200, ["Offenes Lied"]))
            self.assertEqual(self.call(guest, "GET", f"/api/shared/{tok}/songs/" + urllib.parse.quote(song["file"]))[0], 200)
            # signed-in users: unchanged
            self.assertIn(song["id"], [x["id"] for x in self.call(ann, "GET", "/api/songs")[1]["songs"]])
            self.assertEqual(self.call(ann, "GET", "/api/me")[1]["guest_access"], False)
        finally:
            self.app.GUEST_ACCESS = True
        self.call(ann, "DELETE", f"/api/books/{book['id']}")
        self.call(ann, "DELETE", q(song["file"]))

    def test_bulk_edit(self):
        ann = self.client({"sub": "n-1", "preferred_username": "ann", "name": "Ann"})
        ben = self.client({"sub": "b-9", "preferred_username": "ben", "name": "Ben"})
        guest = self.client()
        q = lambda f: "/api/songs/" + urllib.parse.quote(f)
        text = lambda f: self.call(ann, "GET", q(f))[1]["content"]
        mk = lambda who, t: self.call(who, "POST", "/api/songs", {"content": t})[1]
        a = mk(ann, "{title: Bulk A}\n{artist: Ann}\n{key: C}\n{transpose: 2}\n[C]eins\n")
        b = mk(ann, "{title: Bulk B}\n{artist: Ann}\n[G]zwei\n")
        o = mk(ann, "{title: Bulk Alt}\n{x_transpose: -1}\n[D]alt\n")
        x = mk(ben, "{title: Bens Lied}\n[E]drei\n")
        bulk = lambda who, ids, ch: self.call(who, "POST", "/api/songs/bulk", {"ids": ids, "changes": ch})
        ids = [a["id"], b["id"], o["id"]]
        # input checks
        self.assertEqual(bulk(guest, ids, {"public": False})[0], 401)
        self.assertEqual(bulk(ann, [], {"public": False})[0], 400)
        self.assertEqual(bulk(ann, ids, {})[0], 400)
        self.assertEqual(bulk(ann, ids, {"key": "Hallo"})[0], 400)
        self.assertEqual(bulk(ann, ids, {"transpose_by": 12})[0], 400)
        # visibility + key + instrument in one go; ben's song is skipped (not hers)
        st, r = bulk(ann, ids + [x["id"]], {"public": False, "key": "G", "instrument": "ukulele"})
        self.assertEqual((st, r["changed"], [(s["title"], s["reason"]) for s in r["skipped"]]), (200, 3, [("Bens Lied", "keine Berechtigung")]))
        self.assertEqual(self.call(ben, "GET", q(a["file"]))[0], 404)  # private now
        self.assertIn("{key: G}", text(a["file"]))
        self.assertNotIn("{key: C}", text(a["file"]))
        self.assertTrue(text(b["file"]).startswith("{title: Bulk B}\n{artist: Ann}\n{key: G}\n{x_instrument: ukulele}\n"), text(b["file"]))
        h = self.call(ann, "GET", f"/api/history/{a['id']}")[1]["versions"]
        self.assertEqual((h[0]["action"], h[0]["by"]), ("Sammelbearbeitung", "ann"))
        # transpose: moves the song's own {transpose}, converts the old x_transpose, 0 removes it
        bulk(ann, ids, {"transpose_by": 2})
        self.assertIn("{transpose: 4}", text(a["file"]))
        self.assertIn("{transpose: 2}", text(b["file"]))
        self.assertIn("{transpose: 1}", text(o["file"]))
        self.assertNotIn("x_transpose", text(o["file"]))
        self.assertIn("[C]eins", text(a["file"]))  # chords in the text unchanged
        bulk(ann, [b["id"]], {"transpose_by": -2})
        self.assertNotIn("transpose", text(b["file"]))
        bulk(ann, ids, {"key": "", "instrument": ""})
        self.assertNotIn("{key:", text(a["file"]))
        self.assertNotIn("x_instrument", text(b["file"]))
        # collaborators: add ben -> he may change the key, but not visibility or delete
        bulk(ann, ids, {"collab": {"add": ["b-9", "nobody", "n-1"]}})
        self.assertEqual([u["username"] for u in self.call(ann, "GET", f"/api/collab/song/{a['id']}")[1]["users"]], ["ben"])
        st, r = bulk(ben, [a["id"]], {"key": "D"})
        self.assertEqual((st, r["changed"]), (200, 1))
        st, r = bulk(ben, [a["id"]], {"public": True})
        self.assertEqual((r["changed"], r["skipped"][0]["reason"]), (0, "keine Berechtigung"))
        self.assertEqual(bulk(ben, [a["id"]], {"delete": True})[1]["changed"], 0)
        bulk(ann, ids, {"collab": {"remove": ["b-9"], "all": True}})
        self.assertEqual(self.call(ann, "GET", f"/api/collab/song/{a['id']}")[1]["all"], True)
        bulk(ann, ids, {"collab": {"all": False}})
        self.assertEqual(self.call(ben, "GET", q(a["file"]))[0], 404)
        # songbooks
        bk = self.call(ann, "POST", "/api/books", {"name": "Bulkbuch"})[1]["id"]
        bulk(ann, ids, {"book_add": bk})
        self.assertEqual([s["title"] for s in self.call(ann, "GET", f"/api/books/{bk}")[1]["songs"]], ["Bulk A", "Bulk B", "Bulk Alt"])
        bulk(ann, [b["id"]], {"book_remove": bk})
        self.assertEqual(len(self.call(ann, "GET", f"/api/books/{bk}")[1]["songs"]), 2)
        self.assertEqual(bulk(ben, [x["id"]], {"book_add": bk})[0], 403)  # public book of ann: visible, not his to change
        # owner shown by nick to other signed-in users
        bulk(ann, [a["id"]], {"public": True})
        self.assertEqual(self.call(ben, "GET", q(a["file"]))[1]["owner"], "ann")
        # delete: into the trash, restorable
        st, r = bulk(ann, ids, {"delete": True})
        self.assertEqual(r["changed"], 3)
        self.assertEqual(self.call(ann, "GET", q(a["file"]))[0], 404)
        self.assertEqual({s["title"] for s in self.call(ann, "GET", "/api/deleted")[1]["songs"]} >= {"Bulk A", "Bulk B", "Bulk Alt"}, True)
        self.call(ann, "DELETE", f"/api/books/{bk}")
        self.call(ben, "DELETE", q(x["file"]))

    def test_campfire_mode(self):
        """Campfire mode: a songbook open to everybody for a few days, without login or link – also with guest access off."""
        ann = self.client({"sub": "n-1", "preferred_username": "ann", "name": "Ann"})
        ben = self.client({"sub": "b-9", "preferred_username": "ben", "name": "Ben"})
        admin = self.client({"sub": "c-3", "preferred_username": "carol", "groups": ["admin"]})
        guest = self.client()
        q = lambda f: "/api/songs/" + urllib.parse.quote(f)
        mk = lambda who, t, pub=True: self.call(who, "POST", "/api/songs", {"content": t, "public": pub})[1]
        mine = mk(ann, "{title: Lagerlied}\n[C]x\n", False)
        other = mk(ben, "{title: Bens Geheimnis}\n[D]y\n", False)
        alone = mk(ann, "{title: Nicht im Buch}\n[E]z\n", False)
        bid = self.call(ann, "POST", "/api/books", {"name": "Sommerlager", "public": False})[1]["id"]
        for x in (mine, other):
            self.call(admin, "POST", f"/api/books/{bid}/lied", {"song": x["id"], "add": True})
        # default lifetime: admin setting, 1–21 days
        self.assertEqual(self.call(admin, "GET", "/api/admin/settings")[1]["campfire_days"], 7)
        for bad in (0, 22, "3", True):
            self.assertEqual(self.call(admin, "PUT", "/api/admin/settings", {"campfire_days": bad})[0], 400, bad)
            if bad != 0:
                self.assertEqual(self.call(ann, "POST", f"/api/books/{bid}/campfire", {"days": bad})[0], 400, bad)
        self.assertEqual(self.call(admin, "PUT", "/api/admin/settings", {"campfire_days": 10})[1]["campfire_days"], 10)
        self.app.GUEST_ACCESS = False
        try:
            self.assertEqual(self.call(guest, "GET", f"/api/books/{bid}")[0], 404)
            self.assertEqual(self.call(guest, "GET", "/api/me")[1]["campfire"], [])
            # only owner/admin may switch it on
            self.assertEqual(self.call(ben, "POST", f"/api/books/{bid}/campfire", {})[0], 404)
            self.assertEqual(self.call(guest, "POST", f"/api/books/{bid}/campfire", {})[0], 404)
            now = time.time() * 1000
            st, r = self.call(ann, "POST", f"/api/books/{bid}/campfire", {})
            self.assertAlmostEqual(r["campfire_until"], now + 10 * 86_400_000, delta=60_000)  # admin default
            st, r = self.call(ann, "POST", f"/api/books/{bid}/campfire", {"days": 3})
            self.assertAlmostEqual(r["campfire_until"], now + 3 * 86_400_000, delta=60_000)
            # guests: book listed on the start page, opens, songs play – but not others' private songs, no history
            fires = self.call(guest, "GET", "/api/me")[1]["campfire"]
            self.assertEqual([(f["id"], f["name"]) for f in fires], [(bid, "Sommerlager")])
            st, b = self.call(guest, "GET", f"/api/books/{bid}")
            self.assertEqual((st, b["via_campfire"], b["editable"], b["manage"], [x["title"] for x in b["songs"]]),
                             (200, True, False, False, ["Lagerlied"]))
            self.assertAlmostEqual(b["campfire_until"], now + 3 * 86_400_000, delta=60_000)
            self.assertEqual(self.call(guest, "GET", q(mine["file"]))[0], 200)
            self.assertEqual(self.call(guest, "GET", q(other["file"]))[0], 404)  # ben's private song stays hidden
            self.assertEqual(self.call(guest, "GET", q(alone["file"]))[0], 404)  # not in the book
            self.assertEqual(self.call(guest, "GET", f"/api/history/{mine['id']}")[0], 404)
            self.assertEqual(self.call(guest, "GET", "/api/songs")[1]["songs"], [])  # not in the general list
            self.assertIn(bid, [x["id"] for x in self.call(guest, "GET", "/api/books")[1]["books"]])
            with guest.open(self.base + f"/api/books/{bid}/export.cho") as resp:
                txt = resp.read().decode()
            self.assertIn("Lagerlied", txt)
            self.assertNotIn("Bens Geheimnis", txt)
            # read only for guests and other users
            self.assertIn(self.call(ben, "PUT", f"/api/books/{bid}", {"name": "Meins"})[0], (403, 404))  # not his: no change
            self.assertEqual(self.call(guest, "POST", "/api/songs", {"content": "{title: x}\n", "old": mine["file"]})[0], 401)
            # switched off -> closed again
            self.call(ann, "POST", f"/api/books/{bid}/campfire", {"days": 0})
            self.assertEqual(self.call(guest, "GET", f"/api/books/{bid}")[0], 404)
            self.assertEqual(self.call(guest, "GET", q(mine["file"]))[0], 404)
            # expired -> closed
            self.call(ann, "POST", f"/api/books/{bid}/campfire", {"days": 1})
            with self.app.tx() as c:
                c.execute("UPDATE books SET campfire_until=? WHERE id=?", (int(now) - 1000, bid))
            self.assertEqual(self.call(guest, "GET", f"/api/books/{bid}")[0], 404)
            self.assertEqual(self.call(guest, "GET", "/api/me")[1]["campfire"], [])
        finally:
            self.app.GUEST_ACCESS = True
            self.call(admin, "PUT", "/api/admin/settings", {"campfire_days": 7})
        self.call(ann, "DELETE", f"/api/books/{bid}")
        for x, who in ((mine, ann), (alone, ann), (other, ben)):
            self.call(who, "DELETE", q(x["file"]))

    def test_copy_song(self):
        """A user's own version of an existing song: someone else's -> "(nick)", own -> "(2)"; original unchanged."""
        ann = self.client({"sub": "n-1", "preferred_username": "ann", "name": "Ann"})
        ben = self.client({"sub": "b-9", "preferred_username": "ben", "name": "Ben"})
        guest = self.client()
        q = lambda f: "/api/songs/" + urllib.parse.quote(f)
        st, orig = self.call(ann, "POST", "/api/songs", {"content": "{title: Vorlage}\n{artist: Ann}\n[C]Original\n"})
        st, priv = self.call(ann, "POST", "/api/songs", {"content": "{title: Geheimvorlage}\n[D]x\n", "public": False})
        self.assertEqual(self.call(guest, "POST", "/api/copy", {"file": orig["file"]})[0], 401)
        self.assertEqual(self.call(ben, "POST", "/api/copy", {"file": priv["file"]})[0], 404)  # can't see it
        self.assertEqual(self.call(ben, "POST", "/api/copy", {"file": "../x.cho"})[0], 400)
        st, mine = self.call(ben, "POST", "/api/copy", {"file": orig["file"]})
        self.assertEqual((st, mine["file"]), (200, "Ann - Vorlage (ben).cho"))
        s = self.call(ben, "GET", q(mine["file"]))[1]
        self.assertEqual((s["owner"], s["mine"], s["manage"], s["public"], s["content"]), ("ben", True, True, True, "{title: Vorlage}\n{artist: Ann}\n[C]Original\n"))
        h = self.call(ben, "GET", f"/api/history/{mine['id']}")[1]["versions"]
        self.assertEqual((len(h), h[0]["action"], h[0]["by"]), (1, "Kopie von „Vorlage“ (ann)", "ben"))
        # ben changes his version; ann's stays
        st, r = self.call(ben, "POST", "/api/songs", {"content": "{title: Vorlage}\n{artist: Ann}\n[G]Bens Fassung\n", "old": mine["file"]})
        self.assertEqual((st, r["file"]), (200, mine["file"]))
        self.assertIn("[C]Original", self.call(ann, "GET", q(orig["file"]))[1]["content"])
        h2 = self.call(ben, "GET", f"/api/history/{mine['id']}")[1]["versions"]
        st, r = self.call(ben, "POST", "/api/restore", {"version": h2[-1]["id"]})  # back to the copied text
        self.assertEqual((st, r.get("file")), (200, mine["file"]), r)
        # a copy of one's own song: "(2)", private stays private; editing it keeps the name (no "already exists")
        st, again = self.call(ann, "POST", "/api/copy", {"file": priv["file"]})
        self.assertEqual((st, again["file"]), (200, "Geheimvorlage (2).cho"))
        self.assertFalse(self.call(ann, "GET", q(again["file"]))[1]["public"])
        st, r = self.call(ann, "POST", "/api/songs", {"content": "{title: Geheimvorlage}\n[E]geändert\n", "old": again["file"]})
        self.assertEqual((st, r.get("file")), (200, again["file"]), r)
        # a changed title gives the version a new name again
        st, r = self.call(ben, "POST", "/api/songs", {"content": "{title: Bens Lied}\n[G]x\n", "old": mine["file"]})
        self.assertEqual((st, r["file"]), (200, "Bens Lied.cho"))
        mine["file"] = r["file"]
        for who, f in ((ben, mine["file"]), (ann, orig["file"]), (ann, priv["file"]), (ann, again["file"])):
            self.call(who, "DELETE", q(f))

    def test_denied_login_offers_other_account(self):
        cfg = self.app.OIDC.cfg
        cfg.allowed_groups = ["band"]
        try:
            self.client({"sub": "z-1", "preferred_username": "zoe", "groups": ["other"]})
            self.fail("not refused")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 403)
            page = e.read().decode()
            self.assertIn("group missing", page)
            self.assertIn("/realm/logout?", page)  # sign out at the provider to try another account
        finally:
            cfg.allowed_groups = []

    def test_attacks(self):
        bob = self.client({"sub": "b-2", "preferred_username": "bob"})
        # changes from other sites are refused
        st, r = self.call(bob, "POST", "/api/books", {"name": "x"}, {"Origin": "https://evil.example"})
        self.assertEqual(st, 403)
        # callback with an unknown state / login page error -> error page, no session
        for qs in ("code=c99&state=nope", "error=access_denied"):
            try:
                bob.open(self.base + "/auth/callback?" + qs)
                self.fail("no error")
            except urllib.error.HTTPError as e:
                self.assertEqual(e.code, 400)
        # only own hash routes as return target
        self.assertEqual(self.app.safe_return("https://evil.example/"), "#/")
        self.assertEqual(self.app.safe_return("#/lied/x"), "#/lied/x")
        # forged cookie
        forged = self.client()
        forged.addheaders = [("Cookie", "diss_session=abc")]
        self.assertIsNone(self.call(forged, "GET", "/api/me")[1]["user"])


class RequireDb(unittest.TestCase):
    """REQUIRE_DB=on: an unmounted song folder (empty mountpoint) must not get a fresh, empty database."""

    def run_app(self, song_dir, require):
        import socket, subprocess, sys, tempfile  # noqa: E401
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]
        env = {k: v for k, v in os.environ.items() if not k.startswith("OIDC_")}
        env.update(SONG_DIR=song_dir, PORT=str(port), REQUIRE_DB="on" if require else "off")
        p = subprocess.Popen([sys.executable, "-I", os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")],
                             env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.addCleanup(lambda: (p.poll() is None and p.kill(), p.wait()))
        return p, f"http://127.0.0.1:{port}/healthz"

    def health(self, url):
        for _ in range(100):
            try:
                return urllib.request.urlopen(url, timeout=2).status
            except urllib.error.HTTPError as e:
                return e.code
            except OSError:
                time.sleep(0.1)
        self.fail("app did not start")

    def test_missing_db_refuses_to_start(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p, _ = self.run_app(d, True)
            out = p.communicate(timeout=20)[0]
            self.assertNotEqual(p.returncode, 0)
            self.assertIn("is the song folder mounted", out)
            self.assertEqual(os.listdir(d), [])  # no new database created

    def test_db_removed_while_running_is_unhealthy(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p, url = self.run_app(d, False)  # first start: creates the database
            self.assertEqual(self.health(url), 200)
            p.kill(); p.wait()
            p, url = self.run_app(d, True)
            self.assertEqual(self.health(url), 200)
            os.rename(os.path.join(d, ".liederbuch.db"), os.path.join(d, "moved.db"))  # like an unmount
            self.assertEqual(self.health(url), 503)


if __name__ == "__main__":
    unittest.main()
