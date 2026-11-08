# Data, backup and updating

[← Documentation](index.md)

Everything lives in `SONG_DIR`:

| File | Content |
|---|---|
| `Artist - Title.cho` | The songs (plain text, the source of truth) |
| `.liederbuch.db` | SQLite: version history, songbooks, users, sessions, tempos, favorites |
| `.papierkorb/` | Deleted and renamed songs with a timestamp (never emptied automatically) |

Back up the whole folder. Losing the database loses history, songbooks and users, never the songs. Files added,
changed or removed outside the app (e.g. over a network share) are picked up and recorded in the history.

**Updating**: `docker compose pull && docker compose up -d` (without Docker: replace the code and restart). The database is upgraded automatically on the first
start; back up the folder before you update. The browser loads the new interface on the next visit (installed apps:
close and reopen once).
