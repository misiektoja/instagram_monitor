"""Tests for PRIVACY_SUBSTITUTIONS handling in apply_privacy_substitutions."""

import pytest


class TestApplyPrivacySubstitutions:
    def test_disabled_when_empty(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "PRIVACY_SUBSTITUTIONS", [])
        assert im_module.apply_privacy_substitutions("realuser") == "realuser"

    def test_simple_string_substitution(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "PRIVACY_SUBSTITUTIONS", [("realuser", "User1"), ("secret", "X")])
        assert im_module.apply_privacy_substitutions("hi realuser secret") == "hi User1 X"

    def test_dict_keys_preserved_values_substituted(self, im_module, monkeypatch):
        # Keys must stay stable so JSON/API consumers don't break; only values change
        monkeypatch.setattr(im_module, "PRIVACY_SUBSTITUTIONS", [("realuser", "User1")])
        result = im_module.apply_privacy_substitutions({"realuser": {"caption": "realuser posted"}})
        assert "realuser" in result
        assert result["realuser"]["caption"] == "User1 posted"

    def test_recurses_into_lists(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "PRIVACY_SUBSTITUTIONS", [("a", "Z")])
        assert im_module.apply_privacy_substitutions(["a", "bab", {"k": "aaa"}]) == ["Z", "bZb", {"k": "ZZZ"}]

    def test_non_string_primitives_unchanged(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "PRIVACY_SUBSTITUTIONS", [("a", "Z")])
        assert im_module.apply_privacy_substitutions(42) == 42
        assert im_module.apply_privacy_substitutions(None) is None
        assert im_module.apply_privacy_substitutions(True) is True

    def test_tuple_entries_accepted(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "PRIVACY_SUBSTITUTIONS", [("foo", "bar")])
        assert im_module.apply_privacy_substitutions("foofoo") == "barbar"

    def test_invalid_entry_is_ignored_not_crashing(self, im_module, monkeypatch):
        # Wrong arity / non-string entries must be skipped without raising
        monkeypatch.setattr(im_module, "PRIVACY_SUBSTITUTIONS", [("ok", "OK"), ("only-one",), (1, 2), ("", "empty-search")])
        monkeypatch.setattr(im_module, "PRIVACY_SUBSTITUTIONS_INVALID_WARNED", False)
        assert im_module.apply_privacy_substitutions("ok then") == "OK then"

    def test_order_is_applied_sequentially(self, im_module, monkeypatch):
        # Later rules see the output of earlier ones
        monkeypatch.setattr(im_module, "PRIVACY_SUBSTITUTIONS", [("a", "b"), ("b", "c")])
        assert im_module.apply_privacy_substitutions("a") == "c"
