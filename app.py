"""
Inbox Triage Agent — Flask Backend
=====================================
Streams the agent's classify -> decide -> act loop live to the browser
using Server-Sent Events, same pattern as the Research Agent project.
"""

import os
import json
import time
from flask import Flask, request, Response, send_from_directory, jsonify
from flask_cors import CORS
from groq import Groq

app = Flask(__name__, static_folder="static")
CORS(app)

client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))
MODEL = "llama-3.3-70b-versatile"

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

ACTIONS = {
    "auto_reply": "Send an automated helpful reply",
    "escalate_urgent": "Escalate immediately to a human agent",
    "escalate_normal": "Route to a human agent",
    "archive_spam": "Archive as spam/irrelevant",
    "acknowledge": "Send a short thank-you / acknowledgment"
}


def llm_call(prompt, json_mode=True):
    messages = [{"role": "system", "content": "You are a precise, structured assistant."},
                {"role": "user", "content": prompt}]
    kwargs = {"model": MODEL, "messages": messages, "temperature": 0.2}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content


def think_classify(message):
    prompt = f"""Classify this customer message into exactly one category:
complaint, question, urgent_business, spam, or compliment.

Also rate urgency from 1 (low) to 5 (critical).

From: {message['from']}
Subject: {message['subject']}
Body: {message['body']}

Respond ONLY with JSON: {{"category": "...", "urgency": 1-5, "reasoning": "one sentence why"}}"""
    return json.loads(llm_call(prompt))


def decide_action(classification):
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


def act_respond(message, classification, action):
    if action == "archive_spam":
        return "[No reply sent — archived as spam]"
    if action == "escalate_urgent":
        return f"[ESCALATED] Flagged for immediate human review. Reason: {classification['reasoning']}"
    if action == "escalate_normal":
        return f"[ROUTED] Sent to human support queue. Reason: {classification['reasoning']}"

    prompt = f"""Write a short, warm, professional email reply to this customer message.
Keep it under 60 words. Sign off as "Support Team".

Subject: {message['subject']}
Body: {message['body']}
Category: {classification['category']}

Respond ONLY with JSON: {{"reply": "the email reply text"}}"""
    return json.loads(llm_call(prompt))["reply"]


def sse_event(event_type, data):
    return f"data: {json.dumps({'type': event_type, **data})}\n\n"


def run_triage_stream(inbox):
    yield sse_event("status", {"message": f"Processing {len(inbox)} messages..."})

    audit_log = []
    for message in inbox:
        yield sse_event("processing", {"id": message["id"], "from": message["from"], "subject": message["subject"]})

        try:
            classification = think_classify(message)
        except Exception as e:
            yield sse_event("error", {"message": f"Classification failed for message #{message['id']}: {str(e)}"})
            continue

        yield sse_event("classified", {
            "id": message["id"],
            "category": classification["category"],
            "urgency": classification["urgency"],
            "reasoning": classification["reasoning"]
        })

        action = decide_action(classification)
        yield sse_event("decided", {"id": message["id"], "action": action, "action_label": ACTIONS[action]})

        try:
            response = act_respond(message, classification, action)
        except Exception as e:
            response = f"[Error drafting response: {str(e)}]"

        entry = {
            "id": message["id"], "from": message["from"], "subject": message["subject"],
            "category": classification["category"], "urgency": classification["urgency"],
            "reasoning": classification["reasoning"], "action": action,
            "action_label": ACTIONS[action], "response": response
        }
        audit_log.append(entry)
        yield sse_event("responded", entry)
        time.sleep(0.3)

    yield sse_event("done", {"log": audit_log})


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/inbox")
def get_inbox():
    return jsonify({"inbox": SAMPLE_INBOX})


@app.route("/api/triage")
def triage():
    return Response(run_triage_stream(SAMPLE_INBOX), mimetype="text/event-stream",
                     headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/triage-custom", methods=["POST"])
def triage_custom():
    """Process a single custom message submitted from the frontend form."""
    data = request.get_json()
    message = {
        "id": 99,
        "from": data.get("from", "unknown@example.com"),
        "subject": data.get("subject", "(no subject)"),
        "body": data.get("body", "")
    }
    if not message["body"]:
        return jsonify({"error": "Message body is required"}), 400

    return Response(run_triage_stream([message]), mimetype="text/event-stream",
                     headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/health")
def health():
    key = os.environ.get("GROQ_API_KEY", "")
    return jsonify({"status": "ok", "api_key_set": bool(key)})


if __name__ == "__main__":
    print("\n" + "=" * 55)
    print("  Inbox Triage Agent — Web UI")
    print("=" * 55)
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        print("  ⚠️  GROQ_API_KEY not set!")
        print("  Get a free key at https://console.groq.com")
    else:
        print(f"  ✅ API Key detected: {key[:8]}...")
    print("  🌐 Open: http://localhost:5000")
    print("=" * 55 + "\n")
    app.run(debug=True, port=5000, threaded=True)
