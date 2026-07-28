"""Tests for proxy IP endpoint validation and failover behavior."""

import threading
from unittest.mock import Mock, call


# Builds one fake HTTP response with configurable JSON and plain-text content
def make_ip_response(payload=None, text="", json_error=False):
    response = Mock()
    response.text = text
    response.raise_for_status.return_value = None
    if json_error:
        response.json.side_effect = ValueError("not JSON")
    else:
        response.json.return_value = payload
    return response


class TestIpAddressUrlValidation:
    # Accepts a single URL or ordered list while trimming surrounding whitespace
    def test_normalizes_supported_url_configuration(self, im_module):
        assert im_module.normalize_ip_address_urls(" https://example.test/ip ") == ["https://example.test/ip"]
        assert im_module.normalize_ip_address_urls(["https://one.test/ip", "http://two.test/ip"]) == ["https://one.test/ip", "http://two.test/ip"]

    # Rejects empty malformed and credential-bearing endpoint configurations
    def test_rejects_unsafe_or_unusable_url_configuration(self, im_module):
        invalid_values = [[], (), [""], ["example.test/ip"], ["ftp://example.test/ip"], ["https://user:secret@example.test/ip"]]
        for value in invalid_values:
            try:
                im_module.normalize_ip_address_urls(value)
            except ValueError:
                continue
            raise AssertionError(f"Expected invalid IP_ADDRESS_URL value to fail: {value!r}")

    # Keeps every built-in endpoint valid and uses the documented MyIP API path
    def test_default_endpoints_are_valid_and_current(self, im_module):
        urls = im_module.normalize_ip_address_urls()
        assert "https://api.my-ip.io/v2/ip.json" in urls
        assert all(url.startswith("https://") for url in urls)


class TestIpAddressResponseParsing:
    # Accepts documented JSON and plain-text IPv4 or IPv6 response formats
    def test_extracts_valid_ipv4_and_ipv6_responses(self, im_module):
        responses = [
            (make_ip_response({"ip": "203.0.113.7"}), "203.0.113.7"),
            (make_ip_response({"origin": "203.0.113.8, 198.51.100.2"}), "203.0.113.8"),
            (make_ip_response("2001:db8::1"), "2001:db8::1"),
            (make_ip_response(text="2001:db8::2\n", json_error=True), "2001:db8::2"),
        ]
        for response, expected in responses:
            assert im_module._extract_ip_address_response(response) == expected

    # Rejects successful HTTP responses that do not contain an IP address
    def test_rejects_non_ip_response_bodies(self, im_module):
        responses = [
            make_ip_response({"ip": "not-an-ip"}),
            make_ip_response({"status": "rate limited"}),
            make_ip_response(text="<html>proxy login</html>", json_error=True),
            make_ip_response(text="", json_error=True),
        ]
        for response in responses:
            try:
                im_module._extract_ip_address_response(response)
            except ValueError:
                continue
            raise AssertionError("Expected response without an IP address to fail")


class TestGetIpAddressFailover:
    # Reaches every configured endpoint without sleeping between distinct providers
    def test_tries_complete_endpoint_list_before_waiting(self, im_module, monkeypatch):
        urls = [f"https://provider-{index}.test/ip" for index in range(5)]
        monkeypatch.setattr(im_module, "IP_ADDRESS_URL", urls)
        success = make_ip_response({"ip": "203.0.113.9"})
        request_get = Mock(side_effect=[OSError("down 0"), OSError("down 1"), OSError("down 2"), OSError("down 3"), success])
        sleep = Mock(return_value=False)
        monkeypatch.setattr(im_module.req, "get", request_get)
        monkeypatch.setattr(im_module, "interruptible_sleep", sleep)

        result = im_module.get_ip_address(max_retries=3, long_retry_attempts=1)

        assert result == "203.0.113.9"
        assert [item.args[0] for item in request_get.call_args_list] == urls
        sleep.assert_not_called()

    # Tries every entry even when the configured list is longer than max_retries
    def test_long_endpoint_list_is_not_truncated(self, im_module, monkeypatch):
        urls = [f"https://provider-{index}.test/ip" for index in range(10)]
        monkeypatch.setattr(im_module, "IP_ADDRESS_URL", urls)
        request_get = Mock(side_effect=OSError("all unavailable"))
        sleep = Mock(return_value=False)
        monkeypatch.setattr(im_module.req, "get", request_get)
        monkeypatch.setattr(im_module, "interruptible_sleep", sleep)

        result = im_module.get_ip_address(max_retries=3, long_retry_attempts=1)

        assert result.startswith("(unavailable:")
        assert [item.args[0] for item in request_get.call_args_list] == urls
        sleep.assert_not_called()

    # Retries a single legacy URL with the short delay between attempts
    def test_single_url_keeps_retry_behavior(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "IP_ADDRESS_URL", "https://provider.test/ip")
        success = make_ip_response({"ip": "203.0.113.10"})
        request_get = Mock(side_effect=[OSError("down 1"), OSError("down 2"), success])
        sleep = Mock(return_value=False)
        monkeypatch.setattr(im_module.req, "get", request_get)
        monkeypatch.setattr(im_module, "interruptible_sleep", sleep)

        result = im_module.get_ip_address(max_retries=3, retry_delay=7, long_retry_attempts=1)

        assert result == "203.0.113.10"
        assert request_get.call_count == 3
        assert sleep.call_args_list == [call(7, None), call(7, None)]

    # Applies the long delay only after every endpoint in a cycle fails
    def test_long_retry_waits_after_complete_endpoint_cycle(self, im_module, monkeypatch):
        urls = ["https://one.test/ip", "https://two.test/ip"]
        monkeypatch.setattr(im_module, "IP_ADDRESS_URL", urls)
        request_get = Mock(side_effect=OSError("unavailable"))
        sleep = Mock(return_value=False)
        monkeypatch.setattr(im_module.req, "get", request_get)
        monkeypatch.setattr(im_module, "interruptible_sleep", sleep)

        result = im_module.get_ip_address(max_retries=1, long_retry=11, long_retry_attempts=2)

        assert result.startswith("(unavailable:")
        assert [item.args[0] for item in request_get.call_args_list] == urls + urls
        assert sleep.call_args_list == [call(11, None)]

    # Continues failover when an endpoint returns a successful non-IP response
    def test_invalid_success_response_rotates_to_next_endpoint(self, im_module, monkeypatch):
        urls = ["https://bad.test/ip", "https://good.test/ip"]
        monkeypatch.setattr(im_module, "IP_ADDRESS_URL", urls)
        request_get = Mock(side_effect=[make_ip_response(text="<html>blocked</html>", json_error=True), make_ip_response({"ip": "203.0.113.11"})])
        monkeypatch.setattr(im_module.req, "get", request_get)

        result = im_module.get_ip_address(max_retries=1, long_retry_attempts=1)

        assert result == "203.0.113.11"
        assert [item.args[0] for item in request_get.call_args_list] == urls

    # Returns a bounded unavailable result for an empty endpoint list
    def test_empty_endpoint_list_does_not_crash(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "IP_ADDRESS_URL", [])
        request_get = Mock()
        monkeypatch.setattr(im_module.req, "get", request_get)

        result = im_module.get_ip_address()

        assert result == "(unavailable: ValueError: IP_ADDRESS_URL must contain at least one URL)"
        request_get.assert_not_called()

    # Stops before making a request when the caller event is already set
    def test_pre_set_stop_event_skips_requests(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "IP_ADDRESS_URL", ["https://provider.test/ip"])
        request_get = Mock()
        monkeypatch.setattr(im_module.req, "get", request_get)
        stop_event = threading.Event()
        stop_event.set()

        result = im_module.get_ip_address(stop_event=stop_event)

        assert result == "(unavailable: stopped)"
        request_get.assert_not_called()
