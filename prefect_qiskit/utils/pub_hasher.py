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
"""Compute unique hash of primitive inputs."""

import hashlib
import pickle
from functools import singledispatch
from typing import Any

from qiskit.primitives.containers.estimator_pub import EstimatorPub
from qiskit.primitives.containers.sampler_pub import SamplerPub
from qiskit.qasm3 import dumps as oq3_dumps


def pub_hasher(
    pubs: list[SamplerPub] | list[EstimatorPub],
    options: dict[str, Any],
    resource_name: str,
) -> str:
    """Compute task cache key of run_primitive function."""

    # QuantumCircuit doesn't generate the same binary after kernel restart
    # even if we run the same Python code.
    # On the other hand, the OQ3 format will always generate the same string,
    # so we serialize circuit separately through qiskit.qasm3.dumps.
    # Note that QPY evaluates parameter UUID, so circuits created by the
    # same code are not identical in the byte output.
    pub_bytes = list(map(encode_pub, pubs))

    inputs = pickle.dumps((pub_bytes, options, resource_name), protocol=4)
    return hashlib.sha256(inputs).hexdigest()


@singledispatch
def encode_pub(pub) -> bytes:  # type: ignore
    raise TypeError("Unreachable")


@encode_pub.register(SamplerPub)
def encode_sampler_pub(pub):  # type: ignore
    circ = pub.circuit
    circ.name = ""
    return pickle.dumps(
        (oq3_dumps(circ), pub.parameter_values, pub.shots),
        protocol=4,
    )


@encode_pub.register(EstimatorPub)
def encode_estimator_pub(pub):  # type: ignore
    circ = pub.circuit
    circ.name = ""
    return pickle.dumps(
        (oq3_dumps(circ), pub.observables, pub.parameter_values, pub.precision),
        protocol=4,
    )
