"""Temporal worker for the loan underwriting demo."""

import asyncio
import os

from dotenv import load_dotenv
from temporalio.client import Client
from temporalio.contrib.strands import StrandsPlugin
from temporalio.worker import Worker

from tools import calculate_debt_to_income, credit_check
from workflow import LoanUnderwritingWorkflow

load_dotenv()

TASK_QUEUE = "loan-underwriting"


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
        workflows=[LoanUnderwritingWorkflow],
        activities=[credit_check, calculate_debt_to_income],
    )
    print(f"🏦  Loan Underwriting Worker started on task queue: {TASK_QUEUE}")
    print("    Ctrl+C to stop.\n")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
