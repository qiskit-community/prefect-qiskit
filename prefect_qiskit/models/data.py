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
"""Common data structures."""

from datetime import datetime
from typing import NamedTuple


class JobMetrics(NamedTuple):
    """
    A canonical job metrics template.
    Vendor can provide following data if available.
    Provided information is consumed by the primitive runner to create a job metrics artifact.

    Attributes:
        qpu_usage: Duration that a quantum processor was actively running.
        timestamp_created: Time when the user job was created in the queue.
        timestamp_started: Time when the execution started on the control server.
        timestamp_completed: Time when the QPU execution completed on the control server.
    """

    qpu_usage: float | None
    timestamp_created: datetime | None
    timestamp_started: datetime | None
    timestamp_completed: datetime | None
