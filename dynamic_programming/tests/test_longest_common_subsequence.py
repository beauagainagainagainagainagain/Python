"""Tests for :mod:`dynamic_programming.longest_common_subsequence`."""

from __future__ import annotations

from typing import cast

import pytest

from dynamic_programming.longest_common_subsequence import longest_common_subsequence


def _is_subsequence(candidate: str, target: str) -> bool:
    """Return ``True`` if ``candidate`` is a subsequence of ``target``."""
    if not candidate:
        return True

    index = 0
    for character in target:
        if character == candidate[index]:
            index += 1
            if index == len(candidate):
                return True
    return index == len(candidate)


@pytest.mark.parametrize(
    ("first", "second", "expected_length", "expected_subsequence"),
    [
        ("programming", "gaming", 6, "gaming"),
        ("physics", "smartphone", 2, "ph"),
        ("computer", "food", 1, "o"),
        ("abcdef", "ace", 3, "ace"),
        ("ABCD", "ACBD", 3, "ABD"),
    ],
)
def test_longest_common_subsequence_known_examples(
    first: str, second: str, expected_length: int, expected_subsequence: str
) -> None:
    """The doctest examples continue to work when executed by ``pytest``."""
    length, subsequence = longest_common_subsequence(first, second)
    assert length == expected_length
    assert subsequence == expected_subsequence


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("", "abc"),
        ("abc", ""),
        ("", ""),
        ("abc", "def"),
        ("a", "b"),
    ],
)
def test_longest_common_subsequence_no_common_subsequence(
    first: str, second: str
) -> None:
    """Pairs with no shared subsequence should return ``(0, "")``."""
    length, subsequence = longest_common_subsequence(first, second)
    assert length == 0
    assert subsequence == ""


def test_longest_common_subsequence_multiple_valid_answers() -> None:
    """When many LCS strings exist, the chosen answer is still valid."""
    first = "ABCBDAB"
    second = "BDCABA"

    length, subsequence = longest_common_subsequence(first, second)

    assert length == 4
    assert subsequence in {"BCAB", "BCBA", "BDAB"}
    assert _is_subsequence(subsequence, first)
    assert _is_subsequence(subsequence, second)


def test_longest_common_subsequence_is_a_subsequence() -> None:
    """The reported subsequence is present in both inputs and has the right length."""
    first = "abracadabra"
    second = "avada kedavra"

    length_1, subsequence_1 = longest_common_subsequence(first, second)
    length_2, subsequence_2 = longest_common_subsequence(second, first)

    assert length_1 == length_2
    assert len(subsequence_1) == length_1
    assert len(subsequence_2) == length_2
    assert _is_subsequence(subsequence_1, first)
    assert _is_subsequence(subsequence_1, second)
    assert _is_subsequence(subsequence_2, first)
    assert _is_subsequence(subsequence_2, second)


def test_longest_common_subsequence_rejects_none_arguments() -> None:
    """Both parameters must be strings and not ``None``."""
    with pytest.raises(AssertionError):
        longest_common_subsequence(cast(str, None), "abc")
    with pytest.raises(AssertionError):
        longest_common_subsequence("abc", cast(str, None))
