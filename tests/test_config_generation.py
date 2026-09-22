"""Tests for config file parsing and round-tripping helpers."""

import stat
import re
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

    # Generated config preserves a customized ordered IP lookup endpoint list
    def test_ip_address_urls_round_trip_from_runtime_values(self, im_module, monkeypatch):
        custom_urls = ["https://primary.example.test/ip", "https://backup.example.test/ip"]
        monkeypatch.setattr(im_module, "IP_ADDRESS_URL", custom_urls)

        rendered = im_module.generate_config_with_current_values()
        namespace: dict = {}
        exec(rendered, namespace)

        assert namespace["IP_ADDRESS_URL"] == custom_urls

    # Generated webhook defaults document private entry and suppress Discord mentions
    def test_webhook_defaults_match_safe_user_experience(self, im_module):
        rendered = im_module.generate_config_with_current_values()
        namespace: dict = {}
        exec(rendered, namespace)

        assert "instagram_monitor --set-webhook-url" in rendered
        assert namespace["WEBHOOK_TEMPLATE"]["allowed_mentions"] == {"parse": []}
        assert namespace["WEBHOOK_TEMPLATE"]["embeds"][0]["timestamp"] == "{timestamp}"

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


class TestConfigPersistence:
    # Config writes replace the destination and retain a timestamped backup
    def test_write_config_creates_backup(self, im_module):
        with make_test_directory() as directory_name:
            directory = Path(directory_name)
            destination = directory / "instagram_monitor.conf"
            destination.write_text("OLD_VALUE = True\n", encoding="utf-8")
            content = im_module.generate_config_with_current_values({**vars(im_module), "TARGET_USERNAMES": ["saved.target"]})

            status = im_module.write_config_file(destination, content)

            backup_path = Path(status["backup_path"])
            assert destination.read_text(encoding="utf-8") == content
            assert backup_path.read_text(encoding="utf-8") == "OLD_VALUE = True\n"
            assert backup_path.parent == directory
            assert backup_path.name.startswith("instagram_monitor.conf.")
            assert backup_path.name.endswith(".bak")

    # A backup must not widen access to a configuration the user deliberately kept private
    @pytest.mark.skipif(os.name != "posix", reason="file modes are POSIX-only")
    def test_write_config_backup_keeps_owner_only_mode(self, im_module):
        with make_test_directory() as directory_name:
            destination = Path(directory_name) / "instagram_monitor.conf"
            destination.write_text("OLD_VALUE = True\n", encoding="utf-8")
            os.chmod(destination, 0o600)
            content = im_module.generate_config_with_current_values(vars(im_module))

            status = im_module.write_config_file(destination, content)

            backup_path = Path(status["backup_path"])
            assert backup_path.read_text(encoding="utf-8") == "OLD_VALUE = True\n"
            assert backup_path.stat().st_mode & 0o077 == 0
            assert destination.stat().st_mode & 0o077 == 0

    # Invalid config content is rejected before the destination changes
    def test_write_config_rejects_invalid_content(self, im_module):
        with make_test_directory() as directory_name:
            destination = Path(directory_name) / "instagram_monitor.conf"
            destination.write_text("ORIGINAL = True\n", encoding="utf-8")

            with pytest.raises(SyntaxError):
                im_module.write_config_file(destination, "BROKEN = [\n")

            assert destination.read_text(encoding="utf-8") == "ORIGINAL = True\n"
            assert list(destination.parent.glob("*.bak")) == []

    # An existing config is replaced only after the user agrees to it
    def test_generated_config_asks_before_replacing(self, im_module):
        with make_test_directory() as directory_name:
            destination = Path(directory_name) / "instagram_monitor.conf"
            destination.write_text("OLD_VALUE = True\n", encoding="utf-8")
            asked = []

            backup_path, written = im_module.write_generated_config(destination, "INSTA_CHECK_INTERVAL = 5400\n", interactive=True, input_func=lambda prompt: asked.append(prompt) or "n")

            assert (backup_path, written) == (None, False)
            assert len(asked) == 1 and str(destination) in asked[0]
            assert destination.read_text(encoding="utf-8") == "OLD_VALUE = True\n"
            assert list(destination.parent.glob("*.bak")) == []

    # Agreeing replaces the file and keeps the timestamped backup the writer takes
    def test_generated_config_replaces_after_agreement(self, im_module):
        with make_test_directory() as directory_name:
            destination = Path(directory_name) / "instagram_monitor.conf"
            destination.write_text("OLD_VALUE = True\n", encoding="utf-8")

            backup_path, written = im_module.write_generated_config(destination, "INSTA_CHECK_INTERVAL = 5400\n", interactive=True, input_func=lambda prompt: "y")

            assert written is True
            assert destination.read_text(encoding="utf-8") == "INSTA_CHECK_INTERVAL = 5400\n"
            assert Path(backup_path).read_text(encoding="utf-8") == "OLD_VALUE = True\n"

    # --force replaces without asking, so the command stays usable from a script
    def test_generated_config_force_skips_the_question(self, im_module):
        with make_test_directory() as directory_name:
            destination = Path(directory_name) / "instagram_monitor.conf"
            destination.write_text("OLD_VALUE = True\n", encoding="utf-8")

            def refuse(prompt=""):
                raise AssertionError("a question was asked despite --force")

            backup_path, written = im_module.write_generated_config(destination, "INSTA_CHECK_INTERVAL = 5400\n", force=True, interactive=True, input_func=refuse)

            assert written is True
            assert destination.read_text(encoding="utf-8") == "INSTA_CHECK_INTERVAL = 5400\n"
            assert Path(backup_path).read_text(encoding="utf-8") == "OLD_VALUE = True\n"

    # With no terminal to ask on, an existing config is left alone rather than replaced silently
    def test_generated_config_refuses_without_a_terminal(self, im_module):
        with make_test_directory() as directory_name:
            destination = Path(directory_name) / "instagram_monitor.conf"
            destination.write_text("OLD_VALUE = True\n", encoding="utf-8")

            with pytest.raises(im_module.ConfigExistsError, match="no terminal to confirm"):
                im_module.write_generated_config(destination, "INSTA_CHECK_INTERVAL = 5400\n", interactive=False)

            assert destination.read_text(encoding="utf-8") == "OLD_VALUE = True\n"

    # A parent path that is a file is a write failure, not an existing config, so the advice must not say --force
    def test_a_file_in_the_way_of_the_parent_directory_is_not_an_existing_config(self, im_module):
        with make_test_directory() as directory_name:
            blocker = Path(directory_name) / "configs"
            blocker.write_text("not a directory\n", encoding="utf-8")

            with pytest.raises(OSError) as raised:
                im_module.write_generated_config(blocker / "instagram_monitor.conf", "INSTA_CHECK_INTERVAL = 5400\n", interactive=False)

            assert not isinstance(raised.value, im_module.ConfigExistsError)
            assert blocker.read_text(encoding="utf-8") == "not a directory\n"

    # A file that does not exist yet is written without a question
    def test_generated_config_writes_a_new_file_directly(self, im_module):
        with make_test_directory() as directory_name:
            destination = Path(directory_name) / "instagram_monitor.conf"

            def refuse(prompt=""):
                raise AssertionError("a question was asked for a file that does not exist")

            backup_path, written = im_module.write_generated_config(destination, "INSTA_CHECK_INTERVAL = 5400\n", interactive=True, input_func=refuse)

            assert (backup_path, written) == (None, True)
            assert destination.read_text(encoding="utf-8") == "INSTA_CHECK_INTERVAL = 5400\n"


class TestDotenvPersistence:
    # A secret the user turns off is removed, so the next reader does not find the key still present
    def test_cleared_secret_is_removed_rather_than_emptied(self, im_module):
        with make_test_directory() as directory_name:
            destination = Path(directory_name) / ".env"
            destination.write_text('NTFY_ACCESS_TOKEN="tk_saved"\nWEBHOOK_URL=https://example.test/topic\n', encoding="utf-8")

            im_module.update_dotenv_file(destination, {"NTFY_ACCESS_TOKEN": ""})
            content = destination.read_text(encoding="utf-8")

            assert "NTFY_ACCESS_TOKEN" not in content
            assert content == "WEBHOOK_URL=https://example.test/topic\n"
            assert "NTFY_ACCESS_TOKEN" not in dotenv_values(destination, interpolate=False)

    # A saved value written across several lines is replaced whole, since replacing only its first line left
    # the rest of the old secret behind and the next run could not parse what it wrote
    def test_a_multiline_secret_is_replaced_whole(self, im_module):
        with make_test_directory() as directory_name:
            destination = Path(directory_name) / ".env"
            destination.write_text('NTFY_ACCESS_TOKEN="first line\nsecond line"\nOTHER=keep\n', encoding="utf-8")

            im_module.update_dotenv_file(destination, {"NTFY_ACCESS_TOKEN": "replacement"})

            assert destination.read_text(encoding="utf-8") == 'NTFY_ACCESS_TOKEN="replacement"\nOTHER=keep\n'

    # Clearing such a value removes all of it, for the same reason
    def test_a_cleared_multiline_secret_leaves_nothing_behind(self, im_module):
        with make_test_directory() as directory_name:
            destination = Path(directory_name) / ".env"
            destination.write_text('NTFY_ACCESS_TOKEN="first line\nsecond line"\nOTHER=keep\n', encoding="utf-8")

            im_module.update_dotenv_file(destination, {"NTFY_ACCESS_TOKEN": ""})

            assert destination.read_text(encoding="utf-8") == "OTHER=keep\n"

    # Turning off a secret that was never saved does not add an empty key to the file
    def test_clearing_an_unsaved_secret_adds_nothing(self, im_module):
        with make_test_directory() as directory_name:
            destination = Path(directory_name) / ".env"
            destination.write_text("WEBHOOK_URL=https://example.test/topic\n", encoding="utf-8")

            im_module.update_dotenv_file(destination, {"NTFY_ACCESS_TOKEN": ""})

            assert destination.read_text(encoding="utf-8") == "WEBHOOK_URL=https://example.test/topic\n"

    # An exported assignment is removed the same way, so the shell form cannot keep a disabled value
    def test_cleared_secret_is_removed_from_an_exported_line(self, im_module):
        with make_test_directory() as directory_name:
            destination = Path(directory_name) / ".env"
            destination.write_text('export NTFY_ACCESS_TOKEN="tk_saved"\nKEEP=value\n', encoding="utf-8")

            im_module.update_dotenv_file(destination, {"NTFY_ACCESS_TOKEN": ""})

            assert destination.read_text(encoding="utf-8") == "KEEP=value\n"

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


# Verifies an assignment the owner exported keeps its export, since dropping it changes what a shell sourcing the file exports
def test_an_exported_assignment_keeps_its_export(tmp_path, im_module):
    destination = tmp_path / ".env"
    destination.write_text('export SMTP_PASSWORD="old"\nOTHER=keep\n', encoding="utf-8")

    im_module.update_dotenv_file(destination, {"SMTP_PASSWORD": "new"})

    assert destination.read_text(encoding="utf-8") == 'export SMTP_PASSWORD="new"\nOTHER=keep\n'


# Verifies a line break inside a value is escaped rather than written through, since a raw one would split the assignment
def test_a_line_break_in_a_value_cannot_split_the_assignment(tmp_path, im_module):
    destination = tmp_path / ".env"

    im_module.update_dotenv_file(destination, {"SMTP_PASSWORD": "one\ntwo"})

    assert destination.read_text(encoding="utf-8") == 'SMTP_PASSWORD="one\\ntwo"\n'


# Verifies the writer refuses a key this tool does not ship, so a typo cannot put an unknown name in the private file
def test_the_writer_refuses_a_key_this_tool_does_not_ship(tmp_path, im_module):
    with pytest.raises(ValueError):
        im_module.update_dotenv_file(tmp_path / ".env", {"NOT_A_SECRET": "value"})


# Verifies the writer refuses a value that is not text, so a mistyped caller fails before the file is touched
def test_the_writer_refuses_a_value_that_is_not_text(tmp_path, im_module):
    with pytest.raises(TypeError):
        im_module.update_dotenv_file(tmp_path / ".env", {"SMTP_PASSWORD": 1234})


# Verifies the backup name every tool in this family writes, so one documented shape covers them all
def test_the_backup_carries_the_family_name_and_mode(tmp_path, im_module):
    destination = tmp_path / "monitor.conf"
    destination.write_text("SETTING = 1\n", encoding="utf-8")

    backup_path = im_module.create_timestamped_backup(destination)

    assert re.fullmatch(r"monitor\.conf\.\d{14}\.bak", Path(backup_path).name)
    assert Path(backup_path).read_text(encoding="utf-8") == "SETTING = 1\n"
    # Windows has no owner-only permission bits to copy, so only the name and the content are pinned there
    if os.name == "posix":
        assert stat.S_IMODE(Path(backup_path).stat().st_mode) == 0o600


# Verifies a second backup in the same second takes its own name rather than overwriting the first
def test_a_second_backup_in_the_same_second_keeps_the_first(tmp_path, im_module):
    destination = tmp_path / "monitor.conf"
    destination.write_text("first\n", encoding="utf-8")
    first = im_module.create_timestamped_backup(destination)
    destination.write_text("second\n", encoding="utf-8")

    second = im_module.create_timestamped_backup(destination)

    assert first != second
    assert Path(first).read_text(encoding="utf-8") == "first\n"
    assert Path(second).read_text(encoding="utf-8") == "second\n"


# Verifies a destination that is not there yet earns no backup, since there is nothing to copy
def test_a_missing_destination_earns_no_backup(tmp_path, im_module):
    assert im_module.create_timestamped_backup(tmp_path / "absent.conf") is None


# The part of the configuration template every sibling monitor shares, in the order they all use
SHARED_SETTING_ORDER = ("WEBHOOK_HEADERS", "NTFY_ACCESS_TOKEN", "WEBHOOK_TEMPLATE", "WEBHOOK_TRANSFORMS", "DISABLE_LOGGING", "ASCII_LOG_SEPARATORS", "TRUNCATE_CHARS", "CLEAR_SCREEN", "COLORED_OUTPUT", "COLOR_THEME", "VERBOSE_MODE", "DEBUG_MODE", "DELIVERY_CONFIRMATIONS")


# Returns every setting the built-in template declares, in template order, including the commented theme block
def template_setting_order(module):
    order = []
    for line in module.CONFIG_BLOCK.split("\n"):
        match = re.match(r"^([A-Z][A-Z0-9_]*)\s*[:=]", line) or re.match(r"^# ([A-Z][A-Z0-9_]*)\s*=", line)
        if match and match.group(1) not in order:
            order.append(match.group(1))
    return order


# Verifies the template keeps the order shared with the sibling monitors, so one tool's config reads like the next
def test_the_template_keeps_the_shared_setting_order(im_module):
    order = template_setting_order(im_module)

    assert set(SHARED_SETTING_ORDER) <= set(order), f"the template no longer declares {sorted(set(SHARED_SETTING_ORDER) - set(order))}"
    assert [name for name in order if name in SHARED_SETTING_ORDER] == list(SHARED_SETTING_ORDER)


# Verifies the linter defaults below the template repeat it in the same order, so a setting cannot drift or be filed twice
def test_the_linter_defaults_follow_the_template_order(im_module):
    source = Path(im_module.__file__).read_text(encoding="utf-8").split("\n")
    start = next(index for index, line in enumerate(source) if line.startswith("# Do not change values below")) + 1
    end = next(index for index, line in enumerate(source) if line.startswith("exec(CONFIG_BLOCK"))
    order = template_setting_order(im_module)
    mirrored = [match.group(1) for match in (re.match(r"^([A-Z][A-Z0-9_]*)\s*[:=]", line) for line in source[start:end]) if match and match.group(1) in set(order)]

    assert len(mirrored) == len(set(mirrored)), "a setting is repeated in the linter defaults"
    assert mirrored == [name for name in order if name in set(mirrored)]


# Verifies an explicit colour theme survives a config rebuild, since the template ships the setting commented out
def test_a_rebuilt_config_keeps_an_explicit_color_theme(im_module):
    values = dict(im_module.config_template_defaults())
    values["COLOR_THEME"] = {"header": "bright_red"}

    rendered = im_module.generate_config_with_current_values(values)

    assert im_module.parse_config_content(rendered, "<generated>")["COLOR_THEME"] == {"header": "bright_red"}


# Verifies the shipped default stays commented out, so a rebuild does not pin a theme the user never chose
def test_a_rebuilt_config_leaves_the_default_theme_commented(im_module):
    rendered = im_module.generate_config_with_current_values(dict(im_module.config_template_defaults()))

    assert "\nCOLOR_THEME = {" not in rendered
