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
"""Adaptor for Qiskit IBM Runtime Client.

See the following link for the REST API specification.
https://quantum.cloud.ibm.com/docs/en/api/qiskit-runtime-rest#qiskit-runtime-rest-api
"""

import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Literal

import aiohttp
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from pydantic import SecretStr, ValidationError
from qiskit.primitives.containers import PrimitiveResult
from qiskit.primitives.containers.estimator_pub import EstimatorPub
from qiskit.primitives.containers.sampler_pub import SamplerPub
from qiskit.transpiler.target import Target
from qiskit_ibm_runtime.models import BackendConfiguration, BackendProperties
from qiskit_ibm_runtime.utils.backend_converter import convert_to_target
from qiskit_ibm_runtime.utils.json import RuntimeEncoder
from qiskit_ibm_runtime.utils.result_decoder import ResultDecoder

from prefect_qiskit.exceptions import RuntimeJobFailure
from prefect_qiskit.models import JOB_STATUS, JobMetrics
from prefect_qiskit.utils.logging import LoggingMixin
from prefect_qiskit.vendors.ibm_quantum.models import EstimatorV2Schema, SamplerV2Schema

DEFAULT_AUTH_URL: str = "https://iam.cloud.ibm.com"
DEFAULT_RUNTIME_URL: str = "https://quantum.cloud.ibm.com/api/v1/"


@asynccontextmanager
async def runtime_session_ctx(
    client: "IBMQuantumPlatformClient",
    timeout: int = 30,
) -> AsyncGenerator[aiohttp.ClientSession, None]:
    """Asynchronous HTTP session context with error handling.

    Automatically add authentication and CRN in the HTTP request header.
    Catch client error not to print sensitive header in the stack trace.
    """
    timeout = aiohttp.ClientTimeout(total=timeout)
    headers = {
        "IBM-API-Version": "2025-01-01",
        "Accept": "application/json",
        "Authorization": f"Bearer {client.auth.token_manager.get_token()}",
        "Service-CRN": client.crn,
    }
    try:
        async with aiohttp.ClientSession(
            timeout=timeout,
            headers=headers,
            base_url=client.runtime_endpoint_url,
            raise_for_status=True,
        ) as session:
            yield session
    except aiohttp.ClientResponseError as ex:
        raise RuntimeJobFailure(
            reason=f"HTTP {ex.status} on {ex.request_info.url}.",
            retry=True,
        ) from None
    except aiohttp.ClientConnectionError:
        raise RuntimeJobFailure(
            reason=f"Connection failed to {client.runtime_endpoint_url}.",
            retry=True,
        ) from None
    except TimeoutError:
        raise RuntimeJobFailure(
            reason="HTTP request timed out.",
            retry=True,
        ) from None
    except aiohttp.ClientError as ex:
        raise RuntimeJobFailure(
            reason=f"General HTTP client error {ex.__class__.__name__}.",
            retry=True,
        ) from None


class IBMQuantumPlatformClient(LoggingMixin):
    """Adaptor interface for IBM Quantum Platform cloud client."""

    AVOID_RETRY = [9999]

    def __init__(
        self,
        api_key: SecretStr,
        crn: str,
        auth_endpoint_url: str = DEFAULT_AUTH_URL,
        runtime_endpoint_url: str = DEFAULT_RUNTIME_URL,
    ):
        """Create new client.

        Args:
            api_key: API key to access cloud platform.
            crn: Cloud resource name to identify the service to use.
            auth_endpoint_url: Endpoint URL for IAM authentication service.
            api_endpoint_url: Endpoint URL for IBM Qiskit Runtime REST API.
        """
        self.auth = IAMAuthenticator(
            apikey=api_key.get_secret_value(),
            url=auth_endpoint_url,
        )
        self.crn = crn
        self.runtime_endpoint_url = runtime_endpoint_url

    async def check_resource_available(
        self,
        resource_name: str,
    ) -> bool:
        async with runtime_session_ctx(self) as session:
            async with session.get(f"backends/{resource_name}/status") as resp:
                self.logger.debug(f"GET request for {resp.url}")
                ret = await resp.json()
        return ret.get("state", False)

    async def get_resources(
        self,
    ) -> list[str]:
        async with runtime_session_ctx(self) as session:
            async with session.get("backends") as resp:
                self.logger.debug(f"GET request for {resp.url}")
                ret = await resp.json()
        devices = ret.get("devices", [])
        return [d["name"] for d in devices if d["status"]["name"] == "online"]

    async def get_target(
        self,
        resource_name: str,
    ) -> Target:
        async with runtime_session_ctx(self) as session:
            async with session.get(f"backends/{resource_name}/configuration") as resp:
                self.logger.debug(f"GET request for {resp.url}")
                configuration_dict = await resp.json()
            async with session.get(f"backends/{resource_name}/properties") as resp:
                self.logger.debug(f"GET request for {resp.url}")
                properties_dict = await resp.json()
        return convert_to_target(
            configuration=BackendConfiguration.from_dict(configuration_dict),
            properties=BackendProperties.from_dict(properties_dict),
        )

    async def run_primitive(
        self,
        program_id: Literal["sampler", "estimator"],
        inputs: list[SamplerPub] | list[EstimatorPub],
        resource_name: str,
        options: dict[str, Any],
    ) -> str:
        payload = {
            "program_id": None,
            "backend": resource_name,
            **options,
        }
        if "params" in payload:
            params = payload.pop("params").copy()
        else:
            params = {}
        params.update(
            {
                "support_qiskit": True,
                "version": 2,
            }
        )
        match program_id:
            case "sampler":
                params["pubs"] = [
                    [
                        pub.circuit,
                        pub.parameter_values.as_array(pub.circuit.parameters),
                        pub.shots,
                    ]
                    for pub in inputs
                ]
                try:
                    SamplerV2Schema.model_validate(params)
                except ValidationError as ex:
                    raise RuntimeJobFailure(
                        "Primitive input doesn't match the data schema for Runtime REST API.",
                        retry=False,
                    ) from ex
                payload["program_id"] = "sampler"
                payload["params"] = params
            case "estimator":
                params["pubs"] = [
                    [
                        pub.circuit,
                        pub.observables.tolist(),
                        pub.parameter_values.as_array(pub.circuit.parameters),
                        pub.precision,
                    ]
                    for pub in inputs
                ]
                try:
                    EstimatorV2Schema.model_validate(params)
                except ValidationError as ex:
                    raise RuntimeJobFailure(
                        "Primitive input doesn't match the data schema for Runtime REST API.",
                        retry=False,
                    ) from ex
                payload["program_id"] = "estimator"
                payload["params"] = params
            case _:
                raise Exception("Unreachable")
        self.logger.debug(f"Submitting the following payload: {payload}")
        data = json.dumps(payload, cls=RuntimeEncoder)

        async with runtime_session_ctx(self, timeout=900) as session:
            async with session.post("jobs", data=data) as resp:
                self.logger.debug(f"POST request for {resp.url}")
                ret = await resp.json()

        if job_id := ret.get("id", None):
            self.logger.info(f"Job started with job ID {job_id}.")
        else:
            raise RuntimeJobFailure(
                reason="Server didn't return Job ID.",
                retry=True,
            )
        return job_id

    async def get_primitive_result(
        self,
        job_id: str,
    ) -> PrimitiveResult:
        async with runtime_session_ctx(self) as session:
            async with session.get(f"jobs/{job_id}/results") as resp:
                self.logger.debug(f"GET request for {resp.url}")
                ret = await resp.text()
        # Assume job ID is valid.
        # This is true as long as job is not exposed to user program.
        results = ResultDecoder.decode(ret)

        if spans := results.metadata.pop("execution", {}).pop("execution_spans", {}):
            # Remove execution span object
            # Add a simple dictionary instead to avoid IBM specific contexts
            for res, span in zip(results, spans):
                span_info = {
                    "timestamp_start": span.start.isoformat(),
                    "timestamp_completed": span.stop.isoformat(),
                    "duration": span.duration,
                }
                res.metadata["span"] = span_info
        return results

    async def get_job_status(
        self,
        job_id: str,
    ) -> JOB_STATUS:
        async with runtime_session_ctx(self) as session:
            async with session.get(f"jobs/{job_id}") as resp:
                self.logger.debug(f"GET request for {resp.url}")
                ret = await resp.json()
        job_state = ret.get("state", {})

        match status := ret.get("status", "unknown").upper():
            case "QUEUED" | "RUNNING" | "COMPLETED":
                return status
            case "CANCELLED - RAN TOO LONG":
                raise RuntimeJobFailure(
                    reason="Job ran longer than maximum execution time.",
                    job_id=job_id,
                    error_code=job_state.get("reason_code", None),
                    retry=True,
                )
            case "CANCELLED":
                raise RuntimeJobFailure(
                    reason="Job is manually cancelled.",
                    job_id=job_id,
                    retry=False,
                )
            case "FAILED":
                msg_parts = [f"Job {job_id} failed"]
                if reason := job_state.get("reason", None):
                    msg_parts.append(f"The following causes were reported: {reason}")
                if sol := job_state.get("reason_solution", None):
                    msg_parts.append(f"Please consider suggested solution: {sol}")
                msg = ". ".join(msg_parts)
                if not msg.endswith("."):
                    msg += "."
                code = job_state.get("reason_code", None)
                raise RuntimeJobFailure(
                    reason=msg,
                    job_id=job_id,
                    error_code=code,
                    retry=code is not None and code not in self.AVOID_RETRY,
                )
            case _:
                raise RuntimeJobFailure(
                    reason=f"Unknown job status reported '{status}'.",
                    job_id=job_id,
                    retry=True,
                )

    async def get_job_metrics(
        self,
        job_id: str,
    ) -> JobMetrics:
        async with runtime_session_ctx(self) as session:
            async with session.get(f"jobs/{job_id}/metrics") as resp:
                self.logger.debug(f"GET request for {resp.url}")
                ret = await resp.json()

        if "timestamps" in ret:
            try:
                created_dt = datetime.fromisoformat(ret["timestamps"].get("created", None))
            except (ValueError, TypeError):
                created_dt = None
            try:
                running_dt = datetime.fromisoformat(ret["timestamps"].get("running", None))
            except (ValueError, TypeError):
                running_dt = None
            try:
                finished_dt = datetime.fromisoformat(ret["timestamps"].get("finished", None))
            except (ValueError, TypeError):
                finished_dt = None

        return JobMetrics(
            qpu_usage=ret.get("usage", {}).get("quantum_seconds", None),
            timestamp_created=created_dt,
            timestamp_started=running_dt,
            timestamp_completed=finished_dt,
        )
