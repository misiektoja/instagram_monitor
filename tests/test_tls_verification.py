"""Tests for VERIFY_SSL: which requests honor it, what is reported while it is off and its shipped default."""

import ast
import ssl
from pathlib import Path
from types import SimpleNamespace

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE = (PROJECT_ROOT / "instagram_monitor.py").read_text(encoding="utf-8")
WEBHOOK_URL = "https://discord.com/api/webhooks/123456789/aVeryLongWebhookTokenValue"


class _FakeResponse:
    # Answers a recorded request with the success every caller in this suite accepts
    def __init__(self):
        self.status_code = 204
        self.text = ""
        self.headers = {}

    # Returns an empty JSON body, which is what the IP lookup reads
    def json(self):
        return {}


# Records the keyword arguments of every request made through it
class RecordingRequests:
    def __init__(self):
        self.calls = []

    # Stands in for requests.get and for Session.post, both called with the destination first
    def __call__(self, url=None, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return _FakeResponse()

    # Returns the TLS setting the single recorded request carried
    def verified(self):
        assert len(self.calls) == 1, f"expected one request, recorded {len(self.calls)}"
        return self.calls[0].get("verify")


@pytest.fixture
# Restores the setting after each test, since it is a module global the whole tool reads
def tls_setting(im_module, monkeypatch):
    monkeypatch.setattr(im_module, "VERIFY_SSL", im_module.VERIFY_SSL)
    monkeypatch.setattr(im_module, "PROXY_ENABLED", False)
    monkeypatch.setattr(im_module, "PROXY_CERT_PATH", "")
    return monkeypatch


@pytest.mark.parametrize("verify", [True, False])
# Verifies the shared verify argument follows the setting when no proxy certificate is configured
def test_the_shared_verify_argument_follows_the_setting(im_module, tls_setting, verify):
    tls_setting.setattr(im_module, "VERIFY_SSL", verify)

    assert im_module.get_proxies_ssl() is verify


# Verifies a proxy certificate is used only while verification is on, since an off switch cannot check one
def test_a_proxy_certificate_is_ignored_while_verification_is_off(im_module, tls_setting, tmp_path):
    certificate = tmp_path / "proxy-ca.pem"
    certificate.write_text("certificate", encoding="utf-8")
    tls_setting.setattr(im_module, "PROXY_ENABLED", True)
    tls_setting.setattr(im_module, "PROXY_CERT_PATH", str(certificate))

    tls_setting.setattr(im_module, "VERIFY_SSL", True)
    assert im_module.get_proxies_ssl() == str(certificate)

    tls_setting.setattr(im_module, "VERIFY_SSL", False)
    assert im_module.get_proxies_ssl() is False


@pytest.mark.parametrize("verify", [True, False])
# Verifies the connectivity check carries the configured setting rather than the requests library default
def test_the_connectivity_check_honors_the_setting(im_module, tls_setting, verify):
    tls_setting.setattr(im_module, "VERIFY_SSL", verify)
    recorder = RecordingRequests()
    tls_setting.setattr(im_module.req, "get", recorder)

    assert im_module.check_internet("https://instagram.example/probe", 5) is True
    assert recorder.verified() is verify


@pytest.mark.parametrize("verify", [True, False])
# Verifies webhook deliveries carry the setting, so one channel cannot skip a check the others make
def test_the_webhook_delivery_honors_the_setting(im_module, tls_setting, verify):
    tls_setting.setattr(im_module, "VERIFY_SSL", verify)
    tls_setting.setattr(im_module, "WEBHOOK_ENABLED", True)
    tls_setting.setattr(im_module, "WEBHOOK_URL", WEBHOOK_URL)
    tls_setting.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", True)
    recorder = RecordingRequests()
    tls_setting.setattr(im_module.WEBHOOK_SESSION, "post", recorder)

    assert im_module.send_webhook("Title", "desc") == 0
    assert recorder.verified() is verify


# Verifies a webhook sent through the proxy still refuses to skip the check the setting asks for
def test_a_proxied_webhook_delivery_honors_the_setting(im_module, tls_setting):
    tls_setting.setattr(im_module, "VERIFY_SSL", False)
    tls_setting.setattr(im_module, "PROXY_ENABLED", True)
    tls_setting.setattr(im_module, "PROXY_WEBHOOKS", True)
    tls_setting.setattr(im_module, "WEBHOOK_ENABLED", True)
    tls_setting.setattr(im_module, "WEBHOOK_URL", WEBHOOK_URL)
    tls_setting.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", True)
    recorder = RecordingRequests()
    tls_setting.setattr(im_module.WEBHOOK_SESSION, "post", recorder)

    assert im_module.send_webhook("Title", "desc") == 0
    assert recorder.verified() is False


@pytest.mark.parametrize("verify", [True, False])
# Verifies the instaloader session is configured at construction, which is before its first request
def test_the_instaloader_session_honors_the_setting(im_module, tls_setting, verify):
    tls_setting.setattr(im_module, "VERIFY_SSL", verify)
    session = SimpleNamespace(proxies={}, verify=None)
    tls_setting.setattr(im_module.instaloader, "Instaloader", lambda **kwargs: SimpleNamespace(context=SimpleNamespace(_session=session)))

    assert im_module.instaloader_client(quiet=True).context._session.verify is verify


# Verifies an instaloader release that moves its session still returns a usable client instead of failing to start
def test_a_client_without_the_expected_session_still_starts(im_module, tls_setting):
    tls_setting.setattr(im_module, "VERIFY_SSL", False)
    tls_setting.setattr(im_module.instaloader, "Instaloader", lambda **kwargs: SimpleNamespace(context=SimpleNamespace()))

    assert im_module.instaloader_client(quiet=True).context is not None


@pytest.mark.parametrize("verify", [True, False])
# Verifies the SMTP handshake follows the setting, so email is not the one channel that keeps checking certificates
def test_the_smtp_context_honors_the_setting(im_module, tls_setting, verify):
    tls_setting.setattr(im_module, "VERIFY_SSL", verify)

    context = im_module.smtp_ssl_context()

    assert context.check_hostname is verify
    assert (context.verify_mode == ssl.CERT_REQUIRED) is verify


# Verifies no SMTP call site builds its own context, which would keep that one connection verifying while the setting is off
def test_only_the_shared_helper_builds_an_smtp_context():
    assert SOURCE.count("ssl.create_default_context()") == 1


@pytest.mark.parametrize("verify, silenced", [(True, False), (False, True)])
# Verifies the certificate warning is silenced only once the reader has chosen to switch verification off
def test_the_certificate_warning_is_silenced_only_while_verification_is_off(im_module, tls_setting, verify, silenced):
    disabled = []
    tls_setting.setattr(im_module, "VERIFY_SSL", verify)
    tls_setting.setattr(im_module.urllib3, "disable_warnings", lambda category: disabled.append(category))

    im_module.apply_tls_verification_setting()

    assert bool(disabled) is silenced


# Verifies the doctor passes the setting silently while it is on
def test_the_doctor_passes_while_verification_is_on(im_module, tls_setting):
    tls_setting.setattr(im_module, "VERIFY_SSL", True)

    check = next(item for item in im_module.doctor_check_configuration([]) if "TLS" in item.label)

    assert (check.status, check.advice) == ("PASS", None)


# Verifies the doctor warns while verification is off and names the setting to change and where it is documented
def test_the_doctor_warns_while_verification_is_off(im_module, tls_setting):
    tls_setting.setattr(im_module, "VERIFY_SSL", False)

    check = next(item for item in im_module.doctor_check_configuration([]) if "TLS" in item.label)

    assert check.status == "WARN"
    assert "VERIFY_SSL" in check.detail
    assert "VERIFY_SSL" in check.advice.fix
    assert check.advice.fix.endswith(f"\nGuide: {im_module.TLS_GUIDE_URL}")


@pytest.mark.parametrize("verify, concise", [(True, False), (False, True)])
# Verifies the summary always records the setting and puts it in front of the reader only when it is off
def test_the_summary_promotes_the_row_only_while_verification_is_off(im_module, tls_setting, verify, concise):
    tls_setting.setattr(im_module, "VERIFY_SSL", verify)

    row = im_module._startup_tls_summary_row()

    assert (row.concise, row.full) == (concise, True)
    assert row.label == "TLS verification"
    assert row.value == ("On" if verify else "Off, server certificates are not checked")


# Verifies certificates are verified unless the reader turns that off, in the shipped config and the fallback alike
def test_certificates_are_verified_by_default(im_module):
    shipped = im_module.parse_config_content(im_module.CONFIG_BLOCK, "<built-in-config>")

    assert shipped["VERIFY_SSL"] is True
    assert im_module.VERIFY_SSL is True


HTTP_METHODS = frozenset(("get", "post", "put", "patch", "delete", "head", "options", "request"))
# The expressions that carry the TLS decision, so a call passing anything else is a second opinion
VERIFY_ARGUMENTS = frozenset(("get_proxies_ssl()", "verify",))
# A guard against the sweep silently matching nothing after a rename: the tool has 4 call sites today
MINIMUM_HTTP_CALL_SITES = 4


# Returns every name the module binds to a requests session, so a session added later is swept without editing this
def session_receivers():
    return {node.targets[0].id for node in ast.walk(ast.parse(SOURCE)) if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and isinstance(node.value, ast.Call) and ast.unparse(node.value.func).endswith("Session")}


# Returns every outbound HTTP call in the module as a line number paired with its keyword arguments
def http_call_sites():
    receivers = {"req", "requests"} | session_receivers()
    for node in ast.walk(ast.parse(SOURCE)):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        receiver = node.func.value
        if node.func.attr in HTTP_METHODS and isinstance(receiver, ast.Name) and receiver.id in receivers:
            yield node.lineno, {keyword.arg: keyword.value for keyword in node.keywords}


# Verifies every outbound request passes the setting, so a call site added later cannot keep verifying while it is off
def test_every_outbound_request_passes_the_setting():
    calls = list(http_call_sites())

    assert len(calls) >= MINIMUM_HTTP_CALL_SITES, f"the sweep found {len(calls)} HTTP calls, so it no longer matches how requests are made"
    missing = [line for line, keywords in calls if "verify" not in keywords or ast.unparse(keywords["verify"]) not in VERIFY_ARGUMENTS]
    assert not missing, f"instagram_monitor.py lines {missing} make an HTTP call that does not pass the TLS setting"


# Verifies every outbound request carries a deadline, since a call without one hangs the monitoring loop indefinitely
def test_every_outbound_request_carries_a_deadline():
    # A call forwarding **kwargs takes its deadline from the helper that fills them in, which is not readable here
    missing = [line for line, keywords in http_call_sites() if "timeout" not in keywords and None not in keywords]

    assert not missing, f"instagram_monitor.py lines {missing} make an HTTP call without a timeout"
