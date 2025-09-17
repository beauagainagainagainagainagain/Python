"""Install the Python dependencies required by the BlenderGIS add-on.

This helper focuses on the packages that BlenderGIS relies on when it runs
inside Blender's bundled Python interpreter.  It can be executed with the
current interpreter or pointed at Blender's python binary via ``--python``.

Example usage::

    python scripts/install_blendergis_dependencies.py --python /path/to/blender/python

The script keeps the command output verbose so that users can audit the
installation steps and diagnose issues (for example when GDAL requires
additional system libraries).
"""
from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence


@dataclass(frozen=True)
class Package:
    """Descriptor for a Python package that BlenderGIS depends on."""

    name: str
    reason: str
    optional: bool = False


CORE_PACKAGES: Sequence[Package] = (
    Package(
        name="numpy",
        reason="Required for raster manipulation and array math used throughout BlenderGIS.",
    ),
    Package(
        name="Pillow",
        reason="Provides image format handling leveraged by the Tyf module and raster tools.",
    ),
    Package(
        name="pyproj",
        reason="Used for coordinate reference system transformations when GDAL is unavailable.",
    ),
    Package(
        name="imageio",
        reason="Supplies the FreeImage plugin that BlenderGIS calls for reading imagery.",
    ),
)

OPTIONAL_PACKAGES: Sequence[Package] = (
    Package(
        name="gdal",
        reason=(
            "Offers high-performance access to raster and projection utilities.\n"
            "GDAL wheels are platform specific and may require OS-level libraries."
        ),
        optional=True,
    ),
)


def _resolve_python_executable(candidate: str) -> str:
    """Return the absolute path to the python interpreter to use."""

    if os.path.isabs(candidate) and os.path.exists(candidate):
        return candidate

    resolved = shutil.which(candidate)
    if resolved:
        return resolved

    raise FileNotFoundError(f"Unable to locate python interpreter: {candidate!r}")


def _prepare_pip(python: str, *, upgrade: bool = True) -> None:
    """Ensure that ``pip`` is available for the provided interpreter."""

    try:
        _run_command([python, "-m", "pip", "--version"], dry_run=False)
    except subprocess.CalledProcessError:
        # pip is missing, try to bootstrap it via ensurepip
        _run_command([python, "-m", "ensurepip", "--upgrade"], dry_run=False)
    else:
        if not upgrade:
            return

    if upgrade:
        _run_command([python, "-m", "pip", "install", "--upgrade", "pip"], dry_run=False)


def _run_command(command: Sequence[str], *, dry_run: bool) -> subprocess.CompletedProcess[str] | None:
    """Execute ``command`` while echoing it to stdout.

    When ``dry_run`` is true the command is only printed.
    """

    print(f"$ {shlex.join(command)}", flush=True)
    if dry_run:
        return None
    return subprocess.run(command, check=True, text=True)


def _install_packages(
    python: str,
    packages: Iterable[Package],
    *,
    dry_run: bool,
    pip_args: Sequence[str],
    allow_failure: bool = False,
) -> Dict[str, bool]:
    """Install each package and report success or failure."""

    results: Dict[str, bool] = {}
    for package in packages:
        print(f"\nInstalling {package.name} — {package.reason}")
        try:
            _run_command([python, "-m", "pip", "install", package.name, *pip_args], dry_run=dry_run)
        except subprocess.CalledProcessError:
            results[package.name] = False
            if allow_failure:
                print(
                    f"Warning: installing {package.name} failed.\n"
                    "Some BlenderGIS features may be unavailable."
                )
            else:
                raise
        else:
            results[package.name] = True
    return results


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install the Python dependencies that BlenderGIS expects.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "The script installs the core runtime requirements by default. "
            "Use --include-optional to also attempt installing GDAL.\n"
            "Additional packages may be passed with --extra-package."
        ),
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python interpreter to run pip with (defaults to the current interpreter).",
    )
    parser.add_argument(
        "--skip-pip-upgrade",
        action="store_true",
        help="Do not upgrade pip before installing packages.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the commands without executing them.",
    )
    parser.add_argument(
        "--include-optional",
        action="store_true",
        help="Attempt to install optional dependencies such as GDAL.",
    )
    parser.add_argument(
        "--skip-package",
        action="append",
        default=[],
        metavar="NAME",
        help="Name of a package to skip (may be repeated).",
    )
    parser.add_argument(
        "--extra-package",
        action="append",
        default=[],
        metavar="SPEC",
        help="Additional package specifiers to install in addition to the defaults.",
    )
    parser.add_argument(
        "--pip-extra-args",
        default="",
        metavar="ARGS",
        help="Extra arguments forwarded to 'pip install' (e.g. \"--pre --find-links ...\").",
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="Show the packages that would be installed and exit.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)

    try:
        python = _resolve_python_executable(args.python)
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 2

    pip_args = shlex.split(args.pip_extra_args)

    selected_packages: List[Package] = []
    skipped = {name.lower() for name in args.skip_package}

    for package in CORE_PACKAGES:
        if package.name.lower() not in skipped:
            selected_packages.append(package)

    optional_packages = OPTIONAL_PACKAGES if args.include_optional else ()
    for package in optional_packages:
        if package.name.lower() not in skipped:
            selected_packages.append(package)

    if args.extra_package:
        selected_packages.extend(
            Package(name=spec, reason="User supplied dependency.", optional=False)
            for spec in args.extra_package
            if spec.lower() not in skipped
        )

    if args.list_only:
        if selected_packages:
            print("Packages queued for installation:")
            for package in selected_packages:
                suffix = " (optional)" if package.optional else ""
                print(f"  - {package.name}{suffix}: {package.reason}")
        else:
            print("No packages selected for installation.")
        return 0

    if not args.dry_run:
        _prepare_pip(python, upgrade=not args.skip_pip_upgrade)

    core_failures = False
    if selected_packages:
        results = _install_packages(
            python,
            selected_packages,
            dry_run=args.dry_run,
            pip_args=pip_args,
            allow_failure=True,
        )
        core_failures = any(
            not success and not package.optional
            for package in selected_packages
            for success in (results[package.name],)
        )
    else:
        print("No packages selected. Nothing to do.")

    if core_failures:
        print("\nOne or more core dependencies failed to install.", file=sys.stderr)
        return 1

    print("\nDependency installation completed.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
