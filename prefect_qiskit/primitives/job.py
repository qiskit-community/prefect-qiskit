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
"""Prefect integration for Primitive Jobs."""

import asyncio
from typing import Literal

from prefect.blocks.abstract import CredentialsBlock, JobBlock, JobRun
from pydantic import BaseModel, ConfigDict, Field
from qiskit.primitives.containers import PrimitiveResult
from qiskit.primitives.containers.estimator_pub import EstimatorPub
from qiskit.primitives.containers.sampler_pub import SamplerPub

from prefect_qiskit.exceptions import RuntimeJobFailure
from prefect_qiskit.models import AsyncRuntimeClientInterface, JobMetrics
from prefect_qiskit.vendors.qiskit_aer import QiskitAerCredentials


class PrimitiveJobRun(BaseModel, JobRun):
    """
    A handler of running Primitive Job.

    !!! TIP
        You can directly retrieve the result of the job by using Job ID.

        ```python
        from prefect_qiskit.primitives import PrimitiveJobRun
        from prefect_qiskit.vendors.ibm_quantum import IBMQuantumCredentials

        job = PrimitiveJobRun(
            job_id="d0a61oqorbds73c39gt0",
            credentials=IBMQuantumCredentials.load("my-ibm-client"),
        )
        result = await job.fetch_result()
        ```

    Attributes:
        job_id:
            The unique identifier of the running job.
        job_watch_poll_interval:
            The amount of time to wait between Runtime API calls during monitoring.
        credentials:
            A vendor specific credentials that provides a runtime client API.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    job_id: str = Field(
        description="The unique identifier of the running job.",
    )

    job_watch_poll_interval: float = Field(
        default=0.5,
        description="The amount of time to wait between Runtime API calls during monitoring.",
    )

    credentials: CredentialsBlock = Field(
        default_factory=QiskitAerCredentials,
        description="A vendor specific credentials that provides a runtime client API.",
        title="Quantum Runtime Credentials",
    )

    async def fetch_result(self) -> PrimitiveResult:
        """Fetch Qiskit PrimitiveResult object from server."""
        self.logger.info(f"Fetching primitive result from {self.job_id}.")
        client: AsyncRuntimeClientInterface = self.credentials.get_client()

        result = await client.get_primitive_result(
            job_id=self.job_id,
        )
        self.logger.info("Fetch complete.")
        return result

    async def fetch_metrics(self) -> JobMetrics:
        """Fetch JobMetrics object from server."""
        self.logger.info(f"Fetching job metrics from {self.job_id}.")
        client: AsyncRuntimeClientInterface = self.credentials.get_client()

        metrics = await client.get_job_metrics(
            job_id=self.job_id,
        )
        self.logger.info("Fetch complete.")
        return metrics

    async def wait_for_completion(self):
        """Asynchronously wait for the job to complete."""
        self.logger.info(f"Watching job ID {self.job_id}.")
        client: AsyncRuntimeClientInterface = self.credentials.get_client()

        while await client.get_job_status(self.job_id) != "COMPLETED":
            await asyncio.sleep(self.job_watch_poll_interval)
        self.logger.info("Job succeeded.")


class PrimitiveJob(JobBlock):
    """
    Prefect-style definition of a single primitive job.

    Although the job handling logic is backend-agnostic,
    users can provide vendor-specific credentials and execution options
    to communicate with target hardware via the runtime client API.

    Attributes:
        resource_name:
            A target hardware name available with the given credentials.
        credentials:
            A vendor specific credentials that provides a runtime client API.
        primitive_blocs:
            Canonical Qiskit Primitive Unified Blocs data.
        options:
            A vendor specific execution options for primitives.
        program_type:
            Reserved primitive name to run on runtime client API.
        job_watch_poll_interval:
            The amount of time to wait between runtime client API calls during monitoring.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    resource_name: str = Field(
        description="A target hardware name available with the given credentials.",
    )

    credentials: CredentialsBlock = Field(
        default_factory=QiskitAerCredentials,
        description="A vendor specific credentials that provides a runtime client API.",
        title="Quantum Runtime Credentials",
    )

    primitive_blocs: list[SamplerPub] | list[EstimatorPub] = Field(
        description="Canonical Qiskit Primitive Unified Blocs data.",
    )

    options: dict | None = Field(
        default_factory=dict,
        description="A vendor specific execution options for primitives.",
    )

    program_type: Literal["estimator", "sampler"] = Field(
        description="Reserved primitive name to run on runtime client API.",
    )

    job_watch_poll_interval: float = Field(
        default=0.5,
        description="The amount of time to wait between runtime client API calls during monitoring.",
    )

    async def trigger(self) -> PrimitiveJobRun:
        """
        Triggers a job run in an external service and returns a PrimitiveJobRun object
        to track the execution of the run.
        """
        client: AsyncRuntimeClientInterface = self.credentials.get_client()

        if not await client.check_resource_available(resource_name=self.resource_name):
            raise RuntimeJobFailure(
                reason=f"Resource {self.resource_name} is not currently available.",
                job_id=None,
                retry=True,
            )

        self.logger.info(f"Initializing Primitive Job using {self.credentials.get_block_type_name()}.")

        job_id = await client.run_primitive(
            program_id=self.program_type,
            inputs=self.primitive_blocs,
            resource_name=self.resource_name,
            options=self.options or {},
        )

        return PrimitiveJobRun(
            job_id=job_id,
            job_watch_poll_interval=self.job_watch_poll_interval,
            credentials=self.credentials,
        )
