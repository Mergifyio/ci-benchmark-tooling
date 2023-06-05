#!/usr/bin/env python3
import csv
import datetime
import logging
import os
import pathlib
import typing

import daiquiri
import yaml

from ci_benchmark_tooling import github_types
from ci_benchmark_tooling import utils


daiquiri.setup(level=logging.INFO)
LOG = daiquiri.getLogger(__name__)

OUTPUT_CSV_FILE = pathlib.Path(os.path.dirname(__file__)) / "benchmark_data.csv"

GITHUB_JOB_STEPS = ("Set up job", "Complete job")


class JobNameInfos(typing.NamedTuple):
    tested_repository: str
    runner_os: str
    runner_cores: int
    additional_infos: str


class CsvDataLine(typing.NamedTuple):
    runner_os: str
    runner_cores: int
    tested_repository: str
    step_name: str
    time_spent_in_secs: int
    additional_infos: str


def get_infos_from_job_name(job_name: str) -> JobNameInfos:
    if job_name.count(" - ") == 2:
        tested_repository, runner_os, runner_cores = job_name.split(
            " - ",
        )
        additional_infos = ""
    else:
        tested_repository, runner_os, runner_cores, additional_infos = job_name.split(
            " - ",
            3,
        )

    runner_cores_int = int(runner_cores.replace(" cores", ""))

    return JobNameInfos(
        tested_repository,
        runner_os,
        runner_cores_int,
        additional_infos,
    )


def get_yaml_data_job_from_github_action_job_name(
    yaml_data: typing.Any,
    job_name: str,
) -> dict[str, typing.Any] | None:
    """
    Retrieves the job dictionary, from the yaml data of a workflow file, based on the job
    name of a github action.

    To do that, we parse all the matrix in the `strategy/matrix/include`
    of each jobs, and if the job name, in the yaml_data, + the `name` of a matrix
    equals the `job_name`, in parameter of this function then we return the corresponding job.
    """
    for job in yaml_data["jobs"].values():
        for matrix in job["strategy"]["matrix"]["include"]:
            if job["name"].replace("${{ matrix.name }}", matrix["name"]) == job_name:
                return job
    return {}


def get_job_steps_names_from_yaml_job_data(
    yaml_job_data: dict[str, typing.Any],
) -> list[str] | None:
    """
    Retrieves the name of each of the steps of a benchmark job of a github
    action workflow file.
    """
    steps_names = []
    for s in yaml_job_data["steps"]:
        steps_names.append(s["name"])
        steps_names.append(f"Post {s['name']}")
    return steps_names


def get_time_spent_per_job_step(
    job_steps: list[github_types.GitHubJobRunStep],
    build_steps_of_benchmark_job: list[str],
) -> dict[str, datetime.timedelta]:
    time_per_step = {}
    for s in job_steps:
        if s["name"].startswith("Clone "):
            # Ignore the `Clone` of the repo we are benchmarking,
            # since it is not relevant to the benchmark itself
            continue

        time_spent = datetime.datetime.fromisoformat(
            s["completed_at"],
        ) - datetime.datetime.fromisoformat(s["started_at"])

        # Group the build steps of the repository we tested
        if s["name"] in build_steps_of_benchmark_job:
            step_name = "Benchmarked application build"
        else:
            step_name = s["name"]

        if step_name not in time_per_step:
            time_per_step[step_name] = time_spent
        else:
            time_per_step[step_name] += time_spent

    return time_per_step


def generate_csv_data_for_workflow_runs(
    workflow_run_ids: list[int],
    token: str,
    owner: str,
    repository: str,
) -> int:
    client = utils.GitHubClient(token)
    benchmark_files = utils.get_benchmark_file_by_yaml_name_section()

    csv_data: list[CsvDataLine] = []

    for workflow_id in workflow_run_ids:
        resp_wr = client.get(f"/repos/{owner}/{repository}/actions/runs/{workflow_id}")
        if resp_wr.status_code != 200:
            # TODO: Add a retry ?
            LOG.warning(
                "GitHub response error: %s",
                resp_wr.text,
                status_code=resp_wr.status_code,
            )
            continue

        workflow_run = typing.cast(
            github_types.GitHubWorkflowRun,
            resp_wr.json(),
        )
        file = benchmark_files[workflow_run["name"]]

        with open(file) as f:
            yaml_data = yaml.safe_load(f.read())

        # Find the jobs data for the workflow_run
        workflow_run["jobs_url"]
        resp_jobs = client.get(workflow_run["jobs_url"])
        if resp_jobs.status_code != 200:
            # TODO: Add a retry ?
            LOG.warning(
                "GitHub response error: %s",
                resp_wr.text,
                status_code=resp_wr.status_code,
            )
            continue

        job_list = typing.cast(github_types.GitHubJobRunList, resp_jobs.json())
        for job in job_list["jobs"]:
            # Retrieve all the infos we will put in the CSV from the job name
            job_infos = get_infos_from_job_name(job["name"])
            yaml_job_data = get_yaml_data_job_from_github_action_job_name(
                yaml_data,
                job["name"],
            )

            build_steps_of_benchmark_job = get_job_steps_names_from_yaml_job_data(
                yaml_job_data,
            )

            time_per_step = get_time_spent_per_job_step(
                job["steps"],
                build_steps_of_benchmark_job,
            )

            for step, time_spent in time_per_step.items():
                if step in GITHUB_JOB_STEPS:
                    additional_infos = "GitHub Step"
                else:
                    additional_infos = job_infos.additional_infos

                csv_data.append(
                    CsvDataLine(
                        job_infos.runner_os,
                        job_infos.runner_cores,
                        job_infos.tested_repository,
                        step,
                        int(time_spent.total_seconds()),
                        additional_infos,
                    ),
                )

    LOG.info(f"Writing data to {OUTPUT_CSV_FILE}")
    write_csv_data(csv_data)

    return 0


def write_csv_data(csv_data: list[CsvDataLine]) -> None:
    with open(OUTPUT_CSV_FILE, "w") as f:
        csv_writer = csv.writer(f, delimiter=";")
        csv_writer.writerow(
            [
                "Runner OS",
                "Runner cores",
                "Repository tested",
                "Step",
                "Time spent (sec)",
                "Additional infos",
            ],
        )
        csv_writer.writerows(csv_data)


def main(_argv: list[str] | None = None) -> int:
    gh_token = utils.get_required_env_variable("GH_TOKEN")

    github_repository = utils.get_required_env_variable("GITHUB_REPOSITORY")
    owner, repository = github_repository.split("/")

    # TODO: Uncomment once testing done
    # workflow_run_ids = utils.get_required_env_variable("BENCHMARK_WORKFLOW_RUN_IDS")
    # workflow_run_ids_int = list(map(int, workflow_run_ids.split(",")))

    workflow_run_ids_int = [5197754007]

    return generate_csv_data_for_workflow_runs(
        workflow_run_ids_int,
        gh_token,
        owner,
        repository,
    )
