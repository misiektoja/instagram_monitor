"""Tests for the staged setup wizard and its safety gates."""

from pathlib import Path
import tempfile
from unittest.mock import Mock

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = PROJECT_ROOT / "local" / "test_artifacts"


# Creates a disposable setup destination below the project local directory
def make_test_directory():
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(dir=ARTIFACT_ROOT)


# Registers setup-mutated globals with monkeypatch so each test restores them
def protect_setup_globals(im_module, monkeypatch):
    names = ("CLI_CONFIG_PATH", "DOTENV_FILE", "SESSION_USERNAME", "SESSION_PASSWORD", "SKIP_SESSION", "TARGET_USERNAMES", "WEB_DASHBOARD_ENABLED", "DASHBOARD_ENABLED", "WEB_DASHBOARD_HOST", "STATUS_NOTIFICATION", "WEBHOOK_ENABLED", "WEBHOOK_PROVIDER", "WEBHOOK_STATUS_NOTIFICATION", "WEBHOOK_URL", "NTFY_ACCESS_TOKEN")
    for name in names:
        monkeypatch.setattr(im_module, name, getattr(im_module, name), raising=False)


# Builds a minimal editable state for one setup-section unit test
def make_setup_state(im_module, directory: Path):
    baseline = dict(vars(im_module))
    return im_module.WizardSetupState(directory / "instagram_monitor.conf", directory / ".env", baseline, dict(baseline), {}, ["target.user"], True, False, "no-login", "", None, False, False, False, False)


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
            monkeypatch.setattr(im_module, "_wizard_ask_yes_no", lambda *args, **kwargs: next(answers))
            monkeypatch.setattr(im_module, "_wizard_ask_choice", lambda *args, **kwargs: next(choices))

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
            monkeypatch.setattr(im_module, "_wizard_ask_yes_no", lambda *args, **kwargs: next(answers))
            monkeypatch.setattr(im_module, "_wizard_ask_choice", lambda *args, **kwargs: next(choices))
            monkeypatch.setattr(im_module, "run_doctor", Mock(side_effect=AssertionError("doctor called")))

            with pytest.raises(SystemExit) as error:
                im_module.run_setup_wizard(config_file=config_path, env_file=env_path)

            assert error.value.code == 0
            namespace = {}
            exec(config_path.read_text(encoding="utf-8"), namespace)
            assert namespace["TARGET_USERNAMES"] == []
            assert namespace["DOTENV_FILE"] == str(env_path.resolve())
            output = capsys.readouterr().out
            assert "second.target" in output
            assert "--env-file" in output
            assert "custom secrets.env" in output


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
            assert "Session login guide: https://misiektoja.github.io/instagram_monitor/configuration/#logged-in-mode-with-session-login" in output
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

    def test_email_section_uses_the_requested_tls_ssl_question(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            state = make_setup_state(im_module, Path(directory_name))
            questions = []
            answers = iter([True, True])
            texts = iter(["smtp.example.test", "587", "smtp-user", "from@example.test", "to@example.test"])
            # Captures every yes or no question while returning scripted answers
            def ask_yes_no(question, default=True):
                questions.append(question)
                return next(answers)
            monkeypatch.setattr(im_module, "_wizard_ask_yes_no", ask_yes_no)
            monkeypatch.setattr(im_module, "_wizard_ask_text", lambda *args, **kwargs: next(texts))
            monkeypatch.setattr(im_module, "_wizard_ask_secret", lambda *args, **kwargs: "private-password")

            im_module._wizard_collect_email_section(state)

            assert questions == ["Set up email (SMTP) alerts now?", "Enable TLS/SSL for SMTP?"]
            assert state.config_values["SMTP_SSL"] is True


class TestSectionOrder:
    # Verifies initial setup collects email before webhook settings
    def test_initial_setup_matches_spotify_notification_order(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            directory = Path(directory_name)
            calls = []
            protect_setup_globals(im_module, monkeypatch)
            monkeypatch.setattr(im_module.sys, "stdin", Mock(isatty=lambda: True))
            monkeypatch.setattr(im_module, "_wizard_install_method", lambda: "manual")
            monkeypatch.setattr(im_module, "_wizard_collect_target_section", lambda state: calls.append("target"))
            monkeypatch.setattr(im_module, "_wizard_collect_login_section", lambda state, method: calls.append("login"))
            monkeypatch.setattr(im_module, "_wizard_collect_interface_section", lambda state, method: calls.append("interface"))
            monkeypatch.setattr(im_module, "_wizard_collect_email_section", lambda state: calls.append("email"))
            monkeypatch.setattr(im_module, "_wizard_collect_webhook_section", lambda state: calls.append("webhook"))
            monkeypatch.setattr(im_module, "_wizard_review_setup", lambda state, method: calls.append("review") or False)

            with pytest.raises(SystemExit) as error:
                im_module.run_setup_wizard(config_file=directory / "instagram_monitor.conf", env_file=directory / ".env")

            assert error.value.code == 1
            assert calls == ["target", "login", "interface", "email", "webhook", "review"]

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

    # Verifies the setup editor lists email before webhook settings
    def test_editor_matches_spotify_notification_order(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            state = make_setup_state(im_module, Path(directory_name))
            labels = []
            monkeypatch.setattr(im_module, "_wizard_ask_choice", lambda question, options, default_index=0: labels.extend(label for label, _ in options) or 6)

            im_module._wizard_edit_setup_section(state, "manual")

            assert labels == ["Targets and persistence", "Login and session", "Interface", "Email alerts", "Webhook alerts", "File destinations", "Return to summary"]


class TestWizardSafetyGates:
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
            choices = iter([0, 2, 0, 0])
            protect_setup_globals(im_module, monkeypatch)
            monkeypatch.delenv("WEBHOOK_URL", raising=False)
            monkeypatch.setattr(im_module.sys, "stdin", Mock(isatty=lambda: True))
            monkeypatch.setattr(im_module, "_wizard_install_method", lambda: "manual")
            monkeypatch.setattr(im_module, "_wizard_ask_text", lambda *args, **kwargs: "target.user")
            monkeypatch.setattr(im_module, "_wizard_ask_yes_no", lambda *args, **kwargs: next(answers))
            monkeypatch.setattr(im_module, "_wizard_ask_choice", lambda *args, **kwargs: next(choices))
            monkeypatch.setattr(im_module, "_wizard_ask_secret", lambda *args, **kwargs: "https://discord.example.test/hook")
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
            # Captures every yes or no question to prove Start is never offered
            def ask_yes_no(question, default=True):
                questions.append(question)
                return next(answers)
            monkeypatch.setattr(im_module, "_wizard_ask_yes_no", ask_yes_no)
            monkeypatch.setattr(im_module, "_wizard_ask_choice", lambda *args, **kwargs: next(choices))
            monkeypatch.setattr(im_module, "run_doctor", Mock(return_value=2))
            monkeypatch.setattr(im_module, "_wizard_launch_monitor", Mock(side_effect=AssertionError("monitor started")))

            with pytest.raises(SystemExit) as error:
                im_module.run_setup_wizard(config_file=directory / "instagram_monitor.conf", env_file=directory / ".env")

            assert error.value.code == 0
            assert all(not question.startswith("Start monitoring now?") for question in questions)
