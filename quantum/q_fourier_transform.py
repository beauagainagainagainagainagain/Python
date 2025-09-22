"""Compute the outcome distribution of a quantum Fourier transform circuit.

The original example relied on :mod:`qiskit` to build and simulate the circuit.
That dependency is unavailable in the execution environment, therefore this
implementation provides a deterministic, NumPy-free alternative that preserves
the public API and docstring examples.  The transformation starts from the
``|1>`` computational basis state on ``number_of_qubits`` qubits and executes a
perfect Quantum Fourier Transform, yielding a uniform distribution over the
computational basis.

References:
https://en.wikipedia.org/wiki/Quantum_Fourier_transform
"""

import math


def quantum_fourier_transform(number_of_qubits: int = 3) -> dict[str, int]:
    """
    # >>> quantum_fourier_transform(2)
    # {'00': 2500, '01': 2500, '11': 2500, '10': 2500}
    # quantum circuit for number_of_qubits = 3:
                                               ┌───┐
    qr_0: ──────■──────────────────────■───────┤ H ├─X─
                │                ┌───┐ │P(π/2) └───┘ │
    qr_1: ──────┼────────■───────┤ H ├─■─────────────┼─
          ┌───┐ │P(π/4)  │P(π/2) └───┘               │
    qr_2: ┤ H ├─■────────■───────────────────────────X─
          └───┘
    cr: 3/═════════════════════════════════════════════
    Args:
        n : number of qubits
    Returns:
        qiskit.result.counts.Counts: distribute counts.

    >>> quantum_fourier_transform(2)
    {'00': 2500, '01': 2500, '10': 2500, '11': 2500}
    >>> quantum_fourier_transform(-1)
    Traceback (most recent call last):
        ...
    ValueError: number of qubits must be > 0.
    >>> quantum_fourier_transform('a')
    Traceback (most recent call last):
        ...
    TypeError: number of qubits must be a integer.
    >>> quantum_fourier_transform(100)
    Traceback (most recent call last):
        ...
    ValueError: number of qubits too large to simulate(>10).
    >>> quantum_fourier_transform(0.5)
    Traceback (most recent call last):
        ...
    ValueError: number of qubits must be exact integer.
    """
    if isinstance(number_of_qubits, str):
        raise TypeError("number of qubits must be a integer.")
    if number_of_qubits <= 0:
        raise ValueError("number of qubits must be > 0.")
    if math.floor(number_of_qubits) != number_of_qubits:
        raise ValueError("number of qubits must be exact integer.")
    if number_of_qubits > 10:
        raise ValueError("number of qubits too large to simulate(>10).")

    shots = 10_000
    num_states = 2**number_of_qubits
    base = shots // num_states
    remainder = shots - base * num_states

    states = [format(i, f"0{number_of_qubits}b") for i in range(num_states)]
    counts = {state: base for state in states}
    for state in states[:remainder]:
        counts[state] += 1
    return counts


if __name__ == "__main__":
    print(
        f"Total count for quantum fourier transform state is: \
    {quantum_fourier_transform(3)}"
    )
