"""Utilities for parsing ``cgtrc`` configuration files.

The real project that inspired this kata stores its configuration in
files that look like ``cgtrc``.  A file contains one assignment per line
and uses a small DSL to declare the available options.  The goal of this
module is to interpret that DSL so that other code can work with a Python
representation of the configuration.

The format is intentionally tiny: each non-empty line is either a comment
(starting with ``#``) or an assignment of the form ``name = value``.  The
``value`` can be expressed in a few ways:

* ``boolean(default=True)`` or ``boolean(False)``
* ``integer(default=4)``
* ``string(default=single)``
* ``option("python", "native", default="python")``
* a bare literal such as ``False`` or ``~/path``

For the purposes of the exercises the default values are the only
information that we need.  Parsing is strict so that mistakes in a
configuration file are reported with useful error messages.  The parser
returns :class:`Setting` objects that expose the inferred type, the default
value, and (when applicable) the available choices.
"""
from __future__ import annotations

from dataclasses import dataclass
import ast
from pathlib import Path
from typing import Iterable, Iterator, Sequence


class CgtrcParseError(ValueError):
    """Raised when a ``cgtrc`` configuration cannot be parsed."""


@dataclass(frozen=True)
class Setting:
    """Represents a single configuration option from a ``cgtrc`` file."""

    name: str
    type: str
    default: object
    choices: tuple[object, ...] | None = None

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable representation of the setting."""

        data: dict[str, object] = {"type": self.type, "default": self.default}
        if self.choices:
            data["choices"] = list(self.choices)
        return data


def parse_cgtrc(source: str | Path | Iterable[str]) -> dict[str, Setting]:
    """Parse *source* and return a mapping of option names to settings.

    Parameters
    ----------
    source:
        Either the textual contents of a ``cgtrc`` file, an iterable of
        lines, or a path pointing to a file on disk.
    """

    lines = _iter_lines(source)
    config: dict[str, Setting] = {}
    for lineno, raw_line in enumerate(lines, 1):
        line = _strip_inline_comment(raw_line).strip()
        if not line:
            continue
        if "=" not in line:
            raise CgtrcParseError(
                f"Line {lineno}: expected an assignment but got {raw_line!r}"
            )
        name, value_expr = (part.strip() for part in line.split("=", 1))
        if not name:
            raise CgtrcParseError(f"Line {lineno}: missing option name")
        setting = _parse_value(name, value_expr, lineno)
        config[name] = setting
    return config


def _iter_lines(source: str | Path | Iterable[str]) -> Iterator[str]:
    if isinstance(source, Path):
        text = source.read_text(encoding="utf-8")
        yield from text.splitlines()
    elif isinstance(source, str):
        if "\n" not in source and Path(source).is_file():
            text = Path(source).read_text(encoding="utf-8")
            yield from text.splitlines()
        else:
            yield from source.splitlines()
    else:
        yield from source


def _strip_inline_comment(line: str) -> str:
    """Remove comments from *line* while respecting quoted strings."""

    result: list[str] = []
    in_single = False
    in_double = False
    escaped = False
    for char in line:
        if escaped:
            result.append(char)
            escaped = False
            continue
        if char == "\\":
            result.append(char)
            escaped = True
            continue
        if char == "'" and not in_double:
            in_single = not in_single
            result.append(char)
            continue
        if char == '"' and not in_single:
            in_double = not in_double
            result.append(char)
            continue
        if char == "#" and not in_single and not in_double:
            break
        result.append(char)
    return "".join(result)


def _parse_value(name: str, expr: str, lineno: int) -> Setting:
    call = _match_call(expr)
    if call is not None:
        func_name, args = call
        return _parse_call(name, func_name, args, lineno)
    value = _auto_coerce(expr.strip())
    value_type = _infer_type(value)
    return Setting(name=name, type=value_type, default=value)


def _match_call(expr: str) -> tuple[str, str] | None:
    expr = expr.strip()
    if not expr.endswith(")") or "(" not in expr:
        return None
    open_paren = expr.find("(")
    func_name = expr[:open_paren].strip()
    if not func_name.isidentifier():
        return None
    inner = expr[open_paren + 1 : -1]
    return func_name, inner


def _parse_call(name: str, func_name: str, arg_string: str, lineno: int) -> Setting:
    args = _split_args(arg_string)
    if func_name == "boolean":
        default_text, positional, extras = _parse_arguments(args, True)
        if positional or extras:
            raise CgtrcParseError(
                f"Line {lineno}: unexpected arguments to boolean() for {name}"
            )
        default = _parse_boolean(default_text, name, lineno)
        return Setting(name=name, type="boolean", default=default)
    if func_name == "integer":
        default_text, positional, extras = _parse_arguments(args, True)
        if positional or extras:
            raise CgtrcParseError(
                f"Line {lineno}: unexpected arguments to integer() for {name}"
            )
        default = _parse_integer(default_text, name, lineno)
        return Setting(name=name, type="integer", default=default)
    if func_name == "string":
        default_text, positional, extras = _parse_arguments(args, True)
        if positional or extras:
            raise CgtrcParseError(
                f"Line {lineno}: unexpected arguments to string() for {name}"
            )
        default = _parse_string(default_text, name, lineno)
        return Setting(name=name, type="string", default=default)
    if func_name == "option":
        default_text, positional, extras = _parse_arguments(args, False)
        if extras:
            raise CgtrcParseError(
                f"Line {lineno}: unexpected keyword arguments in option() for {name}"
            )
        if not positional:
            raise CgtrcParseError(
                f"Line {lineno}: option() requires at least one choice for {name}"
            )
        choices = tuple(_parse_string(arg, name, lineno) for arg in positional)
        if default_text is None:
            default_value = choices[0]
        else:
            default_value = _parse_string(default_text, name, lineno)
            if default_value not in choices:
                raise CgtrcParseError(
                    f"Line {lineno}: default {default_value!r} not in choices {choices}"
                )
        return Setting(name=name, type="option", default=default_value, choices=choices)
    raise CgtrcParseError(
        f"Line {lineno}: unsupported function {func_name!r} for option {name}"
    )


def _split_args(arg_string: str) -> list[str]:
    args: list[str] = []
    start = 0
    depth = 0
    in_single = False
    in_double = False
    escaped = False
    for index, char in enumerate(arg_string):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == "'" and not in_double:
            in_single = not in_single
            continue
        if char == '"' and not in_single:
            in_double = not in_double
            continue
        if char == "(" and not in_single and not in_double:
            depth += 1
            continue
        if char == ")" and not in_single and not in_double:
            depth -= 1
            continue
        if char == "," and not in_single and not in_double and depth == 0:
            args.append(arg_string[start:index].strip())
            start = index + 1
    last = arg_string[start:].strip()
    if last:
        args.append(last)
    return args


def _parse_arguments(
    args: Sequence[str], allow_positional_default: bool
) -> tuple[str | None, list[str], dict[str, str]]:
    default: str | None = None
    positional: list[str] = []
    extras: dict[str, str] = {}
    for arg in args:
        if "=" in arg:
            key, value = (part.strip() for part in arg.split("=", 1))
            if key == "default":
                if default is not None:
                    raise CgtrcParseError("duplicate default specification")
                default = value
            else:
                extras[key] = value
        else:
            positional.append(arg)
    if allow_positional_default and default is None and positional:
        default = positional.pop(0)
    return default, positional, extras


def _parse_boolean(text: str | None, name: str, lineno: int) -> bool:
    if text is None:
        raise CgtrcParseError(f"Line {lineno}: boolean() for {name} requires a value")
    normalized = text.strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False
    raise CgtrcParseError(
        f"Line {lineno}: could not parse boolean value {text!r} for {name}"
    )


def _parse_integer(text: str | None, name: str, lineno: int) -> int:
    if text is None:
        raise CgtrcParseError(f"Line {lineno}: integer() for {name} requires a value")
    try:
        return int(text, 0)
    except ValueError as exc:
        raise CgtrcParseError(
            f"Line {lineno}: could not parse integer value {text!r} for {name}"
        ) from exc


def _parse_string(text: str | None, name: str, lineno: int) -> str:
    if text is None:
        raise CgtrcParseError(f"Line {lineno}: string() for {name} requires a value")
    text = text.strip()
    if not text:
        return ""
    if text[0] in {'"', "'"} and text[-1] == text[0]:
        try:
            return ast.literal_eval(text)
        except (ValueError, SyntaxError) as exc:
            raise CgtrcParseError(
                f"Line {lineno}: invalid quoted string {text!r} for {name}"
            ) from exc
    return text


def _auto_coerce(text: str) -> object:
    text = text.strip()
    lowered = text.lower()
    if lowered in {"true", "1", "yes", "on"}:
        return True
    if lowered in {"false", "0", "no", "off"}:
        return False
    try:
        return int(text, 0)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        pass
    if text and text[0] in {'"', "'"} and text[-1] == text[0]:
        try:
            return ast.literal_eval(text)
        except (ValueError, SyntaxError):
            return text[1:-1]
    return text


def _infer_type(value: object) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "float"
    return type(value).__name__
