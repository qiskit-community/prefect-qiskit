# Contribution Guidelines

## Open Pull Request

If you'd like to contribute by fixing an issue or adding a new feature to `prefect-qiskit`, 
please open a pull request from a fork of the repository. 

Follow these steps to open a pull request:

1. Fork the repository:<br>
   Create a copy of the repository under your GitHub account.
2. Clone the forked repository:<br>
   Download the repository to your local machine:
   ```bash
   git clone git@github.com:<your-github-account>/prefect-qiskit.git
   ```
3. Install the repository with `dev` dependency:
   ```bash
   pip install -e '.[dev]'
   ```
4. Update code:<br>
   Ensure functions and classes are documented and type hinted.
5. Add tests:<br>
   Write tests that cover the new changes or bug fixes.
   Confirm your changes don't break any test cases:
   ```bash
   pytest tests/
   ```
6. Install `pre-commit`:<br>
   Perform code quality checks before committing:
   ```bash
   pre-commit install
   ```
8. Commit and push:<br>
   Use `git add`, `git commit`, and `git push` to update your forked repository and open a pull request.

## Provide Vendor Implementation

We welcome the implementation of clients for other quantum computing vendors. 
Follow these instructions to add support for a new vendor. 
Feel free to contact us via GitHub issues if you need support.

### Protocol and Block

A typical module structure for a specific vendor implementation looks like this:

```
prefect_qiskit
│   README.md
│   ...   
│
└───vendors
│   │   __init__.py
│   │
│   └───vendor_xyz
│       │   __init__.py
│       │   client.py
│       │   credentials.py
```

* Client file (`client.py`):<br>
  Implement the [`AsyncRuntimeClientInterface`](./reference.md#prefect_qiskit.models.AsyncRuntimeClientInterface) protocol, which is the core of your work.
* Credential file (`credentials.py`)<br>
  Implement the Prefect `CredentialsBlock` to store access credentials for your backend provider.

After implementing the new credential block, add it to the `QuantumCredentialsT` alias in `prefect_qiskit.vendors.__init__.py`. 
This allows `QuantumRuntime` to find the data model so that end users can set a credential for your provider on the Prefect console.

### Add Test Module

Add test cases for the new vendor to prevent future breaking API changes. 
Create a new test module in `tests.vendors`. 
Ideally, include at least one end-to-end test if it makes sense. 

Avoid including real credentials or tests relying on such credentials due to security concerns. 
If you implement a client for REST API, you can dump the server response in JSON files and write practical test cases against this mock server.

!!! WARNING
    Remove all secrets from test data to avoid any security risks.

### Misc

Update the [Supported Vendors](./index.md#supported-vendors) list in documentation as well.
Add the new vendor module to the [API Reference](./reference.md#api-reference).
