"""Tests for the staged setup wizard and its safety gates."""

import builtins
import os
import subprocess
import sys
import tempfile
import types
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock

import signal
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = PROJECT_ROOT / "local" / "test_artifacts"


# Creates a disposable setup destination below the project local directory
@contextmanager
def make_test_directory():
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    previous_directory = Path.cwd()
    with tempfile.TemporaryDirectory(dir=ARTIFACT_ROOT) as directory_name:
        try:
            yield directory_name
        finally:
            os.chdir(previous_directory)


# Registers setup-mutated globals with monkeypatch so each test restores them
def protect_setup_globals(im_module, monkeypatch):
    names = ("CLI_CONFIG_PATH", "DOTENV_FILE", "SESSION_USERNAME", "SESSION_PASSWORD", "SKIP_SESSION", "TARGET_USERNAMES", "WEB_DASHBOARD_ENABLED", "DASHBOARD_ENABLED", "WEB_DASHBOARD_HOST", "STATUS_NOTIFICATION", "WEBHOOK_ENABLED", "WEBHOOK_PROVIDER", "WEBHOOK_STATUS_NOTIFICATION", "WEBHOOK_URL", "NTFY_ACCESS_TOKEN")
    for name in names:
        monkeypatch.setattr(im_module, name, getattr(im_module, name), raising=False)


# Builds a minimal editable state for one setup-section unit test
def make_setup_state(im_module, directory: Path):
    baseline = dict(vars(im_module))
    return im_module.WizardSetupState(directory / "instagram_monitor.conf", directory / ".env", baseline, dict(baseline), {}, ["target.user"], True, False, "no-login", "", None, None, False, False, False, False)


# Verifies duration input accepts bare seconds plus single, decimal and compound unit forms
def test_duration_helper_accepts_supported_units(im_module, monkeypatch):
    for value, expected in (("120", 120), ("120s", 120), ("2m", 120), ("2 mins", 120), ("1h", 3600), ("1.5h", 5400), ("1h 30m", 5400), ("1 day", 86400)):
        monkeypatch.setattr(im_module, "_wizard_input", Mock(return_value=value))
        assert im_module._wizard_ask_duration("Polling interval", 5400) == expected


# Verifies regular setup accepts unit-based polling intervals and stores seconds
def test_polling_section_uses_duration_input(im_module, monkeypatch):
    with make_test_directory() as directory_name:
        state = make_setup_state(im_module, Path(directory_name))
        duration_mock = Mock(return_value=7200)
        monkeypatch.setattr(im_module, "_wizard_ask_duration", duration_mock)
        im_module._wizard_collect_polling_section(state)
        assert state.config_values["INSTA_CHECK_INTERVAL"] == 7200
        duration_mock.assert_called_once_with("Instagram polling interval (seconds or use s/m/h/d)", im_module.INSTA_CHECK_INTERVAL)


class TestTargetCollection:
    # Verifies Web Dashboard setup accepts no initial targets and skips the persistence question
    def test_web_dashboard_setup_accepts_an_empty_target_list(self, im_module, monkeypatch, capsys):
        with make_test_directory() as directory_name:
            state = make_setup_state(im_module, Path(directory_name))
            state.targets = []
            ask_text = Mock(side_effect=[""])
            ask_yes_no = Mock(side_effect=AssertionError("persistence prompt should be skipped for no targets"))
            monkeypatch.setattr(im_module, "_wizard_ask_text", ask_text)
            monkeypatch.setattr(im_module, "_wizard_ask_yes_no", ask_yes_no)

            im_module._wizard_collect_target_section(state, allow_empty=True)

            assert state.targets == []
            assert state.persist_targets is False
            assert state.config_values["TARGET_USERNAMES"] == []
            ask_text.assert_called_once_with("Which Instagram account(s) or target(s) do you want to monitor? (leave empty to add them in the Web Dashboard)", default="", required=False)
            ask_yes_no.assert_not_called()
            assert "No initial targets selected. Add them later in the Web Dashboard." in capsys.readouterr().out

    # Verifies an answer holding no usable name says so, so a rejected answer is not silently asked again
    def test_an_answer_without_a_usable_name_is_explained(self, im_module, monkeypatch, capsys):
        with make_test_directory() as directory_name:
            state = make_setup_state(im_module, Path(directory_name))
            monkeypatch.setattr(im_module, "_wizard_ask_text", Mock(side_effect=[",", "target.user"]))
            monkeypatch.setattr(im_module, "_wizard_ask_yes_no", Mock(side_effect=[False, True]))

            im_module._wizard_collect_target_section(state, allow_empty=False)

            assert state.targets == ["target.user"]
            assert "Enter one or more Instagram usernames separated by commas." in capsys.readouterr().out

    # Verifies a required target can be abandoned, so the question is not a loop the user can only leave with Ctrl+C
    def test_a_required_target_can_be_abandoned(self, im_module, monkeypatch, capsys):
        with make_test_directory() as directory_name:
            state = make_setup_state(im_module, Path(directory_name))
            monkeypatch.setattr(im_module, "_wizard_ask_text", Mock(side_effect=[","]))
            monkeypatch.setattr(im_module, "_wizard_ask_yes_no", Mock(side_effect=[True]))

            im_module._wizard_collect_target_section(state, allow_empty=False)

            assert state.targets == []
            assert state.config_values["TARGET_USERNAMES"] == []
            assert "No initial targets selected. Add them later by running --setup again." in capsys.readouterr().out

    # Verifies non-Web interfaces collect a required target after an initially empty answer
    @pytest.mark.parametrize("interface", [1, 2])
    def test_non_web_interface_requires_a_target(self, im_module, monkeypatch, interface):
        with make_test_directory() as directory_name:
            state = make_setup_state(im_module, Path(directory_name))
            state.targets = []
            collect_targets = Mock(side_effect=lambda current_state, allow_empty: current_state.targets.append("target.user"))
            monkeypatch.setattr(im_module, "_wizard_ask_choice", lambda *args, **kwargs: interface)
            monkeypatch.setattr(im_module, "_wizard_collect_target_section", collect_targets)

            im_module._wizard_collect_interface_section(state, "manual")

            collect_targets.assert_called_once_with(state, allow_empty=False)
            assert state.targets == ["target.user"]

    # Verifies target editing preserves the selected interface's empty-target rule
    @pytest.mark.parametrize("want_web,allow_empty", [(True, True), (False, False)])
    def test_target_editor_uses_the_interface_empty_target_rule(self, im_module, monkeypatch, want_web, allow_empty):
        with make_test_directory() as directory_name:
            state = make_setup_state(im_module, Path(directory_name))
            state.want_web = want_web
            collect_targets = Mock()
            monkeypatch.setattr(im_module, "_wizard_ask_choice", lambda *args, **kwargs: 0)
            monkeypatch.setattr(im_module, "_wizard_collect_target_section", collect_targets)

            im_module._wizard_edit_setup_section(state, "manual")

            collect_targets.assert_called_once_with(state, allow_empty=allow_empty)


class TestEditableReview:
    def test_discard_leaves_destination_files_unchanged(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            directory = Path(directory_name)
            config_path = directory / "instagram_monitor.conf"
            env_path = directory / ".env"
            answers = iter([True, False, False, True])
            choices = iter([0, 2, 2])
            protect_setup_globals(im_module, monkeypatch)
            monkeypatch.setattr(im_module.sys, "stdin", Mock(isatty=lambda: True))
            monkeypatch.setattr(im_module, "_wizard_install_method", lambda: "manual")
            monkeypatch.setattr(im_module, "_wizard_ask_text", lambda *args, **kwargs: "target.user")
            monkeypatch.setattr(im_module, "_wizard_ask_duration", lambda question, default: default)
            monkeypatch.setattr(im_module, "_wizard_ask_yes_no", lambda *args, **kwargs: next(answers))
            monkeypatch.setattr(im_module, "_wizard_ask_choice", lambda *args, **kwargs: next(choices))
            monkeypatch.setattr(im_module, "_wizard_collect_output_section", lambda state: None)

            with pytest.raises(SystemExit) as error:
                im_module.run_setup_wizard(config_file=config_path, env_file=env_path)

            assert error.value.code == 1
            assert not config_path.exists()
            assert not env_path.exists()

    def test_target_section_can_be_edited_before_save(self, im_module, monkeypatch, capsys):
        with make_test_directory() as directory_name:
            directory = Path(directory_name)
            config_path = directory / "instagram_monitor.conf"
            env_path = directory / "custom secrets.env"
            answers = iter([True, False, False, False, False, False])
            choices = iter([0, 2, 1, 0, 0])
            targets = iter(["first.target", "second.target"])
            protect_setup_globals(im_module, monkeypatch)
            monkeypatch.setattr(im_module.sys, "stdin", Mock(isatty=lambda: True))
            monkeypatch.setattr(im_module, "_wizard_install_method", lambda: "manual")
            monkeypatch.setattr(im_module, "_wizard_ask_text", lambda *args, **kwargs: next(targets))
            monkeypatch.setattr(im_module, "_wizard_ask_duration", lambda question, default: default)
            monkeypatch.setattr(im_module, "_wizard_ask_yes_no", lambda *args, **kwargs: next(answers))
            monkeypatch.setattr(im_module, "_wizard_ask_choice", lambda *args, **kwargs: next(choices))
            monkeypatch.setattr(im_module, "run_doctor", Mock(side_effect=AssertionError("doctor called")))
            monkeypatch.setattr(im_module, "_wizard_collect_output_section", lambda state: None)

            with pytest.raises(SystemExit) as error:
                im_module.run_setup_wizard(config_file=config_path, env_file=env_path)

            assert error.value.code == 0
            namespace = {}
            exec(config_path.read_text(encoding="utf-8"), namespace)
            assert namespace["TARGET_USERNAMES"] == []
            assert namespace["DOTENV_FILE"] == str(env_path.resolve())
            output = capsys.readouterr().out
            assert "second.target" in output
            # No secret was entered, so nothing was written to the dotenv and no printed command names it
            assert not env_path.exists()
            assert "--env-file" not in output


class TestBrowserOnboarding:
    def test_chromium_is_a_separate_option_with_one_step_install(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            state = make_setup_state(im_module, Path(directory_name))
            install_mock = Mock(return_value=True)
            choices = iter([2, 0])
            monkeypatch.setattr(im_module, "system", lambda: "Darwin")
            monkeypatch.setattr(im_module, "_wizard_chromium_dependency_available", lambda: False)
            monkeypatch.setattr(im_module, "_wizard_install_chromium_dependency", install_mock)
            monkeypatch.setattr(im_module, "_wizard_ask_choice", lambda *args, **kwargs: next(choices))
            monkeypatch.setattr(im_module, "_wizard_ask_yes_no", lambda *args, **kwargs: True)
            monkeypatch.setattr(im_module, "_wizard_ask_text", lambda *args, **kwargs: "")

            im_module._wizard_collect_login_section(state, "manual")

            install_mock.assert_called_once_with("manual")
            assert state.login_method == "chromium"
            assert state.import_browser == "chrome"
            assert state.logged_in is True

    def test_docker_firefox_is_deferred_and_collects_host_layout(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            state = make_setup_state(im_module, Path(directory_name))
            captured = []
            choices = iter([1, 0])
            # Selects Firefox then macOS while recording the displayed choices
            def choose(question, options, default_index=0):
                captured.append((question, options))
                return next(choices)
            monkeypatch.setattr(im_module, "_wizard_ask_choice", choose)
            monkeypatch.setattr(im_module, "_wizard_ask_text", lambda *args, **kwargs: "login.user")

            im_module._wizard_collect_login_section(state, "docker")

            assert captured[0][1][1][0] == "Import from Firefox after setup, recommended"
            assert captured[1][0] == "Which host environment runs Docker?"
            assert state.import_browser == "firefox"
            assert state.container_host == "macos"

    @pytest.mark.parametrize("choice,expected", [(0, "macos"), (1, "linux"), (2, "linux-snap"), (3, "linux-flatpak"), (4, "windows-powershell"), (5, "windows-cmd")])
    def test_container_firefox_host_selection(self, im_module, monkeypatch, choice, expected):
        monkeypatch.setattr(im_module, "_wizard_ask_choice", lambda *args, **kwargs: choice)
        assert im_module._wizard_select_container_firefox_host() == expected

    def test_unsupported_container_firefox_host_is_not_assumed(self, im_module, monkeypatch, capsys):
        monkeypatch.setattr(im_module, "_wizard_ask_choice", lambda *args, **kwargs: 6)
        assert im_module._wizard_select_container_firefox_host() is None
        assert "not currently available for this host" in capsys.readouterr().out


class TestPromptWording:
    # Verifies the wizard explains setup and paths before checking an existing configuration
    def test_intro_precedes_existing_config_confirmation(self, im_module, monkeypatch, capsys):
        with make_test_directory() as directory_name:
            directory = Path(directory_name)
            config_path = directory / "instagram_monitor.conf"
            env_path = directory / ".env"
            choose_destination = Mock(side_effect=SystemExit(23))
            monkeypatch.setattr(im_module.sys, "stdin", Mock(isatty=lambda: True))
            monkeypatch.setattr(im_module, "_wizard_install_method", lambda: "manual")
            monkeypatch.setattr(im_module, "_wizard_choose_config_destination", choose_destination)

            with pytest.raises(SystemExit) as error:
                im_module.run_setup_wizard(config_file=config_path, env_file=env_path)

            assert error.value.code == 23
            choose_destination.assert_called_once_with(config_path.resolve())
            output = capsys.readouterr().out
            assert "Setup Wizard\n\nThis asks a few questions" in output
            assert "Secrets go to the dotenv file. Non-secret settings go to the config file." in output
            assert "No-login mode is simplest. Firefox session import is recommended for full monitoring." in output
            assert f"Session login guide: {im_module.SESSION_IMPORT_GUIDE_URL}" in output
            assert f"Detected install method: manual\nConfiguration:          {config_path.resolve()}\nDotenv:                 {env_path.resolve()}\n" in output

    def test_webhook_section_names_discord_and_ntfy(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            state = make_setup_state(im_module, Path(directory_name))
            questions = []
            # Captures the webhook question and declines setup
            def ask_yes_no(question, default=True):
                questions.append(question)
                return False
            monkeypatch.setattr(im_module, "_wizard_ask_yes_no", ask_yes_no)

            im_module._wizard_collect_webhook_section(state)

            assert questions == ["Set up webhook alerts (Discord, ntfy etc.)?"]

    def test_email_section_asks_the_mail_server_questions_in_the_shared_order(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            state = make_setup_state(im_module, Path(directory_name))
            questions = []
            answers = iter([True, True])
            texts = iter(["smtp.example.test", "587", "smtp-user", "from@example.test", "to@example.test"])
            # Captures every yes or no question while returning scripted answers
            def ask_yes_no(question, default=True):
                questions.append(question)
                return next(answers)
            # Records the text prompts in the order the wizard asks them
            def ask_text(question, default="", required=False):
                questions.append(question)
                return next(texts)
            monkeypatch.setattr(im_module, "_wizard_ask_yes_no", ask_yes_no)
            monkeypatch.setattr(im_module, "_wizard_ask_text", ask_text)
            monkeypatch.setattr(im_module, "_wizard_ask_secret", lambda *args, **kwargs: "private-password")
            monkeypatch.setattr(im_module, "_wizard_ask_choice", lambda question, options, default_index=0: questions.append(question) or 0)

            im_module._wizard_collect_email_section(state)

            assert questions == ["Configure email notifications?", "SMTP host", "SMTP port", "Enable TLS/SSL for SMTP?", "SMTP username", "Sender email", "Receiver email", "Which email notifications should be enabled?"]
            assert state.config_values["SMTP_SSL"] is True


class TestSectionOrder:
    # Verifies initial setup collects polling before login with one blank line
    def test_initial_setup_matches_spotify_notification_order(self, im_module, monkeypatch, capsys):
        with make_test_directory() as directory_name:
            directory = Path(directory_name)
            calls = []
            protect_setup_globals(im_module, monkeypatch)
            monkeypatch.setattr(im_module.sys, "stdin", Mock(isatty=lambda: True))
            monkeypatch.setattr(im_module, "_wizard_install_method", lambda: "manual")
            monkeypatch.setattr(im_module, "_wizard_collect_target_section", lambda state, allow_empty=False: calls.append(f"target:{allow_empty}"))
            monkeypatch.setattr(im_module, "_wizard_collect_login_section", lambda state, method: (calls.append("login"), print("\nHow do you want to access Instagram?")))
            monkeypatch.setattr(im_module, "_wizard_collect_polling_section", lambda state: (calls.append("polling"), print("Instagram polling interval [5400s - 1h 30m]:")))
            monkeypatch.setattr(im_module, "_wizard_collect_interface_section", lambda state, method: calls.append("interface"))
            monkeypatch.setattr(im_module, "_wizard_collect_email_section", lambda state: calls.append("email"))
            monkeypatch.setattr(im_module, "_wizard_collect_webhook_section", lambda state: calls.append("webhook"))
            monkeypatch.setattr(im_module, "_wizard_collect_output_section", lambda state: calls.append("output"))
            monkeypatch.setattr(im_module, "_wizard_review_setup", lambda state, method: calls.append("review") or False)

            with pytest.raises(SystemExit) as error:
                im_module.run_setup_wizard(config_file=directory / "instagram_monitor.conf", env_file=directory / ".env")

            output = capsys.readouterr().out
            assert error.value.code == 1
            assert calls == ["target:True", "polling", "login", "interface", "email", "webhook", "output", "review"]
            assert "Instagram polling interval [5400s - 1h 30m]:\n\nHow do you want to access Instagram?" in output
            assert "Instagram polling interval [5400s - 1h 30m]:\n\n\nHow do you want to access Instagram?" not in output

    # Verifies a changed dotenv destination recollects email before webhook settings
    def test_destination_change_matches_spotify_notification_order(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            directory = Path(directory_name)
            state = make_setup_state(im_module, directory)
            calls = []
            destinations = iter([str(state.config_path), str(directory / "replacement.env")])
            monkeypatch.setattr(im_module, "_wizard_ask_text", lambda *args, **kwargs: next(destinations))
            monkeypatch.setattr(im_module, "_wizard_collect_login_section", lambda current_state, method: calls.append("login"))
            monkeypatch.setattr(im_module, "_wizard_collect_email_section", lambda current_state: calls.append("email"))
            monkeypatch.setattr(im_module, "_wizard_collect_webhook_section", lambda current_state: calls.append("webhook"))

            im_module._wizard_collect_destination_section(state, "manual")

            assert calls == ["login", "email", "webhook"]

    # Verifies the setup summary and editor put polling before login
    def test_editor_matches_spotify_notification_order(self, im_module, monkeypatch, capsys):
        with make_test_directory() as directory_name:
            state = make_setup_state(im_module, Path(directory_name))
            labels = []
            monkeypatch.setattr(im_module, "_wizard_ask_choice", lambda question, options, default_index=0: labels.extend(label for label, _ in options) or 8)

            im_module._wizard_print_setup_summary(state, "manual")
            summary = capsys.readouterr().out
            im_module._wizard_edit_setup_section(state, "manual")

            assert summary.index("Polling interval:") < summary.index("Login:")
            assert labels == ["Targets and persistence", "Polling interval", "Login and session", "Interface", "Email alerts", "Webhook alerts", "Output files", "File destinations", "Return to summary"]


class TestWizardSafetyGates:
    def test_declined_local_browser_import_without_doctor_does_not_offer_start(self, im_module, monkeypatch, capsys):
        with make_test_directory() as directory_name:
            directory = Path(directory_name)
            questions = []
            answers = iter([False, False])
            protect_setup_globals(im_module, monkeypatch)
            monkeypatch.setattr(im_module.sys, "stdin", Mock(isatty=lambda: True))
            monkeypatch.setattr(im_module, "_wizard_install_method", lambda: "pip")
            monkeypatch.setattr(im_module, "_wizard_collect_target_section", lambda state, allow_empty=False: state.targets.append("target.user"))
            monkeypatch.setattr(im_module, "_wizard_collect_login_section", lambda state, method: (setattr(state, "logged_in", True), setattr(state, "login_method", "firefox"), setattr(state, "session_username", "login.user"), setattr(state, "import_browser", "firefox")))
            monkeypatch.setattr(im_module, "_wizard_collect_polling_section", lambda state: None)
            monkeypatch.setattr(im_module, "_wizard_collect_interface_section", lambda state, method: None)
            monkeypatch.setattr(im_module, "_wizard_collect_email_section", lambda state: None)
            monkeypatch.setattr(im_module, "_wizard_collect_webhook_section", lambda state: None)
            monkeypatch.setattr(im_module, "_wizard_collect_output_section", lambda state: None)
            monkeypatch.setattr(im_module, "_wizard_review_setup", lambda state, method: True)
            monkeypatch.setattr(im_module, "run_doctor", Mock(side_effect=AssertionError("doctor ran")))
            monkeypatch.setattr(im_module, "_wizard_launch_monitor", Mock(side_effect=AssertionError("monitor started")))
            # Captures the declined import and Doctor prompts while rejecting any unexpected start prompt
            def ask_yes_no(question, default=True):
                questions.append(question)
                return next(answers)
            monkeypatch.setattr(im_module, "_wizard_ask_yes_no", ask_yes_no)

            with pytest.raises(SystemExit) as error:
                im_module.run_setup_wizard(config_file=directory / "instagram_monitor.conf", env_file=directory / ".env")

            assert error.value.code == 0
            assert all(not question.startswith("Start monitoring now?") for question in questions)
            assert "Monitoring was not offered because browser import has not completed" in capsys.readouterr().out

    def test_deferred_macos_firefox_setup_skips_doctor_and_orders_commands(self, im_module, monkeypatch, capsys):
        with make_test_directory() as directory_name:
            directory = Path(directory_name)
            monkeypatch.chdir(directory)
            protect_setup_globals(im_module, monkeypatch)
            monkeypatch.setattr(im_module.sys, "stdin", Mock(isatty=lambda: True))
            monkeypatch.setattr(im_module, "_wizard_install_method", lambda: "docker")
            monkeypatch.setattr(im_module, "_wizard_validate_destination", lambda method, path, label: Path(path).expanduser().resolve())
            monkeypatch.setattr(im_module, "_wizard_collect_target_section", lambda state, allow_empty=False: state.targets.append("target.user"))
            monkeypatch.setattr(im_module, "_wizard_collect_login_section", lambda state, method: (setattr(state, "logged_in", True), setattr(state, "login_method", "firefox"), setattr(state, "session_username", "login.user"), setattr(state, "import_browser", "firefox"), setattr(state, "container_host", "macos")))
            monkeypatch.setattr(im_module, "_wizard_collect_polling_section", lambda state: None)
            monkeypatch.setattr(im_module, "_wizard_collect_interface_section", lambda state, method: None)
            monkeypatch.setattr(im_module, "_wizard_collect_email_section", lambda state: None)
            monkeypatch.setattr(im_module, "_wizard_collect_webhook_section", lambda state: None)
            monkeypatch.setattr(im_module, "_wizard_collect_output_section", lambda state: None)
            monkeypatch.setattr(im_module, "_wizard_review_setup", lambda state, method: True)
            ask_mock = Mock(side_effect=AssertionError("Doctor prompt was offered before Firefox import"))
            monkeypatch.setattr(im_module, "_wizard_ask_yes_no", ask_mock)
            doctor_mock = Mock(side_effect=AssertionError("Doctor ran before Firefox import"))
            monkeypatch.setattr(im_module, "run_doctor", doctor_mock)

            with pytest.raises(SystemExit) as error:
                im_module.run_setup_wizard(config_file=directory / "instagram_monitor.conf", env_file=directory / ".env")

            assert error.value.code == 0
            assert not (directory / ".env").exists()
            ask_mock.assert_not_called()
            doctor_mock.assert_not_called()
            output = capsys.readouterr().out
            prerequisite_index = output.index("Before import, open https://www.instagram.com/ in Firefox on the host")
            import_index = output.index("Import Instagram login from Firefox on macOS:")
            doctor_index = output.index("After the import succeeds, check setup:")
            start_index = output.index("After Doctor passes, start monitoring:")
            assert prerequisite_index < import_index < doctor_index < start_index
            assert '${HOME}/Library/Application Support/Firefox/Profiles:/home/instagram/.mozilla/firefox:ro' in output
            assert "--config-file /data/" in output
            assert "instagram_monitor.conf" in output
            assert "--user" not in output
            assert "Run doctor now?" not in output

    @pytest.mark.parametrize("method,port_option", [("docker", "-p 127.0.0.1:8000:8000"), ("compose", "--service-ports")])
    def test_browser_import_keeps_history_and_repeats_dashboard_ready_commands(self, im_module, monkeypatch, capsys, method, port_option):
        with make_test_directory() as directory_name:
            directory = Path(directory_name)
            monkeypatch.chdir(directory)
            config_path = directory / "instagram_monitor.conf"
            env_path = directory / ".env"
            cookie_path = directory / "cookies.sqlite"
            config_path.write_text(f'TARGET_USERNAMES = ["target.user"]\nWEB_DASHBOARD_ENABLED = True\nDOTENV_FILE = {str(env_path)!r}\n', encoding="utf-8")
            env_path.write_text("", encoding="utf-8")
            cookie_path.write_text("", encoding="utf-8")
            protect_setup_globals(im_module, monkeypatch)
            monkeypatch.setattr(im_module, "_wizard_install_method", lambda: method)
            monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py", "--import-browser-session", "--browser", "firefox", "--config-file", str(config_path), "--env-file", str(env_path), "--no-color"])
            monkeypatch.setattr(im_module.signal, "signal", lambda *args, **kwargs: None)
            clear_mock = Mock()
            monkeypatch.setattr(im_module, "clear_screen", clear_mock)
            monkeypatch.setattr(im_module, "print_startup_banner", lambda: None)
            monkeypatch.setattr(im_module, "get_firefox_cookiefile", lambda: str(cookie_path))
            import_mock = Mock(return_value="login.user")
            monkeypatch.setattr(im_module, "import_session", import_mock)

            with pytest.raises(SystemExit) as error:
                im_module.run_main()

            assert error.value.code == 0
            clear_mock.assert_called_once_with(False)
            import_mock.assert_called_once()
            output = capsys.readouterr().out
            assert "Check setup again:" in output
            assert "After Doctor passes, start monitoring:" in output
            doctor_output, monitor_output = output.split("After Doctor passes, start monitoring:", 1)
            assert "--doctor" in doctor_output
            assert port_option not in doctor_output
            assert port_option in monitor_output

    def test_bare_launch_reads_saved_targets_before_first_run_decision(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            config_path = Path(directory_name) / "instagram_monitor.conf"
            config_path.write_text('TARGET_USERNAMES = ["saved.target"]\nWEB_DASHBOARD_ENABLED = False\nDOTENV_FILE = "none"\n', encoding="utf-8")
            captured = {}
            protect_setup_globals(im_module, monkeypatch)
            monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py"])
            monkeypatch.setattr(im_module.signal, "signal", lambda *args, **kwargs: None)
            monkeypatch.setattr(im_module, "clear_screen", lambda *args, **kwargs: None)
            monkeypatch.setattr(im_module, "print_startup_banner", lambda: None)
            monkeypatch.setattr(im_module, "init_color_output", lambda *args, **kwargs: None)
            monkeypatch.setattr(im_module, "find_config_file", lambda path=None: str(config_path))
            # Records the effective values then stops before monitoring begins
            def capture_decision(arguments, configured_targets, web_dashboard_enabled):
                captured.update({"arguments": arguments, "targets": configured_targets, "web": web_dashboard_enabled})
                raise RuntimeError("decision captured")
            monkeypatch.setattr(im_module, "_wizard_should_offer_first_run", capture_decision)

            with pytest.raises(RuntimeError, match="decision captured"):
                im_module.run_main()

            assert captured == {"arguments": ["instagram_monitor.py"], "targets": ["saved.target"], "web": False}

    def test_existing_alternate_destination_is_rechecked(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            directory = Path(directory_name)
            first = directory / "first.conf"
            second = directory / "second.conf"
            first.write_text("first\n", encoding="utf-8")
            second.write_text("second\n", encoding="utf-8")
            answers = iter([False, True])
            monkeypatch.setattr(im_module, "_wizard_ask_yes_no", lambda *args, **kwargs: next(answers))
            monkeypatch.setattr(im_module, "_wizard_ask_text", lambda *args, **kwargs: str(second))

            assert im_module._wizard_choose_config_destination(first) == second.resolve()

    def test_dotenv_failure_blocks_doctor_and_start(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            directory = Path(directory_name)
            config_path = directory / "instagram_monitor.conf"
            env_path = directory / ".env"
            answers = iter([True, False, True])
            choices = iter([0, 2, 0, 0, 0])
            protect_setup_globals(im_module, monkeypatch)
            monkeypatch.delenv("WEBHOOK_URL", raising=False)
            monkeypatch.setattr(im_module.sys, "stdin", Mock(isatty=lambda: True))
            monkeypatch.setattr(im_module, "_wizard_install_method", lambda: "manual")
            monkeypatch.setattr(im_module, "_wizard_ask_text", lambda *args, **kwargs: "target.user")
            monkeypatch.setattr(im_module, "_wizard_ask_duration", lambda question, default: default)
            monkeypatch.setattr(im_module, "_wizard_ask_yes_no", lambda *args, **kwargs: next(answers))
            monkeypatch.setattr(im_module, "_wizard_ask_choice", lambda *args, **kwargs: next(choices))
            monkeypatch.setattr(im_module, "_wizard_ask_secret", lambda *args, **kwargs: "https://discord.example.test/hook")
            monkeypatch.setattr(im_module, "_wizard_collect_output_section", lambda state: None)
            monkeypatch.setattr(im_module, "update_dotenv_file", Mock(side_effect=OSError("write failed")))
            monkeypatch.setattr(im_module, "run_doctor", Mock(side_effect=AssertionError("doctor called")))
            monkeypatch.setattr(im_module, "_wizard_launch_monitor", Mock(side_effect=AssertionError("monitor started")))

            with pytest.raises(SystemExit) as error:
                im_module.run_setup_wizard(config_file=config_path, env_file=env_path)

            assert error.value.code == 1
            assert config_path.exists()
            assert not env_path.exists()

    def test_doctor_failure_blocks_start(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            directory = Path(directory_name)
            answers = iter([True, False, False, True])
            choices = iter([0, 2, 0])
            questions = []
            protect_setup_globals(im_module, monkeypatch)
            monkeypatch.setattr(im_module.sys, "stdin", Mock(isatty=lambda: True))
            monkeypatch.setattr(im_module, "_wizard_install_method", lambda: "manual")
            monkeypatch.setattr(im_module, "_wizard_ask_text", lambda *args, **kwargs: "target.user")
            monkeypatch.setattr(im_module, "_wizard_ask_duration", lambda question, default: default)
            # Captures every yes or no question to prove Start is never offered
            def ask_yes_no(question, default=True):
                questions.append(question)
                return next(answers)
            monkeypatch.setattr(im_module, "_wizard_ask_yes_no", ask_yes_no)
            monkeypatch.setattr(im_module, "_wizard_ask_choice", lambda *args, **kwargs: next(choices))
            monkeypatch.setattr(im_module, "_wizard_collect_output_section", lambda state: None)
            monkeypatch.setattr(im_module, "run_doctor", Mock(return_value=2))
            monkeypatch.setattr(im_module, "_wizard_launch_monitor", Mock(side_effect=AssertionError("monitor started")))

            with pytest.raises(SystemExit) as error:
                im_module.run_setup_wizard(config_file=directory / "instagram_monitor.conf", env_file=directory / ".env")

            assert error.value.code == 0
            assert all(not question.startswith("Start monitoring now?") for question in questions)

    def test_standalone_actions_cannot_be_combined(self, im_module, monkeypatch, capsys):
        monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py", "--setup", "--doctor"])
        monkeypatch.setattr(im_module.signal, "signal", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "clear_screen", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "print_startup_banner", lambda: None)

        with pytest.raises(SystemExit) as error:
            im_module.run_main()

        assert error.value.code == 2
        assert "standalone actions cannot be combined: --setup, --doctor" in capsys.readouterr().err

    def test_private_webhook_entry_rejects_runtime_webhook_overrides(self, im_module, monkeypatch, capsys):
        monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py", "--set-webhook-url", "--webhook-url", "https://example.test/hook"])
        monkeypatch.setattr(im_module.signal, "signal", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "clear_screen", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "print_startup_banner", lambda: None)

        with pytest.raises(SystemExit) as error:
            im_module.run_main()

        assert error.value.code == 2
        assert "--set-webhook-url cannot be combined with --webhook-url" in capsys.readouterr().err


# Verifies the output section records the log choice and the CSV destination it was given
def test_the_output_section_records_the_log_and_csv_choices(im_module, monkeypatch):
    with make_test_directory() as directory_name:
        directory = Path(directory_name)
        state = make_setup_state(im_module, directory)
        monkeypatch.setattr(im_module, "_wizard_ask_yes_no", lambda question, default=True: False)
        monkeypatch.setattr(im_module, "_wizard_ask_text", lambda question, default="", required=False: str(directory / "posts.csv"))

        im_module._wizard_collect_output_section(state)

        assert state.config_values["DISABLE_LOGGING"] is True
        assert state.config_values["CSV_FILE"] == str(directory / "posts.csv")


# Verifies a blank CSV answer disables CSV output rather than storing an empty path as a file name
def test_a_blank_csv_answer_disables_csv_output(im_module, monkeypatch):
    with make_test_directory() as directory_name:
        state = make_setup_state(im_module, Path(directory_name))
        monkeypatch.setattr(im_module, "_wizard_ask_yes_no", lambda question, default=True: True)
        monkeypatch.setattr(im_module, "_wizard_ask_text", lambda question, default="", required=False: "")

        im_module._wizard_collect_output_section(state)

        assert state.config_values["DISABLE_LOGGING"] is False
        assert state.config_values["CSV_FILE"] == ""


class TestRejectedAnswerEscape:
    # Verifies the two escape wordings, so a blank answer and a rejected one are never asked the same way
    @pytest.mark.parametrize("consequence, question, answer, expected", [("", "Try entering the webhook URL again?", "y", True), ("", "Try entering the webhook URL again?", "n", False), ("Webhook alerts stay off until one is set", "Continue without the webhook URL? Webhook alerts stay off until one is set", "y", False), ("Webhook alerts stay off until one is set", "Continue without the webhook URL? Webhook alerts stay off until one is set", "n", True)])
    def test_the_escape_wording_matches_the_kind_of_rejection(self, im_module, monkeypatch, consequence, question, answer, expected):
        questions = []
        # Records the escape question while answering it as the case requires
        def ask(prompt):
            questions.append(prompt)
            return answer
        monkeypatch.setattr(im_module, "_wizard_input", ask)

        assert im_module._wizard_offer_retry("webhook URL", consequence) is expected
        assert question in questions[0]

    # Verifies a required answer can be abandoned instead of trapping the wizard in its own loop
    def test_a_required_text_answer_can_be_abandoned(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "_wizard_input", Mock(return_value=""))
        monkeypatch.setattr(im_module, "_wizard_offer_retry", lambda label, consequence="": False)

        assert im_module._wizard_ask_text("SMTP username", required=True) == ""

    # Verifies a retried required answer is still collected
    def test_a_retried_required_text_answer_is_accepted(self, im_module, monkeypatch):
        answers = iter(["", "smtp-user"])
        monkeypatch.setattr(im_module, "_wizard_input", lambda prompt: next(answers))
        monkeypatch.setattr(im_module, "_wizard_offer_retry", lambda label, consequence="": True)

        assert im_module._wizard_ask_text("SMTP username", required=True) == "smtp-user"

    # Verifies the hidden prompt returns a blank secret instead of looping, leaving the decision to its caller
    def test_a_blank_secret_returns_instead_of_looping(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module.getpass, "getpass", Mock(return_value=""))

        assert im_module._wizard_ask_secret("SMTP password") == ""

    # Verifies abandoning any mail server answer switches every email alert off rather than saving half a server
    @pytest.mark.parametrize("abandoned", ["SMTP host", "SMTP username", "Sender email", "Receiver email"])
    def test_an_abandoned_mail_server_answer_switches_email_off(self, im_module, monkeypatch, abandoned):
        with make_test_directory() as directory_name:
            state = make_setup_state(im_module, Path(directory_name))
            state.want_email = True
            state.baseline_values["STATUS_NOTIFICATION"] = True
            state.config_values["STATUS_NOTIFICATION"] = True
            monkeypatch.setattr(im_module, "_wizard_ask_yes_no", lambda question, default=True: True)
            monkeypatch.setattr(im_module, "_wizard_ask_text", lambda question, default="", required=False: "" if question == abandoned else "587" if question == "SMTP port" else "answer@example.test")
            monkeypatch.setattr(im_module, "_wizard_ask_secret", lambda question: "private-password")
            monkeypatch.setattr(im_module, "_wizard_ask_choice", lambda question, options, default_index=0: 0)

            im_module._wizard_collect_email_section(state)

            assert state.want_email is False
            assert state.config_values["STATUS_NOTIFICATION"] is False
            assert state.config_values.get("SMTP_USER") != "answer@example.test"

    # Verifies a blank SMTP password leaves the saved one alone rather than storing an empty secret
    def test_a_blank_smtp_password_is_not_saved(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            state = make_setup_state(im_module, Path(directory_name))
            monkeypatch.setattr(im_module, "_wizard_ask_yes_no", lambda question, default=True: True)
            monkeypatch.setattr(im_module, "_wizard_ask_text", lambda question, default="", required=False: "587" if question == "SMTP port" else "answer@example.test")
            monkeypatch.setattr(im_module, "_wizard_ask_secret", lambda question: "")
            monkeypatch.setattr(im_module, "_wizard_ask_choice", lambda question, options, default_index=0: 0)

            im_module._wizard_collect_email_section(state)

            assert "SMTP_PASSWORD" not in state.secret_updates
            assert state.want_email is True

    # Verifies a webhook URL nobody can supply switches the channel off instead of repeating the prompt
    @pytest.mark.parametrize("entry, consequence_expected", [("", True), ("not-a-url", False)])
    def test_an_unusable_webhook_url_can_be_abandoned(self, im_module, monkeypatch, entry, consequence_expected):
        with make_test_directory() as directory_name:
            state = make_setup_state(im_module, Path(directory_name))
            state.want_webhook = True
            state.baseline_values.update({"WEBHOOK_ENABLED": True, "WEBHOOK_STATUS_NOTIFICATION": True})
            state.config_values.update({"WEBHOOK_ENABLED": True, "WEBHOOK_STATUS_NOTIFICATION": True})
            labels = []
            monkeypatch.setattr(im_module, "_wizard_ask_yes_no", lambda question, default=True: True)
            monkeypatch.setattr(im_module, "_wizard_ask_choice", lambda question, options, default_index=0: 0)
            monkeypatch.setattr(im_module, "_wizard_ask_secret", lambda question: entry)
            # Refuses the escape after recording which wording the wizard offered
            def offer_retry(label, consequence=""):
                labels.append((label, consequence))
                return False
            monkeypatch.setattr(im_module, "_wizard_offer_retry", offer_retry)

            im_module._wizard_collect_webhook_section(state)

            assert labels == [("webhook URL", "Webhook alerts stay off until one is set" if consequence_expected else "")]
            assert state.want_webhook is False
            assert state.config_values["WEBHOOK_ENABLED"] is False
            assert state.config_values["WEBHOOK_STATUS_NOTIFICATION"] is False
            assert "WEBHOOK_URL" not in state.secret_updates

    # Verifies a retried webhook URL is still collected after one unusable entry
    def test_a_retried_webhook_url_is_accepted(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            state = make_setup_state(im_module, Path(directory_name))
            entries = iter(["", "https://discord.com/api/webhooks/1/token"])
            monkeypatch.setattr(im_module, "_wizard_ask_yes_no", lambda question, default=True: True)
            monkeypatch.setattr(im_module, "_wizard_ask_choice", lambda question, options, default_index=0: 0)
            monkeypatch.setattr(im_module, "_wizard_ask_secret", lambda question: next(entries))
            monkeypatch.setattr(im_module, "_wizard_offer_retry", lambda label, consequence="": True)

            im_module._wizard_collect_webhook_section(state)

            assert state.secret_updates["WEBHOOK_URL"] == "https://discord.com/api/webhooks/1/token"
            assert state.config_values["WEBHOOK_ENABLED"] is True

    # Verifies a blank ntfy access token means no token rather than an unanswerable prompt
    def test_a_blank_ntfy_access_token_means_no_token(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            secret_updates = {}
            monkeypatch.delenv("NTFY_ACCESS_TOKEN", raising=False)
            monkeypatch.setattr(im_module, "_wizard_ask_yes_no", lambda question, default=True: True)
            monkeypatch.setattr(im_module, "_wizard_ask_secret", lambda question: "")
            monkeypatch.setattr(im_module, "_wizard_offer_retry", Mock(side_effect=AssertionError("a blank token should not be rejected")))

            im_module._wizard_collect_ntfy_access_token(secret_updates, Path(directory_name) / ".env")

            assert secret_updates == {}

    # Verifies a token pasted with its authorization scheme can be abandoned and is never saved
    def test_an_ntfy_access_token_pasted_with_its_scheme_can_be_abandoned(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            secret_updates = {}
            labels = []
            monkeypatch.delenv("NTFY_ACCESS_TOKEN", raising=False)
            monkeypatch.setattr(im_module, "_wizard_ask_yes_no", lambda question, default=True: True)
            monkeypatch.setattr(im_module, "_wizard_ask_secret", lambda question: "Bearer tk_secret")
            # Refuses the escape after recording the label the wizard offered
            def offer_retry(label, consequence=""):
                labels.append(label)
                return False
            monkeypatch.setattr(im_module, "_wizard_offer_retry", offer_retry)

            im_module._wizard_collect_ntfy_access_token(secret_updates, Path(directory_name) / ".env")

            assert labels == ["ntfy access token"]
            assert secret_updates == {}

    # Verifies an abandoned sign-in answer leaves no-login rather than writing half a session
    @pytest.mark.parametrize("username, password", [("", "private-password"), ("monitoring.account", "")])
    def test_an_abandoned_sign_in_answer_falls_back_to_no_login(self, im_module, monkeypatch, username, password):
        with make_test_directory() as directory_name:
            state = make_setup_state(im_module, Path(directory_name))
            state.baseline_values["SKIP_SESSION"] = False
            state.config_values["SKIP_SESSION"] = False
            monkeypatch.setattr(im_module, "_wizard_ask_choice", lambda question, options, default_index=0: len(options) - 1)
            monkeypatch.setattr(im_module, "_wizard_ask_text", lambda question, default="", required=False: username)
            monkeypatch.setattr(im_module, "_wizard_ask_secret", lambda question: password)
            monkeypatch.setattr(im_module, "_wizard_offer_retry", lambda label, consequence="": False)

            im_module._wizard_collect_login_section(state, "pip")

            assert state.login_method == "no-login"
            assert state.logged_in is False
            assert state.session_username == ""
            assert state.config_values["SKIP_SESSION"] is True
            assert "SESSION_PASSWORD" not in state.secret_updates

    # Verifies a password left blank on the retry too still leaves no-login rather than saving an empty secret
    def test_a_password_abandoned_after_a_retry_still_falls_back(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            state = make_setup_state(im_module, Path(directory_name))
            state.baseline_values["SKIP_SESSION"] = False
            state.config_values["SKIP_SESSION"] = False
            monkeypatch.setattr(im_module, "_wizard_ask_choice", lambda question, options, default_index=0: len(options) - 1)
            monkeypatch.setattr(im_module, "_wizard_ask_text", lambda question, default="", required=False: "monitoring.account")
            monkeypatch.setattr(im_module, "_wizard_ask_secret", lambda question: "")
            monkeypatch.setattr(im_module, "_wizard_offer_retry", lambda label, consequence="": True)

            im_module._wizard_collect_login_section(state, "pip")

            assert state.login_method == "no-login"
            assert "SESSION_PASSWORD" not in state.secret_updates
            assert state.config_values["SKIP_SESSION"] is True


# Verifies a CSV answer without an extension is saved as a .csv file while an explicit extension is left alone
def test_the_csv_answer_gains_a_csv_extension_when_it_has_none(im_module, monkeypatch):
    with make_test_directory() as directory_name:
        state = make_setup_state(im_module, Path(directory_name))
        monkeypatch.setattr(im_module, "_wizard_ask_yes_no", lambda question, default=True: True)
        for typed, expected in (("activity", "activity.csv"), ("activity.csv", "activity.csv"), ("activity.txt", "activity.txt"), ("", "")):
            monkeypatch.setattr(im_module, "_wizard_ask_text", lambda question, default="", **kwargs: typed)
            im_module._wizard_collect_output_section(state)
            assert state.config_values["CSV_FILE"] == expected


# Verifies a declined email section clears the mail server, so the written config cannot contradict the summary
def test_a_declined_email_section_clears_the_mail_server(im_module, monkeypatch):
    with make_test_directory() as directory_name:
        state = make_setup_state(im_module, Path(directory_name))
        mail_server = {"SMTP_HOST": "smtp.example.com", "SMTP_USER": "monitor", "SENDER_EMAIL": "sender@example.com", "RECEIVER_EMAIL": "receiver@example.com"}
        state.baseline_values.update(mail_server)
        state.config_values.update(mail_server)
        state.secret_updates["SMTP_PASSWORD"] = "private-password"
        monkeypatch.setattr(im_module, "_wizard_ask_yes_no", lambda question, default=True: False)

        im_module._wizard_collect_email_section(state)

        defaults = im_module.config_template_defaults()
        assert all(state.config_values[name] == defaults[name] for name in im_module.WIZARD_SMTP_CONFIG_KEYS)
        assert "SMTP_PASSWORD" not in state.secret_updates


class TestMailServerSignIn:
    # Returns scripted answers for one complete mail server section
    @staticmethod
    def scripted_email(im_module, monkeypatch, choices=(0,), secrets=("private-password",), yes_no=None):
        texts = iter(["smtp.example.test", "587", "monitor@example.test", "monitor@example.test", "alerts@example.test"])
        answers = iter(yes_no if yes_no is not None else [True, True])
        secret_values = iter(secrets)
        choice_values = iter(choices)
        monkeypatch.setattr(im_module, "_wizard_ask_text", lambda question, default="", required=False: next(texts))
        monkeypatch.setattr(im_module, "_wizard_ask_yes_no", lambda question, default=True: next(answers))
        monkeypatch.setattr(im_module, "_wizard_ask_secret", lambda question: next(secret_values))
        monkeypatch.setattr(im_module, "_wizard_ask_choice", lambda question, options, default_index=0: next(choice_values))

    # Verifies the wizard signs in with exactly the answers just given, so a wrong password is caught during setup
    def test_the_wizard_signs_in_with_the_collected_mail_server(self, im_module, monkeypatch, capsys):
        with make_test_directory() as directory_name:
            state = make_setup_state(im_module, Path(directory_name))
            attempts = []
            self.scripted_email(im_module, monkeypatch)
            monkeypatch.setattr(im_module, "_wizard_verify_smtp", lambda values, password: attempts.append((values, password)) or None)

            im_module._wizard_collect_email_section(state)

            assert attempts == [({"SMTP_HOST": "smtp.example.test", "SMTP_PORT": 587, "SMTP_SSL": True, "SMTP_USER": "monitor@example.test", "SENDER_EMAIL": "monitor@example.test", "RECEIVER_EMAIL": "alerts@example.test"}, "private-password")]
            assert "The mail server accepted the sign-in. No email was sent." in capsys.readouterr().out
            assert state.config_values["STATUS_NOTIFICATION"] is True
            assert state.config_values["ERROR_NOTIFICATION"] is True
            assert state.config_values["FOLLOWERS_NOTIFICATION"] is False

    # Verifies a refused sign-in offers the mail server questions again rather than saving settings that cannot work
    def test_a_refused_sign_in_offers_another_attempt(self, im_module, monkeypatch, capsys):
        with make_test_directory() as directory_name:
            state = make_setup_state(im_module, Path(directory_name))
            texts = iter(["smtp.example.test", "587", "monitor@example.test", "monitor@example.test", "alerts@example.test"] * 2)
            answers = iter([True, True, True, True])
            secrets = iter(["wrong-password", "right-password"])
            problems = [("The SMTP server rejected the sign-in", "535 authentication failed", "Use an app password", False), None]
            monkeypatch.setattr(im_module, "_wizard_ask_text", lambda question, default="", required=False: next(texts))
            monkeypatch.setattr(im_module, "_wizard_ask_yes_no", lambda question, default=True: next(answers))
            monkeypatch.setattr(im_module, "_wizard_ask_secret", lambda question: next(secrets))
            monkeypatch.setattr(im_module, "_wizard_ask_choice", lambda question, options, default_index=0: 0)
            monkeypatch.setattr(im_module, "_wizard_offer_retry", lambda label, consequence="": True)
            monkeypatch.setattr(im_module, "_wizard_verify_smtp", lambda values, password: problems.pop(0))

            im_module._wizard_collect_email_section(state)

            output = capsys.readouterr().out
            assert "The SMTP server rejected the sign-in: 535 authentication failed" in output
            assert "To fix: Use an app password" in output
            assert state.secret_updates["SMTP_PASSWORD"] == "right-password"
            assert state.want_email is True

    # Verifies giving up on a refused sign-in switches every email alert off rather than saving settings that cannot work
    def test_an_abandoned_sign_in_switches_email_off(self, im_module, monkeypatch, capsys):
        with make_test_directory() as directory_name:
            state = make_setup_state(im_module, Path(directory_name))
            self.scripted_email(im_module, monkeypatch)
            monkeypatch.setattr(im_module, "_wizard_offer_retry", lambda label, consequence="": False)
            monkeypatch.setattr(im_module, "_wizard_verify_smtp", lambda values, password: ("The SMTP server rejected the sign-in", "535 authentication failed", "Use an app password", False))

            im_module._wizard_collect_email_section(state)

            assert "Email notifications stay off until the mail server accepts the settings." in capsys.readouterr().out
            assert state.want_email is False
            assert all(state.config_values[name] is False for name in im_module.WIZARD_EMAIL_NOTIFICATION_KEYS)

    # Verifies an unreachable mail server keeps the answers, since being offline is the usual reason a correct setup fails here
    def test_an_unreachable_mail_server_keeps_the_answers(self, im_module, monkeypatch, capsys):
        with make_test_directory() as directory_name:
            state = make_setup_state(im_module, Path(directory_name))
            self.scripted_email(im_module, monkeypatch)
            monkeypatch.setattr(im_module, "_wizard_offer_retry", lambda label, consequence="": False)
            monkeypatch.setattr(im_module, "_wizard_verify_smtp", lambda values, password: ("The SMTP server could not be reached", "", "Check SMTP_HOST", True))

            im_module._wizard_collect_email_section(state)

            assert "The settings were kept without being checked. Run --doctor to check the sign-in again." in capsys.readouterr().out
            assert state.config_values["SMTP_HOST"] == "smtp.example.test"
            assert state.want_email is True

    # Verifies the sign-in check reads the answers just given instead of the settings already loaded
    def test_the_sign_in_check_uses_the_collected_settings_then_restores_them(self, im_module, monkeypatch, real_smtp_sign_in):
        seen = {}
        monkeypatch.setattr(im_module, "SMTP_HOST", "old.example.test", raising=False)
        monkeypatch.setattr(im_module, "SMTP_PASSWORD", "old-password", raising=False)
        # Records the settings the sign-in would use without opening a connection
        class RecordingSMTP:
            def __init__(self, host, port, timeout=None):
                seen["host"] = host
                seen["port"] = port
                seen["timeout"] = timeout

            def starttls(self, context=None):
                seen["tls"] = True

            def login(self, user, password):
                seen["login"] = (user, password)

            def quit(self):
                seen["quit"] = True
        monkeypatch.setattr(im_module.smtplib, "SMTP", RecordingSMTP)

        assert im_module._wizard_verify_smtp({"SMTP_HOST": "smtp.example.test", "SMTP_PORT": 587, "SMTP_SSL": True, "SMTP_USER": "monitor@example.test", "SENDER_EMAIL": "monitor@example.test", "RECEIVER_EMAIL": "alerts@example.test"}, "") is None

        assert seen["host"] == "smtp.example.test"
        assert seen["port"] == 587
        assert seen["timeout"] == im_module.WIZARD_SMTP_TIMEOUT
        assert seen["login"] == ("monitor@example.test", "old-password")
        assert seen["quit"] is True
        assert im_module.SMTP_HOST == "old.example.test"


# Private mail server password entry signs in first and never displays what was typed
def test_set_smtp_password_signs_in_before_saving(im_module, monkeypatch, capsys):
    with make_test_directory() as directory_name:
        env_path = Path(directory_name) / ".env"
        password = "app-password-value"
        sign_in = Mock(return_value="monitor@example.test")
        monkeypatch.setattr(im_module, "_wizard_install_method", lambda: "manual")

        result = im_module.run_set_smtp_password(env_file=env_path, interactive=True, getpass_func=lambda prompt: password, sign_in=sign_in)

        assert result == str(env_path.resolve())
        sign_in.assert_called_once_with(password, timeout=5)
        assert f'SMTP_PASSWORD="{password}"' in env_path.read_text(encoding="utf-8")
        output = capsys.readouterr().out
        assert password not in output
        assert "The mail server accepted the password for monitor@example.test" in output


# A password the mail server refuses leaves the private settings file untouched
def test_set_smtp_password_refused_by_the_server_is_not_saved(im_module):
    with make_test_directory() as directory_name:
        env_path = Path(directory_name) / ".env"
        env_path.write_text("KEEP=value\n", encoding="utf-8")
        refuse = Mock(side_effect=im_module.smtplib.SMTPAuthenticationError(535, b"authentication failed"))

        with pytest.raises(im_module.SmtpConfigurationError, match="did not accept the password"):
            im_module.run_set_smtp_password(env_file=env_path, interactive=True, getpass_func=lambda prompt: "wrong", sign_in=refuse)

        assert env_path.read_text(encoding="utf-8") == "KEEP=value\n"


# Private mail server password entry requires a terminal, so the password cannot be echoed or piped in
def test_set_smtp_password_requires_a_terminal(im_module):
    with make_test_directory() as directory_name:
        env_path = Path(directory_name) / ".env"

        with pytest.raises(im_module.SmtpConfigurationError, match="interactive terminal"):
            im_module.run_set_smtp_password(env_file=env_path, interactive=False)

        assert not env_path.exists()


# Declining replacement leaves an existing private mail server password unchanged
def test_set_smtp_password_declined_replacement_is_non_destructive(im_module):
    with make_test_directory() as directory_name:
        env_path = Path(directory_name) / ".env"
        env_path.write_text('SMTP_PASSWORD="original"\n', encoding="utf-8")

        with pytest.raises(im_module.SmtpConfigurationError, match="left as it is"):
            im_module.run_set_smtp_password(env_file=env_path, interactive=True, input_func=lambda prompt: "no", getpass_func=lambda prompt: "replacement", sign_in=Mock())

        assert env_path.read_text(encoding="utf-8") == 'SMTP_PASSWORD="original"\n'


# The sign-in reaches the configured mail server and gives back the password it borrowed
def test_smtp_sign_in_uses_the_configured_mail_server(im_module, monkeypatch):
    session = Mock()
    connect = Mock(return_value=session)
    for name, value in (("SMTP_HOST", "smtp.example.test"), ("SMTP_PORT", 587), ("SMTP_SSL", True), ("SMTP_USER", "monitor@example.test"), ("SMTP_PASSWORD", "saved"), ("SENDER_EMAIL", "monitor@example.test"), ("RECEIVER_EMAIL", "alerts@example.test")):
        monkeypatch.setattr(im_module, name, value)
    monkeypatch.setattr(im_module.smtplib, "SMTP", connect)

    assert im_module.smtp_sign_in("entered", timeout=5) == "monitor@example.test"

    connect.assert_called_once_with("smtp.example.test", 587, timeout=5)
    session.login.assert_called_once_with("monitor@example.test", "entered")
    session.quit.assert_called_once()
    assert im_module.SMTP_PASSWORD == "saved"


# An unconfigured mail server is named instead of surfacing as a bare connection failure
def test_smtp_sign_in_reports_incomplete_settings(im_module, monkeypatch):
    for name, value in (("SMTP_HOST", "your_smtp_server_ssl"), ("SMTP_USER", "your_smtp_user"), ("SENDER_EMAIL", "your_sender_email"), ("RECEIVER_EMAIL", "your_receiver_email")):
        monkeypatch.setattr(im_module, name, value)

    with pytest.raises(im_module.SmtpConfigurationError, match="settings are incomplete"):
        im_module.smtp_sign_in("entered")


# A blank password is refused rather than saved as an empty secret
def test_blank_smtp_password_is_refused(im_module):
    with pytest.raises(im_module.SmtpConfigurationError, match="No SMTP password"):
        im_module.smtp_sign_in("")


# Verifies Ctrl+C at the welcome offer reports one line instead of a traceback
def test_interrupting_the_welcome_offer_reports_a_cancellation(im_module, monkeypatch, capsys):
    def interrupt(*_args, **_kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(im_module.sys, "stdin", Mock(isatty=lambda: True))
    monkeypatch.setattr(builtins, "input", interrupt)
    monkeypatch.setattr(im_module, "run_setup_wizard", lambda *args, **kwargs: pytest.fail("the wizard ran after being interrupted"))

    with pytest.raises(SystemExit) as exit_error:
        im_module._wizard_welcome(None)

    assert exit_error.value.code == 1
    assert "Setup cancelled." in capsys.readouterr().out


# Puts the wizard on the shortest path to the save, so a test can interrupt one chosen prompt
def install_saving_wizard_flow(im_module, monkeypatch, answers):
    choices = iter([0, 2, 1, 0, 0])
    protect_setup_globals(im_module, monkeypatch)
    monkeypatch.setattr(im_module.sys, "stdin", Mock(isatty=lambda: True))
    monkeypatch.setattr(im_module, "_wizard_install_method", lambda: "manual")
    monkeypatch.setattr(im_module, "_wizard_ask_text", lambda *args, **kwargs: "target.user")
    monkeypatch.setattr(im_module, "_wizard_ask_duration", lambda question, default: default)
    monkeypatch.setattr(im_module, "_wizard_ask_yes_no", Mock(side_effect=list(answers)))
    monkeypatch.setattr(im_module, "_wizard_ask_choice", lambda *args, **kwargs: next(choices))
    monkeypatch.setattr(im_module, "run_doctor", lambda *args, **kwargs: 0)
    monkeypatch.setattr(im_module, "_wizard_collect_output_section", lambda state: None)


# Verifies an interrupt before the save says the destination files are untouched
def test_interrupting_the_questions_reports_untouched_files(im_module, monkeypatch, capsys):
    with make_test_directory() as directory_name:
        directory = Path(directory_name)
        config_path = directory / "instagram_monitor.conf"
        protect_setup_globals(im_module, monkeypatch)
        monkeypatch.setattr(im_module.sys, "stdin", Mock(isatty=lambda: True))
        monkeypatch.setattr(im_module, "_wizard_install_method", lambda: "manual")
        monkeypatch.setattr(builtins, "input", Mock(side_effect=KeyboardInterrupt))

        with pytest.raises(SystemExit) as error:
            im_module.run_setup_wizard(config_file=config_path, env_file=directory / ".env")

        assert error.value.code == 1
        assert "Setup cancelled. Destination files were not changed." in capsys.readouterr().out
        assert not config_path.exists()


# Verifies an interrupt at the doctor offer reports the saved setup instead of a cancellation
def test_interrupting_the_doctor_offer_keeps_the_saved_setup(im_module, monkeypatch, capsys):
    with make_test_directory() as directory_name:
        directory = Path(directory_name)
        config_path = directory / "instagram_monitor.conf"
        install_saving_wizard_flow(im_module, monkeypatch, [True, False, False, False, KeyboardInterrupt, False])

        with pytest.raises(SystemExit) as error:
            im_module.run_setup_wizard(config_file=config_path, env_file=directory / ".env")

        output = capsys.readouterr().out
        assert error.value.code == 0
        assert "Setup is saved. Use the commands below when ready." in output
        assert "Setup cancelled" not in output
        assert "Next steps" in output
        assert config_path.is_file()


# Verifies an interrupt at the launch offer reports the saved setup and points at the printed command
def test_interrupting_the_launch_offer_keeps_the_saved_setup(im_module, monkeypatch, capsys):
    with make_test_directory() as directory_name:
        directory = Path(directory_name)
        config_path = directory / "instagram_monitor.conf"
        install_saving_wizard_flow(im_module, monkeypatch, [True, False, False, False, False, KeyboardInterrupt])
        execv_mock = Mock()
        monkeypatch.setattr(im_module.os, "execv", execv_mock)

        with pytest.raises(SystemExit) as error:
            im_module.run_setup_wizard(config_file=config_path, env_file=directory / ".env")

        output = capsys.readouterr().out
        assert error.value.code == 0
        assert "Setup is saved. Start monitoring with the command above when ready." in output
        assert "Setup cancelled" not in output
        execv_mock.assert_not_called()


# Verifies a prompt runs with Python's default Ctrl+C behavior, so the signal handler cannot pre-empt it
def test_prompts_restore_the_default_interrupt_handler(im_module, monkeypatch):
    observed = {}

    def answer(_prompt=""):
        observed["during"] = signal.getsignal(signal.SIGINT)
        return "value"

    monkeypatch.setattr(builtins, "input", answer)
    previous_handler = signal.signal(signal.SIGINT, im_module.signal_handler)
    try:
        assert im_module._wizard_input("Prompt: ") == "value"
        assert observed["during"] is signal.default_int_handler
        assert signal.getsignal(signal.SIGINT) is im_module.signal_handler
    finally:
        signal.signal(signal.SIGINT, previous_handler)


class TestSecretReplacePrompt:
    # Verifies a secret already in the dotenv file is kept when the replacement is declined
    def test_an_existing_dotenv_secret_is_kept_unless_the_replacement_is_confirmed(self, im_module, monkeypatch, capsys):
        with make_test_directory() as directory_name:
            directory = Path(directory_name)
            (directory / ".env").write_text('SMTP_PASSWORD="original"\n', encoding="utf-8")
            state = make_setup_state(im_module, directory)
            monkeypatch.setattr(im_module, "_wizard_ask_yes_no", lambda question, default=True: False)

            queued = im_module._wizard_queue_secret(state.secret_updates, state.env_path, "SMTP_PASSWORD", "typed-password")

            assert queued is False
            assert "SMTP_PASSWORD" not in state.secret_updates
            assert "Existing SMTP_PASSWORD will be retained" in capsys.readouterr().out

    # Verifies a confirmed replacement is queued for the save step
    def test_a_confirmed_replacement_is_queued(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            directory = Path(directory_name)
            (directory / ".env").write_text('SMTP_PASSWORD="original"\n', encoding="utf-8")
            state = make_setup_state(im_module, directory)
            monkeypatch.setattr(im_module, "_wizard_ask_yes_no", lambda question, default=True: True)

            assert im_module._wizard_queue_secret(state.secret_updates, state.env_path, "SMTP_PASSWORD", "typed-password") is True
            assert state.secret_updates["SMTP_PASSWORD"] == "typed-password"

    # Verifies a dotenv file that does not hold the secret yet is written without asking anything
    def test_a_new_secret_is_queued_without_a_question(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            state = make_setup_state(im_module, Path(directory_name))

            def refuse_every_question(question, default=True):
                raise AssertionError(f"Setup asked about a secret the dotenv file does not hold: {question!r}")

            monkeypatch.setattr(im_module, "_wizard_ask_yes_no", refuse_every_question)

            assert im_module._wizard_queue_secret(state.secret_updates, state.env_path, "SESSION_PASSWORD", "typed-password") is True
            assert state.secret_updates["SESSION_PASSWORD"] == "typed-password"

    # Verifies both password prompts guard a stored value, the session password through its own replace question
    def test_both_password_sections_route_through_the_replace_guard(self, im_module):
        from pathlib import Path as _Path

        source = _Path(im_module.__file__).read_text(encoding="utf-8")

        assert 'state.secret_updates["SMTP_PASSWORD"] =' not in source
        assert source.count('_wizard_queue_secret(state.secret_updates, state.env_path, "SMTP_PASSWORD"') == 1
        assert source.count('_wizard_existing_secret("SESSION_PASSWORD", state.env_path)') == 1
        assert source.count('state.secret_updates["SESSION_PASSWORD"] =') == 1
        assert '_wizard_queue_secret(state.secret_updates, state.env_path, "SESSION_PASSWORD"' not in source

    # Verifies a saved Instagram password is offered for replacement before the hidden prompt rather than after it
    def test_a_saved_instagram_password_is_kept_without_being_retyped(self, im_module, monkeypatch, capsys):
        with make_test_directory() as directory_name:
            directory = Path(directory_name)
            (directory / ".env").write_text('SESSION_PASSWORD="original"\n', encoding="utf-8")
            state = make_setup_state(im_module, directory)
            questions = []
            monkeypatch.setattr(im_module, "_wizard_ask_choice", lambda question, options, default_index=0: len(options) - 1)
            monkeypatch.setattr(im_module, "_wizard_ask_text", lambda question, default="", required=False: "monitoring.account")
            monkeypatch.setattr(im_module, "_wizard_ask_yes_no", lambda question, default=True: questions.append(question) or False)
            monkeypatch.setattr(im_module, "_wizard_ask_secret", lambda question: pytest.fail(f"Setup asked for a password it already has: {question!r}"))

            im_module._wizard_collect_login_section(state, "pip")

            assert questions == ["Replace the Instagram password already configured?"]
            assert "SESSION_PASSWORD" not in state.secret_updates
            assert state.config_values["SKIP_SESSION"] is False
            assert state.config_values["SESSION_USERNAME"] == "monitoring.account"
            assert "Existing SESSION_PASSWORD will be retained" in capsys.readouterr().out

    # Verifies confirming the replacement collects the new Instagram password and queues it once
    def test_a_confirmed_instagram_password_replacement_is_queued(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            directory = Path(directory_name)
            (directory / ".env").write_text('SESSION_PASSWORD="original"\n', encoding="utf-8")
            state = make_setup_state(im_module, directory)
            monkeypatch.setattr(im_module, "_wizard_ask_choice", lambda question, options, default_index=0: len(options) - 1)
            monkeypatch.setattr(im_module, "_wizard_ask_text", lambda question, default="", required=False: "monitoring.account")
            monkeypatch.setattr(im_module, "_wizard_ask_yes_no", lambda question, default=True: True)
            monkeypatch.setattr(im_module, "_wizard_ask_secret", lambda question: "replacement-password")

            im_module._wizard_collect_login_section(state, "pip")

            assert state.secret_updates["SESSION_PASSWORD"] == "replacement-password"
            assert state.config_values["SKIP_SESSION"] is False


# Verifies an interrupted entry carries the action and guide the console block prints
def test_an_interrupted_secret_entry_carries_a_fix_and_a_guide(im_module, monkeypatch):
    with make_test_directory() as directory_name:
        destination = Path(directory_name) / ".env"
        monkeypatch.setattr(im_module, "SMTP_HOST", "smtp.example.test")
        monkeypatch.setattr(im_module, "SMTP_USER", "monitor@example.test")

        def interrupt(prompt=""):
            raise KeyboardInterrupt

        with pytest.raises(im_module.SmtpConfigurationError) as raised:
            im_module.run_set_smtp_password(env_file=destination, interactive=True, getpass_func=interrupt, sign_in=Mock(side_effect=AssertionError("signed in")))

        assert str(raised.value) == "SMTP password setup was cancelled and the dotenv file was not changed"
        assert raised.value.fix == "Run --set-smtp-password again when you have the value ready"
        assert raised.value.guide == im_module.SMTP_GUIDE_URL
        assert not destination.exists()


# Verifies the console block prints the action and guide a cancelled entry carries
def test_a_cancelled_secret_command_prints_its_fix_and_guide(im_module, capsys):
    im_module.print_secret_command_error(im_module.SmtpConfigurationError("SMTP password setup was cancelled and the dotenv file was not changed", "Run --set-smtp-password again when you have the value ready", im_module.SMTP_GUIDE_URL))

    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "* Error: SMTP password setup was cancelled and the dotenv file was not changed"
    assert lines[1].endswith("To fix: Run --set-smtp-password again when you have the value ready")
    assert lines[2] == f"Guide: {im_module.SMTP_GUIDE_URL}"


# Verifies the target answer and the polling question sit in the groups the sibling wizards use
def test_the_polling_question_starts_its_own_group(im_module, monkeypatch, capsys):
    with make_test_directory() as directory_name:
        directory = Path(directory_name)
        answers = iter(["someuser", "y", ""])

        # Echoes each prompt with its answer, so the captured text is the transcript a user reads
        def answer(prompt=""):
            typed = next(answers)
            print(f"{prompt}{typed}")
            return typed

        protect_setup_globals(im_module, monkeypatch)
        monkeypatch.setattr(im_module.sys, "stdin", Mock(isatty=lambda: True))
        monkeypatch.setattr(builtins, "input", answer)
        monkeypatch.setattr(im_module, "_wizard_install_method", lambda: "manual")
        monkeypatch.setattr(im_module, "_wizard_collect_login_section", Mock(side_effect=KeyboardInterrupt))

        with pytest.raises(SystemExit):
            im_module.run_setup_wizard(config_file=directory / "instagram_monitor.conf", env_file=directory / ".env")

        transcript = capsys.readouterr().out
        assert "\n\nPersist these targets in the generated config?" not in transcript
        assert "\n\nInstagram polling interval (seconds or use s/m/h/d)" in transcript

# Verifies the guide link opens the setup page the sibling monitors link, with no section fragment
def test_the_welcome_guide_link_opens_the_shared_setup_page(im_module):
    assert im_module.QUICK_START_GUIDE_URL.endswith("/setup-and-first-run/")

# Verifies the doctor setup runs credits the dotenv file, not the fallback the empty source map produces
def test_saved_secrets_are_credited_to_the_dotenv_file(im_module, monkeypatch, tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("SESSION_PASSWORD=a-saved-session-password\n", encoding="utf-8")
    monkeypatch.setattr(im_module, "SECRET_SOURCES", {})
    monkeypatch.setattr(im_module, "EXPORTED_SECRET_KEYS", frozenset())
    state = make_setup_state(im_module, tmp_path)
    state.env_path = env_path

    im_module._wizard_apply_saved_values(state)

    assert im_module.SECRET_SOURCES["SESSION_PASSWORD"] == "dotenv file"


# Verifies a secret exported before startup keeps the environment as its source, since the export still wins
def test_an_exported_secret_is_not_credited_to_the_dotenv_file(im_module, monkeypatch, tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("SESSION_PASSWORD=a-saved-session-password\n", encoding="utf-8")
    monkeypatch.setattr(im_module, "SECRET_SOURCES", {})
    monkeypatch.setattr(im_module, "EXPORTED_SECRET_KEYS", frozenset({"SESSION_PASSWORD"}))
    state = make_setup_state(im_module, tmp_path)
    state.env_path = env_path

    im_module._wizard_apply_saved_values(state)

    assert im_module.SECRET_SOURCES["SESSION_PASSWORD"] == "environment"


# Verifies a config destination switched off is refused, rather than writing settings to a file named 'none'
def test_setup_refuses_a_config_destination_switched_off(tmp_path):
    result = subprocess.run([sys.executable, str(PROJECT_ROOT / "instagram_monitor.py"), "--setup", "--config-file", "none"], cwd=tmp_path, capture_output=True, text=True, check=False)

    assert result.returncode == 2
    assert "--setup requires a config destination and cannot use --config-file none" in result.stderr
    assert not (tmp_path / "none").exists()


# Verifies the non-interactive message points at the same command and files the sibling monitors name
def test_a_non_interactive_setup_names_the_shared_fallback(im_module, monkeypatch, capsys):
    monkeypatch.setattr(im_module.sys.stdin, "isatty", lambda: False)

    with pytest.raises(SystemExit) as raised:
        im_module.run_setup_wizard()

    assert raised.value.code == 1
    lines = capsys.readouterr().out.splitlines()
    assert lines[-1] == "Run --setup from an interactive shell or use --generate-config and edit the files manually."
