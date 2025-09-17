from __future__ import annotations

import textwrap

import pytest

from . import CgtrcParseError, parse_cgtrc


SAMPLE_CGTRC = textwrap.dedent(
    """
    # Comments and blank lines should be ignored
    debug = boolean(default=False)
    precision = string(default=single)
    backend = option("python", "native", default="python")  # inline comment
    cache_dir = string(default="~/.cgt_cache")
    parallel = boolean(default=False)
    num_threads = integer(default=4)
    custom_flag = True
    custom_count = 7
    custom_path = "#not a comment"
    """
)


def test_parse_cgtrc_defaults() -> None:
    config = parse_cgtrc(SAMPLE_CGTRC)
    assert config["debug"].default is False
    assert config["precision"].default == "single"
    backend = config["backend"]
    assert backend.default == "python"
    assert backend.choices == ("python", "native")
    assert config["cache_dir"].default == "~/.cgt_cache"
    assert config["num_threads"].default == 4
    assert config["custom_flag"].default is True
    assert config["custom_count"].default == 7
    assert config["custom_path"].default == "#not a comment"


def test_invalid_boolean_value() -> None:
    with pytest.raises(CgtrcParseError):
        parse_cgtrc("debug = boolean(default=maybe)")


def test_option_default_must_be_choice() -> None:
    text = 'backend = option("python", default="native")'
    with pytest.raises(CgtrcParseError):
        parse_cgtrc(text)
