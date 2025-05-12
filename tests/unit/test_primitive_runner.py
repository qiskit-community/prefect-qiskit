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
"""Test primitive runner."""

import json
import time
from datetime import datetime

import numpy as np
import pytest
from prefect import get_client
from prefect.client.schemas.filters import ArtifactFilter, TaskRunFilter
from pytest_mock import MockerFixture
from qiskit import QuantumCircuit

from prefect_qiskit.exceptions import RuntimeJobFailure
from prefect_qiskit.models import JobMetrics
from prefect_qiskit.primitives.runner import run_primitive
from prefect_qiskit.vendors.qiskit_aer import QiskitAerCredentials
from prefect_qiskit.vendors.qiskit_aer.client import QiskitAerClient


@pytest.mark.asyncio
async def test_retry_until_success(
    mocker: MockerFixture,
    aer_credentials_2q: QiskitAerCredentials,
    bell_circuit_pub: QuantumCircuit,
) -> None:
    """Test retryable error during primitive execution.

    This test uses a patched Aer simulator client.
    get_status method returns a retryable RuntimeJobFailure for the first call,
    and returns "COMPLETED" next.
    The runner workflow must retry on the first failure and return the successful result.
    """
    mocker.patch.object(
        QiskitAerClient,
        "get_job_status",
        side_effect=[
            RuntimeJobFailure("retryable failure", job_id="test_job_123", retry=True),
            "COMPLETED",
        ],
    )

    # API will intentionally fail once
    result = await run_primitive.with_options(
        retries=2,
        retry_delay_seconds=1,
    )(
        primitive_blocs=[bell_circuit_pub],
        program_type="sampler",
        resource_name="aer_simulator",
        credentials=aer_credentials_2q,
        enable_analytics=False,
    )

    assert result[0].data.meas.get_counts() == {"00": 512, "11": 512}

    # Check runtime API is called twice by Prefect workflow
    assert QiskitAerClient.get_job_status.call_count == 2  # type: ignore[attr-defined]
    assert QiskitAerClient.run_primitive.call_count == 2  # type: ignore[attr-defined]
    assert QiskitAerClient.get_primitive_result.call_count == 1  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_unretryable(
    mocker: MockerFixture,
    aer_credentials_2q: QiskitAerCredentials,
    bell_circuit_pub: QuantumCircuit,
) -> None:
    """Test raise when unretryable.

    This test uses a patched Aer simulator client.
    get_status method always returns unretryable RuntimeJobFailure.
    Workflow should not repeat submission of unexecutable job.
    """
    mocker.patch.object(
        QiskitAerClient,
        "get_job_status",
        side_effect=RuntimeJobFailure("unretryable failure", job_id="test_job_123", retry=False),
    )

    with pytest.raises(RuntimeJobFailure):
        await run_primitive.with_options(
            retries=2,
            retry_delay_seconds=1,
        )(
            primitive_blocs=[bell_circuit_pub],
            program_type="sampler",
            resource_name="aer_simulator",
            credentials=aer_credentials_2q,
            enable_analytics=False,
        )

    # Don't submit unretryable job more than once
    assert QiskitAerClient.run_primitive.call_count == 1  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_not_infinite_loop(
    mocker: MockerFixture,
    aer_credentials_2q: QiskitAerCredentials,
    bell_circuit_pub: QuantumCircuit,
) -> None:
    """Test eventually raise.

    This test uses a patched Aer simulator client.
    get_status method always returns retryable RuntimeJobFailure.
    Workflow must stop after certain number of retries.
    """
    mocker.patch.object(
        QiskitAerClient,
        "get_job_status",
        side_effect=RuntimeJobFailure("retryable failure", job_id="test_job_123", retry=True),
    )

    with pytest.raises(RuntimeJobFailure):
        await run_primitive.with_options(
            retries=2,
            retry_delay_seconds=1,
        )(
            primitive_blocs=[bell_circuit_pub],
            program_type="sampler",
            resource_name="aer_simulator",
            credentials=aer_credentials_2q,
            enable_analytics=False,
        )

    # Retry until retry limit
    assert QiskitAerClient.run_primitive.call_count > 1  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_retry_on_task_timeout(
    mocker: MockerFixture,
    aer_credentials_2q: QiskitAerCredentials,
    bell_circuit_pub: QuantumCircuit,
) -> None:
    """Test retry on task timeout.

    This test uses a patched Aer simulator client.
    get_status returns "COMPLETED" after 10 sec from the test starts,
    while the task timeout is intentionally set to 6 seconds.
    This means timeout happens once, but next execution will success.
    """
    test_start = time.time()

    mocker.patch.object(
        QiskitAerClient,
        "get_job_status",
        side_effect=lambda _: "COMPLETED" if time.time() - test_start > 10 else "QUEUED",
    )

    result = await run_primitive.with_options(
        retries=2,
        retry_delay_seconds=0,
        timeout_seconds=6,
    )(
        primitive_blocs=[bell_circuit_pub],
        program_type="sampler",
        resource_name="aer_simulator",
        credentials=aer_credentials_2q,
        enable_analytics=False,
    )

    assert result[0].data.meas.get_counts() == {"00": 512, "11": 512}

    # Check runtime API is called twice by Prefect workflow due to timeout
    assert QiskitAerClient.run_primitive.call_count == 2  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_job_metrics(
    mocker: MockerFixture,
    aer_credentials_2q: QiskitAerCredentials,
    bell_circuit_pub: QuantumCircuit,
) -> None:
    """Test job metrics artifact.

    This test uses a patched Aer simulator client that returns artificial job metrics.
    The artifact is loaded from Prefect server and tested against reference data.
    """
    test_options = {
        "value1": {
            "nested1": 123,
            "nested2": 456,
        },
        "value2": np.array([7, 8, 9]),
    }

    mocker.patch.object(
        QiskitAerClient,
        "get_job_status",
        return_value="COMPLETED",
    )
    mocker.patch.object(
        QiskitAerClient,
        "get_job_metrics",
        return_value=JobMetrics(
            qpu_usage=10,
            timestamp_created=datetime.fromisoformat("2025-01-01T00:00:00"),
            timestamp_started=datetime.fromisoformat("2025-01-01T00:01:00"),
            timestamp_completed=datetime.fromisoformat("2025-01-01T00:10:00"),
        ),
    )

    await run_primitive.with_options(
        task_run_name="test_job_metrics",
        tags=["tag1", "tag2"],
    )(
        primitive_blocs=[bell_circuit_pub],
        program_type="sampler",
        resource_name="aer_simulator",
        credentials=aer_credentials_2q,
        enable_analytics=True,
        options=test_options,
    )

    with get_client(sync_client=True) as client:
        artifacts = client.read_artifacts(
            artifact_filter=ArtifactFilter(key={"any_": ["job-metrics"]}),
            task_run_filter=TaskRunFilter(name={"any_": ["test_job_metrics"]}),
        )
    assert len(artifacts) == 1

    metrics_keys, metrics_vals = json.loads(artifacts[0].data)
    assert metrics_keys == [
        "resource",
        "program_type",
        "num_pubs",
        "job_id",
        "tags",
        "timestamp.created",
        "timestamp.started",
        "timestamp.completed",
        "span.queue",
        "span.work",
        "span.qpu",
        "work_efficiency",
        "pub[0].circuit.depth",
        "pub[0].circuit.size",
        "pub[0].shape",
        "pub[0].timestamp.started",
        "pub[0].timestamp.completed",
        "pub[0].duration",
        "options.value1.nested1",
        "options.value1.nested2",
        "options.value2",
    ]
    assert metrics_vals == [
        "aer_simulator",
        "sampler",
        1,
        "test_job_123",
        ["tag1", "tag2"],
        "2025-01-01T00:00:00",
        "2025-01-01T00:01:00",
        "2025-01-01T00:10:00",
        60.0,
        540.0,
        10,
        1.9,
        3,
        4,
        [],  # tuple, but returned as a list due to json serialization
        None,
        None,
        None,
        "123",
        "456",
        "array([7, 8, 9])",
    ]
