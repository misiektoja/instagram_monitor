"""Semantic regression tests for installation-aware documentation."""

import configparser
import re
import subprocess
import textwrap
from pathlib import Path

import pytest
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]


# Reads one repository text asset as UTF-8
def read_asset(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


# Returns Markdown headings and offsets while ignoring code-fence contents
def markdown_headings(text: str) -> list[tuple[int, int, str]]:
    headings = []
    offset = 0
    in_fence = False
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        if stripped.startswith("```"):
            in_fence = not in_fence
        elif not in_fence:
            match = re.match(r"^(#{1,6})\s+(.+?)\s*$", stripped)
            if match:
                headings.append((offset, len(match.group(1)), match.group(2)))
        offset += len(line)
    return headings


# Returns one Markdown section whose heading contains every requested term
def markdown_section(text: str, level: int, *heading_terms: str) -> str:
    headings = markdown_headings(text)
    lowered_terms = tuple(term.casefold() for term in heading_terms)
    for index, (start, heading_level, heading_text) in enumerate(headings):
        if heading_level == level and all(term in heading_text.casefold() for term in lowered_terms):
            later_boundaries = (later_start for later_start, later_level, _later_text in headings[index + 1:] if later_level <= level)
            end = next(later_boundaries, len(text))
            return text[start:end]
    raise AssertionError(f"No level-{level} Markdown section contains terms: {heading_terms}")


# Returns normalized non-empty lines from fenced Markdown code blocks
def fenced_code_lines(text: str) -> list[str]:
    blocks = re.findall(r"^[ \t]*```[^\n]*\n(.*?)^[ \t]*```[ \t]*$", text, flags=re.MULTILINE | re.DOTALL)
    return [line.strip() for block in blocks for line in textwrap.dedent(block).splitlines() if line.strip()]


# Verifies a document contains all requested concepts without fixing their sentence wording
def assert_concepts(text: str, *concepts: str) -> None:
    lowered = text.casefold()
    for concept in concepts:
        assert concept.casefold() in lowered


# Verifies installation guidance retains every supported delivery and upgrade command
def test_installation_docs_cover_delivery_and_upgrade_commands():
    installation = read_asset("docs/installation.md")
    commands = fenced_code_lines(installation)
    for command in ("pip install instagram_monitor", "curl -fsSLO https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/instagram_monitor.py", "curl -fsSLO https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/requirements.txt", "pip install --upgrade -r requirements.txt", "docker build --pull --tag instagram-monitor:local .", "docker pull misiektoja/instagram-monitor:latest", "docker compose pull"):
        assert command in commands
    assert_concepts(installation, "PyPI", "Docker Hub", "Docker Compose", "Manual")


# Verifies onboarding keeps direct Docker first and avoids redundant image pulls
def test_container_onboarding_prioritizes_direct_docker_and_avoids_redundant_pulls():
    installation = read_asset("docs/installation.md")
    quick_start = read_asset("docs/setup-and-first-run.md")
    compose = read_asset("docker-compose.yml")
    direct_install = markdown_section(installation, 3, "Docker Hub")
    compose_install = markdown_section(installation, 3, "Docker Compose")
    assert installation.index(direct_install) < installation.index(compose_install)
    assert any(line.startswith("docker run --rm --pull=always") for line in fenced_code_lines(direct_install))
    assert "docker pull misiektoja/instagram-monitor:latest" not in fenced_code_lines(direct_install)
    assert "docker compose pull" not in fenced_code_lines(compose_install)
    assert "curl -fsSLO https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/docker-compose.yml" in fenced_code_lines(compose_install)
    assert not any(line.startswith("curl -fsSLO") for line in fenced_code_lines(quick_start))
    assert 'docker run --rm --pull=always -it --init -v "${PWD}:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader misiektoja/instagram-monitor:latest --setup' in fenced_code_lines(quick_start)
    assert 'docker run --rm --pull=always -it --init --user "$(id -u):$(id -g)" -v "$PWD:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader misiektoja/instagram-monitor:latest --setup' in fenced_code_lines(quick_start)
    assert "docker compose run --rm --pull=always instagram_monitor --setup" in fenced_code_lines(quick_start)
    assert "#        docker compose run --rm --pull=always instagram_monitor --setup" in compose


# Verifies both landing pages retain equivalent quick-install commands
def test_landing_pages_offer_equivalent_quick_install_commands():
    required_commands = ("pip install instagram_monitor", "instagram_monitor --setup", "docker compose run --rm --pull=always instagram_monitor --setup", 'docker run --rm --pull=always -it --init -v "${PWD}:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader misiektoja/instagram-monitor:latest --setup', 'docker run --rm --pull=always -it --init --user "$(id -u):$(id -g)" -v "$PWD:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader misiektoja/instagram-monitor:latest --setup')
    for relative_path in ("README.md", "docs/index.md"):
        quick_install = markdown_section(read_asset(relative_path), 3, "Quick", "Install")
        commands = fenced_code_lines(quick_install)
        for command in required_commands:
            assert command in commands
        assert "docker pull misiektoja/instagram-monitor:latest" not in commands
        assert "docker compose pull" not in commands
        assert_concepts(quick_install, "PyPI", "Docker image", "Docker Compose", "Linux", "Windows")


# Verifies manual upgrade guidance remains independently executable
def test_manual_upgrade_docs_are_self_contained():
    installation = read_asset("docs/installation.md")
    manual_upgrade = markdown_section(installation, 3, "Upgrade", "Manual")
    commands = fenced_code_lines(manual_upgrade)
    for filename in ("instagram_monitor.py", "requirements.txt"):
        assert f"https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/{filename}" in manual_upgrade
    for command in ("curl -fsSLO https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/instagram_monitor.py", "curl -fsSLO https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/requirements.txt", "pip install --upgrade -r requirements.txt"):
        assert command in commands


# Verifies usage guidance exposes saved targets and every install-aware command prefix
def test_usage_docs_cover_targets_and_install_commands():
    usage = read_asset("docs/usage.md")
    assert_concepts(usage, "TARGET_USERNAMES", "--targets target_user_1,target_user_2,target_user_3", "python3 instagram_monitor.py", "docker compose run --rm instagram_monitor", "docker compose run --rm --service-ports instagram_monitor", "misiektoja/instagram-monitor:latest")
    assert usage.count("-p 127.0.0.1:8000:8000") >= 3


# Verifies dashboard documentation includes the addresses and flags needed for container port publication
def test_dashboard_docs_cover_container_port_publication():
    view_modes = read_asset("docs/view-modes.md")
    troubleshooting = read_asset("docs/troubleshooting.md")
    compose = read_asset("docker-compose.yml")
    assert_concepts(view_modes, "0.0.0.0", "127.0.0.1", "--service-ports", "INSTAGRAM_MONITOR_WEB_DASHBOARD_PORT=9000")
    assert_concepts(troubleshooting, "0.0.0.0", "127.0.0.1:8000->8000/tcp", "8000/tcp")
    assert "${INSTAGRAM_MONITOR_WEB_DASHBOARD_PORT:-8000}" in compose


# Verifies configuration guidance retains the essential generation and target-precedence concepts
def test_configuration_docs_cover_generation_and_precedence_concepts():
    configuration = read_asset("docs/configuration.md")
    assert_concepts(configuration, "UTF-8", "backup", "defaults", "TARGET_USERNAMES", "--targets", "combined")


# Verifies quick-start guidance includes direct Docker variants for desktop and Linux hosts
def test_quick_start_covers_direct_docker_host_variants():
    quick_start = read_asset("docs/setup-and-first-run.md")
    assert_concepts(quick_start, "macOS", "Windows PowerShell", "Linux", "instagram_monitor_session", "/data")


# Verifies Firefox guidance retains every supported container host mount
def test_firefox_docs_cover_container_host_layouts():
    configuration = read_asset("docs/configuration.md")
    usage = read_asset("docs/usage.md")
    compose = read_asset("docker-compose.yml")
    firefox_section = markdown_section(usage, 3, "Import", "Firefox", "Container")
    mounts = ('-v "${HOME}/Library/Application Support/Firefox/Profiles:/home/instagram/.mozilla/firefox:ro"', '-v "$HOME/.mozilla/firefox:/home/instagram/.mozilla/firefox:ro"', '-v "$HOME/snap/firefox/common/.mozilla/firefox:/home/instagram/.mozilla/firefox:ro"', '-v "$HOME/.var/app/org.mozilla.firefox/.mozilla/firefox:/home/instagram/.mozilla/firefox:ro"', '-v "$env:APPDATA\\Mozilla\\Firefox:/home/instagram/.mozilla/firefox:ro"', '-v "%APPDATA%\\Mozilla\\Firefox:/home/instagram/.mozilla/firefox:ro"')
    for mount in mounts:
        assert firefox_section.count(mount) == 2
        assert mount in compose
    assert firefox_section.count("docker run --rm -it --init") == 6
    assert firefox_section.count("docker compose run --rm -v") == 6
    assert '-v "%cd%:/data:z"' in firefox_section
    assert_concepts(configuration, "Firefox", "Snap", "Flatpak")
    assert_concepts(firefox_section, "Doctor", ":z", ":Z")


# Verifies manual quick-start commands link both authentication modes
def test_quick_start_links_both_authentication_modes():
    quick_start = read_asset("docs/setup-and-first-run.md")
    assert "(configuration.md#no-login-mode-without-session-login)" in quick_start
    assert "(configuration.md#logged-in-mode-with-session-login)" in quick_start


# Verifies Compose smoke checks cannot replace the locally built image with a registry image
def test_container_smoke_checks_disable_pulls():
    workflow = read_asset(".github/workflows/tests.yml")
    assert workflow.count("docker compose -f docker-compose.yml run --rm --pull=never instagram_monitor") == 2


# Verifies Compose loads mounted secrets and attached examples suppress service prefixes
def test_compose_defaults_load_dotenv_and_suppress_attached_prefixes():
    compose = read_asset("docker-compose.yml")
    assert 'command: ["--env-file", "/data/.env"]' in compose
    assert "docker compose up --no-log-prefix" in compose
    for relative_path in ("docs/setup-and-first-run.md", "docs/installation.md", "docs/usage.md", "docs/view-modes.md"):
        assert "docker compose up --no-log-prefix" in read_asset(relative_path)
    assert "docker compose logs -f --no-log-prefix" in fenced_code_lines(read_asset("docs/usage.md"))


# Verifies historical feature links target their current documentation sections
def test_release_notes_use_current_documentation_links():
    release_notes = read_asset("RELEASE_NOTES.md")
    for fragment in ("view-modes/#terminal-dashboard-mode", "view-modes/#web-dashboard-mode", "usage/#webhook-notifications", "usage/#follower-churn-detection", "usage/#output-directory", "usage/#skipping-follow-changes", "anti-detection/#use-the-human-mode", "anti-detection/#use-the-jitter-mode", "configuration/#user-agent"):
        assert f"https://misiektoja.github.io/instagram_monitor/{fragment}" in release_notes
    assert "https://github.com/misiektoja/instagram_monitor#" not in release_notes


# Parses one repository YAML asset
def read_yaml_asset(relative_path: str):
    return yaml.safe_load(read_asset(relative_path))


# Returns the distribution names declared in one pyproject dependency list
def declared_dependency_names(block: str) -> set:
    return {re.split(r"[<>=!;\[ ]", entry.strip(), maxsplit=1)[0] for entry in re.findall(r'"([^"]+)"', block)}


# Verifies the repository keeps the community and licensing documents contributors are pointed to
def test_repository_governance_documents_exist():
    for relative_path in ("SECURITY.md", "SUPPORT.md", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md", "THIRD_PARTY_NOTICES.md", "LICENSE", ".github/pull_request_template.md"):
        asset = PROJECT_ROOT / relative_path
        assert asset.is_file(), relative_path
        assert asset.stat().st_size > 200, relative_path

    owners = read_asset(".github/CODEOWNERS")
    assert re.search(r"^\*\s+@\S+", owners, re.M)


# Verifies each issue template is a well-formed GitHub issue form, since a malformed one silently stops rendering
def test_issue_templates_are_valid_issue_forms():
    templates = sorted((PROJECT_ROOT / ".github" / "ISSUE_TEMPLATE").glob("*.yml"))
    assert {template.name for template in templates} == {"bug_report.yml", "config.yml", "feature_request.yml"}

    for template in templates:
        if template.name == "config.yml":
            continue
        form = yaml.safe_load(template.read_text(encoding="utf-8"))
        assert form["name"] and form["description"] and form["labels"], template.name
        for element in form["body"]:
            assert element["type"] in {"markdown", "input", "textarea", "dropdown", "checkboxes"}, template.name
            if element["type"] == "markdown":
                assert element["attributes"]["value"], template.name
                continue
            assert element["id"] and element["attributes"]["label"], template.name
            if element["type"] == "dropdown":
                assert len(element["attributes"]["options"]) >= 2, template.name


# Verifies the issue chooser routes vulnerabilities to private reporting instead of a public issue
def test_issue_chooser_routes_vulnerabilities_privately():
    config = read_yaml_asset(".github/ISSUE_TEMPLATE/config.yml")
    assert config["blank_issues_enabled"] is False
    urls = {link["url"] for link in config["contact_links"]}
    assert "https://github.com/misiektoja/instagram_monitor/security/advisories/new" in urls
    assert "https://misiektoja.github.io/instagram_monitor/" in urls

    bug_report = read_asset(".github/ISSUE_TEMPLATE/bug_report.yml")
    assert "SECURITY.md" in bug_report


# Verifies the security policy names the private channel and the secrets a report must never carry
def test_security_policy_documents_private_reporting():
    policy = read_asset("SECURITY.md")
    assert "https://github.com/misiektoja/instagram_monitor/security/advisories/new" in policy
    assert_concepts(policy, "Do not open a public issue", "session cookies", "webhook URLs", "Supported versions")


# Verifies contributing guidance states the checks CI actually enforces
def test_contributing_documents_the_enforced_checks():
    contributing = read_asset("CONTRIBUTING.md")
    commands = fenced_code_lines(contributing)
    assert "python -m pytest" in commands
    assert "mkdocs build --strict" in commands
    assert_concepts(contributing, "RELEASE_NOTES.md", "SECURITY.md", "GPL-3.0-or-later", "dev")


# Verifies every dependency source in the repository is watched for updates, not only actions and the base image
def test_dependabot_watches_every_dependency_source():
    updates = read_yaml_asset(".github/dependabot.yml")["updates"]
    watched = {(entry["package-ecosystem"], entry["directory"]) for entry in updates}
    assert ("github-actions", "/") in watched
    assert ("docker", "/") in watched
    assert ("pip", "/") in watched
    assert ("pip", "/docs") in watched
    assert all(entry["target-branch"] == "dev" for entry in updates)


# Verifies third-party notices stay in step with the dependencies the package actually declares
def test_third_party_notices_cover_every_declared_dependency():
    pyproject = read_asset("pyproject.toml")
    notices = read_asset("THIRD_PARTY_NOTICES.md")

    runtime_block = re.search(r"^dependencies = \[(.*?)^\]", pyproject, re.M | re.S)
    optional_block = re.search(r"^\[project\.optional-dependencies\](.*?)^\[", pyproject, re.M | re.S)
    assert runtime_block is not None and optional_block is not None

    declared = declared_dependency_names(runtime_block.group(1)) | declared_dependency_names(optional_block.group(1))
    # Build backends are covered as a group rather than named one by one
    declared -= {"build", "setuptools", "wheel"}

    missing = sorted(name for name in declared if name.casefold() not in notices.casefold())
    assert missing == []
    assert_concepts(notices, "GPL-3.0-or-later", "python:3.14-slim-bookworm", "instaloader")


# Verifies the code scanning and supply chain workflows stay present and keep analyzing this project's language
def test_security_workflows_cover_code_and_supply_chain():
    workflow_directory = PROJECT_ROOT / ".github" / "workflows"
    for name in ("supply-chain.yml", "codeql.yml", "scorecard.yml"):
        assert (workflow_directory / name).is_file(), name

    codeql = read_yaml_asset(".github/workflows/codeql.yml")
    initialize = next(step for step in codeql["jobs"]["analyze"]["steps"] if "codeql-action/init" in step.get("uses", ""))
    assert initialize["with"]["languages"] == "python"
    assert codeql["jobs"]["analyze"]["permissions"]["security-events"] == "write"

    # Publishing the result is what keeps the README badge current, so it must not be silently switched off
    scorecard = read_yaml_asset(".github/workflows/scorecard.yml")
    analysis = next(step for step in scorecard["jobs"]["analysis"]["steps"] if "scorecard-action" in step.get("uses", ""))
    assert analysis["with"]["publish_results"] is True

    supply_chain = read_yaml_asset(".github/workflows/supply-chain.yml")
    assert {"gitleaks", "pip-audit", "sbom", "image-scan"} <= set(supply_chain["jobs"])


# Verifies the citation metadata GitHub renders stays parseable and describes this project
def test_citation_metadata_describes_this_project():
    citation = read_yaml_asset("CITATION.cff")
    assert citation["cff-version"] == "1.2.0"
    assert citation["type"] == "software"
    assert citation["title"] == "instagram_monitor"
    assert citation["message"]
    assert citation["license"] == "GPL-3.0-or-later"
    assert citation["repository-code"] == "https://github.com/misiektoja/instagram_monitor"
    assert citation["date-released"].isoformat() == str(citation["date-released"])

    author = citation["authors"][0]
    assert author["given-names"] and author["family-names"] and author["alias"] == "misiektoja"


# Verifies the sponsor button keeps a target, since an empty file hides it without failing any check
def test_funding_configuration_declares_a_sponsor_target():
    funding = read_yaml_asset(".github/FUNDING.yml")
    assert funding["github"] == "misiektoja"
    assert funding["buy_me_a_coffee"] == "misiektoja"


# Verifies the shared editor settings still declare the style the repository is written in
def test_editor_configuration_declares_the_repository_style():
    settings = configparser.ConfigParser()
    settings.read_string("[editorconfig]\n" + read_asset(".editorconfig"))

    assert settings["editorconfig"]["root"] == "true"
    assert settings["*"]["charset"] == "utf-8"
    assert settings["*"]["end_of_line"] == "lf"
    assert settings["*"]["indent_style"] == "space"
    assert settings["*"]["indent_size"] == "4"
    assert settings["*"]["insert_final_newline"] == "true"
    assert settings["*"]["trim_trailing_whitespace"] == "true"
    assert settings["*.py"]["indent_size"] == "4"
    assert settings["*.html"]["indent_size"] == "4"
    assert settings["*.{yml,yaml}"]["indent_size"] == "2"
    # Two trailing spaces are a Markdown line break, so they must stay exempt from trimming
    assert settings["*.md"]["trim_trailing_whitespace"] == "false"


# Verifies tracked text files obey those whitespace rules, since an editor setting only warns on the machine that has it
def test_tracked_text_files_obey_the_declared_whitespace_rules():
    listing = subprocess.run(["git", "ls-files"], cwd=PROJECT_ROOT, check=False, capture_output=True, text=True)
    if listing.returncode != 0:
        pytest.skip("not a git checkout")

    offenders = []
    for name in listing.stdout.split():
        asset = PROJECT_ROOT / name
        if not asset.is_file() or asset.suffix.casefold() in {".png", ".jpg", ".gif"}:
            continue
        content = asset.read_bytes()
        if b"\r\n" in content:
            offenders.append(f"{name}: CRLF line ending")
        if content and not content.endswith(b"\n"):
            offenders.append(f"{name}: missing final newline")
        # LICENSE is verbatim upstream text and Markdown keeps meaningful trailing spaces
        if name != "LICENSE" and asset.suffix.casefold() != ".md" and re.search(rb"[ \t]+\n", content):
            offenders.append(f"{name}: trailing whitespace")
    assert offenders == []


# Verifies the support document routes each request to a channel that exists
def test_support_document_routes_every_request_type():
    support = read_asset("SUPPORT.md")
    for destination in ("https://github.com/misiektoja/instagram_monitor/discussions", "https://github.com/misiektoja/instagram_monitor/security/advisories/new", "https://github.com/misiektoja/instagram_monitor/issues/new?template=bug_report.yml", "https://github.com/misiektoja/instagram_monitor/issues/new?template=feature_request.yml"):
        assert destination in support
    assert "instagram_monitor --doctor" in fenced_code_lines(support)
    assert_concepts(support, "session cookies", "webhook URLs", "--debug")


# Verifies Git normalizes line endings, since one CRLF commit from a Windows contributor rewrites whole files
def test_line_ending_policy_is_declared():
    attributes = read_asset(".gitattributes")
    assert "* text=auto eol=lf" in attributes
    for pattern in ("*.png binary", "*.jpg binary", "*.gif binary"):
        assert pattern in attributes


# Verifies the optional local hooks run the same linter version CI installs, or a clean commit still fails CI
def test_local_hooks_match_the_pinned_linter():
    pyproject = read_asset("pyproject.toml")
    pinned = re.search(r'lint = \["ruff==([^"]+)"\]', pyproject)
    assert pinned is not None

    hooks = read_yaml_asset(".pre-commit-config.yaml")["repos"]
    ruff_hook = next(entry for entry in hooks if "ruff-pre-commit" in entry["repo"])
    assert ruff_hook["rev"] == f"v{pinned.group(1)}"

    workflow = read_yaml_asset(".github/workflows/tests.yml")
    lint_steps = workflow["jobs"]["lint"]["steps"]
    assert any("ruff check" in step.get("run", "") for step in lint_steps)


# Verifies published archives stay verifiable, since an unsigned download cannot be told apart from a tampered one
def test_release_archives_ship_checksums_and_provenance():
    workflow = read_yaml_asset(".github/workflows/release-assets.yml")
    job = workflow["jobs"]["build-and-upload-assets"]
    assert job["permissions"]["attestations"] == "write"
    assert job["permissions"]["id-token"] == "write"

    assert any("sha256sum" in step.get("run", "") for step in job["steps"])
    assert any("attest-build-provenance" in step.get("uses", "") for step in job["steps"])

    attest = next(step for step in job["steps"] if "attest-build-provenance" in step.get("uses", ""))
    stage = next(step for step in job["steps"] if ".intoto.jsonl" in step.get("run", ""))
    assert f"steps.{attest['id']}.outputs.bundle-path" in stage["env"]["BUNDLE_PATH"]

    upload = next(step for step in job["steps"] if "action-gh-release" in step.get("uses", ""))
    assert "_SHA256SUMS.txt" in upload["with"]["files"]
    # Offline verifiers need the bundle as an asset, since the attestations API may be unreachable
    assert ".intoto.jsonl" in upload["with"]["files"]
