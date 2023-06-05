from collections import abc
import os
import pathlib
import sys
import typing

import daiquiri
import httpx
import yaml


LOG = daiquiri.getLogger(__name__)

DOT_GITHUB_WORKFLOWS_FOLDER = (
    pathlib.Path(os.path.dirname(__file__)) / ".." / ".github" / "workflows"
)


class BenchmarkFileWithNameSection(typing.NamedTuple):
    filename: str
    yaml_name_section_value: str


class BenchmarkFileWithPath(typing.NamedTuple):
    filename: str
    path: str


def get_required_env_variable(env_variable: str) -> typing.Any:
    try:
        return os.environ[env_variable]
    except KeyError:
        LOG.error(f"Could not find required `{env_variable}` in environment.")
        sys.exit(1)


def get_benchmark_filenames_and_yaml_name_section() -> (
    abc.Iterator[BenchmarkFileWithNameSection]
):
    for benchmark_file in DOT_GITHUB_WORKFLOWS_FOLDER.glob("benchmark_*.yml"):
        with open(benchmark_file) as f:
            yaml_data = yaml.safe_load(f.read())

        yield BenchmarkFileWithNameSection(
            filename=benchmark_file.name,
            yaml_name_section_value=yaml_data["name"],
        )


def get_benchmark_file_by_yaml_name_section() -> dict[str, pathlib.Path]:
    d = {}
    for benchmark_file in DOT_GITHUB_WORKFLOWS_FOLDER.glob("benchmark_*.yml"):
        with open(benchmark_file) as f:
            yaml_data = yaml.safe_load(f.read())

        d[yaml_data["name"]] = benchmark_file

    return d


class GitHubClient(httpx.Client):
    def __init__(self, token: str) -> None:
        super().__init__(
            base_url="https://api.github.com",
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "Authorization": f"Bearer {token}",
            },
            http2=True,
        )
