#!/usr/bin/env python3

import logging
import os
import sys

import daiquiri

from ci_benchmark_tooling import utils


daiquiri.setup(level=logging.INFO)


def main(_argv: list[str] | None = None) -> int:
    github_repository = utils.get_required_env_variable("GITHUB_REPOSITORY")
    owner, repository = github_repository.split("/")

    workflow_dispatch_ref = os.getenv("WORKFLOW_DISPATCH_REF", "main")

    for ci_to_benchmark in utils.CIS_TO_BENCHMARK:
        token = utils.get_required_env_variable(ci_to_benchmark["token_env_variable"])
        client = ci_to_benchmark["client"](token)

        ret_value = client.send_dispatch_events_and_wait_for_end(
            owner,
            repository,
            workflow_dispatch_ref,
        )
        if ret_value != 0:
            return ret_value

    return 0


if __name__ == "__main__":
    sys.exit(main())
