"""Offline tests for browser cookie filtering and session path discovery."""

import os
import sqlite3
import stat
import sys
import tempfile
from contextlib import closing
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = PROJECT_ROOT / "local" / "test_artifacts" / "session_import"


# Stands in for the optional pycookiecheat package, which the Chromium reader imports but the test run does not install
def fake_pycookiecheat(get_cookies):
    module: Any = ModuleType("pycookiecheat")
    module.BrowserType = SimpleNamespace(CHROME="chrome", BRAVE="brave", CHROMIUM="chromium")
    module.get_cookies = get_cookies
    return module


class TestFirefoxCookieImport:
    # Legacy Firefox schemas include exact Instagram hosts without suffix lookalikes
    def test_fallback_query_rejects_lookalike_domains(self, im_module):
        ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ARTIFACT_ROOT) as directory_name:
            cookie_path = Path(directory_name) / "cookies.sqlite"
            with closing(sqlite3.connect(cookie_path)) as connection, connection:
                connection.execute("CREATE TABLE moz_cookies (host TEXT, name TEXT, value TEXT)")
                connection.executemany("INSERT INTO moz_cookies VALUES (?, ?, ?)", [("instagram.com", "sessionid", "root"), (".instagram.com", "csrftoken", "subdomain"), ("notinstagram.com", "attacker", "suffix"), ("instagram.com.evil.example", "attacker2", "prefix"), ("evilinstagram.com", "attacker3", "lookalike")])

            cookies = im_module.get_firefox_cookie_dict(str(cookie_path))

        assert cookies == {"sessionid": "root", "csrftoken": "subdomain"}


class TestWindowsFirefoxDiscovery:
    # Builds a Windows home directory under tmp_path and points discovery at it, with the real profile
    # enumeration restored so the globs run against that tree rather than the host's browsers
    @pytest.fixture
    def windows_home(self, im_module, monkeypatch, tmp_path, real_browser_profiles):
        home = tmp_path / "home"
        roaming = home / "AppData" / "Roaming"
        local = home / "AppData" / "Local"
        monkeypatch.setattr(im_module, "system", lambda: "Windows")
        monkeypatch.setattr(im_module, "expanduser", lambda path: str(home) + path[1:] if path.startswith("~") else path)
        monkeypatch.setenv("APPDATA", str(roaming))
        monkeypatch.setenv("LOCALAPPDATA", str(local))
        monkeypatch.setattr(im_module, "FIREFOX_WINDOWS_COOKIE", str(roaming / "Mozilla/Firefox/Profiles/*/cookies.sqlite"))
        return home, roaming, local

    # Creates an empty cookie database, which is all discovery needs to offer a profile
    @staticmethod
    def _make_profile(path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"")
        return path

    # Returns the Store package profile path for one profile directory name
    @staticmethod
    def _store_path(local: Path, profile_dir: str) -> Path:
        return local / "Packages/Mozilla.Firefox_n80bbvh6b1yt2/LocalCache/Roaming/Mozilla/Firefox/Profiles" / profile_dir / "cookies.sqlite"

    # Verifies the regular installer and the Store package are both offered, with the Store one tagged
    def test_regular_and_store_profiles(self, im_module, windows_home):
        _, roaming, local = windows_home
        regular = self._make_profile(roaming / "Mozilla/Firefox/Profiles/regular.default-release/cookies.sqlite")
        store = self._make_profile(self._store_path(local, "store.work"))

        profiles = im_module.list_firefox_profiles()

        assert [Path(profile["path"]) for profile in profiles] == [regular, store]
        assert [profile["name"] for profile in profiles] == ["default-release", "work"]
        assert [profile["install"] for profile in profiles] == ["", "Microsoft Store"]
        assert Path(im_module.resolve_firefox_profile("store.work")) == store

    # Verifies a Store profile is told apart from a regular one of the same name, which is the usual case
    # since both installs create a profile called default-release
    def test_a_store_profile_is_distinguished_from_a_regular_one(self, im_module, windows_home):
        _, roaming, local = windows_home
        self._make_profile(roaming / "Mozilla/Firefox/Profiles/aaa.default-release/cookies.sqlite")
        store = self._make_profile(self._store_path(local, "bbb.default-release"))

        descriptions = [im_module.firefox_profile_description(p) for p in im_module.list_firefox_profiles()]
        assert descriptions == ["default-release", "default-release (Microsoft Store)"]

        with pytest.raises(im_module.CookieImportError) as failure:
            im_module.resolve_firefox_profile("default-release")

        assert "matches 2 profiles" in str(failure.value)
        assert Path(im_module.resolve_firefox_profile("bbb.default-release")) == store

    # Verifies a Store-only machine selects its sole profile instead of reporting that no database was found
    def test_store_only_auto_selection(self, im_module, windows_home):
        _, _, local = windows_home
        store = self._make_profile(self._store_path(local, "a.default"))

        assert Path(im_module.get_firefox_cookiefile()) == store

    # Verifies a missing or redirected environment variable does not hide the package directory under the home
    @pytest.mark.parametrize("redirected", [False, True])
    def test_package_home_fallback(self, im_module, monkeypatch, windows_home, redirected):
        home, _, local = windows_home
        if redirected:
            monkeypatch.setenv("LOCALAPPDATA", str(home / "redirected"))
        else:
            monkeypatch.delenv("LOCALAPPDATA")
            monkeypatch.delenv("APPDATA")
        store = self._make_profile(self._store_path(local, "a.default"))

        assert Path(im_module.get_firefox_cookiefile()) == store

    # Verifies a redirected roaming directory is searched as well as the home-relative one, for either variable
    @pytest.mark.parametrize("variable,relative", [("APPDATA", "Mozilla/Firefox/Profiles/a.default/cookies.sqlite"), ("LOCALAPPDATA", "Packages/Mozilla.Firefox_n80bbvh6b1yt2/LocalCache/Roaming/Mozilla/Firefox/Profiles/a.default/cookies.sqlite")])
    def test_a_redirected_root_is_searched_alongside_the_home_one(self, im_module, monkeypatch, windows_home, variable, relative):
        home, _, _ = windows_home
        monkeypatch.setattr(im_module, "FIREFOX_WINDOWS_COOKIE", str(home / "configured/cookies.sqlite"))
        redirected = home / "redirected"
        monkeypatch.setenv(variable, str(redirected))
        away = self._make_profile(redirected / relative)
        at_home = self._make_profile(home / "AppData" / ("Roaming" if variable == "APPDATA" else "Local") / relative)

        assert [Path(p["path"]) for p in im_module.list_firefox_profiles()] == [away, at_home]

    # Verifies the configured pattern stays first and is still searched when it points somewhere else entirely
    def test_custom_pattern_and_roaming(self, im_module, monkeypatch, windows_home):
        home, _, _ = windows_home
        custom = self._make_profile(home / "custom/cookies.sqlite")
        roaming = home / "redirected-roaming"
        regular = self._make_profile(roaming / "Mozilla/Firefox/Profiles/a.default/cookies.sqlite")
        monkeypatch.setattr(im_module, "FIREFOX_WINDOWS_COOKIE", str(custom))
        monkeypatch.setenv("APPDATA", str(roaming))

        assert im_module.firefox_cookie_patterns()[0] == str(custom)
        assert [Path(p["path"]) for p in im_module.list_firefox_profiles()] == [custom, regular]

    # Verifies the shipped configuration and the environment's answer for the same directory collapse into one
    # pattern, so the ordinary roaming location is not globbed three times on every Windows run
    def test_the_roaming_location_is_searched_once(self, im_module, monkeypatch, windows_home):
        _, roaming, local = windows_home
        monkeypatch.setattr(im_module, "FIREFOX_WINDOWS_COOKIE", "~/AppData/Roaming/Mozilla/Firefox/Profiles/*/cookies.sqlite")
        regular = self._make_profile(roaming / "Mozilla/Firefox/Profiles/a.default/cookies.sqlite")

        patterns = im_module.firefox_cookie_patterns()

        assert len(patterns) == 2
        assert patterns[0] == "~/AppData/Roaming/Mozilla/Firefox/Profiles/*/cookies.sqlite"
        assert patterns[1] == os.path.join(str(local), "Packages", "Mozilla.Firefox_*", "LocalCache", "Roaming", "Mozilla", "Firefox", "Profiles", "*", "cookies.sqlite")
        assert [Path(p["path"]) for p in im_module.list_firefox_profiles()] == [regular]

    # Verifies the Windows branch is exclusive, so the other platforms keep the patterns they had
    @pytest.mark.parametrize("platform", ["Darwin", "Linux"])
    def test_other_platforms_unchanged(self, im_module, monkeypatch, platform):
        monkeypatch.setattr(im_module, "system", lambda: platform)
        monkeypatch.setattr(im_module, "FIREFOX_MACOS_COOKIE", "mac-pattern")
        monkeypatch.setattr(im_module, "FIREFOX_LINUX_COOKIE", "linux-pattern")

        patterns = im_module.firefox_cookie_patterns()

        if platform == "Darwin":
            assert patterns == ("mac-pattern",)
        else:
            assert patterns == ("linux-pattern", "~/snap/firefox/common/.mozilla/firefox/*/cookies.sqlite", "~/.var/app/org.mozilla.firefox/.mozilla/firefox/*/cookies.sqlite", "~/.mozilla/firefox/Profiles/*/cookies.sqlite")


class TestSessionPaths:
    # Unix session discovery includes Instaloader's canonical path plus both legacy locations
    def test_unix_candidates_include_canonical_and_legacy_paths(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "system", lambda: "Darwin")

        candidates = [path.replace("\\", "/") for path in im_module.get_session_file_candidates("Session.User")]

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

    # Verifies only the profiles worth choosing are marked, so a long list is not buried in repeated labels
    def test_the_list_marks_only_the_signed_in_profiles(self, im_module, monkeypatch, capsys):
        monkeypatch.setattr("builtins.input", lambda prompt="": "1")
        choices = [{"label": "Default", "signed_in": False, "value": "Default"}, {"label": "Profile 1", "signed_in": True, "value": "Profile 1"}, {"label": "Profile 2", "signed_in": None, "value": "Profile 2"}]

        im_module.select_profile_interactively("Profiles:", choices)

        listing = capsys.readouterr().out
        assert "* marks a profile signed in to Instagram" in listing
        assert "2) * Profile 1" in listing
        assert "1)   Default\n" in listing, "a profile without a session is left unmarked rather than labelled"
        assert "3)   Profile 2\n" in listing, "an unreadable database is left unmarked rather than guessed at"
        assert "not signed in" not in listing

    # Verifies a list with nothing to mark drops the legend and the marker column rather than indenting for nothing
    def test_a_list_with_no_session_has_no_marker_column(self, im_module, monkeypatch, capsys):
        monkeypatch.setattr("builtins.input", lambda prompt="": "1")
        choices = [{"label": "Default", "signed_in": False, "value": "Default"}, {"label": "Profile 1", "signed_in": None, "value": "Profile 1"}]

        im_module.select_profile_interactively("Profiles:", choices)

        listing = capsys.readouterr().out
        assert "marks a profile" not in listing
        assert "1) Default\n" in listing

    # Verifies the numbers stay aligned once the list runs past nine profiles
    def test_the_numbers_are_aligned_past_nine_profiles(self, im_module, monkeypatch, capsys):
        monkeypatch.setattr("builtins.input", lambda prompt="": "1")
        choices = [{"label": f"Profile {number}", "signed_in": number == 1, "value": str(number)} for number in range(1, 12)]

        im_module.select_profile_interactively("Profiles:", choices)

        listing = capsys.readouterr().out
        assert "   1) * Profile 1" in listing
        assert "  11)   Profile 11" in listing

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


class TestReadOnlyMediaFallback:
    # The Docker Firefox import mounts the profile read-only, and SQLite cannot open a WAL database that way
    # because it still needs to write the shared-memory file. Losing the immutable fallback would break that
    # import completely, which is why this pins it rather than trusting the read-only mode alone
    def test_a_read_only_profile_still_imports(self, im_module):
        ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ARTIFACT_ROOT) as directory_name:
            directory = Path(directory_name)
            cookie_path = directory / "cookies.sqlite"
            writer = sqlite3.connect(cookie_path)
            writer.execute("PRAGMA journal_mode=WAL")
            writer.execute("CREATE TABLE moz_cookies (host TEXT, name TEXT, value TEXT)")
            writer.execute("INSERT INTO moz_cookies VALUES ('instagram.com', 'sessionid', 'mounted')")
            writer.commit()
            writer.close()
            for entry in directory.iterdir():
                entry.chmod(stat.S_IRUSR)
            directory.chmod(stat.S_IRUSR | stat.S_IXUSR)
            try:
                with pytest.raises(sqlite3.OperationalError):
                    sqlite3.connect(im_module.sqlite_readonly_uri(cookie_path), uri=True).execute("SELECT 1 FROM moz_cookies")

                assert im_module.get_firefox_cookie_dict(str(cookie_path)) == {"sessionid": "mounted"}
                assert im_module.cookie_file_has_instagram_session(str(cookie_path), firefox=True) is True
            finally:
                directory.chmod(stat.S_IRWXU)
                for entry in directory.iterdir():
                    entry.chmod(stat.S_IRUSR | stat.S_IWUSR)


class TestFirefoxProfileAmbiguity:
    # Snap, Flatpak and distribution builds keep separate profile trees that commonly share a friendly name
    @staticmethod
    def _two_installs():
        return [{"dir": "aaa.default-release", "name": "default-release", "path": "/home/u/.mozilla/firefox/aaa.default-release/cookies.sqlite", "install": ""}, {"dir": "bbb.default-release", "name": "default-release", "path": "/home/u/snap/firefox/common/.mozilla/firefox/bbb.default-release/cookies.sqlite", "install": "Snap"}]

    # Verifies a name matching two installs is refused rather than resolved to whichever was listed first
    def test_an_ambiguous_profile_name_is_refused(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "list_firefox_profiles", self._two_installs)

        with pytest.raises(im_module.CookieImportError) as failure:
            im_module.resolve_firefox_profile("default-release")

        assert "matches 2 profiles" in str(failure.value)
        assert "aaa.default-release" in str(failure.value) and "bbb.default-release" in str(failure.value)

    # Verifies the full profile directory still resolves, since that is what the ambiguity error tells you to pass
    def test_the_full_directory_resolves_one_install(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "list_firefox_profiles", self._two_installs)

        assert im_module.resolve_firefox_profile("bbb.default-release").endswith("snap/firefox/common/.mozilla/firefox/bbb.default-release/cookies.sqlite")

    # Verifies an unknown name lists the profiles tagged by install, so two entries do not read identically
    def test_an_unknown_profile_lists_installs(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "list_firefox_profiles", self._two_installs)

        with pytest.raises(im_module.CookieImportError) as failure:
            im_module.resolve_firefox_profile("work")

        assert "default-release, default-release (Snap)" in str(failure.value)

    # Verifies the packaging is read from the profile path rather than guessed
    @pytest.mark.parametrize("path,expected", [("/home/u/.mozilla/firefox/a.default/cookies.sqlite", ""), ("/home/u/snap/firefox/common/.mozilla/firefox/a.default/cookies.sqlite", "Snap"), ("/home/u/.var/app/org.mozilla.firefox/.mozilla/firefox/a.default/cookies.sqlite", "Flatpak"), (r"C:\Users\u\AppData\Roaming\Mozilla\Firefox\Profiles\a.default\cookies.sqlite", ""), (r"C:\Users\u\AppData\Local\Packages\Mozilla.Firefox_n80bbvh6b1yt2\LocalCache\Roaming\Mozilla\Firefox\Profiles\a.default\cookies.sqlite", "Microsoft Store")])
    def test_the_install_is_read_from_the_path(self, im_module, path, expected):
        assert im_module.firefox_install_label(path) == expected


class TestSingleProfileWarning:
    # Verifies the one profile available is checked before the import, since there is no other one to pick instead
    def test_the_only_firefox_profile_warns_when_signed_out(self, im_module, monkeypatch, capsys):
        ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ARTIFACT_ROOT) as directory_name:
            cookie_path = Path(directory_name) / "cookies.sqlite"
            with sqlite3.connect(cookie_path) as connection:
                connection.execute("CREATE TABLE moz_cookies (host TEXT, name TEXT, value TEXT)")
                connection.execute("INSERT INTO moz_cookies VALUES ('instagram.com', 'csrftoken', 'x')")
            monkeypatch.setattr(im_module, "list_firefox_profiles", lambda: [{"dir": "a.default", "name": "default", "path": str(cookie_path), "install": ""}])

            assert im_module.get_firefox_cookiefile() == str(cookie_path)
            assert "not signed in to Instagram" in capsys.readouterr().out

    # Verifies a signed-in profile is used without a warning, and an unreadable one is not guessed at
    @pytest.mark.parametrize("name", ["sessionid", None])
    def test_a_usable_or_unknown_profile_warns_about_nothing(self, im_module, monkeypatch, capsys, name):
        ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ARTIFACT_ROOT) as directory_name:
            cookie_path = Path(directory_name) / "cookies.sqlite"
            if name is None:
                cookie_path.write_bytes(b"not a database")
            else:
                with sqlite3.connect(cookie_path) as connection:
                    connection.execute("CREATE TABLE moz_cookies (host TEXT, name TEXT, value TEXT)")
                    connection.execute("INSERT INTO moz_cookies VALUES ('instagram.com', ?, 'x')", (name,))
            monkeypatch.setattr(im_module, "list_firefox_profiles", lambda: [{"dir": "a.default", "name": "default", "path": str(cookie_path), "install": ""}])

            im_module.get_firefox_cookiefile()

            assert "not signed in" not in capsys.readouterr().out


class TestChromiumProfileResolution:
    # Chrome keeps the directory and the display name separate, and the picker shows both
    @staticmethod
    def _profiles():
        return [{"dir": "Default", "name": "Your Chrome", "cookie_file": "/u/Default/Cookies"}, {"dir": "Profile 1", "name": "Test", "cookie_file": "/u/Profile 1/Cookies"}, {"dir": "Profile 2", "name": "Test", "cookie_file": "/u/Profile 2/Cookies"}]

    # Verifies the display name the picker shows also works with --browser-profile, as a Firefox name does
    def test_a_display_name_resolves_to_its_directory(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "list_chromium_profiles", lambda browser: self._profiles())

        assert im_module.resolve_chromium_profile("chrome", "Your Chrome") == "Default"
        assert im_module.resolve_chromium_profile("chrome", "Profile 1") == "Profile 1"

    # Verifies a directory match wins over a display name, since the directory is the unambiguous identifier
    def test_a_directory_is_preferred_over_a_display_name(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "list_chromium_profiles", lambda browser: [{"dir": "Profile 1", "name": "Default", "cookie_file": "/u/Profile 1/Cookies"}, {"dir": "Default", "name": "Other", "cookie_file": "/u/Default/Cookies"}])

        assert im_module.resolve_chromium_profile("chrome", "Default") == "Default"

    # Verifies a display name shared by two profiles is refused rather than resolved to whichever came first
    def test_a_shared_display_name_is_refused(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "list_chromium_profiles", lambda browser: self._profiles())

        with pytest.raises(im_module.CookieImportError) as failure:
            im_module.resolve_chromium_profile("chrome", "Test")

        assert "used by 2 profiles" in str(failure.value)
        assert "Profile 1, Profile 2" in str(failure.value)

    # Verifies an unknown profile lists the directories with their display names, so the answer is usable
    def test_an_unknown_profile_lists_the_directories(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "list_chromium_profiles", lambda browser: self._profiles())

        with pytest.raises(im_module.CookieImportError) as failure:
            im_module.resolve_chromium_profile("chrome", "nope")

        assert "Default (Your Chrome)" in str(failure.value)

    # Verifies a submitted profile cannot reach a cookie database outside the browser's own profiles, which is
    # the guarantee the dashboard already made for Firefox cookie paths
    @pytest.mark.parametrize("escape", ["../../../../tmp/evil", "/tmp/evil", "Default/../../../tmp"])
    def test_a_profile_cannot_escape_the_enumerated_list(self, im_module, monkeypatch, escape):
        monkeypatch.setattr(im_module, "list_chromium_profiles", lambda browser: self._profiles())

        with pytest.raises(im_module.CookieImportError, match="not found"):
            im_module.resolve_chromium_profile("chrome", escape)


class TestChromiumUserDataRoots:
    # Verifies a Snap or Flatpak Chromium is found when no distribution install is present
    @pytest.mark.parametrize("browser,packaged", [("chromium", "~/snap/chromium/common/chromium"), ("chromium", "~/.var/app/org.chromium.Chromium/config/chromium"), ("brave", "~/snap/brave/current/.config/BraveSoftware/Brave-Browser"), ("brave", "~/.var/app/com.brave.Browser/config/BraveSoftware/Brave-Browser")])
    def test_a_packaged_install_is_found(self, im_module, monkeypatch, browser, packaged):
        monkeypatch.setattr(im_module, "system", lambda: "Linux")
        monkeypatch.setattr(im_module.os.path, "isdir", lambda path: path == im_module.expanduser(packaged))

        assert im_module.get_chromium_user_data_dir(browser) == packaged

    # Verifies a distribution install wins, so a machine with both never has to disambiguate them
    def test_the_distribution_install_wins(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "system", lambda: "Linux")
        monkeypatch.setattr(im_module.os.path, "isdir", lambda path: True)

        assert im_module.get_chromium_user_data_dir("chromium") == "~/.config/chromium"

    # Verifies the conventional root is still named when nothing is installed, so the failure stays readable
    def test_a_missing_browser_still_names_a_root(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "system", lambda: "Linux")
        monkeypatch.setattr(im_module.os.path, "isdir", lambda path: False)

        assert im_module.get_chromium_user_data_dir("brave") == "~/.config/BraveSoftware/Brave-Browser"
        assert im_module.get_chromium_user_data_dir("firefox") is None


class TestChromiumProfilesMissing:
    # Verifies a browser whose profiles have never stored a cookie is not reported as a browser that is not installed
    def test_a_profile_without_a_cookie_database_is_explained(self, im_module, monkeypatch, tmp_path):
        (tmp_path / "Default").mkdir()
        (tmp_path / "Profile 1").mkdir()
        monkeypatch.setattr(im_module, "get_chromium_user_data_dir", lambda browser: str(tmp_path))

        message = im_module.chromium_no_profiles_message("chrome")

        assert "Chrome is installed" in message
        assert "Default" in message and "Profile 1" in message
        assert "sign in" in message

    # Verifies a browser that really is absent still says so, with the location that was searched
    def test_a_missing_install_is_named(self, im_module, monkeypatch, tmp_path):
        monkeypatch.setattr(im_module, "get_chromium_user_data_dir", lambda browser: str(tmp_path / "absent"))

        message = im_module.chromium_no_profiles_message("chrome")

        assert "install Chrome" in message
        assert "absent" in message

    # Verifies the picker raises the explanation rather than always blaming a missing install
    def test_the_picker_raises_the_explanation(self, im_module, monkeypatch, tmp_path, real_browser_profiles):
        (tmp_path / "Default").mkdir()
        monkeypatch.setattr(im_module, "system", lambda: "Darwin")
        monkeypatch.setattr(im_module, "get_chromium_user_data_dir", lambda browser: str(tmp_path))

        with pytest.raises(SystemExit) as failure:
            im_module.select_chromium_profile_cli("chrome", None)

        assert "none of its profiles" in str(failure.value)


class TestChromiumKeyringFailure:
    # Verifies a locked or denied keyring is reported as such, not as a browser you forgot to sign in to
    def test_a_keyring_failure_is_not_blamed_on_being_signed_out(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "system", lambda: "Darwin")

        def refuse(*args, **kwargs):
            raise ValueError("Could not find a password for the pair (Chrome Safe Storage, Chrome). Please manually verify they exist in `Keychain Access.app`.")

        monkeypatch.setitem(sys.modules, "pycookiecheat", fake_pycookiecheat(refuse))

        with pytest.raises(im_module.CookieImportError) as failure:
            im_module.get_chromium_cookie_dict("chrome", cookie_file=__file__)

        assert "encryption key" in str(failure.value)
        assert "allow the keychain or keyring prompt" in str(failure.value)
        assert "logged in to Instagram" not in str(failure.value)


class TestDashboardChromiumImport:
    # The dashboard states that it only imports databases it enumerated itself, and that guarantee was previously
    # enforced for Firefox cookie paths but not for the Chromium profile the same handler accepts
    def test_a_submitted_profile_is_resolved_against_the_enumerated_list(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "WEB_DASHBOARD_ENABLED", True)
        monkeypatch.setattr(im_module, "list_chromium_profiles", lambda browser: [{"dir": "Default", "name": "Your Chrome", "cookie_file": "/u/Default/Cookies"}])
        monkeypatch.setattr(im_module, "print_cur_ts", lambda *args, **kwargs: None)
        imported = []
        monkeypatch.setattr(im_module, "import_browser_session_dashboard", lambda browser, cookiefile=None, profile=None: imported.append(profile) or "login.user")
        app = im_module.create_web_dashboard_app()
        assert app is not None
        client = app.test_client()

        refused = client.post("/api/session/browser/import", json={"browser": "chrome", "profile": "../../../../tmp/evil"})

        assert refused.status_code == 400
        assert "not found" in refused.get_json()["error"]
        assert imported == [], "a profile outside the enumerated list never reaches the importer"

        accepted = client.post("/api/session/browser/import", json={"browser": "chrome", "profile": "Your Chrome"})

        assert accepted.get_json()["success"]
        assert imported == ["Default"], "the display name is resolved to the directory the importer expects"


class TestCookieDatabaseOpenCost:
    # A running browser holds its database locked, and the read-only open that sees the log waits out the busy
    # timeout before failing. Attempting it on every profile made listing them stall for seconds per profile
    def test_a_database_without_a_log_skips_the_read_only_attempt(self, im_module, monkeypatch):
        ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ARTIFACT_ROOT) as directory_name:
            cookie_path = Path(directory_name) / "cookies.sqlite"
            with sqlite3.connect(cookie_path) as connection:
                connection.execute("CREATE TABLE moz_cookies (host TEXT, name TEXT, value TEXT)")
                connection.execute("INSERT INTO moz_cookies VALUES ('instagram.com', 'sessionid', 'x')")
            attempted = []
            monkeypatch.setattr(im_module, "sqlite_readonly_uri", lambda path: attempted.append(path) or "file:/nonexistent?mode=ro")

            assert im_module.get_firefox_cookie_dict(str(cookie_path)) == {"sessionid": "x"}
            assert attempted == [], "with no write-ahead log the immutable open already sees everything"

    # Verifies the read-only attempt is still made when a log is present, since that is the only way to see it
    def test_a_database_with_a_log_attempts_the_read_only_open(self, im_module, monkeypatch):
        ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ARTIFACT_ROOT) as directory_name:
            cookie_path = Path(directory_name) / "cookies.sqlite"
            writer = sqlite3.connect(cookie_path)
            writer.execute("PRAGMA journal_mode=WAL")
            writer.execute("CREATE TABLE moz_cookies (host TEXT, name TEXT, value TEXT)")
            writer.commit()
            writer.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            writer.execute("INSERT INTO moz_cookies VALUES ('instagram.com', 'sessionid', 'in_log')")
            writer.commit()
            try:
                assert Path(str(cookie_path) + "-wal").exists()
                attempted = []
                real_uri = im_module.sqlite_readonly_uri
                monkeypatch.setattr(im_module, "sqlite_readonly_uri", lambda path: attempted.append(path) or real_uri(path))

                assert im_module.get_firefox_cookie_dict(str(cookie_path)) == {"sessionid": "in_log"}
                assert attempted, "a log can only be read through the plain read-only open"
            finally:
                writer.close()

    # Verifies the wait on a locked database is bounded, so listing many profiles cannot stall for seconds each
    def test_the_lock_wait_is_bounded(self, im_module):
        assert 0 < im_module.COOKIE_DATABASE_BUSY_TIMEOUT <= 1
