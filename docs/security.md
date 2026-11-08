# Security notes

[← Documentation](index.md)

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
