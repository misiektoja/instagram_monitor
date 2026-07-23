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
