"""LENNY as a supervisor workflow over specialist sub-agent child workflows.

Orchestration model:

    LoanUnderwritingSupervisorWorkflow  (LENNY)
        │
        ├── FraudIdentityWorkflow          ── child workflow ─┐
        ├── EmploymentVerificationWorkflow  ── child workflow ─┤  (run in parallel)
        │                                                      │
        ▼                                                      ▼
    LENNY (TemporalAgent) reads both specialist reports, runs
    credit_check + calculate_debt_to_income himself, and synthesizes
    a single APPROVE / REJECT recommendation over all four sources.
        │
        ⏸  pauses for the human underwriter (approve / reject signal)
        │
        ▼
    SupervisorDecision

Each specialist runs as its own child workflow, so each shows up
independently in the Temporal UI, retries on its own, and could later be
routed to its own task queue / worker pool. LENNY keeps credit_check and
calculate_debt_to_income as activity-backed tools, exactly as in the base
demo — the only thing that changed is that two of his inputs now arrive from
durable sub-agents instead of from his own tool calls.
"""

import asyncio
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from temporalio import workflow
from temporalio.contrib.strands import TemporalAgent
from temporalio.contrib.strands.workflow import activity_as_tool
from temporalio.common import RetryPolicy, VersioningBehavior

with workflow.unsafe.imports_passed_through():
    from shared import LoanApplicant
    from tools import calculate_debt_to_income, credit_check
    from specialist_agents import (
        EmploymentAssessment,
        EmploymentVerificationAgent,
        FraudAssessment,
        FraudIdentityAgent,
        _field,
    )

# ---------------------------------------------------------------------------
# Supervisor prompt
# ---------------------------------------------------------------------------

SUPERVISOR_SYSTEM_PROMPT = """You are LENNY, the senior loan underwriting officer at Temporal National Bank,
acting as the supervising decision-maker over a panel of specialist agents.

Two specialists have already assessed this applicant; their full reports are included in the
application below:
- A Fraud & Identity Verification report (is the applicant real, and are there fraud signals?)
- An Employment & Income Verification report (is the declared income actually true?)

You also have two tools you MUST use yourself:
- credit_check: retrieves the applicant's credit score and rating
- calculate_debt_to_income: computes the debt-to-income ratio from income and loan amount

For each application you MUST:
1. Call BOTH tools (credit_check and calculate_debt_to_income) using the applicant's details.
2. Read the two specialist reports provided in the application.
3. Synthesize ALL FOUR sources into a single recommendation. A fraud HALT or an UNVERIFIABLE
   income are serious adverse findings that can override otherwise acceptable numbers.

Your final response MUST follow this exact format and contain nothing else:

CREDIT CHECK: [result from credit_check] add a line break here
DEBT-TO-INCOME: [result from calculate_debt_to_income] add a line break here
FRAUD FINDING: [one-line summary of the fraud report and its recommendation] add a line break here
EMPLOYMENT FINDING: [one-line summary of the employment report and its recommendation] add a line break here
RISK ASSESSMENT: [2-3 sentences weighing all four sources together] add a line break here
RECOMMENDATION: [APPROVE or REJECT] add a line break here
REASONING: [1-2 sentences in professional underwriting language] add a line break here

Guidance:
- Base the decision on the combined evidence, not any single factor.
- A fraud HALT or a fabricated/synthetic identity should drive a REJECT regardless of credit.
- The RECOMMENDATION line must contain ONLY the word APPROVE or REJECT.
- Output ONLY the seven fields above. No preamble, no stage directions, no extra text.
"""


# ---------------------------------------------------------------------------
# Final decision result
# ---------------------------------------------------------------------------


@dataclass
class SupervisorDecision:
    applicant_name: str
    ai_recommendation: str            # APPROVE | REJECT  (LENNY's synthesis)
    ai_reasoning: str                 # LENNY's full structured assessment
    fraud_recommendation: str         # PROCEED | REVIEW | HALT
    fraud_risk: str                   # LOW | MEDIUM | HIGH
    employment_recommendation: str    # VERIFIED | DISCREPANCY | UNVERIFIABLE
    human_decision: Optional[str] = None   # APPROVED | REJECTED
    human_override: bool = False           # True if the human disagreed with LENNY


# ---------------------------------------------------------------------------
# Supervisor workflow
# ---------------------------------------------------------------------------


@workflow.defn(versioning_behavior=VersioningBehavior.PINNED)  # local dev. For Serverless Workers, add: (versioning_behavior=VersioningBehavior.PINNED)
class LoanUnderwritingSupervisorWorkflow:
    def __init__(self) -> None:
        # LENNY keeps his own activity-backed tools; the specialist evidence is
        # injected into the prompt rather than fetched via tools.
        self.agent = TemporalAgent(
            start_to_close_timeout=timedelta(seconds=90),
            tools=[
                activity_as_tool(
                    credit_check,
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=RetryPolicy(
                        initial_interval=timedelta(seconds=2),
                        maximum_attempts=4,
                    ),
                ),
                activity_as_tool(
                    calculate_debt_to_income,
                    start_to_close_timeout=timedelta(seconds=30),
                ),
            ],
            system_prompt=SUPERVISOR_SYSTEM_PROMPT,
        )
        self._assessment: Optional[str] = None
        self._human_decision: Optional[str] = None
        self._final_decision: Optional[SupervisorDecision] = None

    # --- Signals (human-in-the-loop) ---------------------------------------

    @workflow.signal
    def approve(self) -> None:
        self._human_decision = "APPROVED"

    @workflow.signal
    def reject(self) -> None:
        self._human_decision = "REJECTED"

    # --- Queries (for the starter / UI to poll) ----------------------------

    @workflow.query
    def get_assessment(self) -> Optional[str]:
        """LENNY's synthesized assessment once ready, else None."""
        return self._assessment

    @workflow.query
    def get_final_decision(self) -> Optional[SupervisorDecision]:
        """The final decision once the human has decided, else None."""
        return self._final_decision

    # --- Run ----------------------------------------------------------------

    @workflow.run
    async def run(self, applicant: LoanApplicant) -> SupervisorDecision:
        parent_id = workflow.info().workflow_id

        # 1. Fan the two specialists out as parallel child workflows.
        fraud, employment = await asyncio.gather(
            workflow.execute_child_workflow(
                FraudIdentityAgent.run,
                applicant,
                id=f"{parent_id}-fraud",
            ),
            workflow.execute_child_workflow(
                EmploymentVerificationAgent.run,
                applicant,
                id=f"{parent_id}-employment",
            ),
        )  # type: tuple[FraudAssessment, EmploymentAssessment]

   # Timeline marker: a short, labeled timer renders in purple next to its
        # event in the UI, visually separating the specialist phase from LENNY's.
        await workflow.sleep(
            timedelta(seconds=1),
            summary="Launching LoanUnderwriterAgent LENNY.. ",
        )
 


        # 2. Hand both specialist reports to LENNY and let him pull credit + DTI.
        prompt = (
            f"Make the underwriting decision for this loan application.\n\n"
            f"Applicant ID: {applicant.id}\n"
            f"Name: {applicant.name}\n"
            f"Occupation: {applicant.occupation}\n"
            f"Annual Income: ${applicant.annual_income:,.2f}\n"
            f"Loan Amount Requested: ${applicant.loan_amount:,.2f}\n"
            f"Loan Purpose: {applicant.loan_purpose}\n\n"
            f"--- FRAUD & IDENTITY SPECIALIST REPORT "
            f"(risk={fraud.fraud_risk}, recommendation={fraud.recommendation}) ---\n"
            f"{fraud.raw_assessment}\n\n"
            f"--- EMPLOYMENT & INCOME SPECIALIST REPORT "
            f"(confidence={employment.confidence}, recommendation={employment.recommendation}) ---\n"
            f"{employment.raw_assessment}\n\n"
            f"Now call credit_check and calculate_debt_to_income for applicant ID "
            f"'{applicant.id}' (income {applicant.annual_income}, loan amount "
            f"{applicant.loan_amount}), then produce your decision."
        )

        result = str(await self.agent.invoke_async(prompt))
        self._assessment = result

        ai_recommendation = (_field(result, "RECOMMENDATION") or "REJECT").upper().split()[0]
        if "APPROVE" in ai_recommendation:
            ai_recommendation = "APPROVE"
        else:
            ai_recommendation = "REJECT"  # safe default

        # 3. Wait for the human underwriter's final call.
        await workflow.wait_condition(lambda: self._human_decision is not None)

        expected = "APPROVED" if ai_recommendation == "APPROVE" else "REJECTED"
        human_override = self._human_decision != expected

        self._final_decision = SupervisorDecision(
            applicant_name=applicant.name,
            ai_recommendation=ai_recommendation,
            ai_reasoning=result,
            fraud_recommendation=fraud.recommendation,
            fraud_risk=fraud.fraud_risk,
            employment_recommendation=employment.recommendation,
            human_decision=self._human_decision,
            human_override=human_override,
        )
        return self._final_decision
