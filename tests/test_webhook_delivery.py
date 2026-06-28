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
