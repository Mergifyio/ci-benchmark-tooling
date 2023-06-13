import datetime
import pathlib
import time
import typing

import yaml

from ci_benchmark_tooling import constants
from ci_benchmark_tooling import types
from ci_benchmark_tooling import utils
from ci_benchmark_tooling.clients import base
from ci_benchmark_tooling.http_types import github_types


def get_infos_from_github_job_name(job_name: str) -> types.GitHubJobNameInfos:
    if job_name.count(" - ") == 2:
        tested_repository, runner_os, runner_type = job_name.split(
            " - ",
        )
        additional_infos = ""
    else:
        (
            tested_repository,
            runner_os,
            runner_type,
            additional_infos,
        ) = job_name.split(
            " - ",
            3,
        )

    return types.GitHubJobNameInfos(
        tested_repository,
        runner_os,
        runner_type,
        additional_infos,
    )


def get_job_dict_from_yaml_data_and_job_name(
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
                return typing.cast(dict[str, typing.Any], job)
    return {}


def get_job_steps_names_from_yaml_job_data(
    yaml_job_data: dict[str, typing.Any],
) -> list[str]:
    """
    Retrieves the name of each of the steps of a benchmark job of a github
    action workflow file.
    The returned list also contains the name of each steps prepended with `Post `
    to include the cleanup of each of the build steps as time spent benchmarking.
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
            step_name = constants.CSV_BENCHMARKED_APPLICATION_STEP_NAME
        else:
            step_name = s["name"]

        if step_name not in time_per_step:
            time_per_step[step_name] = time_spent
        else:
            time_per_step[step_name] += time_spent

    return time_per_step


class GitHubClient(base.BaseClient):
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
        self.repository_owner = None
        self.repository_name = None
        self.workflows_names_and_ids = None

    ##############################
    ############ WORKFLOW DISPATCH
    ##############################

    def retrieve_workflows_ids(
        self,
        owner: str,
        repository: str,
        now_as_str: str,
        workflows_names_and_ids: dict[str, int],
    ) -> None:
        while -1 in workflows_names_and_ids.values():
            required_names = [k for k, v in workflows_names_and_ids.items() if v == -1]

            resp_wr = self.get(
                f"/repos/{owner}/{repository}/actions/runs",
                params={
                    "event": "workflow_dispatch",
                    "created": f"{now_as_str}..*",
                },
            )

            if resp_wr.status_code != 200:
                self.logger.warning(
                    "GitHub response error: %s",
                    resp_wr.text,
                    status_code=resp_wr.status_code,
                )
                time.sleep(2)
                continue

            for workflow_run in resp_wr.json()["workflow_runs"]:
                if workflow_run["name"] in required_names:
                    workflows_names_and_ids[workflow_run["name"]] = workflow_run["id"]
                    self.logger.info(
                        "Found workflow_id (%s) for workflow '%s'",
                        workflow_run["id"],
                        workflow_run["name"],
                    )

            time.sleep(2)

    def _send_dispatch_event_for_benchmark_files(
        self,
        owner: str,
        repository: str,
        workflow_dispatch_ref: str,
        benchmark_filenames: list[str],
    ) -> int:
        for benchmark_filename in benchmark_filenames:
            resp = self.post(
                f"/repos/{owner}/{repository}/actions/workflows/{benchmark_filename}/dispatches",
                json={
                    "ref": workflow_dispatch_ref,
                },
            )
            if resp.status_code != 204:
                self.logger.error(
                    "Workflow dispatch request failed: %s",
                    resp.text,
                    status_code=resp.status_code,
                )
                return 1

            self.logger.info(
                "Dispatch event successfuly sent for %s",
                benchmark_filename,
            )

        return 0

    def send_dispatch_events(
        self,
        repository_owner: str,
        repository_name: str,
        workflow_dispatch_ref: str,
    ) -> int:
        self.repository_owner = repository_owner
        self.repository_name = repository_name

        self.logger.info("Sending dispatch events for GitHub workflows")
        benchmark_files = list(
            utils.get_github_benchmark_filenames_and_yaml_name_section(),
        )

        self.logger.info("Benchmark files found: %s", benchmark_files)

        # Need to retrieve `datetime.now` before the dispatch requests so we can properly
        # filter the workflow_runs
        now = datetime.datetime.now(tz=constants.UTC)
        now_as_str = now.strftime("%Y-%m-%dT%H:%M:%S")
        # GitHub needs the utcoffset to be "+XX:XX", the `%z` option of
        # `strftime` returns us "+XXXX", so we need to manually add the `:`
        z = now.strftime("%z")
        now_as_str += f"{z[:3]}:{z[3:]}"

        ret_value = self._send_dispatch_event_for_benchmark_files(
            self.repository_owner,
            self.repository_name,
            workflow_dispatch_ref,
            [f.filename for f in benchmark_files],
        )
        if ret_value != 0:
            return ret_value

        # Initiate the dict of workflow names and ids with
        # all the ids set to -1, the ids will be set by the call
        # to the function `self.retrieve_workflows_ids`
        self.workflows_names_and_ids: dict[str, int] = {
            f.yaml_name_section_value: -1 for f in benchmark_files
        }

        self.retrieve_workflows_ids(
            self.repository_owner,
            self.repository_name,
            now_as_str,
            self.workflows_names_and_ids,
        )
        self.logger.info(
            "Workflow IDs of the latest launched benchmarks: %s",
            self.workflows_names_and_ids.values(),
        )

        workflows_ids_for_env = ",".join(
            map(str, self.workflows_names_and_ids.values()),
        )
        utils.write_workflow_ids_to_github_env(
            constants.GITHUB_WORKFLOW_IDS_ENV_PREFIX,
            workflows_ids_for_env,
        )

        return 0

    def wait_for_workflows_to_end(self) -> None:
        self.logger.info("Starting workflows polling...")

        workflows_names_and_ids = self.workflows_names_and_ids.copy()
        while workflows_names_and_ids:
            keys_to_del = []
            for workflow_name, run_id in workflows_names_and_ids.items():
                resp_wr = self.get(
                    f"/repos/{self.repository_owner}/{self.repository_name}/actions/runs/{run_id}",
                )

                if resp_wr.status_code != 200:
                    self.logger.warning(
                        "GitHub response error: %s",
                        resp_wr.text,
                        status_code=resp_wr.status_code,
                    )
                    time.sleep(60)
                    continue

                if resp_wr.json()["conclusion"] is not None:
                    self.logger.info("Workflow '%s' finished", workflow_name)
                    keys_to_del.append(workflow_name)

            for key in keys_to_del:
                del workflows_names_and_ids[key]

            if not workflows_names_and_ids:
                self.logger.info("Workflows polling finished")
                return

            time.sleep(60)

    ##############################
    ############ CSV RELATED STUFF
    ##############################

    def _get_workflow_csv_data(
        self,
        benchmark_files: dict[str, pathlib.Path],
        workflow_id: str,
        repository_owner: str,
        repository_name: str,
    ) -> list[types.CsvDataLine]:
        csv_data: list[types.CsvDataLine] = []

        resp_wr = self.get(
            f"/repos/{repository_owner}/{repository_name}/actions/runs/{workflow_id}",
        )
        if resp_wr.status_code != 200:
            # TODO: Add a retry ?
            self.logger.warning(
                "GitHub response error: %s",
                resp_wr.text,
                status_code=resp_wr.status_code,
            )
            return []

        workflow_run = typing.cast(
            github_types.GitHubWorkflowRun,
            resp_wr.json(),
        )
        file = benchmark_files[workflow_run["name"]]

        with open(file) as f:
            yaml_data = yaml.safe_load(f.read())

        # Find the jobs data for the workflow_run
        workflow_run["jobs_url"]
        resp_jobs = self.get(workflow_run["jobs_url"])
        if resp_jobs.status_code != 200:
            # TODO: Add a retry ?
            self.logger.warning(
                "GitHub response error: %s",
                resp_wr.text,
                status_code=resp_wr.status_code,
            )
            return []

        job_list = typing.cast(github_types.GitHubJobRunList, resp_jobs.json())
        for job in job_list["jobs"]:
            # Retrieve all the infos we will put in the CSV from the job name
            job_infos = get_infos_from_github_job_name(job["name"])
            yaml_job_data = get_job_dict_from_yaml_data_and_job_name(
                yaml_data,
                job["name"],
            )

            if yaml_job_data is None:
                self.logger.error(
                    "Could not find job '%s' data in yaml file '%s'",
                    job["name"],
                    file.name,
                )
                # TODO: Custom exception
                raise Exception  # noqa

            build_steps_of_benchmark_job = get_job_steps_names_from_yaml_job_data(
                yaml_job_data,
            )

            time_per_step = get_time_spent_per_job_step(
                job["steps"],
                build_steps_of_benchmark_job,
            )

            for step_name, time_spent in time_per_step.items():
                if step_name in constants.GITHUB_JOB_STEPS:
                    additional_infos = "GitHub Step"
                else:
                    additional_infos = job_infos.additional_infos

                csv_data.append(
                    types.CsvDataLine(
                        "GitHub",
                        job_infos.runner_os,
                        job_infos.runner_type,
                        job_infos.tested_repository,
                        step_name,
                        int(time_spent.total_seconds()),
                        additional_infos,
                    ),
                )

        return csv_data

    def generate_csv_data_from_workflows_ids(
        self,
        workflows_ids: list[str],
        repository_owner: str,
        repository_name: str,
    ) -> list[types.CsvDataLine]:
        benchmark_files = utils.get_github_benchmark_file_by_yaml_name_section()

        csv_data: list[types.CsvDataLine] = []

        for workflow_id in workflows_ids:
            csv_data.extend(
                self._get_workflow_csv_data(
                    benchmark_files,
                    workflow_id,
                    repository_owner,
                    repository_name,
                ),
            )

        return csv_data
