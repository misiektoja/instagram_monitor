"""Tests for install-method detection and the command examples it drives (--help epilog, wizard prefixes)."""


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
    def test_manual(self, im_module):
        assert im_module._wizard_cmd_prefix("manual") == "python3 instagram_monitor.py"

    def test_pip(self, im_module):
        assert im_module._wizard_cmd_prefix("pip") == "instagram_monitor"

    def test_docker_only_web_adds_port_publish(self, im_module):
        assert "-p 8000:8000" not in im_module._wizard_cmd_prefix("docker")
        assert "-p 8000:8000" in im_module._wizard_cmd_prefix("docker", web_dashboard=True)

    def test_compose_only_web_adds_service_ports(self, im_module):
        assert im_module._wizard_cmd_prefix("compose") == "docker compose run --rm instagram_monitor"
        assert im_module._wizard_cmd_prefix("compose", web_dashboard=True) == "docker compose run --rm --service-ports instagram_monitor"


class TestFirefoxImportCmd:
    def test_non_container_has_no_mount(self, im_module):
        assert im_module._firefox_import_cmd("pip") == "instagram_monitor --import-browser-session --browser firefox"

    def test_docker_mounts_profile_before_image(self, im_module):
        cmd = im_module._firefox_import_cmd("docker")
        assert '-v "$HOME/.mozilla/firefox:/home/instagram/.mozilla/firefox:ro" misiektoja/instagram-monitor' in cmd
        assert cmd.endswith("--import-browser-session --browser firefox")

    def test_compose_mounts_profile_before_service(self, im_module):
        assert im_module._firefox_import_cmd("compose") == 'docker compose run --rm -v "$HOME/.mozilla/firefox:/home/instagram/.mozilla/firefox:ro" instagram_monitor --import-browser-session --browser firefox'


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


class TestWizardBrowserDesc:
    def test_firefox_mentions_no_extra_packages(self, im_module):
        assert "no extra packages" in im_module._wizard_browser_desc("firefox")

    def test_chromium_family_mentions_pycookiecheat(self, im_module):
        for browser in im_module.CHROMIUM_IMPORT_BROWSERS:
            desc = im_module._wizard_browser_desc(browser)
            assert "pycookiecheat" in desc
            assert im_module.browser_label(browser) in desc


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
