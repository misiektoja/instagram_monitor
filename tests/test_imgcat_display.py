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
