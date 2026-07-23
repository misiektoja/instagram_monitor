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
    assert "No separate image download is required" in installation
    assert "docker pull misiektoja/instagram-monitor:latest" in installation
    assert "docker compose pull" in installation


# Verifies container onboarding prioritizes direct Docker and isolates interactive setup commands
def test_container_onboarding_prioritizes_direct_docker_and_isolates_setup():
    installation = read_asset("docs/installation.md")
    quick_start = read_asset("docs/quick-start.md")
    compose = read_asset("docker-compose.yml")
    assert installation.index("### Install from Docker Hub") < installation.index("### Install with Docker Compose")
    direct_install = installation.split("### Install from Docker Hub", 1)[1].split("### Install with Docker Compose", 1)[0]
    compose_install = installation.split("### Install with Docker Compose", 1)[1].split("### Build the Docker Image Locally", 1)[0]
    assert "docker run --pull=always" in direct_install
    assert "docker pull misiektoja/instagram-monitor:latest" not in direct_install
    assert "\ndocker compose pull\n" not in compose_install
    assert "curl -fsSLO https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/docker-compose.yml" in compose_install
    assert "curl -fsSLO" not in quick_start
    assert "If you opened this page first" in quick_start
    assert '=== "Manual Python script on macOS or Linux"' in quick_start
    assert '=== "Manual Python script on Windows"' in quick_start
    assert quick_start.index('=== "Docker image on macOS or Windows PowerShell"') < quick_start.index('=== "Docker Compose"')
    assert 'docker run --rm --pull=always -it --init -v "${PWD}:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader misiektoja/instagram-monitor:latest --setup' in quick_start
    assert 'docker run --rm --pull=always -it --init --user "$(id -u):$(id -g)" -v "$PWD:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader misiektoja/instagram-monitor:latest --setup' in quick_start
    compose_quick_start = quick_start.split('=== "Docker Compose"', 1)[1].split("Run interactive setup commands", 1)[0]
    assert "run these shell commands in the same terminal immediately before setup" in compose_quick_start
    assert 'export INSTAGRAM_MONITOR_UID="$(id -u)"' in compose_quick_start
    assert 'export INSTAGRAM_MONITOR_GID="$(id -g)"' in compose_quick_start
    assert "docker compose run --rm --pull=always instagram_monitor --setup" in compose_quick_start
    assert "#        docker compose run --rm --pull=always instagram_monitor --setup" in compose
    for relative_path in ("README.md", "docs/index.md"):
        landing_page = read_asset(relative_path)
        quick_install = landing_page.split("Quick Install & Run", 1)[1].split("<a id=\"features\"></a>", 1)[0]
        assert quick_install.index("#### Docker image - fastest container setup") < quick_install.index("#### Docker Compose - shorter recurring commands")
        assert "#### Python from PyPI" in quick_install
        assert "##### macOS or Windows" in quick_install
        assert "##### Linux" in quick_install
        assert "\ndocker pull misiektoja/instagram-monitor:latest" not in quick_install
        assert "\ndocker compose pull" not in quick_install
        assert "docker run --rm --pull=always" in quick_install
        assert "docker compose run --rm --pull=always instagram_monitor --setup" in quick_install
        assert "pip install instagram_monitor\n```\n\nRun setup by itself:\n\n```sh\ninstagram_monitor --setup" in quick_install
        assert 'misiektoja/instagram-monitor:latest --setup\n```\n\nAfter setup finishes, start monitoring with the files created by the wizard:\n\n```sh\ndocker run --rm -it --init -v "${PWD}:/data:z"' in quick_install
        assert 'misiektoja/instagram-monitor:latest --setup\n```\n\nAfter setup finishes, start monitoring:\n\n```sh\ndocker run --rm -it --init --user "$(id -u):$(id -g)"' in quick_install
    readme = read_asset("README.md")
    assert "# Manual Python script on macOS or Linux\npython3 instagram_monitor.py --setup" in readme
    assert "# Manual Python script on Windows\npython instagram_monitor.py --setup" in readme
    assert readme.index("# Docker image on macOS or Windows PowerShell") < readme.index("# Docker Compose on native Linux only")
    assert "# Docker image on macOS or Windows PowerShell\ndocker run --rm --pull=always" in readme
    assert "# Docker Compose on native Linux only\nexport INSTAGRAM_MONITOR_UID" in readme


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
    assert "creates a backup whose name includes the current date and time" in configuration
    assert "Usernames written directly after the command and usernames passed through `--targets` are combined" in configuration


# Verifies quick-start guidance includes direct Docker commands for desktop and Linux hosts
def test_quick_start_covers_direct_docker_host_variants():
    quick_start = read_asset("docs/quick-start.md")
    assert '=== "Docker image on macOS or Windows PowerShell"' in quick_start
    assert '=== "Docker image on Linux"' in quick_start
    assert "instagram_monitor_session:/home/instagram/.config/instaloader" in quick_start


# Verifies Firefox guidance covers Linux package variants for local and container imports
def test_firefox_docs_cover_snap_and_flatpak():
    configuration = read_asset("docs/configuration.md")
    usage = read_asset("docs/usage.md")
    assert "installed natively, through Snap or through Flatpak" in configuration
    assert '-v "$HOME/snap/firefox/common/.mozilla/firefox:/home/instagram/.mozilla/firefox:ro"' in usage
    assert '-v "$HOME/.var/app/org.mozilla.firefox/.mozilla/firefox:/home/instagram/.mozilla/firefox:ro"' in usage
    assert "Do not add `:z` or `:Z` to the whole Firefox profile mount" in usage


# Verifies manual quick-start commands link both Instagram authentication modes
def test_quick_start_links_both_authentication_modes():
    quick_start = read_asset("docs/quick-start.md")
    assert "[No-Login Mode](configuration.md#no-login-mode-without-session-login)" in quick_start
    assert "[Logged-In Mode](configuration.md#logged-in-mode-with-session-login)" in quick_start


# Verifies Compose smoke checks cannot replace the locally built image with a registry image
def test_container_smoke_checks_disable_pulls():
    workflow = read_asset(".github/workflows/tests.yml")
    assert workflow.count("docker compose -f docker-compose.yml run --rm --pull=never instagram_monitor") == 2


# Verifies Compose loads mounted secrets and attached examples suppress service prefixes
def test_compose_defaults_load_dotenv_and_suppress_attached_prefixes():
    compose = read_asset("docker-compose.yml")
    assert 'command: ["--env-file", "/data/.env"]' in compose
    assert "docker compose up --no-log-prefix" in compose
    for relative_path in ("README.md", "docs/index.md", "docs/quick-start.md", "docs/installation.md", "docs/usage.md", "docs/view-modes.md"):
        assert "docker compose up --no-log-prefix" in read_asset(relative_path)
    assert "docker compose logs -f --no-log-prefix" in read_asset("docs/usage.md")


# Verifies historical feature links target their current documentation sections
def test_release_notes_use_current_documentation_links():
    release_notes = read_asset("RELEASE_NOTES.md")
    for fragment in ("view-modes/#terminal-dashboard-mode", "view-modes/#web-dashboard-mode", "usage/#webhook-notifications", "usage/#follower-churn-detection", "usage/#output-directory", "usage/#skipping-follow-changes", "anti-detection/#use-the-human-mode", "anti-detection/#use-the-jitter-mode", "configuration/#user-agent"):
        assert f"https://misiektoja.github.io/instagram_monitor/{fragment}" in release_notes
    assert "https://github.com/misiektoja/instagram_monitor#" not in release_notes
