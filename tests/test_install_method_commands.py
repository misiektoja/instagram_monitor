"""Tests for install-method detection and the command examples it drives."""

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


class TestCmdPrefix:
    def test_manual_matches_active_python_name(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "system", lambda: "Linux")
        monkeypatch.setattr(im_module.sys, "executable", "/opt/runtime/python3.13")
        assert im_module._wizard_cmd_prefix("manual") == "python3.13 instagram_monitor.py"

    def test_pip(self, im_module):
        assert im_module._wizard_cmd_prefix("pip") == "instagram_monitor"

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
        assert im_module._firefox_import_cmd("pip") == "instagram_monitor --import-browser-session --browser firefox"

    @pytest.mark.parametrize("host_os,source", [("macos", '"${HOME}/Library/Application Support/Firefox/Profiles:/home/instagram/.mozilla/firefox:ro"'), ("linux", '"$HOME/.mozilla/firefox:/home/instagram/.mozilla/firefox:ro"'), ("linux-snap", '"$HOME/snap/firefox/common/.mozilla/firefox:/home/instagram/.mozilla/firefox:ro"'), ("linux-flatpak", '"$HOME/.var/app/org.mozilla.firefox/.mozilla/firefox:/home/instagram/.mozilla/firefox:ro"')])
    def test_container_commands_mount_selected_host_profile(self, im_module, host_os, source):
        docker = im_module._firefox_import_cmd("docker", host_os=host_os)
        compose = im_module._firefox_import_cmd("compose", host_os=host_os)
        assert f"-v {source} misiektoja/instagram-monitor" in docker
        assert ('--user "$(id -u):$(id -g)"' in docker) is host_os.startswith("linux")
        assert docker.endswith("--import-browser-session --browser firefox")
        assert compose == f"docker compose run --rm -v {source} instagram_monitor --import-browser-session --browser firefox"

    def test_setup_import_command_carries_config_and_targets(self, im_module, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        command = im_module._firefox_import_cmd("docker", tmp_path / ".env", host_os="macos", config_path=tmp_path / "instagram_monitor.conf", targets=["target.user"])
        assert "--import-browser-session --browser firefox target.user" in command
        assert "--config-file /data/instagram_monitor.conf --env-file /data/.env" in command


class TestFirefoxProfileDiscovery:
    # Verifies native, Snap and Flatpak Firefox profiles are discovered without duplicate cookie paths
    def test_linux_discovers_package_variants(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "system", lambda: "Linux")
        monkeypatch.setattr(im_module, "FIREFOX_LINUX_COOKIE", "/native/*/cookies.sqlite")
        matches = {"/native/*/cookies.sqlite": ["/native/a.default-release/cookies.sqlite"], "/home/test/snap/firefox/common/.mozilla/firefox/*/cookies.sqlite": ["/snap/b.default/cookies.sqlite"], "/home/test/.var/app/org.mozilla.firefox/.mozilla/firefox/*/cookies.sqlite": ["/flatpak/c.work/cookies.sqlite", "/native/a.default-release/cookies.sqlite"]}
        monkeypatch.setattr(im_module, "expanduser", lambda value: value.replace("~", "/home/test", 1))
        monkeypatch.setattr(im_module, "glob", lambda pattern: matches.get(pattern, []))
        profiles = im_module.list_firefox_profiles()
        assert [profile["path"] for profile in profiles] == ["/native/a.default-release/cookies.sqlite", "/snap/b.default/cookies.sqlite", "/flatpak/c.work/cookies.sqlite"]
        assert [profile["name"] for profile in profiles] == ["default-release", "default", "work"]

    # Verifies non-Linux platforms keep using only their configured Firefox pattern
    def test_non_linux_uses_only_configured_pattern(self, im_module, monkeypatch):
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

        assert command.startswith("'/opt/Python Runtime/python3'")
        assert f"--config-file '{config_path.resolve()}'" in command
        assert f"--env-file '{env_path.resolve()}'" in command
        assert "target.user" in command

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
        assert web_line.strip() == "instagram_monitor --web-dashboard"

    def test_compose_epilog_uses_compose_commands(self, im_module, monkeypatch):
        _force_env(monkeypatch, im_module, dockerenv=True, docker_env=False, compose_env=True, argv0="instagram_monitor.py")
        epilog = im_module._build_help_epilog()
        assert "docker compose run --rm instagram_monitor --setup" in epilog
        assert self._web_dashboard_line(epilog).strip() == "docker compose run --rm --service-ports instagram_monitor --web-dashboard"
