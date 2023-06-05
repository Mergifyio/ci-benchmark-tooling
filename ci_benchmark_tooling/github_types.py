import typing


ISODateTimeType = typing.NewType("ISODateTimeType", str)

GitHubLogin = typing.NewType("GitHubLogin", str)
GitHubAccountType = typing.Literal["User", "Organization", "Bot"]
GitHubAccountIdType = typing.NewType("GitHubAccountIdType", int)


class GitHubAccount(typing.TypedDict):
    login: GitHubLogin
    id: GitHubAccountIdType
    type: GitHubAccountType
    avatar_url: str


SHAType = typing.NewType("SHAType", str)
GitHubRefType = typing.NewType("GitHubRefType", str)
GitHubRepositoryIdType = typing.NewType("GitHubRepositoryIdType", int)
GitHubRepositoryName = typing.NewType("GitHubRepositoryName", str)


class GitHubRepository(typing.TypedDict):
    id: GitHubRepositoryIdType
    owner: GitHubAccount
    private: bool
    name: GitHubRepositoryName
    full_name: str
    archived: bool
    url: str
    html_url: str
    default_branch: GitHubRefType


# https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows
GitHubWorkflowTriggerEventType = typing.Literal[
    "pull_request",
    "pull_request_target",
    "push",
    "schedule",
]

GitHubWorkflowRunConclusionType = typing.Literal[
    "success",
    "failure",
    "skipped",
    "cancelled",
    None,
]


class GitHubWorkflowRun(typing.TypedDict):
    id: int
    workflow_id: int
    name: str
    event: GitHubWorkflowTriggerEventType
    conclusion: GitHubWorkflowRunConclusionType
    triggering_actor: GitHubAccount
    jobs_url: str
    head_sha: SHAType
    repository: GitHubRepository
    run_attempt: int
    run_started_at: ISODateTimeType


GitHubJobRunConclusionType = typing.Literal[
    "success",
    "failure",
    "skipped",
    "cancelled",
]


class GitHubJobRunStep(typing.TypedDict):
    name: str
    status: str
    conclusion: GitHubJobRunConclusionType
    number: int
    started_at: ISODateTimeType
    completed_at: ISODateTimeType


class GitHubJobRun(typing.TypedDict):
    id: int
    run_id: int
    name: str
    conclusion: GitHubJobRunConclusionType
    started_at: ISODateTimeType
    completed_at: ISODateTimeType
    steps: list[GitHubJobRunStep]
    labels: list[str]
    runner_name: str
    workflow_name: str


class GitHubJobRunList(typing.TypedDict):
    total_count: int
    jobs: list[GitHubJobRun]
