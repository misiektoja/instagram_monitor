"""Checks the shared secret priority through the real startup and reload paths."""

import importlib
import os
from pathlib import Path
import signal

import pytest


@pytest.fixture
# Isolates environment ownership and effective credentials between scenarios
def monitor(monkeypatch):
    module = importlib.import_module(next(Path(__file__).resolve().parents[1].glob("*_monitor.py")).stem)
    environment = dict(os.environ)
    for name, value in list(vars(module).items()):
        if name.isupper():
            monkeypatch.setattr(module, name, value.copy() if isinstance(value, (dict, list, set)) else value)
    for key in module.SECRET_KEYS:
        monkeypatch.delenv(key, raising=False)
        monkeypatch.setattr(module, key, "")
    for name, value in (("DOTENV_RELOAD_STATE", {}), ("DOTENV_BASE_VALUES", {}), ("DOTENV_MANAGED_KEYS", set()), ("EXPORTED_ENVIRONMENT_KEYS", frozenset()), ("EXPORTED_SECRET_KEYS", frozenset()), ("COMMAND_LINE_SECRET_KEYS", frozenset()), ("SECRET_SOURCES", {})):
        if hasattr(module, name):
            monkeypatch.setattr(module, name, value)
    if hasattr(module, "LOCAL_TIMEZONE"):
        monkeypatch.setattr(module, "LOCAL_TIMEZONE", "UTC")
    if hasattr(module, "TOKEN_SOURCE"):
        monkeypatch.setattr(module, "TOKEN_SOURCE", "cookie")
    yield module
    os.environ.clear()
    os.environ.update(environment)


# Loads a file through the startup loader and applies its resolved credentials
def start(monitor, path):
    if hasattr(monitor, "apply_dotenv_mapping"):
        monitor.EXPORTED_ENVIRONMENT_KEYS = frozenset(key for key in monitor.SECRET_KEYS if os.environ.get(key))
        monitor.apply_dotenv_mapping(monitor.read_dotenv_mapping(path), initialize_base=True)
    else:
        if hasattr(monitor, "EXPORTED_SECRET_KEYS"):
            monitor.EXPORTED_SECRET_KEYS = frozenset(key for key in monitor.SECRET_KEYS if os.environ.get(key))
        monitor.load_managed_dotenv(path, override=False, interpolate=False)
    for key in monitor.SECRET_KEYS:
        if key in os.environ:
            setattr(monitor, key, os.environ[key])
    monitor.DOTENV_FILE = str(path)


@pytest.mark.skipif(not hasattr(signal, "SIGHUP"), reason="SIGHUP is POSIX-only")
@pytest.mark.parametrize("exported", ["", "synthetic-export"])
# Keeps a non-empty export ahead of every valid file snapshot while treating an empty export as absent
def test_reload_preserves_startup_priority(monitor, monkeypatch, tmp_path, exported):
    path = tmp_path / "private.env"
    key = "NTFY_ACCESS_TOKEN"
    monkeypatch.setenv(key, exported)
    path.write_text(f"{key}=synthetic-first\n", encoding="utf-8")
    start(monitor, path)
    assert getattr(monitor, key) == (exported or "synthetic-first")
    for value in ("synthetic-second", ""):
        path.write_text(f'{key}="{value}"\n', encoding="utf-8")
        monitor.reload_secrets_signal_handler(signal.SIGHUP, None)
        assert getattr(monitor, key) == (exported or value)
    path.write_text("# Removed\n", encoding="utf-8")
    monitor.reload_secrets_signal_handler(signal.SIGHUP, None)
    assert getattr(monitor, key) == exported


@pytest.mark.skipif(not hasattr(signal, "SIGHUP"), reason="SIGHUP is POSIX-only")
# Preserves an explicit command-line credential through replacement and deletion of its file entry
def test_reload_preserves_command_line_value(monitor, tmp_path):
    key = {"steam_monitor": "STEAM_API_KEY", "lol_monitor": "RIOT_API_KEY", "github_monitor": "GITHUB_TOKEN", "psn_monitor": "PSN_NPSSO", "xbox_monitor": "MS_APP_CLIENT_ID", "lastfm_monitor": "LASTFM_API_KEY", "spotify_monitor": "SP_DC_COOKIE", "spotify_profile_monitor": "SP_DC_COOKIE", "instagram_monitor": "SESSION_PASSWORD"}[monitor.__name__]
    path = tmp_path / "private.env"
    path.write_text(f"{key}=synthetic-file\n", encoding="utf-8")
    start(monitor, path)
    setattr(monitor, key, "synthetic-command")
    if hasattr(monitor, "COMMAND_LINE_SECRET_KEYS"):
        monitor.COMMAND_LINE_SECRET_KEYS = frozenset({key})
    else:
        monitor.record_secret_source(key, "command line")
    for content in (f"{key}=synthetic-new\n", "# Removed\n"):
        path.write_text(content, encoding="utf-8")
        monitor.reload_secrets_signal_handler(signal.SIGHUP, None)
        assert getattr(monitor, key) == "synthetic-command"


@pytest.mark.skipif(not hasattr(signal, "SIGHUP"), reason="SIGHUP is POSIX-only")
# Leaves working credentials and ownership unchanged when the next snapshot cannot be read
def test_failed_reload_retains_snapshot(monitor, tmp_path):
    path = tmp_path / "private.env"
    path.write_text("NTFY_ACCESS_TOKEN=synthetic-working\n", encoding="utf-8")
    start(monitor, path)
    for content in (b'NTFY_ACCESS_TOKEN="unfinished\n', b"NTFY_ACCESS_TOKEN=\xff\n"):
        path.write_bytes(content)
        monitor.reload_secrets_signal_handler(signal.SIGHUP, None)
        assert monitor.NTFY_ACCESS_TOKEN == "synthetic-working"
    path.write_text("# Removed\n", encoding="utf-8")
    monitor.reload_secrets_signal_handler(signal.SIGHUP, None)
    assert monitor.NTFY_ACCESS_TOKEN == ""


# Builds each tool's real wizard state without starting network authentication
def setup_state(monitor, config, env, mode="normal"):
    import inspect
    if monitor.__name__ == "github_monitor":
        return monitor.build_wizard_state(config, env)
    baseline = {name: value for name, value in vars(monitor).items() if name.isupper()}
    available = dict(config_path=config, env_path=env, baseline_values=baseline, config_values=dict(baseline), secret_updates={}, target="test.user", targets=["test.user"], persist_target=True, persist_targets=True, auth={}, enabled_notifications=[], enabled_webhooks=[], logged_in=False, login_method="no-login", session_username="", import_browser=None, container_host=None, want_web=False, want_terminal=True, want_webhook=False, want_email=False, username="test.user")
    state_type = monitor.ScrobbleHealthSetupState if mode == "scrobble" else monitor.WizardSetupState
    arguments = {key: available[key] for key, parameter in inspect.signature(state_type).parameters.items() if parameter.default is inspect.Parameter.empty}
    return state_type(**arguments)


# Runs the real destination prompts while leaving service-specific sign-in unchanged
def move_destination(monitor, state, target, monkeypatch, mode="normal"):
    import builtins
    import inspect

    # Supplies only the path choices and declines optional notification changes
    def answer(prompt):
        if "Configuration file destination" in prompt:
            return str(state.config_path)
        if "Dotenv file destination" in prompt:
            return str(target)
        return "n"

    for name in ("_wizard_collect_auth_section", "_wizard_collect_login_section", "_wizard_collect_spotify_section", "_wizard_collect_scrobble_health_auth_section", "_wizard_confirm_target", "wizard_collect_authentication"):
        if hasattr(monitor, name):
            monkeypatch.setattr(monitor, name, lambda *args, **kwargs: None)
    monkeypatch.setattr(builtins, "input", answer)
    collector = monitor.wizard_collect_file_destinations if monitor.__name__ == "github_monitor" else monitor._wizard_collect_scrobble_health_destination_section if mode == "scrobble" else monitor._wizard_collect_destination_section
    options = {"method": "manual", "input_func": answer, "getpass_func": lambda prompt: ""}
    collector(state, **{key: value for key, value in options.items() if key in inspect.signature(collector).parameters})


# Saves through the production private-file writer without touching the original destination
def save_private(monitor, state, path):
    if monitor.__name__ == "github_monitor":
        path.write_text(monitor.render_wizard_dotenv(state), encoding="utf-8")
    elif state.secret_updates:
        monitor.update_dotenv_file(path, state.secret_updates)
    return monitor.read_private_settings(path)


@pytest.mark.parametrize("destination_value", [None, "", "synthetic-destination"])
@pytest.mark.parametrize("pending", [None, "", "synthetic-pending"])
# Keeps destination entries ahead of carried credentials and pending replacements
def test_destination_conflicts_require_new_consent(monitor, tmp_path, monkeypatch, destination_value, pending):
    old, new, config = tmp_path / "old.env", tmp_path / "new.env", tmp_path / "monitor.conf"
    key = "NTFY_ACCESS_TOKEN"
    original = f"{key}=synthetic-old\n"
    old.write_text(original, encoding="utf-8")
    if destination_value is not None:
        new.write_text(f'{key}="{destination_value}"\nUNRELATED=keep\n', encoding="utf-8")
    start(monitor, old)
    state = setup_state(monitor, config, old)
    updates = state.secrets if monitor.__name__ == "github_monitor" else state.secret_updates
    if pending is not None:
        updates[key] = pending
    move_destination(monitor, state, new, monkeypatch)
    actual = save_private(monitor, state, new)
    expected = destination_value if destination_value is not None else "synthetic-old" if pending is None else pending
    assert actual.get(key, "") == expected
    assert old.read_text(encoding="utf-8") == original
    if destination_value is not None:
        assert actual["UNRELATED"] == "keep"


# Rejects a damaged destination without changing pending credentials or selected paths
def test_destination_read_failure_keeps_answers(monitor, tmp_path, monkeypatch):
    old, new, config = tmp_path / "old.env", tmp_path / "new.env", tmp_path / "monitor.conf"
    old.write_text("NTFY_ACCESS_TOKEN=synthetic-old\n", encoding="utf-8")
    new.write_text('NTFY_ACCESS_TOKEN="unfinished\n', encoding="utf-8")
    state = setup_state(monitor, config, old)
    updates = state.secrets if monitor.__name__ == "github_monitor" else state.secret_updates
    updates["NTFY_ACCESS_TOKEN"] = "synthetic-pending"
    before = dict(updates)
    with pytest.raises(ValueError, match="syntax"):
        move_destination(monitor, state, new, monkeypatch)
    assert (state.dotenv_path if monitor.__name__ == "github_monitor" else state.env_path) == old
    assert state.config_path == config
    assert (state.secrets if monitor.__name__ == "github_monitor" else state.secret_updates) == before


# Checks carried credentials against every newly selected file during repeated review edits
def test_repeated_destination_changes_recheck_conflicts(monitor, tmp_path, monkeypatch):
    old, second, third = tmp_path / "old.env", tmp_path / "second.env", tmp_path / "third.env"
    old.write_text("NTFY_ACCESS_TOKEN=synthetic-old\n", encoding="utf-8")
    second.write_text("NTFY_ACCESS_TOKEN=synthetic-second\n", encoding="utf-8")
    third.write_text('NTFY_ACCESS_TOKEN=""\n', encoding="utf-8")
    state = setup_state(monitor, tmp_path / "monitor.conf", old)
    move_destination(monitor, state, second, monkeypatch)
    move_destination(monitor, state, third, monkeypatch)
    assert save_private(monitor, state, third)["NTFY_ACCESS_TOKEN"] == ""
    assert monitor.read_private_settings(second)["NTFY_ACCESS_TOKEN"] == "synthetic-second"


@pytest.mark.skipif(not hasattr(signal, "SIGHUP"), reason="SIGHUP is POSIX-only")
@pytest.mark.parametrize("file_present", [False, True])
# Exercises command-line priority through argument parsing, startup resolution and the real reload handler
def test_command_line_priority_from_main(monitor, tmp_path, monkeypatch, file_present):
    import sys
    key, flag = {"spotify_monitor": ("SP_DC_COOKIE", "--spotify-dc-cookie"), "spotify_profile_monitor": ("SP_DC_COOKIE", "--spotify-dc-cookie"), "instagram_monitor": ("SESSION_PASSWORD", "--session-password"), "github_monitor": ("GITHUB_TOKEN", "--github-token"), "steam_monitor": ("STEAM_API_KEY", "--steam-api-key"), "psn_monitor": ("PSN_NPSSO", "--npsso-key"), "xbox_monitor": ("MS_APP_CLIENT_ID", "--ms-app-client-id"), "lastfm_monitor": ("LASTFM_API_KEY", "--lastfm-api-key"), "lol_monitor": ("RIOT_API_KEY", "--riot-api-key")}[monitor.__name__]
    config, path = tmp_path / "monitor.conf", tmp_path / "private.env"
    config.write_text(f'{key}="synthetic-config"\nCLEAR_SCREEN=False\n', encoding="utf-8")
    if file_present:
        path.write_text(f"{key}=synthetic-file\n", encoding="utf-8")
    monkeypatch.setenv(key, "synthetic-export")
    observed = []

    # Checks credentials at Doctor's entry without making network requests
    def doctor(*args, **kwargs):
        observed.append(getattr(monitor, key))
        path.write_text(f"{key}=synthetic-rotated\n", encoding="utf-8")
        monitor.reload_secrets_signal_handler(signal.SIGHUP, None)
        observed.append(getattr(monitor, key))
        return 0

    monkeypatch.setattr(monitor, "run_doctor", doctor)
    monkeypatch.setattr(sys, "argv", [monitor.__file__, "--doctor", "--config-file", str(config), "--env-file", str(path), flag, "synthetic-command"])
    with pytest.raises(SystemExit) as stopped:
        monitor.main()
    assert stopped.value.code == 0
    assert observed == ["synthetic-command", "synthetic-command"]


@pytest.mark.parametrize("replace", [False, True])
# Checks the selected destination's password and requires fresh consent before replacing it
def test_destination_email_review_uses_selected_password(monitor, tmp_path, monkeypatch, replace):
    import builtins
    import inspect
    from io import StringIO
    from types import SimpleNamespace

    old, new, config = tmp_path / "old.env", tmp_path / "new.env", tmp_path / "monitor.conf"
    old.write_text("SMTP_PASSWORD=synthetic-old\n", encoding="utf-8")
    new.write_text("SMTP_PASSWORD=synthetic-destination\n", encoding="utf-8")
    start(monitor, old)
    state = setup_state(monitor, config, old)
    updates = state.secrets if monitor.__name__ == "github_monitor" else state.secret_updates
    updates["SMTP_PASSWORD"] = "synthetic-previous-choice"
    output = StringIO()
    observed, replacements, answered = [], [], []
    cursor = 0

    # Answers the real prompts by label while keeping all entered credentials synthetic
    def answer(prompt=""):
        nonlocal cursor
        shown = prompt or output.getvalue()[cursor:]
        cursor = len(output.getvalue())
        answered.append(shown)
        assert len(answered) < 45, answered
        if "Configuration file destination" in shown:
            return str(config)
        if "Dotenv file destination" in shown:
            return str(new)
        if "already contains SMTP_PASSWORD" in shown:
            replacements.append(shown)
            return "y" if replace else "n"
        if "Configure email notifications" in shown:
            return "y"
        if "SMTP host" in shown:
            return "smtp.example.com"
        if "SMTP username" in shown:
            return "test.user"
        if "Sender email" in shown or "Receiver email" in shown:
            return "test@example.com"
        if "webhook" in shown.lower():
            return "n"
        return ""

    for name in ("_wizard_collect_auth_section", "_wizard_collect_login_section", "_wizard_collect_spotify_section", "_wizard_confirm_target", "wizard_collect_authentication"):
        if hasattr(monitor, name):
            monkeypatch.setattr(monitor, name, lambda *args, **kwargs: None)
    monkeypatch.setattr(builtins, "input", answer)
    monkeypatch.setattr(monitor.getpass, "getpass", lambda prompt: "synthetic-new")

    # Observes the password delivered to the sign-in boundary without contacting a mail server
    def accepted(values, password, **kwargs):
        observed.append(password)
        return True

    # Observes GitHub's resolved password at the same mail-server boundary
    def connect(*args, **kwargs):
        observed.append(monitor.SMTP_PASSWORD)
        return SimpleNamespace(quit=lambda: None)

    if monitor.__name__ == "github_monitor":
        monkeypatch.setattr(monitor, "smtp_connect_and_login", connect)
        collector = monitor.wizard_collect_file_destinations
    else:
        monkeypatch.setattr(monitor, "_wizard_smtp_sign_in_accepted", accepted)
        collector = monitor._wizard_collect_destination_section
    options = {"method": "manual", "input_func": answer, "getpass_func": lambda prompt: "synthetic-new", "stream": output}
    collector(state, **{key: value for key, value in options.items() if key in inspect.signature(collector).parameters})
    expected = "synthetic-new" if replace else "synthetic-destination"
    assert observed == [expected]
    assert len(replacements) == 1
    assert save_private(monitor, state, new)["SMTP_PASSWORD"] == expected
    assert monitor.read_private_settings(old)["SMTP_PASSWORD"] == "synthetic-old"


@pytest.mark.skipif(not hasattr(signal, "SIGHUP"), reason="SIGHUP is POSIX-only")
# Reports a restored configuration fallback as configuration rather than as an exported credential
def test_removed_secret_reports_its_fallback_source(monitor, tmp_path):
    path = tmp_path / "private.env"
    monitor.NTFY_ACCESS_TOKEN = "synthetic-config"
    path.write_text("NTFY_ACCESS_TOKEN=synthetic-file\n", encoding="utf-8")
    start(monitor, path)
    path.write_text("# Removed\n", encoding="utf-8")
    monitor.reload_secrets_signal_handler(signal.SIGHUP, None)
    assert monitor.NTFY_ACCESS_TOKEN == "synthetic-config"
    sources = monitor.secret_source_labels(path) if monitor.__name__ in ("steam_monitor", "lol_monitor") else monitor.SECRET_SOURCES
    assert "NTFY_ACCESS_TOKEN" not in monitor._wizard_exported_secrets()
    assert sources["NTFY_ACCESS_TOKEN"].startswith("config")


@pytest.mark.skipif(not hasattr(signal, "SIGHUP"), reason="SIGHUP is POSIX-only")
# Resolves each new snapshot without reusing an alias left in the process by an earlier file
def test_repeated_reload_uses_current_interpolation_alias(monitor, monkeypatch, tmp_path):
    if monitor.__name__ in ("spotify_monitor", "instagram_monitor", "lastfm_monitor"):
        pytest.skip("This monitor keeps dotenv values literal")
    monkeypatch.delenv("MONITOR_TEST_ALIAS", raising=False)
    path = tmp_path / "private.env"
    path.write_text('MONITOR_TEST_ALIAS=first\nNTFY_ACCESS_TOKEN=${MONITOR_TEST_ALIAS}\n', encoding="utf-8")
    monitor.load_managed_dotenv(path, override=False)
    monitor.DOTENV_FILE = str(path)
    assert os.environ["NTFY_ACCESS_TOKEN"] == "first"
    for value in ("second", "third"):
        path.write_text(f'MONITOR_TEST_ALIAS={value}\nNTFY_ACCESS_TOKEN=${{MONITOR_TEST_ALIAS}}\n', encoding="utf-8")
        monitor.reload_secrets_signal_handler(signal.SIGHUP, None)
        assert monitor.NTFY_ACCESS_TOKEN == value
    path.write_text('NTFY_ACCESS_TOKEN=${MONITOR_TEST_ALIAS}\n', encoding="utf-8")
    monitor.reload_secrets_signal_handler(signal.SIGHUP, None)
    assert monitor.NTFY_ACCESS_TOKEN == ""


# Keeps carried credentials when a later review disables their notification channel
def test_destination_credentials_survive_later_section_review(monitor, monkeypatch, tmp_path):
    import inspect
    import io
    old, new = tmp_path / "old.env", tmp_path / "new.env"
    old.write_text("NTFY_ACCESS_TOKEN=synthetic-kept\n", encoding="utf-8")
    state = setup_state(monitor, tmp_path / "monitor.conf", old)
    move_destination(monitor, state, new, monkeypatch)
    if monitor.__name__ == "github_monitor":
        monitor.wizard_collect_webhook(state, input_func=lambda prompt: "n", stream=io.StringIO())
    else:
        collector = monitor._wizard_collect_webhook_section
        options = {"input_func": lambda prompt: "n"}
        collector(state, **{key: value for key, value in options.items() if key in inspect.signature(collector).parameters})
        monkeypatch.setattr(monitor, "_wizard_print_setup_summary", lambda *args, **kwargs: None)
        monkeypatch.setattr(monitor, "_wizard_ask_choice", lambda *args, **kwargs: 0)
        review_options = {"method": "manual", "input_func": lambda prompt: ""}
        assert monitor._wizard_review_setup(state, **{key: value for key, value in review_options.items() if key in inspect.signature(monitor._wizard_review_setup).parameters})
    assert save_private(monitor, state, new)["NTFY_ACCESS_TOKEN"] == "synthetic-kept"
