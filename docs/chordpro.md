# ChordPro support

[← Documentation](index.md)

Songs are plain [ChordPro](https://www.chordpro.org/chordpro/) files, so they open in the ChordPro program (and other
ChordPro tools) and back. Dissonance understands:

| | Directives |
|---|---|
| Song info | `{title}`/`{t}`, `{sorttitle}` (list order), `{subtitle}`/`{st}`, `{artist}`, `{sortartist}`, `{composer}`, `{lyricist}`, `{album}`, `{year}`, `{copyright}`, `{key}`, `{time}`, `{tempo}`, `{duration}`, `{capo}`, `{meta: name value}` |
| Sections | `{start_of_chorus}`/`{soc}`, verse, bridge, any `{start_of_…}` with `label="…"`, `{chorus}`, `{start_of_tab}`/`{sot}`, `{start_of_grid}`/`{sog}` |
| Grids | bars `\|` `\|\|` `\|.` `\|:` `:\|` `:\|:` `\|1`, cells: chord, `C~G`, `.`, `/`, `%`, `%%`, margin text, strum lines (`\|S dn up …`) |
| Transposition | `{transpose: n}` (also `2f`/`2s`): at the top it is the song's transposition (♭/♯ in play mode, "Remember key" writes it), later ones modulate, `{transpose}` goes back |
| Text | `{comment}`/`{c}`, `{comment_italic}`/`{ci}`, `{comment_box}`/`{cb}`, `{highlight}`, `[Am]` chords, `[*N.C.]` annotations, `#` comments |
| Chords | `{define}` fingerings, instrument selectors like `{comment-ukulele: …}` / `{comment-!guitar: …}` |
| Files | `{new_song}`/`{ns}` (several songs in one file), directives with or without colon (`{title Foo}`) |

Not shown (kept in the file, used by ChordPro's own PDF output): fonts, sizes and colours, page and column control,
images and delegated environments (ABC, LilyPond, SVG). Dissonance's own additions, ignored by other tools:
`{x_instrument: guitar|ukulele}` and `{x_autoscroll: n}`; older files may have `{x_transpose: n}` – still read,
written as `{transpose: n}` the next time the key is remembered.

**Chord diagrams from ChordPro.** `chords.json` holds the guitar and ukulele chord tables of the ChordPro reference
implementation (by Johan Vromans, [Artistic License 2.0](https://github.com/ChordPro/chordpro/blob/master/LICENSE),
compatible with the GPL). It is generated, not edited:

```bash
python3 tools/chordpro_chords.py            # latest ChordPro release -> chords.json (commit the diff)
python3 tools/chordpro_chords.py --check    # only check whether a newer release changed anything
```

The app checks every shape when it loads the table and skips the few that do not fit their name (e.g. `A#7`, stored
at the wrong fret in ChordPro 6.101); its own fingering is used for those.
