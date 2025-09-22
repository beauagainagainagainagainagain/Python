"""Tests for the :mod:`scripts.virtual_container` module."""

from __future__ import annotations

import subprocess
import sys
import os
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.virtual_container import (
    VirtualContainer,
    main,
    parse_env_assignments,
)


def test_virtual_container_create_and_cleanup(tmp_path: Path) -> None:
    container = VirtualContainer.create(base_dir=str(tmp_path), env={"FOO": "bar"})
    try:
        assert container.root.exists()
        assert container.cwd == container.root
        assert container.env["FOO"] == "bar"
    finally:
        container.cleanup()
    assert not container.root.exists()


def test_virtual_container_run_sequence_command(tmp_path: Path) -> None:
    container = VirtualContainer.create(base_dir=str(tmp_path))
    try:
        command = [
            sys.executable,
            "-c",
            "import os; print(os.getcwd())",
        ]
        result = container.run(command, check=True)
        assert result.stdout.strip() == str(container.cwd)
    finally:
        container.cleanup()


def test_virtual_container_run_string_command(tmp_path: Path) -> None:
    container = VirtualContainer.create(base_dir=str(tmp_path))
    try:
        result = container.run("echo hello", check=True)
        assert result.stdout.strip() == "hello"
    finally:
        container.cleanup()


def test_change_directory_and_resolve(tmp_path: Path) -> None:
    container = VirtualContainer.create(base_dir=str(tmp_path))
    try:
        subdir = container.root / "sub"
        subdir.mkdir()
        container.change_directory("sub")
        assert container.cwd == subdir
        assert container.format_path() == "/sub"
        assert container.resolve_path("..") == container.root
        assert container.change_directory("..") == container.root
        assert container.resolve_path("/..") == container.root
        outside = tmp_path / "outside"
        outside.mkdir()
        symlink = container.root / "link"
        if hasattr(os, "symlink"):
            try:
                symlink.symlink_to(outside, target_is_directory=True)
            except (OSError, NotImplementedError):
                pass
            else:
                with pytest.raises(ValueError):
                    container.resolve_path("link")
        assert container.resolve_path("/") == container.root
        assert container.resolve_path("../..") == container.root
        with pytest.raises(FileNotFoundError):
            container.change_directory("missing")
        file_path = container.root / "file.txt"
        file_path.write_text("data")
        with pytest.raises(NotADirectoryError):
            container.resolve_path("/file.txt")
    finally:
        container.cleanup()


def test_run_with_check_raises_on_failure(tmp_path: Path) -> None:
    container = VirtualContainer.create(base_dir=str(tmp_path))
    try:
        with pytest.raises(subprocess.CalledProcessError):
            container.run(
                [sys.executable, "-c", "import sys; sys.exit(3)"],
                check=True,
            )
    finally:
        container.cleanup()


def test_parse_env_assignments_valid() -> None:
    result = parse_env_assignments(["A=1", "B=value"])
    assert result == {"A": "1", "B": "value"}


@pytest.mark.parametrize("assignment", ["invalid", "=value", " =value"])
def test_parse_env_assignments_invalid(assignment: str) -> None:
    with pytest.raises(ValueError):
        parse_env_assignments([assignment])


def test_main_executes_command_and_cleans(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    base_dir = tmp_path / "base"
    exit_code = main(
        [
            "--base-dir",
            str(base_dir),
            "--",
            sys.executable,
            "-c",
            "print('hi')",
        ]
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    assert captured.out == "hi\n"
    assert captured.err == ""
    assert base_dir.exists()
    assert list(base_dir.iterdir()) == []


def test_main_propagates_exit_code(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    base_dir = tmp_path / "base"
    exit_code = main(
        [
            "--base-dir",
            str(base_dir),
            "--",
            sys.executable,
            "-c",
            "import sys; sys.stderr.write('err'); sys.exit(5)",
        ]
    )
    assert exit_code == 5
    captured = capsys.readouterr()
    assert captured.err == "err"
    assert captured.out == ""
    assert list(base_dir.iterdir()) == []


def test_main_injects_environment(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    base_dir = tmp_path / "base"
    exit_code = main(
        [
            "--base-dir",
            str(base_dir),
            "--env",
            "SPECIAL=VALUE",
            "--",
            sys.executable,
            "-c",
            "import os; print(os.environ['SPECIAL'])",
        ]
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    assert captured.out == "VALUE\n"
    assert captured.err == ""
    assert list(base_dir.iterdir()) == []

