"""LoanUnderwritingWorkflow — Temporal + Strands + HITL.

Flow:
  1. TemporalAgent assesses the application using credit_check and
     calculate_debt_to_income tools.
  2. Workflow pauses and exposes the AI assessment via a query so the
     starter can display it to the booth visitor.
  3. Visitor sends an approve() or reject() signal.
  4. Workflow completes with the final LoanDecision.
"""

from datetime import timedelta
from typing import Optional

from temporalio import workflow
from temporalio.contrib.strands import TemporalAgent
from temporalio.contrib.strands.workflow import activity_as_tool
from temporalio.common import VersioningBehavior

with workflow.unsafe.imports_passed_through():
    from prompts import UNDERWRITING_SYSTEM_PROMPT
    from shared import LoanApplicant, LoanDecision
    from tools import calculate_debt_to_income, credit_check


#@workflow.defn # uncomment this when worker is running locally and comment out the line below
@workflow.defn(versioning_behavior=VersioningBehavior.PINNED)
class LoanUnderwritingWorkflow:
    def __init__(self) -> None:
        self.agent = TemporalAgent(
            start_to_close_timeout=timedelta(seconds=60),
            tools=[
                activity_as_tool(credit_check, start_to_close_timeout=timedelta(seconds=30)),
                activity_as_tool(calculate_debt_to_income, start_to_close_timeout=timedelta(seconds=30)),
            ],
            system_prompt=UNDERWRITING_SYSTEM_PROMPT,
        )
        self._assessment: Optional[str] = None
        self._human_decision: Optional[str] = None
        self._final_decision: Optional[LoanDecision] = None

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    @workflow.signal
    def approve(self) -> None:
        self._human_decision = "APPROVED"

    @workflow.signal
    def reject(self) -> None:
        self._human_decision = "REJECTED"

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @workflow.query
    def get_assessment(self) -> Optional[str]:
        """Returns the AI assessment once complete, or None if still running."""
        return self._assessment

    @workflow.query
    def get_final_decision(self) -> Optional[LoanDecision]:
        """Returns the final LoanDecision once the human has decided, or None if still waiting."""
        return self._final_decision

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    @workflow.run
    async def run(self, applicant: LoanApplicant) -> LoanDecision:
        prompt = (
            f"Please assess the following loan application:\n\n"
            f"Applicant Name: {applicant.name}\n"
            f"Applicant ID: {applicant.id}\n"
            f"Occupation: {applicant.occupation}\n"
            f"Annual Income: ${applicant.annual_income:,.2f}\n"
            f"Loan Amount Requested: ${applicant.loan_amount:,.2f}\n"
            f"Loan Purpose: {applicant.loan_purpose}\n"
            f"Additional Context: {applicant.fun_fact}\n"
        )

        result = await self.agent.invoke_async(prompt)
        self._assessment = str(result)

        # Parse AI recommendation out of the structured response
        ai_recommendation = "REJECT"  # safe default
        for line in self._assessment.splitlines():
            if line.strip().startswith("RECOMMENDATION:"):
                value = line.split(":", 1)[-1].strip().upper()
                if "APPROVE" in value:
                    ai_recommendation = "APPROVE"
                break

        # Wait for the human underwriter (booth visitor) to decide
        await workflow.wait_condition(lambda: self._human_decision is not None)

        human_override = self._human_decision != (
            "APPROVED" if ai_recommendation == "APPROVE" else "REJECTED"
        )

        self._final_decision = LoanDecision(
            applicant_name=applicant.name,
            ai_recommendation=ai_recommendation,
            ai_reasoning=self._assessment,
            human_decision=self._human_decision,
            human_override=human_override,
        )

        return self._final_decision
