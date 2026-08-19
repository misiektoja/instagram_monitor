"""Tests for the built wheel and its installed console command."""

import os
import re
import site
import subprocess
import sys
import tempfile
import venv
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = PROJECT_ROOT / "local" / "test_artifacts"


# Creates one disposable package test directory below the project local directory
@pytest.fixture(scope="module")
def package_test_directory() -> Iterator[Path]:
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ARTIFACT_ROOT) as directory_name:
        yield Path(directory_name)


# Builds the project wheel once for package and installed-CLI tests
@pytest.fixture(scope="module")
def built_wheel(package_test_directory: Path) -> Path:
    wheel_directory = package_test_directory / "dist"
    result = subprocess.run([sys.executable, "-m", "build", "--wheel", "--no-isolation", "--outdir", str(wheel_directory), str(PROJECT_ROOT)], check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    wheels = list(wheel_directory.glob("*.whl"))
    assert len(wheels) == 1
    return wheels[0]


# Installs the built wheel into an isolated command environment
@pytest.fixture(scope="module")
def installed_package(package_test_directory: Path, built_wheel: Path) -> tuple[Path, Path]:
    environment_directory = package_test_directory / "venv"
    venv.EnvBuilder(with_pip=True, system_site_packages=True).create(environment_directory)
    python_executable = environment_directory / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    result = subprocess.run([str(python_executable), "-m", "pip", "install", "--no-deps", str(built_wheel)], check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    console_executable = environment_directory / ("Scripts/instagram_monitor.exe" if os.name == "nt" else "bin/instagram_monitor")
    assert console_executable.is_file()
    return python_executable, console_executable


# Runs the installed console command from outside the source tree
def run_installed_console(package_test_directory: Path, installed_package: tuple[Path, Path], *arguments: str) -> subprocess.CompletedProcess[str]:
    _python_executable, console_executable = installed_package
    working_directory = package_test_directory / "working"
    working_directory.mkdir(exist_ok=True)
    environment = installed_environment(installed_package)
    return subprocess.run([str(console_executable), *arguments], cwd=working_directory, env=environment, check=False, capture_output=True, text=True)


# Builds an import path that prefers the tested wheel while reusing installed dependencies
def installed_environment(installed_package: tuple[Path, Path]) -> dict[str, str]:
    python_executable, _console_executable = installed_package
    environment_directory = python_executable.parent.parent
    package_directory = environment_directory / ("Lib/site-packages" if os.name == "nt" else f"lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages")
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join([str(package_directory), *site.getsitepackages()])
    return environment


# Verifies the wheel carries its console entry point and runtime assets
def test_wheel_contains_entry_point_and_runtime_assets(built_wheel: Path):
    with zipfile.ZipFile(built_wheel) as wheel_archive:
        names = wheel_archive.namelist()
        entry_points_name = next(name for name in names if name.endswith(".dist-info/entry_points.txt"))
        entry_points = wheel_archive.read(entry_points_name).decode("utf-8")
    assert "instagram_monitor.py" in names
    assert any(name.endswith("instagram_monitor_data/templates/index.html") for name in names)
    assert any(name.endswith("instagram_monitor_data/instagram_profile_pic_empty.jpg") for name in names)
    assert "instagram_monitor = instagram_monitor:main" in entry_points


# Verifies the installed console exposes version and complete argument help
def test_installed_console_version_and_help(package_test_directory: Path, installed_package: tuple[Path, Path]):
    python_executable, _console_executable = installed_package
    environment = installed_environment(installed_package)
    import_result = subprocess.run([str(python_executable), "-c", "import instagram_monitor; print(instagram_monitor.__file__)"], cwd=package_test_directory, env=environment, check=False, capture_output=True, text=True)
    version_result = run_installed_console(package_test_directory, installed_package, "--version")
    help_result = run_installed_console(package_test_directory, installed_package, "--help")
    assert import_result.returncode == 0, import_result.stdout + import_result.stderr
    assert str(package_test_directory / "venv") in import_result.stdout
    assert version_result.returncode == 0
    assert re.search(r"^instagram_monitor(?:\.py)? v\d", version_result.stdout)
    assert help_result.returncode == 0
    for option in ("--setup", "--doctor", "--generate-config", "--set-webhook-url", "--web-dashboard", "--webhook-provider"):
        assert option in help_result.stdout


# Verifies the installed console can generate a valid portable configuration file
def test_installed_console_generates_valid_config(package_test_directory: Path, installed_package: tuple[Path, Path]):
    destination = package_test_directory / "working" / "generated.conf"
    result = run_installed_console(package_test_directory, installed_package, "--generate-config", str(destination))
    assert result.returncode == 0, result.stdout + result.stderr
    generated = destination.read_text(encoding="utf-8")
    compile(generated, str(destination), "exec")
    assert "TARGET_USERNAMES" in generated
    assert "INSTA_CHECK_INTERVAL" in generated


class TestWorkflowSupplyChain:
    # Every third-party action is pinned to a commit, so a moved tag cannot change what runs with our secrets
    def test_actions_are_pinned_to_commit_shas(self):
        unpinned = []
        for workflow in sorted((PROJECT_ROOT / ".github" / "workflows").glob("*.yml")):
            for match in re.finditer(r"uses:\s*(\S+)", workflow.read_text(encoding="utf-8")):
                reference = match.group(1)
                if reference.startswith("./"):
                    continue
                action, _, ref = reference.partition("@")
                if not re.fullmatch(r"[0-9a-f]{40}", ref):
                    unpinned.append(f"{workflow.name}: {reference}")
        assert unpinned == []

    # Each pin records the human-readable version so updates stay reviewable
    def test_pinned_actions_carry_a_version_comment(self):
        missing = []
        for workflow in sorted((PROJECT_ROOT / ".github" / "workflows").glob("*.yml")):
            for line in workflow.read_text(encoding="utf-8").splitlines():
                if "uses:" in line and "@" in line and "./" not in line and not re.search(r"#\s*v?\d", line):
                    missing.append(f"{workflow.name}: {line.strip()}")
        assert missing == []

    # Event and input values never reach a shell directly, which would allow script injection
    def test_run_steps_do_not_interpolate_event_values(self):
        offenders = []
        for workflow in sorted((PROJECT_ROOT / ".github" / "workflows").glob("*.yml")):
            for block in re.findall(r"run: \|(.*?)(?=\n      [-a-zA-Z]|\Z)", workflow.read_text(encoding="utf-8"), re.S):
                for line in block.splitlines():
                    if "${{" in line:
                        offenders.append(f"{workflow.name}: {line.strip()}")
        assert offenders == []
