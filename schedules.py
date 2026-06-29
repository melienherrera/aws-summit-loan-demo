"""schedule_demo.py — Start the loan workflow on a Temporal Schedule every 10 minutes, 5 times total.
 
Usage:
    uv run schedule_demo.py
 
    # Delete the schedule when done
    uv run schedule_demo.py --delete
"""
 
import asyncio
import os
import sys
from datetime import timedelta
 
from dotenv import load_dotenv
from nanoid import generate
from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleIntervalSpec,
    ScheduleSpec,
    ScheduleState,
)
 
from profiles import get_random_profile
from workflow import LoanUnderwritingWorkflow
 
load_dotenv()
 
TASK_QUEUE = "loan-underwriting"
SCHEDULE_ID = "loan-demo-schedule"
 
 
async def connect() -> Client:
    address = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
    namespace = os.environ.get("TEMPORAL_NAMESPACE", "default")
    api_key = os.environ.get("TEMPORAL_API_KEY")
    kwargs: dict = {"namespace": namespace}
    if api_key or ".tmprl.cloud" in address:
        kwargs["tls"] = True
    if api_key:
        kwargs["api_key"] = api_key
    return await Client.connect(address, **kwargs)
 
 
async def create_schedule(client: Client) -> None:
    applicant = get_random_profile()
 
    await client.create_schedule(
        SCHEDULE_ID,
        Schedule(
            action=ScheduleActionStartWorkflow(
                LoanUnderwritingWorkflow.run,
                applicant,
                id=f"loan-{applicant.id}-{generate(size=6)}",
                task_queue=TASK_QUEUE,
            ),
            spec=ScheduleSpec(
                intervals=[ScheduleIntervalSpec(every=timedelta(minutes=10))]
            ),
            state=ScheduleState(
                limited_actions=True,
                remaining_actions=5,
                note="Loan demo — fires 5 times every 10 minutes",
            ),
        ),
    )
    print(f"✅  Schedule '{SCHEDULE_ID}' created.")
    print(f"    Applicant  : {applicant.name}")
    print(f"    Loan ask   : ${applicant.loan_amount:,.0f}")
    print(f"    Interval   : every 10 minutes")
    print(f"    Runs       : 5 total, then stops automatically")
 
 
async def delete_schedule(client: Client) -> None:
    handle = client.get_schedule_handle(SCHEDULE_ID)
    await handle.delete()
    print(f"🗑️  Schedule '{SCHEDULE_ID}' deleted.")
 
 
async def main() -> None:
    client = await connect()
 
    if "--delete" in sys.argv:
        await delete_schedule(client)
        return
 
    await create_schedule(client)
 
 
if __name__ == "__main__":
    asyncio.run(main())