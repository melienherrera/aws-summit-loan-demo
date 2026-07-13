"""Temporal worker for the loan underwriting demo.

Registers:
  - LoanUnderwritingWorkflow            (original single-agent LENNY)
  - LoanUnderwritingSupervisorWorkflow  (LENNY as supervisor over sub-agents)
  - FraudIdentityWorkflow               (child workflow / specialist)
  - EmploymentVerificationWorkflow      (child workflow / specialist)
plus the original tools and the four mocked specialist tools as activities.
"""

import asyncio

from dotenv import load_dotenv

load_dotenv()  # must run before local imports so workflow.py reads TEMPORAL_ENV at class-definition time

from temporalio.client import Client
from temporalio.contrib.strands import StrandsPlugin
from temporalio.worker import Worker

from shared import temporal_connect_args
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

TASK_QUEUE = "loan-underwriting"


async def main() -> None:
    plugin = StrandsPlugin()
    address, connect_kwargs = temporal_connect_args()
    client = await Client.connect(address, plugins=[plugin], **connect_kwargs)

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
