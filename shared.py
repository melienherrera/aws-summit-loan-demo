"""Shared models and helpers for the loan demo."""

import os
from dataclasses import dataclass
from typing import Optional


def temporal_connect_args() -> tuple[str, dict]:
    """Return (address, kwargs) for Client.connect() based on TEMPORAL_ENV."""
    env = os.environ.get("TEMPORAL_ENV", "local")
    if env == "cloud":
        address = os.environ["TEMPORAL_CLOUD_ADDRESS"]
        return address, {
            "namespace": os.environ["TEMPORAL_CLOUD_NAMESPACE"],
            "api_key": os.environ["TEMPORAL_CLOUD_API_KEY"],
            "tls": True,
        }
    return os.environ.get("TEMPORAL_LOCAL_ADDRESS", "localhost:7233"), {
        "namespace": os.environ.get("TEMPORAL_LOCAL_NAMESPACE", "default"),
    }


@dataclass
class LoanApplicant:
    id: str
    name: str
    occupation: str
    loan_amount: float
    loan_purpose: str
    annual_income: float
    credit_score: int
    fun_fact: str


@dataclass
class LoanDecision:
    applicant_name: str
    ai_recommendation: str  # "APPROVE" or "REJECT"
    ai_reasoning: str
    human_decision: Optional[str] = None  # "APPROVED" or "REJECTED"
    human_override: bool = False  # True if human disagreed with AI