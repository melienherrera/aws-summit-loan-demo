# lambda_function.py
from temporalio.contrib.aws.lambda_worker import LambdaWorkerConfig, run_worker
from temporalio.contrib.strands import StrandsPlugin
from temporalio.worker import WorkerDeploymentVersion
 
from workflow import LoanUnderwritingWorkflow
from tools import credit_check, calculate_debt_to_income
 
# Multi-agent additions
from supervisor import LoanUnderwritingSupervisorWorkflow
from specialist_agents import EmploymentVerificationAgent, FraudIdentityAgent
from specialist_tools import (
    check_application_velocity,
    cross_check_income,
    verify_employer,
    verify_identity_documents,
)
 
 
def configure(config: LambdaWorkerConfig) -> None:
    config.worker_config["task_queue"] = "loan-underwriting"
    config.worker_config["workflows"] = [
        LoanUnderwritingWorkflow,
        LoanUnderwritingSupervisorWorkflow,
        FraudIdentityAgent,
        EmploymentVerificationAgent,
    ]
    config.worker_config["activities"] = [
        credit_check,
        calculate_debt_to_income,
        verify_identity_documents,
        check_application_velocity,
        verify_employer,
        cross_check_income,
    ]
 
    # CRITICAL: attach the Strands plugin so the agent's invoke_model
    # activity is registered. Without this, the workflow fails with
    # "Activity function invoke_model ... is not registered on this worker".
    config.client_connect_config["plugins"] = [StrandsPlugin()]
 
 
lambda_handler = run_worker(
    WorkerDeploymentVersion(
        deployment_name="loan-underwriting-app",
        build_id="build-1",
    ),
    configure,
)
