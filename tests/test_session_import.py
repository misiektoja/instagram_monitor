"""Offline tests for browser cookie filtering and session path discovery."""

import sqlite3
import tempfile
from pathlib import Path

import pytest


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


class TestFirefoxCookieFileResolution:
    # The dashboard may only import a database the tool itself enumerated
    def test_unlisted_path_is_refused(self, im_module, monkeypatch, tmp_path):
        offered = tmp_path / "profile" / "cookies.sqlite"
        offered.parent.mkdir()
        offered.write_bytes(b"")
        outsider = tmp_path / "elsewhere.sqlite"
        outsider.write_bytes(b"")
        monkeypatch.setattr(im_module, "list_firefox_profiles", lambda: [{"dir": "p.default", "name": "default", "path": str(offered)}])

        with pytest.raises(im_module.CookieImportError, match="Select a Firefox profile"):
            im_module.resolve_offered_firefox_cookiefile(str(outsider))

    # An enumerated profile path still resolves so the normal import keeps working
    def test_offered_path_is_accepted(self, im_module, monkeypatch, tmp_path):
        offered = tmp_path / "profile" / "cookies.sqlite"
        offered.parent.mkdir()
        offered.write_bytes(b"")
        monkeypatch.setattr(im_module, "list_firefox_profiles", lambda: [{"dir": "p.default", "name": "default", "path": str(offered)}])

        assert im_module.resolve_offered_firefox_cookiefile(str(offered)) == str(offered)

    # Sensitive absolute paths cannot be probed through the import endpoint
    @pytest.mark.parametrize("target", ["/etc/passwd", "~/.ssh/id_rsa", "../../etc/shadow", ""])
    def test_arbitrary_paths_are_refused(self, im_module, monkeypatch, target):
        monkeypatch.setattr(im_module, "list_firefox_profiles", lambda: [])

        with pytest.raises(im_module.CookieImportError):
            im_module.resolve_offered_firefox_cookiefile(target)


class TestSqliteImmutableUri:
    # A path cannot inject extra SQLite URI parameters and displace immutable=1
    @pytest.mark.parametrize("path,forbidden", [
        ("/tmp/db.sqlite?mode=rwc", "?mode=rwc"),
        ("/tmp/db.sqlite?vfs=unix-none", "?vfs="),
        ("/tmp/a#frag/db.sqlite", "#frag"),
    ])
    def test_uri_parameters_cannot_be_injected(self, im_module, path, forbidden):
        uri = im_module.sqlite_immutable_uri(path)

        assert forbidden not in uri
        assert uri.endswith("?immutable=1")
        assert uri.count("?") == 1

    # An ordinary path is preserved so real profiles still open
    def test_ordinary_path_is_preserved(self, im_module):
        assert im_module.sqlite_immutable_uri("/home/u/.mozilla/firefox/x.default/cookies.sqlite") == "file:/home/u/.mozilla/firefox/x.default/cookies.sqlite?immutable=1"

    # A missing cookie database is reported instead of raising an unhandled error
    def test_missing_cookie_file_is_reported(self, im_module, tmp_path):
        with pytest.raises(im_module.CookieImportError, match="not found"):
            im_module.get_firefox_cookie_dict(str(tmp_path / "absent.sqlite"))
