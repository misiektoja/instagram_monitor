"""Regression tests for installation-aware documentation."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


# Reads one repository text asset as UTF-8
def read_asset(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


# Verifies installation guidance covers every supported delivery and upgrade path
def test_installation_docs_cover_all_delivery_and_upgrade_paths():
    installation = read_asset("docs/installation.md")
    for heading in ("### Install from PyPI", "### Install the Manual Script", "### Install with Docker Compose", "### Install from Docker Hub", "### Upgrade a PyPI Installation", "### Upgrade a Manual Installation", "### Upgrade a Docker Compose Installation", "### Upgrade a Direct Docker Installation", "### Upgrade a Locally Built Docker Image"):
        assert heading in installation
    assert "The published image already contains Python and all core libraries" in installation
    assert "The Docker Compose v2 plugin" in installation
    assert "curl -fsSLO https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/instagram_monitor.py" in installation
    assert "curl -fsSLO https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/requirements.txt" in installation
    assert "pip install --upgrade -r requirements.txt" in installation
    assert "docker build --pull --tag instagram-monitor:local ." in installation


# Verifies manual upgrade guidance repeats linked files and direct download commands
def test_manual_upgrade_docs_are_self_contained():
    installation = read_asset("docs/installation.md")
    manual_upgrade = installation.split("### Upgrade a Manual Installation", 1)[1].split("### Upgrade a Docker Compose Installation", 1)[0]
    assert "[instagram_monitor.py](https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/instagram_monitor.py)" in manual_upgrade
    assert "[requirements.txt](https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/requirements.txt)" in manual_upgrade
    assert "curl -fsSLO https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/instagram_monitor.py" in manual_upgrade
    assert "curl -fsSLO https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/requirements.txt" in manual_upgrade
    assert "pip install --upgrade -r requirements.txt" in manual_upgrade


# Verifies monitoring guidance exposes saved targets and every install-aware command prefix
def test_usage_docs_cover_targets_and_install_commands():
    usage = read_asset("docs/usage.md")
    for value in ("TARGET_USERNAMES", "--targets target_user_1,target_user_2,target_user_3", "python3 instagram_monitor.py", "docker compose run --rm instagram_monitor", "docker compose run --rm --service-ports instagram_monitor", "misiektoja/instagram-monitor:latest"):
        assert value in usage


# Verifies configuration guidance explains direct UTF-8 output and target precedence
def test_configuration_docs_explain_generation_and_precedence():
    configuration = read_asset("docs/configuration.md")
    assert "writes the template directly as UTF-8" in configuration
    assert "creates a timestamped backup first" in configuration
    assert "Positional usernames and `--targets` values are combined" in configuration


# Verifies quick-start guidance includes direct Docker commands for desktop and Linux hosts
def test_quick_start_covers_direct_docker_host_variants():
    quick_start = read_asset("docs/quick-start.md")
    assert "# Docker image on macOS or Windows PowerShell" in quick_start
    assert "# Docker image on Linux" in quick_start
    assert "instagram_monitor_session:/home/instagram/.config/instaloader" in quick_start


# Verifies manual quick-start commands link both Instagram authentication modes
def test_quick_start_links_both_authentication_modes():
    quick_start = read_asset("docs/quick-start.md")
    assert "[No-Login Mode](configuration.md#no-login-mode-without-session-login)" in quick_start
    assert "[Logged-In Mode](configuration.md#logged-in-mode-with-session-login)" in quick_start
