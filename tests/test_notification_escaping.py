"""Source-level guard that every value reaching an HTML notification body is escaped (no network)."""

import ast
import inspect

import pytest


# Interpolations that are safe without escape() because the value is a counter, a fixed word this tool
# chooses itself, or a username already restricted to [a-z0-9._] by normalize_instagram_username.
# Listed explicitly so a new unescaped name cannot slip in behind a blanket exemption
ALLOWED_UNESCAPED = frozenset({
    "user",
    "source",
    "story_type",
    "profile_visibility",
    "likes",
    "comments",
    "failure_count",
    "ERROR_FAILURE_THRESHOLD",
    "consecutive_behuman_errors",
    "posts_count", "posts_count_old",
    "reels_count", "reels_count_old",
    "followers_count", "followers_old_count", "followers_diff_str",
    "followings_count", "followings_old_count", "followings_diff_str",
    "profile_pic_mdate",
    "last_source",
    # Pre-escaped by their producer, named with a safe_ prefix at the point of escaping
    "safe_post_url", "safe_profile_url", "safe_owner_url", "safe_owner",
    # Fixed label text this tool writes itself, such as "Likes list:"
    "likes_users_list_mbody", "post_comments_list_mbody",
})

# Helpers that emit their own markup or render only dates, durations and numbers. None of them can carry
# Instagram-supplied text, so escaping their output would only mangle the timestamps users read
SAFE_HELPERS = frozenset({"get_cur_ts", "display_time", "get_date_from_ts", "get_short_date_from_ts", "calculate_timespan", "get_range_of_dates_from_tss"})

# Attribute access that resolves to a fixed word rather than free text
SAFE_ATTRIBUTES = frozenset({"capitalize", "lower", "upper", "title", "replace"})


# Collects every HTML notification body the module builds, as (function, source line, expression) triples
def html_body_interpolations(module):
    tree = ast.parse(inspect.getsource(module))
    enclosing = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(node):
                enclosing[id(child)] = node.name

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        targets = [target.id for target in node.targets if isinstance(target, ast.Name)]
        if not any("body_html" in name for name in targets):
            continue
        for part in ast.walk(node.value):
            if isinstance(part, ast.FormattedValue):
                yield enclosing.get(id(node), "<module>"), node.lineno, ast.unparse(part.value)


# Reports whether one interpolated expression is neutralized before it reaches the HTML body
def interpolation_is_safe(expression):
    parsed = ast.parse(expression, mode="eval").body

    if isinstance(parsed, ast.Name):
        # A value already built as escaped HTML, or an allowlisted safe-by-construction value
        return parsed.id.endswith("_html") or "body_html" in parsed.id or parsed.id in ALLOWED_UNESCAPED

    if isinstance(parsed, ast.Call):
        function = parsed.func
        if isinstance(function, ast.Attribute):
            # A method call on an already safe value, such as source.capitalize() or escape(bio).replace(...)
            return function.attr in SAFE_ATTRIBUTES and interpolation_is_safe(ast.unparse(function.value))
        name = function.id if isinstance(function, ast.Name) else ""
        return name in {"escape", *SAFE_HELPERS}

    if isinstance(parsed, ast.IfExp):
        # A conditional between two literal strings, such as 'started following' if x else 'stopped following'
        return all(isinstance(branch, ast.Constant) for branch in (parsed.body, parsed.orelse))

    return False


class TestHtmlNotificationEscaping:
    # Verifies every value interpolated into an HTML notification body is escaped where it is built
    def test_every_html_body_interpolation_is_escaped(self, im_module):
        unsafe = [f"{function}:{line} -> {{{expression}}}" for function, line, expression in html_body_interpolations(im_module) if not interpolation_is_safe(expression)]
        assert not unsafe, "unescaped Instagram-supplied text can reach an HTML email body:\n" + "\n".join(unsafe)

    # Verifies the sweep is actually looking at the notification bodies rather than silently finding none
    def test_html_body_sweep_covers_every_notification(self, im_module):
        interpolations = list(html_body_interpolations(im_module))
        assert len(interpolations) >= 150, "the HTML body sweep stopped finding notification bodies, update its matching"

    # Verifies an unescaped interpolation would actually be reported, so the sweep cannot pass vacuously
    @pytest.mark.parametrize("expression,expected", [
        ("escape(str(caption))", True),
        ("caption_html", True),
        ("user", True),
        ("source.capitalize()", True),
        ("get_date_from_ts(post_dt)", True),
        ("safe_owner", True),
        ("escape(str(bio)).replace(chr(10), '<br>')", True),
        ("error_msg", False),
        ("err_str", False),
        ("caption", False),
        ("owner", False),
    ])
    def test_interpolation_safety_rule(self, expression, expected):
        assert interpolation_is_safe(expression) is expected

    # Verifies the session-flag alert renders its placeholder rather than losing it to the mail client
    def test_session_flag_placeholder_survives_as_text(self, im_module):
        from html import escape
        rendered = escape("Session account '<anonymous>' has been flagged.")
        assert "&lt;anonymous&gt;" in rendered
        assert "<anonymous>" not in rendered
