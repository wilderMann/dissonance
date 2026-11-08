"""Run the browser tests: each test gets a fresh app (copy of fixtures/songs) on a free port.

usage: python3 tests/browser/run.py [name-filter ...] [--width 390] [--keep-shots]
Needs Firefox. Screenshots/PDFs go to tests/browser/out/ (git-ignored).
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
from browser import free_port  # noqa: E402

# test file, window widths, server kind
TESTS = [
    ("test_play.py", [390, 1400], "app"),
    ("test_books_history_print.py", [390, 1400], "app"),
    ("test_booklet.py", [390, 1400], "app"),
    ("test_chord_diagrams.py", [390, 1400], "app"),
    ("test_editor_whitespace.py", [390, 1400], "app"),
    ("test_editor_tools.py", [390, 1400], "app"),
    ("test_import.py", [1400], "app"),
    ("test_pwa_keepawake.py", [390], "app"),
    ("test_offline.py", [500], "app"),
    ("test_languages.py", [1400], "app"),
    ("test_login.py", [390, 1400], "login"),
    ("test_favorites.py", [390, 1400], "app"),
    ("test_favorites_login.py", [1400], "login"),
    ("test_play_layout.py", [390, 1400], "app"),
    ("test_tuner.py", [390, 1400], "app"),
    ("test_share.py", [390, 1400], "login"),
    ("test_collab.py", [390, 1400], "login"),
    ("test_chordpro.py", [390, 1400], "app"),
    ("test_notation.py", [390, 1400], "app"),
    ("test_guest_off.py", [390, 1400], "login-noguest"),
    ("test_bulk.py", [390, 1400], "login"),
    ("test_list_index.py", [390, 1400], "login"),
    ("test_campfire.py", [390, 1400], "login-noguest"),
    ("test_english.py", [390, 1400], "app"),
    ("test_single_user.py", [390, 1400], "app"),
    ("test_user_admin.py", [390, 1400], "login"),
    ("test_tablet_layout.py", [360, 375, 390, 412, 768, 810, 820, 1024, 1180], "login"),
]


def start_server(kind, songs, port):
    env = {**os.environ, "SONG_DIR": songs, "PORT": str(port)}
    if kind == "login-noguest":  # as "login", but GUEST_ACCESS=off (server on the internet)
        env["GUEST_ACCESS"], kind = "off", "login"
    if kind == "login":  # app with login against a fake OpenID provider (see test_ug2chordpro.FakeKeycloak)
        cmd = [sys.executable, os.path.join(HERE, "login_server.py")]
    else:
        cmd = [sys.executable, "-I", os.path.join(ROOT, "app.py")]
        env = {k: v for k, v in env.items() if not k.startswith("OIDC_")}
    proc = subprocess.Popen(cmd, env=env, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://localhost:{port}/healthz", timeout=1).read()
            return proc
        except OSError:
            time.sleep(0.1)
    proc.kill()
    raise RuntimeError("app did not start")


def main(argv):
    names = [a for a in argv if not a.startswith("--")]
    widths = [int(argv[i + 1]) for i, a in enumerate(argv) if a == "--width"]
    names = [n for n in names if not n.isdigit()]
    results = []
    for test, ws, kind in TESTS:
        if names and not any(n in test for n in names):
            continue
        for w in widths or ws:
            songs = tempfile.mkdtemp(prefix="diss-songs-")
            shutil.copytree(os.path.join(HERE, "fixtures", "songs"), songs, dirs_exist_ok=True)
            port = free_port()
            server = start_server(kind, songs, port)
            t0 = time.time()
            env = {**os.environ, "BASE": f"http://localhost:{port}", "W": str(w), "H": "900", "SERVER_PID": str(server.pid), "SONG_DIR": songs}
            try:
                p = subprocess.run([sys.executable, os.path.join(HERE, test)], env=env, capture_output=True, text=True, timeout=600)
                out = p.stdout + p.stderr
                status = "OK" if p.returncode == 0 else "FAILED"
            except subprocess.TimeoutExpired:
                out, status = "timeout", "FAILED"
            finally:
                server.terminate()
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.kill()
                shutil.rmtree(songs, ignore_errors=True)
            skipped = "SKIP " in out
            if status == "OK" and "PASS " not in out and not skipped:
                status, out = "FAILED", out + "\n(no checks ran)"
            results.append((test, w, "SKIPPED" if skipped and status == "OK" else status, time.time() - t0))
            print(f"{status:7} {test} @{w}px ({time.time() - t0:.0f}s)", flush=True)
            if status != "OK" or "-v" in argv:
                print("\n".join("    " + line for line in out.strip().splitlines() if not line.startswith("PASS")), flush=True)
    failed = [r for r in results if r[2] == "FAILED"]
    print(f"\n{len(results) - len(failed)}/{len(results)} runs passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
