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
"""Core primitive runner."""

from typing import Literal

from prefect import task
from prefect.artifacts import create_table_artifact
from prefect.blocks.abstract import CredentialsBlock
from prefect.context import TaskRunContext
from prefect.logging import get_run_logger
from prefect.task_engine import TaskRunTimeoutError
from qiskit.primitives.containers import PrimitiveResult
from qiskit.primitives.containers.estimator_pub import EstimatorPub
from qiskit.primitives.containers.sampler_pub import SamplerPub

from prefect_qiskit.exceptions import RuntimeJobFailure
from prefect_qiskit.models import JobMetrics
from prefect_qiskit.primitives.job import PrimitiveJob


async def retry_on_failure(_task, _task_run, state):
    try:
        await state.result()
    except RuntimeJobFailure as ex:
        # Rerun job only when the system failure is temporary reason
        return ex.retry
    except TaskRunTimeoutError:
        # Prefect task timeout, maybe network/queue issue
        return True
    except Exception:
        return False


# TODO integration of metrics database
# TODO automatic job split (workflow optimization)


@task(
    name="run_primitive",
    retry_condition_fn=retry_on_failure,
)
async def run_primitive(
    *,
    primitive_blocs: list[SamplerPub] | list[EstimatorPub],
    program_type: Literal["sampler", "estimator"],
    resource_name: str,
    credentials: CredentialsBlock,
    enable_analytics: bool = True,
    options: dict | None = None,
) -> PrimitiveResult:
    """
    This function implements a Prefect task to manage the execution of
    Qiskit Primitives on an abstract layer,
    providing built-in execution failure protection.

    It accepts PUBs and options, submitting this data to quantum computers via the vendor's API.
    The response is formatted into a Qiskit PrimitiveResult instance.

    If the job is successful and the `enable_analytics` flag is set,
    the task will analyze job metadata,
    create a job-metrics artifact, and save it on the Prefect server.

    Args:
        primitive_blocs: Input sampler PUBs.
        program_type: Primitive ID.
        resource_name: Quantum computing resource.
        credentials: Runtime API credentials.
        enable_analytics: Set True to generate table artifact of job metrics.
        options: Vendor-specific primitive options.

    Returns:
        Qiskit PrimitiveResult object.
    """
    context = TaskRunContext.get()

    job = PrimitiveJob(
        resource_name=resource_name,
        credentials=credentials,
        primitive_blocs=primitive_blocs,
        options=options,
        program_type=program_type,
    )
    job_run = await job.trigger()
    await job_run.wait_for_completion()
    result = await job_run.fetch_result()

    if enable_analytics:
        logger = get_run_logger()
        logger.info("Collecting execution metrics from Job.")

        job_metrics_dict = _make_analytics(
            resource_name=resource_name,
            program_type=program_type,
            job_id=job_run.job_id,
            tags=sorted(context.task.tags),
            primitive_blocs=primitive_blocs,
            results=result,
            metrics=await job_run.fetch_metrics(),
            options=options,
        )

        # Create table artifact
        _ = await create_table_artifact(
            table=[list(job_metrics_dict.keys()), list(job_metrics_dict.values())],
            key="job-metrics",
            description=f"Metrics of primitive run {context.task_run.id} / {context.task_run.name}",
        )

    return result


def _make_analytics(
    resource_name: str,
    program_type: str,
    job_id: str,
    tags: list[str],
    primitive_blocs: list[SamplerPub] | list[EstimatorPub],
    results: PrimitiveResult,
    metrics: JobMetrics,
    options: dict | None = None,
) -> dict:
    assert len(primitive_blocs) == len(results)

    created_dt = metrics.timestamp_created
    started_dt = metrics.timestamp_started
    completed_dt = metrics.timestamp_completed
    if created_dt is not None and started_dt is not None:
        span_queue = (started_dt - created_dt).total_seconds()
    else:
        span_queue = None
    if started_dt is not None and completed_dt is not None:
        span_work = (completed_dt - started_dt).total_seconds()
    else:
        span_work = None
    if span_work is not None and metrics.qpu_usage is not None:
        try:
            work_efficiency = round(metrics.qpu_usage / span_work * 100, 1)
        except ZeroDivisionError:
            work_efficiency = 100
    else:
        work_efficiency = None

    # Overall job information
    job_metrics_dict = {
        "resource": resource_name,
        "program_type": program_type,
        "num_pubs": len(primitive_blocs),
        "job_id": job_id,
        "tags": tags,
        "timestamp.created": created_dt.isoformat() if created_dt else None,
        "timestamp.started": started_dt.isoformat() if started_dt else None,
        "timestamp.completed": completed_dt.isoformat() if completed_dt else None,
        "span.queue": span_queue,
        "span.work": span_work,
        "span.qpu": metrics.qpu_usage,
        "work_efficiency": work_efficiency,
    }

    # PUB specific information
    for i, (primitive_bloc, result) in enumerate(zip(primitive_blocs, results)):
        span = result.metadata.get("span", {})
        job_metrics_dict.update(
            {
                f"pub[{i}].circuit.depth": primitive_bloc.circuit.depth(),
                f"pub[{i}].circuit.size": primitive_bloc.circuit.size(),
                f"pub[{i}].shape": primitive_bloc.shape,
                f"pub[{i}].timestamp.started": span.get("timestamp_start", None),
                f"pub[{i}].timestamp.completed": span.get("timestamp_completed", None),
                f"pub[{i}].duration": span.get("duration", None),
            }
        )

    # Execution options
    flat_options = _flatten_options({"options": options}).items()
    job_metrics_dict.update(flat_options)

    return job_metrics_dict


def _flatten_options(d, parent_key=""):
    flattened = {}

    for k, v in d.items():
        new_key = f"{parent_key}.{k}" if parent_key else k
        if isinstance(v, dict):
            flattened.update(_flatten_options(v, new_key))
        else:
            flattened[new_key] = repr(v)

    return flattened
