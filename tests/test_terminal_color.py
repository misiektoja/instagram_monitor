from io import StringIO

import pytest


# Reads a block the template ships commented out, as the parser would see it once uncommented
def uncomment_block(source, first_line):
    lines = source.split("\n")
    start = next(index for index, line in enumerate(lines) if line.startswith(first_line))
    end = next(index for index in range(start, len(lines)) if lines[index].rstrip() == "# }")
    return "\n".join(line[2:] if line.startswith("# ") else line[1:] for line in lines[start:end + 1])


# Verifies the shipped config template and the built-in theme describe exactly the same colours, so
# generating a config file cannot silently change how any part of the output looks
def test_config_template_theme_matches_the_built_in_theme(im_module):
    commented = im_module.parse_config_content(uncomment_block(im_module.CONFIG_BLOCK, "# COLOR_THEME = {"), "<built-in-config>")

    assert "COLOR_THEME" not in im_module.parse_config_content(im_module.CONFIG_BLOCK, "<built-in-config>")
    assert commented["COLOR_THEME"] == im_module.DEFAULT_COLOR_THEME


# Verifies a configuration that sets the commented-out theme is still accepted, since older files all set it
def test_a_config_setting_the_theme_is_still_accepted(im_module):
    assert im_module.parse_config_content('COLOR_THEME = { "username": "green" }\n', "<config>") == {"COLOR_THEME": {"username": "green"}}


# Verifies the Timestamp label is left uncoloured, matching the sibling monitors
def test_timestamp_label_is_uncolored(im_module):
    assert im_module.DEFAULT_COLOR_THEME["timestamp_label"] == ""


# Verifies every style word used by the shipped theme resolves, allowing a deliberately uncoloured part
def test_default_theme_styles_all_resolve(im_module):
    for name, value in im_module.DEFAULT_COLOR_THEME.items():
        assert im_module._build_ansi_sequence(value) or value == "", name


# Verifies time highlighting accepts valid clock values without matching numeric port mappings
@pytest.mark.parametrize("value", ["00:00", "23:59", "21:07:39", "~21:07:39", "09:15 PM"])
def test_time_color_regex_accepts_only_complete_clock_values(im_module, value):
    assert im_module._TIME_ONLY_RE.fullmatch(value)
    for invalid in ("24:00", "12:60", "8000:8000", "abc12:30", "1:12:30"):
        assert im_module._TIME_ONLY_RE.search(invalid) is None


# Verifies the Docker publishing hint stays plain while a real time remains highlighted
def test_port_mapping_is_not_colored_as_a_time(im_module, monkeypatch):
    monkeypatch.setattr(im_module, "COLOR_ENABLED", True)
    monkeypatch.setattr(im_module, "_COLOR_STYLES", {"date": "\033[35m"})
    port_hint = "* Docker port publishing: Use -p 127.0.0.1:8000:8000 or Compose --service-ports"

    assert im_module._colorize_line(port_hint) == port_hint
    assert im_module._colorize_line("Next check at 21:07:39") == "Next check at \033[35m21:07:39\033[0m"


# Verifies every identity value is coloured for what it is: a name, an id or a link
@pytest.mark.parametrize("line,expected", [
    ("* Targets:                      misiektoja", "* Targets:                      <username>misiektoja<reset>"),
    ("* Targets:                      misiektoja, someone_else", "* Targets:                      <username>misiektoja<reset>, <username>someone_else<reset>"),
    ("Username:\t\t\t\tmisiektoja", "Username:\t\t\t\t<username>misiektoja<reset>"),
    ("User ID:\t\t\t\t1234567890", "User ID:\t\t\t\t<id>1234567890<reset>"),
    ("Profile URL:\t\t\t\thttps://www.instagram.com/misiektoja/", "Profile URL:\t\t\t\t<link>https://www.instagram.com/misiektoja/<reset>"),
])
def test_identity_values_are_coloured_by_their_kind(im_module, monkeypatch, line, expected):
    monkeypatch.setattr(im_module, "COLOR_ENABLED", True)
    monkeypatch.setattr(im_module, "_COLOR_STYLES", {name: f"<{name}>" for name in ("username", "id", "link")})
    monkeypatch.setattr(im_module, "ANSI_RESET", "<reset>")

    assert im_module._colorize_line(line) == expected


# Verifies quoted text is coloured whole, which an apostrophe or a dot used to cut short
@pytest.mark.parametrize("content", ["Don't miss this one", "S.T.A.L.K.E.R. 2 announcement", "back_to_work energy", "summer 2026 / part two"])
def test_quoted_content_is_coloured_whole(im_module, monkeypatch, content):
    monkeypatch.setattr(im_module, "COLOR_ENABLED", True)
    monkeypatch.setattr(im_module, "_COLOR_STYLES", {"username": "<username>"})
    monkeypatch.setattr(im_module, "ANSI_RESET", "<reset>")

    assert f"<username>{content}<reset>" in im_module._colorize_line(f"Caption: '{content}'")


# Verifies two quoted values on one line stay two values, since the closing quote rule could have joined them
def test_two_quoted_values_on_one_line_stay_separate(im_module, monkeypatch):
    monkeypatch.setattr(im_module, "COLOR_ENABLED", True)
    monkeypatch.setattr(im_module, "_COLOR_STYLES", {"username": "<username>"})
    monkeypatch.setattr(im_module, "ANSI_RESET", "<reset>")

    result = im_module._colorize_line("Renamed from 'first name' to 'second name' today")

    assert "<username>first name<reset>" in result
    assert "<username>second name<reset>" in result


# Verifies a quoted path, placeholder, option or URL fragment stays plain, since none of them is content
@pytest.mark.parametrize("value", ["/var/log/instagram.log", "~/logs/output.txt", "state.json", "<username>", "--env-file none", "?code=", "&state="])
def test_quoted_values_that_are_not_content_stay_plain(im_module, monkeypatch, value):
    monkeypatch.setattr(im_module, "COLOR_ENABLED", True)
    monkeypatch.setattr(im_module, "_COLOR_STYLES", {"username": "\x1b[36m"})

    assert "\x1b[36m" not in im_module._colorize_line(f"Value is '{value}' now")


# Verifies a received signal is coloured as the event it is, so the shipped theme key is not a setting that does nothing
def test_a_received_signal_line_uses_the_signal_colour(im_module, monkeypatch):
    monkeypatch.setattr(im_module, "COLOR_ENABLED", True)
    monkeypatch.setattr(im_module, "_COLOR_STYLES", {"signal": "<signal>"})
    monkeypatch.setattr(im_module, "ANSI_RESET", "<reset>")

    assert im_module._colorize_line("* Signal SIGUSR1 received") == "<signal>* Signal SIGUSR1 received<reset>"


# Verifies every part the shipped theme offers is actually looked up somewhere, so a documented setting cannot do nothing
def test_every_theme_part_is_used(im_module):
    import re
    from pathlib import Path

    source = Path(im_module.__file__).read_text(encoding="utf-8")
    looked_up = set(re.findall(r"""colorize\(\s*["']([a-z_]+)["']""", source))
    looked_up |= set(re.findall(r"""_COLOR_STYLES\.get\(["']([a-z_]+)["']""", source))
    looked_up |= set(re.findall(r"""(?:style_name|state_style|key|style) = ["']([a-z_]+)["']""", source))
    looked_up |= set(re.findall(r""",\s*["']([a-z_]+)["']\),?\s*$""", source, re.M))
    looked_up |= set(re.findall(r"""["'][A-Za-z ]+["']:\s*["']([a-z_]+)["']""", source))

    assert not set(im_module.DEFAULT_COLOR_THEME) - looked_up


# Verifies argparse never adds a palette of its own, which from Python 3.14 would survive --no-color
def test_argparse_adds_no_palette_of_its_own(im_module):
    import sys

    assert im_module.argparse_color_kwargs() == ({"color": False} if sys.version_info >= (3, 14) else {})


# Verifies the switch is actually passed to the parser, since the helper alone colours nothing
def test_the_parser_is_built_with_the_argparse_colour_switch(im_module):
    from pathlib import Path

    source = Path(im_module.__file__).read_text(encoding="utf-8")

    assert "**argparse_color_kwargs()" in source.split("argparse.ArgumentParser(", 1)[1].split("\n\n", 1)[0]


# Verifies labeled output and status changes keep their text while using direct bounded parsing
@pytest.mark.parametrize("line,styles", [("* Check interval:\t5 minutes (today)\n", ("timestamp_label", "count_up", "date_range")), ("Timestamp:\t21:07:39\n", ("timestamp_label", "timestamp_value")), ("STATUS: Online\n", ("status_online",)), ("alice changed status from Online to Offline\n", ("status_online", "status_offline"))])
def test_colorize_line_parses_security_sensitive_patterns_without_text_changes(im_module, monkeypatch, line, styles):
    monkeypatch.setattr(im_module, "COLOR_ENABLED", True)
    monkeypatch.setattr(im_module, "_COLOR_STYLES", {style: f"\033[{31 + index}m" for index, style in enumerate(styles)})

    colored = im_module._colorize_line(line)

    assert im_module.ANSI_ESCAPE_RE.sub("", colored) == line
    assert all(im_module._COLOR_STYLES[style] in colored for style in styles)


# Verifies hostile terminal control sequences in remote text cannot drive the operator's terminal
@pytest.mark.parametrize("hostile,expected", [
    ("bio\x1b[2Jcleared", "bio[2Jcleared"),
    ("bio\x1b]0;stolen title\x07", "bio]0;stolen title"),
    ("visible\rhidden", "visiblehidden"),
    ("bell\x07 and null\x00", "bell and null"),
    ("delete\x7f and c1\x9b[3J", "delete and c1[3J"),
])
def test_sanitize_terminal_text_removes_control_sequences(im_module, hostile, expected):
    assert im_module.sanitize_terminal_text(hostile) == expected


# Verifies the tool's own colour codes and ordinary whitespace survive sanitization
def test_sanitize_terminal_text_keeps_colours_and_layout(im_module):
    coloured = "\033[36mInfo\033[0m\tvalue\nnext line"

    assert im_module.sanitize_terminal_text(coloured) == coloured


# Verifies remote text cannot smuggle an escape sequence between the tool's own colour codes
def test_sanitize_terminal_text_cleans_between_colour_codes(im_module):
    smuggled = "\033[36mlabel\033[0m \x1b[2J\033[31mvalue\033[0m"

    assert im_module.sanitize_terminal_text(smuggled) == "\033[36mlabel\033[0m [2J\033[31mvalue\033[0m"


# Verifies the terminal writer sanitizes remote text before it reaches the stream
def test_logger_write_sanitizes_terminal_output(im_module, monkeypatch):
    written = []
    monkeypatch.setattr(im_module, "COLOR_ENABLED", False)
    monkeypatch.setattr(im_module, "DASHBOARD_ENABLED", False)
    monkeypatch.setattr(im_module, "pbar", None)
    logger = im_module.Logger.__new__(im_module.Logger)
    logger.terminal = type("Stream", (), {"write": lambda self, text: written.append(text), "flush": lambda self: None})()
    logger.target_logs = {}
    logger.target_paths = {}
    logger.main_log = None

    logger.write("Bio:\x1b[2J\x1b]0;pwned\x07 done")

    assert written == ["Bio:[2J]0;pwned done"]


# Verifies Rich dashboard values are sanitized before the console renders them
@pytest.mark.parametrize("dashboard_mode", ["user", "config"])
def test_terminal_dashboard_sanitizes_remote_text(im_module, monkeypatch, dashboard_mode):
    hostile = "visible\x1b[2J\x1b]0;pwned\x07hidden"
    target_data = {
        "safeuser": {
            "status": hostile,
            "followers": 1,
            "following": 2,
            "posts": 3,
            "reels": 0,
            "fetched_updates": [{"user": "safeuser", "type": "Post", "timestamp": "Now", "caption": hostile, "timestamp_ts": 1}],
        }
    }
    monkeypatch.setattr(im_module, "DASHBOARD_DATA", {"start_time": im_module.datetime.now(), "activities": [{"time": "Now", "message": hostile}], "targets": target_data})

    if dashboard_mode == "config":
        rendered = im_module.generate_config_dashboard(target_data, {"session_user": hostile})
    else:
        rendered = im_module.generate_user_dashboard(target_data)
    output = StringIO()
    console = im_module.Console(file=output, force_terminal=True, color_system="standard", width=180, height=45)
    console.print(rendered)

    assert rendered is not None
    plain = output.getvalue()
    assert "\x1b[2J" not in plain
    assert "\x1b]0;pwned\x07" not in plain
    assert "visible[2J]0;pwnedhidden" in plain


# Verifies the terminal is handed back even when the process exits without unwinding the input thread
def test_terminal_state_is_restored_once(im_module, monkeypatch):
    restored = []
    fake_termios = type("Termios", (), {"TCSADRAIN": 1, "tcsetattr": staticmethod(lambda stream, when, settings: restored.append(settings))})
    monkeypatch.setitem(__import__("sys").modules, "termios", fake_termios)
    im_module.DASHBOARD_INPUT_TERMINAL_STATE["settings"] = ["saved-state"]

    im_module.restore_dashboard_input_terminal()
    im_module.restore_dashboard_input_terminal()

    assert restored == [["saved-state"]]
    assert im_module.DASHBOARD_INPUT_TERMINAL_STATE["settings"] is None


# Verifies quitting through the signal handler restores the terminal before the process ends
def test_signal_handler_restores_the_terminal(im_module, monkeypatch):
    restored = []
    monkeypatch.setattr(im_module, "restore_dashboard_input_terminal", lambda: restored.append(True))
    monkeypatch.setattr(im_module, "WEB_DASHBOARD_STOP_EVENTS", {})
    monkeypatch.setattr(im_module, "DASHBOARD_ENABLED", False)
    monkeypatch.setattr(im_module.sys, "exit", lambda code=0: (_ for _ in ()).throw(SystemExit(code)))

    with pytest.raises(SystemExit):
        im_module.signal_handler(2, None, message="")

    assert restored == [True]
