from __future__ import annotations

import os
import pathlib
import sys
import typing

import daiquiri
import yaml

from ci_benchmark_tooling import constants
from ci_benchmark_tooling import types
from ci_benchmark_tooling.clients import circleci as cci_client
from ci_benchmark_tooling.clients import github as gh_client


if typing.TYPE_CHECKING:
    from collections import abc


LOG = daiquiri.getLogger(__name__)

DOT_GITHUB_WORKFLOWS_FOLDER = (
    pathlib.Path(os.path.dirname(__file__)) / ".." / ".github" / "workflows"
)
DOT_CIRCLECI_FOLDER = pathlib.Path(os.path.dirname(__file__)) / ".." / ".circleci"


CIS_TO_BENCHMARK: list[types.CiToBenchmark] = [
    {
        "client": gh_client.GitHubClient,
        "token_env_variable": "GH_TOKEN",
        "workflow_ids_env_variable_prefix": constants.GITHUB_WORKFLOW_IDS_ENV_PREFIX,
    },
    {
        "client": cci_client.CircleCiClient,
        "token_env_variable": "CIRCLE_TOKEN",
        "workflow_ids_env_variable_prefix": constants.CIRCLECI_WORKFLOW_IDS_ENV_PREFIX,
    },
]


def get_required_env_variable(env_variable: str) -> typing.Any:
    try:
        return os.environ[env_variable]
    except KeyError:
        LOG.error(f"Could not find required `{env_variable}` in environment.")
        sys.exit(1)


def get_benchmark_workflow_run_ids_env_variable_name(prefix: str) -> str:
    return f"{prefix}_BENCHMARK_WORKFLOW_RUN_IDS"


def write_workflow_ids_to_github_env(env_prefix: str, workflow_ids_str: str) -> None:
    benchmark_env_var = get_benchmark_workflow_run_ids_env_variable_name(env_prefix)

    github_env_file = os.getenv("GITHUB_ENV")
    if not github_env_file:
        os.environ[benchmark_env_var] = workflow_ids_str
        return

    with open(github_env_file, "a") as f:
        print(
            f"{benchmark_env_var}={workflow_ids_str}",
            file=f,
        )


def get_github_benchmark_filenames_and_yaml_name_section() -> (
    abc.Iterator[types.GitHubBenchmarkFileWithNameSection]
):
    for benchmark_file in DOT_GITHUB_WORKFLOWS_FOLDER.glob("benchmark_*.yml"):
        with open(benchmark_file) as f:
            yaml_data = yaml.safe_load(f.read())

        yield types.GitHubBenchmarkFileWithNameSection(
            filename=benchmark_file.name,
            yaml_name_section_value=yaml_data["name"],
        )


def get_github_benchmark_file_by_yaml_name_section() -> dict[str, pathlib.Path]:
    d = {}
    for benchmark_file in DOT_GITHUB_WORKFLOWS_FOLDER.glob("benchmark_*.yml"):
        with open(benchmark_file) as f:
            yaml_data = yaml.safe_load(f.read())

        d[yaml_data["name"]] = benchmark_file

    return d
