"""FastAPI web server for the loan underwriting booth demo."""

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
from pydantic import BaseModel
from temporalio.client import Client

from profiles import PROFILES, get_profile
from shared import LoanApplicant
from workflow import LoanUnderwritingWorkflow

load_dotenv()

app = FastAPI(title="Temporal Loan Underwriting Demo")
app.mount("/static", StaticFiles(directory="static"), name="static")

TASK_QUEUE = "loan-underwriting"
_client: Optional[Client] = None


async def get_client() -> Client:
    global _client
    if _client is None:
        _client = await Client.connect(
            os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
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
    workflow_id = f"loan-{applicant_id}-{generate(size=6)}"

    await client.start_workflow(
        LoanUnderwritingWorkflow.run,
        applicant,
        id=workflow_id,
        task_queue=TASK_QUEUE,
    )

    return {"workflow_id": workflow_id}


@app.post("/apply/{profile_id}")
async def apply(profile_id: str):
    applicant = get_profile(profile_id)
    if not applicant:
        raise HTTPException(status_code=404, detail=f"Profile '{profile_id}' not found")

    client = await get_client()
    workflow_id = f"loan-{profile_id}-{generate(size=6)}"

    await client.start_workflow(
        LoanUnderwritingWorkflow.run,
        applicant,
        id=workflow_id,
        task_queue=TASK_QUEUE,
    )

    return {"workflow_id": workflow_id}


@app.get("/assessment/{workflow_id}")
async def get_assessment(workflow_id: str):
    client = await get_client()
    handle = client.get_workflow_handle(workflow_id)
    assessment = await handle.query(LoanUnderwritingWorkflow.get_assessment)
    return {"assessment": assessment, "ready": assessment is not None}


class DecideRequest(BaseModel):
    decision: str  # "approve" or "reject"


@app.post("/decide/{workflow_id}")
async def decide(workflow_id: str, body: DecideRequest):
    client = await get_client()
    handle = client.get_workflow_handle(workflow_id)

    if body.decision == "approve":
        await handle.signal(LoanUnderwritingWorkflow.approve)
    elif body.decision == "reject":
        await handle.signal(LoanUnderwritingWorkflow.reject)
    else:
        raise HTTPException(status_code=400, detail="decision must be 'approve' or 'reject'")

    return {"status": "signal sent"}


@app.get("/result/{workflow_id}")
async def get_result(workflow_id: str):
    client = await get_client()
    handle = client.get_workflow_handle(workflow_id)
    # Use a query instead of handle.result() to avoid blocking the HTTP request
    result = await handle.query(LoanUnderwritingWorkflow.get_final_decision)
    if result is None:
        return {"ready": False}
    if isinstance(result, dict):
        return {"ready": True, **result}
    return {
        "ready": True,
        "applicant_name": result.applicant_name,
        "ai_recommendation": result.ai_recommendation,
        "human_decision": result.human_decision,
        "human_override": result.human_override,
        "ai_reasoning": result.ai_reasoning,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
