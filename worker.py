# """Temporal worker for the loan underwriting demo."""

# import asyncio
# import os

# from dotenv import load_dotenv
# from temporalio.client import Client
# from temporalio.contrib.strands import StrandsPlugin
# from temporalio.worker import Worker

# from tools import calculate_debt_to_income, credit_check
# from workflow import LoanUnderwritingWorkflow

# load_dotenv()

# TASK_QUEUE = "loan-underwriting"


# def _temporal_connect_options() -> dict[str, str | bool]:
#     """Build Temporal client connection options from environment variables."""
#     options: dict[str, str | bool] = {}
#     namespace = os.environ.get("TEMPORAL_NAMESPACE")
#     api_key = os.environ.get("TEMPORAL_API_KEY")

#     if namespace:
#         options["namespace"] = namespace
#     if api_key:
#         options["api_key"] = api_key
#         options["tls"] = True

#     return options


# async def main() -> None:
#     plugin = StrandsPlugin()
#     client = await Client.connect(
#         os.environ.get("TEMPORAL_ADDRESS", "localhost:7233"),
#         plugins=[plugin],
#         **_temporal_connect_options(),
#     )

#     worker = Worker(
#         client,
#         task_queue=TASK_QUEUE,
#         workflows=[LoanUnderwritingWorkflow],
#         activities=[credit_check, calculate_debt_to_income],
#     )
#     print(f"🏦  Loan Underwriting Worker started on task queue: {TASK_QUEUE}")
#     print("    Ctrl+C to stop.\n")
#     await worker.run()


# if __name__ == "__main__":
#     asyncio.run(main())

"""Temporal worker for the loan underwriting demo.

Registers:
  - LoanUnderwritingWorkflow            (original single-agent LENNY)
  - LoanUnderwritingSupervisorWorkflow  (LENNY as supervisor over sub-agents)
  - FraudIdentityWorkflow               (child workflow / specialist)
  - EmploymentVerificationWorkflow      (child workflow / specialist)
plus the original tools and the four mocked specialist tools as activities.
"""

import asyncio
import os

from dotenv import load_dotenv
from temporalio.client import Client
from temporalio.contrib.strands import StrandsPlugin
from temporalio.worker import Worker

from tools import calculate_debt_to_income, credit_check
from workflow import LoanUnderwritingWorkflow

# Multi-agent additions
from supervisor import LoanUnderwritingSupervisorWorkflow
from specialist_agents import EmploymentVerificationAgent, FraudIdentityAgent
from specialist_tools import (
    check_application_velocity,
    cross_check_income,
    verify_employer,
    verify_identity_documents,
)

load_dotenv()

TASK_QUEUE = "loan-underwriting-local"


def _temporal_connect_options() -> dict[str, str | bool]:
    """Build Temporal client connection options from environment variables."""
    options: dict[str, str | bool] = {}
    namespace = os.environ.get("TEMPORAL_NAMESPACE")
    api_key = os.environ.get("TEMPORAL_API_KEY")

    if namespace:
        options["namespace"] = namespace
    if api_key:
        options["api_key"] = api_key
        options["tls"] = True

    return options


async def main() -> None:
    plugin = StrandsPlugin()
    client = await Client.connect(
        os.environ.get("TEMPORAL_ADDRESS", "localhost:7233"),
        plugins=[plugin],
        **_temporal_connect_options(),
    )

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[
            LoanUnderwritingWorkflow,
            LoanUnderwritingSupervisorWorkflow,
            FraudIdentityAgent,
            EmploymentVerificationAgent,
        ],
        activities=[
            credit_check,
            calculate_debt_to_income,
            verify_identity_documents,
            check_application_velocity,
            verify_employer,
            cross_check_income,
        ],
    )
    print(f"🏦  Loan Underwriting Worker started on task queue: {TASK_QUEUE}")
    print("    Workflows: single-agent + supervisor + 2 specialist sub-agents")
    print("    Ctrl+C to stop.\n")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())