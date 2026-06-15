"""Shared Pydantic models for the loan demo."""

from dataclasses import dataclass
from typing import Optional


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