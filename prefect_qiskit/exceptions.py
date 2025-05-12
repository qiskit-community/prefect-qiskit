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
This module defines custom exceptions.
"""


class RuntimeJobFailure(Exception):
    """
    A custom exception to enable fine-grained control of Prefect task retries.

    All exceptions raised within the implementation of `AsyncRuntimeClientInterface`
    must be type cast into this exception. This exception includes a `retry` flag,
    allowing the Prefect primitive runner to determine
    whether to retry the task upon encountering an exception.

    For instance, if a user creates invalid PUB data,
    the task execution is unlikely to succeed.
    In such cases, the error from PUB validation should be
    type cast into `RuntimeJobFailure` with `retry=False`.
    """

    def __init__(
        self,
        reason: str,
        job_id: str | None = None,
        error_code: str | None = None,
        retry: bool = True,
    ):
        """Define exception.

        Args:
            reason: A human readable explanation of the failure.
            job_id: Failed Job ID.
            error_code: Vendor-specific error code.
            retry: Either retry the primitive execution or not.
        """
        if error_code is not None:
            error_code = str(error_code)
            msg = f"Primitive Job failure ({error_code}); {reason}"
        else:
            msg = f"Primitive Job failure; {reason}"
        super().__init__(msg)
        self.message = msg
        self.error_code = error_code
        self.retry = retry
        self.job_id = job_id

    def __str__(self) -> str:
        return self.message
