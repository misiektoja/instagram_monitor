"""Regression coverage for readable command displays and exact process arguments."""

import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

monitor = importlib.import_module("instagram_monitor")


# Display prefixes do not inherit private interpreter or installation paths
@pytest.mark.parametrize("host, executable", [("Linux", "python3"), ("Darwin", "python3"), ("Windows", "python")])
@pytest.mark.parametrize("method", ["manual", "pip"])
def test_display_prefix_is_short(monkeypatch, host, executable, method):
    monkeypatch.setattr(sys, "executable", "/private/long/environment/bin/python3")
    monkeypatch.setattr(sys, "argv", ["/private/long/tools/instagram_monitor.py" if method == "manual" else "/private/long/bin/instagram_monitor"])
    monkeypatch.setattr(monitor, "__file__", "/private/long/tools/instagram_monitor.py")
    monkeypatch.setattr("platform.system", lambda: host)
    if hasattr(monitor, "system"):
        monkeypatch.setattr(monitor, "system", lambda: host)
    if hasattr(monitor, "INSTALL_METHOD_ENV_VAR"):
        monkeypatch.setenv(monitor.INSTALL_METHOD_ENV_VAR, method)
    if hasattr(monitor, "render_command"):
        actual = monitor.render_command(["--setup"], include_paths=False)
    else:
        actual = monitor._wizard_cmd_prefix(method) + " --setup"
    expected = executable + " instagram_monitor.py --setup" if method == "manual" else "instagram_monitor --setup"
    assert actual == expected
    assert "/private/long/" not in actual


# Real help output keeps every generated example free of runtime installation paths
def test_help_does_not_display_runtime_paths():
    assert monitor.__file__ is not None
    source = Path(monitor.__file__).resolve()
    environment = dict(os.environ, NO_COLOR="1")
    if hasattr(monitor, "INSTALL_METHOD_ENV_VAR"):
        environment.pop(monitor.INSTALL_METHOD_ENV_VAR, None)
    result = subprocess.run([sys.executable, str(source), "--help"], capture_output=True, text=True, env=environment, timeout=30)
    assert result.returncode == 0
    assert str(source) not in result.stdout
    assert sys.executable not in result.stdout
    assert "instagram_monitor.py --setup" in result.stdout


# Dependency recovery hints remain short when the active environment has a long path
def test_dependency_hint_does_not_display_runtime_paths(monkeypatch):
    monkeypatch.setattr(sys, "executable", "/private/long/environment/bin/python3")
    if hasattr(monitor, "pip_install_command"):
        command = monitor.pip_install_command("example-package")
    elif hasattr(monitor, "install_dependency_command"):
        command = monitor.install_dependency_command("example-package")
    elif hasattr(monitor, "notification_images_install_command"):
        command = monitor.notification_images_install_command("pip")
    elif hasattr(monitor, "ntfy_images_install_command"):
        command = monitor.ntfy_images_install_command()
    else:
        command = monitor.missing_dependency_advice("example-package", "Feature is unavailable").fix
    assert "/private/long/" not in command
    assert "install" in command
