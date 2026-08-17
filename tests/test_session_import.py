"""Offline tests for browser cookie filtering and session path discovery."""

import sqlite3
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = PROJECT_ROOT / "local" / "test_artifacts" / "session_import"


class TestFirefoxCookieImport:
    # Legacy Firefox schemas include exact Instagram hosts without suffix lookalikes
    def test_fallback_query_rejects_lookalike_domains(self, im_module):
        ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ARTIFACT_ROOT) as directory_name:
            cookie_path = Path(directory_name) / "cookies.sqlite"
            with sqlite3.connect(cookie_path) as connection:
                connection.execute("CREATE TABLE moz_cookies (host TEXT, name TEXT, value TEXT)")
                connection.executemany("INSERT INTO moz_cookies VALUES (?, ?, ?)", [("instagram.com", "sessionid", "root"), (".instagram.com", "csrftoken", "subdomain"), ("notinstagram.com", "attacker", "suffix"), ("instagram.com.evil.example", "attacker2", "prefix"), ("evilinstagram.com", "attacker3", "lookalike")])

            cookies = im_module.get_firefox_cookie_dict(str(cookie_path))

        assert cookies == {"sessionid": "root", "csrftoken": "subdomain"}


class TestSessionPaths:
    # Unix session discovery includes Instaloader's canonical path plus both legacy locations
    def test_unix_candidates_include_canonical_and_legacy_paths(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "system", lambda: "Darwin")

        candidates = im_module.get_session_file_candidates("Session.User")

        assert candidates[0].endswith("/.config/instaloader/session-session.user")
        assert any(path.endswith("/session.user.session") for path in candidates)
        assert candidates[-1].endswith("/.instaloader/session-session.user")
