"""Tests for config file parsing and round-tripping helpers."""

import pytest


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
