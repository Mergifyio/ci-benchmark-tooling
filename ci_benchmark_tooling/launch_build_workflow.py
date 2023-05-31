#!/usr/bin/env python3

import argparse
import asyncio
import getpass
import logging
import os

import daiquiri
import httpx


daiquiri.setup(level=logging.INFO)

LOG = daiquiri.getLogger(__name__)


class AsyncGithubClient(httpx.AsyncClient):
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


def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="launch_build_workflow",
        description="Launch GitHub action build workflow on a GitHub repository",
    )

    parser.add_argument(
        "repository",
        type=str,
        help=(
            'Name of the repository. Format (without quotes): "owner/repository".'
            " Example: Mergifyio/mergify"
        ),
    )
    parser.add_argument(
        "workflow_name",
        type=str,
        help="Name of the file containing the build workflow. Example: build.yml",
    )
    parser.add_argument(
        "-e",
        "--github_token_env",
        type=str,
        default=None,
        help=(
            "Name of the environment variable from which to fetch the GitHub token, "
            "it must have the `actions:write` permission. If not specified, you will "
            "be prompted to enter it when running the script."
        ),
    )
    parser.add_argument(
        "--ref",
        type=str,
        default="main",
        help="Name of the reference on which to execute the build workflow",
    )

    return parser


async def do_github_request(
    token: str,
    owner: str,
    repository: str,
    workflow_name: str,
    ref: str,
) -> int:
    client = AsyncGithubClient(token)
    # NOTE: Should we allow to specify workflow inputs ?
    resp = await client.post(
        f"/repos/{owner}/{repository}/actions/workflows/{workflow_name}/dispatches",
        json={
            "ref": ref,
        },
    )
    if resp.status_code != 204:
        LOG.error(
            "Workflow dispatch request failed: %s",
            resp.text,
            status_code=resp.status_code,
        )
        return 1

    LOG.info("Workflow dispatch successful")

    # TODO:
    # - Retrieve latest workflow run on the repo
    # - Wait for it to finish
    # - Retrieve time spent (per step ?)

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = get_parser()

    args = parser.parse_args(argv)

    owner, repository = args.repository.split("/")

    if args.github_token_env:
        token = os.getenv(args.github_token_env)
        if not token:
            LOG.error(
                "Could not find any token under environment variable "
                f'"{args.github_token_env}"',
            )
            return 1

    else:
        token = getpass.getpass(prompt="GitHub Token: ")

    return asyncio.run(
        do_github_request(token, owner, repository, args.workflow_name, args.ref),
    )
