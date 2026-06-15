"""Hardcoded loan applicant profiles for the booth demo.

A mix of absurd, funny, and one suspiciously normal applicant.
"""

import random
from typing import Optional

from shared import LoanApplicant

PROFILES: list[LoanApplicant] = [
    LoanApplicant(
        id="nicolas-cage",
        name="Nicolas Cage",
        occupation="Actor / Castle Enthusiast",
        loan_amount=2_000_000.00,
        loan_purpose="To purchase a castle in Germany. Again.",
        annual_income=85_000.00,
        credit_score=490,
        fun_fact="Has previously purchased and then been forced to sell castles in Germany, England, and Rhode Island due to tax obligations. Undeterred.",
    ),
    LoanApplicant(
        id="sir-biscuit",
        name="Sir Biscuit III",
        occupation="Emotional Support Professional",
        loan_amount=500_000.00,
        loan_purpose="Primary residence with large yard. Tennis ball storage facility.",
        annual_income=0.00,
        credit_score=0,
        fun_fact="Sir Biscuit is a golden retriever. He has no SSN, no employment history, and no concept of money. He does have excellent references from 47 humans whose days he has improved.",
    ),
    LoanApplicant(
        id="crypto-bro",
        name="Tyler Blockchain",
        occupation="Web3 Visionary / Founder of 3 failed DAOs",
        loan_amount=1_000_000.00,
        loan_purpose="Seed funding for a blockchain-based blockchain for blockchains.",
        annual_income=12_000.00,
        credit_score=512,
        fun_fact="Tyler's listed income is $12,000 but he insists his 'net worth is technically infinite if you count unrealized gains on coins he invented himself.'",
    ),
    LoanApplicant(
        id="greg-normal",
        name="Greg Henderson",
        occupation="Senior Accountant",
        loan_amount=15_000.00,
        loan_purpose="Kitchen renovation.",
        annual_income=92_000.00,
        credit_score=781,
        fun_fact="Greg is completely normal. He pays his taxes on time, has had the same car for 9 years, and describes his hobbies as 'light hiking and meal prep.' He is the control group.",
    ),
    LoanApplicant(
        id="time-traveler",
        name="Zyx-9 (goes by 'Alex')",
        occupation="Temporal Navigator, 22nd Century Division",
        loan_amount=250_000.00,
        loan_purpose="Secure housing while stranded in 2025 awaiting return portal activation.",
        annual_income=0.00,
        credit_score=0,
        fun_fact="Alex has no credit history because, as they explain, 'currency was abolished in 2089.' They have offered a sports almanac as collateral but refused to specify which years it covers.",
    ),
    LoanApplicant(
        id="captain-redbeard",
        name="Captain Redbeard McGee",
        occupation="Maritime Entrepreneur / Treasure Procurement Specialist",
        loan_amount=80_000.00,
        loan_purpose="Ship repairs and crew payroll. The cannon damage was an accident.",
        annual_income=47_000.00,
        credit_score=388,
        fun_fact="Captain Redbeard's credit score tanked in 2019 after a dispute with a Harbor Authority that he describes as 'a misunderstanding about the definition of international waters.' He has offered 'a portion of future treasure' as collateral.",
    ),
    LoanApplicant(
        id="temporal-engineer",
        name="Gabriela Santos",
        occupation="Senior Software Engineer, Distributed Systems",
        loan_amount=30_000.00,
        loan_purpose="Home office upgrade and standing desk. The irony of applying for a loan through a Temporal workflow is not lost on her.",
        annual_income=175_000.00,
        credit_score=810,
        fun_fact="Gabriela has been making distributed systems reliable since 2021. She once gave a conference talk titled 'Your Queue Is Not a Database' that made three people cry (in a good way).",
    ),
]

_by_id = {p.id: p for p in PROFILES}


def get_profile(profile_id: str) -> Optional[LoanApplicant]:
    return _by_id.get(profile_id)


def get_random_profile() -> LoanApplicant:
    return random.choice(PROFILES)


def list_profiles() -> None:
    print("\n📋  Available Loan Applicants\n")
    print(f"  {'#':<4} {'ID':<22} {'Name':<28} {'Loan Ask'}")
    print(f"  {'-'*4} {'-'*22} {'-'*28} {'-'*12}")
    for i, p in enumerate(PROFILES, 1):
        print(f"  {i:<4} {p.id:<22} {p.name:<28} ${p.loan_amount:,.0f}")
    print()