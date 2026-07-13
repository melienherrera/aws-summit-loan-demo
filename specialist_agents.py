"""Two Temporal Strands specialist agents for the loan demo.

Built in the same style as the base LoanUnderwritingWorkflow (LENNY): each
agent is a `TemporalAgent` running inside its own workflow, with its tools
wrapped via `activity_as_tool` so every tool call is a durable, retryable
Temporal activity.

  1. FraudIdentityAgent        — "is this applicant real and not committing fraud?"
  2. EmploymentVerificationAgent — "is the declared income actually true?"

These run as CHILD WORKFLOWS of LoanUnderwritingSupervisorWorkflow (supervisor.py),
which fans them out in parallel and then lets LENNY aggregate + decide.

The tool activities (in specialist_tools.py) are mocked for the demo. There is
no AgentCore / code interpreter — every tool call is a short, bounded activity,
so the agent loops stay within AWS Lambda execution limits when deployed as
Temporal Serverless Workers.
"""

import os
from dataclasses import dataclass, field
from datetime import timedelta

from temporalio import workflow
from temporalio.contrib.strands import TemporalAgent
from temporalio.contrib.strands.workflow import activity_as_tool
from temporalio.common import RetryPolicy, VersioningBehavior

_versioning_kwargs = (
    {"versioning_behavior": VersioningBehavior.PINNED}
    if os.environ.get("TEMPORAL_ENV") == "cloud"
    else {}
)

with workflow.unsafe.imports_passed_through():
    from shared import LoanApplicant
    from specialist_prompts import (
        EMPLOYMENT_VERIFICATION_SYSTEM_PROMPT,
        FRAUD_IDENTITY_SYSTEM_PROMPT,
    )
    from specialist_tools import (
        check_application_velocity,
        cross_check_income,
        verify_employer,
        verify_identity_documents,
    )

# ---------------------------------------------------------------------------
# Structured results (returned by the child workflows to the supervisor)
# ---------------------------------------------------------------------------


@dataclass
class FraudAssessment:
    applicant_name: str
    fraud_risk: str          # LOW | MEDIUM | HIGH
    recommendation: str      # PROCEED | REVIEW | HALT
    flags: list[str] = field(default_factory=list)
    reasoning: str = ""
    raw_assessment: str = ""


@dataclass
class EmploymentAssessment:
    applicant_name: str
    confidence: str          # LOW | MEDIUM | HIGH
    recommendation: str      # VERIFIED | DISCREPANCY | UNVERIFIABLE
    reasoning: str = ""
    raw_assessment: str = ""


# ---------------------------------------------------------------------------
# Small parsing helper (pure + deterministic — safe inside the workflow)
# ---------------------------------------------------------------------------


def _field(assessment: str, label: str) -> str:
    """Pull the value of a 'LABEL: value' line out of the agent's response."""
    for line in assessment.splitlines():
        if line.strip().upper().startswith(label.upper() + ":"):
            return line.split(":", 1)[-1].strip()
    return ""


# ---------------------------------------------------------------------------
# Agent 1 — Fraud & Identity Verification
# ---------------------------------------------------------------------------


@workflow.defn(**_versioning_kwargs)
class FraudIdentityAgent:
    def __init__(self) -> None:
        self.agent = TemporalAgent(
            start_to_close_timeout=timedelta(seconds=60),
            tools=[
                activity_as_tool(
                    verify_identity_documents,
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=RetryPolicy(
                        initial_interval=timedelta(seconds=2),
                        maximum_attempts=3,
                    ),
                ),
                activity_as_tool(
                    check_application_velocity,
                    start_to_close_timeout=timedelta(seconds=30),
                ),
            ],
            system_prompt=FRAUD_IDENTITY_SYSTEM_PROMPT,
        )

    @workflow.run
    async def run(self, applicant: LoanApplicant) -> FraudAssessment:
        prompt = (
            f"Assess this applicant for identity and fraud risk.\n\n"
            f"Applicant ID: {applicant.id}\n"
            f"Name: {applicant.name}\n"
            f"Occupation: {applicant.occupation}\n"
            f"Loan Amount: ${applicant.loan_amount:,.2f}\n"
            f"Intake notes: {applicant.fun_fact}\n\n"
            f"Call verify_identity_documents and check_application_velocity using "
            f"applicant ID '{applicant.id}'."
        )

        result = str(await self.agent.invoke_async(prompt))

        recommendation = (_field(result, "RECOMMENDATION") or "REVIEW").upper().split()[0]
        if recommendation not in ("PROCEED", "REVIEW", "HALT"):
            recommendation = "REVIEW"  # safe default

        fraud_risk = (_field(result, "FRAUD RISK") or "MEDIUM").upper().split()[0]

        flags_raw = _field(result, "FLAGS")
        flags = (
            [f.strip() for f in flags_raw.split(",") if f.strip()]
            if flags_raw and flags_raw.upper() != "NONE"
            else []
        )

        return FraudAssessment(
            applicant_name=applicant.name,
            fraud_risk=fraud_risk,
            recommendation=recommendation,
            flags=flags,
            reasoning=_field(result, "REASONING"),
            raw_assessment=result,
        )


# ---------------------------------------------------------------------------
# Agent 2 — Employment & Income Verification
# ---------------------------------------------------------------------------


@workflow.defn(**_versioning_kwargs)
class EmploymentVerificationAgent:
    def __init__(self) -> None:
        self.agent = TemporalAgent(
            start_to_close_timeout=timedelta(seconds=60),
            tools=[
                activity_as_tool(verify_employer, start_to_close_timeout=timedelta(seconds=30)),
                activity_as_tool(cross_check_income, start_to_close_timeout=timedelta(seconds=30)),
            ],
            system_prompt=EMPLOYMENT_VERIFICATION_SYSTEM_PROMPT,
        )

    @workflow.run
    async def run(self, applicant: LoanApplicant) -> EmploymentAssessment:
        prompt = (
            f"Verify this applicant's employment and income.\n\n"
            f"Applicant ID: {applicant.id}\n"
            f"Name: {applicant.name}\n"
            f"Occupation: {applicant.occupation}\n"
            f"Declared Annual Income: ${applicant.annual_income:,.2f}\n\n"
            f"Call verify_employer with applicant ID '{applicant.id}', then "
            f"cross_check_income with applicant ID '{applicant.id}' and declared "
            f"annual income {applicant.annual_income}."
        )

        result = str(await self.agent.invoke_async(prompt))

        recommendation = (_field(result, "RECOMMENDATION") or "DISCREPANCY").upper().split()[0]
        if recommendation not in ("VERIFIED", "DISCREPANCY", "UNVERIFIABLE"):
            recommendation = "DISCREPANCY"  # safe default

        confidence = (_field(result, "CONFIDENCE") or "LOW").upper().split()[0]

        return EmploymentAssessment(
            applicant_name=applicant.name,
            confidence=confidence,
            recommendation=recommendation,
            reasoning=_field(result, "REASONING"),
            raw_assessment=result,
        )


# Backward/alternate naming compatibility.
EmployeeVerificationAgent = EmploymentVerificationAgent
