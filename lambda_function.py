# lambda_function.py
from temporalio.contrib.aws.lambda_worker import LambdaWorkerConfig, run_worker
from temporalio.worker import WorkerDeploymentVersion
from temporalio.common import VersioningBehavior

from workflow import LoanUnderwritingWorkflow
from tools import credit_check, calculate_debt_to_income

def configure(config: LambdaWorkerConfig) -> None:
    config.worker_config["task_queue"] = "loan-underwriting"
    config.worker_config["workflows"] = [LoanUnderwritingWorkflow]
    config.worker_config["activities"] = [credit_check, calculate_debt_to_income]
    # Set a default versioning behavior at the worker level
    config.worker_config["default_versioning_behavior"] = VersioningBehavior.PINNED

lambda_handler = run_worker(
    WorkerDeploymentVersion(
        deployment_name="loan-underwriting-app",
        build_id="build-1",
    ),
    configure,
)