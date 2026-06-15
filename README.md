# 🏦 Temporal National Bank — AI Loan Underwriting Demo

A booth demo for AWS Summit showing how [Temporal](https://temporal.io), [AWS Bedrock](https://aws.amazon.com/bedrock/), and the [Strands Agents SDK](https://strandsagents.com/) work together to build durable, human-in-the-loop AI workflows — deployable as a Temporal Serverless Worker on AWS Lambda.

**LENNY** (our AI underwriter) now runs as a **supervisor over a panel of specialist sub-agents**: a Fraud & Identity agent and an Employment & Income agent each run as their own durable child workflow, LENNY synthesizes their findings together with a credit check and a debt-to-income calculation, and **you make the final call**.

---

## What This Demonstrates

| Feature | How it shows up |
|---|---|
| **Durable execution** | The agent workflow survives crashes and resumes exactly where it left off |
| **Activity-backed tools** | Every tool call (credit check, DTI calculation) is a visible Temporal activity with retries |
| **Human-in-the-loop** | Workflow pauses after AI assessment — a human makes the final approve/reject decision via Temporal signal |
| **Strands integration** | `TemporalAgent` replaces manual activity wrapping — clean, idiomatic agent code |
| **AWS Bedrock** | LENNY runs on Amazon Bedrock models via the Strands SDK |
| **Serverless Workers** | Worker runs on AWS Lambda — invoked on demand by Temporal Cloud, no long-lived process required |

---

## Architecture

### Multi-Agent Orchestration

```
Browser UI  →  FastAPI  →  Temporal
                               │
                               ▼
            LoanUnderwritingSupervisorWorkflow   (LENNY)
                               │
        ┌──────────────────────┴──────────────────────┐   ← parallel child workflows
        ▼                                             ▼
 FraudIdentityWorkflow                  EmploymentVerificationWorkflow
 (TemporalAgent)                        (TemporalAgent)
   • verify_identity_documents            • verify_employer
   • check_application_velocity           • cross_check_income
        │                                             │
        └──────────────────────┬──────────────────────┘
                               ▼
                ⏱  "LoanUnderwriterAgent" timer marker
                               ▼
            LENNY (TemporalAgent) aggregates everything:
              • fraud report + employment report (from the children)
              • credit_check               (activity)
              • calculate_debt_to_income   (activity)
                               ▼
                  [AI Recommendation: APPROVE / REJECT]
                               ▼
                       ⏸ Workflow pauses
                               ▼
            Human decides: Approve / Reject   (Temporal signal)
                               ▼
                       SupervisorDecision
```

Each specialist runs as its own child workflow, so it shows up independently in the
Temporal UI, retries on its own, and could later be routed to its own task queue /
worker pool. LENNY keeps `credit_check` and `calculate_debt_to_income` as his own
activity-backed tools; the two specialist reports arrive as durable child-workflow
results and are folded into his prompt.

### Production (Serverless Workers on Temporal Cloud)
```
Browser UI  →  FastAPI  →  Temporal Cloud (AWS-hosted Namespace)
                               │
                    Temporal invokes Lambda per task
                               │
                    ┌──────────▼──────────┐
                    │   AWS Lambda        │  ← lambda_function.py
                    │   (loan-underwriting│    run_worker() handler
                    │    -worker)         │    + StrandsPlugin
                    └──────────┬──────────┘
                               │
                    ┌──────────┴──────────┐
                    │     TemporalAgent   │  ← Strands SDK
                    │  (LENNY the AI)     │
                    └──────────┬──────────┘
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

You can also submit your own application directly from the web UI.

---

## Prerequisites

### Local Development
- Python 3.10+
- [uv](https://docs.astral.sh/uv/) package manager
- [Temporal CLI](https://docs.temporal.io/cli) (`brew install temporal`)
- AWS credentials with Amazon Bedrock access (`AWS_BEARER_TOKEN_BEDROCK` or IAM keys)

### Serverless Workers (Production)
- Python 3.13
- [Temporal Cloud](https://temporal.io/cloud) account with an **AWS-hosted Namespace**
  > ⚠️ Serverless Workers are in pre-release. Request access via your Temporal account team.
- AWS account with permissions to create Lambda functions and IAM roles
- AWS CLI authenticated (`aws sso login --profile <your-profile>`)
- Amazon Bedrock model access enabled in `us-west-2`

---

## Setup

**1. Clone and install dependencies**

```bash
git clone https://github.com/temporal-community/aws-summit-loan-demo.git
cd aws-summit-loan-demo
uv sync
```

**2. Configure environment**

```bash
cp .env.example .env
```

Edit `.env` — for local development you only need:

```bash
AWS_REGION=us-west-2
AWS_BEARER_TOKEN_BEDROCK=your-bedrock-bearer-token
```

---

## Running Locally

You need three terminals:

**Terminal 1 — Temporal dev server**
```bash
temporal server start-dev
```

**Terminal 2 — Worker**
```bash
uv run worker.py
```

**Terminal 3 — Web server**
```bash
uv run app.py
```

Then open **http://localhost:8000** in your browser and the Temporal UI at **http://localhost:8233**.

---

## Failure Mode Demos

Two demos are built into the worker, toggled via `.env`. Run them independently on separate applications.

**Demo 1 — Flaky API retry** (`credit_check` activity)

Simulates the credit bureau returning `429 Too Many Requests`. Temporal retries automatically — no intervention needed. Watch the activity go red → red → red → green in the Temporal UI.

```bash
DEMO_API_RETRY=true
DEMO_API_RETRY_FAILURES=3   # failures before success (default: 3)
```

**Demo 2 — Worker crash** (`calculate_debt_to_income` activity)

Pauses the activity for N seconds, giving you a window to kill the worker (`Ctrl+C`). Restart the worker and Temporal resumes exactly where it left off — no data lost, no re-running completed steps.

```bash
DEMO_CRASH_DELAY=15   # seconds to pause (kill the worker during this window)
```

> Make sure only one demo mode is active at a time. Both default to off (`DEMO_API_RETRY` unset, `DEMO_CRASH_DELAY=0`).

---

## Deploying as a Serverless Worker

The worker can be deployed as an AWS Lambda function invoked on demand by Temporal Cloud — no long-lived polling process required.

> See the full step-by-step deployment guide for details on building the Lambda package, creating IAM roles, deploying via S3, and registering the Worker Deployment Version.

**High-level steps:**

1. Build a Linux x86_64 dependency package (`pip install --platform manylinux2014_x86_64 ...`)
2. Trim unused libraries to stay under Lambda's 250 MB limit
3. Zip dependencies + source files
4. Create a Lambda execution IAM role with Bedrock access
5. Deploy the function via S3 (zip exceeds 70 MB direct upload limit)
6. Deploy a CloudFormation stack so Temporal Cloud can invoke the Lambda
7. Register the Worker Deployment Version with the Temporal CLI
8. Set the version as current

The Lambda handler is `lambda_function.lambda_handler`. It uses `run_worker()` from `temporalio.contrib.aws.lambda_worker` and attaches the same `StrandsPlugin` as the local worker.

**Key environment variables for Lambda:**
```
TEMPORAL_ADDRESS=<namespace>.<account>.tmprl.cloud:7233
TEMPORAL_NAMESPACE=<namespace>
TEMPORAL_API_KEY=<your-api-key>
AWS_REGION=us-west-2
```

> Bedrock credentials are provided automatically via the Lambda execution IAM role — no `AWS_BEARER_TOKEN_BEDROCK` needed in production.

---

## Demo Flow

1. **Fill in a loan application** or pick one of the pre-built profiles
2. **Submit to LENNY** — a durable Temporal workflow starts
3. **Watch the Temporal UI** — see the workflow running, activity calls appearing in real time
4. **Read LENNY's assessment** — credit check result, DTI ratio, professional recommendation
5. **Make the final decision** — Approve or Reject. LENNY's recommendation is advisory. You're in charge.
6. See whether you agreed with the AI — or overruled it

---

## Project Structure

```
aws-summit-loan-demo/
├── workflow.py          # LoanUnderwritingWorkflow — signals, queries, TemporalAgent
├── tools.py             # credit_check + calculate_debt_to_income as Temporal activities
├── worker.py            # Local worker — StrandsPlugin + long-lived polling
├── lambda_function.py   # Serverless Worker — Lambda handler via run_worker()
├── app.py               # FastAPI backend (unchanged for both worker modes)
├── profiles.py          # The 7 applicant profiles
├── prompts.py           # LENNY's system prompt
├── shared.py            # LoanApplicant + LoanDecision dataclasses
├── starter.py           # Optional CLI interface (supports Temporal Cloud)
└── static/
    └── index.html       # Single-page web UI
```

---

## Related

- [Temporal Serverless Workers docs](https://docs.temporal.io/cloud/serverless-workers)
- [Temporal Strands plugin](https://github.com/temporalio/sdk-python/tree/main/temporalio/contrib/strands)
- [Strands Agents SDK](https://strandsagents.com/)
- [Temporal Python SDK](https://github.com/temporalio/sdk-python)
- [samples-python strands_plugin](https://github.com/temporalio/samples-python/pull/310)
