"""Tests for install-method detection and the command examples it drives."""

from command_expectations import runtime_command
import shlex
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


# Forces _wizard_install_method to a known launch environment for one assertion
def _force_env(monkeypatch, im_module, *, dockerenv: bool, docker_env: bool, compose_env: bool, argv0: str):
    monkeypatch.setattr(im_module.os.path, "exists", lambda p: dockerenv and p == "/.dockerenv")
    if docker_env:
        monkeypatch.setenv("INSTAGRAM_MONITOR_DOCKER", "1")
    else:
        monkeypatch.delenv("INSTAGRAM_MONITOR_DOCKER", raising=False)
    if compose_env:
        monkeypatch.setenv("INSTAGRAM_MONITOR_COMPOSE", "1")
    else:
        monkeypatch.delenv("INSTAGRAM_MONITOR_COMPOSE", raising=False)
    monkeypatch.setattr(im_module.sys, "argv", [argv0, "--help"])


class TestInstallMethodDetection:
    def test_manual_when_argv_ends_with_py(self, im_module, monkeypatch):
        _force_env(monkeypatch, im_module, dockerenv=False, docker_env=False, compose_env=False, argv0="instagram_monitor.py")
        assert im_module._wizard_install_method() == "manual"

    def test_pip_when_argv_has_no_py_suffix(self, im_module, monkeypatch):
        _force_env(monkeypatch, im_module, dockerenv=False, docker_env=False, compose_env=False, argv0="/usr/local/bin/instagram_monitor")
        assert im_module._wizard_install_method() == "pip"

    def test_docker_via_dockerenv_file(self, im_module, monkeypatch):
        _force_env(monkeypatch, im_module, dockerenv=True, docker_env=False, compose_env=False, argv0="instagram_monitor.py")
        assert im_module._wizard_install_method() == "docker"

    def test_compose_when_compose_env_set(self, im_module, monkeypatch):
        _force_env(monkeypatch, im_module, dockerenv=True, docker_env=False, compose_env=True, argv0="instagram_monitor.py")
        assert im_module._wizard_install_method() == "compose"


class TestInstallMethodDisplayNames:
    # Every detected method reaches the startup summary as a readable name
    def test_every_method_has_a_readable_name(self, im_module):
        assert im_module.install_method_display_name("manual") == "downloaded script"
        assert im_module.install_method_display_name("pip") == "PyPI install"
        assert im_module.install_method_display_name("docker") == "Docker container"
        assert im_module.install_method_display_name("compose") == "Docker Compose container"

    # Without an explicit method the name follows the detected launch environment
    def test_detected_method_is_used_by_default(self, im_module, monkeypatch):
        _force_env(monkeypatch, im_module, dockerenv=False, docker_env=False, compose_env=False, argv0="instagram_monitor.py")
        assert im_module.install_method_display_name() == "downloaded script"


class TestStartupSummaryDiagnostics:
    # The install method and secret origins belong to the complete view, named and never valued
    def test_full_summary_reports_install_method_and_secret_origins(self, im_module, monkeypatch, tmp_path, capsys):
        env_file = tmp_path / ".env"
        env_file.write_text("SMTP_PASSWORD=from-file\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("WEBHOOK_URL", "https://ntfy.sh/topic")
        monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py", "target.user", "--verbose", "--env-file", str(env_file), "--no-color", "--disable-logging"])
        monkeypatch.setattr(im_module, "CLI_CONFIG_PATH", None)
        monkeypatch.setattr(im_module, "DASHBOARD_ENABLED", False)
        monkeypatch.setattr(im_module, "WEB_DASHBOARD_ENABLED", False)
        monkeypatch.setattr(im_module, "find_config_file", lambda path=None: None)
        monkeypatch.setattr(im_module, "clear_screen", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "check_internet", lambda: True)
        monkeypatch.setattr(im_module, "start_dashboard_input_handler", Mock(side_effect=SystemExit(0)))

        with pytest.raises(SystemExit):
            im_module.run_main()

        output = capsys.readouterr().out
        assert "* Install method:" in output and "downloaded script" in output
        assert "* Secrets from dotenv:" in output and "SMTP_PASSWORD" in output
        assert "* Secrets from environment:" in output and "WEBHOOK_URL" in output
        assert "from-file" not in output and "ntfy.sh/topic" not in output


class TestCmdPrefix:
    def test_manual_matches_active_python_name(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "system", lambda: "Linux")
        monkeypatch.setattr(im_module.sys, "executable", "/opt/runtime/python3.13")
        assert im_module._wizard_cmd_prefix("manual") == runtime_command("python3 instagram_monitor.py")

    def test_pip(self, im_module):
        assert im_module._wizard_cmd_prefix("pip") == runtime_command("instagram_monitor")

    def test_docker_only_web_adds_port_publish(self, im_module):
        assert "-p 127.0.0.1:8000:8000" not in im_module._wizard_cmd_prefix("docker")
        assert "-p 127.0.0.1:8000:8000" in im_module._wizard_cmd_prefix("docker", web_dashboard=True)
        assert "-p 127.0.0.1:9123:9123" in im_module._wizard_cmd_prefix("docker", web_dashboard=True, web_dashboard_port=9123)

    def test_docker_uses_host_shell_identity_on_linux_and_no_override_on_macos(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module.os, "getuid", lambda: 1234, raising=False)
        monkeypatch.setattr(im_module.os, "getgid", lambda: 5678, raising=False)

        prefix = im_module._wizard_cmd_prefix("docker")

        assert '--user "$(id -u):$(id -g)"' in prefix
        assert '-v "${PWD}:/data:z"' in prefix
        assert "--user" not in im_module._wizard_cmd_prefix("docker", host_os="macos")
        assert '--user "$(id -u):$(id -g)"' in im_module._wizard_cmd_prefix("docker", host_os="linux")
        assert '-v "${PWD}:/data:z"' in im_module._wizard_cmd_prefix("docker", host_os="windows-powershell")
        assert '-v "%cd%:/data:z"' in im_module._wizard_cmd_prefix("docker", host_os="windows-cmd")
        assert "--user" not in im_module._wizard_cmd_prefix("docker", host_os="windows-powershell")
        assert "--user" not in im_module._wizard_cmd_prefix("docker", host_os="windows-cmd")

    def test_compose_only_web_adds_service_ports(self, im_module):
        assert im_module._wizard_cmd_prefix("compose") == "docker compose run --rm instagram_monitor"
        assert im_module._wizard_cmd_prefix("compose", web_dashboard=True) == "docker compose run --rm --service-ports instagram_monitor"
        assert im_module._wizard_cmd_prefix("compose", web_dashboard=True, web_dashboard_port=9123) == "docker compose run --rm -p 127.0.0.1:9123:9123 instagram_monitor"


class TestWebDashboardBrowserUrl:
    @pytest.mark.parametrize("bind_host,expected", [("0.0.0.0", "http://127.0.0.1:8123/"), ("::", "http://127.0.0.1:8123/"), ("127.0.0.1", "http://127.0.0.1:8123/"), ("::1", "http://[::1]:8123/"), ("dashboard.local", "http://dashboard.local:8123/")])
    def test_server_bind_is_rendered_as_a_browser_safe_url(self, im_module, bind_host, expected):
        assert im_module._web_dashboard_browser_url(bind_host, 8123) == expected

    def test_container_startup_prints_browser_url_and_publish_hint(self, im_module, monkeypatch, capsys):
        app = Mock()
        thread = Mock()
        monkeypatch.setattr(im_module, "FLASK_AVAILABLE", True)
        monkeypatch.setattr(im_module, "WEB_DASHBOARD_ENABLED", True)
        monkeypatch.setattr(im_module, "WEB_DASHBOARD_HOST", "0.0.0.0")
        monkeypatch.setattr(im_module, "WEB_DASHBOARD_PORT", 8000)
        monkeypatch.setattr(im_module, "WEB_DASHBOARD_APP", None)
        monkeypatch.setattr(im_module, "WEB_DASHBOARD_THREAD", None)
        monkeypatch.setattr(im_module, "create_web_dashboard_app", lambda: app)
        monkeypatch.setattr(im_module, "_running_in_container", lambda: True)
        monkeypatch.setattr(im_module.threading, "Thread", Mock(return_value=thread))

        assert im_module.start_web_dashboard_server() is True

        output = capsys.readouterr().out
        assert "Open Web Dashboard in your browser:\thttp://127.0.0.1:8000/" in output
        assert "0.0.0.0" not in output
        assert "Use -p 127.0.0.1:8000:8000 or Compose --service-ports" in output
        thread.start.assert_called_once_with()


class TestFirefoxImportCmd:
    def test_non_container_has_no_mount(self, im_module):
        assert im_module._firefox_import_cmd("pip") == runtime_command("instagram_monitor --import-browser-session --browser firefox")

    @pytest.mark.parametrize("host_os,source", [("macos", '"${HOME}/Library/Application Support/Firefox/Profiles:/home/instagram/.mozilla/firefox:ro"'), ("linux", '"$HOME/.mozilla/firefox:/home/instagram/.mozilla/firefox:ro"'), ("linux-snap", '"$HOME/snap/firefox/common/.mozilla/firefox:/home/instagram/.mozilla/firefox:ro"'), ("linux-flatpak", '"$HOME/.var/app/org.mozilla.firefox/.mozilla/firefox:/home/instagram/.mozilla/firefox:ro"'), ("windows-powershell", '"$env:APPDATA\\Mozilla\\Firefox\\Profiles:/home/instagram/.mozilla/firefox:ro"'), ("windows-cmd", '"%APPDATA%\\Mozilla\\Firefox\\Profiles:/home/instagram/.mozilla/firefox:ro"')])
    def test_container_commands_mount_selected_host_profile(self, im_module, host_os, source):
        docker = im_module._firefox_import_cmd("docker", host_os=host_os)
        compose = im_module._firefox_import_cmd("compose", host_os=host_os)
        assert f"-v {source} misiektoja/instagram-monitor" in docker
        assert ('--user "$(id -u):$(id -g)"' in docker) is host_os.startswith("linux")
        assert ('-v "%cd%:/data:z"' in docker) is (host_os == "windows-cmd")
        assert docker.endswith("--import-browser-session --browser firefox")
        assert compose == f"docker compose run --rm -v {source} instagram_monitor --import-browser-session --browser firefox"

    def test_setup_import_command_carries_config_and_targets(self, im_module, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        command = im_module._firefox_import_cmd("docker", tmp_path / ".env", host_os="macos", config_path=tmp_path / "instagram_monitor.conf", targets=["target.user"])
        assert "--import-browser-session --browser firefox target.user" in command
        assert "--config-file /data/instagram_monitor.conf --env-file /data/.env" in command


class TestFirefoxProfileDiscovery:
    # Verifies native, Snap and Flatpak Firefox profiles are discovered without duplicate cookie paths
    def test_linux_discovers_package_variants(self, im_module, monkeypatch, real_browser_profiles):
        monkeypatch.setattr(im_module, "system", lambda: "Linux")
        monkeypatch.setattr(im_module, "FIREFOX_LINUX_COOKIE", "/native/*/cookies.sqlite")
        matches = {"/native/*/cookies.sqlite": ["/native/a.default-release/cookies.sqlite"], "/home/test/snap/firefox/common/.mozilla/firefox/*/cookies.sqlite": ["/snap/b.default/cookies.sqlite"], "/home/test/.var/app/org.mozilla.firefox/.mozilla/firefox/*/cookies.sqlite": ["/flatpak/c.work/cookies.sqlite", "/native/a.default-release/cookies.sqlite"]}
        monkeypatch.setattr(im_module, "expanduser", lambda value: value.replace("~", "/home/test", 1))
        monkeypatch.setattr(im_module, "glob", lambda pattern: matches.get(pattern, []))
        profiles = im_module.list_firefox_profiles()
        assert [profile["path"] for profile in profiles] == ["/native/a.default-release/cookies.sqlite", "/snap/b.default/cookies.sqlite", "/flatpak/c.work/cookies.sqlite"]
        assert [profile["name"] for profile in profiles] == ["default-release", "default", "work"]

    # Verifies macOS keeps using only its configured Firefox pattern, since it has no packaged install to find
    def test_macos_uses_only_its_configured_pattern(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "system", lambda: "Darwin")
        monkeypatch.setattr(im_module, "FIREFOX_MACOS_COOKIE", "/custom/firefox/*/cookies.sqlite")
        assert im_module.firefox_cookie_patterns() == ("/custom/firefox/*/cookies.sqlite",)


class TestWizardImportBrowsers:
    def test_non_container_unix_offers_all_browsers(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "system", lambda: "Darwin")
        assert im_module._wizard_import_browsers("pip") == list(im_module.IMPORT_BROWSERS)
        assert "chrome" in im_module._wizard_import_browsers("manual")

    def test_windows_offers_firefox_only(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "system", lambda: "Windows")
        assert im_module._wizard_import_browsers("pip") == ["firefox"]

    def test_container_offers_firefox_only(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "system", lambda: "Linux")
        assert im_module._wizard_import_browsers("docker") == ["firefox"]
        assert im_module._wizard_import_browsers("compose") == ["firefox"]


class TestProfileListSpacing:
    # Verifies Firefox profile choices start after a blank line
    def test_firefox_choices_have_leading_blank_line(self, im_module, monkeypatch, capsys):
        profiles = [{"dir": "one.default", "name": "one", "path": "/tmp/one/cookies.sqlite"}, {"dir": "two.default", "name": "two", "path": "/tmp/two/cookies.sqlite"}]
        monkeypatch.setattr(im_module, "list_firefox_profiles", lambda: profiles)
        monkeypatch.setattr("builtins.input", lambda prompt: "1")
        assert im_module.get_firefox_cookiefile() == profiles[0]["path"]
        assert capsys.readouterr().out.startswith("\nMultiple Firefox profiles found:")

    # Verifies Chromium profile choices start after a blank line
    def test_chromium_choices_have_leading_blank_line(self, im_module, monkeypatch, capsys):
        profiles = [{"dir": "Default", "name": "Personal"}, {"dir": "Profile 1", "name": "Work"}]
        monkeypatch.setattr(im_module, "system", lambda: "Linux")
        monkeypatch.setattr(im_module, "list_chromium_profiles", lambda browser: profiles)
        monkeypatch.setattr("builtins.input", lambda prompt: "2")
        assert im_module.select_chromium_profile_cli("chrome", None) == profiles[1]["dir"]
        assert capsys.readouterr().out.startswith("\nMultiple Chrome profiles found:")


class TestWizardBrowserDesc:
    def test_firefox_mentions_no_extra_packages(self, im_module):
        assert "no extra packages" in im_module._wizard_browser_desc("firefox")

    def test_chromium_family_names_the_selected_browser(self, im_module):
        for browser in im_module.CHROMIUM_IMPORT_BROWSERS:
            desc = im_module._wizard_browser_desc(browser)
            assert "signed-in" in desc
            assert im_module.browser_label(browser) in desc


class TestPortableWizardCommands:
    @pytest.mark.parametrize("method", ["docker", "compose"])
    def test_container_setup_destinations_use_data_mount(self, im_module, method, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config_path, env_path = im_module._wizard_destinations(method)
        assert config_path == Path("/data/instagram_monitor.conf")
        assert env_path == Path("/data/.env")

    @pytest.mark.parametrize("method", ["docker", "compose"])
    def test_container_setup_rejects_destinations_outside_data(self, im_module, method):
        with pytest.raises(ValueError, match="must be inside /data"):
            im_module._wizard_destinations(method, "/tmp/custom.conf", "/data/.env")
        with pytest.raises(ValueError, match="must be inside /data"):
            im_module._wizard_destinations(method, "/data/custom.conf", "/tmp/custom.env")

    def test_container_paths_already_inside_data_are_preserved(self, im_module):
        assert im_module._wizard_container_path("/data/nested/custom.conf") == "/data/nested/custom.conf"

    def test_action_command_quotes_custom_paths(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "system", lambda: "Linux")
        monkeypatch.setattr(im_module.sys, "executable", "/opt/Python Runtime/python3")
        config_path = Path("/tmp/Instagram Monitor/custom config.conf")
        env_path = Path("/tmp/Instagram Monitor/custom secrets.env")

        command = im_module._wizard_action_command("manual", "--doctor", config_path, env_path, ["target.user"])

        assert command.startswith(runtime_command("python3 instagram_monitor.py --doctor"))
        assert f"--config-file '{config_path.resolve()}'" in command
        assert f"--env-file '{env_path.resolve()}'" in command
        assert "target.user" in command

    # A value only shaped like a placeholder is user input, so pasting the rendered command must not run a substitution
    def test_a_value_shaped_like_a_placeholder_is_quoted(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "system", lambda: "Linux")
        crafted = "<$(echo>marker)>"

        assert shlex.split(im_module._wizard_quote_argument(crafted)) == [crafted]
        assert im_module._wizard_quote_argument("<target_insta_user>") == "<target_insta_user>"

    def test_windows_renderer_quotes_paths_with_spaces(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "system", lambda: "Windows")
        command = im_module._wizard_render_command([r"C:\Python Dev\python.exe", r"C:\Python Dev\instagram_monitor.py", "--env-file", r"C:\Python Dev\.env"])
        assert command == r'"C:\Python Dev\python.exe" "C:\Python Dev\instagram_monitor.py" --env-file "C:\Python Dev\.env"'

    def test_windows_launch_uses_argument_list(self, im_module, monkeypatch):
        run_mock = Mock(return_value=SimpleNamespace(returncode=7))
        monkeypatch.setattr(im_module, "system", lambda: "Windows")
        monkeypatch.setattr(im_module.subprocess, "run", run_mock)
        arguments = [r"C:\Python Dev\python.exe", r"C:\Python Dev\instagram_monitor.py", "--doctor"]

        assert im_module._wizard_launch_monitor(arguments) == 7
        run_mock.assert_called_once_with(arguments, check=False)

    # A Windows parent launch treats duplicate Ctrl+C delivery as clean child termination
    def test_windows_launch_handles_parent_keyboard_interrupt(self, im_module, monkeypatch):
        run_mock = Mock(side_effect=KeyboardInterrupt)
        monkeypatch.setattr(im_module, "system", lambda: "Windows")
        monkeypatch.setattr(im_module.subprocess, "run", run_mock)
        arguments = [r"C:\Python Dev\python.exe", r"C:\Python Dev\instagram_monitor.py", "--doctor"]

        assert im_module._wizard_launch_monitor(arguments) == 0
        run_mock.assert_called_once_with(arguments, check=False)


class TestChromiumDependencyInstall:
    def test_install_uses_the_active_interpreter(self, im_module, monkeypatch):
        run_mock = Mock(return_value=SimpleNamespace(returncode=0))
        monkeypatch.setattr(im_module.sys, "executable", "/opt/runtime/python3.13")
        monkeypatch.setattr(im_module.subprocess, "run", run_mock)
        monkeypatch.setattr(im_module, "_wizard_chromium_dependency_available", lambda: True)

        assert im_module._wizard_install_chromium_dependency("manual") is True
        run_mock.assert_called_once_with(["/opt/runtime/python3.13", "-m", "pip", "install", "pycookiecheat>=0.8"], check=False)


class TestWizardMenuSpacing:
    def test_choice_starts_on_a_new_line(self, im_module, monkeypatch, capsys):
        monkeypatch.setattr(im_module, "_wizard_input", lambda prompt: "1")
        print("Previous answer")

        assert im_module._wizard_ask_choice("Choose", [("One", "Description")]) == 0
        assert "Previous answer\n\nChoose" in capsys.readouterr().out


class TestFirstRunDecision:
    def test_saved_targets_skip_the_setup_offer(self, im_module):
        assert im_module._wizard_should_offer_first_run(["instagram_monitor.py"], ["saved.target"], False) is False

    def test_saved_web_dashboard_skips_the_setup_offer(self, im_module):
        assert im_module._wizard_should_offer_first_run(["instagram_monitor.py"], [], True) is False

    def test_empty_bare_launch_offers_setup(self, im_module):
        assert im_module._wizard_should_offer_first_run(["instagram_monitor.py"], [], False) is True


class TestWizardSecretInput:
    # Secret input uses getpass and returns the hidden value
    def test_secret_prompt_uses_getpass(self, im_module, monkeypatch):
        prompts = []
        monkeypatch.setattr(im_module.getpass, "getpass", lambda prompt: prompts.append(prompt) or "private-value")
        monkeypatch.setattr(im_module, "_wizard_input", lambda prompt: (_ for _ in ()).throw(AssertionError("visible input used")))

        assert im_module._wizard_ask_secret("Secret") == "private-value"
        assert prompts == ["Secret: "]


class TestHelpEpilog:
    def _web_dashboard_line(self, epilog):
        return next(line for line in epilog.splitlines() if line.strip().endswith("--web-dashboard"))

    def test_web_dashboard_example_drops_username_placeholder(self, im_module, monkeypatch):
        _force_env(monkeypatch, im_module, dockerenv=False, docker_env=False, compose_env=False, argv0="instagram_monitor")
        web_line = self._web_dashboard_line(im_module._build_help_epilog())
        assert "<username>" not in web_line
        assert web_line.strip() == runtime_command("instagram_monitor --web-dashboard")

    def test_compose_epilog_uses_compose_commands(self, im_module, monkeypatch):
        _force_env(monkeypatch, im_module, dockerenv=True, docker_env=False, compose_env=True, argv0="instagram_monitor.py")
        epilog = im_module._build_help_epilog()
        assert "docker compose run --rm instagram_monitor --setup" in epilog
        assert self._web_dashboard_line(epilog).strip() == "docker compose run --rm --service-ports instagram_monitor --web-dashboard"


class TestHiddenPromptPresentation:
    # Hidden prompts are colorized like the visible ones, so one question does not look different
    def test_hidden_prompts_are_colorized_like_the_visible_ones(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "COLOR_ENABLED", True)
        monkeypatch.setattr(im_module, "_COLOR_STYLES", {name: im_module._build_ansi_sequence(value) for name, value in im_module.DEFAULT_COLOR_THEME.items() if im_module._build_ansi_sequence(value)})
        prompts = []
        monkeypatch.setattr(im_module.getpass, "getpass", lambda prompt: prompts.append(prompt) or "secret")

        assert im_module._wizard_ask_secret("Instagram password") == "secret"
        assert prompts == [im_module.colorize("info", "Instagram password: ")]
        assert prompts[0].endswith(im_module.ANSI_RESET)

    # Debug output is off while a hidden value is read and restored afterwards
    def test_a_hidden_value_is_read_with_debug_output_off(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "DEBUG_MODE", True)
        seen = []
        monkeypatch.setattr(im_module.getpass, "getpass", lambda prompt: seen.append(im_module.DEBUG_MODE) or "secret")

        assert im_module._wizard_ask_secret("Instagram password") == "secret"
        assert im_module.read_secret_privately(lambda prompt: seen.append(im_module.DEBUG_MODE) or "value", "Enter it: ") == "value"
        assert seen == [False, False]
        assert im_module.DEBUG_MODE is True


# Verifies the session recovery command is pasteable as printed and reaches the files this run was given
def test_the_session_recovery_command_names_the_files_this_run_was_given(im_module, monkeypatch, tmp_path):
    config_path = tmp_path / "instagram_monitor.conf"
    env_path = tmp_path / "private.env"
    monkeypatch.setattr(im_module, "system", lambda: "Linux")
    monkeypatch.setattr(im_module.sys, "executable", "/opt/runtime/python3")
    monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py"])
    monkeypatch.setattr(im_module, "CLI_CONFIG_PATH", str(config_path))
    monkeypatch.setattr(im_module, "DOTENV_FILE", str(env_path))

    assert im_module.session_recovery_command() == runtime_command(f"python3 instagram_monitor.py --import-browser-session --browser firefox --config-file {shlex.quote(str(config_path))} --env-file {shlex.quote(str(env_path))}")


# Verifies a dotenv switched off with the none sentinel is not printed as a file path
def test_the_session_recovery_command_skips_a_dotenv_switched_off(im_module, monkeypatch):
    monkeypatch.setattr(im_module, "system", lambda: "Linux")
    monkeypatch.setattr(im_module.sys, "executable", "/opt/runtime/python3")
    monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py"])
    monkeypatch.setattr(im_module, "CLI_CONFIG_PATH", None)
    monkeypatch.setattr(im_module, "DOTENV_FILE", "none")

    assert im_module.session_recovery_command() == runtime_command("python3 instagram_monitor.py --import-browser-session --browser firefox")


# Verifies the config sentinel is carried, since the import it suggests reads the config rather than writing it
def test_the_session_recovery_command_carries_the_config_sentinel(im_module, monkeypatch):
    monkeypatch.setattr(im_module, "system", lambda: "Linux")
    monkeypatch.setattr(im_module.sys, "executable", "/opt/runtime/python3")
    monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py"])
    monkeypatch.setattr(im_module, "CLI_CONFIG_PATH", None)
    monkeypatch.setattr(im_module, "CONFIG_DISCOVERY_DISABLED", True)
    monkeypatch.setattr(im_module, "DOTENV_FILE", "")

    assert im_module.session_recovery_command() == runtime_command("python3 instagram_monitor.py --import-browser-session --browser firefox --config-file none")


class TestContainerFirefoxMounts:
    # The container globs its own ~/.mozilla/firefox/*/cookies.sqlite, so every host mount has to present the
    # profile directories themselves. Windows keeps them one level deeper, under a Profiles folder
    @pytest.mark.parametrize("host_os", sorted(("macos", "linux", "linux-snap", "linux-flatpak", "windows-powershell", "windows-cmd")))
    def test_every_host_mounts_the_profile_directories(self, im_module, host_os):
        source = im_module.CONTAINER_FIREFOX_HOSTS[host_os][1].strip('"').rsplit(":/home/instagram", 1)[0]

        if host_os.startswith("windows"):
            assert source.endswith("\\Mozilla\\Firefox\\Profiles"), "the Windows profile root holds the profiles in a Profiles folder"
        elif host_os == "macos":
            assert source.endswith("/Firefox/Profiles")
        else:
            assert source.endswith("/.mozilla/firefox")

    # Verifies the generated command carries the corrected Windows source
    @pytest.mark.parametrize("host_os,expected", [("windows-powershell", "$env:APPDATA\\Mozilla\\Firefox\\Profiles"), ("windows-cmd", "%APPDATA%\\Mozilla\\Firefox\\Profiles")])
    def test_the_windows_import_command_mounts_the_profiles_folder(self, im_module, host_os, expected):
        command = im_module._firefox_import_cmd("docker", host_os=host_os)

        assert f'-v "{expected}:/home/instagram/.mozilla/firefox:ro"' in command

    # A container handed the Windows profile root by an older command still finds the profiles one level down
    def test_a_container_accepts_the_nested_windows_layout(self, im_module, monkeypatch, real_browser_profiles, tmp_path):
        monkeypatch.setattr(im_module, "system", lambda: "Linux")
        nested = tmp_path / "firefox" / "Profiles" / "abc.default-release"
        nested.mkdir(parents=True)
        (nested / "cookies.sqlite").write_text("", encoding="utf-8")
        monkeypatch.setattr(im_module, "FIREFOX_LINUX_COOKIE", str(tmp_path / "firefox") + "/*/cookies.sqlite")
        monkeypatch.setattr(im_module, "expanduser", lambda value: value.replace("~/.mozilla/firefox", str(tmp_path / "firefox"), 1))

        assert [profile["name"] for profile in im_module.list_firefox_profiles()] == ["default-release"]

    # The nested pattern must not turn an ordinary Linux host into a duplicate listing
    def test_an_ordinary_linux_host_is_unaffected(self, im_module, monkeypatch, real_browser_profiles):
        monkeypatch.setattr(im_module, "system", lambda: "Linux")
        monkeypatch.setattr(im_module, "FIREFOX_LINUX_COOKIE", "/native/*/cookies.sqlite")
        monkeypatch.setattr(im_module, "expanduser", lambda value: value.replace("~", "/home/test", 1))
        monkeypatch.setattr(im_module, "glob", lambda pattern: ["/native/a.default-release/cookies.sqlite"] if pattern == "/native/*/cookies.sqlite" else [])

        assert [profile["path"] for profile in im_module.list_firefox_profiles()] == ["/native/a.default-release/cookies.sqlite"]


class TestRecoveryNamesEveryImportBrowser:
    # Nothing records which browser a session came from, so the Firefox command has to name the alternatives rather
    # than sending a Chrome, Brave or Chromium user to a browser they do not use
    def test_the_hint_names_every_other_supported_browser(self, im_module):
        hint = im_module.session_recovery_browser_hint()

        for browser in im_module.IMPORT_BROWSERS:
            assert (browser in hint) is (browser != "firefox")
        assert "--browser" in hint

    @pytest.mark.parametrize("error,code", [("challenge_required", "instagram.challenge"), ("session file not found", "session.missing"), ("login_required", "session.expired")])
    def test_every_session_advice_carries_the_hint(self, im_module, error, code):
        built = im_module.classify_recovery_error(error, is_logged_in=True)

        assert built.code == code
        assert im_module.session_recovery_browser_hint() in built.fix

    # The prose told every reader to log in through Firefox, whatever browser holds their session
    def test_no_session_advice_sends_the_reader_to_firefox_in_prose(self, im_module):
        source = Path(im_module.__file__).read_text(encoding="utf-8")

        assert "logging in via Firefox" not in source

    # Every message built around the import command has to name the alternatives, or the ones that do not become
    # the messages that quietly send a Chrome user to Firefox
    def test_every_use_of_the_recovery_command_names_the_alternatives(self, im_module):
        source = Path(im_module.__file__).read_text(encoding="utf-8")
        uses = [line for line in source.splitlines() if "{session_recovery_command()}" in line]

        assert len(uses) >= 7
        for line in uses:
            assert "{session_recovery_browser_hint()}" in line, line
