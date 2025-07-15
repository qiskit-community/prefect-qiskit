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
"""Credentials for Qiskit Aer simulator."""

from typing import Literal

from cachetools import LRUCache, cached
from cachetools.keys import hashkey
from prefect.blocks.abstract import CredentialsBlock
from pydantic import Field, field_validator
from qiskit.circuit import Gate
from qiskit.circuit.library.standard_gates import get_standard_gate_name_mapping
from qiskit.providers.fake_provider import GenericBackendV2
from qiskit.transpiler.coupling import CouplingMap

from prefect_qiskit.vendors.qiskit_aer.client import QiskitAerClient

QISKIT_GATES: dict[str, Gate] = get_standard_gate_name_mapping()
NOISE_SEED: int = 1234
CLIENT_CACHE: LRUCache = LRUCache(maxsize=10)


class QiskitAerCredentials(CredentialsBlock):
    """
    Block used to emulate a runtime with the Qiskit Aer simulator.
    This block provides a virtual system configuration to produce a circuit ISA.

    Attributes:
        num_qubits:
            Number of qubits involved in the simulation.
            The host machine or computing node must have enough memory to represent qubit states,
            otherwise workflow execution may hang up.
        basis_gates:
            A list of quantum gate opcode to form a basis gate set.
            The 'delay', 'measure', and 'reset' instruction are included without being specified here.
        noise:
            Simulate noise during quantum gate operation.
            The depolarizing error is considered for gates,
            and the assignment error is considered for measurements.
            See the API doc for NoiseModel in Qiskit Aer for more details.
        coupling_map_type:
            Topology of coupling map.
            Actual connections are automatically generated from the selected topology.


    Example:
        Load stored Qiskit Aer credentials:

        ```python
        from prefect_qiskit.vendors.qiskit_aer import QiskitAerCredentials

        quantum_credentials = QiskitAerCredentials.load("BLOCK_NAME")
        ```
    """

    _logo_url = "https://avatars.githubusercontent.com/u/30696987?s=200&v=4"
    _block_type_name = "Qiskit Aer Credentials"
    _block_type_slug = "qiskit-aer-credentials"

    num_qubits: int = Field(
        default=10,
        description=(
            "Number of qubits involved in the simulation. "
            "The host machine or computing node must have enough memory to represent qubit states, "
            "otherwise workflow execution may hang up."
        ),
        title="Number of Qubits",
        ge=1,
    )

    basis_gates: list[str] = Field(
        default=["rz", "sx", "x", "cz"],
        description=(
            "A list of quantum gate opcode to form a basis gate set. "
            "The 'delay', 'measure', and 'reset' instruction are included without being specified here. "
        ),
        title="Basis Gates",
    )

    noise: bool = Field(
        default=False,
        description=(
            "Simulate noise during quantum gate operation. "
            "The depolarizing error is considered for gates, and the assignment error is considered for measurements. "
            "See the API doc for NoiseModel in Qiskit Aer for more details."
        ),
        title="Apply Noise",
    )

    coupling_map_type: Literal["full", "ring", "linear"] = Field(
        default="linear",
        description=(
            "Topology of coupling map. Actual connections are automatically generated from the selected topology."
        ),
        title="Coupling Map Type",
    )

    @field_validator("basis_gates", mode="before")  # type: ignore
    @classmethod
    def check_basis_gate(cls, val: list[str]) -> list[str]:
        if not all(g in QISKIT_GATES for g in val):
            raise ValueError(f"Basis gates {', '.join(val)} are not fully supported by Qiskit gate definition.")
        return val

    @cached(
        cache=CLIENT_CACHE,
        key=lambda self: hashkey(self.num_qubits, tuple(self.basis_gates), self.noise, self.coupling_map_type),
        info=True,
    )
    def get_client(self) -> QiskitAerClient:
        """Get a mock runtime client running the Aer simulator."""
        match self.coupling_map_type:
            case "full":
                coupling_map = CouplingMap.from_full(
                    num_qubits=self.num_qubits,
                    bidirectional=True,
                )
            case "ring":
                coupling_map = CouplingMap.from_ring(
                    num_qubits=self.num_qubits,
                    bidirectional=True,
                )
            case "linear":
                coupling_map = CouplingMap.from_line(
                    num_qubits=self.num_qubits,
                    bidirectional=True,
                )

        return QiskitAerClient(
            backend=GenericBackendV2(
                num_qubits=self.num_qubits,
                basis_gates=self.basis_gates.copy(),  # list is mutated internally
                coupling_map=coupling_map,
                noise_info=self.noise,
                seed=NOISE_SEED,
            )
        )
