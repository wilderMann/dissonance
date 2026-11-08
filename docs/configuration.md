# Configuration

[← Documentation](index.md)

All settings are environment variables. The login settings (`OIDC_…`) are in [users and login](users-and-login.md).

| Variable | Default | Meaning |
|---|---|---|
| `SONG_DIR` | `/songs` | Folder with the songs (`.cho` files) and the app's database |
| `PORT` | `8080` | Port to listen on |
| `PUBLIC_URL` | – | Address users open, e.g. `https://songs.example.com` (required for login) |
| `TZ` | – | Time zone, e.g. `Europe/Berlin` (timestamps of deleted songs) |
| `TRUSTED_PROXY` | – | Address of your reverse proxy (`*` if only the proxy can reach the app): the client address is then taken from `X-Forwarded-For` for the log |
| `THREADS` | `8` | Worker threads of the web server |
| `CONNECTION_LIMIT` | `200` | Open connections at most (more wait) |
| `SERVER` | `waitress` | `builtin` forces Python's built-in server (development) |
| `GUEST_ACCESS` | `on` | With login: `off` shows people who are not signed in nothing but the sign-in page (share links and campfire mode still work). Use it when the server is reachable from the internet – lyrics are usually copyrighted |
| `REQUIRE_DB` | `off` | `on` once the database exists: the app never creates a new one – it refuses to start, and `/healthz` reports 503, when `SONG_DIR/.liederbuch.db` is missing. Protects you when the song folder (network share, ZFS dataset, USB disk) is not mounted: otherwise the app would start with an empty database and show no songs |

The default lifetime of share links is set in the app (Server settings, admins only).
