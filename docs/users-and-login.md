# Single-user or multi-user, login and roles

[← Documentation](index.md)

## Single-user or multi-user

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


## Login (optional, OpenID Connect)

Without `OIDC_ISSUER` there is no login and everybody may edit. With it, Dissonance uses your identity provider
(authorization code flow with PKCE):

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
