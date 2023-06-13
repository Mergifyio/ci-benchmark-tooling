import time
import typing

import yaml

from ci_benchmark_tooling import constants
from ci_benchmark_tooling import types
from ci_benchmark_tooling import utils
from ci_benchmark_tooling.clients import base
from ci_benchmark_tooling.http_types import circleci_types


BASE_URL_V1_1 = "https://circleci.com/api/v1.1"


def get_time_spent_per_job_steps(
    steps: list[circleci_types.JobDetailsStep],
) -> dict[str, int]:
    time_per_step = {}
    for step in steps:
        # Skip the time spent cloning the repository we are testing since
        # it is not relevant to the benchmarking
        if step["name"].startswith("Clone "):
            continue

        if step["name"] not in constants.CIRCLECI_JOB_STEPS:
            step_name = constants.CSV_BENCHMARKED_APPLICATION_STEP_NAME
        else:
            step_name = step["name"]

        if step_name not in time_per_step:
            time_per_step[step_name] = int(step["actions"][0]["run_time_millis"] / 1000)
        else:
            time_per_step[step_name] += int(
                step["actions"][0]["run_time_millis"] / 1000,
            )

    return time_per_step


def get_machine_image_from_job_name_and_yaml_string(
    yml_string: str,
    job_name: str,
) -> str:
    yml_dict = yaml.safe_load(yml_string)

    if "machine" in yml_dict["jobs"][job_name]:
        # Need to cast the return into str because the whole dict is of type Any
        return str(yml_dict["jobs"][job_name]["machine"]["image"])

    # macos image
    return f"xcode:{yml_dict['jobs'][job_name]['macos']['xcode']}"


class CircleCiClient(base.BaseClient):
    def __init__(self, token: str) -> None:
        super().__init__(
            base_url="https://circleci.com/api/v2",
            headers={
                "Accept": "application/json",
                "Circle-Token": token,
            },
            http2=True,
        )
        self.pipeline_id: str | None = None

    ##############################
    ############ WORKFLOW DISPATCH
    ##############################

    def get_workflows_ids_of_pipeline(self, pipeline_id: str) -> str:
        """
        Returns the list of workflows ids of a pipeline as a comma-separated list.

        If circleci's endpoint return some empty ids, which can happen when the request
        is made too fast after the pipeline was created, then we retry 2 seconds later.
        The retry is made until all ids of a workflows of a pipeline are filled.
        """

        while True:
            time.sleep(2)

            resp_pipeline_workflows = self.get(f"/pipeline/{pipeline_id}/workflow")

            if any(not w["id"] for w in resp_pipeline_workflows.json()["items"]):
                continue

            return ",".join(
                [w["id"] for w in resp_pipeline_workflows.json()["items"]],
            )

    def send_dispatch_events(
        self,
        repository_owner: str,
        repository_name: str,
        workflow_dispatch_ref: str,
    ) -> int:
        self.logger.info("Sending dispatch events for CircleCI workflows")

        resp_new_pipeline = self.post(
            f"/project/github/{repository_owner}/{repository_name}/pipeline",
            json={"branch": workflow_dispatch_ref},
        )
        if resp_new_pipeline.status_code != 201:
            self.logger.error(
                "Failed to create new pipeline: %s",
                resp_new_pipeline.text,
                status_code=resp_new_pipeline.status_code,
            )
            return 1

        self.pipeline_id = resp_new_pipeline.json()["id"]
        self.logger.info("New pipeline ID: %s", self.pipeline_id)

        if self.pipeline_id is None:
            raise RuntimeError("self.pipeline_id should not be None")

        workflows_ids_for_env = self.get_workflows_ids_of_pipeline(self.pipeline_id)
        self.logger.info("Workflows IDS: %s", workflows_ids_for_env)

        utils.write_workflow_ids_to_github_env(
            constants.CIRCLECI_WORKFLOW_IDS_ENV_PREFIX,
            workflows_ids_for_env,
        )

        return 0

    def wait_for_workflows_to_end(self) -> None:
        self.logger.info("Starting workflows polling...")

        while True:
            resp_pipeline_workflows = self.get(
                f"/pipeline/{self.pipeline_id}/workflow",
            )

            if all(
                w["stopped_at"] is not None
                for w in resp_pipeline_workflows.json()["items"]
            ):
                return

            time.sleep(60)

    ##############################
    ############ CSV RELATED STUFF
    ##############################

    def generate_csv_data_from_workflows_ids(
        self,
        workflows_ids: list[str],
        repository_owner: str,
        repository_name: str,
    ) -> list[types.CsvDataLine]:
        csv_data: list[types.CsvDataLine] = []

        for workflow_id in workflows_ids:
            resp_wf_jobs = self.get(f"/workflow/{workflow_id}/job")

            jobs = typing.cast(
                circleci_types.WorkflowsJobs,
                resp_wf_jobs.json(),
            )
            for job in jobs["items"]:
                # The v2 api doesn't have build time per steps, so we need to use v1.1
                resp_job_details = self.get(
                    f"{BASE_URL_V1_1}/project/github/{repository_owner}/{repository_name}/{job['job_number']}",
                )

                details = typing.cast(
                    circleci_types.JobDetails,
                    resp_job_details.json(),
                )

                tested_repository = details["workflows"]["workflow_name"].replace(
                    "Benchmark ",
                    "",
                )

                time_per_step = get_time_spent_per_job_steps(details["steps"])
                runner_os = get_machine_image_from_job_name_and_yaml_string(
                    details["circle_yml"]["string"],
                    details["workflows"]["job_name"],
                )

                for step_name, time_spent in time_per_step.items():
                    additional_infos = ""
                    if step_name in constants.CIRCLECI_JOB_STEPS:
                        additional_infos = "CircleCI machine setup step"

                    csv_data.append(
                        types.CsvDataLine(
                            "CircleCI",
                            runner_os,
                            details["picard"]["resource_class"]["cpu"],
                            tested_repository,
                            step_name,
                            time_spent,
                            additional_infos,
                        ),
                    )

        return csv_data
