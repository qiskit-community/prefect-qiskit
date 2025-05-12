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
"""A logging mixin to provide context dependent logger."""

import logging
import sys
from logging import Logger
from typing import TYPE_CHECKING, TypeAlias

from prefect.exceptions import MissingContextError
from prefect.logging.loggers import get_logger, get_run_logger

if sys.version_info >= (3, 12):
    LoggingAdapter = logging.LoggerAdapter[logging.Logger]
else:
    if TYPE_CHECKING:
        LoggingAdapter = logging.LoggerAdapter[logging.Logger]
    else:
        LoggingAdapter = logging.LoggerAdapter

LoggerOrAdapter: TypeAlias = Logger | LoggingAdapter


class LoggingMixin:
    """Provide context dependent logging.

    When the logger is called from flow run, it returns proper Prefect logger.
    Otherwise it returns Python default logger with class name.

    Logic is copied from original Prefect project.
    """

    @property
    def logger(self) -> LoggerOrAdapter:
        """Return a logger depending on context."""
        try:
            return get_run_logger()
        except MissingContextError:
            return get_logger(self.__class__.__name__)
