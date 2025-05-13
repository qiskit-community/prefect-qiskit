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
"""Prefect integration to manage execution of Qiskit Primitives."""

from importlib.metadata import PackageNotFoundError, version

from .runtime import QuantumRuntime

try:
    __version__ = version("prefect-qiskit")
except PackageNotFoundError:
    pass

__all__ = [
    "QuantumRuntime",
]
