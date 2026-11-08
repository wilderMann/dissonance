# Changelog

All notable changes. Versions follow [semantic versioning](https://semver.org/): a new major version means you may
have to change something in your setup (see the notes of that release).

## [1.0.0] – 2026-11-08

First public release.

- Songs as plain ChordPro files: chords above the lyrics, sections, grids, comments, chord diagrams for guitar and
  ukulele, transposition, German or international chord names.
- Play mode with auto-scroll (tempo saved per song and device type), keeps the screen awake, page-turner keys, tuner.
- Editor with live preview, insert buttons and version history; deleted songs can be restored.
- Import from Ultimate Guitar and Ukulele-Tabs.com links or saved pages, ChordPro files and "chords over lyrics" text.
- Songbooks: order, play in sequence, random song, print on A4 or as a folded A5 booklet, export as ChordPro or ZIP.
- Optional login via OpenID Connect: guests, users and admins, private songs and songbooks, share links, campfire
  mode, collaboration, own versions of songs, bulk edit with owner change, user pages with an activity record.
- Single-user mode without login.
- Installable as an app (PWA), offline use, English and German interface, light and dark theme.
- Docker image for amd64 and arm64 (`ghcr.io/wildermann/dissonance`); `REQUIRE_DB` protects against an unmounted
  songs folder.
