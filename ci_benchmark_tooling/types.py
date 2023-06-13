from __future__ import annotations

import typing


if typing.TYPE_CHECKING:
    from ci_benchmark_tooling.clients import base as base_clients


class GitHubJobNameInfos(typing.NamedTuple):
    tested_repository: str
    runner_os: str
    runner_cores: int
    additional_infos: str


class CsvDataLine(typing.NamedTuple):
    ci_provider: str
    runner_os: str
    runner_cores: int
    tested_repository: str
    step_name: str
    time_spent_in_secs: int
    additional_infos: str


class CiToBenchmark(typing.TypedDict):
    client: type[base_clients.BaseClient]
    token_env_variable: str
    workflow_ids_env_variable_prefix: str


class GitHubBenchmarkFileWithNameSection(typing.NamedTuple):
    filename: str
    yaml_name_section_value: str
