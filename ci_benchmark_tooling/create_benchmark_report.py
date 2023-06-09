#!/usr/bin/env python3
import csv
import logging
import os
import pathlib

import daiquiri

from ci_benchmark_tooling import types
from ci_benchmark_tooling import utils


daiquiri.setup(level=logging.INFO)

OUTPUT_CSV_FILE = pathlib.Path(os.path.dirname(__file__)) / "benchmark_data.csv"


def init_csv_file() -> None:
    with open(OUTPUT_CSV_FILE, "w") as f:
        csv_writer = csv.writer(f, delimiter=";")
        csv_writer.writerow(
            [
                "CI Provider",
                "Runner OS",
                "Runner type",
                "Repository tested",
                "Step",
                "Time spent (sec)",
                "Additional infos",
            ],
        )


def write_csv_data(csv_data: list[types.CsvDataLine]) -> None:
    with open(OUTPUT_CSV_FILE, "a") as f:
        csv_writer = csv.writer(f, delimiter=";")
        csv_writer.writerows(csv_data)


def main(_argv: list[str] | None = None) -> int:
    github_repository = utils.get_required_env_variable("GITHUB_REPOSITORY")
    owner, repository = github_repository.split("/")

    csv_data: list[types.CsvDataLine] = []

    for ci_to_benchmark in utils.CIS_TO_BENCHMARK:
        token = utils.get_required_env_variable(ci_to_benchmark["token_env_variable"])
        client = ci_to_benchmark["client"](token)

        # Retrieve the list of workflows ids from the needed env variable
        workflows_ids_str: str = utils.get_required_env_variable(
            utils.get_benchmark_workflow_run_ids_env_variable_name(
                ci_to_benchmark["workflow_ids_env_variable_prefix"],
            ),
        )
        workflows_ids = workflows_ids_str.split(",")

        csv_data.extend(
            client.generate_csv_data_from_workflows_ids(
                workflows_ids,
                owner,
                repository,
            ),
        )

    init_csv_file()
    write_csv_data(csv_data)

    return 0
