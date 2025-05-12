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
"""Cache key evaluation scripts."""

import numpy as np

MOCK_OPTIONS = {
    "value_x": 123,
    "value_y": ["abc", "cde", "fgh"],
    "value_z": {
        "nest1": 1.23456,
        "nest2": np.float32(123.456),
    },
}
