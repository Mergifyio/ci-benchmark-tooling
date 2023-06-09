import zoneinfo


UTC = zoneinfo.ZoneInfo("UTC")

GITHUB_WORKFLOW_IDS_ENV_PREFIX = "GITHUB"
CIRCLECI_WORKFLOW_IDS_ENV_PREFIX = "CIRCLECI"

GITHUB_JOB_STEPS = ("Set up job", "Complete job")
CIRCLECI_JOB_STEPS = ("Spin up environment", "Preparing environment variables")

CSV_BENCHMARKED_APPLICATION_STEP_NAME = "Benchmarked application build"
