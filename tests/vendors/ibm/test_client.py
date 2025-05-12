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
"""Test IBM specific implementation of runtime client.

This module is responsible for unit test of the client interface especially for some edge cases.
The end to end workflow with realistic HTTP responses is covered by test_e2e.py
"""

from collections.abc import Callable
from typing import Any, TypeAlias
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
from qiskit.circuit import QuantumCircuit
from qiskit.primitives.containers.estimator_pub import EstimatorPub
from qiskit.primitives.containers.sampler_pub import SamplerPub
from qiskit.quantum_info.operators import SparsePauliOp
from yarl import URL

from prefect_qiskit.exceptions import RuntimeJobFailure
from prefect_qiskit.vendors.ibm_quantum import IBMQuantumCredentials

MockHttpRespSetup: TypeAlias = Callable[..., None]


@pytest.fixture
def mock_http_response(
    monkeypatch: pytest.MonkeyPatch,
) -> MockHttpRespSetup:
    """A factory function of dynamic monkeypatch for request of aiohttp response."""

    def _setup(
        method: str,
        *,
        response_json: dict[str, Any] | None = None,
        raise_exc: Exception | None = None,
    ) -> None:
        # Create mock response
        mock_response_ctx = AsyncMock()
        if raise_exc:
            mock_response_ctx.__aenter__.side_effect = raise_exc
        else:
            mock_resp_obj = MagicMock()
            mock_resp_obj.json = AsyncMock(return_value=response_json)
            mock_response_ctx.__aenter__.return_value = mock_resp_obj
        mock_response_ctx.__aexit__.return_value = None

        # Setup mock session
        mock_session = MagicMock()
        setattr(mock_session, method, MagicMock(return_value=mock_response_ctx))

        # Monkeypatch ClientSession with mock
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_ctx.__aexit__.return_value = None

        monkeypatch.setattr(aiohttp, "ClientSession", MagicMock(return_value=mock_session_ctx))

    return _setup


def test_save_load_quantum_credentials() -> None:
    """Test saving and loading credential block in the prefect server"""
    api_key = "test_api_key"
    crn = "crn:test-name"
    auth_url = "https://some-auth-url.ibm_quantum.com/"
    runtime_url = "https://some-runtime-url.ibm_quantum.com/"

    credentials = IBMQuantumCredentials(
        api_key=api_key,
        crn=crn,
        auth_url=auth_url,
        runtime_url=runtime_url,
    )
    credentials.save("test-block")
    loaded = IBMQuantumCredentials.load("test-block")

    assert loaded.api_key.get_secret_value() == api_key
    assert loaded.crn == crn
    assert loaded.auth_url.unicode_string() == auth_url
    assert loaded.runtime_url.unicode_string() == runtime_url


def test_empty_url() -> None:
    """Test URL of empty string is converted into None."""
    credentials = IBMQuantumCredentials(
        api_key="test_api_key",
        crn="crn:test-name",
        auth_url="",
        runtime_url="",
    )

    assert credentials.auth_url is None
    assert credentials.runtime_url is None


def test_invalid_crn() -> None:
    """Test CRN with invalid format will raise error."""
    crn = "this-is-not-crn"

    with pytest.raises(ValueError):
        IBMQuantumCredentials(
            api_key="test_api_key",
            crn=crn,
        )


@pytest.mark.asyncio(loop_scope="function")
async def test_get_request_error(
    mock_http_response: MockHttpRespSetup,
) -> None:
    """Test IAM token is not accidentally exposed in the error message."""
    FAKE_TOKEN = "this_should_be_secret"

    request_info = aiohttp.RequestInfo(
        url=URL("https://quantum.cloud.ibm.com/api/v1/fake/api"),
        method="GET",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {FAKE_TOKEN}",
            "Service-CRN": "crn:test",
        },
        real_url="https://quantum.cloud.ibm.com/api/v1/fake/api",
    )

    exc = aiohttp.ClientResponseError(
        request_info=request_info,
        history=(),
        status=403,
        message="test-message",
    )

    mock_http_response(
        method="get",
        raise_exc=exc,
    )

    credentials = IBMQuantumCredentials(
        api_key="test_api_key",
        crn="crn:test-name",
    )
    client = credentials.get_client()

    with pytest.raises(RuntimeJobFailure) as exc_info:
        await client.get_resources()

    assert FAKE_TOKEN not in str(exc_info.value)
    assert exc_info.value.retry is True


@pytest.mark.asyncio(loop_scope="function")
async def test_invalid_primitive_inputs(
    mock_http_response: MockHttpRespSetup,
    bell_circ: QuantumCircuit,
) -> None:
    """Test client run_primitive with invalid input data."""
    mock_http_response(
        method="post",
        response_json={
            "id": "test-job-id-123",
            "backend": "ibm_test",
        },
    )

    credentials = IBMQuantumCredentials(
        api_key="test_api_key",
        crn="crn:test-name",
    )
    client = credentials.get_client()

    with pytest.raises(RuntimeJobFailure) as exc_info:
        await client.run_primitive(
            program_id="sampler",
            inputs=[SamplerPub(bell_circ)],
            resource_name="ibm_test",
            options={
                "params": {
                    "options": {
                        "default_shots": "xyz",  # must be integer
                    }
                }
            },
        )

    assert exc_info.value.retry is False


@pytest.mark.asyncio(loop_scope="function")
async def test_primitive_inputs_sampler(
    mock_http_response: MockHttpRespSetup,
    bell_circ: QuantumCircuit,
) -> None:
    """Test client run_primitive with sampler."""
    mock_http_response(
        method="post",
        response_json={
            "id": "test-job-id-123",
            "backend": "ibm_test",
        },
    )

    credentials = IBMQuantumCredentials(
        api_key="test_api_key",
        crn="crn:test-name",
    )
    client = credentials.get_client()

    job_id = await client.run_primitive(
        program_id="sampler",
        inputs=[SamplerPub.coerce(bell_circ)],
        resource_name="ibm_test",
        options={
            "params": {
                "options": {
                    "default_shots": 123,
                }
            }
        },
    )

    assert job_id == "test-job-id-123"


@pytest.mark.asyncio(loop_scope="function")
async def test_primitive_inputs_estimator(
    mock_http_response: MockHttpRespSetup,
    bell_circ: QuantumCircuit,
) -> None:
    """Test client run_primitive with estimator."""
    mock_http_response(
        method="post",
        response_json={
            "id": "test-job-id-123",
            "backend": "ibm_test",
        },
    )

    credentials = IBMQuantumCredentials(
        api_key="test_api_key",
        crn="crn:test-name",
    )
    client = credentials.get_client()

    job_id = await client.run_primitive(
        program_id="estimator",
        inputs=[EstimatorPub.coerce([bell_circ, SparsePauliOp.from_list([("XX", 1), ("YY", 1), ("ZZ", 1)])])],
        resource_name="ibm_test",
        options={
            "params": {
                "options": {
                    "default_precision": 0.123,
                }
            }
        },
    )

    assert job_id == "test-job-id-123"


@pytest.mark.asyncio(loop_scope="function")
async def test_job_fail_1010(
    mock_http_response: MockHttpRespSetup,
) -> None:
    """Test job failure with 1010 error."""
    mock_http_response(
        method="get",
        response_json={
            "status": "Failed",
            "state": {
                "status": "Failed",
                "reason": "Error returned at backend level",
                "reason_code": 1010,
            },
        },
    )

    credentials = IBMQuantumCredentials(
        api_key="test_api_key",
        crn="crn:test-name",
    )
    client = credentials.get_client()

    with pytest.raises(RuntimeJobFailure) as exc_info:
        await client.get_job_status("test-job-id-123")

    # Can retry
    assert exc_info.value.retry is True
    assert exc_info.value.message == (
        "Primitive Job failure (1010); "
        "Job test-job-id-123 failed. "
        "The following causes were reported: Error returned at backend level."
    )


@pytest.mark.asyncio(loop_scope="function")
async def test_job_fail_9999(
    mock_http_response: MockHttpRespSetup,
) -> None:
    """Test job failure with 9999 error."""
    mock_http_response(
        method="get",
        response_json={
            "status": "Failed",
            "state": {
                "status": "Failed",
                "reason": "Internal error",
                "reason_code": 9999,
            },
        },
    )

    credentials = IBMQuantumCredentials(
        api_key="test_api_key",
        crn="crn:test-name",
    )
    client = credentials.get_client()

    with pytest.raises(RuntimeJobFailure) as exc_info:
        await client.get_job_status("test-job-id-123")

    # Avoid retry
    assert exc_info.value.retry is False
    assert exc_info.value.message == (
        "Primitive Job failure (9999); Job test-job-id-123 failed. The following causes were reported: Internal error."
    )
