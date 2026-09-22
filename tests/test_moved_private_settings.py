"""Checks retained file credentials after editing a setup destination, and unreadable dotenv reporting."""

import os
import builtins
import re
import socket
import sys

import pytest

from dotenv import dotenv_values

import instagram_monitor as monitor


# Restores startup-mutated settings and mutable bookkeeping after each independent scenario
@pytest.fixture(autouse=True)
def restore_settings(monkeypatch):
    for key in monitor.SECRET_KEYS:
        monkeypatch.setenv(key, os.environ.get(key, ""))
        monkeypatch.delenv(key, raising=False)
    for name, value in list(vars(monitor).items()):
        if name.isupper():
            monkeypatch.setattr(monitor, name, value.copy() if isinstance(value, (dict, list, set)) else value)


# Drives the real setup menus while retaining the previously loaded credential
def test_kept_file_credential_moves_with_setup(tmp_path, monkeypatch, capsys):
    config, old, new = tmp_path / "monitor.conf", tmp_path / "old.env", tmp_path / "new.env"
    key = "SESSION_PASSWORD"
    old.write_text(f'{key}="retained-private-value"\n', encoding="utf-8")
    for name in monitor.SECRET_KEYS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(monitor, "COLORED_OUTPUT", False)
    monitor.load_managed_dotenv(old, override=False, interpolate=False)
    baseline = dict(vars(monitor))
    state = monitor.WizardSetupState(config, old, baseline, dict(baseline), {}, ["target.user"], True, True, "password", "review.test", None, None, False, False, False, False)
    transcript = []

    # Selects public menu choices from the labels the user actually sees
    def answer(prompt=""):
        output = capsys.readouterr().out
        transcript.append(output + prompt)
        if "Configuration file destination" in prompt:
            return str(config)
        if "Dotenv file destination" in prompt:
            return str(new)
        if "Choose [" in prompt:
            if "Choose an authentication mode" in output:
                return "1"
            label = "Username and password" if key == "SESSION_PASSWORD" else "Use an existing SP_DC_COOKIE"
            match = re.search(r"(\d+)\. " + re.escape(label), output)
            assert match, output
            return match.group(1)
        if "Your Instagram username" in prompt:
            return "review.test"
        if "Retain the existing SP_DC_COOKIE" in prompt:
            return "y"
        if "[y/N]" in prompt or "[Y/n]" in prompt:
            return "n"
        raise AssertionError(prompt)

    monkeypatch.setattr(builtins, "input", answer)
    monitor._wizard_collect_destination_section(state, "manual")
    monitor.update_dotenv_file(new, state.secret_updates)
    assert dotenv_values(new, interpolate=False)[key] == "retained-private-value"
    assert dotenv_values(old, interpolate=False)[key] == "retained-private-value"
    assert "retained-private-value" not in "".join(transcript)


# Refuses DNS at the network boundary so Doctor runs offline without replacing its implementation
@pytest.fixture
def offline(monkeypatch):
    def refuse(*_args, **_kwargs):
        raise socket.gaierror("offline")
    monkeypatch.setattr(socket, "getaddrinfo", refuse)


# Writes a dotenv file whose bytes are not valid UTF-8
def unreadable_dotenv(tmp_path):
    env = tmp_path / "broken.env"
    env.write_bytes(b'UNRELATED_SETTING="bad-encoding-\xff"\n')
    return env


# Proves Doctor reports the failed load as a row instead of stopping on the file it exists to describe
def test_doctor_reports_unreadable_dotenv(tmp_path, monkeypatch, capsys, offline):
    config = tmp_path / "monitor.conf"
    config.write_text("CLEAR_SCREEN=False\n", encoding="utf-8")
    env = unreadable_dotenv(tmp_path)
    monkeypatch.setattr(monitor, "COLORED_OUTPUT", False)
    monkeypatch.setattr(sys, "argv", [monitor.__file__, "--doctor", "--config-file", str(config), "--env-file", str(env)])

    with pytest.raises(SystemExit):
        monitor.run_main()

    output = capsys.readouterr().out
    assert "Dotenv file could not be loaded" in output
    assert "is not valid UTF-8 text" in output
    assert "Dotenv file loaded" not in output


# Proves an ordinary run names the file and stops instead of raising out of the dotenv load
def test_startup_reports_unreadable_dotenv(tmp_path, monkeypatch, capsys, offline):
    config = tmp_path / "monitor.conf"
    config.write_text("CLEAR_SCREEN=False\n", encoding="utf-8")
    env = unreadable_dotenv(tmp_path)
    monkeypatch.setattr(monitor, "COLORED_OUTPUT", False)
    monkeypatch.setattr(sys, "argv", [monitor.__file__, "review.test", "--config-file", str(config), "--env-file", str(env)])

    with pytest.raises(SystemExit) as stopped:
        monitor.run_main()

    assert stopped.value.code == 1
    output = capsys.readouterr().out
    assert str(env) in output
    assert "Save the dotenv file as UTF-8" in output


# Proves each cause names itself, so a readable file with bad bytes and an unopenable one do not share one message
@pytest.mark.parametrize("error,expected_detail,expected_fix", [
    (UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"), "is not valid UTF-8 text", "Save the dotenv file as UTF-8"),
    (PermissionError(13, "Permission denied"), "could not be opened", "Check the dotenv file path and its read permissions"),
    (ValueError("unexpected"), "could not be read", "Check that the dotenv file is readable UTF-8 text"),
])
def test_dotenv_load_problem_names_its_cause(error, expected_detail, expected_fix):
    detail, fix = monitor.dotenv_load_problem("/tmp/private.env", error)

    assert detail == f"Dotenv file '/tmp/private.env' {expected_detail}"
    assert fix == expected_fix
