"""Offline workflow tests for send_webhook delivery formatting."""


class _FakeResponse:
    # Stores the HTTP status and text returned by a fake webhook call
    def __init__(self, status_code=204, text=""):
        self.status_code = status_code
        self.text = text


class TestSendWebhook:
    # A successful JSON webhook call formats payload, headers, fields and privacy substitutions
    def test_json_payload_is_sanitized_and_posted(self, im_module, monkeypatch):
        calls = []
        long_value = "x" * (im_module.WEBHOOK_FIELD_VALUE_LIMIT + 10)

        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://example.com/hook")
        monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "WEBHOOK_HEADERS", {"X-Title": "{title}"})
        monkeypatch.setattr(im_module, "WEBHOOK_TRANSFORMS", [("title", "replace", "secret", "masked")])
        monkeypatch.setattr(im_module, "PRIVACY_SUBSTITUTIONS", [("realuser", "User1")])
        monkeypatch.setattr(im_module.req, "post", lambda *args, **kwargs: calls.append((args, kwargs)) or _FakeResponse())

        rc = im_module.send_webhook("realuser secret", "desc realuser", fields=[{"name": "realuser field", "value": long_value, "inline": True}], image_url="https://example.com/image.jpg")

        assert rc == 0
        assert len(calls) == 1
        args, kwargs = calls[0]
        payload = kwargs["json"]
        assert args == ("https://example.com/hook",)
        assert kwargs["headers"]["X-Title"] == "User1 masked"
        assert kwargs["headers"]["User-Agent"] == f"InstagramMonitor/{im_module.VERSION}"
        assert payload["embeds"][0]["title"] == "User1 masked"
        assert payload["embeds"][0]["description"] == "desc User1"
        assert payload["embeds"][0]["image"]["url"] == "https://example.com/image.jpg"
        assert payload["embeds"][0]["fields"][0]["name"] == "User1 field"
        assert payload["embeds"][0]["fields"][0]["value"] == "x" * im_module.WEBHOOK_FIELD_VALUE_LIMIT
        assert payload["embeds"][0]["fields"][0]["inline"] is True

    # A string webhook template is sent as raw data instead of JSON
    def test_string_template_uses_data_post(self, im_module, monkeypatch):
        calls = []

        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://example.com/hook")
        monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "WEBHOOK_TEMPLATE", "{title}:{fields_str}")
        monkeypatch.setattr(im_module.req, "post", lambda *args, **kwargs: calls.append((args, kwargs)) or _FakeResponse())

        rc = im_module.send_webhook("Title", "desc", fields=[{"name": "Name", "value": "Value"}])

        assert rc == 0
        assert len(calls) == 1
        _, kwargs = calls[0]
        assert kwargs["data"] == "Title:Name: Value"
        assert "json" not in kwargs

    # Disabled notification types return without posting to the webhook URL
    def test_notification_type_gate_blocks_post(self, im_module, monkeypatch):
        calls = []

        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://example.com/hook")
        monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", False)
        monkeypatch.setattr(im_module.req, "post", lambda *args, **kwargs: calls.append((args, kwargs)) or _FakeResponse())

        assert im_module.send_webhook("Title", "desc", notification_type="status") == 1
        assert calls == []

    # HTTP 429 responses are retried and a later success is reported as delivered
    def test_rate_limit_response_retries(self, im_module, monkeypatch):
        responses = [_FakeResponse(429, "slow down"), _FakeResponse(204, "")]
        calls = []

        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://example.com/hook")
        monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", True)
        monkeypatch.setattr(im_module.time, "sleep", lambda seconds: None)
        monkeypatch.setattr(im_module.req, "post", lambda *args, **kwargs: calls.append((args, kwargs)) or responses.pop(0))

        assert im_module.send_webhook("Title", "desc") == 0
        assert len(calls) == 2

    # A native ntfy call sends UTF-8 text, field details and the title query parameter
    def test_ntfy_payload_uses_native_topic_api(self, im_module, monkeypatch):
        calls = []
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_PROVIDER", "ntfy")
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://ntfy.sh/private-topic?auth=private-value")
        monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", True)
        monkeypatch.setattr(im_module.req, "post", lambda *args, **kwargs: calls.append((args, kwargs)) or _FakeResponse(200))

        rc = im_module.send_webhook("Instagram title za\u017c\u00f3\u0142\u0107", "Body: Bj\u00f6rk", fields=[{"name": "Count", "value": "3"}], image_url="https://example.com/image.jpg")

        assert rc == 0
        args, kwargs = calls[0]
        assert args == ("https://ntfy.sh/private-topic?auth=private-value",)
        assert kwargs["data"] == "Body: Bj\u00f6rk\n\nCount: 3\n\nImage: https://example.com/image.jpg".encode("utf-8")
        assert kwargs["params"] == {"title": "Instagram title za\u017c\u00f3\u0142\u0107"}
        assert kwargs["headers"]["Content-Type"] == "text/plain; charset=utf-8"
        assert "json" not in kwargs

    # Ntfy message truncation respects its UTF-8 byte limit without splitting a character
    def test_ntfy_message_is_bounded_by_utf8_bytes(self, im_module):
        title, message = im_module.build_ntfy_webhook_message("Title", ("a" * (im_module.NTFY_MESSAGE_LIMIT_BYTES - 1)) + "\U0001f3a5")
        assert title == "Title"
        assert len(message.encode("utf-8")) == im_module.NTFY_MESSAGE_LIMIT_BYTES - 1
        assert not message.endswith("\U0001f3a5")

    # An unsupported provider fails before any webhook request is attempted
    def test_invalid_webhook_provider_is_rejected(self, im_module, monkeypatch):
        calls = []
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_PROVIDER", "unsupported")
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://example.com/hook")
        monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", True)
        monkeypatch.setattr(im_module.req, "post", lambda *args, **kwargs: calls.append((args, kwargs)) or _FakeResponse())

        assert im_module.send_webhook("Title", "Body") == 1
        assert calls == []
