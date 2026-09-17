"""Checks retained file credentials after editing a setup destination."""

import os
import builtins
import re

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
