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
"""Protocol for vendor-specific client interface."""

from typing import Any, Literal, Protocol, runtime_checkable

from qiskit.primitives.containers import PrimitiveResult
from qiskit.primitives.containers.estimator_pub import EstimatorPub
from qiskit.primitives.containers.sampler_pub import SamplerPub
from qiskit.transpiler.target import Target

from prefect_qiskit.models.data import JobMetrics

JOB_STATUS = Literal["QUEUED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"]
"""Reserved status string of runtime job."""


@runtime_checkable
class AsyncRuntimeClientInterface(Protocol):
    """Interface abstraction of runtime client API version 1.

    A hardware vendor must provide a credential Block along with its API client
    that implements all the interfaces defined with this protocol.
    """

    async def check_resource_available(
        self,
        resource_name: str,
    ) -> bool:
        """Asynchronously check whether the target resource is currently available.

        Args:
            resource_name: Name of quantum computing resource.

        Returns:
            True when resource is currently available.
        """
        ...

    async def get_resources(
        self,
    ) -> list[str]:
        """Asynchronously list available resource names for this client.

        Returns:
            A list of resource names under this account.
        """
        ...

    async def get_target(
        self,
        resource_name: str,
    ) -> Target:
        """Asynchronously get Qiskit Target for a specific computing resource.

        Args:
            resource_name: Name of quantum computing resource.

        Returns:
            Qiskit Target.
        """
        ...

    async def run_primitive(
        self,
        program_id: Literal["sampler", "estimator"],
        inputs: list[SamplerPub] | list[EstimatorPub],
        resource_name: str,
        options: dict[str, Any],
    ) -> str:
        """Asynchronously send Primitive Blocs via Runtime API and return Job ID.

        Args:
            program_id: Type of primitive to use.
            inputs: Qiskit Pub payloads that the primitive API will digest.
            resource_name: Name of quantum computing resource.
            options: Execution options.

        Returns:
            Job ID.
        """
        ...

    async def get_primitive_result(
        self,
        job_id: str,
    ) -> PrimitiveResult:
        """Asynchronously get Qiskit PrimitiveResult object from complete Job ID.

        Args:
            job_id: Unique identifier of the job.

        Returns:
            Qiskit PrimitiveResult object.
        """
        ...

    async def get_job_status(
        self,
        job_id: str,
    ) -> JOB_STATUS:
        """Asynchronously get status string of Job ID.

        !!! NOTE
            This function raises error immediately when a job failure occurs.
            A client must inspect whether the job is retriable or not.
            In case the job is retriable, a downstream primitive runner will
            resubmit the same job data to the server.

        Args:
            job_id: Unique identifier of the job.

        Raises:
            RuntimeJobFailure: When job execution fails.

        Returns:
            Job status literal.
        """
        ...

    async def get_job_metrics(
        self,
        job_id: str,
    ) -> JobMetrics:
        """Asynchronously get metrics of Job.

        Args:
            job_id: Unique identifier of the job.

        Returns:
            Execution metrics of the job when available.
        """
        ...
