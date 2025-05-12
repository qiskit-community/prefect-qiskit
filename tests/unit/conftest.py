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
import numpy as np
import pytest
from pytest_mock import MockerFixture
from qiskit.circuit import QuantumCircuit
from qiskit.primitives.containers import (
    BitArray,
    DataBin,
    PrimitiveResult,
    SamplerPubResult,
)
from qiskit.primitives.containers.sampler_pub import SamplerPub

from prefect_qiskit.vendors.qiskit_aer.client import QiskitAerClient


@pytest.fixture
def bell_circuit_pub(
    bell_circ: QuantumCircuit,
) -> SamplerPub:
    """Fixture to return Bell circuit."""
    return SamplerPub.coerce(bell_circ)


@pytest.fixture(autouse=True)
def api_mock_get_primitive_result(
    mocker: MockerFixture,
):
    """QiskitAerClient.get_primitive_result() mocked to return ideal Bell circuit result."""
    mock_response = PrimitiveResult(
        pub_results=[
            SamplerPubResult(
                data=DataBin(
                    meas=BitArray(
                        array=np.repeat([0, 3], 512).reshape((1024, 1)).astype(np.uint8),
                        num_bits=2,
                    ),
                    shape=(),
                ),
                metadata={"shots": 1024},
            )
        ]
    )
    mocker.patch.object(QiskitAerClient, "get_primitive_result", return_value=mock_response)


@pytest.fixture(autouse=True)
def api_mock_run_primitive(
    mocker: MockerFixture,
):
    """QiskitAerClient.run_primitive() mocked to return mock ID of test_job_123."""
    mocker.patch.object(QiskitAerClient, "run_primitive", return_value="test_job_123")
