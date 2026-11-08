"""Ultimate Guitar / Ukulele-Tabs.com -> ChordPro conversion (no dependencies, Python >= 3.11).

Input: a UG tab page (URL or saved HTML; the song is in the `js-store` JSON), a ukulele-tabs.com song page
(song in a <pre>, chords as links), UG's own markup ([ch]..[/ch], [tab]..[/tab]) or plain "chords over lyrics" text.
"""
import html
import json
import re
import urllib.parse
import urllib.request

from i18n import Message


class ConvertError(Message, ValueError):
    """A problem with the input (shown to the user, translated)."""

# ---------------------------------------------------------------- chords

NOTES_SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
NOTES_FLAT = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
NOTE_INDEX = {n: i for i, n in enumerate(NOTES_SHARP)} | {n: i for i, n in enumerate(NOTES_FLAT)}
NOTE_INDEX |= {"H": 11, "Cb": 11, "Fb": 4, "E#": 5, "B#": 0}

# root, quality/extension, optional bass; suffix alphabet keeps words like "Dad" or "Bad" out
CHORD_RE = re.compile(
    r"^(?P<root>[A-H][#b]?)"
    r"(?P<suffix>(?:maj|min|dim|aug|sus|add|no|omit|alt|M|m|\+|°|ø|o|\d|\(|\)|#|b|-|,)*)"
    r"(?:/(?P<bass>[A-H][#b]?))?$"
)
# tokens that may stand on a chord line without being chords -> ChordPro annotations [*..]
ANNOTATION_RE = re.compile(
    r"^(?:n\.?\s?c\.?|\|+:?|:?\|+|x\d+|\(x\d+\)|\d+x|\(\d+x\)|[-–—*/%~>.]+|\.\.\.|\(|\))$", re.I
)
SECTION_RE = re.compile(r"^\s*\[(?!/?(?:ch|tab)\])([^\]\[]{1,40})\]\s*$", re.I)
TAB_STAFF_RE = re.compile(r"^\s*[a-gA-G][#b]?\s*[|:][-0-9|xhpbr/\\~()<>.=^ ]{4,}")
TAG_RE = re.compile(r"\[ch\](.*?)\[/ch\]", re.S)


def is_chord(tok):
    t = tok.strip("()")
    return bool(t) and bool(CHORD_RE.match(t))


def transpose_chord(chord, steps, flats):
    if steps == 0:
        return chord
    m = CHORD_RE.match(chord)
    if not m:
        return chord
    names = NOTES_FLAT if flats else NOTES_SHARP

    def tr(note):
        return names[(NOTE_INDEX[note] + steps) % 12]

    out = tr(m["root"]) + m["suffix"]
    if m["bass"]:
        out += "/" + tr(m["bass"])
    return out


# keys written with flats (major / minor tonic)
FLAT_KEYS = {(5, False), (10, False), (3, False), (8, False), (1, False), (6, False),
             (2, True), (7, True), (0, True), (5, True), (10, True), (3, True)}


def auto_flats(chords, steps):
    """Untransposed: keep the song's own spelling. Transposed: spelling of the new key
    (taken from the first chord, as UG rarely sets a key)."""
    ms = [m for m in map(CHORD_RE.match, chords) if m]
    if not ms:
        return False
    if steps == 0:
        nflat = sum(1 for m in ms if m["root"].endswith("b"))
        nsharp = sum(1 for m in ms if m["root"].endswith("#"))
        return nflat > nsharp
    first = ms[0]
    minor = bool(re.match(r"m(?!aj)|min", first["suffix"]))
    return ((NOTE_INDEX[first["root"]] + steps) % 12, minor) in FLAT_KEYS


# ---------------------------------------------------------------- line model

def tokenize(line, tagged):
    """Split a chord-line candidate into (col, text, is_tagged, glued) tokens."""
    toks = []
    for m in re.finditer(r"\S+", line):
        start, text = m.start(), m.group()
        # a tagged chord can be glued to a marker ("G*" = one strum, "Am-"): split it off,
        # the marker keeps the chord's column so it does not split the lyric word
        for tcol, tlen in tagged:
            if start == tcol and len(text) > tlen:
                toks.append((start, text[:tlen], True, False))
                toks.append((start, text[tlen:], False, True))
                break
        else:
            toks.append((start, text, any(start == c for c, _ in tagged), False))
    return toks


def parse_line(raw):
    """-> dict(kind=blank|section|chords|text|tab, ...)"""
    line = raw.replace("\t", "    ").rstrip()
    # remove UG [tab] wrappers (they only group a chord line with its lyric line)
    line = re.sub(r"\[/?tab\]", "", line, flags=re.I)
    if not line.strip():
        return {"kind": "blank"}
    m = SECTION_RE.match(line)
    if m:
        return {"kind": "section", "name": m.group(1).strip()}

    # strip [ch] tags, remember where the chords sit
    plain, tagged, pos = "", [], 0
    for m in TAG_RE.finditer(line):
        plain += line[pos:m.start()]
        tagged.append((len(plain), len(m.group(1))))
        plain += m.group(1)
        pos = m.end()
    plain += line[pos:]

    if TAB_STAFF_RE.match(plain):
        return {"kind": "tab", "text": plain}

    toks = tokenize(plain, tagged)

    def chord_tok(t):
        return t[2] or is_chord(t[1])

    def chordish(t):
        return chord_tok(t) or ANNOTATION_RE.match(t[1])

    note = None
    n = 0
    while n < len(toks) and chordish(toks[n]):
        n += 1
    # "E  B  F#   C#m (only once, then stop)" -> chords + trailing note
    if 0 < n < len(toks) and sum(map(chord_tok, toks[:n])) >= 2 and toks[n][1][0] in "([":
        note = (toks[n][0], plain[toks[n][0]:].strip())
        toks = toks[:n]
    has_chord = any(map(chord_tok, toks))
    has_nc = any(re.fullmatch(r"n\.?\s?c\.?", t[1], re.I) for t in toks)
    if toks and all(map(chordish, toks)) and (has_chord or has_nc):
        items = []
        for seq, (col, text, tag, glued) in enumerate(toks):
            if chord_tok((col, text, tag, glued)):
                items.append((col, text.strip("()"), "chord", 0))
            else:
                items.append((col, text, "annot", 1 if glued else 0))
        if note:
            items.append((note[0], note[1], "annot", 0))
        return {"kind": "chords", "items": items}
    if tagged:
        # text with chords inside, e.g. "(Am C G D - Capo 4)"
        return {"kind": "text", "text": TAG_RE.sub(lambda m: "[" + m.group(1) + "]", line), "inline": True}
    inner = re.findall(r"\[([^\]\[]*)\]", plain)
    if inner and all(is_chord(c) or c.startswith("*") for c in inner):
        # already ChordPro-style ("[Am]Hello")
        return {"kind": "text", "text": plain, "inline": True}
    return {"kind": "text", "text": plain}


def no_brackets(text):
    """[ ] would start a chord in ChordPro – keep them out of lyrics and annotations."""
    return text.replace("[", "(").replace("]", ")")


def fmt_item(text, kind, steps, flats):
    if kind == "chord":
        return "[" + transpose_chord(text, steps, flats) + "]"
    return "[*" + no_brackets(text) + "]"


def merge(chord_line, lyric, steps, flats):
    out = lyric
    # insert from the right so earlier columns stay valid
    # glued markers sort after their chord's column -> inserted first -> end up right after the chord
    for col, text, kind, _ in sorted(chord_line["items"], key=lambda i: (i[0], i[3]), reverse=True):
        if col > len(out):
            out = out + " " * (col - len(out))
        out = out[:col] + fmt_item(text, kind, steps, flats) + out[col:]
    return out.rstrip()


def chords_only(chord_line, steps, flats):
    out = ""
    for _, t, k, glued in chord_line["items"]:
        out += ("" if glued or not out else " ") + fmt_item(t, k, steps, flats)
    return out


def inline_transpose(text, steps, flats):
    return re.sub(r"\[([^\]*][^\]]*)\]", lambda m: "[" + transpose_chord(m.group(1), steps, flats) + "]", text)


# ---------------------------------------------------------------- sections

def section_env(name):
    n = name.lower()
    if re.search(r"pre|post", n):
        return "verse"
    if re.search(r"chorus|refrain|hook", n):
        return "chorus"
    if re.search(r"bridge", n):
        return "bridge"
    return "verse"


def body_to_chordpro(content, steps=0, flats=None):
    lines = [parse_line(l) for l in content.replace("\r\n", "\n").replace("\r", "\n").split("\n")]

    if flats is None:
        flats = auto_flats([t for l in lines if l["kind"] == "chords" for _, t, k, _ in l["items"] if k == "chord"], steps)

    out, env, in_tab, i = [], None, False, 0

    def close():
        nonlocal env, in_tab
        if in_tab:
            out.append("{end_of_tab}")
            in_tab = False
        while out and out[-1] == "":
            out.pop()
        if env:
            out.append("{end_of_%s}" % env)
            env = None

    # lines before the first [Section] are notes ("* = One strum") – but only if the song has sections
    seen_section = not any(l["kind"] == "section" for l in lines)
    while i < len(lines):
        l = lines[i]
        k = l["kind"]
        if k != "tab" and in_tab:
            out.append("{end_of_tab}")
            in_tab = False
        if k == "section":
            close()
            if out:
                out.append("")
            env = section_env(l["name"])
            out.append("{start_of_%s: %s}" % (env, l["name"]))
            seen_section = True
        elif k == "blank":
            if out and out[-1] != "" and not out[-1].startswith("{start_of"):
                out.append("")
        elif k == "tab":
            if not in_tab:
                out.append("{start_of_tab}")
                in_tab = True
            out.append(l["text"].rstrip())
        elif k == "chords":
            nxt = lines[i + 1] if i + 1 < len(lines) else None
            if nxt and nxt["kind"] == "text" and not nxt.get("inline"):
                out.append(merge(l, no_brackets(nxt["text"]), steps, flats))
                i += 1
            else:
                out.append(chords_only(l, steps, flats))
        else:
            text = l["text"] if l.get("inline") else no_brackets(l["text"])
            if l.get("inline"):
                text = inline_transpose(text, steps, flats)
            if not l.get("inline") and (not seen_section or text.lstrip().startswith("#")):
                # "# note" would be a hidden comment line in ChordPro – show it as a visible comment instead
                out.append("{comment: %s}" % text.strip().lstrip("#").strip())
            else:
                out.append(text.rstrip())
        i += 1
    close()
    # collapse blank runs
    res = []
    for line in out:
        if line == "" and (not res or res[-1] == ""):
            continue
        res.append(line)
    return "\n".join(res).strip() + "\n"


# ---------------------------------------------------------------- UG page

def extract_ug(page_html):
    m = re.search(r'class="js-store"\s+data-content="([^"]*)"', page_html)
    if not m:
        raise ConvertError("Keine Ultimate-Guitar-Songdaten in der Seite gefunden (js-store fehlt).")
    data = json.loads(html.unescape(m.group(1)))
    page = data.get("store", {}).get("page", {}).get("data", {})
    tv = page.get("tab_view") or {}
    tab = page.get("tab") or {}
    content = (tv.get("wiki_tab") or {}).get("content")
    if not content:
        kind = tab.get("type") or "?"
        raise ConvertError("Dieser Tab ({kind}) enthält keinen Text – Pro-/Official-Tabs werden nicht unterstützt.", kind=kind)
    meta = tv.get("meta") or {}
    tuning = meta.get("tuning") or {}
    return {
        "title": tab.get("song_name") or "",
        "artist": tab.get("artist_name") or "",
        "key": tab.get("tonality_name") or meta.get("tonality") or "",
        "capo": meta.get("capo") or 0,
        "tuning": tuning.get("value") if tuning.get("name") not in (None, "", "Standard") else "",
        "type": tab.get("type") or "",
        "instrument": instrument_of(tab.get("type") or "", tab.get("tab_url") or "", tuning.get("value") or ""),
        "url": tab.get("tab_url") or "",
        "content": content,
    }


class AlbumPage(ConvertError):
    """ukulele-tabs.com album page: no song on it, only a link to the song page (url, may be empty)."""
    def __init__(self, url=""):
        if url:
            super().__init__("Das ist eine Album-Seite von Ukulele-Tabs.com, kein Lied. Das Lied ist hier: {url}", url=url)
        else:
            super().__init__("Das ist eine Album-Seite von Ukulele-Tabs.com, kein Lied.")
        self.url = url


UKT_BASE = "https://www.ukulele-tabs.com"


def _meta(page_html, prop):
    m = re.search(r'<meta\s+(?:property|name)="%s"\s+content="([^"]*)"' % re.escape(prop), page_html)
    return html.unescape(m.group(1)).strip() if m else ""


def extract_ukt(page_html):
    """Song page of ukulele-tabs.com: lyrics + chords in a <pre>, chords are <a class="… chord">Am</a> with a hidden
    diagram image inside; artist/song in the page's ad script, key in itemprop="musicalKey"."""
    url = _meta(page_html, "og:url")
    pre = re.search(r"<pre[^>]*>(.*?)</pre>", page_html, re.S)
    if not pre:
        # album page: link to the tab of the same song, if there is one
        title = _meta(page_html, "og:title")
        song = re.split(r"\s+by\s+", title)[0]
        slug = re.sub(r"[^a-z0-9]+", "-", song.lower()).strip("-")
        links = re.findall(r'href="(/uke-songs/[^"/]+/[^"]*-uke-tab-\d+\.html)"', page_html)
        link = next((l for l in links if slug and l.rsplit("/", 1)[1].startswith(slug + "-uke-tab-")), "")
        raise AlbumPage(UKT_BASE + link if link else "")
    body = re.sub(r"<span>\s*<img[^>]*>\s*</span>", "", pre.group(1))
    body = re.sub(r'<a\b[^>]*class="[^"]*\bchord\b[^"]*"[^>]*>(.*?)</a>', r"[ch]\1[/ch]", body, flags=re.S)
    body = re.sub(r"<br\s*/?>", "\n", body)
    body = html.unescape(re.sub(r"<[^>]+>", "", body)).replace("\r", "").replace("\xa0", " ")
    m = re.search(r"artist:\s*'((?:[^'\\]|\\.)*)',\s*song:\s*'((?:[^'\\]|\\.)*)'", page_html)
    if m:
        artist, title = (html.unescape(x.replace("\\'", "'")) for x in m.groups())
    else:  # "Bubbly Uke tab by Colbie Caillat"
        title, _, artist = _meta(page_html, "og:title").partition(" by ")
        title = re.sub(r"\s+Uke tab$", "", title, flags=re.I)
    key = re.search(r'itemprop="musicalKey"\s+content="\s*([^"]*?)\s*"', page_html)
    return {"title": title.strip(), "artist": artist.strip(), "key": key.group(1) if key else "", "capo": 0,
            "tuning": "", "type": "Ukulele", "instrument": "ukulele", "url": url, "content": body.strip("\n") + "\n"}


def extract_page(page_html):
    if "js-store" in page_html:
        return extract_ug(page_html)
    if re.search(r'content="Ukulele-Tabs\.com"|ukulele-tabs\.com/', page_html, re.I):
        return extract_ukt(page_html)
    raise ConvertError("Keine Songdaten gefunden – unterstützt werden Seiten von Ultimate Guitar (js-store) und Ukulele-Tabs.com.")


def instrument_of(kind, url, tuning):
    """UG marks ukulele sheets as type "Ukulele Chords" and in the URL (…-ukulele-123); guitar otherwise, bass unmarked."""
    if "ukulele" in kind.lower() or "-ukulele-" in url.lower() or re.sub(r"\s+", "", tuning.upper()) in ("GCEA", "ADF#B", "DGBE"):
        return "ukulele"
    if "bass" in kind.lower():
        return ""
    return "guitar"


ALLOWED_HOST = re.compile(r"^([a-z0-9-]+\.)?(ultimate-guitar|ukulele-tabs)\.com$")
UA = "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0"


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def check_url(url):
    u = urllib.parse.urlsplit(url.strip())
    if u.scheme != "https" or not ALLOWED_HOST.match((u.hostname or "").lower()):
        raise ConvertError("Nur https-Links von ultimate-guitar.com und ukulele-tabs.com werden geladen.")
    return u.geturl()


def fetch_page(url, timeout=15, limit=5 * 1024 * 1024):
    url = check_url(url)
    opener = urllib.request.build_opener(_SafeRedirect)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "de,en;q=0.8"})
    with opener.open(req, timeout=timeout) as r:
        body = r.read(limit + 1)
    if len(body) > limit:
        raise ConvertError("Seite zu groß.")
    return body.decode("utf-8", "replace")


# ---------------------------------------------------------------- top level

INSTRUMENTS = ("guitar", "ukulele")


LABELS = {"en": {"tuning": "Tuning", "source": "Source"}, "de": {"tuning": "Stimmung", "source": "Quelle"}}


def convert(content, title="", artist="", key="", capo=0, tuning="", url="", steps=0,
            flats=None, apply_capo=False, instrument="", lang="en"):
    """lang: language of the notes the converter adds (tuning comment, source line)."""
    words = LABELS.get(lang, LABELS["en"])
    capo = int(capo or 0)
    if apply_capo and capo:
        steps += capo
        capo = 0
    head = []
    if title:
        head.append("{title: %s}" % title)
    if artist:
        head.append("{artist: %s}" % artist)
    if key:
        head.append("{key: %s}" % transpose_chord(key, steps, bool(flats)))
    if capo:
        head.append("{capo: %d}" % capo)
    if instrument in INSTRUMENTS:
        head.append("{x_instrument: %s}" % instrument)
    if tuning and instrument != "ukulele":
        head.append("{comment: %s: %s}" % (words["tuning"], tuning))
    if url:
        head.append("# %s: %s" % (words["source"], url))
    body = body_to_chordpro(content, steps, flats)
    return ("\n".join(head) + "\n\n" if head else "") + body


def convert_page(page_html, instrument="", **opts):
    """instrument: "" = as detected from the page, else guitar/ukulele."""
    s = extract_page(page_html)
    s["instrument"] = instrument or s["instrument"]
    text = convert(s["content"], s["title"], s["artist"], s["key"], s["capo"], s["tuning"], s["url"],
                   instrument=s["instrument"], **opts)
    return s, text


def filename(title, artist):
    base = " - ".join(x for x in (artist, title) if x) or "song"
    base = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "", base).strip(" .")
    return (base[:120] or "song") + ".cho"
