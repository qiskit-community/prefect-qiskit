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
"""Adaptor for Qiskit Aer simulator."""

import asyncio
import os
import pickle
import uuid
from datetime import datetime
from typing import Any, Literal

from diskcache import Cache
from prefect.settings import PREFECT_HOME
from qiskit.primitives.backend_estimator_v2 import BackendEstimatorV2
from qiskit.primitives.backend_sampler_v2 import BackendSamplerV2
from qiskit.primitives.containers import PrimitiveResult
from qiskit.primitives.containers.estimator_pub import EstimatorPub
from qiskit.primitives.containers.sampler_pub import SamplerPub
from qiskit.providers.backend import BackendV2
from qiskit.transpiler.target import Target

from prefect_qiskit.exceptions import RuntimeJobFailure
from prefect_qiskit.models import JOB_STATUS, JobMetrics
from prefect_qiskit.utils.logging import LoggingMixin

DISK_CACHE: Cache = Cache(os.path.join(PREFECT_HOME.value(), "qiskit"))


class QiskitAerClient(LoggingMixin):
    """Local quantum runtime implemented with the Qiskit Aer simulator.

    Service queue is emulated by using a file system and Python asyncio.
    Job data is locally stored in an SQL database created in the Prefect home directory.
    When a job starts, it writes an entry in the database and spawns a new thread for simulation.
    The thread updates the database with results after the circuit simulation completes.

    Since job data is locally stored in the file system,
    a client can access the job data from child processes and threads.

    Note that jobs are processed sequentially because the Aer simulator uses
    the thread executor by default and this client also uses a thread-based parallerism.
    You can use this client with a process executor to run primitives concurrently.
    """

    NAME = "aer_simulator"

    def __init__(
        self,
        backend: BackendV2,
    ):
        """Create new Runtime API client."""
        self._backend = backend

    async def check_resource_available(
        self,
        resource_name: str,
    ) -> bool:
        if resource_name != self.NAME:
            raise RuntimeJobFailure(
                f"Resource name must be '{self.NAME}' for Qiskit Aer client.",
                retry=False,
            )
        return True

    async def get_resources(
        self,
    ) -> list[str]:
        return [self.NAME]

    async def get_target(
        self,
        resource_name: str,
    ) -> Target:
        if resource_name != self.NAME:
            raise RuntimeJobFailure(
                f"Resource name must be '{self.NAME}' for Qiskit Aer client.",
                retry=False,
            )
        return self._backend.target

    async def run_primitive(
        self,
        program_id: Literal["sampler", "estimator"],
        inputs: list[SamplerPub] | list[EstimatorPub],
        resource_name: str,
        options: dict[str, Any],
    ) -> str:
        if resource_name != self.NAME:
            raise RuntimeJobFailure(
                f"Resource name must be '{self.NAME}' for Qiskit Aer client.",
                retry=False,
            )
        match program_id:
            case "sampler":
                backend_primitive = BackendSamplerV2(
                    backend=self._backend,
                    options=options,
                )
            case "estimator":
                backend_primitive = BackendEstimatorV2(
                    backend=self._backend,
                    options=options,
                )
            case _:
                raise Exception("Unreachable")

        job_id = create_job_id()
        self.logger.info(f"Job started with job ID {job_id}.")

        # Run in a child thread
        job_status = {
            "results": None,
            "status": "QUEUED",
            "msg": None,
            "created": datetime.now(),
            "running": None,
            "finished": None,
        }
        DISK_CACHE.add(job_id, job_status)
        asyncio.create_task(
            coro=execute_primitive(backend_primitive, inputs, job_id),
            name=job_id,
        )
        return job_id

    async def get_primitive_result(
        self,
        job_id: str,
    ) -> PrimitiveResult:
        try:
            job_status = DISK_CACHE[job_id]
        except KeyError as ex:
            raise RuntimeError(f"Job ID {job_id} is not found") from ex
        return pickle.loads(job_status["result"])

    async def get_job_status(
        self,
        job_id: str,
    ) -> JOB_STATUS:
        try:
            job_status = DISK_CACHE[job_id]
        except KeyError as ex:
            raise RuntimeError(f"Job ID {job_id} is not found") from ex
        if job_status["status"] == "FAILED":
            raise RuntimeJobFailure(
                reason=job_status.get("msg", None),
                job_id=job_id,
                retry=False,
            )
        return job_status["status"]

    async def get_job_metrics(
        self,
        job_id: str,
    ) -> JobMetrics:
        try:
            job_status = DISK_CACHE[job_id]
        except KeyError as ex:
            raise RuntimeError(f"Job ID {job_id} is not found") from ex

        return JobMetrics(
            qpu_usage=0,
            timestamp_created=job_status.get("created", None),
            timestamp_started=job_status.get("running", None),
            timestamp_completed=job_status.get("finished", None),
        )


async def execute_primitive(
    primitive: BackendSamplerV2 | BackendEstimatorV2,
    inputs: list[SamplerPub] | list[EstimatorPub],
    job_id: str,
) -> None:
    try:
        job_status = DISK_CACHE[job_id]
    except KeyError as ex:
        raise RuntimeError(f"Job ID {job_id} is not initialized") from ex

    job = primitive.run(inputs)
    job_status.update(
        {
            "status": "RUNNING",
            "running": datetime.now(),
        }
    )
    DISK_CACHE.set(job_id, job_status)
    try:
        result = job.result()
        job_status.update(
            {
                "result": pickle.dumps(result),
                "status": "COMPLETED",
                "finished": datetime.now(),
            }
        )
    except Exception as ex:
        job_status.update(
            {
                "msg": str(ex),
                "status": "FAILED",
                "finished": datetime.now(),
            }
        )
    finally:
        DISK_CACHE.set(job_id, job_status)


def create_job_id() -> str:
    return uuid.uuid4().hex
