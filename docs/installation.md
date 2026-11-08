# Installation

[← Documentation](index.md)

## Try it without Docker

You need Python 3.11 or newer – nothing else.

```bash
git clone https://github.com/wilderMann/dissonance.git && cd dissonance
mkdir songs
SONG_DIR=./songs python3 app.py
```

Open <http://localhost:8080>, click **＋** and choose *New song* to write one or *Import* to bring songs in. Without a login configured,
everybody who can reach the app may edit – fine for your own computer or a trusted home network.


## Docker details

The quick setup is in the [README](../README.md#deployment). Some more details:

- Image tags: `1.0.0` (exactly this release), `1.0` (bug fixes only), `1` (all 1.x releases – recommended) and
  `latest`. A new major version (`2`) may need changes to your setup; read its notes in the
  [changelog](../CHANGELOG.md) first.
- To build the image yourself, clone the repository and replace `image:` with `build: .` in the compose file.
- The songs folder must be writable by the user the container runs as – uid 1000 by default (`sudo chown 1000 songs`);
  set `user: "1001:1001"` (compose) or `--user 1001:1001` to use another one. Existing `.cho` files you copy into
  the folder are picked up automatically.
- After the first start, set `REQUIRE_DB=on` (see [Configuration](configuration.md)) if the songs folder lives on a
  network share or another file system that might not be mounted when the container starts – the app then refuses to
  start instead of showing an empty songbook.
- Podman works the same way (`podman compose`, or `podman run` with the options from the README).

## Behind a reverse proxy (recommended)

Put Dissonance behind your reverse proxy (Traefik, Caddy, nginx, …) with **HTTPS**. Browsers only allow installing the
app, keeping the screen awake and secure login cookies on HTTPS. Example for Caddy:

```
songs.example.com {
    reverse_proxy dissonance:8080
}
```

Set `PUBLIC_URL=https://songs.example.com` so redirects and cookies use the right address. If the app should only be
reachable from your home network or VPN, restrict it at the proxy (IP allow list).


## Without Docker (as a service)

Copy the repository to the server, install the web server with `pip install --require-hashes -r requirements.txt`
(Waitress, pure Python) and run `python3 -I app.py` as a service (systemd, …) with the environment variables from [Configuration](configuration.md).
Without Waitress the app falls back to Python's built-in server – fine for trying it out at home, but not hardened
against slow or hostile clients, so don't put that on the internet.
