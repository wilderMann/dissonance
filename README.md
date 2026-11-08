# Dissonance

**A self-hosted online songbook for playing guitar or ukulele with friends** – at the campfire, in a rehearsal room or
on the couch. Songs are stored as plain [ChordPro](https://www.chordpro.org/) files, shown with the chords above the
lyrics, scroll by themselves while you play, and can be collected into songbooks and printed as a folded A5 booklet.

| Play mode (dark) | Editor |
|---|---|
| ![Play mode with chord diagrams](docs/screenshots/play-desktop-dark.png) | ![Editor with live preview and insert buttons](docs/screenshots/editor-dark.png) |
| **Songbook** | **A5 booklet print** |
| ![Songbook](docs/screenshots/songbook.png) | ![Booklet sheet](docs/screenshots/booklet.png) |

<p align="center"><img src="docs/screenshots/phone-list.png" width="260" alt="Song list on a phone">
<img src="docs/screenshots/phone-play.png" width="260" alt="Play mode on a phone"></p>

## Why Dissonance?

- **Your songs, your server.** Songs are ordinary `.cho` text files in one folder – readable without the app, easy to back
  up, sync or edit with any editor. No account at a chord site, no ads, no tracking.
- **Made for playing, not for browsing.** Big, readable chords, auto-scroll with a tempo per song and device, the screen
  stays on, works offline once loaded, installable as an app on phones and tablets.
- **From the internet to your songbook in seconds.** Paste a link from Ultimate Guitar or Ukulele-Tabs.com, upload ChordPro
  files or paste "chords over lyrics" text – it is converted to clean ChordPro.
- **Songbooks you can print.** Pick songs, order them, print them on A4 or as an A5 booklet (correct page order for
  double-sided printing and folding), export as ChordPro or ZIP.
- **Share with friends.** Optional login through your own identity provider (Keycloak, Authentik, Authelia, …):
  guests read public songs, users keep public or private songs and songbooks, admins manage everything.
- **Tiny.** Python with one dependency (the Waitress web server), one HTML page, no build step, no database server –
  a single container.

## Features

**The song list**
- Sort by title, artist, last change or owner; letter headings and a **letter index on the right edge**, spread over
  the screen height (tap or drag to jump, big letter next to the finger; the current section is marked while
  scrolling; owner sort: initials of the owners). Search by title and artist, favorites filter.

**Playing**
- Chords above the lyrics, sections (verse, chorus, bridge, tab), comments; long lines wrap together with their chords.
- Auto-scroll with tempo 1–40, saved per song, per user and per device type (phone / tablet / PC); tap the song to pause.
- Transpose for display (♯/♭ spelling follows the key), font size, chords on/off, full screen.
- **German chord names** (H, B = B♭) or international (B, B♭) – each user picks in the settings (saved in the account,
  for guests in the browser); admins set the default for everybody in the Server settings. Applies to the song, grids,
  diagrams, the key, lists and the tuner. The files always keep international names, as ChordPro expects; an `H` in
  a file is read as B.
- **Chord diagrams** for guitar or ukulele – above the song or in a column next to it that stays visible while
  scrolling, with finger numbers. Fingerings come from [ChordPro](https://www.chordpro.org)'s chord tables (≈ 1,150
  guitar and 220 ukulele chord names); anything not in there from movable barre shapes and a search for the easiest
  grip. `{define}` lines in a song take precedence.
- **Favorites**: tap ♡ in the list or in a song, filter the list with ♥. Without login there is one shared list for the
  server; with login every user has their own, and guests keep theirs in the browser (moved to the account when they
  sign in).
- Keyboard and Bluetooth page turners: space = play/pause, arrow keys / page up/down = turn the page.
- The back arrow and the title stay at the top while you scroll; the end of the song never hides behind the controls.
- **Tuner** in the browser (👤 or ⚙ menu at the top right → Tuner): guitar (standard, drop D) and ukulele (GCEA, low G) – it
  detects the string you pluck, or tap a string to lock it and hear its note; adjustable A4. Uses the microphone,
  needs HTTPS.
- Keeps the screen awake (Screen Wake Lock, with a fallback for older browsers).

**Editing**
- ChordPro editor with live preview, visible spaces/line ends (toggle), transpose the text itself.
- Insert buttons for title, artist, key, capo, verse/chorus/bridge/tab (wrap the selected lines), comments, and one
  button per chord used in the song.
- Mark a song as written for guitar or ukulele.
- **Version history** for every song (editor → **⋯** → History): see what changed (line diff), compare with now,
  restore any version. Deleted songs can be restored as well.

**Importing**
- Links or saved pages from **Ultimate Guitar** (chords and tabs) and **Ukulele-Tabs.com**.
- **ChordPro files** (`.cho`, `.chordpro`, `.chopro`, `.crd`, `.pro`, `.txt`), several songs per file (`{new_song}`),
  UTF-8 or Windows-1252.
- Plain "chords over lyrics" text, with sections like `[Chorus]` recognised.
- German chord sheets (with H chords) are recognised and converted to international names (H → B, B → B♭); the
  notation can be switched per song before saving.
- Put the imported songs straight into a songbook; under "More options": transpose, ♯/♭ spelling, instrument, apply the capo.

**Songbooks and printing**
- Any number of songbooks; a song can be in several. Play a songbook in order with "next song".
- **Campfire mode** (with login; songbook → ⋯ → Campfire mode): open a songbook to *everybody* for 1 day … 3 weeks – at the
  plain app address, without login and without a link, also with `GUEST_ACCESS=off` (scout camp: everybody opens
  the site and lands in the songbook; with several active songbooks a short list appears). Shows what a share link
  shows (public songs + the owner's own songs), read-only, no version history; ends by itself or with "End".
  Owners and admins switch it on; the default duration is an admin setting (Server settings, 7 days out of the box).
- The songbook toolbar keeps Play, Random and Sort; everything else is in the **⋯** menu: Print / download (one dialog:
  print or PDF, one `.cho` file, ZIP of single files), share, campfire mode, visibility, collaborators, rename, delete.
- 🎲 **Random** opens a random song of the songbook.
- **⇅ Sort** in a songbook: sort by title, artist, owner or key in one tap, or drag songs by their handle ⠿ (mouse,
  touch; arrow keys on the handle); ✕ takes a song out of the book. Outside sort mode the list stays clean.
- Print view: cover, table of contents, one song per page or continuous, two columns, font size, chords on/off.
- **A5 booklet**: pages laid out on A4 landscape in booklet order, page numbers and a table of contents with real page
  numbers, songs of two pages start on a left page so you never turn pages mid-song, option for printers that flip on
  the long edge.
- Export a songbook as one ChordPro file or as a ZIP of numbered `.cho` files.
- **Share a songbook** (with login; songbook → ⋯ → Share) with a link – also a private one. Whoever has the link can view, play, print and
  download it without an account; "New link" replaces it, "Stop sharing" switches it off. Private songs of other
  people in the book stay hidden. Links expire: choose 1 day … 1 year or unlimited when sharing (admins set the
  default in the Server settings, 30 days out of the box); an expired link can be extended and then works again.

**Working together** (with login)
- **Bulk edit** (☑ Select in the song list): pick songs – or "all shown" after searching/filtering – and change
  key, instrument, transposition (the song's `{transpose}`, the text stays as it is), songbook (add/remove) or delete
  them (to the trash); with login also visibility and collaborators, and admins can set a new **owner** (e.g. to hand
  songs from before the login to their users). Rights are checked per song like single edits (collaborators may change
  key/instrument/transposition, only owners and admins visibility, collaborators and deleting); songs that can't be
  changed are skipped and listed. Text changes become one "bulk edit" version in the history. Bulk edit works without
  login too.
- Every song shows who owns it – by **username** (👤 andi; also on your own songs), never the full name, and only to signed-in users.
- **⧉ Own version** (song → **⋯**): copies a song you can see into your own song – someone else's
  becomes `Artist - Title (nick).cho`, your own `… (2)` – and opens it in the editor; same text and visibility, the
  original stays untouched, the history notes "Copy of “Title” (owner)". Such versions keep their name when you
  edit or restore them (as long as title and artist stay the same).
- **The same song more than once**: if someone creates a song whose name another user already has, it becomes their
  own version (file `Artist - Title (nick).cho`); the list shows both with the same title, told apart by the owner.
  The "already exists" dialog only appears for songs you may edit (your own or shared with you).
- **Collaborate on a song or a songbook** (editor → ⋯ → Collaborators, or songbook → ⋯ → Collaborators): pick users, or allow every signed-in
  user. Collaborators can edit the song – or the songbook's song list and the owner's songs in it – even when it is
  private, and restore old versions. Deleting, visibility, share links and the collaborator list stay with the owner
  (and admins). Songs you work on are marked "👥 shared work".
- The history shows who saved each version (to the people working on the song).
- **Users in the Server settings** (admins): tap a user to see their songs and songbooks (private ones too) and their
  activity – sign-ins, saved songs, songbooks created/renamed/changed/deleted, songs added or removed, visibility,
  owner and collaborator changes, share links and campfire mode (newest first, the last 500 entries). Deleting a user
  also deletes their activity record.
- **Importing a song that already exists** shows what differs (line diff) and lets you take the new version (it
  becomes the next version of the existing song, the old one stays in the history), keep the existing one, keep both
  ("… (2)") or rename the new one.

**Everything else**
- Works on phones, tablets and desktops; light and dark theme; English and German interface.
- Installable as an app (PWA) and usable offline for songs you have opened or saved for offline use.
- Optional users and roles via OpenID Connect (see below) – see "Single-user or multi-user" for what changes.

## Quick start

You need Python 3.11 or newer – nothing else.

```bash
git clone https://github.com/wilderMann/dissonance.git && cd dissonance
mkdir songs
SONG_DIR=./songs python3 app.py
```

Open <http://localhost:8080>, click **＋** and choose *New song* to write one or *Import* to bring songs in. Without a login configured,
everybody who can reach the app may edit – fine for your own computer or a trusted home network.

## Installation

### Docker / Podman

Ready-made images for amd64 and arm64 (Raspberry Pi 4/5) are published at
`ghcr.io/wildermann/dissonance`. Get the example [`docker-compose.yml`](docker-compose.yml) and start it:

```bash
mkdir dissonance && cd dissonance && mkdir songs
curl -O https://raw.githubusercontent.com/wilderMann/dissonance/main/docker-compose.yml
docker compose up -d
```

It runs the image read-only and without capabilities as an unprivileged user and stores everything in `./songs`.
The container listens on port 8080 and has a health check at `/healthz`.

Image tags: `1.0.0` (exactly this release), `1.0` (bug fixes only), `1` (all 1.x releases – recommended) and `latest`.
A new major version (`2`) may need changes to your setup; read its notes in the [changelog](CHANGELOG.md) first.
To build the image yourself instead, clone the repository and replace `image:` with `build: .` in the compose file.

The songs folder must be writable by the container user (uid 1000 in the image), e.g. `sudo chown 1000 songs`.
Existing `.cho` files you copy into the folder are picked up automatically.

After the first start, set `REQUIRE_DB=on` (see Configuration) if the songs folder lives on a network share or
another file system that might not be mounted when the container starts – the app then refuses to start instead of
showing an empty songbook.

### Behind a reverse proxy (recommended)

Put Dissonance behind your reverse proxy (Traefik, Caddy, nginx, …) with **HTTPS**. Browsers only allow installing the
app, keeping the screen awake and secure login cookies on HTTPS. Example for Caddy:

```
songs.example.com {
    reverse_proxy dissonance:8080
}
```

Set `PUBLIC_URL=https://songs.example.com` so redirects and cookies use the right address. If the app should only be
reachable from your home network or VPN, restrict it at the proxy (IP allow list).

### Without Docker

Copy the repository to the server, install the web server with `pip install --require-hashes -r requirements.txt`
(Waitress, pure Python) and run `python3 -I app.py` as a service (systemd, …) with the environment variables below.
Without Waitress the app falls back to Python's built-in server – fine for trying it out at home, but not hardened
against slow or hostile clients, so don't put that on the internet.

## Configuration

All settings are environment variables.

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

### Single-user or multi-user

Dissonance runs in one of two modes, chosen by one setting: **without `OIDC_ISSUER` it is a single-user server,
with it a multi-user server.** Songs, songbooks and history are the same in both; only the rights and the features
that need several people change.

| | Single-user (no login) | Multi-user (login) |
|---|---|---|
| Who may do what | everybody who can reach the server may do everything | guests, users and admins (see Roles below) |
| Playing, editing, importing, songbooks, printing, history, bulk edit | ✓ | ✓ |
| Public / private songs and songbooks | – (everything is visible) | ✓ |
| Share links, campfire mode, collaborators | – | ✓ |
| Owners | – (new songs have none) | ✓ (shown by username) |
| Favorites | one list for the whole server | per user (guests: in the browser) |
| Chord-name notation (B or H) | per browser | per user (default: admin setting) |
| Server settings, user pages with activity | – | admins |

Features that only make sense with several people do not show up at all on a single-user server.

**Switching from single-user to multi-user** (setting up the login later): everything created so far has no owner.
It stays visible to everybody who may see public things and only admins may change it. Admins hand such songs to
their users with **bulk edit → Owner** (☑ Select, pick the songs, choose the new owner). The shared favorites list
of the single-user server is kept in the database but not shown to anybody.

> ⚠️ **Switching from multi-user back to single-user makes everything public.** Without login everybody who can reach
> the server is admin: **every private song and songbook can be read, changed and deleted by anyone**. Only do this on
> a server that nobody else can reach. Owners, visibility, collaborators and personal favorites stay in the database
> and are used again as soon as the login is switched back on; share links and campfire mode stop working while it
> is off.

Ownership is tied to the user ID (`sub`) from your identity provider. When you move to another provider or realm,
users get new IDs and show up as new, empty accounts – give their songs back with bulk edit → Owner (or "Delete
user → transfer to me" on the old account).

### Login (optional, OpenID Connect)

Without `OIDC_ISSUER` there is no login and everybody may edit. With it, Dissonance uses your identity provider
(authorization code flow with PKCE). The options follow the naming of Headscale's `oidc` block:

| Variable | Default | Meaning |
|---|---|---|
| `OIDC_ISSUER` | – (login off) | Issuer URL of your provider; its `/.well-known/openid-configuration` is read |
| `OIDC_CLIENT_ID` | `dissonance` | Client ID |
| `OIDC_CLIENT_SECRET_PATH` | – | File containing only the client secret (preferred) |
| `OIDC_CLIENT_SECRET` | – | The secret directly. Neither set = public client (PKCE only) |
| `OIDC_SCOPE` | `openid profile email` | Requested scopes (space or comma separated) |
| `OIDC_PKCE` | `true` | Use PKCE (S256) |
| `OIDC_TOKEN_AUTH` | `basic` | Send the secret as HTTP Basic auth (`basic`) or in the form (`post`) |
| `OIDC_EXTRA_PARAMS` | – | Extra parameters for the login page, URL-encoded, e.g. `prompt=login` |
| `OIDC_GROUPS_CLAIM` | `groups` | Claim with the user's groups or roles; dotted paths allowed (`realm_access.roles`) |
| `OIDC_ADMIN_GROUPS` | `admin` | Groups/roles that make a user an admin of the app (comma list) |
| `OIDC_ALLOWED_GROUPS` | – (everybody) | Only members of these groups may log in |
| `OIDC_ALLOWED_DOMAINS` | – | Only e-mail addresses of these domains may log in |
| `OIDC_ALLOWED_USERS` | – | Only these e-mail addresses / usernames may log in |
| `OIDC_USERNAME_CLAIM` | `preferred_username` | Claim used as username (falls back to `email`, `sub`) |
| `OIDC_PROVIDER_NAME` | – | Shown on the sign-in button ("Sign in with …") |
| `OIDC_ACCOUNT_URL` | – | Your provider's self-service page (password, profile), linked in the user menu |
| `OIDC_TIMEOUT` | `10` | Seconds for requests to the provider |

**At your provider**, create an OpenID Connect client with
- redirect URI `https://songs.example.com/auth/callback`,
- post-logout redirect URI `https://songs.example.com/`,
- a groups (or roles) claim if you want admins.

Provider notes:
- **Keycloak** – client authentication on, standard flow only, PKCE method S256. Add a "Group Membership" mapper
  (claim `groups`, full group path off), or use realm roles with `OIDC_GROUPS_CLAIM=realm_access.roles`.
  Account page: `<issuer>/account/`.
- **Authentik** – OAuth2/OpenID provider; `OIDC_ISSUER=https://auth.example.com/application/o/<app-slug>/`. The default
  `profile` scope contains `groups`.
- **Authelia** – add the client with `scopes: [openid, profile, email, groups]` and set `OIDC_SCOPE=openid profile email groups`.
- **Others** (Zitadel, Kanidm, Pocket ID, …) – set `OIDC_GROUPS_CLAIM` to the claim your provider uses.

Docker example with a secret file:

```yaml
    environment:
      - PUBLIC_URL=https://songs.example.com
      - OIDC_ISSUER=https://auth.example.com/realms/example
      - OIDC_CLIENT_ID=dissonance
      - OIDC_CLIENT_SECRET_PATH=/run/secrets/oidc
      - OIDC_ADMIN_GROUPS=admin
    volumes:
      - ./songs:/songs
      - ./oidc-secret:/run/secrets/oidc:ro   # only the secret, readable by the container user
```

**Roles**

| | Guest | User | Admin |
|---|---|---|---|
| See, play, print, download public songs and songbooks | ✓ (not with `GUEST_ACCESS=off`) | ✓ | ✓ |
| Create and import songs and songbooks (public or private) | | ✓ | ✓ |
| Edit | | own items + where they collaborate | everything |
| Delete, change visibility, share link, collaborators | | own items | everything |
| See private items | | own + where they collaborate | all |
| Open a shared songbook (link) | ✓ | ✓ | ✓ |
| Favorites | in the browser | own list | own list |
| Server settings (defaults, users, activity) | | | ✓ |
| Change the owner of songs (bulk edit) | | | ✓ |

New songs and songbooks are public unless marked private. A song name someone else already uses gets a suffix
(" (2)") instead of overwriting. Songs that existed before login was switched on (or that were copied into the folder)
have no owner: they are public and only admins can edit them (admins give them an owner with bulk edit → Owner). Group changes take effect at the next login; sessions
last 30 days. Deleting a user in the app removes them from Dissonance (their songs are transferred to you or deleted),
but they can log in again – lock people out at the identity provider.

## Using it

- **Songs** – the list with search; ♡ marks a favorite, ♥ next to the sort order shows only favorites; **＋** opens *New
  song* and *Import*.
- **Play mode** – open a song; the bar at the bottom starts/stops auto-scroll and sets the tempo. **⋯** opens font
  size, transpose, chords on/off, chord diagrams (off / above / right), guitar or ukulele, full screen and "Remember
  key" (stores the transposition in the song). The tempo is saved automatically. The song's own **⋯** (top right)
  adds it to songbooks, makes your own version, prints it or downloads the `.cho` file.
- **Edit** – "✎ Edit" in a song: ChordPro text on the left, preview on the right, insert buttons above. The bar has
  Save, Cancel and transpose; its **⋯** holds visibility, instrument, whitespace markers, "History" (shows and restores
  earlier versions), collaborators and "Delete" (moves the song to the trash, restorable under "Restore deleted songs").
- **Songbooks** – create one, add songs, order them (⇅ Sort), then **Play** (with "next song"); **⋯** → *Print /
  download* for print/PDF, one `.cho` file or a ZIP. In a song, **⋯** → *Add to songbooks*.
- **Booklet** – in the print view choose "A5 booklet", print on A4 landscape, double-sided (flip on the short edge,
  scale 100 %, no headers/footers), fold the stack in the middle.
- **On the phone** – open the site and choose "Install app" / "Add to Home screen" in the browser menu. "Save offline"
  in the song list stores all songs on the device.
- **Settings** – language, theme, chord diagrams, font size, default tempo, editor whitespace (stored per browser).
  The menu at the top right holds settings, the tuner and the light/dark switch – 👤 with your name when signed in
  (plus account page, server settings for admins and sign out), ⚙ without login or as a guest.

## ChordPro support

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

## Data and backup

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

## Security notes

- Without login everybody who can reach the app can change and delete songs – keep it on a trusted network or put
  authentication in front of it.
- With login: sessions are random tokens in an HttpOnly, Secure, SameSite=Lax cookie, stored hashed; requests that
  change data are refused from foreign origins; private songs of others are invisible (404).
- Share links are random 144-bit tokens; anyone who has one can read that songbook (and the owner's songs in it), so
  treat them like a password and use "New link" / "Stop sharing" when one got too far. They expire after the chosen
  lifetime (default 30 days, set by admins).
- The web server is [Waitress](https://docs.pylonsproject.org/projects/waitress/): it buffers each request completely
  before the app sees it (slow clients only hold a socket, not a worker), limits header size (64 KB), body size
  (20 MB), connections and idle time (30 s). With `PUBLIC_URL` on https the app sends HSTS.
- `OIDC_ALLOWED_GROUPS` is checked at sign-in. Someone removed from the group keeps an existing session until it
  expires (30 days) – delete them under "Users" to end it right away.
- Imports fetch pages only from `https://*.ultimate-guitar.com` and `https://*.ukulele-tabs.com`, and only for
  signed-in users when login is enabled.
- The container runs read-only, without capabilities, as an unprivileged user.

## Development

```
app.py            API (songs, history, songbooks, users); WSGI app for Waitress + built-in fallback server
requirements.txt  Waitress, pinned with its hash
VERSION           the release version (tags are v + this); CHANGELOG.md – what changed per release
.github/          release workflow: tests, Docker image to ghcr.io, GitHub release
auth.py           OpenID Connect login
i18n.py           server messages in English and German
ug2chordpro.py    converter: Ultimate Guitar, Ukulele-Tabs.com, chords-over-lyrics text → ChordPro
index.html        the whole interface (HTML, CSS, JavaScript; no build step)
sw.js             service worker (offline cache)
chords.json       chord diagrams from ChordPro (generated by tools/chordpro_chords.py)
tools/            chordpro_chords.py – updates chords.json; screenshots.py – the README screenshots;
                  docx2chordpro.py – Word song collection to ChordPro (needs Pillow)
tests/browser/    browser tests
```

**Languages**: German texts are the keys (`$t("…")` in `index.html`, `i18n.py` on the server) with an English table.
To add or change a text, write it in German and add the English version; a unit test checks the server side.

**Tests**

```bash
python3 -m unittest test_ug2chordpro          # converter, API, login/roles (fake OpenID provider), languages
TEST_SERVER=builtin python3 -m unittest test_ug2chordpro   # the same against the built-in fallback server
python3 tests/browser/run.py                  # browser tests, needs Firefox (headless, driven over Marionette)
python3 tests/browser/run.py test_play --width 390 -v
```

The browser tests start a fresh app with invented test songs for each test (with a fake OpenID provider where login
is needed) and cover play mode, songbooks, history, printing and the booklet (PDF), chord diagrams, the editor, import,
PWA/keep-awake, offline use, languages, login, roles, sharing, campfire mode, collaboration, bulk edit and the
single-user mode, at phone, tablet and desktop widths (list in `tests/browser/run.py`). Screenshots and PDFs go to `tests/browser/out/`. Some converter tests need saved pages from
the supported sites in `examples/`; they are not part of the repository and those tests are skipped without them.

**Releases**: set the new version in `VERSION`, add a section to `CHANGELOG.md`, commit, then tag and push
(`git tag v1.2.3 && git push origin v1.2.3`). The release workflow checks that tag and `VERSION` match, runs the unit
tests, publishes the image for amd64 and arm64 to `ghcr.io` and creates the GitHub release with the changelog section.
The version is shown in the settings and names the offline cache, so browsers pick up a new release by themselves.

**Contributing**: issues and pull requests are welcome. Please keep it dependency-free (standard library + Waitress, no
build step), add the English text for every new German one, and run the unit and browser tests.

## License

[GPL-3.0](LICENSE). `chords.json` contains chord definitions from [ChordPro](https://www.chordpro.org)
(Artistic License 2.0).
