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
This module implements credentials for each quantum computing vendor,
following the Prefect `CredentialsBlock` structure.
Users can create and store these credentials on the Prefect server.

The block must implement the `.get_client` method,
which returns a client instance for the vendor-specific API,
adhering to the `AsyncRuntimeClientInterface` protocol.
This client is used by the primitive runner task and is not exposed externally.
Although users can access the client instance via this method,
it should be considered a private class and
may be subject to future API changes without deprecation.
"""

from .ibm_quantum.credentials import IBMQuantumCredentials
from .qiskit_aer.credentials import QiskitAerCredentials

QuantumCredentialsT = IBMQuantumCredentials | QiskitAerCredentials

__all__ = [
    "IBMQuantumCredentials",
    "QiskitAerCredentials",
]
