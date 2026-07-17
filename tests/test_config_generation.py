"""Tests for config file parsing and round-tripping helpers."""

import os
from pathlib import Path
import tempfile
from unittest.mock import Mock

import pytest
from dotenv import dotenv_values


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = PROJECT_ROOT / "local" / "test_artifacts"


# Creates a disposable test directory under the project local directory
def make_test_directory():
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(dir=ARTIFACT_ROOT)


class TestSplitInlineComment:
    def test_plain_value_no_comment(self, im_module):
        assert im_module._split_inline_comment_preserving_strings("5400") == ("5400", "")

    def test_value_with_trailing_comment(self, im_module):
        assert im_module._split_inline_comment_preserving_strings("5400  # 1,5 hours") == ("5400", "# 1,5 hours")

    def test_hash_inside_single_quotes_is_not_a_comment(self, im_module):
        assert im_module._split_inline_comment_preserving_strings("'a#b'") == ("'a#b'", "")

    def test_hash_inside_double_quotes_is_not_a_comment(self, im_module):
        assert im_module._split_inline_comment_preserving_strings('"a#b"  # real') == ('"a#b"', "# real")

    def test_escaped_quote_does_not_open_string(self, im_module):
        rhs = r"'a\'b' # c"
        value, comment = im_module._split_inline_comment_preserving_strings(rhs)
        assert value == r"'a\'b'"
        assert comment == "# c"

    def test_trailing_whitespace_is_stripped(self, im_module):
        assert im_module._split_inline_comment_preserving_strings("True   ") == ("True", "")


class TestFormatConfigValue:
    def test_string_single_quote_default(self, im_module):
        assert im_module._format_config_value("hello", prefer_double_quotes=False) == "'hello'"

    def test_string_double_quote_preference(self, im_module):
        assert im_module._format_config_value("hello", prefer_double_quotes=True) == '"hello"'

    def test_string_with_embedded_quote_is_escaped(self, im_module):
        assert im_module._format_config_value("a'b", prefer_double_quotes=False) == r"'a\'b'"
        assert im_module._format_config_value('a"b', prefer_double_quotes=True) == r'"a\"b"'

    def test_backslash_is_escaped(self, im_module):
        assert im_module._format_config_value("a\\b", prefer_double_quotes=False) == r"'a\\b'"

    def test_none_renders_as_none(self, im_module):
        assert im_module._format_config_value(None, prefer_double_quotes=False) == "None"

    @pytest.mark.parametrize("value,expected", [(True, "True"), (False, "False"), (42, "42"), (3.5, "3.5")])
    def test_non_string_primitives_use_repr(self, im_module, value, expected):
        assert im_module._format_config_value(value, prefer_double_quotes=False) == expected


class TestGenerateConfigWithCurrentValues:
    def test_output_is_valid_python_and_reflects_overrides(self, im_module, monkeypatch):
        # Override a couple of runtime globals and confirm they surface in the rendered config
        monkeypatch.setattr(im_module, "INSTA_CHECK_INTERVAL", 1234, raising=False)
        monkeypatch.setattr(im_module, "TIME_FORMAT_12H", True, raising=False)

        rendered = im_module.generate_config_with_current_values()

        # Re-exec the rendered config into a clean namespace; it must parse cleanly
        ns: dict = {}
        exec(rendered, ns)
        assert ns["INSTA_CHECK_INTERVAL"] == 1234
        assert ns["TIME_FORMAT_12H"] is True

    def test_comments_and_blank_lines_are_preserved(self, im_module):
        rendered = im_module.generate_config_with_current_values()
        # The config block is full of comment lines; at least the section markers survive
        assert "SESSION_USERNAME" in rendered
        assert rendered.count("#") > 10

    # Generated config retains safe template values for secrets and custom headers
    def test_secret_values_and_webhook_headers_are_never_rendered(self, im_module, monkeypatch):
        secrets = {
            "SESSION_PASSWORD": "session-private-value",
            "SMTP_PASSWORD": "smtp-private-value",
            "WEBHOOK_URL": "https://example.test/private-webhook",
            "PROXY_URL": "https://proxy-user:proxy-private-value@example.test",
            "NTFY_ACCESS_TOKEN": "tk_private_access_token",
        }
        for key, value in secrets.items():
            monkeypatch.setattr(im_module, key, value, raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_HEADERS", {"Authorization": "Bearer private-header-value"})

        rendered = im_module.generate_config_with_current_values()
        namespace: dict = {}
        exec(rendered, namespace)

        for key, value in secrets.items():
            assert value not in rendered
            assert namespace[key] != value
        assert "private-header-value" not in rendered
        assert namespace["WEBHOOK_HEADERS"] == {}


class TestDotenvPersistence:
    # Atomic dotenv updates preserve unrelated content and round-trip quoted secret values
    def test_update_preserves_content_and_special_values(self, im_module):
        with make_test_directory() as directory_name:
            destination = Path(directory_name) / ".env"
            destination.write_text("# keep this\nUNRELATED=stay\nWEBHOOK_URL=old\n\nWEBHOOK_URL=duplicate\n", encoding="utf-8")
            webhook_url = "https://example.test/topic?auth=value#fragment"
            token = " space # double\" slash\\line\nnext ${HOME}"

            status = im_module.update_dotenv_file(destination, {"WEBHOOK_URL": webhook_url, "NTFY_ACCESS_TOKEN": token})
            content = destination.read_text(encoding="utf-8")
            parsed = dotenv_values(destination, interpolate=False)

            assert content.startswith("# keep this\nUNRELATED=stay\n")
            assert content.count("WEBHOOK_URL=") == 1
            assert parsed["WEBHOOK_URL"] == webhook_url
            assert parsed["NTFY_ACCESS_TOKEN"] == token
            assert status == {"path": str(destination), "updated_keys": ("WEBHOOK_URL", "NTFY_ACCESS_TOKEN")}
            assert webhook_url not in repr(status)
            assert token not in repr(status)

    # Dotenv updates reject keys outside the secret allowlist
    def test_update_rejects_unknown_keys(self, im_module):
        with make_test_directory() as directory_name:
            destination = Path(directory_name) / ".env"
            with pytest.raises(ValueError, match="Unsupported dotenv key"):
                im_module.update_dotenv_file(destination, {"UNEXPECTED_KEY": "secret"})
            assert not destination.exists()

    # Dotenv files are restricted to mode 0600 on POSIX systems
    def test_update_sets_posix_mode(self, im_module):
        if os.name != "posix":
            pytest.skip("POSIX file modes are unavailable")
        with make_test_directory() as directory_name:
            destination = Path(directory_name) / ".env"
            im_module.update_dotenv_file(destination, {"NTFY_ACCESS_TOKEN": "secret"})
            assert destination.stat().st_mode & 0o777 == 0o600

    # Failed atomic replacement leaves the existing dotenv file unchanged
    def test_update_replace_failure_preserves_original(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            directory = Path(directory_name)
            destination = directory / ".env"
            original = "# keep\nWEBHOOK_URL=old\n"
            destination.write_text(original, encoding="utf-8")
            monkeypatch.setattr(im_module.os, "replace", Mock(side_effect=OSError("replace failed")))

            with pytest.raises(OSError, match="replace failed"):
                im_module.update_dotenv_file(destination, {"WEBHOOK_URL": "https://example.test/new"})

            assert destination.read_text(encoding="utf-8") == original
            assert [path.name for path in directory.iterdir()] == [".env"]
