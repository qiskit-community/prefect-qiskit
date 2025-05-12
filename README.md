# Prefect Qiskit

[![License](https://img.shields.io/github/license/Qiskit-Community/prefect-qiskit.svg)](https://opensource.org/licenses/Apache-2.0)
[![Release](https://img.shields.io/github/release/Qiskit-Community/prefect-qiskit.svg)](https://github.com/Qiskit-Community/prefect-qiskit/releases)
![Python](https://img.shields.io/pypi/pyversions/prefect-qiskit.svg)

This library integrates [Prefect](https://www.prefect.io/) with [Qiskit Primitives](https://docs.quantum.ibm.com/api/qiskit/primitives), 
which are vendor-agnostic abstractions for quantum computation. 

Given the high cost and limited processing time of quantum computation, 
fatal errors can disrupt the entire workflow. 
This library enhances software fault tolerance 
by implementing primitive execution within a Prefect workflow.

For more details, visit the full documentation [here]().

## Installation

Prefect Qiskit requires Python 3.10 or later. 
We encourage install via ``pip``

```bash
pip install prefect-qiskit
```

Pip will handle all dependencies automatically and you will always install the latest version.


## Quantum Computing Workflow

The programming model and syntax are largely consistent with conventional Qiskit primitives, 
allowing easy integration of Prefect's powerful job management features 
into existing experiment codebases. 
The key difference is the use of the `QuantumRuntime` Block, 
which implements the Prefect API for quantum computing.

Unlike the conventional pattern that uses primitive class instances to create jobs, 
the runtime Block encapsulates vendor-specific job handling 
and provides robust error handling during execution.

For example, the following script samples the probability distribution of 
the Bell state using the Qiskit Aer simulator.

```python
from prefect import flow, task
from prefect_qiskit import QuantumRuntime
from prefect_qiskit.vendors import QiskitAerCredentials
from qiskit.circuit import QuantumCircuit
from qiskit.transpiler import generate_preset_pass_manager


@task
def transpile_task(circuit, target):
    pm = generate_preset_pass_manager(
        optimization_level=2,
        target=target,
    )
    return pm.run(circuit)


@flow
def sample_bell():
    # 1. Create QuantumRuntime for Aer backend
    credentials = QiskitAerCredentials(
        num_qubits=2, 
        noise=True,
    )
    runtime = QuantumRuntime(
        resource_name="aer_simulator", 
        credentials=credentials,
    )
    # 2. Create ISA quantum circuit
    bell = QuantumCircuit(2)
    bell.h(0)
    bell.cx(0, 1)
    bell.measure_all()
    isa_circ = transpile_task(
        circuit=bell, 
        target=runtime.get_target(),
    )
    # 3. Execute workflow sampler
    result = runtime.sampler(
        [isa_circ], 
        options={"default_shots": 100},
    )
    print(result[0].data.meas.get_counts())


# Run the flow
if __name__ == "__main__":
    sample_bell()
```

Before running your workflow, start the Prefect server:

```bash
prefect server start --background
```

You can then run the workflow as a standard Python script. Once the workflow begins, 
you can monitor its execution status in the Prefect console. 
For common workflow usage, refer to the [Prefect documentation](https://docs.prefect.io/v3/develop/write-flows).

> [!TIP]
> The runtime Block also supports asynchronous execution.
> For massive parallel execution of primitives, 
> using the `await` expression will efficiently utilize your computational resources.


## Registering Blocks

Register Blocks to make them available for use with the Prefect console.

```bash
prefect block register -m prefect_qiskit
prefect block register -m prefect_qiskit.vendors
```

## Contribution Guidelines

If you'd like to contribute to Prefect Qiskit, please take a look at our [contribution guidelines](). By participating, you are expected to uphold our code of conduct.

We use [GitHub issues](https://github.com/qiskit-community/prefect-qiskit/issues) for tracking requests and bugs.
For Prefect workflow, open issues and PRs against [PrefectHQ/prefect](https://github.com/PrefectHQ/prefect) instead of this repository.
Likewise, open issues and PRs against [Qiskit/qiskit](https://github.com/Qiskit/qiskit) for Qiskit Primitives.

## License

[Apache License 2.0](LICENSE.txt)
