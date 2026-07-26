"""Tool definitions and handlers the personas can call via Claude tool use."""

import json
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DIGEST_DATA_DIR = REPO_ROOT / "trends-dashboard" / "data"

TOOL_DEFINITIONS = [
    {
        "name": "set_reminder",
        "description": (
            "Schedule a reminder to be sent to the user in this chat at a "
            "specific time. Use the current date/time given in the system "
            "prompt to resolve relative times like 'in 20 minutes' or "
            "'tomorrow at 9am'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "due": {
                    "type": "string",
                    "description": "Local due time as ISO 8601, e.g. 2026-07-26T18:30:00",
                },
                "text": {
                    "type": "string",
                    "description": "What to remind the user about, phrased in your own voice",
                },
            },
            "required": ["due", "text"],
        },
    },
    {
        "name": "list_reminders",
        "description": "List the user's pending reminders in this chat.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "cancel_reminder",
        "description": "Cancel a pending reminder by its id (from list_reminders).",
        "input_schema": {
            "type": "object",
            "properties": {
                "reminder_id": {"type": "string", "description": "Reminder id to cancel"}
            },
            "required": ["reminder_id"],
        },
    },
    {
        "name": "get_latest_digest",
        "description": (
            "Fetch the most recent tech/legal-tech news digest produced by the "
            "newsletter pipeline: top topics, mention counts, sentiment, and "
            "representative headlines. Use when the user asks what's going on "
            "in the news or their digest."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
]


def _get_latest_digest():
    """Return a compact summary of the newest digest JSON, or an explanation."""
    index_path = DIGEST_DATA_DIR / "index.json"
    try:
        index = json.loads(index_path.read_text())
        digests = sorted(index["digests"], key=lambda d: d["run_date"])
        latest = digests[-1]
        digest = json.loads((DIGEST_DATA_DIR / latest["file"]).read_text())
    except (OSError, json.JSONDecodeError, KeyError, IndexError) as exc:
        return f"No digest data available ({exc})."
    topics = sorted(
        digest.get("topics", []), key=lambda t: t.get("mention_count", 0), reverse=True
    )
    summary = {
        "date_range": f"{latest['date_range_start']} to {latest['date_range_end']}",
        "newsletter_count": latest.get("newsletter_count"),
        "rss_article_count": latest.get("rss_article_count"),
        "top_topics": [
            {
                "name": t.get("name"),
                "category": t.get("category"),
                "mentions": t.get("mention_count"),
                "sentiment": t.get("sentiment"),
                "headlines": t.get("representative_headlines", [])[:3],
            }
            for t in topics[:8]
        ],
    }
    return json.dumps(summary, ensure_ascii=False)


def handle_tool_call(name, tool_input, chat_id, persona_key, state):
    """Execute one tool call for a persona and return a string result."""
    if name == "set_reminder":
        due = tool_input.get("due", "")
        try:
            datetime.fromisoformat(due)
        except ValueError:
            return f"Error: due time '{due}' is not valid ISO 8601."
        reminder_id = state.add_reminder(chat_id, persona_key, due, tool_input["text"])
        return f"Reminder {reminder_id} set for {due}."
    if name == "list_reminders":
        reminders = state.list_reminders(chat_id)
        if not reminders:
            return "No pending reminders."
        return json.dumps(
            [
                {"id": r["id"], "due": r["due"], "text": r["text"], "set_by": r["persona"]}
                for r in reminders
            ],
            ensure_ascii=False,
        )
    if name == "cancel_reminder":
        if state.cancel_reminder(chat_id, tool_input.get("reminder_id", "")):
            return "Reminder cancelled."
        return "No reminder with that id."
    if name == "get_latest_digest":
        return _get_latest_digest()
    return f"Unknown tool: {name}"
