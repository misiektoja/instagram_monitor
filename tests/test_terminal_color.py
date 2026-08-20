import pytest


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
