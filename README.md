# 🏦 Temporal National Bank — AI Loan Underwriting Demo

A booth demo for AWS Summit showing how [Temporal](https://temporal.io), [AWS Bedrock](https://aws.amazon.com/bedrock/), and the [Strands Agents SDK](https://strandsagents.com/) work together to build durable, human-in-the-loop AI workflows.

**LENNY** (our AI underwriter) assesses loan applications using real tool calls. You make the final call.

---

## What This Demonstrates

| Feature | How it shows up |
|---|---|
| **Durable execution** | The agent workflow survives crashes and resumes exactly where it left off |
| **Activity-backed tools** | Every tool call (credit check, DTI calculation) is a visible Temporal activity with retries |
| **Human-in-the-loop** | Workflow pauses after AI assessment — a human makes the final approve/reject decision via Temporal signal |
| **Strands integration** | `TemporalAgent` replaces manual activity wrapping — clean, idiomatic agent code |
| **AWS Bedrock** | LENNY runs on Amazon Bedrock models via the Strands SDK |

---

## Architecture

```
Browser UI  →  FastAPI  →  Temporal Workflow
                               │
                    ┌──────────┴──────────┐
                    │     TemporalAgent    │  ← Strands SDK + Bedrock
                    │  (LENNY the AI)      │
                    └──────────┬──────────┘
                               │
              ┌────────────────┴────────────────┐
              │                                 │
     credit_check (activity)     calculate_debt_to_income (activity)
              │                                 │
              └────────────────┬────────────────┘
                               │
                    [AI Recommendation]
                               │
                    ⏸ Workflow pauses
                               │
                    Human decides: Approve / Reject
                               │  (Temporal signal)
                    Workflow completes
```

---

## The Applicants

Seven profiles ranging from completely reasonable to deeply questionable:

| Applicant | Ask | Situation |
|---|---|---|
| Nicolas Cage | $2,000,000 | Castle. Germany. Again. |
| Sir Biscuit III | $500,000 | Golden retriever. No SSN. Excellent references. |
| Tyler Blockchain | $1,000,000 | Web3 visionary. Income: vibes. |
| Greg Henderson | $15,000 | Accountant. Perfect credit. Suspiciously normal. |
| Zyx-9 ("Alex") | $250,000 | Time traveler. No credit history ("hasn't happened yet"). |
| Captain Redbeard McGee | $80,000 | Maritime entrepreneur. Collateral: one ship, weathered. |
| Gabriela Santos | $30,000 | Temporal engineer. Has already automated this process. |

---

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) package manager
- [Temporal CLI](https://docs.temporal.io/cli) (`brew install temporal`)
- AWS credentials with Amazon Bedrock access

---

## Setup

**1. Clone and install dependencies**

```bash
git clone <repo-url>
cd loan-demo
uv sync
```

**2. Configure environment**

```bash
cp .env.example .env
```

Edit `.env` with your AWS credentials:

```bash
AWS_REGION=us-west-2
AWS_BEARER_TOKEN_BEDROCK=your-bedrock-token
```

---

## Running the Demo

You need three terminals:

**Terminal 1 — Temporal dev server**
```bash
temporal server start-dev
```

**Terminal 2 — Worker**
```bash
cd loan-demo
uv run worker.py
```

**Terminal 3 — Web server**
```bash
cd loan-demo
uv run app.py
```

Then open **http://localhost:8000** in your browser.

---

## Demo Flow

1. **Pick an applicant** from the profile grid
2. **Review their application** and submit to LENNY
3. **Watch the Temporal UI** at `http://localhost:8233` — see the workflow running, activity calls appearing in real time
4. **Read LENNY's assessment** — credit check result, DTI ratio, professional recommendation
5. **Make the final decision** — Approve or Reject. LENNY's recommendation is advisory. You're in charge.
6. See whether you agreed with the AI — or overruled it

---

## Project Structure

```
loan-demo/
├── workflow.py      # LoanUnderwritingWorkflow — signals, queries, TemporalAgent
├── tools.py         # credit_check + calculate_debt_to_income as Temporal activities
├── worker.py        # StrandsPlugin + worker setup
├── app.py           # FastAPI backend
├── profiles.py      # The 7 applicant profiles
├── prompts.py       # LENNY's system prompt
├── shared.py        # LoanApplicant + LoanDecision dataclasses
├── starter.py       # Optional CLI interface
└── static/
    └── index.html   # Single-page web UI
```

---

## Related

- [Temporal Strands plugin](https://github.com/temporalio/sdk-python/tree/main/temporalio/contrib/strands)
- [Strands Agents SDK](https://strandsagents.com/)
- [Temporal Python SDK](https://github.com/temporalio/sdk-python)
- [samples-python strands_plugin](https://github.com/temporalio/samples-python/pull/310)
