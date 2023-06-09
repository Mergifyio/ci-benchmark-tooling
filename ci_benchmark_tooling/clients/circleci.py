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
    # Need to cast into str because the whole dict is of type Any
    return str(yml_dict["jobs"][job_name]["machine"]["image"])


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

    ##############################
    ############ WORKFLOW DISPATCH
    ##############################

    def wait_for_pipeline_workflows_to_end(self, pipeline_id: str) -> None:
        self.logger.info("Starting workflows polling...")

        while True:
            resp_pipeline_workflows = self.get(f"/pipeline/{pipeline_id}/workflows")
            if resp_pipeline_workflows.status_code != 200:
                self.logger.warning(
                    "CircleCI response error: %s",
                    resp_pipeline_workflows.text,
                    status_code=resp_pipeline_workflows.status_code,
                )
                continue

            if all(
                w["stopped_at"] is not None
                for w in resp_pipeline_workflows.json()["items"]
            ):
                return

            time.sleep(60)

    def send_dispatch_events_and_wait_for_end(
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

        pipeline_id = resp_new_pipeline.json()["id"]
        self.logger.info("New pipeline ID: %s", pipeline_id)

        resp_pipeline_workflows = self.get(f"/pipeline/{pipeline_id}/workflows")
        if resp_pipeline_workflows.status_code != 200:
            self.logger.error(
                "CircleCI response error: %s",
                resp_pipeline_workflows.text,
                status_code=resp_pipeline_workflows.status_code,
            )
            return 1

        workflows_ids = [w["id"] for w in resp_pipeline_workflows.json()["items"]]
        utils.write_workflow_ids_to_github_env(
            constants.CIRCLECI_WORKFLOW_IDS_ENV_PREFIX,
            ",".join(workflows_ids),
        )

        self.wait_for_pipeline_workflows_to_end(pipeline_id)

        return 0

    ##############################
    ############ CSV RELATED STUFF
    ##############################

    def generate_csv_data_from_workflows_ids(
        self,
        workflows_ids: list[str],
        repository_owner: str,
        repository_name: str,
    ) -> list[types.CsvDataLine]:
        # TODO

        csv_data: list[types.CsvDataLine] = []

        for workflow_id in workflows_ids:
            resp_wf_jobs = self.get(f"/workflow/{workflow_id}/job")
            if resp_wf_jobs.status_code != 200:
                # TODO: Add retry
                self.logger.warning(
                    "CircleCI response error: %s",
                    resp_wf_jobs.text,
                    status_code=resp_wf_jobs.status_code,
                )
                continue

            jobs = typing.cast(
                circleci_types.WorkflowsJobs,
                resp_wf_jobs.json(),
            )
            for job in jobs["items"]:
                # The v2 api doesn't have build time per steps, so we need to use v1.1
                resp_job_details = self.get(
                    f"{BASE_URL_V1_1}/project/github/{repository_owner}/{repository_name}/{job['job_number']}",
                )
                if resp_job_details.status_code != 200:
                    # TODO: Add retry
                    self.logger.warning(
                        "CircleCI response error: %s",
                        resp_job_details.text,
                        status_code=resp_job_details.status_code,
                    )
                    continue

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
                        additional_infos = "CircleCI Step"

                    csv_data.append(
                        types.CsvDataLine(
                            "CircleCI",
                            runner_os,
                            details["picard"]["resource_class"]["class"],
                            tested_repository,
                            step_name,
                            time_spent,
                            additional_infos,
                        ),
                    )

        return csv_data
