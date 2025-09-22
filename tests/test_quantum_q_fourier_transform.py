import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quantum.q_fourier_transform import quantum_fourier_transform


def test_quantum_fourier_transform_distribution():
    counts = quantum_fourier_transform(3)
    assert sum(counts.values()) == 10_000
    assert len(counts) == 8
    assert all(abs(count - 1250) <= 1 for count in counts.values())


@pytest.mark.parametrize(
    "argument, exc_type, message",
    [
        (-1, ValueError, "must be > 0"),
        ("a", TypeError, "must be a integer"),
        (100, ValueError, "too large"),
        (0.5, ValueError, "must be exact integer"),
    ],
)
def test_quantum_fourier_transform_invalid_inputs(argument, exc_type, message):
    with pytest.raises(exc_type, match=message):
        quantum_fourier_transform(argument)
