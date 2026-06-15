"""Loan underwriting tools as Temporal activities wrapped with activity_as_tool.

Running tools as activities (rather than inline @tool) avoids the Temporal
workflow sandbox, which restricts stdlib internals that Strands uses internally.
Each tool call becomes a visible Temporal activity in the event history.

Failure Mode Demos
──────────────────
Demo 1 — Flaky API retry (credit_check):
  Set DEMO_API_RETRY=true to simulate the credit bureau returning 429s.
  Temporal retries automatically. Set DEMO_API_RETRY_FAILURES=N to control
  how many times it fails before succeeding (default: 4).

Demo 2 — Worker crash (calculate_debt_to_income):
  Set DEMO_CRASH_DELAY=15 to pause this activity for N seconds.
  Kill the worker during that window — Temporal resumes automatically
  when the worker restarts, picking up exactly where it left off.
"""

import asyncio
import os
import random

from temporalio import activity

# Mocked credit scores keyed by applicant ID.
_CREDIT_SCORES: dict[str, int] = {
    "nicolas-cage": 490,
    "sir-biscuit": 0,
    "crypto-bro": 512,
    "greg-normal": 781,
    "time-traveler": 0,
    "captain-redbeard": 388,
    "temporal-engineer": 810,
}

_SCORE_RATINGS = [
    (800, "Exceptional"),
    (740, "Very Good"),
    (670, "Good"),
    (580, "Fair"),
    (300, "Poor"),
    (0, "No Credit History"),
]


def _rating(score: int) -> str:
    for threshold, label in _SCORE_RATINGS:
        if score >= threshold:
            return label
    return "No Credit History"


@activity.defn
async def credit_check(applicant_id: str) -> str:
    """Look up the credit score and rating for a loan applicant.

    Args:
        applicant_id: The unique identifier for the applicant (e.g. 'greg-normal').

    Returns:
        A string summarising the credit score and rating.
    """
    # ── Demo 1: Flaky Credit Bureau API ───────────────────────────
    # Simulates the credit bureau returning 429 Too Many Requests.
    # Temporal retries automatically — no intervention needed.
    # Set DEMO_API_RETRY=true and optionally DEMO_API_RETRY_FAILURES=N
    if os.environ.get("DEMO_API_RETRY", "").lower() == "true":
        attempt = activity.info().attempt
        max_failures = int(os.environ.get("DEMO_API_RETRY_FAILURES", "2"))
        if attempt <= max_failures:
            activity.logger.warning(
                f"[DEMO 1] Attempt {attempt}/{max_failures} — credit bureau returned 429 Too Many Requests. Temporal will retry..."
            )
            raise Exception(
                f"Credit bureau API error: 429 Too Many Requests (attempt {attempt}/{max_failures})"
            )
        activity.logger.info(
            f"[DEMO 1] Attempt {attempt} — credit bureau responded successfully."
        )
    # ──────────────────────────────────────────────────────────────

    score = _CREDIT_SCORES.get(applicant_id)
    if score is None:
        # Custom applicant — generate a random score
        score = random.randint(400, 800)
    rating = _rating(score)
    if score == 0:
        return f"Credit score: N/A | Rating: {rating} (no credit history on file)"
    return f"Credit score: {score} | Rating: {rating}"


@activity.defn
async def calculate_debt_to_income(annual_income: float, loan_amount: float) -> str:
    """Calculate the debt-to-income ratio for a loan application.

    Args:
        annual_income: The applicant's annual income in USD.
        loan_amount: The total loan amount requested in USD.

    Returns:
        A string with the DTI ratio and risk assessment.
    """
    # ── Demo 2: Worker Crash ───────────────────────────────────────
    # Pauses this activity so you have a window to kill the worker.
    # Temporal resumes automatically when the worker restarts.
    # Set DEMO_CRASH_DELAY=15 (seconds) in .env to enable.
    delay = int(os.environ.get("DEMO_CRASH_DELAY", "0"))
    if delay > 0:
        activity.logger.info(
            f"[DEMO 2] calculate_debt_to_income sleeping {delay}s — kill the worker now!"
        )
        for _ in range(delay):
            activity.heartbeat()
            await asyncio.sleep(1)
        activity.logger.info("[DEMO 2] Worker restarted — resuming exactly where we left off.")
    # ──────────────────────────────────────────────────────────────

    if annual_income <= 0:
        return "DTI: N/A — applicant reports zero or no income. High risk."

    ratio = loan_amount / annual_income
    percentage = f"{ratio * 100:.1f}%"

    if ratio < 0.3:
        assessment = "Low risk. Loan amount is well within acceptable income range."
    elif ratio < 1.0:
        assessment = "Moderate risk. Loan amount is significant relative to annual income."
    elif ratio < 3.0:
        assessment = "High risk. Loan amount substantially exceeds annual income."
    else:
        assessment = "Very high risk. Loan amount is extreme relative to reported income."

    return f"DTI ratio: {ratio:.2f} ({percentage}) — {assessment}"
