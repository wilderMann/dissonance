"""Convert a Word song collection (.docx, chords above lyrics aligned with spaces/tabs) to ChordPro files.

Local tool, not part of the web app. One song per "Heading 1" paragraph ("Title- Artist"). Word documents use a
proportional font (Calibri), so chord positions are found by measuring text widths with metric-compatible fonts
(Carlito for Calibri, Liberation Mono for Courier New) instead of counting characters; the aligned
"chords over lyrics" text then goes through the normal converter (sections, annotations, transposition rules).

usage: python3 docx2chordpro.py <file.docx> <output dir>
"""
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

from PIL import ImageFont

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import ug2chordpro as ug  # noqa: E402

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
FONTS = {  # Word font -> metric-compatible font file (regular, bold)
    "calibri": ("/usr/share/fonts/google-carlito-fonts/Carlito-Regular.ttf", "/usr/share/fonts/google-carlito-fonts/Carlito-Bold.ttf"),
    "courier new": ("/usr/share/fonts/liberation-mono-fonts/LiberationMono-Regular.ttf", "/usr/share/fonts/liberation-mono-fonts/LiberationMono-Bold.ttf"),
}
_font_cache = {}


def width(text, font, bold, half_points):
    """Advance width in twips (1/20 pt)."""
    files = FONTS.get(font.lower(), FONTS["calibri"])
    key = (files[bool(bold)])
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(key, 1000)
    return _font_cache[key].getlength(text) / 1000 * (half_points / 2) * 20


class Styles:
    """Run properties from styles.xml (basedOn chain) and document defaults; theme font = Calibri."""

    def __init__(self, z):
        root = ET.fromstring(z.read("word/styles.xml"))
        self.styles = {s.get(W + "styleId"): s for s in root.iter(W + "style")}
        self.names = {k: (s.find(W + "name").get(W + "val") if s.find(W + "name") is not None else "") for k, s in self.styles.items()}
        d = root.find(f"{W}docDefaults/{W}rPrDefault/{W}rPr")
        self.default = self.props(d, {"font": "Calibri", "sz": 22, "b": False})
        tabs = re.search(rb'w:defaultTabStop w:val="(\d+)"', z.read("word/settings.xml"))
        self.tab = int(tabs.group(1)) if tabs else 708

    @staticmethod
    def props(rpr, base):
        p = dict(base)
        if rpr is None:
            return p
        f = rpr.find(W + "rFonts")
        if f is not None and f.get(W + "ascii"):
            p["font"] = f.get(W + "ascii")
        sz = rpr.find(W + "sz")
        if sz is not None:
            p["sz"] = int(sz.get(W + "val"))
        b = rpr.find(W + "b")
        if b is not None:
            p["b"] = b.get(W + "val") not in ("0", "false")
        return p

    def of_style(self, sid, seen=()):
        s = self.styles.get(sid)
        if s is None or sid in seen:
            return dict(self.default)
        based = s.find(W + "basedOn")
        base = self.of_style(based.get(W + "val"), seen + (sid,)) if based is not None else dict(self.default)
        return self.props(s.find(W + "rPr"), base)


def para_lines(p, st):
    """Lines of a paragraph (split at <w:br>) as (text, xs): xs[i] = x start of char i in twips.
    Only the paragraph's own runs – text boxes / drawings (layout leftovers) are skipped."""
    ps = p.find(f"{W}pPr/{W}pStyle")
    sid = ps.get(W + "val") if ps is not None else None
    pprops = st.of_style(sid) if sid else dict(st.default)
    lines, text, xs, x = [], [], [], 0.0
    runs = [r for child in p for r in ([child] if child.tag == W + "r" else child.iter(W + "r") if child.tag in (W + "hyperlink", W + "smartTag", W + "ins") else [])]
    for r in runs:
        rs = r.find(f"{W}rPr/{W}rStyle")
        base = st.of_style(rs.get(W + "val")) if rs is not None else pprops
        props = st.props(r.find(W + "rPr"), base)
        for n in r:
            if n.tag == W + "t":
                for ch in n.text or "":
                    text.append(ch); xs.append(x)
                    x += width(ch, props["font"], props["b"], props["sz"])
            elif n.tag == W + "tab":
                text.append("\t"); xs.append(x)
                x = (int(x // st.tab) + 1) * st.tab
            elif n.tag in (W + "br", W + "cr"):
                lines.append(("".join(text), xs)); text, xs, x = [], [], 0.0
    lines.append(("".join(text), xs))
    return lines, st.names.get(sid, "")


def align(chord_line, lyric_line):
    """Chord line + lyric line (measured) -> the same pair as monospace text, chords over the right characters."""
    (ctext, cxs), (ltext, lxs) = chord_line, lyric_line
    lead = len(ltext) - len(ltext.lstrip(" \t"))
    lyric = ltext[lead:].replace("\t", " ").rstrip()
    lx = lxs[lead:lead + len(lyric)]
    out, end = "", 0
    for m in re.finditer(r"[^ \t]+", ctext):
        cx = cxs[m.start()]
        col = 0
        while col < len(lx) and (lx[col + 1] if col + 1 < len(lx) else lx[col] + 1e9) <= cx + 1:
            col += 1
        if lx and cx > lx[-1] + 200:  # clearly behind the lyric: keep the visual gap roughly
            col = len(lyric) + 1 + int((cx - lx[-1]) // 120)
        col = max(col, end + 1 if out else 0)
        out = out.ljust(col) + m.group(0)
        end = len(out)
    return out, lyric


def split_title(h):
    h = " ".join(h.split())
    m = re.match(r"^(.+?)(?:\s*[-–]\s+|\s+by\s+)(.+)$", h)
    return (m.group(1).strip(), m.group(2).strip()) if m else (h, "")


def in_textbox(body):
    """ids of paragraphs that sit inside text boxes (skipped: they duplicate the song text)."""
    return {id(p) for tb in body.iter(W + "txbxContent") for p in tb.iter(W + "p")}


def align_mono(chord_line, lyric_line):
    """Same pair by character columns (text pasted from a fixed-width source, e.g. Ultimate Guitar)."""
    c, l = chord_line[0].expandtabs(8).rstrip(), lyric_line[0].expandtabs(8).rstrip()
    lead = min(len(l) - len(l.lstrip()), len(c) - len(c.lstrip()))
    return c[lead:], l[lead:]


def chord_cols(c):
    return [(m.start(), m.group(0)) for m in re.finditer(r"\S+", c)]


def at_word_start(col, lyric):
    return col >= len(lyric.rstrip()) or col == 0 or lyric[col - 1] == " "


def snap(c, l):
    """A chord one letter into a word ("H[Bb]elp") almost always belongs to the word start."""
    out, end = "", 0
    for col, tok in chord_cols(c):
        if 0 < col < len(l) and l[col - 1] != " " and (col == 1 or l[col - 2] == " ") and col - 1 >= end:
            col -= 1
        out = out.ljust(col) + tok
        end = len(out) + 1
    return out


SECTION_PREFIX = re.compile(r"^\s*[\[(]((?:[A-Za-zÄÖÜäöü-]+)(?: ?\d+)?)[\])]:?\s*")


def split_section(l):
    """"[Chorus] Wenn du …" -> ("[Chorus]", "Wenn du …", leading spaces to shift the chords by); [Am] is no label."""
    m = SECTION_PREFIX.match(l)
    if m and not ug.is_chord(m.group(1)) and ug.SECTION_RE.match("[" + m.group(1) + "]"):
        # the label was typed in front of the lyric later – the chords still refer to the lyric without it
        return "[" + m.group(1) + "]", l[m.end():], len(l) - len(l.lstrip(" "))
    lead = len(l) - len(l.lstrip(" "))
    return None, l[lead:], lead


def shift(c, cut):
    """Move a chord line left by cut columns (right if negative; chords that would fall off stay at 0, in order)."""
    out = ""
    for col, tok in chord_cols(c):
        col = max(col - cut, len(out) + 1 if out else 0, 0)
        out = out.ljust(col) + tok
    return out


def best_shift(c, l, span=4):
    """Hand-made chord lines are often off by a few spaces for a whole line: try small offsets and keep the one
    with the most chords at word starts (ties: the smallest move)."""
    best = (sum(at_word_start(col, l) for col, _ in chord_cols(c)), 0, c)
    for d in range(-span, span + 1):
        if not d:
            continue
        moved = shift(c, -d) if d > 0 else shift(c, -d)
        hits = sum(at_word_start(col, l) for col, _ in chord_cols(moved))
        if hits > best[0] or (hits == best[0] and abs(d) < abs(best[1])):
            best = (hits, d, moved)
    return best[2]


INLINE_CHORD = re.compile(r"(?<!\S)([A-H][#b]?(?:m|maj7|m7|7|sus2|sus4|dim|aug|add9|6|9)?(?:/[A-H][#b]?)?)(?=\s|$)")


def inline_chords(lines):
    """Songs written as "An der C Haltestelle" (chord names in the lyric line) -> "An der [C]Haltestelle"."""
    out = []
    for t in lines:
        t = INLINE_CHORD.sub(r"[\1]", t)
        out.append(re.sub(r"(\[[^\]]+\]) (?=\S)(?!\[)", r"\1", t))
    return out


def song_text(lines):
    """Measured lines -> plain 'chords over lyrics' text for the converter, plus notes for the report.
    Chord/lyric pairs are aligned twice (measured widths vs. character columns); per song the method that puts
    more chords at word starts wins – Word files mix visually aligned songs and songs pasted from fixed-width text."""
    kinds = [ug.parse_line(t.replace("\t", " "))["kind"] for t, _ in lines]
    pairs = {i for i in range(len(lines) - 1) if kinds[i] == "chords" and kinds[i + 1] == "text"}
    score = {}
    for name, fn in (("Breite", align), ("Spalten", align_mono)):
        hits = total = 0
        for i in pairs:
            c, l = fn(lines[i], lines[i + 1])
            for col, _ in chord_cols(c):
                total += 1
                hits += at_word_start(col, l)
        score[name] = hits / total if total else 0
    method = "Breite" if score["Breite"] > score["Spalten"] else "Spalten"
    fn = align if method == "Breite" else align_mono
    out, notes, final, i = [], [], [], 0
    while i < len(lines):
        t, xs = lines[i]
        if i in pairs:
            c, l = fn(lines[i], lines[i + 1])
            sec, l, cut = split_section(l)
            if sec:
                out.append(sec)
            c = snap(best_shift(shift(c, cut), l), l)
            final += [at_word_start(col, l) for col, _ in chord_cols(c)]
            out += [c, l]
            i += 2
            continue
        if kinds[i] == "chords":
            out.append(re.sub(r"[ \t]+", "  ", t.strip()))
        else:
            sec, rest, _ = split_section(t.replace("\t", " "))
            out += [x for x in (sec, rest.strip()) if x is not None and (x or not sec)]
            if re.search(r"\b[A-H][#b]?m?7?\b\s*\(", t):
                notes.append(f"Akkord im Text? „{t.strip()[:70]}“")
        i += 1
    if not pairs and not any(k == "chords" for k in kinds):
        candidate = inline_chords(out)
        if sum(x.count("[") for x in candidate) - sum(x.count("[") for x in out) >= 5:
            notes.append("Akkorde standen im Text („An der C Haltestelle“) – umgewandelt, bitte prüfen")
            return "\n".join(candidate), notes
    share = sum(final) / len(final) if final else 0
    notes.insert(0, f"{share:.0%} der Akkorde am Wortanfang (Ausrichtung nach {method})")
    return "\n".join(out), notes


def main(src, dest):
    z = zipfile.ZipFile(src)
    st = Styles(z)
    body = ET.fromstring(z.read("word/document.xml")).find(W + "body")
    skip = in_textbox(body)
    songs, cur, preamble = [], None, []
    for p in body.iter(W + "p"):
        if id(p) in skip:
            continue
        lines, style = para_lines(p, st)
        if style.lower() == "heading 1":
            head = " ".join("".join(t for t, _ in lines).split())
            if head:
                cur = {"heading": head, "lines": []}
                songs.append(cur)
            elif cur is not None:
                cur["lines"].append(("", []))
            continue
        (cur["lines"] if cur is not None else preamble).extend(lines)
    os.makedirs(dest, exist_ok=True)
    report, combined, used = [], [], set()
    for n, s in enumerate(songs, 1):
        title, artist = split_title(s["heading"])
        text, notes = song_text(s["lines"])
        cho = ug.convert(text, title, artist, lang="de")
        cho = cho.replace("{artist: %s}\n" % artist, "{artist: %s}\n# Quelle: %s\n" % (artist, os.path.basename(src)), 1) if artist else cho
        name = ug.filename(title, artist)
        base, k = name[:-4], 2
        while name in used:
            name, k = f"{base} ({k}).cho", k + 1
        used.add(name)
        with open(os.path.join(dest, name), "w", encoding="utf-8") as f:
            f.write(cho)
        combined.append(cho.rstrip("\n"))
        chords = len(re.findall(r"\[[^*\]][^\]]*\]", cho))
        warn = list(notes)
        if not artist:
            warn.append("kein Interpret im Titel erkannt")
        if chords == 0:
            warn.append("keine Akkorde gefunden")
        report.append(f"| {n} | {name} | {chords} | {'; '.join(warn)} |")
    with open(os.path.join(dest, "_alle Lieder.cho"), "w", encoding="utf-8") as f:
        f.write("\n{new_song}\n".join(combined) + "\n")
    with open(os.path.join(dest, "_Bericht.md"), "w", encoding="utf-8") as f:
        f.write(f"# {os.path.basename(src)} → ChordPro\n\n{len(songs)} Lieder. Vor dem ersten Lied ignoriert: "
                f"{' / '.join(t.strip() for t, _ in preamble if t.strip())[:200]}\n\n"
                "| # | Datei | Akkorde | Hinweise |\n|---|---|---|---|\n" + "\n".join(report) + "\n")
    print(f"{len(songs)} songs -> {dest}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
