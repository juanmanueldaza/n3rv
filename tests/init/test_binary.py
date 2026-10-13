"""Tests for n3rv binary resolution in generated files."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from n3rv.init.binary import resolve_n3rv_binary


def _make_executable(path: Path) -> Path:
    path.write_text("#!/bin/sh\nexit 0\n")
    path.chmod(0o755)
    return path


def test_resolve_prefers_binary_next_to_interpreter(tmp_path, monkeypatch) -> None:
    """The interpreter's sibling wins over whatever PATH resolves to."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    interpreter = bindir / "python3"
    _make_executable(interpreter)
    sibling = _make_executable(bindir / "n3rv")

    monkeypatch.setattr(sys, "executable", str(interpreter))
    monkeypatch.setattr("shutil.which", lambda name: "/somewhere/else/n3rv")

    assert resolve_n3rv_binary() == str(sibling)


def test_resolve_falls_back_to_path(tmp_path, monkeypatch) -> None:
    """With no sibling, PATH is still consulted."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    interpreter = bindir / "python3"
    _make_executable(interpreter)

    monkeypatch.setattr(sys, "executable", str(interpreter))
    monkeypatch.setattr("shutil.which", lambda name: "/path/resolved/n3rv")

    assert resolve_n3rv_binary() == "/path/resolved/n3rv"


def test_resolve_ignores_non_executable_sibling(tmp_path, monkeypatch) -> None:
    """A non-executable file named n3rv next to the interpreter is not used."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    interpreter = bindir / "python3"
    _make_executable(interpreter)
    (bindir / "n3rv").write_text("not executable")

    monkeypatch.setattr(sys, "executable", str(interpreter))
    monkeypatch.setattr("shutil.which", lambda name: "/path/resolved/n3rv")

    assert resolve_n3rv_binary() == "/path/resolved/n3rv"


def test_resolve_returns_none_when_absent(tmp_path, monkeypatch) -> None:
    bindir = tmp_path / "bin"
    bindir.mkdir()
    interpreter = bindir / "python3"
    _make_executable(interpreter)

    monkeypatch.setattr(sys, "executable", str(interpreter))
    monkeypatch.setattr("shutil.which", lambda name: None)

    assert resolve_n3rv_binary() is None


@pytest.mark.parametrize("missing", [True, False])
def test_resolve_handles_missing_interpreter_dir(tmp_path, monkeypatch, missing: bool) -> None:
    """A sys.executable whose directory does not exist must not raise."""
    exe = tmp_path / ("gone/python3" if missing else "bin/python3")
    if not missing:
        exe.parent.mkdir()
        _make_executable(exe)

    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setattr("shutil.which", lambda name: "/path/resolved/n3rv")

    assert resolve_n3rv_binary() == "/path/resolved/n3rv"
