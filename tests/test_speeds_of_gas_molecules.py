import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from physics.speeds_of_gas_molecules import avg_speed_of_molecule, mps_speed_of_molecule


def test_avg_speed_of_molecule_matches_expected():
    nitrogen = avg_speed_of_molecule(273, 0.028)
    oxygen = avg_speed_of_molecule(300, 0.032)
    assert nitrogen == pytest.approx(454.34887551, abs=1e-8)
    assert oxygen == pytest.approx(445.52572734, abs=1e-8)


def test_mps_speed_of_molecule_matches_expected():
    nitrogen = mps_speed_of_molecule(273, 0.028)
    oxygen = mps_speed_of_molecule(300, 0.032)
    assert nitrogen == pytest.approx(402.65620702, abs=1e-8)
    assert oxygen == pytest.approx(394.83689555, abs=1e-8)


@pytest.mark.parametrize(
    "function, args, message",
    [
        (avg_speed_of_molecule, (-1, 0.028), "temperature"),
        (avg_speed_of_molecule, (273, 0.0), "Molar mass"),
        (mps_speed_of_molecule, (-1, 0.028), "temperature"),
        (mps_speed_of_molecule, (273, 0.0), "Molar mass"),
    ],
)
def test_speed_functions_raise_for_invalid_inputs(function, args, message):
    with pytest.raises(Exception, match=message):
        function(*args)
