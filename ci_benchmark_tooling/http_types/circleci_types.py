import typing

from ci_benchmark_tooling.http_types import base


JobStatusT = typing.Literal[
    "success",
    "running",
    "not_run",
    "failed",
    "retried",
    "queued",
    "not_running",
    "infrastructure_fail",
    "timedout",
    "on_hold",
    "terminated-unknown",
    "blocked",
    "canceled",
    "unauthorized",
]
JobTypeT = typing.Literal["build", "approval"]

UUIDString = typing.NewType("UUIDString", str)


class WorkflowsJob(typing.TypedDict):
    canceled_by: UUIDString
    dependencies: list[UUIDString]
    job_number: int
    id: UUIDString
    started_at: base.ISODateTimeType
    name: str
    approved_by: UUIDString
    project_slug: str
    status: JobStatusT
    type: JobTypeT
    stopped_at: base.ISODateTimeType
    approval_request_id: UUIDString


class WorkflowsJobs(typing.TypedDict):
    items: list[WorkflowsJob]
    next_page_token: str


WorkflowStatusT = typing.Literal[
    "success",
    "running",
    "not_run",
    "failed",
    "error",
    "failing",
    "on_hold",
    "canceled",
    "unauthorized",
]


class Workflow(typing.TypedDict):
    pipeline_id: UUIDString
    canceled_by: UUIDString
    id: UUIDString
    name: str
    project_slug: str
    errored_by: UUIDString
    tag: str
    status: WorkflowStatusT
    started_by: UUIDString
    pipeline_number: str  # string of integer, eg: "25"
    created_at: base.ISODateTimeType
    stopped_at: base.ISODateTimeType


# ###### All the dict belows are from API V1.1:
# ###### https://circleci.com/docs/api/v1/index.html

# https://circleci.com/docs/api/v1/index.html#single-job
# Need to use the functional syntax because of the "class" name
ResourceClass = typing.TypedDict(
    "ResourceClass",
    {
        "class": str,
        "name": str,
        "cpu": int,
        "ram": int,
    },
)


class JobPicard(typing.TypedDict):
    executor: str
    resource_class: ResourceClass


# A lot of keys were omitted for simplicity since they are not going to be used
class JobDetailsStepActions(typing.TypedDict):
    bash_command: str
    end_time: base.ISODateTimeType
    failed: bool | None
    index: int
    name: str
    output_url: str
    run_time_millis: int
    start_time: base.ISODateTimeType
    status: JobStatusT
    step: int


class JobDetailsStep(typing.TypedDict):
    actions: list[JobDetailsStepActions]
    name: str


JobDetailsStatusT = typing.Literal[
    "retried",
    "canceled",
    "infrastructure_fail",
    "timedout",
    "not_run",
    "running",
    "failed",
    "queued",
    "not_running",
    "no_tests",
    "fixed",
    "success",
]

JobDetailsOutcomeT = typing.Literal[
    "canceled",
    "infrastructure_fail",
    "timedout",
    "failed",
    "no_tests",
    "success",
]


class JobDetailsWorkflows(typing.TypedDict):
    job_id: UUIDString
    job_name: str
    workflow_id: UUIDString
    workflow_name: str
    workspace_id: UUIDString


class JobDetails(typing.TypedDict):
    # There is a lot more infos in this dict, but we only type
    # what is interesting to us.
    build_time_millis: int
    circle_yml: dict[str, typing.Any]
    outcome: JobDetailsOutcomeT
    picard: JobPicard
    status: JobDetailsStatusT
    start_time: base.ISODateTimeType
    stop_time: base.ISODateTimeType
    steps: list[JobDetailsStep]
    workflows: JobDetailsWorkflows
