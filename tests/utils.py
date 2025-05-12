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
"""Test utilities."""

from qiskit.primitives.containers.sampler_pub_result import SamplerPubResult
from qiskit.quantum_info import hellinger_fidelity


def assert_sampler_fidelity(
    result: SamplerPubResult,
    ref: dict[str, int],
    atol: float = 0.1,
) -> None:
    """Assert when hellinger_fidelity is lower than atol.

    Args:
        result: Sampler primitive result with 'meas' register.
        ref: Reference count dictionary.
        atol: Absolute tolerable error.
    """
    assert hellinger_fidelity(result.data.meas.get_counts(), ref) > 1 - atol
