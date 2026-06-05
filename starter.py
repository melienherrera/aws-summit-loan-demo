"""Interactive CLI starter for the loan underwriting booth demo.

Usage:
    uv run starter.py              # pick a profile interactively
    uv run starter.py greg-normal  # jump straight to a specific profile
    uv run starter.py --random     # randomly pick a profile
"""

import asyncio
import os
import sys
from typing import Optional

from dotenv import load_dotenv
from nanoid import generate
from temporalio.client import Client

from profiles import PROFILES, get_profile, get_random_profile, list_profiles
from shared import LoanApplicant, LoanDecision
from workflow import LoanUnderwritingWorkflow

load_dotenv()

TASK_QUEUE = "loan-underwriting"


async def _connect_temporal_client() -> Client:
    address = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
    namespace = os.environ.get("TEMPORAL_NAMESPACE", "default")
    api_key = os.environ.get("TEMPORAL_API_KEY")

    connect_kwargs: dict[str, object] = {"namespace": namespace}
    is_cloud_endpoint = ".tmprl.cloud" in address

    if api_key:
        connect_kwargs["api_key"] = api_key

    if api_key or is_cloud_endpoint:
        # Temporal Cloud requires TLS and supports API key auth.
        connect_kwargs["tls"] = True

    return await Client.connect(address, **connect_kwargs)


def _divider() -> None:
    print("\n" + "─" * 60 + "\n")


def _print_profile(applicant: LoanApplicant) -> None:
    _divider()
    print(f"  📁  LOAN APPLICATION #{applicant.id.upper()}")
    print(f"\n  Applicant:   {applicant.name}")
    print(f"  Occupation:  {applicant.occupation}")
    print(f"  Loan Ask:    ${applicant.loan_amount:,.2f}")
    print(f"  Purpose:     {applicant.loan_purpose}")
    print(f"  Income:      ${applicant.annual_income:,.2f}/yr")
    print(f"\n  📌 Notes from intake officer:")
    print(f"     {applicant.fun_fact}")
    _divider()


def _print_assessment(assessment: str) -> None:
    print("  🤖  LENNY'S ASSESSMENT (AI Underwriter)\n")
    for line in assessment.strip().splitlines():
        print(f"     {line}")
    _divider()


def _print_result(decision: LoanDecision) -> None:
    emoji = "✅" if decision.human_decision == "APPROVED" else "❌"
    print(f"\n  {emoji}  FINAL DECISION: {decision.human_decision}")

    if decision.human_override:
        print(
            f"\n  ⚠️  You overruled the AI! LENNY recommended {decision.ai_recommendation}."
        )
        print("     The human remains in control. As it should be.")
    else:
        print(f"\n  🤝  You agreed with LENNY's recommendation of {decision.ai_recommendation}.")

    _divider()
    print(f"  {decision.applicant_name} has been {decision.human_decision}.")

    # Fun per-applicant closing lines
    closings = {
        "Nicolas Cage": "May his castle dreams live on.",
        "Sir Biscuit III": "Woof." if decision.human_decision == "APPROVED" else "*sad tail wag*",
        "Tyler Blockchain": "To the moon. Or not.",
        "Greg Henderson": "Greg will now update his spreadsheet.",
        "Zyx-9 (goes by 'Alex')": "The timeline has been updated accordingly.",
        "Captain Redbeard McGee": "Arr." if decision.human_decision == "APPROVED" else "The sea provides.",
        "Gabriela Santos": "She has already automated this entire process.",
    }
    closing = closings.get(decision.applicant_name)
    if closing:
        print(f"  {closing}")
    _divider()


def _pick_profile() -> Optional[LoanApplicant]:
    args = sys.argv[1:]

    if "--random" in args:
        return get_random_profile()

    if args:
        profile = get_profile(args[0])
        if not profile:
            print(f"Unknown profile ID: '{args[0]}'")
            list_profiles()
        return profile

    # Interactive selection
    list_profiles()
    choice = input("  Enter applicant number or ID (or 'r' for random): ").strip()

    if choice.lower() == "r":
        return get_random_profile()

    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(PROFILES):
            return PROFILES[idx]
        print("Invalid number.")
        return None

    return get_profile(choice)


async def main() -> None:
    applicant = _pick_profile()
    if not applicant:
        return

    _print_profile(applicant)
    input("  Press Enter to submit application and start AI assessment...")

    client = await _connect_temporal_client()

    workflow_id = f"loan-{applicant.id}-{generate(size=6)}"
    handle = await client.start_workflow(
        LoanUnderwritingWorkflow.run,
        applicant,
        id=workflow_id,
        task_queue=TASK_QUEUE,
    )

    print(f"\n  🚀  Workflow started: {workflow_id}")
    print("  ⏳  LENNY is reviewing the application...\n")

    # Poll until the AI assessment is ready
    assessment: Optional[str] = None
    while assessment is None:
        await asyncio.sleep(1)
        assessment = await handle.query(LoanUnderwritingWorkflow.get_assessment)

    _print_assessment(assessment)

    # Human decision
    while True:
        choice = input("  Your decision — [A]pprove or [R]eject? ").strip().lower()
        if choice in ("a", "approve"):
            await handle.signal(LoanUnderwritingWorkflow.approve)
            break
        elif choice in ("r", "reject"):
            await handle.signal(LoanUnderwritingWorkflow.reject)
            break
        else:
            print("  Please enter 'a' to approve or 'r' to reject.")

    print("\n  ⏳  Finalising decision...")
    result: LoanDecision = await handle.result()
    _print_result(result)


if __name__ == "__main__":
    asyncio.run(main())
