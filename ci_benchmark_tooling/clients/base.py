from __future__ import annotations

import abc
import typing

import daiquiri
import httpx
import tenacity


if typing.TYPE_CHECKING:
    from ci_benchmark_tooling import types


class BaseClient(httpx.Client, abc.ABC):
    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        httpx.Client.__init__(self, *args, **kwargs)
        self.logger = daiquiri.getLogger(self.__class__.__name__)

    @abc.abstractmethod
    def send_dispatch_events(
        self,
        repository_owner: str,
        repository_name: str,
        workflow_dispatch_ref: str,
    ) -> int:
        """
        Send workflow dispatch events to the relevant CI Provider, and save
        the required data in the instance of the object to be able to
        poll the workflows to know if they finished or not.
        This function also needs to write the worklows ids to the GITHUB_ENV
        and with a environment variable name prefix relevant to the CI Provider.
        """
        ...

    @abc.abstractmethod
    def wait_for_workflows_to_end(self) -> None:
        """
        Use the data saved in the object instance, by `send_dispatch_events`,
        to check if the workflows we dispatch ended.
        """
        ...

    @abc.abstractmethod
    def generate_csv_data_from_workflows_ids(
        self,
        workflows_ids: list[str],
        repository_owner: str,
        repository_name: str,
    ) -> list[types.CsvDataLine]:
        ...

    def request(self, *args: typing.Any, **kwargs: typing.Any) -> httpx.Response:
        for attempt in tenacity.Retrying(
            reraise=True,
            retry=tenacity.retry_if_exception_type(
                (httpx.StreamError, httpx.HTTPError),
            ),
            wait=tenacity.wait_exponential(0.2),
        ):
            with attempt:
                resp = super().request(*args, **kwargs)

        return resp
