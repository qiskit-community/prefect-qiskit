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
"""Test PUB hashing.

The structure of this test case may look weird!!!

We found that Qiskit QuantumCircuit creates a different byte output with pickle.dumps
when we create the same object in different Python kernels.
The key use case of the cache feature is the omission of duplicated primitive executions
when re-running of the entire workflow due to accidental Python kernel crashes or
upon reaching the maximum reexecution limit.
This cache saves users from losing the experiment results run prior to the failure.

To cover this situation as a test case, we must simulate the creation of
Primitive Unified Blocs with different Python kernels and evaluate their Prefect cache key.

This module tests the cache key equivalency by executing a standalone python program
with subprocess calls, and extracting generated keys from stdout to compare.
"""

import os
import subprocess
import sys

import pytest
from qiskit.circuit import Parameter, QuantumCircuit
from qiskit.primitives.containers.estimator_pub import EstimatorPub
from qiskit.primitives.containers.sampler_pub import SamplerPub
from qiskit.quantum_info import SparsePauliOp

from prefect_qiskit.utils.pub_hasher import pub_hasher


@pytest.fixture
def current_folder_path(
    request: pytest.FixtureRequest,
):
    return os.path.dirname(request.node.fspath)


@pytest.mark.parametrize(
    ["test_file"],
    [
        pytest.param("sampler_pub", id="sampler_pub"),
        pytest.param("estimator_pub", id="estimator_pub"),
        # pytest.param("isa_pub", id="isa_pub"),  # TODO: uncomment after 2.2.2 (see qiskit #14729)
    ],
)
def test_sampler_pub_hash(
    current_folder_path: str,
    test_file: str,
) -> None:
    """Test Prefect cache key equivalency with independent Python kernels."""
    py_file = ".".join(["scripts", test_file])

    key1 = subprocess.run(
        [sys.executable, "-m", py_file],
        cwd=current_folder_path,
        check=True,
        capture_output=True,
    ).stdout.strip()

    key2 = subprocess.run(
        [sys.executable, "-m", py_file],
        cwd=current_folder_path,
        check=True,
        capture_output=True,
    ).stdout.strip()

    assert key1 == key2


def test_pub_different_params() -> None:
    """Test Prefect cache key with same circuit and different parameters."""
    param = Parameter("θ")
    circ = QuantumCircuit(1)
    circ.rx(param, 0)
    circ.measure_all()

    key1 = pub_hasher(
        pubs=[SamplerPub.coerce((circ, [0.456]))],
        options={"test": 123},
        resource_name="backend_xyz",
    )
    key2 = pub_hasher(
        pubs=[SamplerPub.coerce((circ, [0.123]))],
        options={"test": 123},
        resource_name="backend_xyz",
    )

    assert key1 != key2


def test_pub_different_order() -> None:
    """Test Prefect cache key with same set but different order."""
    param = Parameter("θ")
    circ = QuantumCircuit(1)
    circ.rx(param, 0)
    circ.measure_all()

    key1 = pub_hasher(
        pubs=[
            SamplerPub.coerce((circ, [0.456])),
            SamplerPub.coerce((circ, [0.123])),
        ],
        options={"test": 123},
        resource_name="backend_xyz",
    )
    key2 = pub_hasher(
        pubs=[
            SamplerPub.coerce((circ, [0.123])),
            SamplerPub.coerce((circ, [0.456])),
        ],
        options={"test": 123},
        resource_name="backend_xyz",
    )

    # Note: This changes the result memory allocation, which can impact postprocessing.
    assert key1 != key2


def test_pub_different_observable() -> None:
    """Test Prefect cache key with same circuit but different observable."""
    param = Parameter("θ")
    circ = QuantumCircuit(1)
    circ.rx(param, 0)
    circ.measure_all()

    key1 = pub_hasher(
        pubs=[
            EstimatorPub.coerce((circ, SparsePauliOp.from_list([("X", 1), ("Y", 2)]), [0.123])),
        ],
        options={"test": 123},
        resource_name="backend_xyz",
    )
    key2 = pub_hasher(
        pubs=[
            EstimatorPub.coerce((circ, SparsePauliOp.from_list([("X", 2), ("Y", 1)]), [0.123])),
        ],
        options={"test": 123},
        resource_name="backend_xyz",
    )

    assert key1 != key2
