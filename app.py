"""Dissonance: UG -> ChordPro converter + songbook (stdlib only). Listens on :8080.

Songs are plain .cho files in SONG_DIR (default /songs); deleted songs go to SONG_DIR/.papierkorb/.
Version history, songbooks, users: SQLite database SONG_DIR/.liederbuch.db.
Login via any OpenID Connect provider when OIDC_ISSUER is set (auth.py, README); without it everybody is admin.
"""
import contextlib
import hashlib
import html
import http
import http.cookies
import io
import json
import os
import re
import secrets
import sqlite3
import sys
import tempfile
import threading
import time
import urllib.parse
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ug2chordpro as ug  # noqa: E402
import auth  # noqa: E402
import i18n  # noqa: E402

MAX_BODY = 20 * 1024 * 1024
MAX_SONG = 1024 * 1024
SONG_DIR = Path(os.environ.get("SONG_DIR", "/songs"))
TRASH = ".papierkorb"
DB_NAME = ".liederbuch.db"
PUBLIC_URL = os.environ.get("PUBLIC_URL", "").rstrip("/")  # e.g. https://songs.example.com
SESSION_DAYS = 30
# GUEST_ACCESS=off (with login): people who are not signed in see nothing except share links – for servers on the
# internet, where "public" songs would otherwise be readable by everybody (lyrics are usually copyrighted).
GUEST_ACCESS = os.environ.get("GUEST_ACCESS", "on").strip().lower() not in ("off", "0", "false", "no")
# REQUIRE_DB=on: never create a new database – refuse to start (and report unhealthy) when SONG_DIR/.liederbuch.db is
# missing. Protects against a song folder that is not mounted: an empty mountpoint would otherwise get a fresh, empty
# database and the app would show no songs, users or songbooks. Set it once the database exists.
REQUIRE_DB = os.environ.get("REQUIRE_DB", "off").strip().lower() in ("on", "1", "true", "yes")
ROBOTS = b"User-agent: *\nDisallow: /\n"  # private songbook: no search engines (also X-Robots-Tag on every response)
COOKIE = "diss_session"


def _oidc():
    try:
        cfg = auth.Config.from_env()
    except (OSError, ValueError) as e:
        sys.exit(f"OIDC configuration: {e}")
    if cfg is None:
        return None
    if not PUBLIC_URL:
        sys.exit("OIDC_ISSUER is set, but PUBLIC_URL (e.g. https://chords.example.com) is missing")
    return auth.OIDC(cfg, PUBLIC_URL + "/auth/callback")


OIDC = _oidc()
LOCAL_ADMIN = {"sub": None, "name": "", "username": "", "admin": True}  # no login configured: full access
STATIC = {  # path -> (file, content type)
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/sw.js": ("sw.js", "text/javascript; charset=utf-8"),
    "/manifest.webmanifest": ("manifest.webmanifest", "application/manifest+json"),
    "/icon.svg": ("icon.svg", "image/svg+xml"),
    "/chords.json": ("chords.json", "application/json"),
    "/icon-192.png": ("icon-192.png", "image/png"),
    "/icon-512.png": ("icon-512.png", "image/png"),
    "/icon-maskable-512.png": ("icon-maskable-512.png", "image/png"),
    "/apple-touch-icon.png": ("apple-touch-icon.png", "image/png"),
    "/nosleep.mp4": ("nosleep.mp4", "video/mp4"),
    "/nosleep.webm": ("nosleep.webm", "video/webm"),
}
SONG_NAME_RE = re.compile(r"^[^/\\\x00-\x1f]+\.cho$")
DIRECTIVE_RE = re.compile(r"^\{\s*([a-z_]+)(?:\s*:\s*|\s+)(.*?)\s*\}\s*$", re.I | re.M)  # {title: X} or {title X}
ALIASES = {"t": "title", "st": "subtitle"}


class HttpError(i18n.Message):
    """Error answer; the text is German with {placeholders} (fmt), translated per request (i18n.py)."""

    def __init__(self, code, msg, fmt=None, **extra):
        super().__init__(msg, **(fmt or {}))
        self.code, self.extra = code, extra


# ---------------------------------------------------------------- converter

def do_convert(req, lang="en"):
    src, value = req.get("source"), (req.get("value") or "")
    opts = {
        "steps": int(req.get("transpose") or 0),
        "flats": {"sharp": False, "flat": True}.get(req.get("spelling")),
        "apply_capo": bool(req.get("apply_capo")),
        "instrument": req.get("instrument") if req.get("instrument") in ug.INSTRUMENTS else "",
        "lang": lang,
    }
    if not value.strip():
        raise ug.ConvertError("Keine Eingabe.")
    if src == "url":
        page = ug.fetch_page(value)
        try:
            s, text = ug.convert_page(page, **opts)
        except ug.AlbumPage as e:  # ukulele-tabs.com album link: follow it to the song once
            if not e.url:
                raise
            s, text = ug.convert_page(ug.fetch_page(e.url), **opts)
    elif src == "html":
        s, text = ug.convert_page(value, **opts)
    elif src == "text":
        s = {"title": (req.get("title") or "").strip(), "artist": (req.get("artist") or "").strip()}
        text = ug.convert(value, s["title"], s["artist"], **opts)
    else:
        raise ug.ConvertError("Unbekannte Quelle.")
    return {"ok": True, "title": s["title"], "artist": s["artist"], "instrument": opts["instrument"] if src == "text" else s["instrument"],
            "filename": ug.filename(s["title"], s["artist"]), "chordpro": text}


def make_zip(files):
    buf, used = io.BytesIO(), set()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            name = ug.filename(os.path.splitext(f.get("name") or "song")[0], "")
            base, n = name[:-4], 2
            while name in used:
                name, n = f"{base} ({n}).cho", n + 1
            used.add(name)
            z.writestr(name, f.get("content") or "")
    return buf.getvalue()


# ---------------------------------------------------------------- songbook

def meta_of(text):
    meta = {}
    for k, v in DIRECTIVE_RE.findall(text[:4000]):
        k = ALIASES.get(k.lower(), k.lower())
        if k == "meta" and (mm := re.match(r"(\S+)\s+(.*)", v)):  # {meta: artist Foo}
            k, v = ALIASES.get(mm[1].lower(), mm[1].lower()), mm[2]
        if k in ("title", "artist", "key", "capo", "subtitle", "x_instrument", "sorttitle", "sortartist") and k not in meta:
            meta[k] = v
    return meta


def song_path(name):
    name = urllib.parse.unquote(name)
    if not SONG_NAME_RE.match(name) or name.startswith(".") or name != os.path.basename(name):
        raise HttpError(400, "Ungültiger Dateiname.")
    return SONG_DIR / name


def mtime_of(p):
    return p.stat().st_mtime_ns // 1_000_000  # ms, fits JS numbers


_meta_cache = {}


def now_ms():
    return time.time_ns() // 1_000_000


def single():
    """Single-user server: no login configured, whoever reaches it may do everything. Things that only make sense
    with several people (visibility, share links, campfire mode, collaborators) do not exist there."""
    return OIDC is None


def not_single():
    if single():
        raise HttpError(404, "Nicht gefunden.")


def note(c, u, action, kind=None, rid=None, detail=None):
    """Activity record of a signed-in user (see the activity table)."""
    if u and u.get("sub"):
        c.execute("INSERT INTO activity (at, user, action, kind, rid, detail) VALUES (?, ?, ?, ?, ?, ?)",
                  (now_ms(), u["sub"], action, kind, rid, detail))


def song_title(c, sid):
    """Title of a song for the activity record (also for deleted songs)."""
    try:
        text, file = head_of(c, sid)
    except TypeError:
        return ""
    return meta_of(text).get("title") or (file or "")[:-4]


# History + songbooks live in a small SQLite database next to the songs. The .cho files stay the source of truth;
# every saved state is stored once as a blob (sha256, like git objects) and each save adds a version row.
SCHEMA = """
CREATE TABLE IF NOT EXISTS blobs (sha TEXT PRIMARY KEY, content TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS songs (id INTEGER PRIMARY KEY, file TEXT UNIQUE, mtime INTEGER, deleted INTEGER);
CREATE TABLE IF NOT EXISTS versions (id INTEGER PRIMARY KEY, song INTEGER NOT NULL REFERENCES songs(id),
  sha TEXT NOT NULL REFERENCES blobs(sha), file TEXT NOT NULL, at INTEGER NOT NULL, action TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS versions_song ON versions(song, id);
CREATE TABLE IF NOT EXISTS tempos (song INTEGER NOT NULL REFERENCES songs(id), device TEXT NOT NULL,
  speed INTEGER NOT NULL, updated INTEGER NOT NULL, PRIMARY KEY (song, device));
CREATE TABLE IF NOT EXISTS books (id INTEGER PRIMARY KEY, name TEXT NOT NULL, updated INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS book_songs (book INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
  song INTEGER NOT NULL REFERENCES songs(id), pos INTEGER NOT NULL, PRIMARY KEY (book, song));
CREATE TABLE IF NOT EXISTS users (sub TEXT PRIMARY KEY, username TEXT, name TEXT, admin INTEGER NOT NULL DEFAULT 0,
  last_login INTEGER);
CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, sub TEXT NOT NULL REFERENCES users(sub), expires INTEGER NOT NULL,
  id_token TEXT);
CREATE TABLE IF NOT EXISTS user_tempos (song INTEGER NOT NULL REFERENCES songs(id), device TEXT NOT NULL, user TEXT NOT NULL,
  speed INTEGER NOT NULL, updated INTEGER NOT NULL, PRIMARY KEY (song, device, user));
CREATE TABLE IF NOT EXISTS favorites (user TEXT NOT NULL, song INTEGER NOT NULL REFERENCES songs(id), added INTEGER NOT NULL,
  PRIMARY KEY (user, song));
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS collab (kind TEXT NOT NULL, rid INTEGER NOT NULL, who TEXT NOT NULL, PRIMARY KEY (kind, rid, who));
CREATE TABLE IF NOT EXISTS activity (id INTEGER PRIMARY KEY, at INTEGER NOT NULL, user TEXT NOT NULL, action TEXT NOT NULL,
  kind TEXT, rid INTEGER, detail TEXT);
CREATE INDEX IF NOT EXISTS activity_user ON activity(user, at);
"""
# collab: who may edit a song (kind "song") or songbook ("book") besides its owner and the admins –
# who = OIDC "sub" of a user, or "*" for every signed-in user. versions.user = "sub" of who saved it (NULL: outside
# the app, or from before this was recorded).
# activity: what a user did besides saving song texts (those are in versions.user): logins, songbooks, sharing,
# visibility, owners, collaborators – for the admin's user page. Only with login (single-user servers have no users).
# owner = OIDC "sub" of the creator (NULL: from before the user system or added outside the app – only admins edit it); public 1/0
OWNED = ("songs", "books")
_db, _db_lock = None, threading.Lock()


@contextlib.contextmanager
def tx():
    """One connection, one writer at a time (a handful of users); commits on success."""
    global _db
    with _db_lock:
        if _db is None:
            if REQUIRE_DB:  # mode=rw: fails instead of creating an empty database
                _db = sqlite3.connect(f"file:{urllib.parse.quote(str(SONG_DIR / DB_NAME))}?mode=rw", uri=True,
                                      check_same_thread=False)
            else:
                _db = sqlite3.connect(SONG_DIR / DB_NAME, check_same_thread=False)
            _db.execute("PRAGMA foreign_keys = ON")
            _db.executescript(SCHEMA)
            for table in OWNED:
                cols = {r[1] for r in _db.execute(f"PRAGMA table_info({table})")}
                if "owner" not in cols:
                    _db.execute(f"ALTER TABLE {table} ADD COLUMN owner TEXT")
                if "public" not in cols:
                    _db.execute(f"ALTER TABLE {table} ADD COLUMN public INTEGER NOT NULL DEFAULT 1")
            if "share" not in {r[1] for r in _db.execute("PRAGMA table_info(books)")}:
                _db.execute("ALTER TABLE books ADD COLUMN share TEXT")  # secret token of the share link (NULL: not shared)
            _db.execute("CREATE UNIQUE INDEX IF NOT EXISTS books_share ON books(share)")
            if "notation" not in {r[1] for r in _db.execute("PRAGMA table_info(users)")}:
                _db.execute("ALTER TABLE users ADD COLUMN notation TEXT")  # chord names: intl/german, NULL = app default
            if "user" not in {r[1] for r in _db.execute("PRAGMA table_info(versions)")}:
                _db.execute("ALTER TABLE versions ADD COLUMN user TEXT")
            if "share_expires" not in {r[1] for r in _db.execute("PRAGMA table_info(books)")}:
                _db.execute("ALTER TABLE books ADD COLUMN share_expires INTEGER")  # ms; NULL: the link does not expire
            if "campfire_until" not in {r[1] for r in _db.execute("PRAGMA table_info(books)")}:
                _db.execute("ALTER TABLE books ADD COLUMN campfire_until INTEGER")  # ms; campfire mode active until then
        with _db:
            yield _db


def sha_of(text):
    return hashlib.sha256(text.encode()).hexdigest()


def add_version(c, sid, text, file, action, by=None):
    """by: "sub" of the user who made this version (None: outside the app)."""
    sha = sha_of(text)
    head = c.execute("SELECT sha, file FROM versions WHERE song=? ORDER BY id DESC LIMIT 1", (sid,)).fetchone()
    if head == (sha, file) and action in ("geändert", "importiert"):
        return  # nothing changed ("Merken" with the same values, or the same song imported again)
    c.execute("INSERT OR IGNORE INTO blobs VALUES (?, ?)", (sha, text))
    c.execute("INSERT INTO versions (song, sha, file, at, action, user) VALUES (?, ?, ?, ?, ?, ?)",
              (sid, sha, file, now_ms(), action, by))


def head_of(c, sid):
    return c.execute("SELECT b.content, v.file FROM versions v JOIN blobs b USING (sha) WHERE v.song=? "
                     "ORDER BY v.id DESC LIMIT 1", (sid,)).fetchone()


def track(c, p):
    """Song id of file p; records edits made outside the app (SMB, editor) as a version."""
    mt = mtime_of(p)
    row = c.execute("SELECT id, mtime FROM songs WHERE file=?", (p.name,)).fetchone()
    if row and row[1] == mt:
        return row[0]
    text = p.read_text(encoding="utf-8", errors="replace")
    if row:
        sid = row[0]
        if sha_of(text) != c.execute("SELECT sha FROM versions WHERE song=? ORDER BY id DESC LIMIT 1", (sid,)).fetchone()[0]:
            add_version(c, sid, text, p.name, "außerhalb geändert")
        c.execute("UPDATE songs SET mtime=? WHERE id=?", (mt, sid))
    else:
        sid = c.execute("INSERT INTO songs (file, mtime) VALUES (?, ?)", (p.name, mt)).lastrowid
        add_version(c, sid, text, p.name, "aufgenommen")
    return sid


def retire(c, sid, action, by=None):
    content, file = head_of(c, sid)
    c.execute("UPDATE songs SET file=NULL, mtime=NULL, deleted=? WHERE id=?", (now_ms(), sid))
    add_version(c, sid, content, file, action, by)


def song_files():
    return [p for p in SONG_DIR.glob("*.cho") if not p.name.startswith(".")]


def cached_meta(p):
    mt = mtime_of(p)
    cached = _meta_cache.get(p.name)
    if not cached or cached[0] != mt:
        cached = (mt, meta_of(p.read_text(encoding="utf-8", errors="replace")))
        _meta_cache[p.name] = cached
    return mt, cached[1]


def entry(sid, file, mt, m):
    return {"id": sid, "file": file, "mtime": mt, "title": m.get("title") or (file or "")[:-4],
            "artist": m.get("artist") or m.get("subtitle") or "", "key": m.get("key") or "", "capo": m.get("capo") or "",
            "instrument": m.get("x_instrument", "").lower() if m.get("x_instrument", "").lower() in ug.INSTRUMENTS else ""} \
        | {k: m[k] for k in ("sorttitle", "sortartist") if m.get(k)}


# ---------------------------------------------------------------- permissions

# Three levels: view (public, or own/collaborating/admin), edit (owner, collaborators, admins: change the text or the
# songbook's songs, restore versions) and manage (owner and admins only: delete, visibility, share link, collaborators).

def can_view(u, owner, public, co=False):
    if u is None and not GUEST_ACCESS:
        return False  # guests only get in through a share link (see via_share)
    return bool(public) or co or (u is not None and (u["admin"] or (owner is not None and owner == u["sub"])))


def can_manage(u, owner):
    return u is not None and (u["admin"] or (owner is not None and owner == u["sub"]))


def can_edit(u, owner, co=False):
    """co: u collaborates on it (see collab_ids)."""
    return can_manage(u, owner) or (co and u is not None)


def collab_ids(c, u):
    """(song ids, book ids) u collaborates on: named, or "*" (all signed-in users). Working on a songbook includes
    the songs in it that belong to the book's owner – never more than the owner could change."""
    if u is None or u["sub"] is None:
        return frozenset(), frozenset()
    who = (u["sub"], "*")
    songs = {r[0] for r in c.execute("SELECT rid FROM collab WHERE kind='song' AND who IN (?, ?)", who)}
    books = {r[0] for r in c.execute("SELECT rid FROM collab WHERE kind='book' AND who IN (?, ?)", who)}
    if books:
        songs |= {r[0] for r in c.execute(
            "SELECT bs.song FROM book_songs bs JOIN books b ON b.id = bs.book JOIN songs s ON s.id = bs.song "
            f"WHERE bs.book IN ({','.join('?' * len(books))}) AND s.owner IS b.owner", tuple(books))}
    return frozenset(songs), frozenset(books)


def co_of(c, u, table, rid):
    return rid in collab_ids(c, u)[0 if table == "songs" else 1]


def need_user(u):
    if u is None:
        raise HttpError(401, "Bitte zuerst anmelden.")


def owner_of(c, table, rid):
    row = c.execute(f"SELECT owner, public FROM {table} WHERE id=?", (rid,)).fetchone()
    if not row:
        raise HttpError(404, "Lied nicht gefunden." if table == "songs" else "Liederbuch nicht gefunden.")
    return row


def check_view(u, c, table, rid):
    owner, public = owner_of(c, table, rid)
    if not can_view(u, owner, public, co_of(c, u, table, rid)):  # private things of others look like they do not exist
        raise HttpError(404, "Lied nicht gefunden." if table == "songs" else "Liederbuch nicht gefunden.")
    return owner, public


def check_edit(u, c, table, rid):
    owner, public = check_view(u, c, table, rid)
    if not can_edit(u, owner, co_of(c, u, table, rid)):
        raise HttpError(403, "Das darf nur, wer es angelegt hat, wer mitarbeitet (oder ein Admin)." if u else "Bitte zuerst anmelden.")
    return owner, public


def check_manage(u, c, table, rid):
    owner, public = check_view(u, c, table, rid)
    if not can_manage(u, owner):
        raise HttpError(403, "Das darf nur, wer es angelegt hat (oder ein Admin)." if u else "Bitte zuerst anmelden.")
    return owner, public


def owner_nick(c, owner):
    """Username (nick, e.g. "andi") of a user – never the full name."""
    row = c.execute("SELECT username FROM users WHERE sub=?", (owner,)).fetchone()
    return row[0] if row and row[0] else ""


def access(u, owner, public, c, co=False):
    """Fields every song/book entry carries for the interface. The owner is shown by username to signed-in users
    (guests should not learn who is registered)."""
    show = owner and u is not None and u["sub"] is not None
    name = (owner_nick(c, owner),) if show else None
    return {"public": bool(public), "owner": name[0] if name else "", "mine": u is not None and owner is not None and owner == u["sub"],
            "editable": can_edit(u, owner, co), "manage": can_manage(u, owner), "collab": bool(co) and not can_manage(u, owner)}


def all_songs():
    """Every current song (tracks files added/changed/removed outside the app) with owner/public."""
    out = []
    with tx() as c:
        files = song_files()
        for p in files:
            sid = track(c, p)
            mt, m = cached_meta(p)
            out.append(entry(sid, p.name, mt, m))
        names = {p.name for p in files}
        for sid, file in c.execute("SELECT id, file FROM songs WHERE file IS NOT NULL").fetchall():
            if file not in names:
                retire(c, sid, "außerhalb gelöscht")
        acl = {r[0]: r[1:] for r in c.execute("SELECT id, owner, public FROM songs")}
    for s in out:
        s["_owner"], s["_public"] = acl[s["id"]]
    return out


def fav_key(u):
    """Favorites belong to the user; without a login system there is one server-wide list (user "")."""
    return "" if u["sub"] is None else u["sub"]


def favorites_of(c, u):
    """Song ids the user has hearted; guests keep theirs in the browser."""
    if u is None:
        return set()
    return {r[0] for r in c.execute("SELECT song FROM favorites WHERE user=?", (fav_key(u),))}


def set_favorite(req, u=LOCAL_ADMIN):
    """{"song": id, "fav": true/false}; several at once (merging a guest's browser favorites): {"songs": [ids], "fav": true}."""
    need_user(u)
    ids = [int(i) for i in req["songs"]] if "songs" in req else [int(req["song"])]
    fav = bool(req.get("fav", True))
    with tx() as c:
        for sid in ids:
            try:
                check_view(u, c, "songs", sid)
            except HttpError:
                if "songs" in req:  # merging: skip songs that are gone or private
                    continue
                raise
            if fav:
                c.execute("INSERT OR IGNORE INTO favorites VALUES (?, ?, ?)", (fav_key(u), sid, now_ms()))
            else:
                c.execute("DELETE FROM favorites WHERE user=? AND song=?", (fav_key(u), sid))
    return {"ok": True}


def list_songs(u=LOCAL_ADMIN, extra=None):
    """Songs the user may see; extra(owner, public) lets a share link show more (see via_share)."""
    out = []
    songs = all_songs()
    with tx() as c:
        favs = favorites_of(c, u)
        co_songs = collab_ids(c, u)[0]
        for s in songs:
            co = s["id"] in co_songs
            if can_view(u, s["_owner"], s["_public"], co) or (extra and extra(s["_owner"], s["_public"])):
                out.append({k: v for k, v in s.items() if not k.startswith("_")} | access(u, s["_owner"], s["_public"], c, co)
                           | {"fav": s["id"] in favs})
    out.sort(key=lambda s: (s.get("sorttitle", s["title"]).casefold(), s["artist"].casefold()))
    return out


def write_atomic(p, text):
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=".tmp-", suffix=".cho")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.chmod(tmp, 0o664)
        os.replace(tmp, p)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def to_trash(p):
    trash = SONG_DIR / TRASH
    trash.mkdir(exist_ok=True)
    os.replace(p, trash / f"{p.stem} {time.strftime('%Y-%m-%d %H%M%S')}.cho")


def store(c, sid, cur, target, text, action, by=None):
    """Write text as song sid (None = new; cur = its current file name or None) to target and record a version."""
    if target.exists() and target.name != cur:
        other = track(c, target)
        to_trash(target)
        retire(c, other, "überschrieben", by)
    write_atomic(target, text)
    if sid is None:
        sid = c.execute("INSERT INTO songs (file) VALUES (?)", (target.name,)).lastrowid
        action = "neu"
    c.execute("UPDATE songs SET file=?, mtime=?, deleted=NULL WHERE id=?", (target.name, mtime_of(target), sid))
    add_version(c, sid, text, target.name, action, by)
    if cur and cur != target.name and (SONG_DIR / cur).exists():
        to_trash(SONG_DIR / cur)
    return {"ok": True, "id": sid, "file": target.name, "mtime": mtime_of(target)}


def clean(text):
    text = (text or "").replace("\r\n", "\n")
    if len(text.encode()) > MAX_SONG:
        raise HttpError(413, "Lied zu groß.")
    return text if text.endswith("\n") else text + "\n"


def target_of(text, fallback=None):
    m = meta_of(text)
    if m.get("title"):
        return song_path(ug.filename(m["title"], m.get("artist", "")))
    if fallback:
        return song_path(fallback)
    raise HttpError(400, "Bitte einen Titel angeben: {{title: …}}")


def free_name(target):
    """Next unused "Artist - Title (n).cho"."""
    n = 2
    while (p := target.with_name(f"{target.stem} ({n}).cho")).exists():
        n += 1
    return p


def own_copy_name(target, u):
    """The same song by another user: "Artist - Title (nick).cho" (then "(nick 2)", …) – several users may each
    have their own version of a song; the title stays the same, the owner tells them apart."""
    nick = re.sub(r"[^\w .-]+", "", (u or {}).get("username") or "") or "Kopie"
    p = target.with_name(f"{target.stem} ({nick}).cho")
    n = 2
    while p.exists():
        p = target.with_name(f"{target.stem} ({nick} {n}).cho")
        n += 1
    return p


def save_song(req, u=LOCAL_ADMIN):
    """Name comes from {title}/{artist}. old = file being edited (rename if the name changed).
    public: optional true/false (new songs default to public)."""
    need_user(u)
    text = clean(req.get("content"))
    target = target_of(text)
    old = song_path(req["old"]) if req.get("old") else None
    overwrite = bool(req.get("overwrite"))
    if old and old.exists() and old != target and old.name.startswith(target.stem + " (") and old.name.endswith(").cho"):
        target = old  # a "… (nick)" / "… (2)" version keeps its name as long as title and artist stay the same
    with tx() as c:
        sid = track(c, old) if old and old.exists() else None
        owner = check_edit(u, c, "songs", sid)[0] if sid else u["sub"]
        action = None
        if old and old == target:
            if not old.exists():
                raise HttpError(409, "Das Lied wurde inzwischen gelöscht.", conflict="deleted")
            if req.get("base_mtime") and mtime_of(old) != int(req["base_mtime"]) and not overwrite:
                raise HttpError(409, "Das Lied wurde inzwischen woanders geändert.", conflict="changed")
        elif target.exists():
            tsid = track(c, target)
            towner, tpublic = owner_of(c, "songs", tsid)
            tco = co_of(c, u, "songs", tsid)
            if not can_edit(u, towner, tco):
                # someone else's song with this name: this one becomes the user's own version "… (nick)"
                target = own_copy_name(target, u)
            elif req.get("copy"):  # "keep both" with one's own (or a shared) song
                target = free_name(target)
            elif not overwrite:
                raise HttpError(409, "„{name}“ gibt es schon.", {"name": target.name}, conflict="exists",
                                file=target.name, editable=True)
            elif old is None:  # imported over an existing song: becomes its next version, the history stays together
                sid, old, owner, action = tsid, target, towner, "importiert"
        action = action or ("umbenannt" if old and old != target else "geändert")
        res = store(c, sid, old.name if sid else None, target, text, action, u["sub"])
        if not sid:
            c.execute("UPDATE songs SET owner=?, public=? WHERE id=?",
                      (u["sub"], 1 if single() else int(req.get("public", True) is not False), res["id"]))
        elif "public" in req and can_manage(u, owner) and not single():
            c.execute("UPDATE songs SET public=? WHERE id=?", (int(bool(req["public"])), sid))
        return res


def delete_song(p, u=LOCAL_ADMIN):
    with tx() as c:
        sid = track(c, p)
        check_manage(u, c, "songs", sid)
        to_trash(p)
        retire(c, sid, "gelöscht", u["sub"])
    return {"ok": True}


DEVICES = ("phone", "tablet", "pc")


def tempos_for(c, sid, u, owner):
    """Saved scroll tempos: the user's own, else the song owner's, else from before the user system."""
    t = dict(c.execute("SELECT device, speed FROM tempos WHERE song=?", (sid,)).fetchall())
    for who in (owner, u and u["sub"]):
        if who:
            t.update(c.execute("SELECT device, speed FROM user_tempos WHERE song=? AND user=?", (sid, who)).fetchall())
    return t


def get_song(p, u=LOCAL_ADMIN, token=None):
    """token: opened from a share link – the song must be in that songbook (see via_share)."""
    with tx() as c:
        sid = track(c, p)
        via = False
        if token:
            bid, bowner = shared(c, token)
            owner, public = owner_of(c, "songs", sid)
            if not can_view(u, owner, public, co_of(c, u, "songs", sid)):
                in_book = c.execute("SELECT 1 FROM book_songs WHERE book=? AND song=?", (bid, sid)).fetchone()
                if not (in_book and via_share(bowner)(owner, public)):
                    raise HttpError(404, "Lied nicht gefunden.")
                via = True  # only visible through the link: no favorites/tempos/books for it
        else:
            owner, public = owner_of(c, "songs", sid)
            if not can_view(u, owner, public, co_of(c, u, "songs", sid)):
                if campfire_song(c, sid) is None:
                    raise HttpError(404, "Lied nicht gefunden.")
                via = True  # through a songbook in campfire mode
        co_songs, co_books = collab_ids(c, u)
        books = [b for b, o in c.execute("SELECT b.id, b.owner FROM book_songs bs JOIN books b ON b.id = bs.book "
                                         "WHERE bs.song=?", (sid,)) if can_edit(u, o, b in co_books)]  # the 📚 dialog
        tempos = tempos_for(c, sid, u, owner)
        acc = access(u, owner, public, c, sid in co_songs) | {"fav": sid in favorites_of(c, u), "via_share": via}
    return {"ok": True, "id": sid, "file": p.name, "mtime": mtime_of(p), "books": books, "tempos": tempos,
            "content": p.read_text(encoding="utf-8", errors="replace"), **acc}


def set_tempo(req, u=LOCAL_ADMIN):
    """Auto-scroll tempo per song, device class (phone/tablet/pc) and user – screen size changes what feels right."""
    need_user(u)
    sid, device, speed = int(req.get("song") or 0), req.get("device"), int(req.get("speed") or 0)
    if device not in DEVICES or not 1 <= speed <= 40:
        raise HttpError(400, "Ungültiges Tempo.")
    with tx() as c:
        check_view(u, c, "songs", sid)
        if u["sub"] is None:  # no user system: one tempo for everybody
            c.execute("INSERT INTO tempos VALUES (?, ?, ?, ?) ON CONFLICT (song, device) DO UPDATE SET speed=excluded.speed, "
                      "updated=excluded.updated", (sid, device, speed, now_ms()))
        else:
            c.execute("INSERT INTO user_tempos VALUES (?, ?, ?, ?, ?) ON CONFLICT (song, device, user) DO UPDATE SET "
                      "speed=excluded.speed, updated=excluded.updated", (sid, device, u["sub"], speed, now_ms()))
    return {"ok": True}


# ---------------------------------------------------------------- bulk edit

TRANSPOSE_LINE = re.compile(r"^\{\s*transpose(?:\s*:\s*|\s+)([+-]?\d+)\s*([sfk]?)\s*\}\s*$", re.I)
HEADER_KEYS = ("title", "t", "sorttitle", "subtitle", "st", "artist", "sortartist", "composer", "lyricist", "copyright",
               "album", "year", "key", "time", "tempo", "duration", "capo", "meta", "tag")


def _header_end(lines):
    """Index after the leading block of song-info directives ({title}, {artist}, {key}, …, {x_…})."""
    i = 0
    while i < len(lines):
        m = re.match(r"^\s*\{\s*([a-z_]+)", lines[i], re.I)
        if not (m and (m[1].lower() in HEADER_KEYS or m[1].lower().startswith("x_"))):
            break
        i += 1
    return i


def set_directive(text, name, value):
    """{name: value} replaced (first occurrence) or added after the header lines; value None removes it."""
    lines = text.split("\n")
    rx = re.compile(r"^\s*\{\s*" + re.escape(name) + r"(?:\s*:.*|\s+.*)?\}\s*$", re.I)
    at = next((i for i, l in enumerate(lines) if rx.match(l)), None)
    if value is None:
        if at is not None:
            del lines[at]
    elif at is not None:
        lines[at] = "{%s: %s}" % (name, value)
    else:
        lines.insert(_header_end(lines), "{%s: %s}" % (name, value))
    return "\n".join(lines)


def shift_transpose(text, delta):
    """The song's own transposition ({transpose} before the first chord, or the old x_transpose) moved by delta
    semitones – like "Tonart merken" in the app; the chords in the text are not changed."""
    lines = text.split("\n")
    cur, at, suffix = 0, None, ""
    for i, l in enumerate(lines):
        m = TRANSPOSE_LINE.match(l)
        if m:
            cur, at, suffix = int(m[1]), i, m[2]
            break
        if re.search(r"\[[^\]*][^\]]*\]", l) or re.match(r"^\s*\{\s*(start_of_grid|sog)\b", l, re.I):
            break
    xl = next((i for i, l in enumerate(lines) if re.match(r"^\{\s*x_transpose\s*:", l, re.I)), None)
    if at is None and xl is not None:
        try:
            cur = int(lines[xl].split(":", 1)[1].strip(" }"))
        except ValueError:
            cur = 0
    if xl is not None:
        del lines[xl]
        if at is not None and xl < at:
            at -= 1
    new = cur + delta
    if at is not None:
        if new:
            lines[at] = "{transpose: %d%s}" % (new, suffix)
        else:
            del lines[at]
    elif new:
        lines.insert(_header_end(lines), "{transpose: %d}" % new)
    return "\n".join(lines)


BULK_MAX = 2000


def bulk_edit(req, u=LOCAL_ADMIN):
    """Several songs at once. req: {"ids": [...], "changes": {...}} with any of
    public (bool), key (str; "" removes), instrument ("guitar"/"ukulele"/"" removes), transpose_by (int),
    collab {"add": [subs], "remove": [subs], "all": true/false}, book_add (id), book_remove (id), delete (true).
    Rights per song as for single edits: text changes need edit rights (collaborators too), visibility,
    collaborators and delete need owner/admin. Songs that can't be changed are skipped and listed."""
    need_user(u)
    ids = req.get("ids") or []
    ch = req.get("changes") or {}
    if not isinstance(ids, list) or not ids or len(ids) > BULK_MAX or not isinstance(ch, dict) or not ch:
        raise HttpError(400, "Ungültige Anfrage.")
    ids = list(dict.fromkeys(int(i) for i in ids))
    key = ch.get("key")
    if key is not None and (not isinstance(key, str) or len(key) > 20 or (key.strip() and not ug.CHORD_RE.match(key.strip()))):
        raise HttpError(400, "Ungültige Tonart.")
    inst = ch.get("instrument")
    if inst is not None and inst not in ("",) + tuple(ug.INSTRUMENTS):
        raise HttpError(400, "Ungültige Anfrage.")
    tb = ch.get("transpose_by")
    if tb is not None and (isinstance(tb, bool) or not isinstance(tb, int) or not -11 <= tb <= 11):
        raise HttpError(400, "Ungültige Anfrage.")
    collab = ch.get("collab")
    if collab is not None and not isinstance(collab, dict):
        raise HttpError(400, "Ungültige Anfrage.")
    if single() and ("public" in ch or collab is not None):
        raise HttpError(400, "Ungültige Anfrage.")
    new_owner = ch.get("owner")
    if "owner" in ch:
        if not u["admin"]:
            raise HttpError(403, "Nur für Admins.")
        if not isinstance(new_owner, str) or not new_owner:
            raise HttpError(400, "Ungültige Anfrage.")
    text_change = key is not None or inst is not None or bool(tb)
    manage_change = "public" in ch or collab is not None or ch.get("delete") or "owner" in ch
    changed, skipped = 0, []
    with tx() as c:
        co_songs = collab_ids(c, u)[0]
        for bid_key in ("book_add", "book_remove"):
            if ch.get(bid_key) is not None:
                check_edit(u, c, "books", int(ch[bid_key]))
        known = {r[0] for r in c.execute("SELECT sub FROM users")}
        if "owner" in ch and new_owner not in known:
            raise HttpError(404, "Benutzer nicht gefunden.")
        owner_nick_new = owner_nick(c, new_owner) if "owner" in ch else ""
        for sid in ids:
            row = c.execute("SELECT file, owner, public FROM songs WHERE id=?", (sid,)).fetchone()
            if not row or not row[0] or not (SONG_DIR / row[0]).exists():
                skipped.append({"id": sid, "title": "", "reason": "nicht gefunden"})
                continue
            file, owner, public = row
            co = sid in co_songs
            title = meta_of((SONG_DIR / file).read_text(encoding="utf-8", errors="replace")).get("title") or file[:-4]
            if not can_view(u, owner, public, co):
                skipped.append({"id": sid, "title": "", "reason": "nicht gefunden"})
                continue
            if (text_change or ch.get("book_add") is not None or ch.get("book_remove") is not None) and not can_edit(u, owner, co) \
                    or manage_change and not can_manage(u, owner):
                skipped.append({"id": sid, "title": title, "reason": "keine Berechtigung"})
                continue
            p = SONG_DIR / file
            track(c, p)
            if ch.get("delete"):
                to_trash(p)
                retire(c, sid, "gelöscht", u["sub"])
                c.execute("DELETE FROM collab WHERE kind='song' AND rid=?", (sid,))
                changed += 1
                continue
            if text_change:
                text = p.read_text(encoding="utf-8", errors="replace")
                new = text
                if key is not None:
                    new = set_directive(new, "key", key.strip() or None)
                if inst is not None:
                    new = set_directive(new, "x_instrument", inst or None)
                if tb:
                    new = shift_transpose(new, tb)
                if new != text:
                    store(c, sid, file, p, clean(new), "Sammelbearbeitung", u["sub"])
            if "public" in ch and bool(public) != bool(ch["public"]):
                c.execute("UPDATE songs SET public=? WHERE id=?", (int(bool(ch["public"])), sid))
                note(c, u, "öffentlich gemacht" if ch["public"] else "privat gemacht", "song", sid, title)
            if "owner" in ch and owner != new_owner:
                c.execute("UPDATE songs SET owner=? WHERE id=?", (new_owner, sid))
                c.execute("DELETE FROM collab WHERE kind='song' AND rid=? AND who=?", (sid, new_owner))
                note(c, u, "Besitzer geändert", "song", sid, f"{title} → {owner_nick_new}")
            if collab is not None:
                for who in collab.get("add") or []:
                    if isinstance(who, str) and who in known and who != owner:
                        c.execute("INSERT OR IGNORE INTO collab VALUES ('song', ?, ?)", (sid, who))
                for who in collab.get("remove") or []:
                    if isinstance(who, str):
                        c.execute("DELETE FROM collab WHERE kind='song' AND rid=? AND who=?", (sid, who))
                if collab.get("all") is True:
                    c.execute("INSERT OR IGNORE INTO collab VALUES ('song', ?, '*')", (sid,))
                elif collab.get("all") is False:
                    c.execute("DELETE FROM collab WHERE kind='song' AND rid=? AND who='*'", (sid,))
                note(c, u, "Mitarbeit geändert", "song", sid, title)
            if ch.get("book_add") is not None:
                bid = int(ch["book_add"])
                if c.execute("INSERT OR IGNORE INTO book_songs SELECT ?, ?, coalesce(max(pos), -1) + 1 FROM book_songs WHERE book=?",
                             (bid, sid, bid)).rowcount:
                    note(c, u, "Lied hinzugefügt", "book", bid, title)
            if ch.get("book_remove") is not None:
                if c.execute("DELETE FROM book_songs WHERE book=? AND song=?", (int(ch["book_remove"]), sid)).rowcount:
                    note(c, u, "Lied entfernt", "book", int(ch["book_remove"]), title)
            changed += 1
        for bid_key in ("book_add", "book_remove"):
            if ch.get(bid_key) is not None:
                c.execute("UPDATE books SET updated=max(?, updated + 1) WHERE id=?", (now_ms(), int(ch[bid_key])))
    return {"ok": True, "changed": changed, "skipped": skipped}


def copy_song(req, u=LOCAL_ADMIN):
    """{"file": name}: the signed-in user's own version of a song they may see – someone else's song becomes
    "Artist - Title (nick).cho", one's own "… (2)". Same text and visibility; the original stays as it is. Only with
    normal visibility (not through a share link or campfire mode)."""
    need_user(u)
    p = song_path(req.get("file") or "")
    if not p.exists():
        raise HttpError(404, "Lied nicht gefunden.")
    with tx() as c:
        sid = track(c, p)
        owner, public = check_view(u, c, "songs", sid)
        text = p.read_text(encoding="utf-8", errors="replace")
        mine = u["sub"] is not None and owner == u["sub"]
        target = free_name(p) if mine or u["sub"] is None else own_copy_name(p, u)
        res = store(c, None, None, target, clean(text), "neu", u["sub"])
        title = meta_of(text).get("title") or p.stem
        nick = owner_nick(c, owner) if owner else ""
        c.execute("UPDATE versions SET action=? WHERE id=(SELECT max(id) FROM versions WHERE song=?)",
                  ("Kopie von „%s“%s" % (title, " (%s)" % nick if nick else ""), res["id"]))
        c.execute("UPDATE songs SET owner=?, public=? WHERE id=?", (u["sub"], int(bool(public)), res["id"]))
    return res


def set_visibility(req, u=LOCAL_ADMIN):
    """{"song": id} or {"book": id}, "public": true/false."""
    not_single()
    table, rid = ("songs", req["song"]) if "song" in req else ("books", req["book"])
    with tx() as c:
        check_manage(u, c, table, int(rid))
        c.execute(f"UPDATE {table} SET public=? WHERE id=?", (int(bool(req.get("public"))), int(rid)))
        what = song_title(c, int(rid)) if table == "songs" else c.execute("SELECT name FROM books WHERE id=?", (int(rid),)).fetchone()[0]
        note(c, u, "öffentlich gemacht" if req.get("public") else "privat gemacht", table[:-1] if table == "songs" else "book", int(rid), what)
    return {"ok": True}


def history(sid, u=LOCAL_ADMIN):
    with tx() as c:
        owner, _ = check_view(u, c, "songs", sid)
        editable = can_edit(u, owner, co_of(c, u, "songs", sid))
        row = c.execute("SELECT file, deleted FROM songs WHERE id=?", (sid,)).fetchone()
        if row[0] and (SONG_DIR / row[0]).exists():
            track(c, SONG_DIR / row[0])
        vs = c.execute("SELECT v.id, v.at, v.action, v.file, v.sha, b.content, us.username "
                       "FROM versions v JOIN blobs b USING (sha) LEFT JOIN users us ON us.sub = v.user "
                       "WHERE v.song=? ORDER BY v.id DESC", (sid,)).fetchall()
    # who saved a version: only for those who work on the song (guests should not learn who is registered)
    return {"ok": True, "id": sid, "file": row[0], "deleted": row[1], "editable": editable,
            "versions": [{"id": v[0], "at": v[1], "action": v[2], "file": v[3], "sha": v[4][:8], "content": v[5],
                          "by": (v[6] or "") if editable else ""} for v in vs]}


def restore(req, u=LOCAL_ADMIN):
    """Make an old version the current state of its song again (also brings deleted songs back)."""
    need_user(u)
    with tx() as c:
        row = c.execute("SELECT v.song, v.file, b.content, s.file, v.at FROM versions v JOIN blobs b USING (sha) "
                        "JOIN songs s ON s.id = v.song WHERE v.id=?", (int(req.get("version") or 0),)).fetchone()
        if not row:
            raise HttpError(404, "Version nicht gefunden.")
        sid, vfile, text, cur, at = row
        check_edit(u, c, "songs", sid)
        if cur and not (SONG_DIR / cur).exists():
            retire(c, sid, "außerhalb gelöscht")
            cur = None
        target = target_of(text, vfile)
        if cur and cur != target.name and cur.startswith(target.stem + " (") and cur.endswith(").cho"):
            target = SONG_DIR / cur  # a "… (nick)" / "… (2)" version keeps its name
        if target.exists() and target.name != cur:
            tsid = track(c, target)
            if not can_edit(u, owner_of(c, "songs", tsid)[0], co_of(c, u, "songs", tsid)):
                target = own_copy_name(target, u)
        if target.exists() and target.name != cur and not req.get("overwrite"):
            raise HttpError(409, "„{name}“ gibt es schon.", {"name": target.name}, conflict="exists", file=target.name)
        if cur:
            track(c, SONG_DIR / cur)
        when = time.strftime("%d.%m.%Y %H:%M", time.localtime(at / 1000))
        return store(c, sid, cur, target, text, f"wiederhergestellt (Stand {when})", u["sub"])


def deleted_songs(u=LOCAL_ADMIN):
    with tx() as c:
        rows = c.execute("SELECT s.id, s.deleted, v.id, v.file, b.content, s.owner FROM songs s "
                         "JOIN versions v ON v.id = (SELECT max(id) FROM versions WHERE song = s.id) "
                         "JOIN blobs b ON b.sha = v.sha WHERE s.file IS NULL ORDER BY s.deleted DESC").fetchall()
    return [{**entry(sid, file, None, meta_of(content)), "file": None, "deleted": at, "version": vid}
            for sid, at, vid, file, content, owner in rows if can_manage(u, owner)]


# ---------------------------------------------------------------- songbooks (Liederbücher)

def books(u=LOCAL_ADMIN):
    out = []
    with tx() as c:
        songs = {r[0]: r[1:] for r in c.execute("SELECT id, owner, public FROM songs WHERE file IS NOT NULL")}
        co_songs, co_books = collab_ids(c, u)
        has_collab = {r[0] for r in c.execute("SELECT DISTINCT rid FROM collab WHERE kind='book'")}
        fires = campfire_books(c)
        for bid, name, updated, owner, public, share, expires, fire_until in c.execute(
                "SELECT id, name, updated, owner, public, share, share_expires, campfire_until FROM books").fetchall():
            normal = can_view(u, owner, public, bid in co_books)
            if not normal and bid not in fires:
                continue
            ids = [r[0] for r in c.execute("SELECT song FROM book_songs WHERE book=?", (bid,))]
            seen = (lambda o, p, i: can_view(u, o, p, i in co_songs)) if normal else (lambda o, p, i: via_share(owner)(o, p))
            count = sum(1 for i in ids if i in songs and seen(*songs[i], i))
            acc = access(u, owner, public, c, bid in co_books)
            out.append({"id": bid, "name": name, "updated": updated, "count": count,
                        "shared": share_active(share, expires) and acc["manage"],
                        "together": bid in has_collab and acc["editable"],
                        "campfire_until": fire_until if bid in fires else None} | acc)
    out.sort(key=lambda b: b["name"].casefold())
    return out


def book_name(name):
    name = " ".join((name or "").split())
    if not name or len(name) > 200:
        raise HttpError(400, "Bitte einen Namen angeben.")
    return name


def create_book(req, u=LOCAL_ADMIN):
    need_user(u)
    with tx() as c:
        name = book_name(req.get("name"))
        bid = c.execute("INSERT INTO books (name, updated, owner, public) VALUES (?, ?, ?, ?)",
                        (name, now_ms(), u["sub"], 1 if single() else int(req.get("public", True) is not False))).lastrowid
        note(c, u, "Liederbuch angelegt", "book", bid, name)
    return {"ok": True, "id": bid}


def get_book(bid, content=False, u=LOCAL_ADMIN, token=None):
    """Songs the viewer may not see (private songs of others) are left out; deleted ones only show to editors.
    token: opened from a share link (bid is ignored) – read-only, shows what via_share allows."""
    extra, fire = None, False
    if token:
        with tx() as c:
            bid, bowner = shared(c, token)
        extra = via_share(bowner)
    else:
        with tx() as c:  # campfire mode: everybody may open the book, like with a share link
            bowner, bpublic = owner_of(c, "books", bid)
            if not can_view(u, bowner, bpublic, co_of(c, u, "books", bid)) and bid in campfire_books(c):
                extra, fire = via_share(bowner), True
    by_id = {s["id"]: s for s in list_songs(u, extra)}
    with tx() as c:
        owner, public = owner_of(c, "books", bid) if token or fire else check_view(u, c, "books", bid)
        b = c.execute("SELECT name, updated, share, share_expires, campfire_until FROM books WHERE id=?", (bid,)).fetchone()
        co = co_of(c, u, "books", bid)
        editable = can_edit(u, owner, co) and not token
        manage = can_manage(u, owner) and not token
        ids = [r[0] for r in c.execute("SELECT song FROM book_songs WHERE book=? ORDER BY pos", (bid,))]
        live = {r[0] for r in c.execute("SELECT id FROM songs WHERE file IS NOT NULL")}
        songs = []
        for sid in ids:
            if sid in by_id:
                s = dict(by_id[sid])
                if content:
                    s["content"] = (SONG_DIR / s["file"]).read_text(encoding="utf-8", errors="replace")
            elif sid not in live and editable:  # deleted: listed (can be restored) but not played or printed
                text, file = head_of(c, sid)
                s = {**entry(sid, None, None, meta_of(text)), "deleted": True}
            else:
                continue
            songs.append(s)
        acc = access(u, owner, public, c, co) | {"editable": editable, "manage": manage}
        days_default = share_days_default(c)
        fire_days = campfire_days_default(c)
    active = b[4] if b[4] and b[4] > now_ms() else None
    return {"ok": True, "id": bid, "name": b[0], "updated": b[1], "songs": songs, **acc,
            "share": b[2] if manage else None, "share_expires": b[3] if manage else None,
            "share_days": days_default, "via_share": bool(token), "via_campfire": fire,
            "campfire_until": active, "campfire_days": fire_days}


def update_book(bid, req, u=LOCAL_ADMIN):
    """Rename and/or replace the song order; base_updated guards against two people editing at once.
    Songs the editor cannot see (private songs of others, added by an admin) keep their place at the end."""
    with tx() as c:
        check_edit(u, c, "books", bid)
        b = c.execute("SELECT name, updated FROM books WHERE id=?", (bid,)).fetchone()
        if req.get("base_updated") and int(req["base_updated"]) != b[1] and not req.get("overwrite"):
            raise HttpError(409, "Das Liederbuch wurde inzwischen woanders geändert.", conflict="changed")
        name = book_name(req["name"]) if "name" in req else b[0]
        if "songs" in req:
            ids = list(dict.fromkeys(int(i) for i in req["songs"]))
            acl = {r[0]: r[1:] for r in c.execute("SELECT id, owner, public FROM songs")}
            co_songs = collab_ids(c, u)[0]
            known = {i for i in ids if i in acl and can_view(u, *acl[i], i in co_songs)}
            hidden = [r[0] for r in c.execute("SELECT song FROM book_songs WHERE book=? ORDER BY pos", (bid,))
                      if not can_view(u, *acl.get(r[0], (None, 1)), r[0] in co_songs)]
            ids = [i for i in ids if i in known] + hidden
            known |= set(hidden)
            c.execute("DELETE FROM book_songs WHERE book=?", (bid,))
            c.executemany("INSERT INTO book_songs VALUES (?, ?, ?)", [(bid, i, n) for n, i in enumerate(ids) if i in known])
        updated = max(now_ms(), b[1] + 1)
        c.execute("UPDATE books SET name=?, updated=? WHERE id=?", (name, updated, bid))
        if name != b[0]:
            note(c, u, "Liederbuch umbenannt", "book", bid, f"{b[0]} → {name}")
        if "songs" in req:
            note(c, u, "Liederbuch geändert", "book", bid, name)
    return {"ok": True, "id": bid, "updated": updated}


def toggle_book_song(bid, req, u=LOCAL_ADMIN):
    """Add a song to the end of a book or take it out (from the song view)."""
    sid = int(req.get("song") or 0)
    with tx() as c:
        check_edit(u, c, "books", bid)
        check_view(u, c, "songs", sid)
        if req.get("add"):
            n = c.execute("INSERT OR IGNORE INTO book_songs SELECT ?, ?, coalesce(max(pos), -1) + 1 FROM book_songs WHERE book=?",
                          (bid, sid, bid)).rowcount
        else:
            n = c.execute("DELETE FROM book_songs WHERE book=? AND song=?", (bid, sid)).rowcount
        if n:
            note(c, u, "Lied hinzugefügt" if req.get("add") else "Lied entfernt", "book", bid, song_title(c, sid))
        c.execute("UPDATE books SET updated=max(?, updated + 1) WHERE id=?", (now_ms(), bid))
    return {"ok": True}


def delete_book(bid, u=LOCAL_ADMIN):
    with tx() as c:
        check_manage(u, c, "books", bid)
        note(c, u, "Liederbuch gelöscht", "book", bid, c.execute("SELECT name FROM books WHERE id=?", (bid,)).fetchone()[0])
        c.execute("DELETE FROM books WHERE id=?", (bid,))
        c.execute("DELETE FROM collab WHERE kind='book' AND rid=?", (bid,))
    return {"ok": True}


def export_book(bid, fmt, u=LOCAL_ADMIN, token=None):
    b = get_book(bid, content=True, u=u, token=token)
    songs = [s for s in b["songs"] if not s.get("deleted")]
    if fmt == "cho":  # one file with all songs, as the chordpro tool expects for a songbook
        body = "\n{new_song}\n".join(s["content"].rstrip("\n") + "\n" for s in songs)
        return f"# Liederbuch: {b['name']}\n" + body, "text/plain; charset=utf-8", b["name"] + ".cho"
    buf, width = io.BytesIO(), len(str(len(songs)))
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for n, s in enumerate(songs, 1):
            z.writestr(f"{n:0{width}d} {s['file']}", s["content"])
    return buf.getvalue(), "application/zip", b["name"] + ".zip"


# ---------------------------------------------------------------- campfire mode
# A songbook can be opened by everybody for a few days (scout camp) – plain at the app address, no login, no link,
# also with GUEST_ACCESS=off. It shows what a share link shows (public songs + the book owner's own songs).
CAMPFIRE_DAYS_DEFAULT = 7
CAMPFIRE_DAYS_MAX = 21


def campfire_books(c):
    """Songbooks in campfire mode right now: {book id: owner}."""
    if single():
        return {}
    return {r[0]: r[1] for r in c.execute("SELECT id, owner FROM books WHERE campfire_until > ?", (now_ms(),))}


def campfire_song(c, sid):
    """Id of an active campfire songbook through which song sid may be seen, else None."""
    for bid, bowner, sowner, spublic in c.execute(
            "SELECT b.id, b.owner, s.owner, s.public FROM book_songs bs JOIN books b ON b.id = bs.book "
            "JOIN songs s ON s.id = bs.song WHERE bs.song=? AND b.campfire_until > ?", (sid, now_ms())):
        if via_share(bowner)(sowner, spublic):
            return bid
    return None


def campfire_days_default(c):
    try:
        return max(1, min(CAMPFIRE_DAYS_MAX, int(setting(c, "campfire_days", CAMPFIRE_DAYS_DEFAULT))))
    except ValueError:
        return CAMPFIRE_DAYS_DEFAULT


def campfire_days(v):
    if isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= CAMPFIRE_DAYS_MAX:
        raise HttpError(400, "Ungültige Gültigkeitsdauer.")
    return v


def set_campfire(bid, req, u=LOCAL_ADMIN):
    """{"days": n} switches campfire mode on for n days from now (1–21; default: admin setting), {"days": 0} off."""
    not_single()
    with tx() as c:
        check_manage(u, c, "books", bid)
        days = campfire_days(req["days"]) if "days" in req else campfire_days_default(c)
        until = now_ms() + days * DAY_MS if days else None
        c.execute("UPDATE books SET campfire_until=? WHERE id=?", (until, bid))
        note(c, u, "Lagerfeuer-Modus gestartet" if until else "Lagerfeuer-Modus beendet", "book", bid,
             c.execute("SELECT name FROM books WHERE id=?", (bid,)).fetchone()[0])
    return {"ok": True, "campfire_until": until}


def campfire_list():
    """Active campfire songbooks for the start page (everybody may see these)."""
    if single():
        return []
    with tx() as c:
        return [{"id": r[0], "name": r[1], "until": r[2]} for r in
                c.execute("SELECT id, name, campfire_until FROM books WHERE campfire_until > ? ORDER BY name", (now_ms(),))]


# ---------------------------------------------------------------- share links
# A songbook can be shared with a secret link (#/teilen/<token>), also when it is private: whoever has the link may
# read, play, print and download it without an account. The token is random (144 bit); a new one replaces the old
# link, switching sharing off makes the link invalid. Links expire after a number of days (chosen when sharing;
# the default is an admin setting, 0 = never); an expired link can be extended and then works again.
SHARE_RE = re.compile(r"[A-Za-z0-9_-]{16,64}")
SHARE_DAYS_DEFAULT = 30
SHARE_DAYS_MAX = 3650
DAY_MS = 86_400_000


def setting(c, key, default):
    row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row[0] if row else default


def share_days_default(c):
    """Lifetime of new share links in days (admin setting), 0 = they do not expire."""
    try:
        return max(0, min(SHARE_DAYS_MAX, int(setting(c, "share_days", SHARE_DAYS_DEFAULT))))
    except ValueError:
        return SHARE_DAYS_DEFAULT


def share_active(token, expires):
    return bool(token) and (expires is None or expires > now_ms())


def shared(c, token):
    """(book id, book owner) of a share link that is still valid."""
    not_single()
    row = c.execute("SELECT id, owner, share_expires FROM books WHERE share=?", (token,)).fetchone() \
        if SHARE_RE.fullmatch(token or "") else None
    if not row:
        raise HttpError(404, "Dieser Link gilt nicht (mehr) – die Freigabe wurde vielleicht beendet.")
    if not share_active(token, row[2]):
        raise HttpError(404, "Dieser Link ist abgelaufen.")
    return row[:2]


def via_share(book_owner):
    """Songs a share link shows: public ones and the book owner's own private ones (private songs of other people
    stay hidden, even when an admin put them into the book)."""
    return lambda owner, public: bool(public) or (owner is not None and owner == book_owner)


def share_days(v):
    if isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= SHARE_DAYS_MAX:
        raise HttpError(400, "Ungültige Gültigkeitsdauer.")
    return v


def set_share(bid, req, u=LOCAL_ADMIN):
    """{"on": true} -> link (kept if there is one), {"on": true, "renew": true} -> new link (the old one stops
    working), {"on": false} -> no link. "days": lifetime from now (0 = no expiry; default: admin setting) – for a
    new link, or with an existing one to extend/shorten it."""
    not_single()
    with tx() as c:
        check_manage(u, c, "books", bid)
        token, expires = c.execute("SELECT share, share_expires FROM books WHERE id=?", (bid,)).fetchone()
        old = token
        days = share_days(req["days"]) if "days" in req else None
        if not req.get("on", True):
            token = expires = None
        else:
            if not token or req.get("renew"):
                token = secrets.token_urlsafe(18)
                days = share_days_default(c) if days is None else days
            if days is not None:
                expires = now_ms() + days * DAY_MS if days else None
        c.execute("UPDATE books SET share=?, share_expires=? WHERE id=?", (token, expires, bid))
        note(c, u, "Teilen beendet" if not token else "Teilen-Link erstellt" if token != old else "Teilen-Link verlängert",
             "book", bid, c.execute("SELECT name FROM books WHERE id=?", (bid,)).fetchone()[0])
    return {"ok": True, "share": token, "share_expires": expires}


# Chord names on screen: "intl" (B, Bb) or "german" (H, B = Bb). Files always stay international (ChordPro);
# this is only how the app shows them. Per user (account; guests: browser), default for everybody set by admins.
NOTATIONS = ("intl", "german")


def notation_default(c):
    v = setting(c, "notation", "intl")
    return v if v in NOTATIONS else "intl"


def notation_value(v, allow_none=False):
    if v is None and allow_none:
        return None
    if v not in NOTATIONS:
        raise HttpError(400, "Ungültige Anfrage.")
    return v


def get_settings(u):
    """Settings for everybody (admin page); only admins see them."""
    if not (u and u["admin"]):
        raise HttpError(403, "Nur für Admins.")
    with tx() as c:
        return {"ok": True, "share_days": share_days_default(c), "notation": notation_default(c),
                "campfire_days": campfire_days_default(c)}


def put_settings(req, u):
    if not (u and u["admin"]):
        raise HttpError(403, "Nur für Admins.")
    with tx() as c:
        if "share_days" in req:
            c.execute("INSERT INTO settings (key, value) VALUES ('share_days', ?) "
                      "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(share_days(req["share_days"])),))
        if "notation" in req:
            c.execute("INSERT INTO settings (key, value) VALUES ('notation', ?) "
                      "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (notation_value(req["notation"]),))
        if "campfire_days" in req:
            d = campfire_days(req["campfire_days"])
            if not d:
                raise HttpError(400, "Ungültige Gültigkeitsdauer.")
            c.execute("INSERT INTO settings (key, value) VALUES ('campfire_days', ?) "
                      "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(d),))
        return {"ok": True, "share_days": share_days_default(c), "notation": notation_default(c),
                "campfire_days": campfire_days_default(c)}


def me_info(u):
    with tx() as c:
        own = c.execute("SELECT notation FROM users WHERE sub=?", (u["sub"],)).fetchone() if u and u["sub"] else None
        info = {"notation": own[0] if own else None, "notation_default": notation_default(c),
                "guest_access": GUEST_ACCESS or OIDC is None}
    return info | {"campfire": campfire_list()}  # own transaction (tx() is not re-entrant)


def set_my_notation(req, u):
    """{"notation": "intl" | "german" | null (= app default)} for the signed-in user."""
    need_user(u)
    if u["sub"] is None:
        raise HttpError(400, "Ungültige Anfrage.")
    with tx() as c:
        c.execute("UPDATE users SET notation=? WHERE sub=?", (notation_value(req.get("notation"), True), u["sub"]))
    return {"ok": True, **me_info(u)}


# ---------------------------------------------------------------- collaboration

def user_directory(u):
    """Everybody who has signed in once – to pick collaborators from (signed-in users only)."""
    need_user(u)
    with tx() as c:
        rows = c.execute("SELECT sub, username, coalesce(name, username) FROM users ORDER BY lower(coalesce(name, username))").fetchall()
    return {"ok": True, "users": [{"id": r[0], "username": r[1] or "", "name": r[2] or r[1] or "", "me": r[0] == u["sub"]}
                                  for r in rows]}


def get_collab(kind, rid, u):
    table = "songs" if kind == "song" else "books"
    with tx() as c:
        owner, _ = check_edit(u, c, table, rid)
        rows = c.execute("SELECT c.who, us.username, coalesce(us.name, us.username) FROM collab c "
                         "LEFT JOIN users us ON us.sub = c.who WHERE c.kind=? AND c.rid=?", (kind, rid)).fetchall()
        oname = c.execute("SELECT coalesce(name, username) FROM users WHERE sub=?", (owner,)).fetchone()
    return {"ok": True, "all": any(r[0] == "*" for r in rows), "manage": can_manage(u, owner),
            "owner": {"id": owner, "name": oname[0] if oname else ""},
            "users": sorted(({"id": r[0], "username": r[1] or "", "name": r[2] or r[1] or ""} for r in rows if r[0] != "*"),
                            key=lambda x: x["name"].casefold())}


def put_collab(kind, rid, req, u):
    """{"all": true/false, "users": [sub, …]} replaces who may work on the song/songbook (owner and admins only)."""
    not_single()
    table = "songs" if kind == "song" else "books"
    users = req.get("users") or []
    if not isinstance(users, list) or len(users) > 500 or not all(isinstance(x, str) for x in users):
        raise HttpError(400, "Ungültige Anfrage.")
    with tx() as c:
        owner, _ = check_manage(u, c, table, rid)
        known = {r[0] for r in c.execute("SELECT sub FROM users")}
        who = {x for x in users if x in known and x != owner} | ({"*"} if req.get("all") else set())
        c.execute("DELETE FROM collab WHERE kind=? AND rid=?", (kind, rid))
        c.executemany("INSERT INTO collab VALUES (?, ?, ?)", [(kind, rid, w) for w in sorted(who)])
        note(c, u, "Mitarbeit geändert", kind, rid,
             song_title(c, rid) if kind == "song" else c.execute("SELECT name FROM books WHERE id=?", (rid,)).fetchone()[0])
    return get_collab(kind, rid, u)


def attachment(name):
    safe = re.sub(r'[^A-Za-z0-9 ._-]', "_", name)
    return {"Content-Disposition": f"attachment; filename=\"{safe}\"; filename*=UTF-8''{urllib.parse.quote(name)}"}


# ---------------------------------------------------------------- login sessions

def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def start_session(user, id_token):
    """User row from the login (name, admin group – refreshed on every login) + a new session; returns the token."""
    token = secrets.token_urlsafe(32)
    with tx() as c:
        c.execute("INSERT INTO users (sub, username, name, admin, last_login) VALUES (?, ?, ?, ?, ?) ON CONFLICT (sub) DO UPDATE SET username=excluded.username, "
                  "name=excluded.name, admin=excluded.admin, last_login=excluded.last_login",
                  (user["sub"], user["username"], user["name"], int(user["admin"]), now_ms()))
        c.execute("DELETE FROM sessions WHERE expires < ?", (now_ms(),))
        c.execute("INSERT INTO sessions VALUES (?, ?, ?, ?)", (token_hash(token), user["sub"], now_ms() + SESSION_DAYS * 86_400_000, id_token))
        note(c, user, "angemeldet")
    return token


def session_user(token):
    if not token:
        return None
    with tx() as c:
        row = c.execute("SELECT u.sub, u.username, u.name, u.admin FROM sessions s JOIN users u ON u.sub = s.sub "
                        "WHERE s.id=? AND s.expires > ?", (token_hash(token), now_ms())).fetchone()
    return {"sub": row[0], "username": row[1], "name": row[2] or row[1], "admin": bool(row[3])} if row else None


def end_session(token):
    with tx() as c:
        row = c.execute("SELECT id_token FROM sessions WHERE id=?", (token_hash(token),)).fetchone()
        c.execute("DELETE FROM sessions WHERE id=?", (token_hash(token),))
    return row[0] if row else ""


def admin_users(u):
    """All users who ever logged in, with what they own (for the admin page)."""
    if not (u and u["admin"]):
        raise HttpError(403, "Nur für Admins.")
    with tx() as c:
        rows = c.execute(
            "SELECT u.sub, u.username, u.name, u.admin, u.last_login, "
            "(SELECT count(*) FROM songs s WHERE s.owner = u.sub AND s.file IS NOT NULL), "
            "(SELECT count(*) FROM songs s WHERE s.owner = u.sub AND s.file IS NOT NULL AND s.public = 0), "
            "(SELECT count(*) FROM books b WHERE b.owner = u.sub), "
            "(SELECT count(*) FROM sessions x WHERE x.sub = u.sub AND x.expires > ?) "
            "FROM users u ORDER BY lower(coalesce(u.name, u.username))", (now_ms(),)).fetchall()
    return [{"sub": r[0], "username": r[1], "name": r[2] or r[1], "admin": bool(r[3]), "last_login": r[4], "songs": r[5],
             "private": r[6], "books": r[7], "sessions": r[8], "me": r[0] == u["sub"]} for r in rows]


ACTIVITY_MAX = 500


def admin_user(sub, u):
    """One user for the admin page: their songs and songbooks and what they did (newest first)."""
    if not (u and u["admin"]):
        raise HttpError(403, "Nur für Admins.")
    with tx() as c:
        row = c.execute("SELECT sub, username, name, admin, last_login FROM users WHERE sub=?", (sub,)).fetchone()
        if not row:
            raise HttpError(404, "Benutzer nicht gefunden.")
        songs = []
        for sid, file, public in c.execute("SELECT id, file, public FROM songs WHERE owner=? AND file IS NOT NULL", (sub,)).fetchall():
            p = SONG_DIR / file
            if p.exists():
                mt, m = cached_meta(p)
                songs.append(entry(sid, file, mt, m) | {"public": bool(public)})
        songs.sort(key=lambda s: (s["title"].casefold(), s["artist"].casefold()))
        books = [{"id": r[0], "name": r[1], "public": bool(r[2]), "songs": r[3]} for r in c.execute(
            "SELECT b.id, b.name, b.public, (SELECT count(*) FROM book_songs bs WHERE bs.book = b.id) FROM books b "
            "WHERE b.owner=? ORDER BY lower(b.name)", (sub,))]
        live = {r[0] for r in c.execute("SELECT id FROM books")}
        acts = [{"at": r[0], "action": r[1], "kind": "song", "id": r[2], "file": r[4], "detail": (r[3] or "")[:-4]}
                for r in c.execute("SELECT v.at, v.action, v.song, v.file, s.file FROM versions v JOIN songs s ON s.id = v.song "
                                   "WHERE v.user=? ORDER BY v.at DESC LIMIT ?", (sub, ACTIVITY_MAX))]
        for at, action, kind, rid, detail in c.execute(
                "SELECT at, action, kind, rid, detail FROM activity WHERE user=? ORDER BY at DESC LIMIT ?", (sub, ACTIVITY_MAX)):
            a = {"at": at, "action": action, "kind": kind or "", "id": rid, "detail": detail or ""}
            if kind == "song":
                f = c.execute("SELECT file FROM songs WHERE id=?", (rid,)).fetchone()
                a["file"] = f[0] if f else None
            elif kind == "book" and rid not in live:
                a["id"] = None  # deleted songbook: no link
            acts.append(a)
    acts.sort(key=lambda a: a["at"], reverse=True)
    return {"ok": True, "user": {"sub": row[0], "username": row[1] or "", "name": row[2] or row[1] or "", "admin": bool(row[3]),
                                 "last_login": row[4], "me": row[0] == u["sub"]},
            "songs": songs, "books": books, "activity": acts[:ACTIVITY_MAX]}


def delete_user(sub, mode, u):
    """Remove a user from the app: sessions, tempos, user row. Their songs/songbooks go to the deleting admin
    (mode "transfer") or are deleted (songs into the trash folder + history, so an admin can still restore them).
    They can log in again later (new, empty account) – to lock someone out, do it at the identity provider."""
    if not (u and u["admin"]):
        raise HttpError(403, "Nur für Admins.")
    if sub == u["sub"]:
        raise HttpError(400, "Du kannst dich nicht selbst löschen.")
    if mode not in ("transfer", "delete"):
        raise HttpError(400, "Bitte angeben, was mit den Liedern passieren soll.")
    with tx() as c:
        if not c.execute("SELECT 1 FROM users WHERE sub=?", (sub,)).fetchone():
            raise HttpError(404, "Benutzer nicht gefunden.")
        if mode == "transfer":
            songs = c.execute("UPDATE songs SET owner=? WHERE owner=?", (u["sub"], sub)).rowcount
            books = c.execute("UPDATE books SET owner=? WHERE owner=?", (u["sub"], sub)).rowcount
        else:
            files = c.execute("SELECT id, file FROM songs WHERE owner=? AND file IS NOT NULL", (sub,)).fetchall()
            for sid, file in files:
                p = SONG_DIR / file
                if p.exists():
                    track(c, p)
                    to_trash(p)
                retire(c, sid, "gelöscht (Benutzer entfernt)", u["sub"])
            songs = len(files)
            books = c.execute("DELETE FROM books WHERE owner=?", (sub,)).rowcount
            c.execute("UPDATE songs SET owner=? WHERE owner=?", (u["sub"], sub))  # deleted songs: admins keep the history
        c.execute("DELETE FROM sessions WHERE sub=?", (sub,))
        c.execute("DELETE FROM user_tempos WHERE user=?", (sub,))
        c.execute("DELETE FROM favorites WHERE user=?", (sub,))
        c.execute("DELETE FROM collab WHERE who=?", (sub,))
        note(c, u, "Benutzer gelöscht", None, None, owner_nick(c, sub))
        c.execute("DELETE FROM activity WHERE user=?", (sub,))
        c.execute("DELETE FROM users WHERE sub=?", (sub,))
    return {"ok": True, "songs": songs, "books": books}


def cookie_header(value, max_age):
    secure = "; Secure" if PUBLIC_URL.startswith("https://") else ""
    return f"{COOKIE}={value}; Path=/; HttpOnly; SameSite=Lax; Max-Age={max_age}{secure}"


def safe_return(r):
    """Only hash routes of this app (#/lied/…) – no open redirect."""
    return r if isinstance(r, str) and re.fullmatch(r"#/[^\s]{0,500}", r) else "#/"


# ---------------------------------------------------------------- http

class Headers(dict):
    """Request headers with lower-case keys; get() ignores case like http.server's header object."""

    def get(self, key, default=None):
        return super().get(key.lower(), default)


METHODS = ("GET", "HEAD", "POST", "PUT", "DELETE")


class Request:
    """One request, independent of the server: the production server (Waitress, via wsgi_app) and the built-in
    fallback (Handler, http.server) both fill it in, call handle_method() and send out status/headers/body."""

    def __init__(self, command, path, headers, rfile):
        self.command, self.path, self.headers, self.rfile = command, path, headers, rfile
        self.status, self.out_headers, self.out = 500, [], b""

    def send(self, code, body, ctype, extra=None):
        self.status = code
        self.out_headers = [
            ("Content-Type", ctype),
            ("Content-Length", str(len(body))),
            ("X-Content-Type-Options", "nosniff"),
            ("Referrer-Policy", "no-referrer"),
            ("Content-Security-Policy",
             "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; "
             "img-src 'self' data:; media-src 'self'; frame-ancestors 'self'"),
            ("Cache-Control", "no-cache"),
            ("X-Robots-Tag", "noindex, nofollow"),
        ]
        if PUBLIC_URL.startswith("https://"):
            self.out_headers.append(("Strict-Transport-Security", "max-age=31536000"))
        self.out_headers += list((extra or {}).items())
        self.out = b"" if self.command == "HEAD" else body

    def send_json(self, code, obj):
        self.send(code, json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            raise HttpError(413, "Anfrage zu groß.")
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            raise HttpError(400, "Ungültige Anfrage.") from None

    def token(self):
        jar = http.cookies.SimpleCookie()
        try:
            jar.load(self.headers.get("Cookie") or "")
        except http.cookies.CookieError:
            return ""
        return jar[COOKIE].value if COOKIE in jar else ""

    def user(self):
        """Logged-in user, None for guests; everybody is admin when no login is configured."""
        if OIDC is None:
            return LOCAL_ADMIN
        if self._user is False:
            self._user = session_user(self.token())
        return self._user

    def redirect(self, url, extra=None):
        self.send(302, b"", "text/plain", {"Location": url, **(extra or {})})

    def auth_route(self, path, query):
        if path == "/auth/login":
            if OIDC is None:
                return self.redirect("/")
            return self.redirect(OIDC.start(safe_return(query.get("r"))))
        if path == "/auth/callback":
            user, id_token, ret = OIDC.finish(query)
            token = start_session(user, id_token)
            return self.redirect("/" + ret, {"Set-Cookie": cookie_header(token, SESSION_DAYS * 86400)})
        if path == "/auth/logout":
            id_token = end_session(self.token()) if self.token() else ""
            after = (PUBLIC_URL or "") + "/"
            url = OIDC.logout_url(id_token, after) if OIDC and id_token else "/"
            return self.redirect(url, {"Set-Cookie": cookie_header("", 0)})
        raise HttpError(404, "Nicht gefunden.")

    def route(self, method):
        split = urllib.parse.urlsplit(self.path)
        path = split.path
        if method == "GET" and path in STATIC:
            f, ctype = STATIC[path]
            return self.send(200, (HERE / f).read_bytes(), ctype)
        if method == "GET" and path == "/healthz":
            return self.send(*healthz())
        if method == "GET" and path == "/robots.txt":
            return self.send(200, ROBOTS, "text/plain; charset=utf-8")
        if method == "GET" and path.startswith("/auth/"):
            return self.auth_route(path, dict(urllib.parse.parse_qsl(split.query)))
        u = self.user()
        if method == "GET" and path == "/api/me":
            me = u and {k: u[k] for k in ("name", "username", "admin")}
            return self.send_json(200, {"ok": True, "auth": OIDC is not None, "user": me,
                                        "provider": OIDC.cfg.provider_name if OIDC else "",
                                        "account_url": OIDC.cfg.account_url if OIDC else "", **me_info(u)})
        if method == "PUT" and path == "/api/me/notation":
            return self.send_json(200, set_my_notation(self.body(), u))
        if method == "GET" and path == "/api/users":
            return self.send_json(200, user_directory(u))
        if m := re.fullmatch(r"/api/collab/(song|book)/(\d+)", path):
            if method == "GET":
                return self.send_json(200, get_collab(m[1], int(m[2]), u))
            if method == "PUT":
                return self.send_json(200, put_collab(m[1], int(m[2]), self.body(), u))
        if path == "/api/admin/settings":
            if method == "GET":
                return self.send_json(200, get_settings(u))
            if method == "PUT":
                return self.send_json(200, put_settings(self.body(), u))
        if path == "/api/admin/users" and method == "GET":
            return self.send_json(200, {"ok": True, "users": admin_users(u)})
        if (m := re.fullmatch(r"/api/admin/users/([A-Za-z0-9._@:|-]{1,200})", path)) and method == "GET":
            return self.send_json(200, admin_user(m[1], u))
        if (m := re.fullmatch(r"/api/admin/users/([A-Za-z0-9._@:|-]{1,200})", path)) and method == "DELETE":
            mode = dict(urllib.parse.parse_qsl(split.query)).get("mode", "")
            return self.send_json(200, delete_user(m[1], mode, u))
        if method == "POST" and path == "/api/songs/bulk":
            return self.send_json(200, bulk_edit(self.body(), u))
        if path == "/api/songs":
            if method == "GET":
                return self.send_json(200, {"ok": True, "songs": list_songs(u)})
            if method == "POST":
                return self.send_json(200, save_song(self.body(), u))
        if path.startswith("/api/songs/"):
            p = song_path(path[len("/api/songs/"):])
            if not p.exists():
                raise HttpError(404, "Lied nicht gefunden.")
            if method == "GET":
                return self.send_json(200, get_song(p, u))
            if method == "DELETE":
                return self.send_json(200, delete_song(p, u))
        if method == "POST" and path == "/api/tempo":
            return self.send_json(200, set_tempo(self.body(), u))
        if method == "POST" and path == "/api/favorite":
            return self.send_json(200, set_favorite(self.body(), u))
        if method == "POST" and path == "/api/copy":
            return self.send_json(200, copy_song(self.body(), u))
        if method == "POST" and path == "/api/visibility":
            return self.send_json(200, set_visibility(self.body(), u))
        if method == "GET" and path == "/api/deleted":
            need_user(u)
            return self.send_json(200, {"ok": True, "songs": deleted_songs(u)})
        if m := re.fullmatch(r"/api/history/(\d+)", path):
            if method == "GET":
                return self.send_json(200, history(int(m[1]), u))
        if method == "POST" and path == "/api/restore":
            return self.send_json(200, restore(self.body(), u))
        if path == "/api/books":
            if method == "GET":
                return self.send_json(200, {"ok": True, "books": books(u)})
            if method == "POST":
                return self.send_json(200, create_book(self.body(), u))
        if (m := re.fullmatch(r"/api/shared/([A-Za-z0-9_-]{1,64})(/inhalt|/export\.cho|/export\.zip|/songs/[^/]+)?", path)) \
                and method == "GET":
            tok, sub = m[1], m[2]
            if sub in (None, "/inhalt"):
                return self.send_json(200, get_book(0, content=bool(sub), u=u, token=tok))
            if sub.startswith("/export"):
                data, ctype, name = export_book(0, sub[-3:], u, tok)
                return self.send(200, data.encode() if isinstance(data, str) else data, ctype, attachment(name))
            p = song_path(sub[len("/songs/"):])
            if not p.exists():
                raise HttpError(404, "Lied nicht gefunden.")
            return self.send_json(200, get_song(p, u, tok))
        if m := re.fullmatch(r"/api/books/(\d+)(/inhalt|/lied|/share|/campfire|/export\.cho|/export\.zip)?", path):
            bid, sub = int(m[1]), m[2]
            if method == "GET" and sub in (None, "/inhalt"):
                return self.send_json(200, get_book(bid, content=bool(sub), u=u))
            if method == "GET" and sub and sub.startswith("/export"):
                data, ctype, name = export_book(bid, sub[-3:], u)
                return self.send(200, data.encode() if isinstance(data, str) else data, ctype, attachment(name))
            if method == "PUT" and not sub:
                return self.send_json(200, update_book(bid, self.body(), u))
            if method == "POST" and sub == "/share":
                return self.send_json(200, set_share(bid, self.body(), u))
            if method == "POST" and sub == "/campfire":
                return self.send_json(200, set_campfire(bid, self.body(), u))
            if method == "POST" and sub == "/lied":
                return self.send_json(200, toggle_book_song(bid, self.body(), u))
            if method == "DELETE" and not sub:
                return self.send_json(200, delete_book(bid, u))
        if method == "POST" and path == "/api/convert":
            need_user(u)  # fetches pages from the internet: only for signed-in users
            try:
                return self.send_json(200, do_convert(self.body(), self.lang))
            except ug.ConvertError as e:
                return self.send_json(200, {"ok": False, "error": e.localized(self.lang)})
            except ValueError:
                return self.send_json(200, {"ok": False, "error": i18n.tr(self.lang, "Ungültige Anfrage.")})
            except OSError as e:  # network errors while fetching
                return self.send_json(200, {"ok": False, "error": i18n.tr(self.lang, "Laden fehlgeschlagen: {err}", err=e)})
        if method == "POST" and path == "/api/zip":
            return self.send(200, make_zip(self.body().get("files") or []), "application/zip",
                             {"Content-Disposition": 'attachment; filename="chordpro.zip"'})
        raise HttpError(404, "Nicht gefunden.")

    def same_origin(self):
        """Changes only from our own pages (cookies are SameSite=Lax as well)."""
        origin = self.headers.get("Origin")
        if not origin:
            return True
        own = urllib.parse.urlsplit(PUBLIC_URL).netloc if PUBLIC_URL else self.headers.get("Host")
        return urllib.parse.urlsplit(origin).netloc == own

    def handle_method(self, method):
        self._user = False
        jar = http.cookies.SimpleCookie()
        try:
            jar.load(self.headers.get("Cookie") or "")
        except http.cookies.CookieError:
            pass
        self.lang = i18n.pick(self.headers.get("X-Lang"), jar["lang"].value if "lang" in jar else None,
                              self.headers.get("Accept-Language"))
        try:
            if method != "GET" and not self.same_origin():
                raise HttpError(403, "Fremde Herkunft.")
            self.route(method)
        except auth.AuthError as e:
            other = ""
            if getattr(e, "denied", False) and OIDC:  # signed in at the provider, but not allowed here: offer another account
                with contextlib.suppress(auth.AuthError):
                    url = OIDC.logout_url(getattr(e, "id_token", ""), (PUBLIC_URL or "") + "/")
                    other = f" · <a href='{html.escape(url)}'>{i18n.tr(self.lang, 'Mit einem anderen Konto anmelden')}</a>"
            page = ("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
                    f"<title>Dissonance</title><body style='font:16px system-ui;margin:2em'><h1>{i18n.tr(self.lang, 'Anmeldung fehlgeschlagen')}</h1>"
                    f"<p>{html.escape(e.localized(self.lang))}</p><p><a href='/'>{i18n.tr(self.lang, 'Zurück zu Dissonance')}</a>{other}</p>").encode()
            self.send(502 if "erreichbar" in e.text else 403 if "freigeschaltet" in e.text else 400, page, "text/html; charset=utf-8")
        except HttpError as e:
            self.send_json(e.code, {"ok": False, "error": e.localized(self.lang), **e.extra})
        except (ValueError, TypeError, KeyError):
            self.send_json(400, {"ok": False, "error": i18n.tr(self.lang, "Ungültige Anfrage.")})
        except OSError as e:
            self.send_json(500, {"ok": False, "error": i18n.tr(self.lang, "Speicherfehler: {err}", err=e.strerror or e)})

    def run(self):
        if self.command not in METHODS:
            self.send(405, b"", "text/plain", {"Allow": ", ".join(METHODS)})
        else:
            self.handle_method("GET" if self.command == "HEAD" else self.command)
        return self


def log(remote, command, path, status):
    sys.stderr.write(f'{remote} "{command} {path}" {status}\n')


STATUS_TEXT = {c: http.HTTPStatus(c).phrase for c in http.HTTPStatus}


def wsgi_app(environ, start_response):
    """WSGI entry point (Waitress in production)."""
    headers = Headers({k[5:].replace("_", "-").lower(): v for k, v in environ.items() if k.startswith("HTTP_")})
    for key in ("CONTENT_LENGTH", "CONTENT_TYPE"):
        if environ.get(key):
            headers[key.replace("_", "-").lower()] = environ[key]
    path = environ.get("REQUEST_URI") or (urllib.parse.quote(environ.get("PATH_INFO", "/").encode("latin-1"))
                                         + ("?" + environ["QUERY_STRING"] if environ.get("QUERY_STRING") else ""))
    r = Request(environ["REQUEST_METHOD"], path, headers, environ["wsgi.input"]).run()
    log(environ.get("REMOTE_ADDR", "-"), r.command, path, r.status)
    start_response(f"{r.status} {STATUS_TEXT.get(r.status, '')}", r.out_headers)
    return [r.out]


class Handler(BaseHTTPRequestHandler):
    """Built-in fallback server (Python standard library only) – for development and setups without Waitress.
    Not hardened against slow clients; production uses Waitress (see serve)."""
    server_version = "dissonance"

    def log_message(self, fmt, *args):
        pass  # requests are logged by log()

    def respond(self):
        r = Request(self.command, self.path, Headers({k.lower(): v for k, v in self.headers.items()}), self.rfile).run()
        log(self.address_string(), r.command, self.path, r.status)
        self.send_response(r.status)
        for k, v in r.out_headers:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(r.out)

    do_GET = do_HEAD = do_POST = do_PUT = do_DELETE = respond


def db_problem():
    """Why the database is not usable, or None. Checks the file on disk too: an open connection keeps working on a
    file whose folder was unmounted or replaced underneath."""
    try:
        if REQUIRE_DB and not (SONG_DIR / DB_NAME).is_file():
            return f"{SONG_DIR / DB_NAME} is missing (REQUIRE_DB=on) – is the song folder mounted?"
        with tx() as c:
            c.execute("SELECT 1").fetchone()
    except Exception as e:  # noqa: BLE001 – any failure means unhealthy
        return f"database not usable: {e}"
    return None


def healthz():
    problem = db_problem()
    return (503, (problem + "\n").encode(), "text/plain; charset=utf-8") if problem else (200, b"ok\n", "text/plain")


def _stop(*_):
    raise SystemExit(0)  # as PID 1 in a container Python ignores SIGTERM by default -> slow "docker stop"


def serve(port, host=""):
    """Waitress when it is installed (Dockerfile) and SERVER is not "builtin", otherwise http.server.
    Waitress reads every request completely before the app sees it, so slow clients only cost a cheap socket,
    not one of the worker threads; limits below."""
    try:
        import waitress
    except ImportError:
        waitress = None
    if waitress and os.environ.get("SERVER", "waitress") != "builtin":
        proxy = os.environ.get("TRUSTED_PROXY", "")  # e.g. "*" behind a reverse proxy: log the real client address
        print(f"listening on :{port} (waitress), songs in {SONG_DIR}", flush=True)
        waitress.serve(wsgi_app, host=host or "0.0.0.0", port=port, ident="dissonance",
                       threads=int(os.environ.get("THREADS", "8")),
                       connection_limit=int(os.environ.get("CONNECTION_LIMIT", "200")),
                       channel_timeout=30, max_request_header_size=64 * 1024, max_request_body_size=MAX_BODY,
                       **({"trusted_proxy": proxy, "trusted_proxy_count": 1, "trusted_proxy_headers": "x-forwarded-for",
                           "clear_untrusted_proxy_headers": True} if proxy else {}))
    else:
        print(f"listening on :{port} (built-in server), songs in {SONG_DIR}", flush=True)
        ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    import signal
    signal.signal(signal.SIGTERM, _stop)
    if problem := db_problem():
        sys.exit("Not starting: " + problem)
    serve(int(os.environ.get("PORT", "8080")))
