"""App with login against the fake OpenID provider from the unit tests; who logs in comes from WHO_FILE (JSON claims).
Started by run.py for test_login.py (env SONG_DIR, PORT, WHO_FILE)."""
import json
import os
import sys
from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
import test_ug2chordpro as t  # noqa: E402
import app  # noqa: E402
import auth  # noqa: E402

WHO = os.environ.get("WHO_FILE", os.path.join(os.environ["SONG_DIR"], ".who.json"))


class FileKeycloak(t.FakeKeycloak):
    @property
    def next(self):
        with open(WHO) as f:
            return json.load(f)

    @next.setter
    def next(self, v):
        pass


kc = FileKeycloak()
port = int(os.environ["PORT"])
app.SONG_DIR, app._db = Path(os.environ["SONG_DIR"]), None
app.PUBLIC_URL = f"http://localhost:{port}"
app.OIDC = auth.OIDC(auth.Config(issuer=kc.base, client_id="dissonance", client_secret="geheim", provider_name="Testcloak"),
                     app.PUBLIC_URL + "/auth/callback")
app.serve(port, "127.0.0.1")
