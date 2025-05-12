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
from qiskit.primitives.containers.estimator_pub import EstimatorPub
from qiskit.providers.fake_provider import GenericBackendV2
from qiskit.quantum_info import SparsePauliOp
from qiskit.transpiler import generate_preset_pass_manager

from prefect_qiskit.utils.pub_hasher import pub_hasher

from . import MOCK_OPTIONS

backend = GenericBackendV2(10, noise_info=True, seed=123)
pm = generate_preset_pass_manager(optimization_level=2, target=backend.target)

params = ParameterVector("θ", length=3)
op = SparsePauliOp.from_list([("ZZZ", 1)])

circ = QuantumCircuit(3)
for i, par in enumerate(params):
    circ.rx(par, i)
circ.measure_all()

isa_circ = pm.run(circ)
isa_op = op.apply_layout(isa_circ.layout)

key = pub_hasher(
    pubs=[
        EstimatorPub.coerce(
            (isa_circ, isa_op, np.random.default_rng(seed=123).random((7, 3))),
            precision=0.00123,
        ),
    ],
    options=MOCK_OPTIONS,
    resource_name="backend_xyz",
)

print(key)
