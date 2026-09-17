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


class TestInstagramSessionProbe:
    # Verifies a Chromium database answers the sign-in question from the cookie name alone, without decryption
    def test_a_chromium_profile_with_a_session_cookie_reads_as_signed_in(self, im_module):
        ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ARTIFACT_ROOT) as directory_name:
            cookie_path = Path(directory_name) / "Cookies"
            with sqlite3.connect(cookie_path) as connection:
                connection.execute("CREATE TABLE cookies (host_key TEXT, name TEXT, value TEXT, encrypted_value BLOB)")
                connection.execute("INSERT INTO cookies VALUES (?, ?, ?, ?)", (".instagram.com", "sessionid", "", b"v10encrypted"))

            assert im_module.cookie_file_has_instagram_session(str(cookie_path)) is True

    # Verifies a profile that only visited Instagram while logged out is reported as not signed in
    def test_a_profile_without_a_session_cookie_reads_as_signed_out(self, im_module):
        ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ARTIFACT_ROOT) as directory_name:
            cookie_path = Path(directory_name) / "Cookies"
            with sqlite3.connect(cookie_path) as connection:
                connection.execute("CREATE TABLE cookies (host_key TEXT, name TEXT, value TEXT)")
                connection.executemany("INSERT INTO cookies VALUES (?, ?, ?)", [(".instagram.com", "csrftoken", "x"), (".instagram.com", "mid", "y")])

            assert im_module.cookie_file_has_instagram_session(str(cookie_path)) is False

    # Verifies a lookalike domain cannot make a profile look signed in, matching the Firefox reader's own guard
    def test_a_lookalike_domain_does_not_read_as_signed_in(self, im_module):
        ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ARTIFACT_ROOT) as directory_name:
            cookie_path = Path(directory_name) / "Cookies"
            with sqlite3.connect(cookie_path) as connection:
                connection.execute("CREATE TABLE cookies (host_key TEXT, name TEXT, value TEXT)")
                connection.executemany("INSERT INTO cookies VALUES (?, ?, ?)", [("evilinstagram.com", "sessionid", "x"), ("instagram.com.evil.example", "sessionid", "y")])

            assert im_module.cookie_file_has_instagram_session(str(cookie_path)) is False

    # Verifies the Firefox schema is read through its own table and column names
    def test_a_firefox_profile_is_read_through_the_firefox_schema(self, im_module):
        ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ARTIFACT_ROOT) as directory_name:
            cookie_path = Path(directory_name) / "cookies.sqlite"
            with sqlite3.connect(cookie_path) as connection:
                connection.execute("CREATE TABLE moz_cookies (host TEXT, name TEXT, value TEXT)")
                connection.execute("INSERT INTO moz_cookies VALUES (?, ?, ?)", ("instagram.com", "sessionid", "x"))

            assert im_module.cookie_file_has_instagram_session(str(cookie_path), firefox=True) is True
            assert im_module.cookie_file_has_instagram_session(str(cookie_path)) is None, "the Chromium schema is absent, so the state is unknown rather than a guess"

    # Verifies an unreadable or missing database says nothing instead of claiming the profile is signed out
    @pytest.mark.parametrize("content", [None, b"not a database"])
    def test_an_unreadable_database_reports_an_unknown_state(self, im_module, content):
        ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ARTIFACT_ROOT) as directory_name:
            cookie_path = Path(directory_name) / "Cookies"
            if content is not None:
                cookie_path.write_bytes(content)

            assert im_module.cookie_file_has_instagram_session(str(cookie_path)) is None

    # Verifies an empty Firefox profile fails before a login attempt, so a wrong choice costs no Instagram request
    def test_an_empty_firefox_profile_fails_before_any_request(self, im_module, monkeypatch):
        ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ARTIFACT_ROOT) as directory_name:
            cookie_path = Path(directory_name) / "cookies.sqlite"
            with sqlite3.connect(cookie_path) as connection:
                connection.execute("CREATE TABLE moz_cookies (host TEXT, name TEXT, value TEXT)")
            monkeypatch.setattr(im_module, "list_firefox_profiles", lambda: [{"dir": "a.default", "name": "default", "path": str(cookie_path)}, {"dir": "b.work", "name": "work", "path": "/tmp/other"}])

            with pytest.raises(im_module.CookieImportError) as failure:
                im_module.get_firefox_cookie_dict(str(cookie_path))

        assert "No Instagram cookies found" in str(failure.value)
        assert "other profiles: work" in str(failure.value), "the failure names where else the session might be"


class TestProfileSelection:
    # Verifies an out-of-range, negative or unparsable answer is re-asked instead of ending the command
    @pytest.mark.parametrize("bad", ["-1", "0x", "9", "", "two"])
    def test_an_invalid_answer_is_re_asked(self, im_module, monkeypatch, capsys, bad):
        answers = iter([bad, "2"])
        monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
        choices = [{"label": "Default", "signed_in": False, "value": "Default"}, {"label": "Profile 1", "signed_in": False, "value": "Profile 1"}]

        assert im_module.select_profile_interactively("Profiles:", choices) == "Profile 1"
        assert "Enter a number between 1 and 2" in capsys.readouterr().out

    # Verifies a negative number can never index backwards into the list and silently pick another profile
    def test_a_negative_answer_never_selects_a_profile(self, im_module, monkeypatch):
        answers = iter(["-1", "1"])
        monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
        choices = [{"label": "Default", "signed_in": False, "value": "Default"}, {"label": "Profile 1", "signed_in": False, "value": "Profile 1"}]

        assert im_module.select_profile_interactively("Profiles:", choices) == "Default"

    # Verifies zero still exits, since that is the documented way out of the picker
    def test_zero_exits_the_picker(self, im_module, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda prompt="": "0")
        choices = [{"label": "Default", "signed_in": True, "value": "Default"}]

        with pytest.raises(SystemExit):
            im_module.select_profile_interactively("Profiles:", choices)

    # Verifies the list says which profile holds an Instagram session, so the choice is not made blind
    def test_the_list_marks_which_profile_is_signed_in(self, im_module, monkeypatch, capsys):
        monkeypatch.setattr("builtins.input", lambda prompt="": "1")
        choices = [{"label": "Default", "signed_in": False, "value": "Default"}, {"label": "Profile 1", "signed_in": True, "value": "Profile 1"}, {"label": "Profile 2", "signed_in": None, "value": "Profile 2"}]

        im_module.select_profile_interactively("Profiles:", choices)

        listing = capsys.readouterr().out
        assert "1) Default  [not signed in to Instagram]" in listing
        assert "2) Profile 1  [signed in to Instagram]" in listing
        assert "3) Profile 2\n" in listing, "an unreadable database is left unlabelled rather than guessed at"

    # Verifies Enter takes the only signed-in profile, and is re-asked when the answer would be a guess
    def test_enter_takes_the_only_signed_in_profile(self, im_module, monkeypatch, capsys):
        monkeypatch.setattr("builtins.input", lambda prompt="": "")
        one_signed_in = [{"label": "Default", "signed_in": False, "value": "Default"}, {"label": "Profile 1", "signed_in": True, "value": "Profile 1"}]

        assert im_module.select_profile_interactively("Profiles:", one_signed_in) == "Profile 1"
        assert "(default)" in capsys.readouterr().out

        answers = iter(["", "1"])
        monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
        both_signed_in = [{"label": "Default", "signed_in": True, "value": "Default"}, {"label": "Profile 1", "signed_in": True, "value": "Profile 1"}]

        assert im_module.select_profile_interactively("Profiles:", both_signed_in) == "Default"


class TestLiveBrowserCookies:
    # Builds a WAL cookie database whose newest row is still only in the write-ahead log, as a running browser leaves it
    @staticmethod
    def _live_database(directory: Path, firefox: bool = True):
        cookie_path = directory / ("cookies.sqlite" if firefox else "Cookies")
        table, column = ("moz_cookies", "host") if firefox else ("cookies", "host_key")
        writer = sqlite3.connect(cookie_path)
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute(f"CREATE TABLE {table} ({column} TEXT, name TEXT, value TEXT)")
        writer.commit()
        writer.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        writer.execute(f"INSERT INTO {table} VALUES (?, ?, ?)", ("instagram.com", "sessionid", "fresh"))
        writer.commit()
        return cookie_path, writer

    # Verifies a session written moments ago by a still-running Firefox is read, rather than reported as absent
    def test_a_running_firefox_session_is_read(self, im_module):
        ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ARTIFACT_ROOT) as directory_name:
            cookie_path, writer = self._live_database(Path(directory_name))
            try:
                assert Path(str(cookie_path) + "-wal").exists(), "the row has to still be in the log for this to test anything"
                assert im_module.get_firefox_cookie_dict(str(cookie_path)) == {"sessionid": "fresh"}
            finally:
                writer.close()

    # Verifies the picker does not mark a running browser's profile as signed out while the import would succeed
    @pytest.mark.parametrize("firefox", [True, False])
    def test_a_running_browser_profile_reads_as_signed_in(self, im_module, firefox):
        ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ARTIFACT_ROOT) as directory_name:
            cookie_path, writer = self._live_database(Path(directory_name), firefox=firefox)
            try:
                assert im_module.cookie_file_has_instagram_session(str(cookie_path), firefox=firefox) is True
            finally:
                writer.close()

    # Verifies a database that cannot be opened read-only still falls back to the immutable mode
    def test_an_unreadable_mode_falls_back_to_immutable(self, im_module, monkeypatch):
        ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ARTIFACT_ROOT) as directory_name:
            cookie_path = Path(directory_name) / "cookies.sqlite"
            with sqlite3.connect(cookie_path) as connection:
                connection.execute("CREATE TABLE moz_cookies (host TEXT, name TEXT, value TEXT)")
                connection.execute("INSERT INTO moz_cookies VALUES ('instagram.com', 'sessionid', 'checkpointed')")
            monkeypatch.setattr(im_module, "sqlite_readonly_uri", lambda path: "file:/nonexistent/db.sqlite?mode=ro")

            assert im_module.get_firefox_cookie_dict(str(cookie_path)) == {"sessionid": "checkpointed"}

    # Verifies the read-only URI cannot have its parameters displaced by a path, as the immutable one cannot
    @pytest.mark.parametrize("path,forbidden", [("/tmp/db.sqlite?immutable=0", "?immutable=0"), ("/tmp/db.sqlite?vfs=unix-none", "?vfs="), ("/tmp/a#frag/db.sqlite", "#frag")])
    def test_the_read_only_uri_cannot_be_injected(self, im_module, path, forbidden):
        uri = im_module.sqlite_readonly_uri(path)

        assert forbidden not in uri
        assert uri.endswith("?mode=ro")
        assert uri.count("?") == 1
