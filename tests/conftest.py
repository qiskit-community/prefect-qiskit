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
import os
from collections.abc import Generator

import pytest
from prefect.testing.utilities import prefect_test_harness
from qiskit.circuit import QuantumCircuit

from prefect_qiskit.vendors.qiskit_aer import QiskitAerCredentials


@pytest.fixture(autouse=True, scope="module")
def prefect_test_fixture(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[None, None, None]:
    """Fixture to start prefect server in test mode."""
    storage_dir = tmp_path_factory.mktemp("storage")
    os.environ["PREFECT_LOCAL_STORAGE_PATH"] = str(storage_dir)
    with prefect_test_harness():
        yield


@pytest.fixture
def bell_circ() -> QuantumCircuit:
    """Fixture to return Bell circuit."""
    vqc = QuantumCircuit(2)
    vqc.h(0)
    vqc.cx(0, 1)
    vqc.measure_all()

    return vqc


@pytest.fixture
def aer_credentials_2q() -> QiskitAerCredentials:
    """Fixture to return Aer credentials with 2Q generic backend."""
    return QiskitAerCredentials(
        num_qubits=2,
        noise=False,
        coupling_map_type="linear",
    )
