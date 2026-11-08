"""OpenID Connect login (authorization code flow + PKCE), stdlib only – works with any OIDC provider
(Keycloak, Authentik, Authelia, Zitadel, Kanidm, Pocket ID, Google, Entra ID …).

Configuration comes from environment variables (see Config.from_env / docs/users-and-login.md).
The ID token comes straight from the token endpoint over TLS, so – as OIDC Core 3.1.3.7 allows – its issuer is
trusted via the TLS connection instead of verifying the signature; iss, aud/azp, exp and nonce are still checked.
"""
import base64
import hashlib
import json
import os
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from i18n import Message

PENDING_TTL = 600  # s a login may take on the provider's page


class AuthError(Message):
    pass


def _b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _list(value):
    return [x.strip() for x in (value or "").replace(",", " ").split() if x.strip()]


def jwt_claims(token):
    try:
        seg = token.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(seg + "=" * (-len(seg) % 4)))
    except (IndexError, ValueError) as e:
        raise AuthError("Ungültiges ID-Token.") from e


def claim(claims, path):
    """Dotted claim path: "groups", "realm_access.roles", "resource_access.dissonance.roles"."""
    v = claims
    for part in path.split("."):
        if not isinstance(v, dict):
            return None
        v = v.get(part)
    return v


@dataclass
class Config:
    issuer: str
    client_id: str
    client_secret: str = ""            # empty = public client (PKCE only)
    scope: list = field(default_factory=lambda: ["openid", "profile", "email"])
    pkce: bool = True
    token_auth: str = "basic"          # client_secret_basic (OAuth default) or "post"
    extra_params: dict = field(default_factory=dict)
    groups_claim: str = "groups"
    admin_groups: list = field(default_factory=lambda: ["admin"])
    allowed_groups: list = field(default_factory=list)   # empty = everybody may log in
    allowed_domains: list = field(default_factory=list)
    allowed_users: list = field(default_factory=list)
    username_claim: str = "preferred_username"
    provider_name: str = ""            # shown on the login button, e.g. "Keycloak"
    account_url: str = ""              # provider's self-service page (password, profile), linked in the user menu
    timeout: int = 10

    @classmethod
    def from_env(cls, env=os.environ):
        """None when OIDC_ISSUER is not set (login disabled)."""
        issuer = env.get("OIDC_ISSUER", "").strip()
        if not issuer:
            return None
        secret_path = env.get("OIDC_CLIENT_SECRET_PATH") or env.get("OIDC_CLIENT_SECRET_FILE") or ""
        if secret_path:
            with open(secret_path, encoding="utf-8") as f:
                secret = f.read().strip()
        else:
            secret = env.get("OIDC_CLIENT_SECRET", "")
        c = cls(issuer=issuer, client_id=env.get("OIDC_CLIENT_ID", "dissonance"), client_secret=secret)
        if env.get("OIDC_SCOPE"):
            c.scope = _list(env["OIDC_SCOPE"])
        if "openid" not in c.scope:
            c.scope.insert(0, "openid")
        c.pkce = env.get("OIDC_PKCE", "true").lower() not in ("0", "false", "no", "off")
        c.token_auth = "post" if env.get("OIDC_TOKEN_AUTH", "basic").lower() == "post" else "basic"
        c.extra_params = dict(urllib.parse.parse_qsl(env.get("OIDC_EXTRA_PARAMS", "")))
        c.groups_claim = env.get("OIDC_GROUPS_CLAIM", "groups")
        if "OIDC_ADMIN_GROUPS" in env or "OIDC_ADMIN_GROUP" in env:
            c.admin_groups = _list(env.get("OIDC_ADMIN_GROUPS") or env.get("OIDC_ADMIN_GROUP"))
        c.allowed_groups = _list(env.get("OIDC_ALLOWED_GROUPS"))
        c.allowed_domains = [d.lower().lstrip("@") for d in _list(env.get("OIDC_ALLOWED_DOMAINS"))]
        c.allowed_users = [u.lower() for u in _list(env.get("OIDC_ALLOWED_USERS"))]
        c.username_claim = env.get("OIDC_USERNAME_CLAIM", "preferred_username")
        c.provider_name = env.get("OIDC_PROVIDER_NAME", "")
        c.account_url = env.get("OIDC_ACCOUNT_URL", "")
        c.timeout = int(env.get("OIDC_TIMEOUT", "10"))
        if not c.client_secret and not c.pkce:
            raise ValueError("OIDC: without a client secret PKCE must stay on (public client)")
        return c


def _in(groups, wanted):
    """Group names match with or without a leading "/" (Keycloak's full group path)."""
    have = {g.lstrip("/") for g in groups}
    return any(w.lstrip("/") in have for w in wanted)


class OIDC:
    def __init__(self, cfg, redirect_uri):
        self.cfg, self.redirect_uri = cfg, redirect_uri
        self.issuer = cfg.issuer.rstrip("/")
        self._config, self._config_at = None, 0
        self._pending, self._lock = {}, threading.Lock()

    def config(self):
        if not self._config or time.time() - self._config_at > 3600:
            url = self.issuer + "/.well-known/openid-configuration"
            try:
                with urllib.request.urlopen(url, timeout=self.cfg.timeout) as r:
                    cfg = json.load(r)
            except OSError as e:
                raise AuthError("Der Anmeldedienst ist nicht erreichbar ({err}).", err=e) from e
            if cfg.get("issuer", "").rstrip("/") != self.issuer:
                raise AuthError("Der Anmeldedienst meldet einen anderen Issuer als konfiguriert (OIDC_ISSUER).")
            self._config, self._config_at = cfg, time.time()
        return self._config

    def start(self, return_to):
        """URL of the provider's login page; state/nonce/PKCE verifier are kept here until the callback."""
        state, nonce, verifier = secrets.token_urlsafe(24), secrets.token_urlsafe(24), secrets.token_urlsafe(48)
        now = time.time()
        with self._lock:
            self._pending = {k: v for k, v in self._pending.items() if now - v[3] < PENDING_TTL}
            self._pending[state] = (nonce, verifier, return_to, now)
        q = {**self.cfg.extra_params, "response_type": "code", "client_id": self.cfg.client_id,
             "redirect_uri": self.redirect_uri, "scope": " ".join(self.cfg.scope), "state": state, "nonce": nonce}
        if self.cfg.pkce:
            q |= {"code_challenge": _b64url(hashlib.sha256(verifier.encode()).digest()), "code_challenge_method": "S256"}
        return self.config()["authorization_endpoint"] + "?" + urllib.parse.urlencode(q)

    def _post(self, url, form):
        headers = {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}
        if self.cfg.client_secret and self.cfg.token_auth == "basic":
            pair = urllib.parse.quote(self.cfg.client_id, safe="") + ":" + urllib.parse.quote(self.cfg.client_secret, safe="")
            headers["Authorization"] = "Basic " + base64.b64encode(pair.encode()).decode()
        elif self.cfg.client_secret:
            form["client_secret"] = self.cfg.client_secret
        req = urllib.request.Request(url, urllib.parse.urlencode(form).encode(), headers)
        try:
            with urllib.request.urlopen(req, timeout=self.cfg.timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            raise AuthError("Der Anmeldedienst hat die Anmeldung abgelehnt (HTTP {code}).", code=e.code) from e
        except OSError as e:
            raise AuthError("Der Anmeldedienst ist nicht erreichbar ({err}).", err=e) from e

    def _userinfo(self, access_token):
        url = self.config().get("userinfo_endpoint")
        if not url or not access_token:
            return {}
        req = urllib.request.Request(url, headers={"Authorization": "Bearer " + access_token, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.cfg.timeout) as r:
                return json.load(r)
        except (OSError, ValueError):
            return {}

    def finish(self, query):
        """Callback query -> (user dict, id_token, return_to). user: sub, username, name, email, groups, admin."""
        if "error" in query:
            raise AuthError("Anmeldung abgebrochen: {why}", why=query.get("error_description", query["error"]))
        with self._lock:
            pending = self._pending.pop(query.get("state", ""), None)
        if not pending or time.time() - pending[3] > PENDING_TTL:
            raise AuthError("Die Anmeldung ist abgelaufen – bitte nochmal versuchen.")
        nonce, verifier, return_to, _ = pending
        form = {"grant_type": "authorization_code", "code": query.get("code", ""), "redirect_uri": self.redirect_uri,
                "client_id": self.cfg.client_id}
        if self.cfg.pkce:
            form["code_verifier"] = verifier
        tokens = self._post(self.config()["token_endpoint"], form)
        id_token = tokens.get("id_token") or ""
        c = jwt_claims(id_token)
        aud = c.get("aud") if isinstance(c.get("aud"), list) else [c.get("aud")]
        if c.get("iss", "").rstrip("/") != self.issuer or self.cfg.client_id not in aud \
                or (c.get("azp") and c["azp"] != self.cfg.client_id):
            raise AuthError("ID-Token ist nicht für diese App ausgestellt.")
        if c.get("exp", 0) < time.time() - 60 or c.get("nonce") != nonce or not c.get("sub"):
            raise AuthError("ID-Token ist abgelaufen oder ungültig.")
        # some providers only put groups/email into the userinfo response
        if claim(c, self.cfg.groups_claim) is None or "email" not in c:
            info = self._userinfo(tokens.get("access_token"))
            if info.get("sub") == c["sub"]:
                c = {**info, **c}  # ID-token claims win, missing ones come from userinfo
        groups = claim(c, self.cfg.groups_claim) or []
        groups = [groups] if isinstance(groups, str) else [str(g) for g in groups]
        user = {"sub": c["sub"], "email": (c.get("email") or "").lower(), "groups": groups,
                "username": c.get(self.cfg.username_claim) or c.get("preferred_username") or c.get("email") or c["sub"],
                "admin": _in(groups, self.cfg.admin_groups)}
        user["name"] = c.get("name") or user["username"]
        try:
            self.check_allowed(user)
        except AuthError as e:
            e.denied, e.id_token = True, id_token  # the error page offers to sign out at the provider (other account)
            raise
        return user, id_token, return_to

    def check_allowed(self, u):
        """allowed_groups / allowed_domains / allowed_users: all lists that are set must match."""
        cfg = self.cfg
        if cfg.allowed_groups and not _in(u["groups"], cfg.allowed_groups):
            raise AuthError("Dein Konto ist für diese App nicht freigeschaltet (Gruppe fehlt).")
        if cfg.allowed_domains and u["email"].rpartition("@")[2] not in cfg.allowed_domains:
            raise AuthError("Dein Konto ist für diese App nicht freigeschaltet (E-Mail-Domain).")
        if cfg.allowed_users and u["email"] not in cfg.allowed_users and u["username"].lower() not in cfg.allowed_users:
            raise AuthError("Dein Konto ist für diese App nicht freigeschaltet.")

    def logout_url(self, id_token, after):
        end = self.config().get("end_session_endpoint")
        if not end:
            return after
        q = {"client_id": self.cfg.client_id, "post_logout_redirect_uri": after}
        if id_token:
            q["id_token_hint"] = id_token
        return end + "?" + urllib.parse.urlencode(q)
