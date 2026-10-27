"""Offline tests for terminal image display argument handling."""

import pytest


class TestDisplayImageInTerminal:
    # The viewer is launched with an argument vector so shell metacharacters in a path stay inert
    @pytest.mark.parametrize("image_file", ["/tmp/pic.jpg", "/tmp/$(touch marker)/pic.jpg", "/tmp/a;b`id`.jpg", "/tmp/a b&c.jpg"])
    def test_paths_are_passed_as_arguments_without_a_shell(self, im_module, monkeypatch, image_file):
        runs = []
        monkeypatch.setattr(im_module, "imgcat_exe", "/usr/local/bin/imgcat")
        monkeypatch.setattr(im_module.subprocess, "run", lambda *args, **kwargs: runs.append((args, kwargs)))

        im_module.display_image_in_terminal(image_file)

        assert runs[0][0][0] == ["/usr/local/bin/imgcat", image_file]
        assert "shell" not in runs[0][1]

    # Nothing is launched when no viewer is configured
    def test_missing_viewer_runs_nothing(self, im_module, monkeypatch):
        runs = []
        monkeypatch.setattr(im_module, "imgcat_exe", "")
        monkeypatch.setattr(im_module.subprocess, "run", lambda *args, **kwargs: runs.append(args))

        im_module.display_image_in_terminal("/tmp/pic.jpg")

        assert runs == []

    # Spacing around the image is emitted by the tool rather than by a shell echo
    @pytest.mark.parametrize("before,after,expected", [(True, False, ["\n", "run"]), (False, True, ["run", "\n"]), (False, False, ["run"])])
    def test_blank_lines_surround_the_image_as_requested(self, im_module, monkeypatch, capsys, before, after, expected):
        order = []
        monkeypatch.setattr(im_module, "imgcat_exe", "/usr/local/bin/imgcat")
        monkeypatch.setattr(im_module.subprocess, "run", lambda *args, **kwargs: order.append("run"))
        monkeypatch.setattr("builtins.print", lambda *args, **kwargs: order.append("\n"))

        im_module.display_image_in_terminal("/tmp/pic.jpg", blank_line_before=before, blank_line_after=after)

        assert order == expected


class TestResolveExecutable:
    # A bare command name is looked up on PATH and never taken from the current directory
    def test_a_bare_name_is_not_taken_from_the_current_directory(self, im_module, monkeypatch, tmp_path):
        planted = tmp_path / "imgcat"
        planted.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        planted.chmod(0o755)
        empty_path_dir = tmp_path / "empty-path"
        empty_path_dir.mkdir()
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("PATH", str(empty_path_dir))

        with pytest.raises(FileNotFoundError):
            im_module.resolve_executable("imgcat")

    # A PATH entry that is the current directory does not make a planted program acceptable either
    def test_a_bare_name_found_through_path_in_the_current_directory_is_refused(self, im_module, monkeypatch, tmp_path):
        planted = tmp_path / "imgcat"
        planted.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        planted.chmod(0o755)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("PATH", str(tmp_path))

        with pytest.raises(FileNotFoundError):
            im_module.resolve_executable("imgcat")

    # A bare name installed on PATH resolves to its full path
    def test_a_bare_name_on_path_resolves_to_its_full_path(self, im_module, monkeypatch, tmp_path):
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        installed = bin_dir / "imgcat"
        installed.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        installed.chmod(0o755)
        work = tmp_path / "work"
        work.mkdir()
        monkeypatch.chdir(work)
        monkeypatch.setenv("PATH", str(bin_dir))

        assert im_module.resolve_executable("imgcat") == str(installed)

    # A path must name an executable file, and a home-relative path is expanded
    def test_a_path_must_name_an_executable_file(self, im_module, monkeypatch, tmp_path):
        program = tmp_path / "viewer.sh"
        program.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        program.chmod(0o755)
        plain = tmp_path / "notes.txt"
        plain.write_text("not a program\n", encoding="utf-8")
        monkeypatch.setenv("HOME", str(tmp_path))

        assert im_module.resolve_executable(str(program)) == str(program)
        assert im_module.resolve_executable("~/viewer.sh") == str(program)
        with pytest.raises(FileNotFoundError):
            im_module.resolve_executable(str(plain))
        with pytest.raises(FileNotFoundError):
            im_module.resolve_executable(str(tmp_path / "missing.sh"))

    # Only values with a directory part or a home prefix count as paths
    @pytest.mark.parametrize("value,expected", [("imgcat", False), ("imgcat.exe", False), ("", False), ("/usr/local/bin/imgcat", True), ("./imgcat", True), ("~/bin/imgcat", True), ("bin/imgcat", True)])
    def test_path_values_are_told_apart_from_command_names(self, im_module, value, expected):
        assert im_module.names_program_by_path(value) is expected


# Writes an executable shell script that records nothing and exits cleanly
def _write_program(path):
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(0o755)
    return path


# Runs the CLI up to the point where the viewer has been resolved and returns the resolved value
def _resolved_viewer_after_startup(im_module, monkeypatch, arguments):
    observed = []

    def stop_after_resolution(*args, **kwargs):
        observed.append(im_module.imgcat_exe)
        raise SystemExit(99)

    monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py", "target.user", "--env-file", "none", "--no-color"] + list(arguments))
    monkeypatch.setattr(im_module, "CLI_CONFIG_PATH", None)
    monkeypatch.setattr(im_module, "CONFIG_DISCOVERED_IN_CWD", False)
    monkeypatch.setattr(im_module, "IMGCAT_PATH", "")
    monkeypatch.setattr(im_module, "imgcat_exe", "")
    monkeypatch.setattr(im_module, "clear_screen", lambda *args, **kwargs: None)
    monkeypatch.setattr(im_module, "check_internet", lambda: True)
    monkeypatch.setattr(im_module, "resolve_truncate_chars", stop_after_resolution)

    with pytest.raises(SystemExit) as exc:
        im_module.run_main()

    assert exc.value.code == 99
    return observed[0]


class TestViewerPathTrust:
    # A config file found in the current directory cannot hand the tool a program to run
    def test_a_path_from_a_config_found_in_the_current_directory_is_ignored(self, im_module, monkeypatch, tmp_path, capsys):
        program = _write_program(tmp_path / "planted-viewer.sh")
        (tmp_path / "instagram_monitor.conf").write_text(f'IMGCAT_PATH = "{program}"\n', encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        resolved = _resolved_viewer_after_startup(im_module, monkeypatch, [])

        assert resolved == ""
        assert im_module.CONFIG_DISCOVERED_IN_CWD is True
        output = capsys.readouterr().out
        assert f"IMGCAT_PATH '{program}' is ignored" in output
        assert "found in the current directory" in output
        assert "--config-file" in output

    # The same file named with --config-file is the operator's choice, so the path is used
    def test_the_same_path_is_used_when_the_file_is_named(self, im_module, monkeypatch, tmp_path):
        program = _write_program(tmp_path / "chosen-viewer.sh")
        (tmp_path / "instagram_monitor.conf").write_text(f'IMGCAT_PATH = "{program}"\n', encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        resolved = _resolved_viewer_after_startup(im_module, monkeypatch, ["--config-file", "instagram_monitor.conf"])

        assert resolved == str(program)
        assert im_module.CONFIG_DISCOVERED_IN_CWD is False

    # A command name from a discovered config is still looked up on PATH
    def test_a_command_name_from_a_discovered_config_is_looked_up_on_path(self, im_module, monkeypatch, tmp_path):
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        installed = _write_program(bin_dir / "viewer-on-path")
        _write_program(tmp_path / "viewer-on-path")
        (tmp_path / "instagram_monitor.conf").write_text('IMGCAT_PATH = "viewer-on-path"\n', encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("PATH", str(bin_dir))

        resolved = _resolved_viewer_after_startup(im_module, monkeypatch, [])

        assert resolved == str(installed)

    # A command name that only exists in the current directory is not run
    def test_a_command_name_present_only_in_the_current_directory_is_not_resolved(self, im_module, monkeypatch, tmp_path):
        _write_program(tmp_path / "imgcat")
        empty_path_dir = tmp_path / "empty-path"
        empty_path_dir.mkdir()
        (tmp_path / "instagram_monitor.conf").write_text('IMGCAT_PATH = "imgcat"\n', encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("PATH", str(empty_path_dir))

        assert _resolved_viewer_after_startup(im_module, monkeypatch, []) == ""

    # Doctor reports the ignored path so a silent "Disabled" row has an explanation
    def test_doctor_reports_a_program_path_from_a_discovered_config(self, im_module, monkeypatch, tmp_path):
        config = tmp_path / "instagram_monitor.conf"
        config.write_text('IMGCAT_PATH = "/opt/viewer/imgcat"\n', encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(im_module, "CLI_CONFIG_PATH", None)
        monkeypatch.setattr(im_module, "CONFIG_DISCOVERED_IN_CWD", True)
        monkeypatch.setattr(im_module, "IMGCAT_PATH", "/opt/viewer/imgcat")

        checks = im_module.doctor_check_configuration([])
        warning = next(check for check in checks if check.label.startswith("IMGCAT_PATH names a program by path"))

        assert warning.status == "WARN"
        assert "/opt/viewer/imgcat" in warning.detail
        assert "--config-file" in warning.advice.fix
        assert warning.advice.fix.endswith(f"\nGuide: {im_module.CONFIG_GUIDE_URL}")

    # Doctor stays quiet for a command name and for a path from a file the operator named
    @pytest.mark.parametrize("discovered,value", [(True, "imgcat"), (False, "/opt/viewer/imgcat")])
    def test_doctor_stays_quiet_for_trusted_viewer_settings(self, im_module, monkeypatch, tmp_path, discovered, value):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(im_module, "CLI_CONFIG_PATH", None)
        monkeypatch.setattr(im_module, "CONFIG_DISCOVERED_IN_CWD", discovered)
        monkeypatch.setattr(im_module, "IMGCAT_PATH", value)

        checks = im_module.doctor_check_configuration([])

        assert not any(check.label.startswith("IMGCAT_PATH names a program by path") for check in checks)
