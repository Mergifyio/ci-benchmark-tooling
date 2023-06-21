#!/usr/bin/env python3
import argparse
import csv
import logging
import os
import pathlib

import daiquiri

from ci_benchmark_tooling import types
from ci_benchmark_tooling import utils


daiquiri.setup(level=logging.INFO)
LOG = daiquiri.getLogger(__name__)

OUTPUT_CSV_FILE = pathlib.Path(os.path.dirname(__file__)) / "benchmark_data.csv"


def init_csv_file() -> None:
    with open(OUTPUT_CSV_FILE, "w") as f:
        csv_writer = csv.writer(f, delimiter=";")
        csv_writer.writerow(
            [
                "CI Provider",
                "Runner OS",
                "Runner type",
                "Runner cores",
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


def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create benchmark report",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "source",
        choices=["env", "api"],
        help="""\
'env' will retrieve the workflows ids for each ci provider from environment variables.
'api' will retrieve the workflows ids for each ci provider from api requests, by fetching
the latest benchmark workflows run.
If you specify every workflows ids from the optional arguments, then you can pick whatever choice for this.
""",
    )

    for ci in utils.CIS_TO_BENCHMARK:
        parser.add_argument(
            f"--{ci['workflow_ids_env_variable_prefix'].lower()}",
            type=str,
            help=f"Comma-separated list of the workflows ids to create the report from for {ci['workflow_ids_env_variable_prefix'].lower()}.",
            metavar="WORKFLOWS_IDS",
            default=None,
        )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = get_parser()

    args = parser.parse_args(argv)

    github_repository = utils.get_required_env_variable("GITHUB_REPOSITORY")
    repo_owner, repo_name = github_repository.split("/")

    csv_data: list[types.CsvDataLine] = []

    for ci_to_benchmark in utils.CIS_TO_BENCHMARK:
        token = utils.get_required_env_variable(ci_to_benchmark["token_env_variable"])
        client = ci_to_benchmark["client"](token)

        ids_from_parser = getattr(
            args,
            ci_to_benchmark["workflow_ids_env_variable_prefix"].lower(),
        )
        if ids_from_parser is not None:
            workflows_ids = ids_from_parser.split(",")
        elif args.source == "env":
            workflows_ids_str: str = utils.get_required_env_variable(
                utils.get_benchmark_workflow_run_ids_env_variable_name(
                    ci_to_benchmark["workflow_ids_env_variable_prefix"],
                ),
            )
            workflows_ids = workflows_ids_str.split(",")
        elif args.source == "api":
            workflows_ids = client.get_latest_benchmark_workflows_ids(
                repo_owner,
                repo_name,
            )
        else:
            raise RuntimeError("How did we get here???")

        LOG.info(
            "Workflows ids for %s = %s",
            ci_to_benchmark["workflow_ids_env_variable_prefix"],
            workflows_ids,
        )

        csv_data.extend(
            client.generate_csv_data_from_workflows_ids(
                workflows_ids,
                repo_owner,
                repo_name,
            ),
        )

    init_csv_file()
    write_csv_data(csv_data)

    return 0
