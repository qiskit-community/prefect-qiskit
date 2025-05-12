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
"""Test primitive workflow with QuantumRuntime."""

from pathlib import Path

import pytest
from diskcache import Cache
from prefect import get_client, task
from prefect.client.schemas.filters import ArtifactFilter, TaskRunFilter
from pytest_mock import MockerFixture
from qiskit.circuit import QuantumCircuit
from qiskit.primitives.containers import PrimitiveResult
from qiskit.quantum_info.operators import SparsePauliOp
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from utils import assert_sampler_fidelity

from prefect_qiskit.primitives.job import PrimitiveJobRun
from prefect_qiskit.runtime import QuantumRuntime
from prefect_qiskit.vendors.qiskit_aer import QiskitAerCredentials
from prefect_qiskit.vendors.qiskit_aer.client import QiskitAerClient


@pytest.fixture(autouse=True)
def temp_cache(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    """Fixture to replace disk cache with temp location and cleanup."""
    test_cache = Cache(tmp_path / "test_cache")
    with monkeypatch.context() as mp:
        mp.setattr(
            "prefect_qiskit.vendors.qiskit_aer.client.DISK_CACHE",
            test_cache,
        )
        yield
    test_cache.clear()
    test_cache.close()


def test_client_cached() -> None:
    """Test client cache for the same backend configuration."""
    credentials1 = QiskitAerCredentials(
        num_qubits=2,
        basis_gates=["sx", "rz", "cz"],
        noise=True,
    )
    credentials2 = QiskitAerCredentials(
        num_qubits=2,
        basis_gates=["sx", "rz", "cx"],
        noise=True,
    )

    assert credentials1.get_client() is credentials1.get_client()
    assert credentials1.get_client() is not credentials2.get_client()


def test_sampler(
    aer_credentials_2q: QiskitAerCredentials,
    bell_circ: QuantumCircuit,
    hh_circ: QuantumCircuit,
) -> None:
    """Test sampler within sync context."""
    runtime = QuantumRuntime(
        resource_name="aer_simulator",
        credentials=aer_credentials_2q,
        enable_job_analytics=False,
    )
    options = {
        "default_shots": 10000,
        "seed_simulator": 1234,
    }
    pm = generate_preset_pass_manager(optimization_level=2, target=runtime.get_target())

    result = runtime.sampler(pm.run([bell_circ, hh_circ]), options=options)

    assert_sampler_fidelity(result[0], {"00": 1, "11": 1})
    assert_sampler_fidelity(result[1], {"00": 1, "01": 1, "10": 1, "11": 1})


def test_estimator(
    aer_credentials_2q: QiskitAerCredentials,
    bell_circ: QuantumCircuit,
) -> None:
    """Test estimator within sync context."""
    op = SparsePauliOp.from_list([("ZZ", 1)])

    runtime = QuantumRuntime(
        resource_name="aer_simulator",
        credentials=aer_credentials_2q,
        enable_job_analytics=False,
    )
    options = {
        "seed_simulator": 1234,
    }
    pm = generate_preset_pass_manager(optimization_level=2, target=runtime.get_target())
    isa_qc = pm.run(bell_circ)
    isa_op = op.apply_layout(isa_qc.layout)

    result = runtime.estimator([(isa_qc, isa_op)], options=options)

    assert float(result[0].data.evs) == pytest.approx(1.0, abs=0.1)


@pytest.mark.asyncio
async def test_sampler_mult_async(
    aer_credentials_2q: QiskitAerCredentials,
    bell_circ: QuantumCircuit,
    hh_circ: QuantumCircuit,
) -> None:
    """Test multiple sampler executions within async context."""
    runtime = QuantumRuntime(
        resource_name="aer_simulator",
        credentials=aer_credentials_2q,
        enable_job_analytics=False,
    )
    options = {
        "default_shots": 10000,
        "seed_simulator": 1234,
    }
    pm = generate_preset_pass_manager(optimization_level=2, target=await runtime.get_target())

    result1 = await runtime.sampler(pm.run([bell_circ]), options=options)
    result2 = await runtime.sampler(pm.run([hh_circ]), options=options)

    assert_sampler_fidelity(result1[0], {"00": 1, "11": 1})
    assert_sampler_fidelity(result2[0], {"00": 1, "01": 1, "10": 1, "11": 1})


def test_sampler_custom_tags(
    aer_credentials_2q: QiskitAerCredentials,
    bell_circ: QuantumCircuit,
) -> None:
    """Test sampler with custom tags and filter job metric artifact."""
    runtime = QuantumRuntime(
        resource_name="aer_simulator",
        credentials=aer_credentials_2q,
        enable_job_analytics=True,
    )
    options = {
        "default_shots": 10000,
        "seed_simulator": 1234,
    }
    pm = generate_preset_pass_manager(optimization_level=2, target=runtime.get_target())

    runtime.sampler(
        pm.run([bell_circ]),
        options=options,
        tags=["test_sampler_custom_tags"],
    )

    with get_client(sync_client=True) as client:
        artifacts = client.read_artifacts(
            artifact_filter=ArtifactFilter(key={"any_": ["job-metrics"]}),
            task_run_filter=TaskRunFilter(tags={"all_": ["test_sampler_custom_tags"]}),
        )
    assert len(artifacts) == 1


@pytest.mark.skip(reason="This test require qiskit/#12963")
def test_sampler_cache(
    mocker: MockerFixture,
    aer_credentials_2q: QiskitAerCredentials,
    bell_circ: QuantumCircuit,
) -> None:
    """Test caching the primitive results."""
    # TODO remove skip after Qiskit 2.1 is released

    spy = mocker.spy(QiskitAerClient, "run_primitive")

    runtime = QuantumRuntime(
        resource_name="aer_simulator",
        credentials=aer_credentials_2q,
        enable_job_analytics=False,
        execution_cache=True,
    )
    options = {
        "default_shots": 10000,
        "seed_simulator": 1234,
    }
    pm = generate_preset_pass_manager(optimization_level=2, target=runtime.get_target())

    result1 = runtime.sampler(
        pm.run([bell_circ]),
        options=options,
    )
    assert spy.call_count == 1

    # This execution must be cached
    result2 = runtime.sampler(
        pm.run([bell_circ]),
        options=options,
    )
    assert spy.call_count == 1
    assert result1[0].data.meas.get_counts() == result2[0].data.meas.get_counts()

    # This execution must ignore cache
    runtime.execution_cache = False

    runtime.sampler(
        pm.run([bell_circ]),
        options=options,
    )
    assert spy.call_count == 2


def test_sampler_as_task(
    aer_credentials_2q: QiskitAerCredentials,
    bell_circ: QuantumCircuit,
) -> None:
    """Test sampler execution as a Prefect task."""

    @task
    def sample_task(
        runtime: QuantumRuntime,
        circuit: QuantumCircuit,
    ) -> PrimitiveResult:
        options = {
            "default_shots": 10000,
            "seed_simulator": 1234,
        }
        pm = generate_preset_pass_manager(optimization_level=2, target=runtime.get_target())

        return runtime.sampler(pm.run([circuit]), options=options)

    runtime = QuantumRuntime(
        resource_name="aer_simulator",
        credentials=aer_credentials_2q,
        enable_job_analytics=False,
    )
    result = sample_task(runtime, bell_circ)
    assert_sampler_fidelity(result[0], {"00": 1, "11": 1})


@pytest.mark.asyncio
async def test_result_retrieve(
    mocker: MockerFixture,
    aer_credentials_2q: QiskitAerCredentials,
    bell_circ: QuantumCircuit,
) -> None:
    """Test retrieval of primitive results by using job ID."""
    # Fix job ID for retrieval.
    # In a practical situation, a user may find the job ID in the prefect console logs.
    mocker.patch(
        "prefect_qiskit.vendors.qiskit_aer.client.create_job_id",
        return_value="test_job_123",
    )

    runtime = QuantumRuntime(
        resource_name="aer_simulator",
        credentials=aer_credentials_2q,
        enable_job_analytics=False,
    )
    options = {
        "default_shots": 10000,
        "seed_simulator": 1234,
    }
    pm = generate_preset_pass_manager(optimization_level=2, target=await runtime.get_target())

    result = (await runtime.sampler(pm.run([bell_circ]), options=options))[0]

    job = PrimitiveJobRun(
        job_id="test_job_123",
        credentials=aer_credentials_2q,
    )
    # This method is async only. The test is async because of this.
    result_retrieved = (await job.fetch_result())[0]

    assert result.data.meas.get_counts() == result_retrieved.data.meas.get_counts()
