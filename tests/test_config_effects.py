"""Verifies config-file settings actually reach the code that consumes them (no network)."""

import inspect
from pathlib import Path
from unittest.mock import Mock

import pytest


@pytest.fixture
# Restores every module-level setting a real startup run mutates, so one test cannot leak into the next
def restored_globals(im_module):
    snapshot = {name: value for name, value in vars(im_module).items() if name.isupper()}
    yield
    for name, value in snapshot.items():
        setattr(im_module, name, value)
    for name in [name for name in vars(im_module) if name.isupper() and name not in snapshot]:
        delattr(im_module, name)


class TestConnectivityCheckResolution:
    # Verifies no connectivity setting is frozen into the function signature where a config file cannot reach it
    def test_connectivity_defaults_are_not_bound_at_import(self, im_module):
        parameters = inspect.signature(im_module.check_internet).parameters

        assert [parameters[name].default for name in ("url", "timeout")] == [None, None], "resolving these at import time would freeze them before any config file loads"

    # Verifies a config-file URL and timeout reach the startup check rather than the built-in defaults
    def test_configured_url_and_timeout_reach_the_request(self, im_module, monkeypatch):
        recorded = {}
        monkeypatch.setattr(im_module, "CHECK_INTERNET_URL", "https://probe.example/ping")
        monkeypatch.setattr(im_module, "CHECK_INTERNET_TIMEOUT", 17)
        monkeypatch.setattr(im_module.req, "get", lambda url, **kwargs: recorded.update(url=url, **kwargs))

        assert im_module.check_internet() is True
        assert recorded["url"] == "https://probe.example/ping"
        assert recorded["timeout"] == 17

    # Verifies an explicit argument still wins over the resolved global, so callers keep full control
    @pytest.mark.parametrize("url,timeout", [("https://explicit.example", 3), ("https://other.example", 9)])
    def test_explicit_arguments_win(self, im_module, monkeypatch, url, timeout):
        recorded = {}
        monkeypatch.setattr(im_module, "CHECK_INTERNET_URL", "https://global.example")
        monkeypatch.setattr(im_module, "CHECK_INTERNET_TIMEOUT", 99)
        monkeypatch.setattr(im_module.req, "get", lambda target, **kwargs: recorded.update(url=target, **kwargs))

        assert im_module.check_internet(url, timeout) is True
        assert (recorded["url"], recorded["timeout"]) == (url, timeout)

    # Verifies a later change to the global is observed, which is the whole point of resolving at call time
    def test_a_later_global_change_is_observed(self, im_module, monkeypatch):
        seen = []
        monkeypatch.setattr(im_module.req, "get", lambda url, **kwargs: seen.append(url))

        monkeypatch.setattr(im_module, "CHECK_INTERNET_URL", "https://first.example")
        im_module.check_internet()
        monkeypatch.setattr(im_module, "CHECK_INTERNET_URL", "https://second.example")
        im_module.check_internet()

        assert seen == ["https://first.example", "https://second.example"]


class TestLivenessReminderRecomputation:
    # Verifies the reminder follows the configured liveness interval whatever the check interval is
    @pytest.mark.parametrize("check_interval,liveness_interval,expected", [(300, 43200, 43200), (600, 43200, 43200), (3600, 21600, 21600), (5400, 43200, 43200), (86400, 43200, 43200)])
    def test_recompute_follows_the_effective_interval(self, im_module, monkeypatch, check_interval, liveness_interval, expected):
        monkeypatch.setattr(im_module, "INSTA_CHECK_INTERVAL", check_interval)
        monkeypatch.setattr(im_module, "LIVENESS_CHECK_INTERVAL", liveness_interval)
        monkeypatch.setattr(im_module, "LIVENESS_REMINDER_SECONDS", 0)

        im_module.recompute_liveness_reminder()

        assert im_module.LIVENESS_REMINDER_SECONDS == expected

    # Verifies a disabled liveness interval or a stopped poll switches the reminder off
    @pytest.mark.parametrize("check_interval,liveness_interval", [(300, 0), (0, 43200), (0, 0)])
    def test_disabled_settings_switch_the_reminder_off(self, im_module, monkeypatch, check_interval, liveness_interval):
        monkeypatch.setattr(im_module, "INSTA_CHECK_INTERVAL", check_interval)
        monkeypatch.setattr(im_module, "LIVENESS_CHECK_INTERVAL", liveness_interval)
        monkeypatch.setattr(im_module, "LIVENESS_REMINDER_SECONDS", 99)

        im_module.recompute_liveness_reminder()

        assert im_module.LIVENESS_REMINDER_SECONDS == 0


class TestVerboseNotices:
    # Verifies a verbose notice closes with the timestamp trailer once the monitoring screen has started
    def test_a_verbose_notice_closes_with_the_timestamp_trailer(self, im_module, monkeypatch, capsys):
        monkeypatch.setattr(im_module, "VERBOSE_MODE", True)
        monkeypatch.setattr(im_module, "MONITORING_ACTIVE", False)

        im_module.verbose_notice("Skipping updates for someone")
        assert capsys.readouterr().out == "* Skipping updates for someone\n"

        im_module.mark_monitoring_started()
        im_module.verbose_notice("Skipping updates for someone")
        output = capsys.readouterr().out

        assert output.startswith("* Skipping updates for someone\n")
        assert "Timestamp:" in output

    # Verifies a verbose notice stays silent without the flag, so the quiet default is unchanged
    def test_a_verbose_notice_stays_silent_without_the_flag(self, im_module, monkeypatch, capsys):
        monkeypatch.setattr(im_module, "VERBOSE_MODE", False)

        im_module.verbose_notice("Skipping updates for someone")

        assert capsys.readouterr().out == ""

    # Verifies the per-check hours-range notice goes through the shared notice helper rather than a bare print
    def test_the_hours_range_notice_uses_the_shared_helper(self):
        source = (Path(__file__).resolve().parents[1] / "instagram_monitor.py").read_text(encoding="utf-8")

        assert "verbose_notice(skip_notice)" in source


class TestPerCheckReporting:
    # Verifies the per-check lines stay debug traces, since two verbose blocks per cycle buried the events worth reading
    def test_the_check_boundaries_are_debug_only_traces(self):
        source = (Path(__file__).resolve().parents[1] / "instagram_monitor.py").read_text(encoding="utf-8")

        assert 'verbose_print(f"Starting check #' not in source
        assert 'verbose_print(f"Check #' not in source
        assert 'debug_print("Starting check"' in source
        assert 'debug_print("Completed check"' in source


class TestWebhookDestination:
    # Drives the real command line up to the monitoring call and returns the webhook state startup settled on
    def webhook_state_after_startup(self, im_module, monkeypatch, tmp_path, webhook_url):
        config = tmp_path / "instagram_monitor.conf"
        config.write_text('LOCAL_TIMEZONE = "UTC"\nDISABLE_LOGGING = True\nWEBHOOK_ENABLED = True\nWEBHOOK_PROVIDER = "ntfy"\n' + f'WEBHOOK_URL = "{webhook_url}"\n', encoding="utf-8")
        monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py", "target.user", "--config-file", str(config), "--env-file", "none", "--no-color"])
        monkeypatch.setattr(im_module, "clear_screen", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "check_internet", lambda *args, **kwargs: True)
        monkeypatch.setattr(im_module, "instagram_monitor_user", Mock(side_effect=SystemExit(99)))

        with pytest.raises(SystemExit) as exc:
            im_module.run_main()

        assert exc.value.code == 99
        return im_module.WEBHOOK_ENABLED

    # Verifies an unedited webhook destination switches the channel off instead of being treated as configured
    def test_a_placeholder_webhook_url_switches_the_channel_off(self, im_module, monkeypatch, tmp_path, restored_globals):
        assert self.webhook_state_after_startup(im_module, monkeypatch, tmp_path, "your_webhook_url") is False

    # Verifies a real destination still leaves the webhook channel on
    def test_a_configured_webhook_url_keeps_the_channel_on(self, im_module, monkeypatch, tmp_path, restored_globals):
        assert self.webhook_state_after_startup(im_module, monkeypatch, tmp_path, "https://ntfy.sh/some-topic") is True


# Drives the real startup path with the report stubbed out, so only the resolution the run performs is observed
def run_startup(im_module, monkeypatch, tmp_path, argv=(), config_text="", environment=None, clear_screen=False):
    for name in im_module.SECRET_KEYS:
        monkeypatch.delenv(name, raising=False)
    for name, value in (environment or {}).items():
        monkeypatch.setenv(name, value)
    config = tmp_path / "instagram_monitor.conf"
    config.write_text(f"CLEAR_SCREEN = {clear_screen}\nDISABLE_LOGGING = True\n" + config_text, encoding="utf-8")
    monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py", "--doctor", "--debug", "--no-color", "--config-file", str(config), "--env-file", "none", *argv])
    monkeypatch.setattr(im_module, "clear_screen", lambda *args, **kwargs: None)
    monkeypatch.setattr(im_module, "run_doctor", lambda *args, **kwargs: 0)
    with pytest.raises(SystemExit):
        im_module.run_main()


class TestSecretTrace:
    # The diagnostic line is documented as comma-separated key=value fields, so no field value may carry one
    @pytest.mark.parametrize("value, expected", [
        ("a-password-the-user-picked", {"value": "set"}),
        ("your_smtp_password", {"value": "not set"}),
        ("", {"value": "not set"}),
        (None, {"value": "not set"}),
    ])
    def test_no_secret_field_value_carries_a_comma(self, im_module, value, expected):
        assert im_module.secret_fields(value) == expected
        assert all("," not in str(part) for part in expected.values())

    # A source outside the set is a typo rather than a new layer, so it is refused instead of reaching the summary
    def test_an_unsupported_secret_source_is_refused(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "SECRET_SOURCES", {})

        with pytest.raises(ValueError, match="Unsupported secret source"):
            im_module.record_secret_source("SMTP_PASSWORD", "somewhere else", "a-password-the-user-picked")

        assert im_module.SECRET_SOURCES == {}

    # A placeholder is not a value, so recording it clears the earlier answer rather than adding a row
    def test_a_placeholder_clears_the_recorded_source(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "SECRET_SOURCES", {"SMTP_PASSWORD": "dotenv file"})

        im_module.record_secret_source("SMTP_PASSWORD", "command line", "your_smtp_password")

        assert im_module.SECRET_SOURCES == {}

    # Confirms every layer that can supply a secret is traced under the source that actually supplied it
    @pytest.mark.parametrize("argv, environment, config_text, expected", [
        ((), {}, 'SMTP_PASSWORD = "a-password-the-user-picked"\n', "name=SMTP_PASSWORD, source=configuration file or command line, value=set"),
        ((), {"NTFY_ACCESS_TOKEN": "tk_exported_token"}, "", "name=NTFY_ACCESS_TOKEN, source=environment, value=set"),
        (("--webhook-url", "https://ntfy.sh/traced-topic"), {}, "", "name=WEBHOOK_URL, source=command line, value=set"),
        (("--proxy-url", "http://127.0.0.1:8080"), {}, "", "name=PROXY_URL, source=command line, value=set"),
    ])
    def test_every_secret_layer_is_traced(self, im_module, monkeypatch, tmp_path, capsys, restored_globals, argv, environment, config_text, expected):
        run_startup(im_module, monkeypatch, tmp_path, argv, config_text, environment)

        output = capsys.readouterr().out
        assert f"Secret resolution: {expected}" in output
        assert "a-password-the-user-picked" not in output

    # The command line is the last layer to supply a secret, so a run with none says so only after it has had its say
    def test_a_run_with_no_secret_anywhere_says_so(self, im_module, monkeypatch, tmp_path, capsys, restored_globals):
        run_startup(im_module, monkeypatch, tmp_path)

        output = capsys.readouterr().out
        assert "Secret resolution:" not in output
        assert "No private settings were resolved from config, dotenv, environment or the command line" in output


class TestEarlyStartupTimestamps:
    # LOCAL_TIMEZONE still holds the 'Auto' sentinel until it is resolved, which is not a zone pytz can build
    def test_a_timestamp_survives_the_unresolved_timezone(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "LOCAL_TIMEZONE", "Auto")

        assert im_module.now_local().tzinfo is not None
        assert im_module.now_local_naive().tzinfo is None
        assert im_module.get_hour_min_from_ts(im_module.now_local(), show_seconds=True)

    # The first debug line is printed before the timezone is resolved, so it must not be what ends the run
    def test_the_first_debug_line_does_not_end_the_run(self, im_module, monkeypatch, tmp_path, capsys, restored_globals):
        monkeypatch.setattr(im_module, "LOCAL_TIMEZONE", "Auto")

        run_startup(im_module, monkeypatch, tmp_path, clear_screen=True)

        assert "Terminal screen clear skipped because debug mode is active" in capsys.readouterr().out


class TestTechnicalDetail:
    # The classified detail is the raw failure, which belongs to a debug run rather than to the normal error block
    @pytest.mark.parametrize("debug, expected", [(True, True), (False, False)])
    def test_the_technical_detail_line_follows_debug_mode(self, im_module, debug, expected):
        advice = im_module.make_recovery_advice("network.unavailable", "The service could not be reached", "Check the connection", True, "ConnectionError: [Errno 61] Connection refused")

        rendered = im_module.render_recovery_advice(advice, debug=debug)

        assert ("Technical detail: ConnectionError: [Errno 61] Connection refused" in rendered) is expected

    # A detail that only repeats a line already printed spends a line saying nothing
    def test_a_detail_repeating_the_summary_is_dropped(self, im_module):
        advice = im_module.make_recovery_advice("config.missing", "Config file 'x.conf' does not exist", "Correct the path", False, "Config file 'x.conf' does not exist")

        assert "Technical detail:" not in im_module.render_recovery_advice(advice, debug=True)


class TestSecretReporting:
    # Confirms an unedited placeholder is never reported as a loaded secret, whichever layer recorded it
    def test_placeholder_secrets_are_not_reported_as_loaded(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "SECRET_SOURCES", {"WEBHOOK_URL": "dotenv file", "SMTP_PASSWORD": "configuration file or command line"})
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "your_webhook_url")
        monkeypatch.setattr(im_module, "SMTP_PASSWORD", "your_smtp_password")

        from_file, from_environment, from_settings, from_command_line = im_module.doctor_secret_sources(None)

        assert "WEBHOOK_URL" not in from_file + from_environment + from_settings + from_command_line
        assert "SMTP_PASSWORD" not in from_file + from_environment + from_settings + from_command_line


class TestConfigLoadReporting:
    # Verifies the settings count is a debug trace rather than a verbose line, since it says nothing a user acts on
    def test_the_config_settings_count_is_a_debug_only_trace(self, im_module, tmp_path, monkeypatch, capsys):
        config = tmp_path / "instagram_monitor.conf"
        config.write_text("CLEAR_SCREEN = False\nDISABLE_LOGGING = True\n", encoding="utf-8")
        namespace = {}

        monkeypatch.setattr(im_module, "VERBOSE_MODE", True)
        monkeypatch.setattr(im_module, "DEBUG_MODE", False)
        im_module.load_config_file(config, namespace=namespace)
        assert "settings from the configuration file" not in capsys.readouterr().out

        monkeypatch.setattr(im_module, "VERBOSE_MODE", False)
        monkeypatch.setattr(im_module, "DEBUG_MODE", True)
        im_module.load_config_file(config, namespace=namespace)
        assert "Configuration applied" in capsys.readouterr().out


class TestStartupScreenClearing:
    # Verifies only debug keeps the screen, since a cleared terminal loses the run being compared against
    @pytest.mark.parametrize(("flag", "expected"), (("--debug", False), ("--verbose", True)))
    def test_only_debug_mode_keeps_the_screen(self, im_module, monkeypatch, tmp_path, restored_globals, flag, expected):
        config = tmp_path / "instagram_monitor.conf"
        config.write_text('LOCAL_TIMEZONE = "UTC"\nDISABLE_LOGGING = True\nCLEAR_SCREEN = True\n', encoding="utf-8")
        cleared = []
        monkeypatch.setattr(im_module, "clear_screen", lambda enabled=True: cleared.append(bool(enabled)))
        monkeypatch.setattr(im_module, "CLEAR_SCREEN", True)
        monkeypatch.setattr(im_module, "DEBUG_MODE", False)
        monkeypatch.setattr(im_module, "VERBOSE_MODE", False)
        monkeypatch.setattr(im_module, "check_internet", lambda *args, **kwargs: True)
        monkeypatch.setattr(im_module, "instagram_monitor_user", Mock(side_effect=SystemExit(99)))
        monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py", "target.user", "--config-file", str(config), "--env-file", "none", "--no-color", flag])

        with pytest.raises(SystemExit):
            im_module.run_main()

        assert cleared == [expected]

    @pytest.mark.parametrize(("argv", "expected"), ((["instagram_monitor.py", "--doctor"], True), (["instagram_monitor.py", "--set-smtp-password"], True), (["instagram_monitor.py", "--send-test-email"], True), (["instagram_monitor.py", "--help"], True), (["instagram_monitor.py", "target.user"], False)))
    # Verifies the one-shot commands keep whatever is already on the screen, so their output stays scrollable
    def test_one_shot_commands_keep_the_terminal_history(self, im_module, monkeypatch, argv, expected):
        monkeypatch.setattr(im_module.sys, "argv", argv)

        assert im_module.keep_terminal_history() is expected

    # Verifies a redirected stdout is never cleared, so no escape sequence or TERM warning reaches the captured output
    def test_a_redirected_stdout_is_never_cleared(self, im_module, monkeypatch):
        commands = []
        monkeypatch.setattr(im_module.sys.stdout, "isatty", lambda: False, raising=False)
        monkeypatch.setattr(im_module.os, "system", lambda command: commands.append(command))

        im_module.clear_screen(True)

        assert commands == []


@pytest.mark.parametrize("source, position", [("dotenv file", 0), ("environment", 1), ("configuration file or command line", 2), ("command line", 3)])
# Verifies each source that can supply a secret lands in its own bucket, so none of them is filed under another
def test_each_secret_source_lands_in_its_own_bucket(im_module, monkeypatch, source, position):
    for name in im_module.SECRET_KEYS:
        monkeypatch.setattr(im_module, name, "your_placeholder", raising=False)
    monkeypatch.setattr(im_module, "SECRET_SOURCES", {"SMTP_PASSWORD": source}, raising=False)
    monkeypatch.setattr(im_module, "SMTP_PASSWORD", "a-real-secret-value", raising=False)

    buckets = im_module.doctor_secret_sources(None)

    assert buckets[position] == ["SMTP_PASSWORD"]
    assert [names for index, names in enumerate(buckets) if index != position] == [[], [], []]
