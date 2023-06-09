from __future__ import annotations

import abc
import typing

import daiquiri
import httpx


if typing.TYPE_CHECKING:
    from ci_benchmark_tooling import types


class BaseClient(httpx.Client, abc.ABC):
    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        httpx.Client.__init__(self, *args, **kwargs)
        self.logger = daiquiri.getLogger(self.__class__.__name__)

    @abc.abstractmethod
    def send_dispatch_events_and_wait_for_end(
        self,
        repository_owner: str,
        repository_name: str,
        workflow_dispatch_ref: str,
    ) -> int:
        ...

    @abc.abstractmethod
    def generate_csv_data_from_workflows_ids(
        self,
        workflows_ids: list[str],
        repository_owner: str,
        repository_name: str,
    ) -> list[types.CsvDataLine]:
        ...
