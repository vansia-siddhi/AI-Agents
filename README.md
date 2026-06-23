# Inbox Triage Agent (Free, No Paid API)

A decision-making AI agent project — a step up from the Research Agent.
Instead of just reading and summarizing, this agent makes **decisions with
consequences** for each message: classify → decide → act → log.

## What makes this different from the Research Agent

| Research Agent | Triage Agent (this project) |
|---|---|
| Read → summarize | Read → **decide what to do** |
| One kind of output (a report) | Multiple possible actions (reply, escalate, archive...) |
| Pure LLM reasoning | LLM reasoning **+ plain Python if/else rules** |
| No real consequence | Each decision routes the message somewhere different |

This pattern — LLM for judgment calls, code for hard rules — is how most
real production agents are actually built (customer support bots, ticket
routers, CRM automations).

## The loop

```
📧 Message in
   ↓
🧠 THINK (LLM)    → classify: complaint / question / urgent_business / spam / compliment
                  → rate urgency 1-5
   ↓
⚡ DECIDE (code)  → simple if/else picks an action based on classification + urgency
   ↓
📝 ACT            → draft a reply (LLM) OR write a routing note (no LLM needed)
   ↓
📋 LOG            → save decision + reasoning to an audit trail
```

## Setup

1. Get a free Groq key at https://console.groq.com (same one from the Research Agent project — reuse it)
2. Install deps: `pip install -r requirements.txt`
3. Set the key:
   - Windows PowerShell: `$env:GROQ_API_KEY="gsk_..."`
   - Mac/Linux: `export GROQ_API_KEY="gsk_..."`

## Run it

**Terminal version** (5 sample messages, prints to console):
```
python agent.py
```
Saves results to `triage_log.json`.

**Web version** (live streaming UI):
```
python app.py
```
Then open http://localhost:5000 — you can either run the 5 sample messages,
or switch to the "Try Your Own Message" tab and triage anything you type.

## Files

```
triage_agent/
├── agent.py            # terminal version, standalone
├── app.py              # Flask backend with SSE streaming
├── requirements.txt
└── static/
    ├── index.html
    ├── style.css
    └── script.js
```

## Exercises to extend this

1. **Add a 6th category**: e.g. "billing_question" with its own action.
2. **Connect to real email**: swap `SAMPLE_INBOX` for the Gmail API (read-only)
   so it triages your actual inbox (start with a test/throwaway account!).
3. **Add a confidence threshold**: if the LLM isn't confident in its
   classification, force `escalate_normal` regardless of category — a basic
   but important safety pattern for production agents.
4. **Persist the audit log**: instead of overwriting `triage_log.json` each run,
   append to it, so you build a history of every decision ever made.
5. **Combine with the Research Agent**: when a message is classified as
   `urgent_business`, trigger the Research Agent to look up context about
   the sender's company before escalating — this is your first taste of
   multi-agent systems.
