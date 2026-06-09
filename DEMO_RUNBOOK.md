# 🏦 AWS Summit Booth Demo Runbook
## Temporal National Bank — AI Loan Underwriting

---

## The Pitch (30 seconds)

> *"This is a loan underwriting system powered by Temporal, AWS Bedrock, and the Strands Agents SDK.
> An AI called LENNY reviews every application — but a human always makes the final call.
> Watch what happens when things go wrong."*

---

## Pre-Show Setup Checklist

Run through this before the booth opens. Everything should be green before the first visitor.

### Terminals (need 3)

**Terminal 1 — Temporal dev server**
```bash
temporal server start-dev
```
✅ Confirm: `http://localhost:8233` loads in browser

**Terminal 2 — Worker**
```bash
cd ~/Documents/Cursor/loan-demo
export AWS_BEARER_TOKEN_BEDROCK=<your-token>
uv run worker.py
```
✅ Confirm: `🏦 Loan Underwriting Worker started` appears

**Terminal 3 — Web server**
```bash
cd ~/Documents/Cursor/loan-demo
uv run app.py
```
✅ Confirm: `http://localhost:8000` loads the landing page in browser

### Browser Setup
- **Tab 1**: `http://localhost:8000` — the demo UI (full screen, this is what visitors see)
- **Tab 2**: `http://localhost:8233` — Temporal UI (keep handy, pull up during demos)

### Sanity Check
Run one application end-to-end with **Greg Henderson** (the normal one) before the booth opens. Make sure the full flow works: submit → LENNY assesses → approve → result screen.

---

## Demo Flow (Standard — ~3 minutes)

### Step 1: Hook (30 sec)
Point at the landing page.

> *"This is a loan application form. Fill it in — or scroll down and pick one of our pre-loaded applicants. Some of them are... interesting."*

Let the visitor scroll down and discover the profiles. They'll react to Nicolas Cage or Sir Biscuit. That's the hook.

### Step 2: Submit (30 sec)
Let them pick a profile (or fill in the custom form with their own info). Hit **Submit to LENNY**.

> *"This just started a durable Temporal workflow. Let's watch it run."*

Pull up **Tab 2** (Temporal UI). Show the workflow appearing. Point at the activities running.

> *"Every tool call LENNY makes — the credit check, the debt-to-income analysis — those are Temporal activities. Each one has automatic retries, timeouts, and full observability."*

### Step 3: LENNY's verdict (30 sec)
When the assessment appears, read out the highlight.

> *"LENNY has made a recommendation. But LENNY is advisory — you're the underwriter. What do you think?"*

Hand them the decision. Let them approve or reject. Make it dramatic.

### Step 4: Result (30 sec)
Show the result screen. Point out whether they agreed or overruled LENNY.

> *"The workflow is complete. Every step is in the event history. This is fully auditable — you can replay exactly what happened and why."*

---

## Failure Mode Demos

Run these on **separate applications** from the standard flow. Set the env var, restart the worker, then demo.

---

### Demo 1: Flaky API Retry (~2 minutes)

**What it shows:** The credit bureau API fails multiple times. Temporal retries automatically. No human intervention needed.

**Setup:**
```bash
# In your .env
DEMO_API_RETRY=true
# Restart the worker
```

**Script:**
1. Submit any application (Captain Redbeard is great for this)
2. Pull up Temporal UI
3. Watch `credit_check` go red in the event history

> *"The credit bureau just returned a 429 — Too Many Requests. In a normal system, this would either crash or require someone to manually re-run it. Watch what Temporal does..."*

4. Watch it retry automatically — red, red, red, then green

> *"Temporal retried it automatically. Three failures, then success. Zero code changes. Zero human intervention. This is what durable execution means."*

**Talking point:** *"In production, this could be a real rate limit, a flaky third-party API, a network blip. Temporal just handles it."*

---

### Demo 2: Worker Crash (~3 minutes)

**What it shows:** Kill the worker mid-activity. Restart it. The workflow resumes exactly where it left off.

**Setup:**
```bash
# In your .env
DEMO_CRASH_DELAY=15
# Restart the worker
```

**Script:**
1. Submit any application
2. Watch the loading screen — when the worker logs `[DEMO 2] calculate_debt_to_income sleeping 15s` you have a 15-second window
3. Pull up Temporal UI — show the `calculate_debt_to_income` activity running
4. **Kill the worker** (`Ctrl+C` in Terminal 2)

> *"I just killed the server. Right now. Mid-activity."*

5. Point at Temporal UI — workflow is still there, activity is scheduled, nothing lost

> *"The workflow is still running. It's just waiting. No data lost. No corruption. The state is in Temporal."*

6. Restart the worker: `uv run worker.py`

> *"Watch — it picks up exactly where it left off."*

7. Activity completes, assessment appears

> *"It didn't start over. It didn't re-run the credit check. It resumed from the exact checkpoint where we crashed. That's durable execution."*

**Talking point:** *"At a booth, this is a party trick. In production, this is what keeps your AI agent from losing work during a deploy, a crash, or a cloud outage."*

---

## Profile Guide

| Profile | Best for | LENNY usually says |
|---|---|---|
| **Greg Henderson** | Sanity check, first run | APPROVE |
| **Nicolas Cage** | Laughs, high DTI demo | REJECT |
| **Sir Biscuit III** | Biggest laughs, zero income | REJECT |
| **Tyler Blockchain** | Tech crowd, vibes income | REJECT |
| **Captain Redbeard** | Flaky API demo (poor credit) | REJECT |
| **Gabriela Santos** | Temporal crowd, self-referential | APPROVE |
| **Zyx-9 ("Alex")** | Thin file / no credit history | REJECT |
| **Custom form** | Personal engagement | Depends |

**Tip:** Start with Greg (boring → shows the baseline), then do Sir Biscuit or Nicolas Cage (laughs → shows the AI takes everything seriously), then do a failure mode demo.

---

## Talking Points by Audience

### For builders / engineers
- *"Model calls, tool calls, and MCP calls all execute as Temporal activities — automatic retries, timeouts, full event history."*
- *"The Strands integration means you write normal agent code. Temporal handles durability transparently."*
- *"Kill the worker mid-agent-run. It resumes. That's the whole pitch."*

### For architects / decision-makers
- *"AI agents fail silently. A network blip, a rate limit, a bad response — and you've lost work. Temporal makes agents reliable by default."*
- *"The human-in-the-loop pause is durable too. The workflow can sit in that state for days without consuming resources. Resume it whenever."*
- *"This runs on Temporal Cloud with Serverless Workers — Lambda invoked on demand by Temporal. No servers to manage."*

### For AWS / Bedrock audience
- *"LENNY runs on Amazon Bedrock via the Strands Agents SDK — AWS's own agent framework."*
- *"The Lambda worker is invoked by Temporal Cloud on demand. No persistent compute."*
- *"Bedrock handles the AI. Temporal handles the reliability. Strands connects them."*

---

## Common Questions

**Q: Is LENNY making real AI decisions?**
> Yes — it's calling AWS Bedrock (Claude) and running real tool calls. The credit scores and DTI calculation are mocked data, but the reasoning is real.

**Q: What happens if someone approves Sir Biscuit?**
> The workflow completes normally. LENNY's recommendation was REJECT, so it'll show as a human override. *"The human remains in control. As it should be."*

**Q: Can this run in production?**
> Yes — the Serverless Workers version runs on AWS Lambda invoked by Temporal Cloud. No long-lived server required.

**Q: How long can the workflow sit waiting for human approval?**
> Indefinitely. The workflow pauses with zero resource consumption until a signal arrives. Days, weeks, doesn't matter.

**Q: What's Strands?**
> AWS's open-source agent SDK — similar to OpenAI Agents SDK but AWS-native with first-class Bedrock support. The Temporal integration wraps the agent's model calls and tool calls as durable activities.

---

## Emergency Procedures

**Worker won't start:**
```bash
# Check AWS token is set
echo $AWS_BEARER_TOKEN_BEDROCK
# Refresh if empty
export AWS_BEARER_TOKEN_BEDROCK=<token>
```

**Demo stuck on loading screen:**
- Check worker terminal for errors
- Check Temporal UI — is the workflow running or failed?
- If failed: start a fresh application, don't reuse a broken workflow

**Temporal UI not showing workflow:**
- Make sure `temporal server start-dev` is running
- Hard refresh the browser (`Cmd+Shift+R`)

**LENNY returns garbled output:**
- Restart the worker
- AWS Bearer token may have expired — refresh it

**Forgot to turn off demo mode:**
```bash
# Remove from .env
DEMO_API_RETRY=   # leave blank or delete
DEMO_CRASH_DELAY=0
# Restart worker
```

---

## Reset Between Visitors

The demo resets automatically — clicking **"Review another applicant"** returns to the landing page. Each application is a separate workflow with a unique ID.

No need to restart anything between visitors. Just click reset and hand it over.
