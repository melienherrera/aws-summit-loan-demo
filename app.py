import asyncio
import os
import random
import re
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from nanoid import generate
from pydantic import BaseModel, Field
from temporalio.client import Client

from profiles import PROFILES, get_profile
from shared import LoanApplicant
from supervisor import LoanUnderwritingSupervisorWorkflow
from workflow import LoanUnderwritingWorkflow

load_dotenv()

app = FastAPI(title="Temporal Loan Underwriting Demo")
app.mount("/static", StaticFiles(directory="static"), name="static")

TASK_QUEUE = "loan-underwriting"
_client: Optional[Client] = None


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


async def get_client() -> Client:
    global _client
    if _client is None:
        _client = await Client.connect(
            os.environ.get("TEMPORAL_ADDRESS", "localhost:7233"),
            **_temporal_connect_options(),
        )
    return _client


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------


@app.get("/")
async def root():
    return FileResponse("static/index.html")


@app.get("/profiles")
async def list_profiles():
    return [
        {
            "id": p.id,
            "name": p.name,
            "occupation": p.occupation,
            "loan_amount": p.loan_amount,
            "loan_purpose": p.loan_purpose,
            "annual_income": p.annual_income,
            "credit_score": p.credit_score,
            "fun_fact": p.fun_fact,
        }
        for p in PROFILES
    ]


class CustomApplicantRequest(BaseModel):
    name: str
    occupation: str
    loan_amount: float
    annual_income: float
    loan_purpose: str


class BulkApplyRequest(BaseModel):
    count: int = 100


class BulkDecideRequest(BaseModel):
    decision: str  # "approve" or "reject"
    workflow_ids: list[str] = Field(default_factory=list)


def _infer_credit_score(annual_income: float) -> int:
    """Assign a plausible credit score based on income tier."""
    if annual_income <= 0:
        return 0
    elif annual_income < 37500:
        return random.randint(480, 580)
    elif annual_income < 75000:
        return random.randint(580, 670)
    elif annual_income < 150000:
        return random.randint(670, 740)
    else:
        return random.randint(740, 820)


def _build_dummy_applicant(index: int) -> LoanApplicant:
    """Generate a dummy applicant payload for bulk workflow starts."""
    occupations = [
        "Software Engineer",
        "Teacher",
        "Marketing Manager",
        "Retail Associate",
        "Freelancer",
        "Nurse",
        "Operations Analyst",
    ]
    loan_purposes = [
        "Home improvement",
        "Debt consolidation",
        "Business expansion",
        "Education",
        "Vehicle purchase",
    ]
    annual_income = random.choice([48_000.0, 72_000.0, 96_000.0, 130_000.0, 180_000.0])
    loan_amount = random.choice([10_000.0, 20_000.0, 35_000.0, 50_000.0, 75_000.0])
    applicant_id = f"bulk-{index + 1:03d}-{generate(size=4)}"

    return LoanApplicant(
        id=applicant_id,
        name=f"Demo Applicant {index + 1}",
        occupation=random.choice(occupations),
        loan_amount=loan_amount,
        loan_purpose=random.choice(loan_purposes),
        annual_income=annual_income,
        credit_score=_infer_credit_score(annual_income),
        fun_fact="Generated demo payload for bulk workflow start.",
    )


async def _start_application_workflow(client: Client, applicant: LoanApplicant) -> str:
    """Start the supervisor underwriting workflow (LENNY over sub-agents)."""
    workflow_id = f"loan-{applicant.id}-{generate(size=6)}"
    await client.start_workflow(
        LoanUnderwritingSupervisorWorkflow.run,
        applicant,
        id=workflow_id,
        task_queue=TASK_QUEUE,
    )
    return workflow_id


async def _signal_decision(client: Client, workflow_id: str, decision: str) -> None:
    """Send an approve/reject signal (by name, so it works for any workflow)."""
    handle = client.get_workflow_handle(workflow_id)
    if decision == "approve":
        await handle.signal("approve")
    elif decision == "reject":
        await handle.signal("reject")
    else:
        raise HTTPException(status_code=400, detail="decision must be 'approve' or 'reject'")


# NOTE: /apply/custom MUST be defined before /apply/{profile_id}
# otherwise FastAPI matches "custom" as a profile_id param.
@app.post("/apply/custom")
async def apply_custom(body: CustomApplicantRequest):
    applicant_id = "custom-" + re.sub(r"[^a-z0-9]", "-", body.name.lower())[:20]
    applicant = LoanApplicant(
        id=applicant_id,
        name=body.name,
        occupation=body.occupation,
        loan_amount=body.loan_amount,
        loan_purpose=body.loan_purpose,
        annual_income=body.annual_income,
        credit_score=_infer_credit_score(body.annual_income),
        fun_fact=f"Application submitted directly at the booth. Occupation: {body.occupation}.",
    )

    client = await get_client()
    workflow_id = await _start_application_workflow(client, applicant)

    return {"workflow_id": workflow_id}


@app.post("/apply/bulk")
async def apply_bulk(body: BulkApplyRequest):
    count = max(1, min(body.count, 100))
    client = await get_client()
    applicants = [_build_dummy_applicant(i) for i in range(count)]

    workflow_ids = await asyncio.gather(
        *(
            client.start_workflow(
                LoanUnderwritingWorkflow.run,
                applicant,
                id=f"loan-{applicant.id}-{generate(size=6)}",
                task_queue=TASK_QUEUE,
            )
            for applicant in applicants
        )
    )

    return {
        "started": len(workflow_ids),
        "workflow_ids": [handle.id for handle in workflow_ids],
    }


@app.post("/apply/{profile_id}")
async def apply(profile_id: str):
    applicant = get_profile(profile_id)
    if not applicant:
        raise HTTPException(status_code=404, detail=f"Profile '{profile_id}' not found")

    client = await get_client()
    workflow_id = await _start_application_workflow(client, applicant)

    return {"workflow_id": workflow_id}


@app.get("/assessment/{workflow_id}")
async def get_assessment(workflow_id: str):
    client = await get_client()
    handle = client.get_workflow_handle(workflow_id)
    assessment = await handle.query("get_assessment")
    return {"assessment": assessment, "ready": assessment is not None}


class DecideRequest(BaseModel):
    decision: str  # "approve" or "reject"


@app.post("/decide/{workflow_id}")
async def decide(workflow_id: str, body: DecideRequest):
    client = await get_client()
    await _signal_decision(client, workflow_id, body.decision)

    return {"status": "signal sent"}


@app.post("/decide-bulk")
async def decide_bulk(body: BulkDecideRequest):
    if not body.workflow_ids:
        raise HTTPException(status_code=400, detail="workflow_ids cannot be empty")

    if body.decision not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="decision must be 'approve' or 'reject'")

    client = await get_client()
    results = await asyncio.gather(
        *(_signal_decision(client, workflow_id, body.decision) for workflow_id in body.workflow_ids),
        return_exceptions=True,
    )
    signaled = sum(1 for result in results if not isinstance(result, Exception))
    failed = len(results) - signaled

    return {
        "requested": len(body.workflow_ids),
        "decision": body.decision,
        "signaled": signaled,
        "failed": failed,
    }


@app.get("/result/{workflow_id}")
async def get_result(workflow_id: str):
    client = await get_client()
    handle = client.get_workflow_handle(workflow_id)
    # Query by name (returns a plain dict), so this works for the supervisor
    # decision (incl. fraud/employment fields) and the single-agent decision alike.
    result = await handle.query("get_final_decision")
    if result is None:
        return {"ready": False}
    if isinstance(result, dict):
        return {"ready": True, **result}
    return {"ready": True, "decision": result}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)