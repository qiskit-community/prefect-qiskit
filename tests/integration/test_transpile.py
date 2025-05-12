# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
"""Test transpile workflow with QuantumRuntime."""

import pytest
from qiskit.circuit import QuantumCircuit
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager

from prefect_qiskit.runtime import QuantumRuntime
from prefect_qiskit.vendors.qiskit_aer import QiskitAerCredentials


@pytest.fixture
def vcirc() -> QuantumCircuit:
    vqc = QuantumCircuit(2)
    vqc.h(0)
    vqc.cx(0, 1)
    return vqc


@pytest.fixture
def bell_isa_cz(vcirc) -> QuantumCircuit:
    return generate_preset_pass_manager(
        optimization_level=2,
        basis_gates=["rz", "sx", "cz"],
    ).run(vcirc)


@pytest.fixture
def bell_isa_cx(vcirc) -> QuantumCircuit:
    return generate_preset_pass_manager(
        optimization_level=2,
        basis_gates=["rz", "sx", "cx"],
    ).run(vcirc)


@pytest.mark.parametrize(
    ["basis", "target_isa"],
    [
        pytest.param(["rz", "sx", "cz"], "bell_isa_cz", id="cz-basis"),
        pytest.param(["rz", "sx", "cx"], "bell_isa_cx", id="cx-basis"),
    ],
)
def test_transpile_with_runtime(
    vcirc: QuantumCircuit,
    request: pytest.FixtureRequest,
    basis: list[str],
    target_isa: str,
) -> None:
    """Test transpile with QuantumRuntime API inside sync context."""
    runtime = QuantumRuntime(
        resource_name="aer_simulator",
        credentials=QiskitAerCredentials(num_qubits=2, basis_gates=basis),
    )

    pm = generate_preset_pass_manager(
        optimization_level=2,
        target=runtime.get_target(),
    )
    isa = pm.run(vcirc)

    assert isa == request.getfixturevalue(target_isa)


@pytest.mark.parametrize(
    ["basis", "target_isa"],
    [
        pytest.param(["rz", "sx", "cz"], "bell_isa_cz", id="cz-basis"),
        pytest.param(["rz", "sx", "cx"], "bell_isa_cx", id="cx-basis"),
    ],
)
@pytest.mark.asyncio
async def test_transpile_with_runtime_async(
    vcirc: QuantumCircuit,
    request: pytest.FixtureRequest,
    basis: list[str],
    target_isa: str,
) -> None:
    """Test transpile with QuantumRuntime API inside async context."""
    runtime = QuantumRuntime(
        resource_name="aer_simulator",
        credentials=QiskitAerCredentials(num_qubits=2, basis_gates=basis),
    )

    pm = generate_preset_pass_manager(
        optimization_level=2,
        target=await runtime.get_target(),
    )
    isa = pm.run(vcirc)

    assert isa == request.getfixturevalue(target_isa)
