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
"""Credentials for IBM Quantum."""

from prefect.blocks.abstract import CredentialsBlock
from pydantic import Field, HttpUrl, SecretStr, field_validator

from prefect_qiskit.vendors.ibm_quantum.client import IBMQuantumPlatformClient


class IBMQuantumCredentials(CredentialsBlock):
    """
    Block used to manage runtime service authentication with IBM Quantum.

    Attributes:
        api_key:
            API key to access IBM Quantum Platform.
        crn:
            Cloud resource name to identify the service to use.
        auth_url:
            A custom endpoint URL for IAM authentication.
        runtime_url:
            A custom endpoint URL for Qiskit Runtime API.

    Example:
        Load stored IBM Quantum credentials:

        ```python
        from prefect_qiskit.vendors.ibm_quantum import IBMQuantumCredentials

        quantum_credentials = IBMQuantumCredentials.load("BLOCK_NAME")
        ```
    """

    _logo_url = "https://avatars.githubusercontent.com/u/30696987?s=200&v=4"
    _block_type_name = "IBM Quantum Credentials"
    _block_type_slug = "ibm-quantum-credentials"

    api_key: SecretStr = Field(
        description="API key to access IBM Quantum Platform.",
        title="API Key",
    )

    crn: str = Field(
        description="Cloud resource name to identify the service to use.",
        title="Cloud Resolution Name",
        pattern="^crn:.*$",
    )

    auth_url: HttpUrl | None = Field(
        default=None,
        description="A custom endpoint URL for IAM authentication.",
        title="Authentication Endpoint URL",
    )

    runtime_url: HttpUrl | None = Field(
        default=None,
        description="A custom endpoint URL for Qiskit Runtime API.",
        title="Runtime Endpoint URL",
    )

    @field_validator("auth_url", "runtime_url", mode="before")  # type: ignore
    @classmethod
    def ensure_url(cls, value: str | HttpUrl) -> HttpUrl | None:
        if isinstance(value, str):
            if not value:
                return None
            else:
                return HttpUrl(url=value)
        return value

    def get_client(self) -> IBMQuantumPlatformClient:
        """Get IBM Runtime REST API client."""
        kwargs = {}
        if self.auth_url:
            kwargs["auth_endpoint_url"] = self.auth_url.unicode_string()
        if self.runtime_url:
            kwargs["runtime_endpoint_url"] = self.runtime_url.unicode_string()

        return IBMQuantumPlatformClient(
            api_key=self.api_key,
            crn=self.crn,
            **kwargs,
        )
