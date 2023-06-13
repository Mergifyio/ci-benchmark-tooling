import datetime
import re
import time
import typing

from ci_benchmark_tooling import constants
from ci_benchmark_tooling import types
from ci_benchmark_tooling import utils
from ci_benchmark_tooling.clients import base
from ci_benchmark_tooling.http_types import github_types


RE_IMAGE_NAME_CORES = re.compile(r"-\d+-cores$")


def get_infos_from_github_job_name(job_name: str) -> types.GitHubJobNameInfos:
    if job_name.count(" - ") == 2:
        (
            tested_repository,
            runner_os,
            runner_cores,
        ) = job_name.split(
            " - ",
        )
        additional_infos = ""
    else:
        (
            tested_repository,
            runner_os,
            runner_cores,
            additional_infos,
        ) = job_name.split(
            " - ",
            3,
        )

    # Remove the trailing `-\d+-cores` from the image name, it
    # will be redundant
    runner_os = RE_IMAGE_NAME_CORES.sub("", runner_os)

    runner_cores_int = int(runner_cores.replace(" cores", ""))

    return types.GitHubJobNameInfos(
        tested_repository,
        runner_os,
        runner_cores_int,
        additional_infos,
    )


def get_time_spent_per_job_step(
    job_steps: list[github_types.GitHubJobRunStep],
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
        if s["name"] not in constants.GITHUB_JOB_STEPS:
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
        self.repository_owner: str | None = None
        self.repository_name: str | None = None
        self.workflows_names_and_ids: dict[str, int] | None = None

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
            self.post(
                f"/repos/{owner}/{repository}/actions/workflows/{benchmark_filename}/dispatches",
                json={
                    "ref": workflow_dispatch_ref,
                },
            )

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
        self.workflows_names_and_ids = {
            f.yaml_name_section_value: -1 for f in benchmark_files
        }

        self.retrieve_workflows_ids(
            self.repository_owner,
            self.repository_name,
            now_as_str,
            self.workflows_names_and_ids,
        )

        workflows_ids_for_env = ",".join(
            map(str, self.workflows_names_and_ids.values()),
        )
        self.logger.info("Workflows IDs: %s", workflows_ids_for_env)

        utils.write_workflow_ids_to_github_env(
            constants.GITHUB_WORKFLOW_IDS_ENV_PREFIX,
            workflows_ids_for_env,
        )

        return 0

    def wait_for_workflows_to_end(self) -> None:
        self.logger.info("Starting workflows polling...")

        if self.workflows_names_and_ids is None:
            raise RuntimeError(
                "self.workflows_names_and_ids should not be None",
            )

        workflows_names_and_ids = self.workflows_names_and_ids.copy()
        while workflows_names_and_ids:
            keys_to_del = []
            for workflow_name, run_id in workflows_names_and_ids.items():
                resp_wr = self.get(
                    f"/repos/{self.repository_owner}/{self.repository_name}/actions/runs/{run_id}",
                )

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
        workflow_id: str,
        repository_owner: str,
        repository_name: str,
    ) -> list[types.CsvDataLine]:
        csv_data: list[types.CsvDataLine] = []

        resp_wr = self.get(
            f"/repos/{repository_owner}/{repository_name}/actions/runs/{workflow_id}",
        )

        workflow_run = typing.cast(
            github_types.GitHubWorkflowRun,
            resp_wr.json(),
        )
        # Find the jobs data for the workflow_run
        workflow_run["jobs_url"]
        resp_jobs = self.get(workflow_run["jobs_url"])

        job_list = typing.cast(github_types.GitHubJobRunList, resp_jobs.json())
        for job in job_list["jobs"]:
            # Retrieve all the infos we will put in the CSV from the job name
            job_infos = get_infos_from_github_job_name(job["name"])
            time_per_step = get_time_spent_per_job_step(job["steps"])

            for step_name, time_spent in time_per_step.items():
                if step_name in constants.GITHUB_JOB_STEPS:
                    additional_infos = "GitHub runner setup step"
                else:
                    additional_infos = job_infos.additional_infos

                csv_data.append(
                    types.CsvDataLine(
                        "GitHub",
                        job_infos.runner_os,
                        job_infos.runner_cores,
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
        csv_data: list[types.CsvDataLine] = []

        for workflow_id in workflows_ids:
            csv_data.extend(
                self._get_workflow_csv_data(
                    workflow_id,
                    repository_owner,
                    repository_name,
                ),
            )

        return csv_data
