#!/usr/bin/env python3
"""Utility to spin up a lightweight virtual container for running commands.

The virtual container concept implemented here provides an isolated working
directory (with environment settings) for executing shell commands.  It is
aimed at cases where a throwaway sandbox is preferred to running commands
directly in the repository tree.  The tool supports both interactive and
one-off command execution modes.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Mapping, MutableMapping, Sequence


@dataclass
class VirtualContainer:
    """Manage a throwaway workspace for executing shell commands.

    Parameters
    ----------
    root:
        The root directory that represents ``/`` within the virtual container.
    cwd:
        The current working directory inside the container.  Defaults to the
        ``root``.
    env:
        A copy of the environment variables that should be supplied to spawned
        commands.
    """

    root: Path
    cwd: Path
    env: MutableMapping[str, str]

    @classmethod
    def create(
        cls,
        *,
        base_dir: str | None = None,
        env: Mapping[str, str] | None = None,
    ) -> "VirtualContainer":
        """Instantiate a new virtual container."""

        if base_dir is not None:
            Path(base_dir).mkdir(parents=True, exist_ok=True)
        root_dir = Path(
            tempfile.mkdtemp(prefix="virtual_container_", dir=base_dir)
        ).resolve()
        env_vars: Dict[str, str] = dict(os.environ)
        if env:
            env_vars.update(env)
        return cls(root=root_dir, cwd=root_dir, env=env_vars)

    def run(
        self,
        command: Sequence[str] | str,
        *,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        """Run a command inside the container and return the completed process."""

        if isinstance(command, str):
            exec_command = command
            shell = True
        else:
            exec_command = list(command)
            shell = False
        completed = subprocess.run(
            exec_command,
            cwd=str(self.cwd),
            env=self.env,
            capture_output=True,
            text=True,
            shell=shell,
        )
        if check and completed.returncode != 0:
            raise subprocess.CalledProcessError(
                completed.returncode,
                exec_command,
                output=completed.stdout,
                stderr=completed.stderr,
            )
        return completed

    def cleanup(self) -> None:
        """Remove the virtual container directory tree."""

        if self.root.exists():
            shutil.rmtree(self.root)

    def format_path(self, path: Path | None = None) -> str:
        """Return a container-relative representation of *path*."""

        target = path or self.cwd
        if target == self.root:
            return "/"
        return f"/{target.relative_to(self.root)}"

    def resolve_path(self, raw_path: str) -> Path:
        """Resolve *raw_path* to a directory within the container.

        Absolute paths are interpreted relative to the container root in the
        same way they would be inside a real container.
        """

        if not raw_path:
            raise ValueError("path cannot be empty")
        path_obj = Path(raw_path)
        if path_obj.is_absolute():
            normalized = self.root.joinpath(*path_obj.parts[1:])
        else:
            normalized = self.cwd / path_obj
        resolved = normalized.resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:  # pragma: no cover - safety guard
            raise ValueError("cannot leave the container root") from exc
        if not resolved.exists():
            raise FileNotFoundError(raw_path)
        if not resolved.is_dir():
            raise NotADirectoryError(raw_path)
        return resolved

    def change_directory(self, raw_path: str) -> Path:
        """Change the container's working directory."""

        target = self.resolve_path(raw_path)
        self.cwd = target
        return self.cwd


def parse_env_assignments(assignments: Iterable[str]) -> Dict[str, str]:
    """Parse ``KEY=VALUE`` assignments supplied on the command line."""

    parsed: Dict[str, str] = {}
    for item in assignments:
        if "=" not in item:
            raise ValueError(f"invalid environment assignment: '{item}'")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError("environment variable name cannot be empty")
        parsed[key] = value
    return parsed


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line argument parser for the script."""

    parser = argparse.ArgumentParser(
        description=(
            "Create a lightweight virtual container directory and execute commands "
            "inside it."
        )
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help=(
            "Command to execute inside the container.  When omitted an interactive "
            "prompt is started."
        ),
    )
    parser.add_argument(
        "-e",
        "--env",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Environment variables to inject into the container.",
    )
    parser.add_argument(
        "--base-dir",
        type=str,
        default=None,
        help="Directory where container instances should be created.",
    )
    parser.add_argument(
        "--persist",
        action="store_true",
        help="Do not delete the container directory when the program exits.",
    )
    return parser


def container_prompt(container: VirtualContainer) -> str:
    """Return a shell-like prompt for the interactive session."""

    return f"{container.format_path()}$ "


def interactive_loop(container: VirtualContainer) -> int:
    """Run an interactive terminal loop inside the container."""

    print("Starting virtual container interactive session.")
    print("Type 'exit' or 'quit' (or press Ctrl-D) to leave.")
    while True:
        try:
            command = input(container_prompt(container)).strip()
        except EOFError:
            print()
            break
        if not command:
            continue
        if command in {"exit", "quit"}:
            break
        if command == "cd":
            container.change_directory("/")
            continue
        if command.startswith("cd "):
            target = command[3:].strip() or "/"
            try:
                container.change_directory(target)
            except OSError as exc:
                print(f"cd: {exc}")
            continue
        result = container.run(command)
        if result.stdout:
            sys.stdout.write(result.stdout)
        if result.stderr:
            sys.stderr.write(result.stderr)
        print(f"[exit {result.returncode}]")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        env_vars = parse_env_assignments(args.env)
    except ValueError as exc:
        parser.error(str(exc))
    container = VirtualContainer.create(base_dir=args.base_dir, env=env_vars)
    exit_code = 0
    try:
        if args.command:
            command = args.command
            if command and command[0] == "--":
                command = command[1:]
            if not command:
                parser.error("a command must follow '--'")
            if len(command) == 1:
                command = command[0]
            result = container.run(command)
            if result.stdout:
                sys.stdout.write(result.stdout)
            if result.stderr:
                sys.stderr.write(result.stderr)
            exit_code = result.returncode
        else:
            exit_code = interactive_loop(container)
    finally:
        if args.persist:
            print(
                "Container preserved at",
                container.root,
            )
        else:
            container.cleanup()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
