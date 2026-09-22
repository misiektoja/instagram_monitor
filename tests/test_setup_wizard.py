"""Tests for the staged setup wizard and its safety gates."""

import builtins
import os
import shlex
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock

import signal
import pytest

import instagram_monitor as im


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


# Answers each mail server prompt with a value that prompt accepts, so a section under test reaches its end instead
# of looping on an answer the wizard rejects
def mail_answer(question, default="", required=False):
    lowered = question.lower()
    if "url" in lowered:
        return "https://ntfy.sh/example"
    if "host" in lowered:
        return "smtp.example.test"
    if "port" in lowered:
        return "587"
    return "answer@example.test"


# Builds a minimal editable state for one setup-section unit test
def make_setup_state(im_module, directory: Path):
    baseline = dict(vars(im_module))
    return im_module.WizardSetupState(directory / "instagram_monitor.conf", directory / ".env", baseline, dict(baseline), {}, ["target.user"], True, False, "no-login", "", None, None, False, False, False, False)


# Setup writes the switch its question named, so a question promising more than its switch delivers is the drift
# this catches. A followings change is a status event and no follower switch gates it
class TestTheFollowQuestionsNameTheSwitchTheyWrite:
    # Runs one real notification section through its custom preset and returns the question asked per switch
    @staticmethod
    def _questions(im_module, section, choice_answer):
        asked = []
        with make_test_directory() as directory_name:
            state = make_setup_state(im_module, Path(directory_name))
            with pytest.MonkeyPatch.context() as patcher:
                patcher.setattr(im_module, "_wizard_ask_yes_no", lambda question, default=True: asked.append(question) or True)
                patcher.setattr(im_module, "_wizard_ask_text", mail_answer)
                patcher.setattr(im_module, "_wizard_ask_positive_int", lambda question, default, maximum=None: 587)
                patcher.setattr(im_module, "_wizard_ask_secret", lambda question: "private-value")
                patcher.setattr(im_module, "_wizard_verify_smtp", lambda values, password: None)
                patcher.setattr(im_module, "_wizard_ask_choice", lambda question, options, **kwargs: choice_answer(question, options))
                section(state)
        return asked

    @pytest.mark.parametrize("section_name,choice_index", [("_wizard_collect_email_section", 2), ("_wizard_collect_webhook_section", 2)])
    def test_the_follower_question_does_not_promise_followings(self, im_module, section_name, choice_index):
        presets = []

        # Every choice but the notification one takes its first option, so the run reaches the per-switch questions
        def answer(question, options):
            if "notification" in question or "alert" in question:
                presets.append(options)
                return choice_index
            return 0

        asked = self._questions(im_module, getattr(im_module, section_name), answer)
        status_question = next(item for item in asked if "posts" in item)
        follower_question = next(item for item in asked if "follows or unfollows" in item)

        assert "followings" in status_question
        assert "following" not in follower_question
        assert "Also" in presets[-1][1][1]
        assert "following" not in presets[-1][1][1]
        assert "followings" in presets[-1][0][1]


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
            assert "Enter one or more Instagram usernames or profile URLs separated by commas." in capsys.readouterr().out

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
            monkeypatch.setattr(im_module, "_wizard_collect_connection_section", lambda state: None)
            monkeypatch.setattr(im_module, "_wizard_collect_output_section", lambda state: None)

            with pytest.raises(SystemExit) as error:
                im_module.run_setup_wizard(config_file=config_path, env_file=env_path)

            assert error.value.code == 1
            assert not config_path.exists()
            assert not env_path.exists()

    # A rerun over an existing configuration proposes its saved settings, which is what the rebuild question offers
    def test_a_rerun_proposes_the_saved_settings(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            directory = Path(directory_name)
            config_path = directory / "instagram_monitor.conf"
            config_path.write_text('TARGET_USERNAMES = ["saved.review.user"]\nINSTA_CHECK_INTERVAL = 1234\n', encoding="utf-8")
            env_path = directory / ".env"
            offered = {}
            answers = iter([True, True, False, False, True])
            choices = iter([0, 2, 2])
            protect_setup_globals(im_module, monkeypatch)
            monkeypatch.setattr(im_module.sys, "stdin", Mock(isatty=lambda: True))
            monkeypatch.setattr(im_module, "_wizard_install_method", lambda: "manual")
            monkeypatch.setattr(im_module, "_wizard_ask_text", lambda question, default="", required=False, **kwargs: offered.setdefault("targets", default))
            monkeypatch.setattr(im_module, "_wizard_ask_duration", lambda question, default: offered.setdefault("interval", default))
            monkeypatch.setattr(im_module, "_wizard_ask_yes_no", lambda *args, **kwargs: next(answers))
            monkeypatch.setattr(im_module, "_wizard_ask_choice", lambda *args, **kwargs: next(choices))
            monkeypatch.setattr(im_module, "_wizard_collect_connection_section", lambda state: None)
            monkeypatch.setattr(im_module, "_wizard_collect_output_section", lambda state: None)

            with pytest.raises(SystemExit):
                im_module.run_setup_wizard(config_file=config_path, env_file=env_path)

            assert offered == {"targets": "saved.review.user", "interval": 1234}

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
            monkeypatch.setattr(im_module, "_wizard_collect_connection_section", lambda state: None)
            monkeypatch.setattr(im_module, "_wizard_collect_output_section", lambda state: None)

            with pytest.raises(SystemExit) as error:
                im_module.run_setup_wizard(config_file=config_path, env_file=env_path)

            assert error.value.code == 0
            namespace = {}
            exec(config_path.read_text(encoding="utf-8"), namespace)
            assert namespace["TARGET_USERNAMES"] == []
            output = capsys.readouterr().out
            assert "second.target" in output
            # No secret was entered, so nothing was written to the dotenv, no printed command names it and the
            # saved config does not name it either
            assert not env_path.exists()
            assert namespace["DOTENV_FILE"] == ""
            assert "--env-file" not in output


class TestTheConfigNamesTheDotenvOnlyWhenItExists:
    # Runs one setup that saves without entering a secret, returning the saved config values and the dotenv path
    def _save_without_secrets(self, im_module, monkeypatch, directory: Path, collect_login=None):
        config_path = directory / "instagram_monitor.conf"
        env_path = directory / ".env"
        answers = iter([True, False, False, False, False, False])
        choices = iter([0, 2, 1, 0, 0])
        protect_setup_globals(im_module, monkeypatch)
        monkeypatch.setattr(im_module.sys, "stdin", Mock(isatty=lambda: True))
        monkeypatch.setattr(im_module, "_wizard_install_method", lambda: "manual")
        monkeypatch.setattr(im_module, "_wizard_ask_text", lambda *args, **kwargs: "target.user")
        monkeypatch.setattr(im_module, "_wizard_ask_duration", lambda question, default: default)
        monkeypatch.setattr(im_module, "_wizard_ask_yes_no", lambda *args, **kwargs: next(answers))
        monkeypatch.setattr(im_module, "_wizard_ask_choice", lambda *args, **kwargs: next(choices))
        monkeypatch.setattr(im_module, "run_doctor", lambda *args, **kwargs: 0)
        monkeypatch.setattr(im_module, "_wizard_collect_login_section", collect_login or (lambda state, method: None))
        monkeypatch.setattr(im_module, "_wizard_collect_connection_section", lambda state: None)
        monkeypatch.setattr(im_module, "_wizard_collect_output_section", lambda state: None)

        with pytest.raises(SystemExit):
            im_module.run_setup_wizard(config_file=config_path, env_file=env_path)

        namespace = {}
        exec(config_path.read_text(encoding="utf-8"), namespace)
        return namespace, env_path

    # A setup that writes no secret writes no dotenv, so naming one would open every later run with a warning about
    # a file this setup decided not to create
    def test_a_setup_without_secrets_names_no_dotenv(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            namespace, env_path = self._save_without_secrets(im_module, monkeypatch, Path(directory_name))

            assert not env_path.exists()
            assert namespace["DOTENV_FILE"] == ""
            assert im_module.DOTENV_FILE == ""

    # The next run reads the config setup saved, and a warning about a file setup chose not to create is what it must
    # not open with. The same run against a config naming a missing file is the control that the warning still works
    def test_the_saved_config_opens_the_next_run_without_a_warning(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            directory = Path(directory_name)
            self._save_without_secrets(im_module, monkeypatch, directory)
            config_path = directory / "instagram_monitor.conf"

            command = [sys.executable, str(PROJECT_ROOT / "instagram_monitor.py"), "--config-file", str(config_path), "--exposure", "--no-color"]
            quiet = subprocess.run(command, cwd=directory, capture_output=True, text=True, check=False)
            config_path.write_text(config_path.read_text(encoding="utf-8").replace('DOTENV_FILE = ""', f'DOTENV_FILE = {str(directory / "absent.env")!r}'), encoding="utf-8")
            warned = subprocess.run(command, cwd=directory, capture_output=True, text=True, check=False)

            assert "does not exist" not in quiet.stdout
            assert "does not exist" in warned.stdout

    # A secret entered during setup is written to the dotenv, so the config has to name the file the run needs to read
    def test_a_setup_that_writes_a_secret_names_the_dotenv(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            def collect_login(state, method):
                state.secret_updates["SESSION_PASSWORD"] = "written-by-setup"

            namespace, env_path = self._save_without_secrets(im_module, monkeypatch, Path(directory_name), collect_login)

            assert env_path.exists()
            assert namespace["DOTENV_FILE"] == str(env_path.resolve())
            assert im_module.DOTENV_FILE == str(env_path.resolve())

    # A rerun over a dotenv an earlier setup wrote must keep naming it, since its secrets are still the ones in use
    def test_a_rerun_keeps_naming_an_existing_dotenv(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            directory = Path(directory_name)
            (directory / ".env").write_text("SESSION_PASSWORD = 'kept'\n", encoding="utf-8")

            namespace, env_path = self._save_without_secrets(im_module, monkeypatch, directory)

            assert namespace["DOTENV_FILE"] == str(env_path.resolve())


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

    # Derived from the mount table rather than restating it, so a host added there is covered here without editing
    # this test and cannot be offered under another host's key
    @pytest.mark.parametrize("choice", range(len(im.CONTAINER_FIREFOX_HOSTS)))
    def test_container_firefox_host_selection(self, im_module, monkeypatch, choice):
        captured = []

        def choose(question, options, **keywords):
            captured.extend(options)
            return choice

        monkeypatch.setattr(im_module, "_wizard_ask_choice", choose)
        host = list(im_module.CONTAINER_FIREFOX_HOSTS)[choice]

        assert im_module._wizard_select_container_firefox_host() == host
        assert captured[choice] == (im_module.CONTAINER_FIREFOX_HOSTS[host][0], im_module.CONTAINER_FIREFOX_HOST_HINTS[host]), "the menu offered text neither table holds for that host"

    # The "Another system" entry sits after every host in the table, so its index is read from the table rather than
    # written as a literal that stops meaning "the last entry" as soon as a host is added
    def test_unsupported_container_firefox_host_is_not_assumed(self, im_module, monkeypatch, capsys):
        monkeypatch.setattr(im_module, "_wizard_ask_choice", lambda *args, **kwargs: len(im_module.CONTAINER_FIREFOX_HOSTS))
        assert im_module._wizard_select_container_firefox_host() is None
        assert "not currently available for this host" in capsys.readouterr().out

    # Verifies every host in the mount table carries the wizard prose the menu needs, since a host present in one
    # and missing from the other would raise while the menu is being drawn
    def test_every_mounted_host_has_a_menu_hint(self, im_module):
        assert list(im_module.CONTAINER_FIREFOX_HOST_HINTS) == list(im_module.CONTAINER_FIREFOX_HOSTS)


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
            choose_destination.assert_called_once_with(config_path.resolve(), "manual")
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
            monkeypatch.setattr(im_module, "_wizard_collect_connection_section", lambda state: calls.append("connection"))
            monkeypatch.setattr(im_module, "_wizard_collect_output_section", lambda state: calls.append("output"))
            monkeypatch.setattr(im_module, "_wizard_review_setup", lambda state, method: calls.append("review") or False)

            with pytest.raises(SystemExit) as error:
                im_module.run_setup_wizard(config_file=directory / "instagram_monitor.conf", env_file=directory / ".env")

            output = capsys.readouterr().out
            assert error.value.code == 1
            assert calls == ["target:True", "polling", "login", "connection", "interface", "email", "webhook", "output", "review"]
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
            monkeypatch.setattr(im_module, "_wizard_ask_choice", lambda question, options, default_index=0: labels.extend(label for label, _ in options) or 9)

            im_module._wizard_print_setup_summary(state, "manual")
            summary = capsys.readouterr().out
            im_module._wizard_edit_setup_section(state, "manual")

            assert summary.index("Polling interval:") < summary.index("Login:")
            assert labels == ["Targets", "Polling interval", "Login and session", "Instagram connection", "Interface", "Email notifications", "Webhook alerts", "Output files", "File destinations", "Return to summary"]


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
            monkeypatch.setattr(im_module, "_wizard_collect_connection_section", lambda state: None)
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
            monkeypatch.setattr(im_module, "_wizard_collect_connection_section", lambda state: None)
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

            assert im_module._wizard_choose_config_destination(first, "manual") == second.resolve()

    # An alternate destination that cannot be written is refused and asked again instead of failing at the save
    def test_existing_config_decline_rejects_an_unusable_alternate_path(self, im_module, monkeypatch, capsys):
        with make_test_directory() as directory_name:
            directory = Path(directory_name)
            existing = directory / "instagram_monitor.conf"
            alternate = directory / "alternate.conf"
            existing.write_text("old\n", encoding="utf-8")
            answers = iter([str(directory), str(existing / "nested.conf"), str(alternate)])
            monkeypatch.setattr(im_module, "_wizard_ask_yes_no", lambda *args, **kwargs: False)
            monkeypatch.setattr(im_module, "_wizard_ask_text", lambda *args, **kwargs: next(answers))

            assert im_module._wizard_choose_config_destination(existing, "manual") == alternate.resolve()

            output = capsys.readouterr().out
            assert "Configuration destination must be a file path, not a directory." in output
            assert "Configuration destination does not have a usable parent directory." in output

    # A host destination is checked for being a file with a writable parent, as the setup page promises
    def test_host_destinations_are_checked_before_the_first_question(self, im_module, tmp_path):
        with pytest.raises(ValueError, match="must be a file path, not a directory"):
            im_module._wizard_validate_destination("manual", tmp_path, "Configuration destination")
        blocker = tmp_path / "blocker"
        blocker.write_text("", encoding="utf-8")
        with pytest.raises(ValueError, match="does not have a usable parent directory"):
            im_module._wizard_validate_destination("pip", blocker / "nested.conf", "Dotenv destination")
        assert im_module._wizard_validate_destination("manual", tmp_path / "missing" / "instagram_monitor.conf", "Configuration destination") == (tmp_path / "missing" / "instagram_monitor.conf").resolve()

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
            monkeypatch.setattr(im_module, "_wizard_collect_connection_section", lambda state: None)
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
            monkeypatch.setattr(im_module, "_wizard_collect_connection_section", lambda state: None)
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
        answers = {"Write the normal per-target log file?": False, "Write a CSV file of the changes?": True}
        monkeypatch.setattr(im_module, "_wizard_ask_yes_no", lambda question, default=True: answers.get(question, default))
        monkeypatch.setattr(im_module, "_wizard_ask_text", lambda question, default="", required=False: str(directory / "posts.csv"))

        im_module._wizard_collect_output_section(state)

        assert state.config_values["DISABLE_LOGGING"] is True
        assert state.config_values["CSV_FILE"] == str(directory / "posts.csv")


# Verifies declining CSV output clears a saved path, which the path prompt alone could never do
def test_declining_csv_output_clears_a_saved_path(im_module, monkeypatch):
    with make_test_directory() as directory_name:
        state = make_setup_state(im_module, Path(directory_name))
        state.config_values["CSV_FILE"] = "saved.csv"
        state.baseline_values["CSV_FILE"] = "saved.csv"
        answers = {"Write a CSV file of the changes?": False}
        monkeypatch.setattr(im_module, "_wizard_ask_yes_no", lambda question, default=True: answers.get(question, default))

        im_module._wizard_collect_output_section(state)

        assert state.config_values["CSV_FILE"] == ""


# Verifies a blank CSV answer disables CSV output rather than storing an empty path as a file name
def test_a_blank_csv_answer_disables_csv_output(im_module, monkeypatch):
    with make_test_directory() as directory_name:
        state = make_setup_state(im_module, Path(directory_name))
        monkeypatch.setattr(im_module, "_wizard_ask_yes_no", lambda question, default=True: True)
        monkeypatch.setattr(im_module, "_wizard_ask_text", lambda question, default="", required=False: "")

        im_module._wizard_collect_output_section(state)

        assert state.config_values["DISABLE_LOGGING"] is False
        assert state.config_values["CSV_FILE"] == ""


# Answers each connection question by the index named for it, and records what was offered
def scripted_connection_choices(im_module, monkeypatch, answers):
    asked = {}

    def ask(question, options, default_index=0):
        if "should be collected" in question:
            key = "collect"
        elif "names a day" in question:
            key = "budget"
        elif "reels be monitored" in question:
            key = "reels"
        else:
            key = "source"
            assert "follower and following lists" in question, f"unexpected wizard question: {question}"
        asked[key] = {"options": [label for label, _ in options], "default": default_index}
        return answers.get(key, default_index)

    monkeypatch.setattr(im_module, "_wizard_ask_choice", ask)
    return asked


# Verifies the cap the collect question names can be changed where it is named, since it governs both name options
def test_setup_can_change_the_daily_name_cap(im_module, monkeypatch):
    with make_test_directory() as directory_name:
        state = make_setup_state(im_module, Path(directory_name))
        state.logged_in = True
        state.config_values["IDENTITY_BUDGET_PER_DAY"] = 2000
        asked = scripted_connection_choices(im_module, monkeypatch, {"collect": 2, "budget": 1})
        monkeypatch.setattr(im_module, "_wizard_ask_positive_int", lambda question, default, maximum=None: 750)

        im_module._wizard_collect_connection_section(state)

        assert asked["budget"]["options"][0] == "Keep the cap at 2000 names a day"
        assert asked["budget"]["default"] == 0
        assert state.config_values["IDENTITY_BUDGET_PER_DAY"] == 750


# Verifies the cap can be removed, which is the answer that lets a run collect names without a daily stop
def test_setup_can_remove_the_daily_name_cap(im_module, monkeypatch):
    with make_test_directory() as directory_name:
        state = make_setup_state(im_module, Path(directory_name))
        state.logged_in = True
        state.config_values["IDENTITY_BUDGET_PER_DAY"] = 2000
        scripted_connection_choices(im_module, monkeypatch, {"collect": 1, "budget": 2})

        im_module._wizard_collect_connection_section(state)

        assert state.config_values["IDENTITY_BUDGET_PER_DAY"] == 0


# Verifies a setup collecting no names is not asked about a cap that would govern nothing
def test_a_counts_only_setup_is_not_asked_about_the_cap(im_module, monkeypatch):
    with make_test_directory() as directory_name:
        state = make_setup_state(im_module, Path(directory_name))
        state.logged_in = True
        asked = scripted_connection_choices(im_module, monkeypatch, {"collect": 0})

        im_module._wizard_collect_connection_section(state)

        assert "budget" not in asked


# Verifies the connection section records the list surface and leaves the saved transport settings alone
def test_the_connection_section_records_the_list_surface_only(im_module, monkeypatch):
    with make_test_directory() as directory_name:
        state = make_setup_state(im_module, Path(directory_name))
        state.logged_in = True
        state.baseline_values.update({"HTTP_BACKEND": "requests", "CURL_CFFI_IMPERSONATE": "safari"})
        scripted_connection_choices(im_module, monkeypatch, {"collect": 2, "source": 2})

        im_module._wizard_collect_connection_section(state)

        assert state.config_values["FOLLOW_LIST_SOURCE"] == "graphql"
        assert state.config_values["HTTP_BACKEND"] == "requests"
        assert state.config_values["CURL_CFFI_IMPERSONATE"] == "safari"


# Verifies login setup is offered the experimental browser source next to the three API surfaces
def test_login_setup_is_offered_the_browser_source(im_module, monkeypatch):
    with make_test_directory() as directory_name:
        state = make_setup_state(im_module, Path(directory_name))
        state.logged_in = True
        monkeypatch.setattr(im_module, "playwright_available", lambda: True)
        asked = scripted_connection_choices(im_module, monkeypatch, {"collect": 2, "source": 3})

        im_module._wizard_collect_connection_section(state)

        assert asked["source"]["options"] == ["Auto", "REST only", "GraphQL only", "Browser (experimental)"]
        assert state.config_values["FOLLOW_LIST_SOURCE"] == "browser"
        assert state.config_values["HTTP_BACKEND"] == "curl_cffi"
        assert state.config_values["CURL_CFFI_IMPERSONATE"] == "auto"


# Verifies the browser source moves a saved stock transport to curl_cffi, since monitoring refuses the mismatch
def test_the_browser_source_moves_the_stock_transport_to_curl_cffi(im_module, monkeypatch, capsys):
    with make_test_directory() as directory_name:
        state = make_setup_state(im_module, Path(directory_name))
        state.logged_in = True
        state.baseline_values["HTTP_BACKEND"] = "requests"
        monkeypatch.setattr(im_module, "playwright_available", lambda: True)
        scripted_connection_choices(im_module, monkeypatch, {"collect": 2, "source": 3})

        im_module._wizard_collect_connection_section(state)

        assert state.config_values["FOLLOW_LIST_SOURCE"] == "browser"
        assert state.config_values["HTTP_BACKEND"] == "curl_cffi"
        assert "the transport is set to curl_cffi" in capsys.readouterr().out


# Verifies a saved browser pin from another family goes back to auto, while a Chromium pin is left alone
def test_the_browser_source_unpins_an_impersonation_from_another_family(im_module, monkeypatch, capsys):
    with make_test_directory() as directory_name:
        state = make_setup_state(im_module, Path(directory_name))
        state.logged_in = True
        state.baseline_values["CURL_CFFI_IMPERSONATE"] = "firefox"
        monkeypatch.setattr(im_module, "playwright_available", lambda: True)
        scripted_connection_choices(im_module, monkeypatch, {"collect": 2, "source": 3})

        im_module._wizard_collect_connection_section(state)

        assert state.config_values["CURL_CFFI_IMPERSONATE"] == "auto"
        assert "instead of firefox" in capsys.readouterr().out

        state.baseline_values["CURL_CFFI_IMPERSONATE"] = "chrome"
        im_module._wizard_collect_connection_section(state)

        assert state.config_values["CURL_CFFI_IMPERSONATE"] == "chrome"
        assert capsys.readouterr().out == ""


# Verifies a machine without Playwright is told what to install rather than offered a source that cannot run
def test_a_missing_playwright_is_named_on_the_browser_source(im_module, monkeypatch):
    with make_test_directory() as directory_name:
        state = make_setup_state(im_module, Path(directory_name))
        state.logged_in = True
        monkeypatch.setattr(im_module, "playwright_available", lambda: False)
        described = {}

        def ask(question, options, default_index=0):
            if "should be collected" in question:
                return 2
            described.update(dict(options))
            return default_index

        monkeypatch.setattr(im_module, "_wizard_ask_choice", ask)

        im_module._wizard_collect_connection_section(state)

        assert "playwright install chromium" in described["Browser (experimental)"]
        assert state.config_values["FOLLOW_LIST_SOURCE"] == "auto"


# Verifies no-login setup is not asked a question about lists no surface returns without a session
def test_no_login_setup_is_not_asked_for_a_follower_list_source(im_module, monkeypatch):
    with make_test_directory() as directory_name:
        state = make_setup_state(im_module, Path(directory_name))
        asked = scripted_connection_choices(im_module, monkeypatch, {})

        im_module._wizard_collect_connection_section(state)

        assert "source" not in asked
        assert state.config_values["FOLLOW_LIST_SOURCE"] == state.baseline_values["FOLLOW_LIST_SOURCE"]


# Verifies the review summary names the list surface in login mode and never the transport setup does not ask about
def test_the_summary_names_the_connection_answers(im_module, monkeypatch, capsys):
    with make_test_directory() as directory_name:
        state = make_setup_state(im_module, Path(directory_name))
        state.logged_in = True
        state.config_values.update({"HTTP_BACKEND": "curl_cffi", "CURL_CFFI_IMPERSONATE": "firefox", "FOLLOW_LIST_SOURCE": "rest"})

        im_module._wizard_print_setup_summary(state, "manual")

        summary = capsys.readouterr().out
        assert "Follower list source:" in summary and "rest" in summary
        assert "HTTP backend:" not in summary and "impersonating" not in summary


# Verifies no-login setup is not shown a follower list row for lists it never fetches
def test_the_summary_hides_the_list_source_without_a_session(im_module, capsys):
    with make_test_directory() as directory_name:
        state = make_setup_state(im_module, Path(directory_name))

        im_module._wizard_print_setup_summary(state, "manual")

        summary = capsys.readouterr().out
        assert "Polling interval:" in summary
        assert "Follower list source:" not in summary


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
            monkeypatch.setattr(im_module, "_wizard_ask_text", lambda question, default="", required=False: "" if question == abandoned else mail_answer(question))
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
            monkeypatch.setattr(im_module, "_wizard_ask_text", mail_answer)
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
            monkeypatch.setattr(im_module, "_wizard_ask_text", lambda question, default="", answer=typed, **kwargs: answer)
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

        # The caller resolves the password the next run would use, so the check signs in with exactly what it is given
        assert im_module._wizard_verify_smtp({"SMTP_HOST": "smtp.example.test", "SMTP_PORT": 587, "SMTP_SSL": True, "SMTP_USER": "monitor@example.test", "SENDER_EMAIL": "monitor@example.test", "RECEIVER_EMAIL": "alerts@example.test"}, "old-password") is None

        assert seen["host"] == "smtp.example.test"
        assert seen["port"] == 587
        assert seen["timeout"] == im_module.WIZARD_SMTP_TIMEOUT
        assert seen["login"] == ("monitor@example.test", "old-password")
        assert seen["quit"] is True
        assert im_module.SMTP_HOST == "old.example.test"


# Setup reports the sign-in succeeded and then writes the files a restart reads. A check that proves one password
# while a different one is what gets read leaves the user with a setup that was announced as working and is not
class TestTheCheckedSecretIsTheOneTheNextRunUses:
    # Runs one complete email section over a dotenv file that already holds a password and returns what was signed in with
    @staticmethod
    def _run(im_module, monkeypatch, directory, typed, replace_saved, exported=None):
        env_path = Path(directory) / ".env"
        env_path.write_text('SMTP_PASSWORD="saved-in-file"\n', encoding="utf-8")
        state = make_setup_state(im_module, Path(directory))
        state.env_path = env_path
        texts = iter(["smtp.example.test", "587", "monitor@example.test", "monitor@example.test", "alerts@example.test"])
        answers = iter([True, True, replace_saved, True, True, True])
        attempts = []
        monkeypatch.delenv("SMTP_PASSWORD", raising=False)
        if exported is not None:
            monkeypatch.setenv("SMTP_PASSWORD", exported)
        monkeypatch.setattr(im_module, "_wizard_ask_text", lambda question, default="", required=False: next(texts))
        monkeypatch.setattr(im_module, "_wizard_ask_yes_no", lambda question, default=True: next(answers))
        monkeypatch.setattr(im_module, "_wizard_ask_secret", lambda question: typed)
        monkeypatch.setattr(im_module, "_wizard_ask_choice", lambda question, options, default_index=0: 0)
        monkeypatch.setattr(im_module, "_wizard_verify_smtp", lambda values, password: attempts.append(password) or None)
        im_module._wizard_collect_email_section(state)
        return attempts, state.secret_updates.get("SMTP_PASSWORD")

    # Keeping the saved password used to check the one just typed, which is the one thrown away
    def test_a_declined_replacement_checks_the_password_that_is_kept(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            attempts, queued = self._run(im_module, monkeypatch, directory_name, "typed-new", False)

            assert attempts == ["saved-in-file"]
            assert queued is None

    # An export wins at startup, so a saved replacement is not what the next run reads
    def test_an_exported_value_is_what_gets_checked(self, im_module, monkeypatch, capsys):
        with make_test_directory() as directory_name:
            attempts, queued = self._run(im_module, monkeypatch, directory_name, "typed-new", True, exported="exported-elsewhere")

            assert attempts == ["exported-elsewhere"]
            assert queued == "typed-new"
            output = capsys.readouterr().out
            assert "SMTP_PASSWORD is exported in this environment" in output
            assert "exported-elsewhere" not in output

    # The ordinary path must stay as it was: an accepted replacement is both checked and saved
    def test_an_accepted_replacement_is_checked_and_saved(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            attempts, queued = self._run(im_module, monkeypatch, directory_name, "typed-new", True)

            assert attempts == ["typed-new"]
            assert queued == "typed-new"

    # The resolver answers for the run that follows setup, so the startup order is what it has to follow
    def test_the_resolver_follows_the_startup_precedence(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            env_path = Path(directory_name) / ".env"
            env_path.write_text('SMTP_PASSWORD="saved-in-file"\n', encoding="utf-8")
            monkeypatch.delenv("SMTP_PASSWORD", raising=False)
            monkeypatch.setattr(im_module, "SMTP_PASSWORD", "from-config-file", raising=False)

            assert im_module.effective_secret_after_setup("SMTP_PASSWORD", env_path, {}) == ("saved-in-file", False)
            assert im_module.effective_secret_after_setup("SMTP_PASSWORD", env_path, {"SMTP_PASSWORD": "accepted"}) == ("accepted", False)
            monkeypatch.setenv("SMTP_PASSWORD", "exported")
            assert im_module.effective_secret_after_setup("SMTP_PASSWORD", env_path, {"SMTP_PASSWORD": "accepted"}) == ("exported", True)
            monkeypatch.delenv("SMTP_PASSWORD", raising=False)
            assert im_module.effective_secret_after_setup("SMTP_PASSWORD", Path(directory_name) / "absent.env", {}) == ("from-config-file", False)

    # The command saves to the dotenv file, which an export overrides, so the run it promises would still fail
    def test_the_password_command_says_when_an_export_shadows_the_saved_one(self, im_module, monkeypatch, capsys):
        with make_test_directory() as directory_name:
            env_path = Path(directory_name) / ".env"
            configure_mail(im_module, monkeypatch)
            monkeypatch.setattr(im_module, "_wizard_install_method", lambda: "manual")
            monkeypatch.setenv("SMTP_PASSWORD", "exported-elsewhere")

            im_module.run_set_smtp_password(env_file=env_path, interactive=True, getpass_func=lambda prompt: "app-password-value", sign_in=Mock(return_value="monitor@example.test"))

            output = capsys.readouterr().out
            assert "SMTP_PASSWORD is exported in this environment" in output
            assert "Unset the exported SMTP_PASSWORD" in output
            assert "exported-elsewhere" not in output

    # A run with no export must not be told about one, or the warning becomes noise that is ignored when it matters
    def test_the_password_command_stays_quiet_without_an_export(self, im_module, monkeypatch, capsys):
        with make_test_directory() as directory_name:
            env_path = Path(directory_name) / ".env"
            configure_mail(im_module, monkeypatch)
            monkeypatch.setattr(im_module, "_wizard_install_method", lambda: "manual")
            monkeypatch.delenv("SMTP_PASSWORD", raising=False)

            im_module.run_set_smtp_password(env_file=env_path, interactive=True, getpass_func=lambda prompt: "app-password-value", sign_in=Mock(return_value="monitor@example.test"))

            assert "is exported in this environment" not in capsys.readouterr().out


# Sets the mail settings a sign-in needs, so a test reaches the prompts rather than the completeness guard
def configure_mail(im_module, monkeypatch):
    for name, value in (("SMTP_HOST", "smtp.example.test"), ("SMTP_USER", "monitor@example.test"), ("SENDER_EMAIL", "monitor@example.test"), ("RECEIVER_EMAIL", "alerts@example.test")):
        monkeypatch.setattr(im_module, name, value)


# Private mail server password entry signs in first and never displays what was typed
def test_set_smtp_password_signs_in_before_saving(im_module, monkeypatch, capsys):
    with make_test_directory() as directory_name:
        env_path = Path(directory_name) / ".env"
        password = "app-password-value"
        sign_in = Mock(return_value="monitor@example.test")
        configure_mail(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "_wizard_install_method", lambda: "manual")

        result = im_module.run_set_smtp_password(env_file=env_path, interactive=True, getpass_func=lambda prompt: password, sign_in=sign_in)

        assert result == str(env_path.resolve())
        sign_in.assert_called_once_with(password, timeout=5)
        assert f'SMTP_PASSWORD="{password}"' in env_path.read_text(encoding="utf-8")
        output = capsys.readouterr().out
        assert password not in output
        assert "The mail server accepted the password for monitor@example.test" in output


# A password the mail server refuses leaves the private settings file untouched
def test_set_smtp_password_refused_by_the_server_is_not_saved(im_module, monkeypatch):
    with make_test_directory() as directory_name:
        env_path = Path(directory_name) / ".env"
        env_path.write_text("KEEP=value\n", encoding="utf-8")
        configure_mail(im_module, monkeypatch)
        refuse = Mock(side_effect=im_module.smtplib.SMTPAuthenticationError(535, b"authentication failed"))

        with pytest.raises(im_module.SmtpConfigurationError, match="did not accept the password"):
            im_module.run_set_smtp_password(env_file=env_path, interactive=True, getpass_func=lambda prompt: "wrong", sign_in=refuse)

        assert env_path.read_text(encoding="utf-8") == "KEEP=value\n"


# The mail settings are checked before anything is typed, so a password is never entered for nothing
def test_set_smtp_password_checks_the_mail_settings_before_prompting(im_module, monkeypatch, capsys):
    with make_test_directory() as directory_name:
        env_path = Path(directory_name) / ".env"
        for name, value in (("SMTP_HOST", "your_smtp_server_ssl"), ("SMTP_USER", "your_smtp_user"), ("SENDER_EMAIL", "monitor@example.test"), ("RECEIVER_EMAIL", "alerts@example.test")):
            monkeypatch.setattr(im_module, name, value)

        def refuse(prompt=""):
            raise AssertionError("a prompt was shown before the settings were checked")

        with pytest.raises(im_module.SmtpConfigurationError) as raised:
            im_module.run_set_smtp_password(env_file=env_path, interactive=True, input_func=refuse, getpass_func=refuse, sign_in=Mock(side_effect=AssertionError("signed in")))

        assert str(raised.value) == "The mail server settings are incomplete, SMTP_HOST and SMTP_USER are not set"
        assert raised.value.fix == "Set SMTP_HOST and SMTP_USER in the config file, or run --setup, then run --set-smtp-password again"
        assert raised.value.guide == im_module.SMTP_GUIDE_URL
        assert "your_smtp_server_ssl" not in capsys.readouterr().out
        assert not env_path.exists()


# The refusal names only the settings that are actually missing, so a partly configured mail server is not misreported
def test_set_smtp_password_names_only_the_missing_settings(im_module, monkeypatch):
    with make_test_directory() as directory_name:
        env_path = Path(directory_name) / ".env"
        for name, value in (("SMTP_HOST", "smtp.example.test"), ("SMTP_USER", "monitor@example.test"), ("SENDER_EMAIL", "monitor@example.test"), ("RECEIVER_EMAIL", "your_receiver_email")):
            monkeypatch.setattr(im_module, name, value)

        with pytest.raises(im_module.SmtpConfigurationError) as raised:
            im_module.run_set_smtp_password(env_file=env_path, interactive=True, getpass_func=lambda prompt: "entered", sign_in=Mock(side_effect=AssertionError("signed in")))

        assert str(raised.value) == "The mail server settings are incomplete, RECEIVER_EMAIL is not set"


# Private mail server password entry requires a terminal, so the password cannot be echoed or piped in
def test_set_smtp_password_requires_a_terminal(im_module):
    with make_test_directory() as directory_name:
        env_path = Path(directory_name) / ".env"

        with pytest.raises(im_module.SmtpConfigurationError, match="interactive terminal"):
            im_module.run_set_smtp_password(env_file=env_path, interactive=False)

        assert not env_path.exists()


# Declining replacement leaves an existing private mail server password unchanged
def test_set_smtp_password_declined_replacement_is_non_destructive(im_module, monkeypatch):
    with make_test_directory() as directory_name:
        env_path = Path(directory_name) / ".env"
        env_path.write_text('SMTP_PASSWORD="original"\n', encoding="utf-8")
        configure_mail(im_module, monkeypatch)

        with pytest.raises(im_module.SmtpConfigurationError, match="left as it is"):
            im_module.run_set_smtp_password(env_file=env_path, interactive=True, input_func=lambda prompt: "no", getpass_func=lambda prompt: "replacement", sign_in=Mock())

        assert env_path.read_text(encoding="utf-8") == 'SMTP_PASSWORD="original"\n'


# The sign-in reaches the configured mail server without disturbing the configured password
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


# A rejection reply that quotes the credentials back is the normal shape for several providers, so every surface
# that prints one has to be checked with a password no global holds while the failure is being rendered
class TestAProviderErrorThatEchoesThePassword:
    SECRET = "hunter2-private-value"

    # Builds a mail server class whose sign-in fails with a reply repeating the password it was given
    @staticmethod
    def _echoing_server():
        import smtplib

        class EchoingSMTP:
            # Accepts connection arguments without opening a socket
            def __init__(self, host, port, timeout=5):
                pass

            # Accepts TLS setup without opening a connection
            def starttls(self, context=None):
                pass

            # Rejects authentication with a reply that echoes the supplied password
            def login(self, user, password):
                raise smtplib.SMTPAuthenticationError(535, f"5.7.8 Not accepted. Sent: user={user} pass={password}".encode())

            # Closes the simulated SMTP connection
            def quit(self):
                pass

        return EchoingSMTP

    # Points the module at a configured mail server that always echoes the password back
    def _install(self, im_module, monkeypatch, saved_password=""):
        for name, value in (("SMTP_HOST", "smtp.example.test"), ("SMTP_PORT", 587), ("SMTP_SSL", True), ("SMTP_USER", "monitor@example.test"), ("SMTP_PASSWORD", saved_password), ("SENDER_EMAIL", "monitor@example.test"), ("RECEIVER_EMAIL", "alerts@example.test")):
            monkeypatch.setattr(im_module, name, value)
        monkeypatch.setattr(im_module.smtplib, "SMTP", self._echoing_server())

    # The password command holds the only copy of the value being checked, so it has to hand it to the renderer
    def test_the_password_command_does_not_print_what_was_typed(self, im_module, monkeypatch):
        self._install(im_module, monkeypatch)
        with make_test_directory() as directory_name:
            env_path = Path(directory_name) / ".env"

            with pytest.raises(im_module.SmtpConfigurationError) as raised:
                im_module.run_set_smtp_password(env_file=env_path, interactive=True, input_func=lambda prompt: "y", getpass_func=lambda prompt: self.SECRET, config_path="none")

            assert self.SECRET not in str(raised.value)
            assert "[private value]" in str(raised.value)
            assert "did not accept the password" in str(raised.value)
            assert not env_path.exists()

    # Setup renders the same reply through its own detail line, which the wizard prints under the summary
    def test_the_wizard_check_does_not_return_what_was_typed(self, im_module, monkeypatch, real_smtp_sign_in):
        self._install(im_module, monkeypatch)
        values = {"SMTP_HOST": "smtp.example.test", "SMTP_PORT": 587, "SMTP_SSL": True, "SMTP_USER": "monitor@example.test", "SENDER_EMAIL": "monitor@example.test", "RECEIVER_EMAIL": "alerts@example.test"}

        summary, detail, fix, retryable = im_module._wizard_verify_smtp(values, self.SECRET)

        assert self.SECRET not in detail
        assert "[private value]" in detail
        assert summary == "The SMTP server rejected the sign-in"
        assert retryable is False

    # Doctor reads the configured password, so the classification and the detail both have to survive redaction
    def test_the_doctor_report_does_not_print_the_configured_password(self, im_module, monkeypatch):
        self._install(im_module, monkeypatch, saved_password=self.SECRET)
        monkeypatch.setattr(im_module, "ERROR_NOTIFICATION", True)
        report = im_module.DoctorReport()

        checks = im_module.doctor_check_notifications(report)

        failed = [check for check in checks if check.status == "FAIL" and check.section == "Notifications"]
        assert failed, "the rejected sign-in was not reported"
        rendered = " ".join(f"{check.label} {check.detail}" for check in failed)
        assert self.SECRET not in rendered
        assert "[private value]" in rendered
        assert "The SMTP server rejected the sign-in" in rendered

    # The sign-in used to publish the candidate as SMTP_PASSWORD and restore it before the caller rendered the
    # failure, which left the caller redacting a value that was no longer there
    def test_the_sign_in_never_publishes_the_password_it_is_checking(self, im_module, monkeypatch):
        seen = []
        self._install(im_module, monkeypatch, saved_password="saved-private-value")
        monkeypatch.setattr(im_module, "smtp_ssl_context", lambda: seen.append(im_module.SMTP_PASSWORD))

        with pytest.raises(im_module.smtplib.SMTPAuthenticationError):
            im_module.smtp_sign_in(self.SECRET)

        assert seen == ["saved-private-value"]
        assert im_module.SMTP_PASSWORD == "saved-private-value"


# A value being checked before it is saved is held by the caller and by no global, so the renderer takes it directly
def test_error_text_redaction_covers_a_value_no_global_holds(im_module, monkeypatch):
    monkeypatch.setattr(im_module, "SMTP_PASSWORD", "")

    assert im_module.sanitize_error_text("reply quoting candidate-private-value") == "reply quoting candidate-private-value"
    assert im_module.sanitize_error_text("reply quoting candidate-private-value", "candidate-private-value") == "reply quoting [private value]"
    assert im_module.sanitize_error_text("reply quoting abc", "abc") == "reply quoting abc"
    assert im_module.format_error_message(ValueError("reply quoting candidate-private-value"), "candidate-private-value") == "ValueError: reply quoting [private value]"


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
        im_module.print_welcome_screen(None)

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
    monkeypatch.setattr(im_module, "_wizard_collect_connection_section", lambda state: None)
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
        install_saving_wizard_flow(im_module, monkeypatch, [True, False, False, False, True, KeyboardInterrupt])
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


# Runs the real email section with every other prompt answered, returning the questions asked and the stored secret
def run_email_password_section(im_module, monkeypatch, directory, saved=None, replace=True):
    if saved is not None:
        (directory / ".env").write_text(f'SMTP_PASSWORD="{saved}"\n', encoding="utf-8")
    state = make_setup_state(im_module, directory)
    questions = []

    def yes_no(question, default=True):
        questions.append(question)
        return replace if "Replace the SMTP password" in question else True

    monkeypatch.setattr(im_module, "_wizard_ask_yes_no", yes_no)
    monkeypatch.setattr(im_module, "_wizard_ask_text", mail_answer)
    monkeypatch.setattr(im_module, "_wizard_ask_secret", lambda question: "typed-password")
    monkeypatch.setattr(im_module, "_wizard_ask_choice", lambda question, options, default_index=0: 0)
    monkeypatch.setattr(im_module, "_wizard_smtp_sign_in_accepted", lambda values, password: True)
    im_module._wizard_collect_email_section(state)
    return questions, state


class TestSecretReplacePrompt:
    # Verifies a secret already in the dotenv file is kept when the replacement is declined
    def test_an_existing_dotenv_secret_is_kept_unless_the_replacement_is_confirmed(self, im_module, monkeypatch, capsys):
        with make_test_directory() as directory_name:
            questions, state = run_email_password_section(im_module, monkeypatch, Path(directory_name), saved="original", replace=False)

            assert "SMTP_PASSWORD" not in state.secret_updates
            assert any("Replace the SMTP password already configured" in question for question in questions)
            assert "Existing SMTP_PASSWORD will be retained" in capsys.readouterr().out

    # Verifies a confirmed replacement is queued for the save step
    def test_a_confirmed_replacement_is_queued(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            questions, state = run_email_password_section(im_module, monkeypatch, Path(directory_name), saved="original", replace=True)

            assert state.secret_updates["SMTP_PASSWORD"] == "typed-password"
            # Consent is asked once, before the value is typed, not again afterwards
            assert len([question for question in questions if "SMTP_PASSWORD" in question or "SMTP password" in question]) == 1

    # Verifies a dotenv file that does not hold the secret yet is written without asking anything
    def test_a_new_secret_is_queued_without_a_question(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            questions, state = run_email_password_section(im_module, monkeypatch, Path(directory_name))

            assert state.secret_updates["SMTP_PASSWORD"] == "typed-password"
            assert not [question for question in questions if "SMTP_PASSWORD" in question or "SMTP password" in question]

    # Verifies both password prompts offer a stored value for replacement before the hidden prompt rather than after it
    def test_both_password_sections_route_through_the_replace_guard(self, im_module):
        from pathlib import Path as _Path

        source = _Path(im_module.__file__).read_text(encoding="utf-8")

        for key in ("SESSION_PASSWORD", "SMTP_PASSWORD"):
            assert source.count(f'_wizard_existing_secret("{key}", state.env_path, secret_updates=state.secret_updates)') == 1
            assert source.count(f'state.secret_updates["{key}"] =') == 1

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
        configure_mail(im_module, monkeypatch)

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

    state.config_path = tmp_path / "saved-settings.conf"
    state.config_path.write_text("\n".join(f"{name} = {value!r}" for name, value in state.config_values.items() if name in im_module.config_template_defaults()) + "\n", encoding="utf-8")
    im_module._wizard_apply_saved_values(state)

    assert im_module.SECRET_SOURCES["SESSION_PASSWORD"] == "dotenv file"


# Verifies a secret exported before startup keeps the environment as its source, since the export still wins
def test_an_exported_secret_is_not_credited_to_the_dotenv_file(im_module, monkeypatch, tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("SESSION_PASSWORD=a-saved-session-password\n", encoding="utf-8")
    monkeypatch.setattr(im_module, "SECRET_SOURCES", {})
    monkeypatch.setattr(im_module, "EXPORTED_SECRET_KEYS", frozenset({"SESSION_PASSWORD"}))
    monkeypatch.setenv("SESSION_PASSWORD", "synthetic-export")
    state = make_setup_state(im_module, tmp_path)
    state.env_path = env_path

    state.config_path = tmp_path / "saved-settings.conf"
    state.config_path.write_text("\n".join(f"{name} = {value!r}" for name, value in state.config_values.items() if name in im_module.config_template_defaults()) + "\n", encoding="utf-8")
    im_module._wizard_apply_saved_values(state)

    assert im_module.SECRET_SOURCES["SESSION_PASSWORD"] == "environment"

    assert im_module.SESSION_PASSWORD == "synthetic-export"


# Verifies a config destination switched off is refused, rather than writing settings to a file named 'none'
def test_setup_refuses_a_config_destination_switched_off(tmp_path):
    result = subprocess.run([sys.executable, str(PROJECT_ROOT / "instagram_monitor.py"), "--setup", "--config-file", "none"], cwd=tmp_path, capture_output=True, text=True, check=False)

    assert result.returncode == 1
    assert "Setup cannot start: --setup requires a config destination. Replace '--config-file none' with a writable path." in result.stdout
    assert "usage:" not in result.stderr
    assert not (tmp_path / "none").exists()


# Verifies the non-interactive message points at the same command and files the sibling monitors name
def test_a_non_interactive_setup_names_the_shared_fallback(im_module, monkeypatch, capsys):
    monkeypatch.setattr(im_module.sys.stdin, "isatty", lambda: False)

    with pytest.raises(SystemExit) as raised:
        im_module.run_setup_wizard()

    assert raised.value.code == 1
    lines = capsys.readouterr().out.splitlines()
    assert lines[-2] == "Run --setup from an interactive shell or use --generate-config and edit the files manually."
    assert lines[-1] == f"Guide: {im_module.QUICK_START_GUIDE_URL}"


# Verifies the port question rejects a number no TCP port can be, instead of saving it for the doctor to reject
def test_the_smtp_port_question_rejects_a_number_above_the_port_range(im_module, monkeypatch, capsys):
    answers = iter(["70000", "y", "2525"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    chosen = im_module._wizard_ask_positive_int("SMTP port", 587, maximum=65535)

    assert chosen == 2525
    assert "  Enter a whole number from 1 through 65535." in capsys.readouterr().out


# Verifies declining the retry offer keeps the saved value rather than asking the same question forever
def test_declining_the_retry_offer_keeps_the_saved_number(im_module, monkeypatch, capsys):
    answers = iter(["70000", "n"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    assert im_module._wizard_ask_positive_int("SMTP port", 587, maximum=65535) == 587


# Verifies the launch offer only follows a doctor run that passed, so a declined doctor ends at the printed commands
def test_declining_the_doctor_removes_the_launch_offer(im_module, monkeypatch):
    with make_test_directory() as directory_name:
        directory = Path(directory_name)
        install_saving_wizard_flow(im_module, monkeypatch, [True, False, False, False, False])
        launch_mock = Mock(side_effect=AssertionError("monitor started"))
        monkeypatch.setattr(im_module, "_wizard_launch_monitor", launch_mock)

        with pytest.raises(SystemExit) as error:
            im_module.run_setup_wizard(config_file=directory / "instagram_monitor.conf", env_file=directory / ".env")

        assert error.value.code == 0
        questions = [call.args[0] for call in im_module._wizard_ask_yes_no.call_args_list]
        assert not any(question.startswith("Start monitoring now?") for question in questions)
        launch_mock.assert_not_called()


# Verifies a doctor run that passed is what unlocks the launch offer
def test_a_passed_doctor_run_unlocks_the_launch_offer(im_module, monkeypatch):
    with make_test_directory() as directory_name:
        directory = Path(directory_name)
        install_saving_wizard_flow(im_module, monkeypatch, [True, False, False, False, True, True])
        launch_mock = Mock(return_value=0)
        monkeypatch.setattr(im_module, "_wizard_launch_monitor", launch_mock)

        with pytest.raises(SystemExit) as error:
            im_module.run_setup_wizard(config_file=directory / "instagram_monitor.conf", env_file=directory / ".env")

        assert error.value.code == 0
        launch_mock.assert_called_once()


# Verifies declining the retry offer after a value the wizard cannot use keeps the default rather than asking again
def test_a_rejected_duration_keeps_the_default(im_module, monkeypatch, capsys):
    prompts = []
    answers = iter(["later", "n"])

    def script(prompt=""):
        prompts.append(prompt)
        return next(answers)

    monkeypatch.setattr("builtins.input", script)

    assert im_module._wizard_ask_duration("Instagram polling interval (seconds or use s/m/h/d)", 60) == 60
    assert "Keeping 60s - 1m." in capsys.readouterr().out
    # The hint the question carries belongs in the prompt, not in the offer that repeats it
    assert any("Try entering the Instagram polling interval again? [Y/n]: " in prompt for prompt in prompts), prompts


@pytest.fixture(autouse=True)
# Starts each setup scenario without file ownership left by another test
def isolated_dotenv_ownership(monkeypatch, im_module):
    monkeypatch.setattr(im_module, "DOTENV_RELOAD_STATE", {})


# Verifies names are opt-in in setup, so pressing Enter through the wizard never requests one
def test_setup_asks_what_to_collect_before_how(im_module, monkeypatch):
    with make_test_directory() as directory_name:
        state = make_setup_state(im_module, Path(directory_name))
        state.logged_in = True
        asked = scripted_connection_choices(im_module, monkeypatch, {})

        im_module._wizard_collect_connection_section(state)

        assert asked["collect"]["options"] == ["Counts only, no names", "Followers only", "Followers and following"]
        assert asked["collect"]["default"] == 0, "the option that never requests a name is the default"
        assert state.config_values["SKIP_FOLLOWERS"] is True
        assert state.config_values["SKIP_FOLLOWINGS"] is True


# Verifies choosing both lists records the answer and goes on to ask where to read them from
def test_setup_can_collect_both_lists(im_module, monkeypatch):
    with make_test_directory() as directory_name:
        state = make_setup_state(im_module, Path(directory_name))
        state.logged_in = True
        asked = scripted_connection_choices(im_module, monkeypatch, {"collect": 2})

        im_module._wizard_collect_connection_section(state)

        assert state.config_values["SKIP_FOLLOWERS"] is False
        assert state.config_values["SKIP_FOLLOWINGS"] is False
        assert "source" in asked
        assert state.config_values["FOLLOW_LIST_SOURCE"] == "auto"


# Verifies the expensive answers name the daily cap and its value, not only the setting that holds it
def test_the_collection_options_name_the_identity_budget(im_module, monkeypatch):
    with make_test_directory() as directory_name:
        state = make_setup_state(im_module, Path(directory_name))
        state.logged_in = True
        monkeypatch.setattr(im_module, "IDENTITY_BUDGET_PER_DAY", 2000)
        described = {}
        asked_question = []

        def ask(question, options, default_index=0):
            if "should be collected" in question:
                asked_question.append(question)
                described.update(dict(options))
            return 0

        monkeypatch.setattr(im_module, "_wizard_ask_choice", ask)

        im_module._wizard_collect_connection_section(state)

        assert "IDENTITY_BUDGET_PER_DAY (currently 2000)" in asked_question[0]
        monkeypatch.setattr(im_module, "IDENTITY_BUDGET_PER_DAY", 750)
        im_module._wizard_collect_connection_section(state)

        assert "(currently 750)" in asked_question[1], "a changed budget is reported as it is, never as the shipped default"
        assert not [label for label, desc in described.items() if "IDENTITY_BUDGET_PER_DAY" in desc], "the cap governs both name options, so it is stated once on the question"


# Verifies a disabled budget is described as disabled instead of showing a cap of zero names a day
def test_the_collection_options_say_when_no_budget_is_set(im_module, monkeypatch):
    with make_test_directory() as directory_name:
        state = make_setup_state(im_module, Path(directory_name))
        state.logged_in = True
        monkeypatch.setattr(im_module, "IDENTITY_BUDGET_PER_DAY", 0)
        described = {}
        asked_question = []

        def ask(question, options, default_index=0):
            if "should be collected" in question:
                asked_question.append(question)
                described.update(dict(options))
            return 0

        monkeypatch.setattr(im_module, "_wizard_ask_choice", ask)

        im_module._wizard_collect_connection_section(state)

        assert "nothing caps how many are collected" in asked_question[0]
        assert "0 names a day" not in asked_question[0]


# Verifies choosing followers only leaves the following list alone while still reading followers
def test_setup_can_collect_followers_only(im_module, monkeypatch):
    with make_test_directory() as directory_name:
        state = make_setup_state(im_module, Path(directory_name))
        state.logged_in = True
        scripted_connection_choices(im_module, monkeypatch, {"collect": 1})

        im_module._wizard_collect_connection_section(state)

        assert state.config_values["SKIP_FOLLOWERS"] is False
        assert state.config_values["SKIP_FOLLOWINGS"] is True
        assert state.config_values["FOLLOW_LIST_SOURCE"] == "auto"


# Verifies a setup that collects no names is never asked where to read them from
def test_setup_skips_the_source_question_when_no_names_are_collected(im_module, monkeypatch):
    with make_test_directory() as directory_name:
        state = make_setup_state(im_module, Path(directory_name))
        state.logged_in = True
        asked = scripted_connection_choices(im_module, monkeypatch, {"collect": 0})

        im_module._wizard_collect_connection_section(state)

        assert state.config_values["SKIP_FOLLOWERS"] is True
        assert state.config_values["SKIP_FOLLOWINGS"] is True
        assert "source" not in asked, "a setup that collects no names has nothing to choose a surface for"
        assert state.config_values["FOLLOW_LIST_SOURCE"] == state.baseline_values["FOLLOW_LIST_SOURCE"], "the saved surface is left as it was rather than rewritten"


# Verifies no-login setup is asked neither question, since no surface lists names without a session
def test_no_login_setup_is_asked_nothing_about_names(im_module, monkeypatch):
    with make_test_directory() as directory_name:
        state = make_setup_state(im_module, Path(directory_name))
        state.logged_in = False
        asked = scripted_connection_choices(im_module, monkeypatch, {})

        im_module._wizard_collect_connection_section(state)

        assert asked == {}


# Verifies the review summary reports what will be collected, not only where it comes from
def test_the_summary_reports_what_is_collected(im_module, capsys):
    with make_test_directory() as directory_name:
        state = make_setup_state(im_module, Path(directory_name))
        state.logged_in = True
        state.config_values.update({"SKIP_FOLLOWERS": True, "SKIP_FOLLOWINGS": True})

        im_module._wizard_print_setup_summary(state, "manual")

        summary = capsys.readouterr().out
        assert "Follower lists:" in summary and "counts only, no names" in summary
        assert "Follower list source:" not in summary, "a setup that collects no names has no surface to report"


# Drives the browser import step with scripted answers and returns the yes/no questions and menus it offered
def run_browser_import(im_module, monkeypatch, directory: Path, browser: str, import_results, answers, choices=()):
    state = make_setup_state(im_module, directory)
    state.logged_in = True
    state.login_method = browser
    state.import_browser = browser
    asked = []
    menus = []
    attempts = iter(import_results)

    def attempt(*args, **kwargs):
        outcome = next(attempts)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    scripted = iter(answers)
    scripted_choices = iter(choices)

    def choose(question, options, default_index=0):
        labels = [label for label, _ in options]
        menus.append({"question": question, "labels": labels, "options": dict(options), "default": default_index})
        wanted = next(scripted_choices)
        return next(index for index, label in enumerate(labels) if wanted in label)

    monkeypatch.setattr(im_module, "import_session", attempt)
    monkeypatch.setattr(im_module, "select_chromium_profile_cli", lambda browser_name, explicit: "Default")
    monkeypatch.setattr(im_module, "get_firefox_cookiefile", lambda: str(directory / "cookies.sqlite"))
    monkeypatch.setattr(im_module, "_wizard_ask_yes_no", lambda question, default=True: (asked.append(question), next(scripted))[1])
    monkeypatch.setattr(im_module, "_wizard_ask_choice", choose)
    monkeypatch.setattr(im_module, "_wizard_ask_text", lambda *args, **kwargs: "typed.user")
    completed = im_module._wizard_finish_browser_import(state, "manual")
    return completed, asked, menus, state


class TestBrowserImportRetry:
    # Verifies a failed import offers another attempt rather than dropping setup through to the username prompt
    def test_a_failed_import_can_be_retried_on_the_spot(self, im_module, monkeypatch, capsys):
        with make_test_directory() as directory_name:
            directory = Path(directory_name)
            (directory / "cookies.sqlite").write_text("", encoding="utf-8")
            failure = im_module.CookieImportError("No Instagram cookies found in Chrome (profile 'Default')")
            completed, asked, menus, state = run_browser_import(im_module, monkeypatch, directory, "chrome", [failure, "login.user"], [True], ["Try the Chrome import again"])

        assert completed is True
        assert state.session_username == "login.user"
        assert any("Try the Chrome import again" in label for label in menus[0]["labels"])
        assert "Chrome import failed" in capsys.readouterr().out

    # Verifies skipping the import stops asking and leaves it marked incomplete
    def test_skipping_the_import_stops_asking(self, im_module, monkeypatch, capsys):
        with make_test_directory() as directory_name:
            directory = Path(directory_name)
            (directory / "cookies.sqlite").write_text("", encoding="utf-8")
            failure = im_module.CookieImportError("No Instagram cookies found in Chrome (profile 'Default')")
            completed, asked, menus, state = run_browser_import(im_module, monkeypatch, directory, "chrome", [failure], [True], ["Skip the import"])

        assert completed is False
        assert len(menus) == 1
        assert "--import-browser-session" in capsys.readouterr().out

    # Verifies a failed import can move to another browser, since the session often lives in one setup did not offer first
    def test_a_failed_import_can_switch_to_another_browser(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            directory = Path(directory_name)
            (directory / "cookies.sqlite").write_text("", encoding="utf-8")
            failure = im_module.CookieImportError("No Instagram cookies found in Chrome (profile 'Default')")
            completed, asked, menus, state = run_browser_import(im_module, monkeypatch, directory, "chrome", [failure, "login.user"], [True], ["Import from a different browser", "Firefox"])

        assert completed is True
        assert state.import_browser == "firefox", "the retry imports from the browser the user switched to"
        assert state.login_method == "firefox", "the saved login method follows the switch, so the summary and a rerun agree with it"
        assert state.session_username == "login.user"

    # Verifies backing out of the browser list keeps the current browser instead of ending the import
    def test_cancelling_the_switch_keeps_the_current_browser(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            directory = Path(directory_name)
            failure = im_module.CookieImportError("No Instagram cookies found in Chrome (profile 'Default')")
            completed, asked, menus, state = run_browser_import(im_module, monkeypatch, directory, "chrome", [failure, "login.user"], [True], ["Import from a different browser", "Keep trying the current browser"])

        assert completed is True
        assert state.import_browser == "chrome"

    # Verifies the retry menu is not offered for a browser the platform cannot import from
    def test_no_switch_is_offered_when_only_one_browser_is_supported(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            directory = Path(directory_name)
            (directory / "cookies.sqlite").write_text("", encoding="utf-8")
            monkeypatch.setattr(im_module, "_wizard_import_browsers", lambda method: ["firefox"])
            failure = im_module.CookieImportError("No Instagram cookies found in Firefox")
            completed, asked, menus, state = run_browser_import(im_module, monkeypatch, directory, "firefox", [failure], [True], ["Skip the import"])

        assert completed is False
        assert not any("different browser" in label for label in menus[0]["labels"])

    # Verifies an aborted profile picker is treated as a failed attempt rather than ending setup
    def test_an_aborted_profile_picker_is_retryable(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            directory = Path(directory_name)
            (directory / "cookies.sqlite").write_text("", encoding="utf-8")
            state = make_setup_state(im_module, directory)
            state.logged_in = True
            state.import_browser = "chrome"
            asked = []
            picks = iter([SystemExit("No profile selected, aborting ..."), "Profile 1"])

            def pick(browser_name, explicit):
                outcome = next(picks)
                if isinstance(outcome, BaseException):
                    raise outcome
                return outcome

            scripted = iter([True])
            monkeypatch.setattr(im_module, "select_chromium_profile_cli", pick)
            monkeypatch.setattr(im_module, "import_session", lambda *args, **kwargs: "login.user")
            monkeypatch.setattr(im_module, "_wizard_ask_yes_no", lambda question, default=True: (asked.append(question), next(scripted))[1])
            monkeypatch.setattr(im_module, "_wizard_ask_choice", lambda question, options, default_index=0: 0)

            assert im_module._wizard_finish_browser_import(state, "manual") is True
            assert state.session_username == "login.user"

    # Verifies declining the import outright is still one question, with no retry offered for an attempt never made
    def test_declining_the_import_offers_no_retry(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            directory = Path(directory_name)
            completed, asked, menus, state = run_browser_import(im_module, monkeypatch, directory, "chrome", [], [False])

        assert completed is False
        assert menus == []


# Drives the login menu with scripted option labels and yes/no answers, reporting the session files it should see
def run_login_section(im_module, monkeypatch, directory: Path, labels, answers=(), session_files=None):
    state = make_setup_state(im_module, directory)
    asked = []
    scripted_labels = iter(labels)
    scripted_answers = iter(answers)

    def choose(question, options, default_index=0):
        wanted = next(scripted_labels)
        return next(index for index, (label, _) in enumerate(options) if wanted in label)

    monkeypatch.setattr(im_module, "_wizard_ask_choice", choose)
    monkeypatch.setattr(im_module, "_wizard_ask_text", lambda *args, **kwargs: "login.user")
    monkeypatch.setattr(im_module, "_wizard_ask_yes_no", lambda question, default=True: (asked.append(question), next(scripted_answers))[1])
    monkeypatch.setattr(im_module, "get_session_file_candidates", lambda username: list(session_files) if session_files is not None else [str(directory / f"session-{username}")])
    im_module._wizard_collect_login_section(state, "manual")
    return state, asked


class TestExistingInstaloaderSession:
    # Verifies the only login method that depends on a file setup does not create is checked before it is saved
    def test_a_missing_session_file_returns_to_the_login_menu(self, im_module, monkeypatch, capsys):
        with make_test_directory() as directory_name:
            directory = Path(directory_name)
            state, asked = run_login_section(im_module, monkeypatch, directory, ["Use an existing Instaloader session", "No login"], answers=[False])

        output = capsys.readouterr().out
        assert state.login_method == "no-login"
        assert state.config_values["SKIP_SESSION"] is True
        assert "No Instaloader session file was found" in output
        assert "instaloader --login login.user" in output

    # Verifies an account that already has a session file is saved without a warning
    def test_an_existing_session_file_is_accepted(self, im_module, monkeypatch, capsys):
        with make_test_directory() as directory_name:
            directory = Path(directory_name)
            session_file = directory / "session-login.user"
            session_file.write_text("", encoding="utf-8")
            state, asked = run_login_section(im_module, monkeypatch, directory, ["Use an existing Instaloader session"], session_files=[str(session_file)])

        assert state.login_method == "existing"
        assert state.config_values["SKIP_SESSION"] is False
        assert state.config_values["SESSION_USERNAME"] == "login.user"
        assert "No Instaloader session file was found" not in capsys.readouterr().out
        assert asked == []

    # Verifies the warning can be overridden, since the session may be created before monitoring starts
    def test_the_warning_can_be_overridden(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            directory = Path(directory_name)
            state, asked = run_login_section(im_module, monkeypatch, directory, ["Use an existing Instaloader session"], answers=[True])

        assert state.config_values["SKIP_SESSION"] is False
        assert state.config_values["SESSION_USERNAME"] == "login.user"


# Leaves the browser session cache populated, so the next test proves the shared fixture empties it again. A cache
# carried into a later test changes what that test sees and fails only in a full run, never when it runs alone
def test_the_wizard_browser_cache_can_be_left_populated():
    im._WIZARD_BROWSER_SESSION_COUNTS["firefox"] = (1, 1)

    assert im._WIZARD_BROWSER_SESSION_COUNTS


# Verifies the shared fixture resets the browser session cache, so the test above cannot bias this one
def test_the_wizard_browser_cache_is_reset_between_tests():
    assert im._WIZARD_BROWSER_SESSION_COUNTS == {}


# Stubs the profile listings so the login menu describes a known set of browsers
def stub_browser_profiles(im_module, monkeypatch, firefox, chromium):
    monkeypatch.setattr(im_module, "list_firefox_profiles", lambda: [{"dir": f"x.{name}", "name": name, "path": f"/f/{name}", "install": ""} for name in firefox])
    monkeypatch.setattr(im_module, "list_chromium_profiles", lambda browser: [{"dir": name, "name": name, "cookie_file": f"/c/{browser}/{name}"} for name in chromium.get(browser, [])])
    monkeypatch.setattr(im_module, "cookie_file_has_instagram_session", lambda cookie_file, firefox=False: str(cookie_file).endswith("signed"))
    monkeypatch.setattr(im_module, "_wizard_chromium_dependency_available", lambda: True)
    im_module._WIZARD_BROWSER_SESSION_COUNTS.clear()


# Drives the login menu and returns the option descriptions it offered for each question
def collect_login_menus(im_module, monkeypatch, directory: Path, method: str, answers):
    monkeypatch.setattr(im_module, "system", lambda: "Linux")
    state = make_setup_state(im_module, directory)
    menus = {}
    scripted = iter(answers)

    def ask(question, options, default_index=0):
        key = "login" if "access Instagram" in question else "chromium"
        menus[key] = {"options": dict(options), "labels": [label for label, _ in options], "default": default_index}
        return next(scripted)

    monkeypatch.setattr(im_module, "_wizard_ask_choice", ask)
    monkeypatch.setattr(im_module, "_wizard_ask_text", lambda *args, **kwargs: "login.user")
    im_module._wizard_collect_login_section(state, method)
    return menus, state


class TestLoginMenuReportsBrowserSessions:
    # Verifies the browser choice reports which browsers actually hold a session, rather than being made blind
    def test_the_menu_names_the_browsers_holding_a_session(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            stub_browser_profiles(im_module, monkeypatch, ["a-signed", "b", "c"], {"chrome": ["Default-signed"], "brave": ["Default"], "chromium": []})
            menus, _ = collect_login_menus(im_module, monkeypatch, Path(directory_name), "manual", [2, 0])

        assert "1 of 3 profiles here are signed in to Instagram." in menus["login"]["options"]["Import from Firefox, recommended"]
        assert "Signed in here: Chrome." in menus["login"]["options"]["Import from Chrome, Brave or Chromium"]

    # Verifies a machine with no signed-in Chromium profile is told so before pycookiecheat is even needed
    def test_no_chromium_session_is_reported_on_the_group_option(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            stub_browser_profiles(im_module, monkeypatch, ["a-signed"], {"chrome": ["Default"], "brave": [], "chromium": []})
            menus, _ = collect_login_menus(im_module, monkeypatch, Path(directory_name), "manual", [2, 0])

        assert "None of them has a signed-in profile on this machine." in menus["login"]["options"]["Import from Chrome, Brave or Chromium"]

    # Verifies the Chromium sub-menu leads with the browser the import can actually succeed with
    def test_the_chromium_submenu_defaults_to_the_signed_in_browser(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            stub_browser_profiles(im_module, monkeypatch, [], {"chrome": ["Default"], "brave": ["Default-signed"], "chromium": []})
            menus, state = collect_login_menus(im_module, monkeypatch, Path(directory_name), "manual", [2, 1])

        assert menus["chromium"]["labels"] == ["Chrome", "Brave", "Chromium"]
        assert menus["chromium"]["default"] == 1
        assert state.import_browser == "brave"

    # Verifies a browser with no profiles is named as absent instead of described as one you can import from
    def test_a_browser_without_profiles_is_named_as_absent(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            stub_browser_profiles(im_module, monkeypatch, [], {"chrome": ["Default-signed"], "brave": [], "chromium": []})
            menus, _ = collect_login_menus(im_module, monkeypatch, Path(directory_name), "manual", [2, 0])

        assert menus["chromium"]["options"]["Brave"] == "No Brave profiles were found on this machine."
        assert "Import from the signed-in Brave profile" not in menus["chromium"]["options"]["Brave"]
        assert menus["login"]["options"]["Import from Firefox, recommended"].endswith("No Firefox profiles were found on this machine.")

    # Verifies a container describes nothing local, since the host profiles it imports are not mounted yet
    def test_a_container_setup_describes_no_local_profiles(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            stub_browser_profiles(im_module, monkeypatch, ["a-signed"], {})
            monkeypatch.setattr(im_module, "_wizard_select_container_firefox_host", lambda: "macos")
            menus, _ = collect_login_menus(im_module, monkeypatch, Path(directory_name), "docker", [1])

        firefox_option = menus["login"]["options"]["Import from Firefox after setup, recommended"]
        assert "signed in to Instagram" not in firefox_option
        assert "were found on this machine" not in firefox_option

    # Verifies an unreadable profile listing leaves the menu silent rather than claiming a browser is unusable
    def test_an_unreadable_listing_says_nothing(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            stub_browser_profiles(im_module, monkeypatch, [], {})
            monkeypatch.setattr(im_module, "list_firefox_profiles", lambda: (_ for _ in ()).throw(OSError("permission denied")))
            im_module._WIZARD_BROWSER_SESSION_COUNTS.clear()
            menus, _ = collect_login_menus(im_module, monkeypatch, Path(directory_name), "manual", [1])

        assert menus["login"]["options"]["Import from Firefox, recommended"] == "Reuses your Firefox session with no additional package."


# Runs the target section with scripted answers, returning the collected targets and everything printed
def run_target_section(im_module, monkeypatch, directory, answers, retries=(), allow_empty=False):
    state = make_setup_state(im_module, directory)
    state.targets = []
    monkeypatch.setattr(im_module, "_wizard_ask_text", Mock(side_effect=list(answers)))
    monkeypatch.setattr(im_module, "_wizard_ask_yes_no", Mock(side_effect=list(retries) + [True] * 8))
    im_module._wizard_collect_target_section(state, allow_empty=allow_empty)
    return state


class TestTargetsAreCheckedBeforeTheyAreSaved:
    # The welcome screen offers a profile URL, so setup and monitoring both have to take one
    @pytest.mark.parametrize("answer,expected", [
        ("https://www.instagram.com/someuser/", ["someuser"]),
        ("instagram.com/Some.User", ["some.user"]),
        ("@someuser, other.user", ["someuser", "other.user"]),
    ])
    def test_a_profile_url_is_stored_as_the_account_name(self, im_module, monkeypatch, answer, expected):
        with make_test_directory() as directory_name:
            state = run_target_section(im_module, monkeypatch, Path(directory_name), [answer])

            assert state.targets == expected
            assert state.config_values["TARGET_USERNAMES"] == expected

    # A target setup accepts and monitoring refuses turns a finished setup into a command that stops before it starts
    @pytest.mark.parametrize("answer", ["not a username!!", "https://www.instagram.com/p/ABC123/", "a" * 31])
    def test_a_target_the_next_run_would_refuse_is_re_asked(self, im_module, monkeypatch, capsys, answer):
        with make_test_directory() as directory_name:
            state = run_target_section(im_module, monkeypatch, Path(directory_name), [answer, "good.user"], retries=[False])

            assert state.targets == ["good.user"]
            assert "cannot be monitored" in capsys.readouterr().out
            for target in state.targets:
                assert im_module.normalize_instagram_username(target) == target

    # Choosing to continue without a target has to end the question rather than loop on an answer setup will not take
    def test_continuing_without_a_target_leaves_the_list_empty(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            state = run_target_section(im_module, monkeypatch, Path(directory_name), ["not a username!!"], retries=[True], allow_empty=True)

            assert state.targets == []
            assert state.config_values["TARGET_USERNAMES"] == []


class TestEditingLoginReasksTheListQuestion:
    # Runs the review edit menu on one section with the login answer scripted
    @staticmethod
    def _edit_login(im_module, monkeypatch, directory, login_label, start_logged_in):
        state = make_setup_state(im_module, directory)
        state.logged_in = start_logged_in
        state.login_method = "existing" if start_logged_in else "no-login"
        state.config_values.update({"SKIP_FOLLOWERS": False, "SKIP_FOLLOWINGS": False})
        asked = []

        def choose(question, options, default_index=0):
            asked.append(question)
            if "Which setup section" in question:
                return 2
            if "access Instagram" in question:
                return [label for label, _ in options].index(login_label)
            return 0

        monkeypatch.setattr(im_module, "_wizard_ask_choice", choose)
        monkeypatch.setattr(im_module, "_wizard_ask_text", lambda question, default="", required=False: "login.user")
        monkeypatch.setattr(im_module, "_wizard_ask_yes_no", lambda question, default=True: True)
        monkeypatch.setattr(im_module, "_wizard_confirm_existing_session", lambda state: True)
        im_module._wizard_edit_setup_section(state, "pip")
        return asked, state

    # The list questions are their own menu item, so a session enabled here would otherwise write the shipped
    # defaults, which collect every name, without the question that exists to prevent that
    def test_enabling_a_session_asks_what_to_collect(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            asked, state = self._edit_login(im_module, monkeypatch, Path(directory_name), "Use an existing Instaloader session", start_logged_in=False)

            assert state.logged_in is True
            assert any("should be collected" in question for question in asked)
            assert state.config_values["SKIP_FOLLOWERS"] is True
            assert state.config_values["SKIP_FOLLOWINGS"] is True

    # Turning the session off leaves answers the summary stops showing, so the file records what will happen
    def test_removing_the_session_records_counts_only(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            asked, state = self._edit_login(im_module, monkeypatch, Path(directory_name), "No login", start_logged_in=True)

            assert state.logged_in is False
            assert state.config_values["SKIP_FOLLOWERS"] is True
            assert state.config_values["SKIP_FOLLOWINGS"] is True
            assert not any("should be collected" in question for question in asked)

    # Re-picking the same kind of login is not a change, so the list answers already given stand
    def test_keeping_the_session_does_not_re_ask(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            asked, state = self._edit_login(im_module, monkeypatch, Path(directory_name), "Use an existing Instaloader session", start_logged_in=True)

            assert state.logged_in is True
            assert not any("should be collected" in question for question in asked)
            assert state.config_values["SKIP_FOLLOWERS"] is False


class TestMailAnswersAreCheckedBeforeTheyAreSaved:
    # Runs the email section with one answer replaced by a value the sender would refuse
    @staticmethod
    def _collect(im_module, monkeypatch, directory, label, bad_value, retry=True):
        state = make_setup_state(im_module, directory)
        seen = []

        def text(question, default="", required=False):
            seen.append(question)
            return bad_value if question == label and seen.count(label) == 1 else mail_answer(question)

        monkeypatch.setattr(im_module, "_wizard_ask_text", text)
        monkeypatch.setattr(im_module, "_wizard_ask_yes_no", lambda question, default=True: retry if "Try entering" in question else True)
        monkeypatch.setattr(im_module, "_wizard_ask_secret", lambda question: "private-password")
        monkeypatch.setattr(im_module, "_wizard_ask_choice", lambda question, options, default_index=0: 0)
        monkeypatch.setattr(im_module, "_wizard_smtp_sign_in_accepted", lambda values, password: True)
        im_module._wizard_collect_email_section(state)
        return seen, state

    # The sign-in check only proves the username and password, so an address it never sees was reported as working
    @pytest.mark.parametrize("label,key,bad", [("Sender email", "SENDER_EMAIL", "x"), ("Receiver email", "RECEIVER_EMAIL", "nobody@"), ("SMTP host", "SMTP_HOST", "not a host")])
    def test_a_value_the_sender_would_refuse_is_re_asked(self, im_module, monkeypatch, capsys, label, key, bad):
        with make_test_directory() as directory_name:
            seen, state = self._collect(im_module, monkeypatch, Path(directory_name), label, bad)

            assert seen.count(label) == 2
            assert state.config_values[key] != bad
            assert state.want_email is True
            assert "Enter a" in capsys.readouterr().out

    # Abandoning the answer switches email off rather than saving a channel that cannot deliver
    def test_abandoning_the_answer_switches_email_off(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            seen, state = self._collect(im_module, monkeypatch, Path(directory_name), "Sender email", "x", retry=False)

            assert state.want_email is False
            assert state.config_values["STATUS_NOTIFICATION"] is False

    # The addresses setup saves have to be the ones the send path accepts, or setup reports a working channel
    def test_the_saved_addresses_pass_the_send_path_check(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            seen, state = self._collect(im_module, monkeypatch, Path(directory_name), "Sender email", "x")

            for key in ("SENDER_EMAIL", "RECEIVER_EMAIL"):
                assert im_module.is_valid_email_address(state.config_values[key]) is True
            assert im_module.smtp_host_is_usable(state.config_values["SMTP_HOST"]) is True


class TestSessionUsernameIsCheckedWhereItIsCollected:
    # Runs the login section with one scripted username answer
    @staticmethod
    def _collect(im_module, monkeypatch, directory, answers, retries=()):
        state = make_setup_state(im_module, directory)
        monkeypatch.setattr(im_module, "_wizard_ask_choice", lambda question, options, default_index=0: [label for label, _ in options].index("Username and password") if "access Instagram" in question else 0)
        monkeypatch.setattr(im_module, "_wizard_ask_text", Mock(side_effect=list(answers)))
        monkeypatch.setattr(im_module, "_wizard_ask_yes_no", Mock(side_effect=list(retries) + [False] * 8))
        monkeypatch.setattr(im_module, "_wizard_ask_secret", lambda question: "private-password")
        im_module._wizard_collect_login_section(state, "pip")
        return state

    # A name monitoring refuses is otherwise saved as the account to sign in with and fails at the first request
    def test_an_unusable_username_is_re_asked(self, im_module, monkeypatch, capsys):
        with make_test_directory() as directory_name:
            state = self._collect(im_module, monkeypatch, Path(directory_name), ["my account", "login.user"], retries=[True])

            assert state.session_username == "login.user"
            assert state.logged_in is True
            assert "1-30 letters" in capsys.readouterr().out

    def test_declining_the_retry_falls_back_to_no_login(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            state = self._collect(im_module, monkeypatch, Path(directory_name), ["my account"], retries=[False])

            assert state.logged_in is False
            assert state.config_values["SKIP_SESSION"] is True

    # The existing-session check reported a found session for a name no session file can exist for
    def test_the_existing_session_check_refuses_an_unusable_name(self, im_module, monkeypatch, capsys):
        with make_test_directory() as directory_name:
            state = make_setup_state(im_module, Path(directory_name))
            state.session_username = "my account"

            assert im_module._wizard_confirm_existing_session(state) is False
            assert "cannot be used as an Instagram username" in capsys.readouterr().out


# The import prints its next steps for the configuration it was given, so it has to be handed the one setup wrote
def test_the_printed_import_command_carries_the_config(im_module, monkeypatch):
    with make_test_directory() as directory_name:
        monkeypatch.setattr(im_module, "system", lambda: "Linux")
        state = make_setup_state(im_module, Path(directory_name))
        state.import_browser = "chrome"

        command = im_module._wizard_browser_import_command(state, "pip")

        assert f"--config-file {shlex.quote(str(state.config_path))}" in command
        assert f"--env-file {shlex.quote(str(state.env_path))}" in command


# A dashboard moved off the default port was still advertised at the default one
@pytest.mark.parametrize("port,expected", [(8000, "http://127.0.0.1:8000/"), (9443, "http://127.0.0.1:9443/")])
def test_the_dashboard_address_uses_the_configured_port(im_module, monkeypatch, port, expected):
    monkeypatch.setattr(im_module, "WEB_DASHBOARD_PORT", port, raising=False)

    assert im_module.web_dashboard_local_url() == expected
    assert "127.0.0.1:8000" not in Path(im_module.__file__).read_text(encoding="utf-8").split("def web_dashboard_local_url")[1]


# 'python -m instagram_monitor' runs the installed package, so the printed commands must not name a downloaded script
def test_a_module_launch_is_reported_as_an_installed_package(im_module, monkeypatch):
    monkeypatch.setattr(im_module.sys, "argv", ["/opt/venv/lib/python3.14/site-packages/instagram_monitor/__main__.py"])

    assert im_module._wizard_install_method() == "pip"
