import pytest
from dotenv import dotenv_values

import instagram_monitor as monitor


@pytest.mark.parametrize("prefix", ["", "export ", " \texport\t ", "\t"])
@pytest.mark.parametrize("quoted_key", [False, True])
@pytest.mark.parametrize("replacement", ["new # value\nwith 'quotes'", ""])
# Verifies updates preserve export prefixes while replacing or removing complete quoted and multiline assignments
def test_dotenv_key_quotes_are_not_part_of_the_export_prefix(tmp_path, prefix, quoted_key, replacement):
    destination = tmp_path / ".env"
    key = "'SMTP_PASSWORD'" if quoted_key else "SMTP_PASSWORD"
    destination.write_text(f'# personal note\n\n{prefix}{key}="old\nsecret"\nSMTP_PASSWORD="duplicate"\nUNRELATED=keep\n', encoding="utf-8")
    assert dotenv_values(destination, interpolate=False)["SMTP_PASSWORD"] == "duplicate"

    monitor.update_dotenv_file(destination, {"SMTP_PASSWORD": replacement})

    content = destination.read_text(encoding="utf-8")
    parsed = dotenv_values(destination, interpolate=False)
    assert parsed == ({"SMTP_PASSWORD": replacement, "UNRELATED": "keep"} if replacement else {"UNRELATED": "keep"})
    assert content.startswith("# personal note\n\n")
    assert content.endswith("UNRELATED=keep\n")
    assert content.count("SMTP_PASSWORD") == bool(replacement)
    assert "old" not in content and "duplicate" not in content
    if replacement:
        assert content.splitlines()[2].startswith(prefix + "SMTP_PASSWORD=")
