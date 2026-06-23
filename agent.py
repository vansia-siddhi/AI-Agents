"""
Inbox Triage Agent
===================
A decision-making AI agent that processes a batch of unsorted messages
(simulating emails / support tickets) and for each one:

  1. THINK   -> classify the message (complaint, question, urgent, spam, etc.)
  2. DECIDE  -> choose an action based on the classification (auto-reply,
                escalate to human, archive, flag urgent)
  3. ACT     -> draft the appropriate response or routing note
  4. LOG     -> record every decision + reasoning to a running audit log

This is different from the Research Agent: instead of read -> summarize,
this agent makes DECISIONS WITH CONSEQUENCES, which is the core skill behind
real customer-support/CRM/ticketing automation.

Uses Groq's free API (same as the Research Agent project).
"""

import os
import json
import time
from groq import Groq

client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))
MODEL = "llama-3.3-70b-versatile"

# ── Sample "inbox" -- in a real system this would come from an email API,
#    a support ticket system, or a webhook. Hardcoded here for practice. ──
SAMPLE_INBOX = [
    {
        "id": 1,
        "from": "priya.sharma@example.com",
        "subject": "Order #4521 never arrived",
        "body": "I ordered 3 weeks ago and still nothing. This is unacceptable, I want a refund immediately or I'm disputing the charge with my bank."
    },
    {
        "id": 2,
        "from": "raj.patel@example.com",
        "subject": "Quick question about sizing",
        "body": "Hi, does the medium size run small? I'm usually a US size 10. Thanks!"
    },
    {
        "id": 3,
        "from": "winbig@totally-legit-prizes.biz",
        "subject": "YOU HAVE WON $1,000,000!!!",
        "body": "Click here now to claim your prize before it expires!!! Limited time only!!!"
    },
    {
        "id": 4,
        "from": "facilities@partner-corp.com",
        "subject": "URGENT: Server downtime affecting production",
        "body": "Our integration with your API has been failing since 9am with 500 errors. This is blocking our checkout flow for all customers. Need immediate assistance."
    },
    {
        "id": 5,
        "from": "happy.customer@example.com",
        "subject": "Just wanted to say thanks!",
        "body": "Your support team helped me last week and I just wanted to say the service was amazing. Keep it up!"
    },
]

# ── Decision rules the agent can choose from ──
ACTIONS = {
    "auto_reply": "Send an automated helpful reply",
    "escalate_urgent": "Escalate immediately to a human agent (urgent/business-critical)",
    "escalate_normal": "Route to a human agent (needs personal judgment)",
    "archive_spam": "Archive as spam/irrelevant",
    "acknowledge": "Send a short thank-you / acknowledgment"
}


def llm_call(prompt, system="You are a precise, structured assistant.", json_mode=True):
    messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    kwargs = {"model": MODEL, "messages": messages, "temperature": 0.2}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content


class TriageAgent:
    """
    Demonstrates: THINK (classify) -> DECIDE (pick action) -> ACT (respond) -> LOG
    """

    def __init__(self):
        self.audit_log = []  # the agent's memory of every decision made

    def think_classify(self, message):
        """Step 1 - THINK: classify the message."""
        prompt = f"""Classify this customer message into exactly one category:
complaint, question, urgent_business, spam, or compliment.

Also rate urgency from 1 (low) to 5 (critical).

From: {message['from']}
Subject: {message['subject']}
Body: {message['body']}

Respond ONLY with JSON: {{"category": "...", "urgency": 1-5, "reasoning": "one sentence why"}}"""
        raw = llm_call(prompt)
        return json.loads(raw)

    def decide_action(self, classification):
        """Step 2 - DECIDE: rule-based decision using the classification.
        This is deliberately a simple if/else, not another LLM call --
        showing that agents can mix LLM reasoning with plain code logic."""
        category = classification["category"]
        urgency = classification["urgency"]

        if category == "spam":
            return "archive_spam"
        if category == "urgent_business" or urgency >= 4:
            return "escalate_urgent"
        if category == "compliment":
            return "acknowledge"
        if category == "question":
            return "auto_reply"
        return "escalate_normal"

    def act_respond(self, message, classification, action):
        """Step 3 - ACT: draft the actual response/routing note."""
        if action == "archive_spam":
            return "[No reply sent — archived as spam]"

        if action == "escalate_urgent":
            return f"[ESCALATED] Flagged for immediate human review. Reason: {classification['reasoning']}"

        if action == "escalate_normal":
            return f"[ROUTED] Sent to human support queue. Reason: {classification['reasoning']}"

        # auto_reply / acknowledge -> actually draft a message with the LLM
        prompt = f"""Write a short, warm, professional email reply to this customer message.
Keep it under 60 words. Sign off as "Support Team".

Original message:
Subject: {message['subject']}
Body: {message['body']}

Category: {classification['category']}

Respond ONLY with JSON: {{"reply": "the email reply text"}}"""
        raw = llm_call(prompt)
        return json.loads(raw)["reply"]

    def process_message(self, message):
        """Run the full THINK -> DECIDE -> ACT loop for one message."""
        classification = self.think_classify(message)
        action = self.decide_action(classification)
        response = self.act_respond(message, classification, action)

        log_entry = {
            "id": message["id"],
            "from": message["from"],
            "subject": message["subject"],
            "category": classification["category"],
            "urgency": classification["urgency"],
            "reasoning": classification["reasoning"],
            "action": action,
            "action_label": ACTIONS[action],
            "response": response,
        }
        self.audit_log.append(log_entry)
        return log_entry

    def run(self, inbox):
        """Process every message in the inbox, one at a time."""
        print(f"\n{'='*70}\n📥 INBOX TRIAGE AGENT — Processing {len(inbox)} messages\n{'='*70}\n")

        for message in inbox:
            print(f"📧 Message #{message['id']}: \"{message['subject']}\"")
            print(f"   From: {message['from']}")

            entry = self.process_message(message)

            print(f"   🧠 Classified as: {entry['category'].upper()} (urgency {entry['urgency']}/5)")
            print(f"   💭 Reasoning: {entry['reasoning']}")
            print(f"   ⚡ Decision: {entry['action_label']}")
            print(f"   📝 Response: {entry['response']}")
            print()
            time.sleep(0.5)

        self._print_summary()
        return self.audit_log

    def _print_summary(self):
        print(f"{'='*70}\n📊 SUMMARY\n{'='*70}")
        counts = {}
        for entry in self.audit_log:
            counts[entry["action_label"]] = counts.get(entry["action_label"], 0) + 1
        for label, count in counts.items():
            print(f"   {label}: {count}")
        print()


if __name__ == "__main__":
    if not os.environ.get("GROQ_API_KEY"):
        print("⚠️  Set your free Groq API key first:")
        print('    $env:GROQ_API_KEY="your_key_here"   (Windows PowerShell)')
        print("    export GROQ_API_KEY=your_key_here    (Mac/Linux)")
        print("\nGet a free key at: https://console.groq.com")
        exit(1)

    agent = TriageAgent()
    log = agent.run(SAMPLE_INBOX)

    with open("triage_log.json", "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2)
    print("💾 Full audit log saved to triage_log.json")
