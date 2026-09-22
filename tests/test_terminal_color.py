import ast
import argparse
import re
import threading
from io import StringIO
from pathlib import Path

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


# Verifies the liveness banner timestamp carries the timestamp colour instead of the generic date colour
def test_liveness_check_timestamp_uses_timestamp_style(im_module, monkeypatch):
    monkeypatch.setattr(im_module, "COLOR_ENABLED", True)
    monkeypatch.setattr(im_module, "_COLOR_STYLES", {"timestamp_value": "\033[36m", "date": "\033[35m"})

    colored = im_module._colorize_line("Liveness check, timestamp:\tWed 26 Aug 2026, 20:23:03")

    assert colored == "Liveness check, timestamp:\t\033[36mWed 26 Aug 2026, 20:23:03" + im_module.ANSI_RESET


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


# Verifies a received signal marks its own name, so the shipped theme key is not a setting that does nothing
def test_a_received_signal_line_uses_the_signal_colour(im_module, monkeypatch):
    monkeypatch.setattr(im_module, "COLOR_ENABLED", True)
    monkeypatch.setattr(im_module, "_COLOR_STYLES", {"signal": "<signal>"})
    monkeypatch.setattr(im_module, "ANSI_RESET", "<reset>")

    assert im_module._colorize_line("* Signal SIGUSR1 received") == "* Signal <signal>SIGUSR1<reset> received"


# Verifies a warning marks its opening word instead of painting the line, so the values inside it stay visible
def test_a_warning_marks_its_opening_word_and_leaves_the_rest(im_module, monkeypatch):
    monkeypatch.setattr(im_module, "COLOR_ENABLED", True)
    monkeypatch.setattr(im_module, "_COLOR_STYLES", {"warning": "<warning>", "ip_address": "<ip>"})
    monkeypatch.setattr(im_module, "ANSI_RESET", "<reset>")

    assert im_module._colorize_line("* Warning: the host 192.168.1.10 stopped responding") == "* <warning>Warning:<reset> the host <ip>192.168.1.10<reset> stopped responding"


# Verifies a value colour never equals a whole-line style that can enclose it, which would hide the value
def test_block_styles_never_hide_a_name(im_module):
    resolved = {name: im_module._build_ansi_sequence(im_module.DEFAULT_COLOR_THEME[name]) for name in im_module.BLOCK_STYLE_PARTS + im_module.NAME_STYLE_PARTS}
    for block in im_module.BLOCK_STYLE_PARTS:
        for name in im_module.NAME_STYLE_PARTS:
            assert resolved[name] != resolved[block], f"{name} is invisible inside a {block} line"


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


# Verifies an ordinary English "no" inside a sentence stays plain, so a healthy report does not read as a failure
@pytest.mark.parametrize("line", [
    "* Monitoring healthy for misiektoja. No tracked change since the last check",
    "* No .env file found, skipping env-var reload",
    "* No target specified. Pass a TARGET_USERNAME or set TARGET_USERNAMES in the config.",
    "  The mail server accepted the sign-in. No email was sent.",
    "Running preflight checks. No files will be written.",
    "* Error: The saved Instagram session may no longer be valid",
])
def test_an_english_no_in_a_sentence_is_not_painted(im_module, monkeypatch, line):
    monkeypatch.setattr(im_module, "COLOR_ENABLED", True)
    monkeypatch.setattr(im_module, "_COLOR_STYLES", {"status_online": "<yes>", "status_offline": "<no>"})

    colored = im_module._colorize_line(line)

    assert "<yes>" not in colored and "<no>" not in colored


# Verifies a Yes or No answer is coloured as the whole value of a labelled row
@pytest.mark.parametrize(("answer", "style"), [("Yes", "status_online"), ("No", "status_offline")])
def test_an_answer_row_keeps_its_status_colour(im_module, monkeypatch, answer, style):
    monkeypatch.setattr(im_module, "COLOR_ENABLED", True)
    monkeypatch.setattr(im_module, "_COLOR_STYLES", {style: "<answer>"})

    colored = im_module._colorize_line(f"Can view all contents:\t\t\t{answer}")

    assert colored == f"Can view all contents:\t\t\t<answer>{answer}{im_module.ANSI_RESET}"


# Verifies argparse never adds a palette of its own, which from Python 3.14 would survive --no-color
def test_argparse_adds_no_palette_of_its_own(im_module):
    import sys

    assert im_module.argparse_color_kwargs() == ({"color": False} if sys.version_info >= (3, 14) else {})


# Verifies the switch is actually passed to the parser, since the helper alone colours nothing
def test_the_parser_is_built_with_the_argparse_colour_switch(im_module):
    from pathlib import Path

    source = Path(im_module.__file__).read_text(encoding="utf-8")

    construction = re.search(r"\n    parser = \w+\(\n(.*?)\n\n", source, re.S)

    assert construction is not None, "the parser construction could not be found"
    assert "**argparse_color_kwargs()" in construction.group(1)


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


# Verifies the email announcement is coloured like the webhook one, in the shape the shared delivery helper prints
@pytest.mark.parametrize("line,part", [
    ("Sending email notification to alerts@example.test", "email"),
    ("Sending webhook notification", "webhook"),
])
def test_a_delivery_announcement_is_painted_for_its_channel(im_module, monkeypatch, line, part):
    monkeypatch.setattr(im_module, "COLOR_ENABLED", True)
    monkeypatch.setattr(im_module, "_COLOR_STYLES", {part: f"<{part}>"})
    monkeypatch.setattr(im_module, "ANSI_RESET", "<reset>")

    assert im_module._colorize_line(line) == f"<{part}>{line}<reset>"


# Verifies the two channels keep the values every sibling monitor ships, so a channel reads the same in all of them
def test_the_delivery_channels_keep_the_shared_colours(im_module):
    assert im_module.DEFAULT_COLOR_THEME["email"] == "bright_cyan"
    assert im_module.DEFAULT_COLOR_THEME["webhook"] == "bright_blue"


# Verifies indented wizard hints stay plain, matching the five tools that never coloured them
def test_indented_wizard_hints_are_not_colored():
    source = (Path(__file__).resolve().parents[1] / "instagram_monitor.py").read_text(encoding="utf-8")

    coloured = re.findall(r'colorize\("warning", f?"  [^"]*', source)

    # The doctor summary sentence is the one indented line all seven colour
    assert [line for line in coloured if "All critical checks passed" not in line] == []


# Renders the Settings Mode panel and returns its plain text
def render_config_panel(im_module, config_data, width=200, height=80):
    output = StringIO()
    im_module.Console(file=output, width=width, height=height).print(im_module.generate_config_dashboard({}, config_data))
    return output.getvalue()


class TestTerminalConfigIdentity:
    # Settings Mode has to name the identity the run presents, like the other surfaces do
    def test_the_panel_names_the_connection_settings(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "HTTP_BACKEND", "curl_cffi")
        monkeypatch.setattr(im_module, "_CURL_CFFI_AVAILABLE", True)
        monkeypatch.setattr(im_module, "CURL_CFFI_IMPERSONATE", "auto")
        monkeypatch.setattr(im_module, "FOLLOW_LIST_SOURCE", "rest")
        monkeypatch.setattr(im_module, "USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/147.0")

        plain = render_config_panel(im_module, im_module.get_dashboard_config_data())

        assert "HTTP Backend" in plain and "curl_cffi" in plain
        assert "Impersonated Browser" in plain and "auto -> firefox" in plain
        assert "Follower List Source" in plain and "REST" in plain

    # Showing curl_cffi while the run falls back to requests would misreport what Instagram sees
    def test_the_panel_names_the_transport_fallback(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "HTTP_BACKEND", "curl_cffi")
        monkeypatch.setattr(im_module, "_CURL_CFFI_AVAILABLE", False)

        plain = render_config_panel(im_module, im_module.get_dashboard_config_data())

        assert "not installed" in plain

    # Nothing is impersonated without curl_cffi, so the row must not carry a stale target
    def test_the_panel_blanks_the_target_without_curl_cffi(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "HTTP_BACKEND", "requests")
        monkeypatch.setattr(im_module, "CURL_CFFI_IMPERSONATE", "firefox")

        plain = render_config_panel(im_module, im_module.get_dashboard_config_data())

        assert "Impersonated Browser" in plain
        assert "firefox" not in plain

    # The agents are read from the same sanitized snapshot as every other row, not from the live globals
    def test_the_agents_follow_the_privacy_substitutions(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "USER_AGENT", "Mozilla/5.0 SecretBuild/1")
        monkeypatch.setattr(im_module, "USER_AGENT_MOBILE", "Instagram 445.0.0.1.100 (iPhone17,1; iOS 26_0)")
        monkeypatch.setattr(im_module, "PRIVACY_SUBSTITUTIONS", [("SecretBuild/1", "<redacted>"), ("iPhone17,1", "<device>")])

        plain = render_config_panel(im_module, im_module.get_dashboard_config_data(), width=260)

        assert "SecretBuild" not in plain and "iPhone17,1" not in plain
        assert "<redacted>" in plain and "<device>" in plain

    # An agent that is not set yet reads as Auto rather than as an empty row
    def test_an_unset_agent_reads_as_auto(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "USER_AGENT", "")
        monkeypatch.setattr(im_module, "USER_AGENT_MOBILE", "")

        plain = render_config_panel(im_module, im_module.get_dashboard_config_data())

        assert "Browser UA:" in plain and "Auto" in plain


# Verifies the TLS row colours its state word, the one setting whose off state weakens a security property
def test_the_tls_row_colours_its_state(im_module, monkeypatch):
    monkeypatch.setattr(im_module, "COLOR_ENABLED", True)
    monkeypatch.setattr(im_module, "_COLOR_STYLES", {"boolean_true": "\033[32m", "boolean_false": "\033[31m"})

    on_row = im_module._colorize_line("* TLS verification:             On")
    off_row = im_module._colorize_line("* TLS verification:             Off, server certificates are not checked")

    assert on_row == f"* TLS verification:             \033[32mOn{im_module.ANSI_RESET}"
    assert off_row == f"* TLS verification:             \033[31mOff{im_module.ANSI_RESET}, server certificates are not checked"


HELP_SAMPLE = """usage: monitor [-h] [--config-file PATH] [TARGET]

positional arguments:
  TARGET                The target to monitor

Configuration & dotenv files:
  --config-file PATH    Path to a config file
  -m, --check-interval SECONDS
                        Time between checks (default: 60)

Examples:

Getting started:
  # Guided setup, see https://example.invalid/guide/
  python3 monitor.py --setup <target>

Guide: https://example.invalid/guide/
"""

HELP_SAMPLE_EPILOG = HELP_SAMPLE[HELP_SAMPLE.index("Examples:"):]


# Enables colour with the shipped theme and returns the escape sequence of every part
@pytest.fixture
def help_palette(monkeypatch, im_module):
    styles = {name: im_module._build_ansi_sequence(value) for name, value in im_module.DEFAULT_COLOR_THEME.items() if im_module._build_ansi_sequence(value)}
    monkeypatch.setattr(im_module, "COLOR_ENABLED", True)
    monkeypatch.setattr(im_module, "_COLOR_STYLES", styles)
    return styles


# Returns the sample help screen with the help palette applied
@pytest.fixture
def colored_help(help_palette, im_module):
    return im_module.colorize_help_text(HELP_SAMPLE, HELP_SAMPLE_EPILOG)


# Verifies colouring changes no character of the screen, since argparse laid out its columns on the plain text
def test_the_coloured_help_keeps_the_plain_layout(colored_help, im_module):
    assert im_module.ANSI_ESCAPE_RE.sub("", colored_help) == HELP_SAMPLE


# Verifies the argument groups and the example tasks share one heading colour, the anchors the reader scans for
def test_the_help_headings_carry_the_heading_colour(help_palette, colored_help, im_module):
    for heading in ("positional arguments:", "Configuration & dotenv files:", "Examples:", "Getting started:"):
        assert f"{help_palette['help_heading']}{heading}{im_module.ANSI_RESET}" in colored_help


# Verifies an option name and the value it takes are coloured apart, in the usage block and in the option rows
def test_the_help_option_names_and_their_values_are_coloured_apart(help_palette, colored_help, im_module):
    option = f"{help_palette['help_option']}--config-file{im_module.ANSI_RESET}"
    metavar = f"{help_palette['help_metavar']}PATH{im_module.ANSI_RESET}"

    assert f"{option} {metavar}" in colored_help
    assert f"[{option} {metavar}]" in colored_help
    assert f"{help_palette['help_usage']}usage:{im_module.ANSI_RESET}" in colored_help
    assert f"{help_palette['help_metavar']}TARGET{im_module.ANSI_RESET}                The target to monitor" in colored_help


# Verifies the examples separate the comment from the command and mark the value the reader has to replace
def test_the_help_examples_mark_comments_commands_and_placeholders(help_palette, colored_help, im_module):
    assert f"{help_palette['help_comment']}  # Guided setup" in colored_help
    assert f"{help_palette['help_command']}  python3 monitor.py --setup" in colored_help
    assert f"{help_palette['help_placeholder']}<target>{im_module.ANSI_RESET}" in colored_help


# Verifies a default note is dimmed and a documentation link keeps the shared link colour
def test_the_help_default_notes_and_links_stay_secondary(help_palette, colored_help, im_module):
    assert f"{help_palette['help_default']}(default: 60){im_module.ANSI_RESET}" in colored_help
    assert f"{help_palette['link']}https://example.invalid/guide/{im_module.ANSI_RESET}" in colored_help


# Verifies the help screen stays plain while colour is switched off, so --no-color and NO_COLOR clear all of it
def test_the_help_palette_switches_off_with_colour(im_module):
    assert im_module.colorize_help_text(HELP_SAMPLE, HELP_SAMPLE_EPILOG) == HELP_SAMPLE


# Verifies the finished help screen reaches the terminal untouched, past the colouriser that paints monitoring output
def test_the_help_screen_is_not_repainted_by_the_monitoring_rules(help_palette, im_module):
    buffer = StringIO()
    parser = im_module.ColoredHelpParser(prog="monitor", formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--config-file", metavar="PATH", help="Path to a config file")
    parser.print_help(im_module.ColorStream(buffer))

    written = buffer.getvalue()
    assert written == parser.format_help()
    assert help_palette["help_option"] in written


# Verifies a cut line closes the colour it opened, so the truncated tail does not paint every line printed after it
def test_a_truncated_line_closes_its_open_colour(im_module):
    pytest.importorskip("wcwidth")

    truncated = im_module.truncate_string_per_line("\x1b[31m0123456789ABCDEF\x1b[0m", 10)

    assert truncated == "\x1b[31m0123456789" + im_module.ANSI_RESET


# Verifies no extra reset is added when the colour closed before the cut or the line was never cut
def test_a_closed_or_uncut_colour_gains_no_extra_reset(im_module):
    pytest.importorskip("wcwidth")

    assert im_module.truncate_string_per_line("\x1b[31m0123\x1b[0m456789ABCDEF", 10) == "\x1b[31m0123\x1b[0m456789"
    assert im_module.truncate_string_per_line("\x1b[31m0123\x1b[0m", 10) == "\x1b[31m0123\x1b[0m"
    assert im_module.truncate_string_per_line("0123456789ABCDEF", 10) == "0123456789"


# Verifies an application version in a user agent row is not read as an address
@pytest.mark.parametrize("value", ["Instagram 282.0.7.727 (iPhone12,5; iOS 12_1)", "Instagram 219.0.0.12.117 Android (30/11; 420dpi)"])
def test_a_user_agent_version_is_not_coloured_as_an_address(im_module, monkeypatch, value):
    monkeypatch.setattr(im_module, "COLOR_ENABLED", True)
    monkeypatch.setattr(im_module, "_COLOR_STYLES", {"ip_address": "\033[93m"})

    line = f"* Mobile user agent:            {value}"

    assert im_module._colorize_line(line) == line


# Verifies a real address still carries the address colour
def test_an_address_keeps_its_colour(im_module, monkeypatch):
    monkeypatch.setattr(im_module, "COLOR_ENABLED", True)
    monkeypatch.setattr(im_module, "_COLOR_STYLES", {"ip_address": "\033[93m"})

    assert im_module._colorize_line("Connected through 10.0.0.5") == f"Connected through \033[93m10.0.0.5{im_module.ANSI_RESET}"


# Verifies the setup screens colour their links, since they print before the output stream colouriser is installed
def test_setup_screen_links_are_coloured(im_module, monkeypatch):
    link = im_module._build_ansi_sequence(im_module.DEFAULT_COLOR_THEME["link"])
    monkeypatch.setattr(im_module, "COLOR_ENABLED", True)
    monkeypatch.setattr(im_module, "_COLOR_STYLES", {"link": link})

    assert im_module.colorize_links("Guide: https://example.test/page") == f"Guide: {link}https://example.test/page{im_module.ANSI_RESET}"


# Verifies no setup screen prints a link without colouring it, which is how a plain link gets in
def test_no_setup_screen_prints_a_plain_link(im_module):
    setup = re.compile(r"^(?:run_setup_wizard|run_scrobble_health_setup_wizard|_wizard_|run_set_|run_browser_cookie_import|print_welcome_screen|print_doctor_next_steps|print_spotify_scrobble_app_guidance)")
    tree = ast.parse(Path(im_module.__file__).read_text(encoding="utf-8"))
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    plain = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "print"):
            continue
        nested = list(ast.walk(node))
        prints_link = any(isinstance(item, ast.Constant) and isinstance(item.value, str) and "http" in item.value for item in nested) or any(isinstance(item, ast.Name) and "URL" in item.id for item in nested)
        coloured = any(isinstance(item, ast.Name) and item.id in ("colorize", "colorize_links") for item in nested)
        owner, current = "", parents.get(node)
        while current is not None:
            if isinstance(current, ast.FunctionDef):
                owner = current.name
                break
            current = parents.get(current)
        if prints_link and not coloured and setup.match(owner):
            plain.append(f"{owner}:{node.lineno}")

    assert plain == []


class TestTheWidthCapAppliesToTheScreenOnly:
    """The saved copy used to be derived from the line already cut to the terminal width.

    `truncate_string_per_line` and `Logger.write` were each correct on their own, so the unit tests above
    never saw it: setting a width silently shortened the log file too, against what the documentation
    promises. These drive the real Logger and read the file it wrote.
    """

    # Writes one long line through the real Logger and returns what the screen and the log file received
    @staticmethod
    def _write(im_module, monkeypatch, tmp_path, line, target=None):
        pytest.importorskip("wcwidth")
        monkeypatch.setattr(im_module, "TRUNCATE_CHARS", 40)
        monkeypatch.setattr(im_module, "DASHBOARD_ENABLED", False)
        monkeypatch.setattr(im_module, "pbar", None)
        log_path = tmp_path / "monitor.log"
        logger = im_module.Logger(str(log_path))
        screen = StringIO()
        logger.terminal = screen
        if target:
            target_path = tmp_path / f"{target}.log"
            logger.add_target_log(target, str(target_path))
            thread = threading.Thread(target=logger.write, args=(line,), name=f"instagram_monitor:{target}")
            thread.start()
            thread.join()
            return screen.getvalue(), log_path.read_text(encoding="utf-8"), target_path.read_text(encoding="utf-8")
        logger.write(line)
        return screen.getvalue(), log_path.read_text(encoding="utf-8"), ""

    # The documentation promises the log file always keeps the full line, whatever the screen was given
    def test_a_line_cut_for_the_screen_is_saved_in_full(self, im_module, monkeypatch, tmp_path):
        line = "* Biography: " + "b" * 300 + "\n"

        screen, saved, _ = self._write(im_module, monkeypatch, tmp_path, line)

        assert len(screen.rstrip("\n")) == 40
        assert saved == line

    # A target log is the copy most runs actually read, so it earns the same promise as the main log
    def test_a_target_log_keeps_the_full_line_too(self, im_module, monkeypatch, tmp_path):
        line = "* Biography: " + "b" * 300 + "\n"

        screen, saved, target_saved = self._write(im_module, monkeypatch, tmp_path, line, target="target.user")

        assert len(screen.rstrip("\n")) == 40
        assert saved == target_saved == line

    # The saved copy still arrives plain and with tabs expanded, which is what the width cap must not change
    def test_the_saved_copy_stays_plain_with_its_tabs_expanded(self, im_module, monkeypatch, tmp_path):
        monkeypatch.setattr(im_module, "COLORED_OUTPUT", True)
        line = "Followers:\t" + "9" * 300 + "\n"

        _, saved, _ = self._write(im_module, monkeypatch, tmp_path, line)

        assert "\x1b" not in saved
        assert "\t" not in saved
        assert saved.strip().endswith("9" * 300)


# Verifies a fix block keeps its guide line a link while the rest of the block stays informational
def test_a_fix_block_guide_line_is_a_link(im_module, monkeypatch):
    link = im_module._build_ansi_sequence(im_module.DEFAULT_COLOR_THEME["link"])
    info = im_module._build_ansi_sequence(im_module.DEFAULT_COLOR_THEME["info"])
    monkeypatch.setattr(im_module, "COLOR_ENABLED", True)
    monkeypatch.setattr(im_module, "_COLOR_STYLES", {"link": link, "info": info})

    assert im_module.colorize_fix_line("To fix: Set the key then re-run") == f"{info}To fix: Set the key then re-run{im_module.ANSI_RESET}"
    assert im_module.colorize_fix_line("Guide: https://example.test/page") == f"Guide: {link}https://example.test/page{im_module.ANSI_RESET}"
    assert 'colorize("info", f"Guide:' not in Path(im_module.__file__).read_text(encoding="utf-8")


# Verifies a settings row is never painted as an error, since a value such as the follow list source reads like a log keyword
def test_a_summary_row_is_not_painted_by_a_log_keyword(im_module, monkeypatch):
    monkeypatch.setattr(im_module, "COLOR_ENABLED", True)
    monkeypatch.setattr(im_module, "_COLOR_STYLES", {name: f"<{name}>" for name in im_module.DEFAULT_COLOR_THEME})
    row = im_module._format_startup_summary_row(im_module.StartupSummaryRow("Follow list source", "auto (REST, GraphQL on failure)")).rstrip("\n")

    assert im_module._colorize_line(row) == row


# Verifies an ordinary error line still carries the block colour the summary rows opt out of
def test_an_error_line_is_still_painted(im_module, monkeypatch):
    monkeypatch.setattr(im_module, "COLOR_ENABLED", True)
    monkeypatch.setattr(im_module, "_COLOR_STYLES", {"error": "<error>"})

    assert im_module._colorize_line("* Error: the request timed out") == f"<error>* Error: the request timed out{im_module.ANSI_RESET}"


# Verifies the row shape the colouriser matches is the one the summary emitter prints, so the two cannot drift
def test_every_summary_row_is_recognised_by_its_value_column(im_module):
    rows = [im_module.StartupSummaryRow("Targets", "misiektoja"), im_module.StartupSummaryRow("Email transport", "Not configured"), im_module.StartupSummaryRow("  Proxy IP Address", "10.0.0.1")]

    for row in rows:
        line = im_module._format_startup_summary_row(row).rstrip("\n")
        assert im_module.is_startup_summary_row(line)
        assert line.index(row.value.strip()) == im_module.STARTUP_SUMMARY_VALUE_COLUMN

    assert not im_module.is_startup_summary_row("* Error: something failed")
    assert not im_module.is_startup_summary_row("* Warning: a timeout was hit")


# Verifies a date does not reach back over a padded gap and read the word in front of it as a weekday
def test_a_wide_gap_before_a_date_is_not_read_as_a_weekday(im_module):
    padded = im_module._LONG_DATE_RE.search("A padded column end     07 Feb 26, 00:05:42")
    weekday = im_module._LONG_DATE_RE.search("Sun 06 Apr 2025, 21:21:46")

    assert padded is not None and padded.group(0) == "07 Feb 26, 00:05:42"
    assert weekday is not None and weekday.group(0) == "Sun 06 Apr 2025, 21:21:46"
