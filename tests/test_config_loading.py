"""Offline tests for restricted configuration file loading."""

from unittest.mock import Mock

import pytest


class TestParseConfigContent:
    # A config file may only assign settings, never run code
    @pytest.mark.parametrize("hostile", [
        "import os\n",
        "INSTA_CHECK_INTERVAL = 5400\nimport os\n",
        "__import__('os').system('true')\n",
        "from pathlib import Path\n",
        "if True:\n    INSTA_CHECK_INTERVAL = 1\n",
        "def helper():\n    return 1\n",
        "for i in range(3):\n    pass\n",
        "print('side effect')\n",
        "class Evil:\n    pass\n",
        "exec('INSTA_CHECK_INTERVAL = 1')\n",
    ])
    def test_executable_content_is_refused(self, im_module, hostile):
        with pytest.raises(ValueError):
            im_module.parse_config_content(hostile, "<hostile>")

    # Values must be plain literals, so a call or a name reference cannot smuggle evaluation in
    @pytest.mark.parametrize("hostile", [
        "INSTA_CHECK_INTERVAL = __import__('os').getpid()\n",
        "CSV_FILE = open('/etc/passwd').read()\n",
        "OUTPUT_DIR = os.environ['HOME']\n",
        "TARGET_USERNAMES = [__import__('os').getpid()]\n",
    ])
    def test_non_literal_values_are_refused(self, im_module, hostile):
        with pytest.raises(ValueError):
            im_module.parse_config_content(hostile, "<hostile>")

    # Unknown setting names are refused so a typo cannot silently do nothing
    def test_unknown_setting_is_refused(self, im_module):
        with pytest.raises(ValueError, match="not a recognized setting"):
            im_module.parse_config_content("TOTALLY_MADE_UP = 1\n", "<unknown>")

    # A config written by an older version still loads when it carries settings a later release removed
    def test_retired_settings_are_ignored(self, im_module):
        parsed = im_module.parse_config_content("DISCORD_MAX_FIELDS = 25\nINSTA_CHECK_INTERVAL = 3600\n", "<legacy>")

        assert parsed == {"INSTA_CHECK_INTERVAL": 3600}

    # The caller can collect which retired settings were ignored so it can tell the user
    def test_retired_settings_are_reported_to_the_caller(self, im_module):
        retired = []
        im_module.parse_config_content("DISCORD_MAX_FIELDS = 25\nDISCORD_EMBED_TITLE_LIMIT = 256\n", "<legacy>", retired)

        assert retired == ["DISCORD_MAX_FIELDS", "DISCORD_EMBED_TITLE_LIMIT"]

    # Allowing retired names must not weaken rejection of any other unknown setting
    def test_retired_allowance_does_not_accept_other_unknown_names(self, im_module):
        assert im_module.RETIRED_CONFIG_SETTINGS.isdisjoint(im_module.config_allowed_names())
        with pytest.raises(ValueError, match="not a recognized setting"):
            im_module.parse_config_content("DISCORD_TYPO_LIMIT = 1\n", "<unknown>")

    # Ordinary settings of every supported literal shape load correctly
    def test_supported_literals_are_parsed(self, im_module):
        parsed = im_module.parse_config_content(
            "INSTA_CHECK_INTERVAL = 3600\n"
            "RANDOM_SLEEP_DIFF_LOW = -900\n"
            "TIME_FORMAT_12H = True\n"
            "CSV_FILE = 'out.csv'\n"
            "TARGET_USERNAMES = ['alice', 'bob']\n"
            "COLOR_THEME = {'header': 'bright_cyan'}\n"
            "PRIVACY_SUBSTITUTIONS = [('a.user', 'XXX')]\n"
            "NEXT_OPERATION_DELAY = 0.7\n",
            "<good>",
        )
        assert parsed["INSTA_CHECK_INTERVAL"] == 3600
        assert parsed["RANDOM_SLEEP_DIFF_LOW"] == -900
        assert parsed["TIME_FORMAT_12H"] is True
        assert parsed["TARGET_USERNAMES"] == ["alice", "bob"]
        assert parsed["COLOR_THEME"] == {"header": "bright_cyan"}
        assert parsed["PRIVACY_SUBSTITUTIONS"] == [("a.user", "XXX")]
        assert parsed["NEXT_OPERATION_DELAY"] == 0.7

    # Comments and blank lines stay allowed so generated configs remain readable
    def test_comments_and_blank_lines_are_allowed(self, im_module):
        parsed = im_module.parse_config_content("# a comment\n\nINSTA_CHECK_INTERVAL = 5400  # trailing\n", "<comments>")

        assert parsed == {"INSTA_CHECK_INTERVAL": 5400}

    # The built-in template is itself a valid restricted config
    def test_builtin_template_parses(self, im_module):
        parsed = im_module.parse_config_content(im_module.CONFIG_BLOCK, "<built-in>")

        assert len(parsed) > 100
        assert "INSTA_CHECK_INTERVAL" in parsed and "WEBHOOK_TEMPLATE" in parsed

    # A generated config round-trips through the loader that will read it back
    def test_generated_config_round_trips(self, im_module):
        rendered = im_module.generate_config_with_current_values()

        assert len(im_module.parse_config_content(rendered, "<generated>")) > 100

    # Advanced settings documented outside the template stay loadable
    @pytest.mark.parametrize("name,value", [("FLAGGED_PROBE_USERNAME", "'instagram'"), ("FLAGGED_PROBE_TTL", "600")])
    def test_documented_extra_settings_are_allowed(self, im_module, name, value):
        assert name in im_module.parse_config_content(f"{name} = {value}\n", "<extras>")

    # Every documented extra names a real module setting, so the allowlist cannot drift
    def test_extra_config_keys_exist_as_settings(self, im_module):
        for name in im_module.EXTRA_CONFIG_KEYS:
            assert hasattr(im_module, name)


class TestLoadConfigFile:
    # A rejected config applies nothing at all, so a bad file cannot half-configure the tool
    def test_rejected_config_applies_no_values(self, im_module, tmp_path, capsys):
        config = tmp_path / "instagram_monitor.conf"
        config.write_text("INSTA_CHECK_INTERVAL = 1234\nimport os\nCSV_FILE = 'x.csv'\n", encoding="utf-8")
        namespace = {}

        assert im_module.load_config_file(str(config), namespace) is False
        assert namespace == {}
        assert "only 'NAME = value' settings are allowed" in capsys.readouterr().out

    # A valid config is applied to the namespace
    def test_valid_config_is_applied(self, im_module, tmp_path):
        config = tmp_path / "instagram_monitor.conf"
        config.write_text("INSTA_CHECK_INTERVAL = 1234\nCSV_FILE = 'x.csv'\n", encoding="utf-8")
        namespace = {}

        assert im_module.load_config_file(str(config), namespace) is True
        assert namespace == {"INSTA_CHECK_INTERVAL": 1234, "CSV_FILE": "x.csv"}

    # An unreadable file is reported instead of raising
    def test_missing_file_is_reported(self, im_module, tmp_path, capsys):
        assert im_module.load_config_file(str(tmp_path / "absent.conf"), {}) is False
        assert "Error loading config file" in capsys.readouterr().out

    # A Windows path written with single backslashes still loads, with a warning
    def test_unescaped_windows_path_is_recovered(self, im_module, tmp_path, capsys):
        config = tmp_path / "instagram_monitor.conf"
        config.write_text('OUTPUT_DIR = "C:\\Users\\monitor"\n', encoding="utf-8")
        namespace = {}

        assert im_module.load_config_file(str(config), namespace) is True
        assert namespace["OUTPUT_DIR"] == "C:\\Users\\monitor"
        assert "read literally" in capsys.readouterr().out

    # A full-screen dashboard retains config upgrade guidance after replacing the normal terminal view
    def test_retired_setting_note_is_retained_in_terminal_dashboard(self, im_module, monkeypatch):
        activities = []
        monkeypatch.setattr(im_module, "DASHBOARD_ENABLED", True)
        monkeypatch.setattr(im_module, "RICH_AVAILABLE", True)
        monkeypatch.setattr(im_module, "log_activity", lambda message, **kwargs: activities.append((message, kwargs)))

        im_module.retain_retired_settings_in_dashboard(["DISCORD_MAX_FIELDS"], "/data/instagram_monitor.conf")

        assert activities == [("Configuration upgrade note: DISCORD_MAX_FIELDS was removed in a later version and is ignored. You can delete it from /data/instagram_monitor.conf.", {"level": "warning"})]

    # Text mode keeps using its existing terminal note without adding a dashboard activity
    def test_retired_setting_note_is_not_duplicated_without_terminal_dashboard(self, im_module, monkeypatch):
        activities = []
        monkeypatch.setattr(im_module, "DASHBOARD_ENABLED", False)
        monkeypatch.setattr(im_module, "RICH_AVAILABLE", True)
        monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: activities.append((args, kwargs)))

        im_module.retain_retired_settings_in_dashboard(["DISCORD_MAX_FIELDS"], "/data/instagram_monitor.conf")

        assert activities == []

    # The normal CLI passes captured retired settings into the dashboard retention path after resolving --dashboard
    def test_cli_retains_retired_setting_after_resolving_dashboard(self, im_module, monkeypatch, tmp_path):
        config = tmp_path / "instagram_monitor.conf"
        config.write_text("DISCORD_MAX_FIELDS = 25\nLOCAL_TIMEZONE = 'UTC'\n", encoding="utf-8")
        retainer = Mock(side_effect=SystemExit(99))
        monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py", "target.user", "--dashboard", "--config-file", str(config), "--env-file", "none", "--no-color"])
        monkeypatch.setattr(im_module, "clear_screen", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "check_internet", lambda: True)
        monkeypatch.setattr(im_module, "retain_retired_settings_in_dashboard", retainer)

        with pytest.raises(SystemExit) as exc:
            im_module.run_main()

        assert exc.value.code == 99
        assert im_module.DASHBOARD_ENABLED is True
        retainer.assert_called_once_with(["DISCORD_MAX_FIELDS"], str(config))


class TestEarlyOutputConfig:
    # Screen clearing happens before arguments are parsed, so the config value must still win
    def test_clear_screen_from_config_is_applied_early(self, im_module, monkeypatch, tmp_path):
        config = tmp_path / "instagram_monitor.conf"
        config.write_text("CLEAR_SCREEN = False\nCOLORED_OUTPUT = False\n", encoding="utf-8")
        monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py", "--config-file", str(config)])
        monkeypatch.setattr(im_module, "CLEAR_SCREEN", True)
        monkeypatch.setattr(im_module, "COLORED_OUTPUT", True)

        im_module.apply_early_output_config()

        assert im_module.CLEAR_SCREEN is False
        assert im_module.COLORED_OUTPUT is False

    # A config that does not mention these settings leaves the built-in defaults alone
    def test_absent_settings_keep_defaults(self, im_module, monkeypatch, tmp_path):
        config = tmp_path / "instagram_monitor.conf"
        config.write_text("INSTA_CHECK_INTERVAL = 5400\n", encoding="utf-8")
        monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py", "--config-file", str(config)])
        monkeypatch.setattr(im_module, "CLEAR_SCREEN", True)

        im_module.apply_early_output_config()

        assert im_module.CLEAR_SCREEN is True

    # A broken config stays silent here so the later load can report it with full detail
    def test_broken_config_is_ignored_early(self, im_module, monkeypatch, tmp_path, capsys):
        config = tmp_path / "instagram_monitor.conf"
        config.write_text("import os\n", encoding="utf-8")
        monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py", "--config-file", str(config)])
        monkeypatch.setattr(im_module, "CLEAR_SCREEN", True)

        im_module.apply_early_output_config()

        assert im_module.CLEAR_SCREEN is True
        assert capsys.readouterr().out == ""

    # The config path is recovered from raw arguments in both accepted spellings
    @pytest.mark.parametrize("arguments,expected", [
        (["--config-file", "a.conf"], "a.conf"),
        (["--config-file=b.conf"], "b.conf"),
        (["target", "--config-file", "c.conf", "--debug"], "c.conf"),
        (["--debug"], None),
        ([], None),
    ])
    def test_config_file_argument_is_recovered(self, im_module, arguments, expected):
        assert im_module.early_config_file_argument(arguments) == expected
