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
This module abstracts the runtime client interface and common data structures.

The Quantum Runtime implementation for Prefect adheres to
the Qiskit programming model for quantum primitives,
which is vendor hardware agnostic.

Primitives utilize Primitive Unified Blocs (PUBs)
along with an execution options dictionary.
Execution options can specify a vendor-specific schema
based on supported features, such as built-in error mitigations.

This module defines the protocol for API adapters that Prefect primitives can use.
The protocol does not specify actual communication methods,
allowing hardware vendors to implement any protocols, such as RESTful or gRPC,
to interact with their hardware.
All methods are asynchronous to leverage Prefect's native async support.
"""

from .data import JobMetrics
from .interface import JOB_STATUS, AsyncRuntimeClientInterface

__all__ = [
    "AsyncRuntimeClientInterface",
    "JobMetrics",
    "JOB_STATUS",
]
