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
"""
This module provides an abstraction layer for managing the execution of Qiskit Primitives.
Execution is managed by a Prefect task behind the scenes, enhancing system error resilience.

The runtime supports both synchronous and asynchronous execution of primitives.
Asynchronous execution is particularly efficient for I/O-bound tasks,
typical in client-server remote computing scenarios.

Users must supply Prefect credential blocks for the specific vendor to run on the target hardware.
"""

import asyncio
from functools import partial

from prefect._internal.compatibility.async_dispatch import async_dispatch
from prefect.blocks.core import Block
from prefect.cache_policies import NO_CACHE, CacheKeyFnPolicy
from prefect.tasks import Task
from prefect.utilities.asyncutils import run_coro_as_sync
from pydantic import Field, model_validator
from qiskit.primitives import PrimitiveResult
from qiskit.primitives.containers.estimator_pub import EstimatorPub, EstimatorPubLike
from qiskit.primitives.containers.sampler_pub import SamplerPub, SamplerPubLike
from qiskit.transpiler import Target
from typing_extensions import Self

from prefect_qiskit.models import AsyncRuntimeClientInterface
from prefect_qiskit.primitives.runner import retry_on_failure, run_primitive
from prefect_qiskit.utils.pub_hasher import pub_hasher
from prefect_qiskit.vendors import QiskitAerCredentials, QuantumCredentialsT

# A prefix of cached result file name when the cache mode is enabled.
CACHE_PREFIX = "qiskit-primitive-"


class QuantumRuntime(Block):
    """
    Prefect Block used to execute Qiskit Primitives on quantum computing resources.
    Quantum Runtime is a vendor agnostic implementation of primitive execution.

    Attributes:
        resource_name:
            Name of a quantum computing resource available with your credentials.
            Input value is validated and an error is raised when the resource name is not found.
        credentials:
            Credentials to access the quantum computing resource from a target vendor.
        enable_job_analytics:
            Enable quantum job analytics.
            When analytics is enabled, each primitive execution will create
            a table artifact 'job-metrics' that reports various
            execution metrics the vendor provides as a job metadata.
        max_retry:
            Maximum number of primitive execution retry on failure.
            Primitive execution raises an error after all executions fail or
            the error is not retryable.
        retry_delay:
            Standby time in seconds before creating new execution task on failure.
            This setting is applied only if the maximum retry is nonzero.
        timeout:
            Primitive execution timeout in seconds.
            Execution task will raise TaskRunTimeoutError after timeout.
            If the maximum number of reruns has not been reached,
            the error is also suppressed and new execution task is created.
        execution_cache:
            Cache primitive execution result in a local file system.
            A cache key is computed from the input Primitive Unified Blocs, options, and resource name.
            Overhead of the primitive operands evaluation is incurred.

    Example:
        Load stored Quantum Runtime and run Qiskit sampler primitive.

        ```python
        from prefect_qiskit.runtime import QuantumRuntime
        from qiskit.circuit import QuantumCircuit
        from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager

        runtime = QuantumRuntime.load("BLOCK_NAME")

        vqc = QuantumCircuit(2)
        vqc.h(0)
        vqc.cx(0, 1)
        vqc.measure_all()

        pm = generate_preset_pass_manager(optimization_level=2, target=runtime.get_target())

        result = runtime.sampler(pm.run([vqc]))
        ```
    """

    _logo_url = "https://avatars.githubusercontent.com/u/30696987?s=200&v=4"
    _block_type_name = "Quantum Runtime"
    _block_type_slug = "quantum-runtime"

    resource_name: str = Field(
        description=(
            "Name of a quantum computing resource available with your credentials. "
            "Input value is validated and an error is raised when the resource name is not found."
        ),
        title="Resource Name",
    )

    credentials: QuantumCredentialsT = Field(
        default_factory=QiskitAerCredentials,
        description="Credentials to access the quantum computing resource from a target vendor. ",
        title="Quantum Runtime Credentials",
    )

    enable_job_analytics: bool = Field(
        default=True,
        description=(
            "Enable quantum job analytics. "
            "When analytics is enabled, each primitive execution will create a table artifact 'job-metrics' "
            "that reports various execution metrics the vendor provides as a job metadata."
        ),
        title="Job Analytics",
    )

    max_retry: int = Field(
        default=5,
        description=(
            "Maximum number of primitive execution retry on failure. "
            "Primitive execution raises an error after all executions fail or "
            "the error is not retryable."
        ),
        title="Max Primitive Retry",
        ge=0,
    )

    retry_delay: int = Field(
        default=300,
        description=(
            "Standby time in seconds before creating new execution task on failure. "
            "This setting is applied only if the maximum retry is nonzero."
        ),
        title="Retry Delay",
        ge=0,
    )

    timeout: int | None = Field(
        default=None,
        description=(
            "Primitive execution timeout in seconds. "
            "Execution task will raise TaskRunTimeoutError after timeout. "
            "If the maximum number of reruns has not been reached, "
            "the error is also suppressed and new execution task is created."
        ),
        title="Execution Timeout",
        ge=0,
    )

    execution_cache: bool = Field(
        default=False,
        description=(
            "Cache primitive execution result in a local file system. "
            "A cache key is computed from the input Primitive Unified Blocs, options, and resource name. "
            "Overhead of the primitive operands evaluation is incurred. "
        ),
        title="Execution Cache",
    )

    @model_validator(mode="after")
    def check_resource(self) -> Self:
        client: AsyncRuntimeClientInterface = self.credentials.get_client()

        allowed_list = run_coro_as_sync(client.get_resources())
        if self.resource_name not in allowed_list:
            raise ValueError(
                f"Resource name {self.resource_name} is not available under your account. "
                f"Following resources are available: {', '.join(allowed_list)}."
            )
        return self

    async def async_get_target(
        self,
    ) -> Target:
        """Asynchronously get Qiskit Target of specific backend.

        Returns:
            Qiskit Target object.
        """
        client: AsyncRuntimeClientInterface = self.credentials.get_client()
        return await client.get_target(self.resource_name)

    @async_dispatch(async_get_target)
    def get_target(self) -> Target:
        """Get Qiskit Target of specific backend.

        Returns:
            Qiskit Target object.
        """
        client: AsyncRuntimeClientInterface = self.credentials.get_client()
        coro = client.get_target(self.resource_name)
        return asyncio.run(coro)

    async def async_sampler(
        self,
        sampler_pubs: list[SamplerPubLike],
        options: dict | None = None,
        tags: list[str] | None = None,
    ) -> PrimitiveResult:
        """Asynchronously run sampler primitive.

        Args:
            sampler_pubs: Operands of sampler primitive.
            options: Vendor-specific primitive options.
            tags: Arbitrary labels to add to the Primitive task tags of execution.

        Returns:
            Qiskit PrimitiveResult object.
        """
        opted_run_primitive = self.build_runner_task(tags=tags)

        return await opted_run_primitive(
            primitive_blocs=list(map(SamplerPub.coerce, sampler_pubs)),
            program_type="sampler",
            options=options,
        )

    @async_dispatch(async_sampler)
    def sampler(
        self,
        sampler_pubs: list[SamplerPubLike],
        options: dict | None = None,
        tags: list[str] | None = None,
    ) -> PrimitiveResult:
        """Run sampler primitive.

        Args:
            sampler_pubs: Operands of sampler primitive.
            options: Vendor-specific primitive options.
            tags: Arbitrary labels to add to the Primitive task tags of execution.

        Returns:
            Qiskit PrimitiveResult object.
        """
        opted_run_primitive = self.build_runner_task(tags=tags)

        coro = opted_run_primitive(
            primitive_blocs=list(map(SamplerPub.coerce, sampler_pubs)),
            program_type="sampler",
            options=options,
        )
        return asyncio.run(coro)

    async def async_estimator(
        self,
        estimator_pubs: list[SamplerPubLike],
        options: dict | None = None,
        tags: list[str] | None = None,
    ) -> PrimitiveResult:
        """Asynchronously run estimator primitive.

        Args:
            estimator_pubs: Operands of estimator primitive.
            options: Vendor-specific primitive options.
            tags: Arbitrary labels to add to the Primitive task tags of execution.

        Returns:
            Qiskit PrimitiveResult object.
        """
        opted_run_primitive = self.build_runner_task(tags=tags)

        return await opted_run_primitive(
            primitive_blocs=list(map(EstimatorPub.coerce, estimator_pubs)),
            program_type="estimator",
            options=options,
        )

    @async_dispatch(async_estimator)
    def estimator(
        self,
        estimator_pubs: list[EstimatorPubLike],
        options: dict | None = None,
        tags: list[str] | None = None,
    ) -> PrimitiveResult:
        """Run estimator primitive.

        Args:
            estimator_pubs: Operands of estimator primitive.
            options: Vendor-specific primitive options.
            tags: Arbitrary labels to add to the Primitive task tags of execution.

        Returns:
            Qiskit PrimitiveResult object.
        """
        opted_run_primitive = self.build_runner_task(tags=tags)

        coro = opted_run_primitive(
            primitive_blocs=list(map(EstimatorPub.coerce, estimator_pubs)),
            program_type="estimator",
            options=options,
        )
        return asyncio.run(coro)

    def build_runner_task(
        self,
        **kwargs,
    ) -> Task:
        """Build Prefect Task object that runs primitive.

        Args:
            kwargs: Keyword arguments to instantiate Prefect Task.

        Returns:
            A configured prefect task.
        """
        configured_runner = partial(
            run_primitive,
            resource_name=self.resource_name,
            credentials=self.credentials,
            enable_analytics=self.enable_job_analytics,
        )

        if self.execution_cache:
            kwargs.update(
                {
                    "cache_policy": CacheKeyFnPolicy(cache_key_fn=_primitive_cache),
                    "persist_result": True,
                    "result_serializer": "compressed/pickle",
                }
            )
        else:
            kwargs.update(
                {
                    "cache_policy": NO_CACHE,
                    "persist_result": False,
                }
            )

        return Task(
            fn=configured_runner,
            name="run_primitive",
            retries=self.max_retry,
            retry_delay_seconds=self.retry_delay,
            timeout_seconds=self.timeout,
            retry_condition_fn=retry_on_failure,
            **kwargs,
        )


def _primitive_cache(_, parameters) -> str:
    key = pub_hasher(
        pubs=parameters["primitive_blocs"],
        options=parameters["options"],
        resource_name=parameters["resource_name"],
    )
    return CACHE_PREFIX + key
