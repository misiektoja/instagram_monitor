"""Regression checks for secret reloads and external output."""
import importlib
import os
from pathlib import Path
import signal

import pytest


@pytest.fixture
# Isolates the real monitor's secret resolution state
def monitor(monkeypatch):
    source = next(Path(__file__).resolve().parents[1].glob("*_monitor.py"))
    module = importlib.import_module(source.stem)
    environment = dict(os.environ)
    original = {key: value for key, value in vars(module).items() if key.isupper()}
    for key in getattr(module, "SECRET_KEYS", ("NTFY_ACCESS_TOKEN",)):
        monkeypatch.delenv(key, raising=False)
    for name, value in (("NTFY_ACCESS_TOKEN", ""), ("LOCAL_TIMEZONE", "UTC"), ("DEBUG_MODE", False), ("DOTENV_RELOAD_STATE", {}), ("DOTENV_BASE_VALUES", {}), ("DOTENV_MANAGED_KEYS", set()), ("EXPORTED_ENVIRONMENT_KEYS", set()), ("EXPORTED_SECRET_KEYS", frozenset()), ("SECRET_SOURCES", {})):
        monkeypatch.setattr(module, name, value, raising=False)
    yield module
    os.environ.clear()
    os.environ.update(environment)
    for key, value in original.items():
        setattr(module, key, value)


# Applies the production startup loader or the released python-dotenv startup behavior
def load_file(module, path):
    if hasattr(module, "load_startup_secrets"):
        module.load_startup_secrets(str(path))
    elif hasattr(module, "load_managed_dotenv"):
        module.load_managed_dotenv(path, override=False, interpolate=False)
    elif hasattr(module, "apply_dotenv_mapping"):
        module.apply_dotenv_mapping(module.read_dotenv_mapping(path), initialize_base=True)
    else:
        from dotenv import load_dotenv
        load_dotenv(path, override=False, interpolate=False)
    module.NTFY_ACCESS_TOKEN = os.environ.get("NTFY_ACCESS_TOKEN", module.NTFY_ACCESS_TOKEN)


@pytest.mark.skipif(not hasattr(signal, "SIGHUP"), reason="SIGHUP is POSIX-only")
@pytest.mark.parametrize("fallback", ["", "synthetic-config-fallback"])
# Restores the non-file value when a previously loaded assignment disappears
def test_deleted_file_secret_is_reconciled(monitor, monkeypatch, tmp_path, fallback):
    path = tmp_path / "private.env"
    path.write_text("NTFY_ACCESS_TOKEN=synthetic-file-token\n", encoding="utf-8")
    monkeypatch.setattr(monitor, "DOTENV_FILE", str(path))
    monkeypatch.setattr(monitor, "NTFY_ACCESS_TOKEN", fallback)
    load_file(monitor, path)
    assert monitor.NTFY_ACCESS_TOKEN == "synthetic-file-token"
    path.write_text("# Deliberately cleared while retaining unrelated content\nUNRELATED=keep\n", encoding="utf-8")
    monitor.reload_secrets_signal_handler(signal.SIGHUP, None)
    assert monitor.NTFY_ACCESS_TOKEN == fallback
    assert os.environ.get("NTFY_ACCESS_TOKEN", "") == fallback


@pytest.mark.skipif(not hasattr(signal, "SIGHUP"), reason="SIGHUP is POSIX-only")
# Preserves startup exports across both reload directions
def test_exported_secret_reload_precedence(monitor, monkeypatch, tmp_path):
    path = tmp_path / "private.env"
    path.write_text("NTFY_ACCESS_TOKEN=synthetic-file-token\n", encoding="utf-8")
    monkeypatch.setattr(monitor, "DOTENV_FILE", str(path))
    monkeypatch.setenv("NTFY_ACCESS_TOKEN", "synthetic-export-token")
    monkeypatch.setattr(monitor, "EXPORTED_ENVIRONMENT_KEYS", {"NTFY_ACCESS_TOKEN"}, raising=False)
    monkeypatch.setattr(monitor, "EXPORTED_SECRET_KEYS", frozenset({"NTFY_ACCESS_TOKEN"}), raising=False)
    load_file(monitor, path)
    assert monitor.NTFY_ACCESS_TOKEN == "synthetic-export-token"
    monitor.reload_secrets_signal_handler(signal.SIGHUP, None)
    expected = "synthetic-export-token"
    assert monitor.NTFY_ACCESS_TOKEN == expected
    path.write_text("# Removed\n", encoding="utf-8")
    monitor.reload_secrets_signal_handler(signal.SIGHUP, None)
    assert monitor.NTFY_ACCESS_TOKEN == "synthetic-export-token"


@pytest.mark.skipif(not hasattr(signal, "SIGHUP"), reason="SIGHUP is POSIX-only")
@pytest.mark.parametrize("content", [b'NTFY_ACCESS_TOKEN="unterminated\n', b"NTFY_ACCESS_TOKEN=\xff\n"])
# Keeps the last usable credentials when a file has invalid syntax or encoding
def test_failed_reload_preserves_credentials(monitor, monkeypatch, tmp_path, content):
    path = tmp_path / "private.env"
    path.write_text("NTFY_ACCESS_TOKEN=synthetic-file-token\n", encoding="utf-8")
    monkeypatch.setattr(monitor, "DOTENV_FILE", str(path))
    load_file(monitor, path)
    path.write_bytes(content)
    monitor.reload_secrets_signal_handler(signal.SIGHUP, None)
    assert monitor.NTFY_ACCESS_TOKEN == "synthetic-file-token"
    assert os.environ["NTFY_ACCESS_TOKEN"] == "synthetic-file-token"


# Keeps provider text printable when a count exceeds the interpreter's integer-conversion limit
def test_large_external_count_is_printable(monitor, monkeypatch):
    if not hasattr(monitor, "_colorize_line"):
        pytest.skip("The released version has no color renderer")
    monkeypatch.setattr(monitor, "COLORED_OUTPUT", True)
    text = "from " + "9" * 5000 + " to 1\n"
    assert "9" * 5000 in monitor._colorize_line(text)


# Reports an unusable SMTP port instead of raising a conversion exception
def test_invalid_smtp_port_is_reported(monitor, monkeypatch):
    if not hasattr(monitor, "email_settings_problem"):
        pytest.skip("This monitor uses a separate SMTP validator")
    monkeypatch.setattr(monitor, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(monitor, "SMTP_PORT", None)
    assert monitor.email_settings_problem() is not None


# Keeps ordinary configuration recoverable without copying replaced inline credentials during setup
def test_setup_backup_excludes_inline_secret(monitor, tmp_path):
    import inspect
    if not hasattr(monitor, "create_timestamped_backup"):
        pytest.skip("The released version has no setup backup helper")
    path = tmp_path / "settings.conf"
    original = '# Retain this comment\nSMTP_PASSWORD = """synthetic-older-password\nsecond line"""\nUNRELATED = ["keep", 3]\n'
    path.write_text(original, encoding="utf-8")
    options = {"redact_secrets": True} if "redact_secrets" in inspect.signature(monitor.create_timestamped_backup).parameters else {}
    backup = monitor.create_timestamped_backup(path, **options)
    saved = Path(backup).read_text(encoding="utf-8")
    assert "synthetic-older-password" not in saved
    assert "second line" not in saved
    assert 'UNRELATED = ["keep", 3]' in saved
    assert "# Retain this comment" in saved
    assert path.read_text(encoding="utf-8") == original
    if os.name == "posix":
        assert Path(backup).stat().st_mode & 0o777 == 0o600


# Keeps the general regenerate-config backup faithful to the original file
def test_ordinary_backup_preserves_original(monitor, tmp_path):
    if not hasattr(monitor, "create_timestamped_backup"):
        pytest.skip("The released version has no configuration backup helper")
    path = tmp_path / "settings.conf"
    original = "SMTP_PASSWORD='synthetic-old'\n# broken config remains recoverable\ninvalid = [\n"
    path.write_text(original, encoding="utf-8")
    backup = monitor.create_timestamped_backup(path)
    assert Path(backup).read_text(encoding="utf-8") == original


# Redacts an entire echoed credential before limiting provider error output
def test_provider_response_does_not_leak_secret_prefix(monitor, monkeypatch, capsys):
    import requests
    token = "synthetic-provider-secret-" + "q" * 230
    for name, value in (("WEBHOOK_ENABLED", True), ("WEBHOOK_PROVIDER", "ntfy"), ("WEBHOOK_URL", "https://ntfy.sh/synthetic-test-topic"), ("NTFY_ACCESS_TOKEN", token), ("NTFY_IMAGES", False), ("DEBUG_MODE", True)):
        monkeypatch.setattr(monitor, name, value, raising=False)

    # Substitutes only the HTTP response while retaining the real request and error renderer
    def send(session, request, **kwargs):
        response = requests.Response()
        response.request = request
        response.url = request.url
        response.status_code = 400
        response._content = ("Rejected value " + token + " trailing text").encode()
        return response

    monkeypatch.setattr(requests.Session, "send", send)
    if monitor.__name__ == "lol_monitor":
        monkeypatch.setattr(monitor, "WEBHOOK_SESSION", requests.Session())
    if monitor.__name__ == "xbox_monitor":
        import httpx

        # Supplies the same provider failure through Xbox Monitor's real HTTPX transport
        def httpx_send(transport, request):
            return httpx.Response(400, request=request, text="Rejected value " + token + " trailing text")

        monkeypatch.setattr(httpx.HTTPTransport, "handle_request", httpx_send)
    assert monitor.send_webhook("test", "test", force=True) == 1
    output = capsys.readouterr()
    assert token[:80] not in output.out + output.err


@pytest.mark.skipif(not hasattr(signal, "SIGHUP"), reason="SIGHUP is POSIX-only")
# Makes an explicit clear through the real writer effective at the next reload
def test_writer_clear_reaches_reload(monitor, monkeypatch, tmp_path):
    path = tmp_path / "private.env"
    path.write_text("NTFY_ACCESS_TOKEN=synthetic-file-token\n", encoding="utf-8")
    monkeypatch.setattr(monitor, "DOTENV_FILE", str(path))
    load_file(monitor, path)
    if hasattr(monitor, "update_dotenv_file"):
        monitor.update_dotenv_file(path, {"NTFY_ACCESS_TOKEN": ""})
    elif hasattr(monitor, "update_dotenv_value"):
        monitor.update_dotenv_value(path, "NTFY_ACCESS_TOKEN", "")
    else:
        pytest.skip("The released version has no matching secret writer")
    monitor.reload_secrets_signal_handler(signal.SIGHUP, None)
    assert monitor.NTFY_ACCESS_TOKEN == ""


@pytest.mark.parametrize("directory", [False, True])
# Rejects a CSV file whose parent is missing or whose path names a directory
def test_doctor_rejects_unusable_csv_path(monitor, tmp_path, directory):
    path = tmp_path / "missing" / "events.csv"
    if directory:
        path.mkdir(parents=True)
    if hasattr(monitor, "doctor_add_path_check"):
        report = monitor.DoctorReport()
        monitor.doctor_add_path_check(report, "CSV destination", path)
        assert report.checks[-1].status == "FAIL"
    elif hasattr(monitor, "doctor_destination_check"):
        assert monitor.doctor_destination_check("CSV destination", path).status == "FAIL"
    elif hasattr(monitor, "path_is_writable"):
        assert not monitor.path_is_writable(path)
    else:
        pytest.skip("This monitor has no matching Doctor output-path helper")


# Redacts a secret repeated in a hand-written backup comment
def test_setup_backup_redacts_repeated_comment_value(monitor, tmp_path):
    if not hasattr(monitor, "redact_config_backup"):
        pytest.skip("The released version has no setup backup redactor")
    path = tmp_path / "settings.conf"
    path.write_text('SMTP_PASSWORD = "synthetic-private-value" # previous: synthetic-private-value\nUNRELATED = 7\n', encoding="utf-8")
    backup = monitor.create_timestamped_backup(path, redact_secrets=True)
    assert "synthetic-private-value" not in Path(backup).read_text(encoding="utf-8")
    assert "UNRELATED = 7" in Path(backup).read_text(encoding="utf-8")


# Keeps unrelated numbers and strings valid when a short secret also appears in a comment
def test_setup_backup_keeps_settings_with_short_secret(monitor, tmp_path):
    if not hasattr(monitor, "redact_config_backup"):
        pytest.skip("The released version has no setup backup redactor")
    path = tmp_path / "settings.conf"
    path.write_text('SMTP_PASSWORD = "1" # previous: 1\nUNRELATED = 1800\n', encoding="utf-8")
    backup = monitor.create_timestamped_backup(path, redact_secrets=True)
    content = Path(backup).read_text(encoding="utf-8")
    assert 'SMTP_PASSWORD = "" # previous: <redacted>' in content
    assert "UNRELATED = 1800" in content
