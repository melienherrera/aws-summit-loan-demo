"""Mocked tool activities for the two specialist underwriting agents.

These back the Fraud/Identity and Employment/Income Verification agents. Each
tool is a Temporal activity wrapped with `activity_as_tool` inside the agent
workflow, so every tool call shows up as a durable, retryable activity in the
event history — exactly like `credit_check` in the base demo.

The bodies are MOCKED: instead of calling a real KYC vendor, payroll API, or
fraud network, they return canned results keyed by the demo applicant IDs (with
a random fallback for custom/bulk applicants). Swap the bodies for real API
calls later — the agent and workflow code won't change.

No AgentCore / code interpreter here: each call is a short, bounded activity,
which keeps the agent loops within AWS Lambda execution limits when the worker
runs as a Temporal Serverless Worker.
"""

import os
import random

from temporalio import activity
from temporalio.exceptions import ApplicationError

# ---------------------------------------------------------------------------
# Mock datasets keyed by the demo applicant IDs (see profiles.py)
# ---------------------------------------------------------------------------

_IDENTITY: dict[str, str] = {
    "greg-normal": "Government ID matches declared name, DOB, and address. Liveness check passed.",
    "temporal-engineer": "Government ID verified. Name, DOB, and address all match the application.",
    "nicolas-cage": "Identity verified. Note: 14 prior addresses on file across 3 countries (all castles).",
    "crypto-bro": "MISMATCH: ID name 'Tyler B. Smith' does not match bank account holder 'Tyler Blockchain'.",
    "sir-biscuit": "NO GOVERNMENT ID ON FILE. Applicant has no SSN and no issued identity documents.",
    "time-traveler": "ANOMALY: ID issue date is 2087. No identity records exist prior to 2025.",
    "captain-redbeard": "Submitted ID is a hand-drawn maritime charter. Not a recognized identity document.",
}

_VELOCITY: dict[str, str] = {
    "greg-normal": "1 loan application in the last 30 days. Normal.",
    "temporal-engineer": "1 loan application in the last 30 days. Normal.",
    "nicolas-cage": "2 loan applications in the last 30 days (both for castles). Slightly elevated.",
    "crypto-bro": "9 loan applications across 9 lenders in the last 30 days. HIGH velocity.",
    "sir-biscuit": "1 loan application in the last 30 days. Normal (good boy).",
    "time-traveler": "Applications detected across 4 non-contiguous time periods. Cannot establish a baseline.",
    "captain-redbeard": "3 applications in the last 30 days, all from different ports. Elevated.",
}

_EMPLOYER: dict[str, str] = {
    "greg-normal": "Employer 'Acme Corp' verified via payroll provider. Status: active, tenure 6 years.",
    "temporal-engineer": "Employer 'Temporal Technologies' verified. Status: active, tenure 3 years.",
    "nicolas-cage": "Self-employed (Actor). No single payroll record; income is project-based and irregular.",
    "crypto-bro": "No active payroll record. Listed employer is 'Founder, 3 dissolved DAOs'. Unverifiable.",
    "sir-biscuit": "No employer or payroll record on file. Occupation listed as 'Emotional Support Professional'.",
    "time-traveler": "Listed employer is not yet incorporated. No payroll record exists.",
    "captain-redbeard": "Self-employed maritime operator. Cash-based; no payroll provider on file.",
}

# applicant_id -> fn(declared_annual_income) -> (observed_annual_income, note)
_INCOME: dict[str, "callable"] = {
    "greg-normal": lambda d: (d * 1.01, "Payroll income matches declared within 1%."),
    "temporal-engineer": lambda d: (d * 0.99, "Payroll income matches declared within 1%."),
    "nicolas-cage": lambda d: (d * 0.72, "Royalty deposits are volatile; trailing 12mo is ~28% below declared."),
    "crypto-bro": lambda d: (0.0, "No payroll or deposit income observed. Declared income is unsupported."),
    "sir-biscuit": lambda d: (0.0, "No income observed, consistent with the declared $0."),
    "time-traveler": lambda d: (0.0, "No verifiable income in the current time period."),
    "captain-redbeard": lambda d: (d * 0.5, "Only ~50% of declared income appears in traceable deposits."),
}


# ---------------------------------------------------------------------------
# Fraud & Identity tools
# ---------------------------------------------------------------------------


@activity.defn
async def verify_identity_documents(applicant_id: str) -> str:
    """Verify the applicant's government identity documents (KYC).

    Confirms the submitted ID matches the declared name, date of birth, and
    address, and runs a liveness / synthetic-identity check.

    Args:
        applicant_id: Unique applicant identifier (e.g. 'greg-normal').

    Returns:
        A human-readable summary of the identity verification result.
    """
    # Optional failure-mode demo: simulate a flaky KYC vendor returning 503s.
    # Temporal retries automatically per this tool's retry_policy.
    # Set DEMO_KYC_RETRY=true (and optionally DEMO_KYC_RETRY_FAILURES=N).
    if os.environ.get("DEMO_KYC_RETRY", "").lower() == "true":
        attempt = activity.info().attempt
        max_failures = int(os.environ.get("DEMO_KYC_RETRY_FAILURES", "2"))
        if attempt <= max_failures:
            activity.logger.warning(
                f"[DEMO] KYC vendor 503 (attempt {attempt}/{max_failures}). Temporal will retry..."
            )
            raise ApplicationError(
                f"KYC vendor unavailable: 503 Service Unavailable (attempt {attempt})",
                type="KYCVendorError",
                non_retryable=False,
            )

    return _IDENTITY.get(
        applicant_id,
        random.choice(
            [
                "Government ID matches declared details. Liveness check passed.",
                "Minor discrepancy: address on ID is one move behind the application. Low concern.",
            ]
        ),
    )


@activity.defn
async def check_application_velocity(applicant_id: str) -> str:
    """Check how many recent loan applications this applicant has filed.

    High velocity across many lenders in a short window is a common
    first-party / synthetic fraud signal.

    Args:
        applicant_id: Unique applicant identifier.

    Returns:
        A human-readable summary of recent application velocity.
    """
    return _VELOCITY.get(
        applicant_id,
        f"{random.randint(1, 2)} loan application(s) in the last 30 days. Normal.",
    )


# ---------------------------------------------------------------------------
# Employment & Income tools
# ---------------------------------------------------------------------------


@activity.defn
async def verify_employer(applicant_id: str) -> str:
    """Verify the applicant's employer and employment status via payroll data.

    Args:
        applicant_id: Unique applicant identifier.

    Returns:
        A human-readable summary of employer verification.
    """
    return _EMPLOYER.get(
        applicant_id,
        "Employer verified via payroll provider. Status: active.",
    )


@activity.defn
async def cross_check_income(applicant_id: str, declared_annual_income: float) -> str:
    """Cross-check declared income against observed payroll / deposit income.

    Args:
        applicant_id: Unique applicant identifier.
        declared_annual_income: The annual income the applicant declared, in USD.

    Returns:
        A human-readable summary comparing declared vs. observed income,
        including the percentage variance.
    """
    fn = _INCOME.get(applicant_id)
    if fn is None:
        observed = declared_annual_income * random.uniform(0.9, 1.1)
        note = "Observed income is broadly consistent with declared."
    else:
        observed, note = fn(declared_annual_income)

    if declared_annual_income > 0:
        variance = (observed - declared_annual_income) / declared_annual_income * 100
        variance_str = f"{variance:+.0f}%"
    else:
        variance_str = "N/A (declared $0)"

    return (
        f"Declared: ${declared_annual_income:,.0f}/yr | "
        f"Observed: ${observed:,.0f}/yr | Variance: {variance_str}. {note}"
    )
