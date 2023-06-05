#!/usr/bin/env python3

import datetime
import logging
import os
import sys
import time
import zoneinfo

import daiquiri

from ci_benchmark_tooling import utils


UTC = zoneinfo.ZoneInfo("UTC")
daiquiri.setup(level=logging.INFO)
LOG = daiquiri.getLogger(__name__)


def send_dispatch_event_for_benchmark_files(
    client: utils.GitHubClient,
    gh_token: str,
    owner: str,
    repository: str,
    workflow_dispatch_ref: str,
    benchmark_filenames: list[str],
) -> int:
    client = utils.GitHubClient(gh_token)
    for benchmark_filename in benchmark_filenames:
        resp = client.post(
            f"/repos/{owner}/{repository}/actions/workflows/{benchmark_filename}/dispatches",
            json={
                "ref": workflow_dispatch_ref,
            },
        )
        if resp.status_code != 204:
            LOG.error(
                "Workflow dispatch request failed: %s",
                resp.text,
                status_code=resp.status_code,
            )
            return 1

        LOG.info("Dispatch event successfuly sent for %s", benchmark_filename)

    return 0


def retrieve_workflow_run_ids(
    client: utils.GitHubClient,
    owner: str,
    repository: str,
    now_as_str: str,
    workflows_ids: dict[str, int],
) -> None:
    while -1 in workflows_ids.values():
        required_names = [k for k, v in workflows_ids.items() if v == -1]

        resp_wr = client.get(
            f"/repos/{owner}/{repository}/actions/runs",
            params={
                "event": "workflow_dispatch",
                "created": f"{now_as_str}..*",
            },
        )

        if resp_wr.status_code != 200:
            LOG.warning(
                "GitHub response error: %s",
                resp_wr.text,
                status_code=resp_wr.status_code,
            )
            time.sleep(2)
            continue

        for workflow_run in resp_wr.json()["workflow_runs"]:
            if workflow_run["name"] in required_names:
                workflows_ids[workflow_run["name"]] = workflow_run["id"]
                LOG.info(
                    "Found workflow_id (%s) for workflow '%s'",
                    workflow_run["id"],
                    workflow_run["name"],
                )

        time.sleep(2)


def wait_for_workflow_runs_to_end(
    client: utils.GitHubClient,
    owner: str,
    repository: str,
    workflows_ids: dict[str, int],
) -> None:
    LOG.info("Starting workflows polling...")

    while workflows_ids:
        keys_to_del = []
        for workflow_name, run_id in workflows_ids.items():
            resp_wr = client.get(f"/repos/{owner}/{repository}/actions/runs/{run_id}")

            if resp_wr.status_code != 200:
                LOG.warning(
                    "GitHub response error: %s",
                    resp_wr.text,
                    status_code=resp_wr.status_code,
                )
                continue

            if resp_wr.json()["conclusion"] is not None:
                LOG.info("Workflow %s finished", workflow_name)
                keys_to_del.append(workflow_name)

        for key in keys_to_del:
            del workflows_ids[key]

        if not workflows_ids:
            return

        time.sleep(60)


def main(_argv: list[str] | None = None) -> int:
    gh_token = utils.get_required_env_variable("GH_TOKEN")

    github_repository = utils.get_required_env_variable("GITHUB_REPOSITORY")
    owner, repository = github_repository.split("/")

    workflow_dispatch_ref = os.getenv("WORKFLOW_DISPATCH_REF", "main")

    client = utils.GitHubClient(gh_token)
    benchmark_files = list(utils.get_benchmark_filenames_and_yaml_name_section())

    LOG.info("Benchmark files found: %s", benchmark_files)

    # Need to retrieve `datetime.now` before the dispatch requests so we can properly
    # filter the workflow_runs
    now = datetime.datetime.now(tz=UTC)
    now_as_str = now.strftime("%Y-%m-%dT%H:%M:%S")
    # GitHub needs the utcoffset to be "+XX:XX", the `%z` option of
    # `strftime` returns us "+XXXX", so we need to manually add the `:`
    z = now.strftime("%z")
    now_as_str += f"{z[:3]}:{z[3:]}"

    ret_value = send_dispatch_event_for_benchmark_files(
        client,
        gh_token,
        owner,
        repository,
        workflow_dispatch_ref,
        [f.filename for f in benchmark_files],
    )
    if ret_value != 0:
        return ret_value

    benchmark_workflow_runs_ids: dict[str, int] = {
        f.yaml_name_section_value: -1 for f in benchmark_files
    }

    retrieve_workflow_run_ids(
        client,
        owner,
        repository,
        now_as_str,
        benchmark_workflow_runs_ids,
    )

    LOG.info(
        "Workflow IDs of the latest launched benchmarks: %s",
        benchmark_workflow_runs_ids.values(),
    )

    benchmkark_workflow_run_ids_for_env = ",".join(
        map(str, benchmark_workflow_runs_ids.values()),
    )
    github_env_file = os.getenv("GITHUB_ENV")
    if github_env_file:
        with open(github_env_file, "a") as f:
            print(
                f"BENCHMARK_WORKFLOW_RUN_IDS={benchmkark_workflow_run_ids_for_env}",
                file=f,
            )
    else:
        os.environ["BENCHMARK_WORKFLOW_RUN_IDS"] = benchmkark_workflow_run_ids_for_env

    wait_for_workflow_runs_to_end(
        client,
        owner,
        repository,
        benchmark_workflow_runs_ids,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
