import copy
import json
import socket
import sys

import pytest
from dotenv import dotenv_values

import instagram_monitor as monitor


@pytest.fixture(autouse=True)
# Restores effective configuration after each isolated startup case
def isolated_configuration(monkeypatch, tmp_path):
    for name, value in list(vars(monitor).items()):
        if name.isupper():
            monkeypatch.setattr(monitor, name, copy.copy(value) if isinstance(value, (dict, list, set)) else value)
    for key in monitor.SECRET_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)


@pytest.mark.parametrize("debug", [False, True])
@pytest.mark.parametrize("source", ['SMTP_PASSWORD: "synthetic-private-credential" =\n', 'SMTP_PASSWORD = (\n    "synthetic-private-credential" unexpected\n)\n'])
# Malformed source may contain credentials that never reached effective configuration
def test_syntax_error_omits_unloaded_credentials(monkeypatch, tmp_path, capsys, debug, source):
    monkeypatch.setattr(monitor, "DEBUG_MODE", debug)
    config = tmp_path / "broken.conf"
    config.write_text(source, encoding="utf-8")
    assert not monitor.load_config_file(config, namespace={})
    output = capsys.readouterr().out
    assert "synthetic-private-credential" not in output
    assert "broken.conf" in output
    assert "Source:" not in output


@pytest.mark.parametrize("existing", [None, "", "synthetic-existing"])
# Inline credentials survive replacement without overriding an explicit dotenv value
def test_preserve_inline_credentials(tmp_path, existing):
    config = tmp_path / "settings.conf"
    original = 'SMTP_PASSWORD = "synthetic-inline"\n'
    config.write_text(original, encoding="utf-8")
    env = tmp_path / "private.env"
    if existing is not None:
        env.write_text("SMTP_PASSWORD=" + json.dumps(existing) + "\nKEEP=unchanged\n", encoding="utf-8")
    monitor.preserve_inline_config_secrets(config, env)
    saved = dotenv_values(env, interpolate=False)
    assert saved["SMTP_PASSWORD"] == ("synthetic-inline" if existing is None else existing)
    assert config.read_text(encoding="utf-8") == original
    if existing is not None:
        assert saved["KEEP"] == "unchanged"
    else:
        assert env.stat().st_mode & 0o077 == 0


# A failed private write cannot destroy the original inline credential
def test_preservation_failure_leaves_original_config(tmp_path):
    config = tmp_path / "settings.conf"
    original = 'SMTP_PASSWORD = "synthetic-inline"\n'
    config.write_text(original, encoding="utf-8")
    directory = tmp_path / "not-a-file"
    directory.mkdir()
    with pytest.raises((OSError, ValueError)):
        monitor.preserve_inline_config_secrets(config, directory)
    assert config.read_text(encoding="utf-8") == original


@pytest.mark.parametrize("value", [float("inf"), float("nan"), -1, True, "30", 10 ** 400])
# Effective runtime validation rejects unusable timing values without conversion errors
def test_invalid_runtime_timing(monkeypatch, value):
    setting = "SPOTIFY_CHECK_INTERVAL" if hasattr(monitor, "runtime_numeric_errors") else "CHECK_INTERNET_TIMEOUT"
    monkeypatch.setattr(monitor, setting, value)
    validate = getattr(monitor, "runtime_numeric_errors", None) or monitor.runtime_configuration_errors
    assert any(setting in error for error in validate())


# Normal startup must report invalid timing before attempting a connection
def test_normal_startup_validates_before_network(monkeypatch, tmp_path, capsys):
    config = tmp_path / "settings.conf"
    setting = "SPOTIFY_CHECK_INTERVAL" if hasattr(monitor, "runtime_numeric_errors") else "CHECK_INTERNET_TIMEOUT"
    config.write_text(setting + " = 1e309\n", encoding="utf-8")
    calls = []

    # Records attempts at the actual socket boundary without replacing a provider client
    def offline(sock, address):
        calls.append(address)
        raise OSError("Network is unreachable")
    monkeypatch.setattr(socket.socket, "connect", offline)
    monkeypatch.setattr(sys, "argv", [monitor.__file__, "--config-file", str(config), "--env-file", "none", "--send-test-email"])
    with pytest.raises(SystemExit) as stopped:
        monitor.main()
    assert stopped.value.code == 1
    assert not calls
    output = capsys.readouterr()
    assert setting in output.out + output.err


@pytest.mark.parametrize("record", [{}, [], [1], [-1, []], ["2", []], [2, {}], [1, [None]]])
# Invalid collection state cannot become a replacement comparison baseline
def test_invalid_collection(tmp_path, record):
    path = tmp_path / "collection.json"
    original = json.dumps(record)
    path.write_text(original, encoding="utf-8")
    with pytest.raises(ValueError):
        monitor.read_follow_record(path)
    assert path.read_text(encoding="utf-8") == original


# A reported total can exceed a partial saved list and extra metadata is retained
def test_partial_collection_with_extra_metadata(tmp_path):
    path = tmp_path / "collection.json"
    record = [10, ["someone"], {"note": "kept by the operator"}]
    path.write_text(json.dumps(record), encoding="utf-8")
    assert monitor.read_follow_record(path) == record


# A missing target is a local input error even when the machine is offline
def test_missing_target_precedes_connectivity(monkeypatch, capsys):
    calls = []

    def offline(sock, address):
        calls.append(address)
        raise OSError("Network is unreachable")
    monkeypatch.setattr(socket.socket, "connect", offline)
    monkeypatch.setattr(sys, "argv", [monitor.__file__, "--config-file", "none", "--env-file", "none", "--no-color"])
    with pytest.raises(SystemExit) as stopped:
        monitor.main()
    assert stopped.value.code == 1
    assert not calls
    assert "At least one TARGET_USERNAME argument is required" in capsys.readouterr().out
