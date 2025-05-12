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
import numpy as np
from qiskit.circuit import ParameterVector, QuantumCircuit
from qiskit.primitives.containers.sampler_pub import SamplerPub

from prefect_qiskit.utils.pub_hasher import pub_hasher

from . import MOCK_OPTIONS

params = ParameterVector("θ", length=3)

circ1 = QuantumCircuit(3)
for i, par in enumerate(params):
    circ1.rx(par, i)
circ1.measure_all()

circ2 = QuantumCircuit(3)
for i, par in enumerate(params):
    circ2.rz(par, i)
circ2.measure_all()

key = pub_hasher(
    pubs=[
        SamplerPub.coerce(
            (circ1, np.random.default_rng(seed=123).random((7, 3))),
            shots=1234,
        ),
        SamplerPub.coerce(
            (circ2, np.random.default_rng(seed=456).random((4, 3))),
            shots=5678,
        ),
    ],
    options=MOCK_OPTIONS,
    resource_name="backend_xyz",
)

print(key)
