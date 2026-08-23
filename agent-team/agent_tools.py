"""Tool definitions and handlers the personas can call via Claude tool use.

Handlers receive a ctx dict: {chat_id, persona_key, state, vault,
health_export_dir}. Vault-backed tools degrade gracefully when the vault
isn't reachable (e.g. running off the Mac).
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

from health_export import read_health_metrics, rings_closed

REPO_ROOT = Path(__file__).resolve().parent.parent
DIGEST_DATA_DIR = REPO_ROOT / "trends-dashboard" / "data"

BOOL_CELL = {"yes": "✅", "no": "X", "skip": "—", "": ""}
HABIT_BOOL_COLS = {
    "rings": "Rings",
    "floss": "Floss",
    "vibe_plate": "Vibe plate",
    "red_light": "Red light",
    "leg_roller": "Leg roller",
    "read_audio": "Read (audio)",
    "read_physical": "Read (physical)",
}

_BOOL_PROP = {
    "type": "string",
    "enum": ["yes", "no", "skip", ""],
    "description": "yes, no, skip (intentionally), or '' if unknown",
}

TOOL_DEFINITIONS = [
    {
        "name": "set_reminder",
        "description": (
            "Schedule a reminder to be sent to the user in this chat at a "
            "specific time. Use the current date/time given in the system "
            "prompt to resolve relative times like 'in 20 minutes'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "due": {
                    "type": "string",
                    "description": "Local due time as ISO 8601, e.g. 2026-07-27T18:30:00",
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
            "Fetch the most recent tech/legal-tech news digest: top topics, "
            "mention counts, sentiment, representative headlines."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "read_vault_note",
        "description": (
            "Read a note from the Obsidian vault by vault-relative path, e.g. "
            "'Daily/2026-07-27.md', 'Tracking/Habits/2026-07.md', "
            "'Reading/queue.md', 'Tasks/Master.md'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Vault-relative note path"}
            },
            "required": ["path"],
        },
    },
    {
        "name": "capture_reading",
        "description": (
            "Save a link/article the user wants captured into the vault's "
            "reading queue Inbox. Deduplicates by URL."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL to capture"},
                "title": {"type": "string", "description": "Short human title"},
            },
            "required": ["url", "title"],
        },
    },
    {
        "name": "get_open_tasks",
        "description": "List unchecked tasks from the vault's Tasks/Master.md.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "complete_task",
        "description": (
            "Mark a task done in Tasks/Master.md by checking its box. Pass a "
            "distinctive substring of the task text from get_open_tasks."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "task_text": {
                    "type": "string",
                    "description": "Substring identifying the task line",
                }
            },
            "required": ["task_text"],
        },
    },
    {
        "name": "list_vault_files",
        "description": (
            "List markdown note paths in the vault, optionally under a "
            "subfolder. Use this to discover where something lives (e.g. the "
            "To Try lists, Projects) before appending to it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "subpath": {
                    "type": "string",
                    "description": "Vault-relative folder to list; '' for whole vault",
                }
            },
        },
    },
    {
        "name": "append_to_note",
        "description": (
            "Append ONE line (usually a '- ...' bullet) under a section "
            "heading in a vault note — e.g. a movie to a To Try list, a "
            "'Worked on' entry in today's daily note, an update under a "
            "project. Append-only: it never rewrites existing content. "
            "Creates the section if the note lacks it. If unsure which note "
            "or section, use list_vault_files/read_vault_note first, and ask "
            "the user when genuinely ambiguous."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Vault-relative note path, e.g. 'Daily/2026-07-27.md'",
                },
                "section": {
                    "type": "string",
                    "description": "Heading text to file under, e.g. 'Worked on'",
                },
                "line": {
                    "type": "string",
                    "description": "The line to append, e.g. '- Sinners (rec. by Sam)'",
                },
            },
            "required": ["path", "section", "line"],
        },
    },
    {
        "name": "read_health_export",
        "description": (
            "Read the day's Apple Health numbers (steps, calories via "
            "MyFitnessPal sync, weight, and — when the Activity metrics "
            "are exported — a computed 'rings' yes/no verdict) from the "
            "Health Auto Export folder. The phone pushes a finished day "
            "automatically overnight, so a date's numbers usually become "
            "available the following morning; a result flagged "
            "'partial' means the day's totals are not final yet."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "YYYY-MM-DD; defaults to today",
                }
            },
        },
    },
    {
        "name": "record_habits",
        "description": (
            "Write the user's habit answers into the monthly habit grid in "
            "the vault. Only pass fields you actually know; blanks leave "
            "existing cells untouched. Use read_health_export first for "
            "steps/calories/weight when available."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "YYYY-MM-DD; defaults to today"},
                "steps": {"type": "integer", "description": "Step count, omit if unknown"},
                "calories": {"type": "integer", "description": "Calories, omit if unknown"},
                "weight": {"type": "number", "description": "Weight, omit if not measured"},
                "rings": _BOOL_PROP,
                "floss": _BOOL_PROP,
                "vibe_plate": _BOOL_PROP,
                "red_light": _BOOL_PROP,
                "leg_roller": _BOOL_PROP,
                "read_audio": _BOOL_PROP,
                "read_physical": _BOOL_PROP,
            },
        },
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


def _record_habits(tool_input, vault):
    """Translate record_habits input into habit-grid cells and write them."""
    date_str = tool_input.get("date") or datetime.now().strftime("%Y-%m-%d")
    values = {}
    if tool_input.get("steps") is not None:
        values["Steps"] = f"{int(tool_input['steps']):,}"
    if tool_input.get("calories") is not None:
        values["Calories"] = f"{int(tool_input['calories']):,}"
    if tool_input.get("weight") is not None:
        values["Weight"] = str(tool_input["weight"])
    for field, column in HABIT_BOOL_COLS.items():
        answer = str(tool_input.get(field, "") or "").lower()
        if answer in BOOL_CELL and answer != "":
            values[column] = BOOL_CELL[answer]
    if not values:
        return "Nothing to record — no fields provided."
    return vault.upsert_habit_row(date_str, values)


def record_health_rows(ctx, days=4):
    """Deterministically write recent days' health metrics to the habit grid.

    Runs before the LLM habit check-in so the numbers land even if the
    persona's turn fails or hits its token limit. Only fills days whose
    Steps cell is still empty (never overwrites a hand-corrected value) and
    skips days flagged 'partial' (their finished totals arrive the next
    day). Returns a short summary for the log / Telegram.
    """
    vault = ctx["vault"]
    export_dir = ctx.get("health_export_dir")
    goals = ctx.get("ring_goals")
    recorded, last_error = [], None
    today = datetime.now().date()
    for i in range(days):
        date_str = (today - timedelta(days=i)).isoformat()
        cells = vault.habit_row_cells(date_str)
        if cells is None or cells.get("Steps"):
            continue  # row missing, or steps already recorded
        metrics = read_health_metrics(export_dir, date_str)
        if "error" in metrics:
            last_error = metrics["error"]  # e.g. eviction vs phone not syncing
            continue
        if metrics.get("steps") is None or metrics.get("partial"):
            continue  # nothing usable yet, or day not finished
        fields = {"date": date_str, "steps": metrics["steps"]}
        if metrics.get("calories") is not None:
            fields["calories"] = metrics["calories"]
        if metrics.get("weight") is not None:
            fields["weight"] = metrics["weight"]
        rings = rings_closed(metrics, goals)
        if rings:
            fields["rings"] = rings
        _record_habits(fields, vault)
        recorded.append(date_str)
    if recorded:
        return "recorded " + ", ".join(recorded)
    if last_error:
        return "no rows recorded — " + last_error
    return "no new days to record"


def handle_tool_call(name, tool_input, ctx):
    """Execute one tool call for a persona and return a string result."""
    state, chat_id, persona_key = ctx["state"], ctx["chat_id"], ctx["persona_key"]
    vault = ctx["vault"]
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
    if name == "read_vault_note":
        return vault.read_note(tool_input.get("path", ""))
    if name == "capture_reading":
        return vault.append_reading_item(
            tool_input.get("url", ""), tool_input.get("title", "(untitled)")
        )
    if name == "get_open_tasks":
        tasks = vault.open_tasks()
        if not tasks:
            return "No open tasks found (or Tasks/Master.md unavailable)."
        return "\n".join(f"{i + 1}. {t}" for i, t in enumerate(tasks))
    if name == "complete_task":
        if vault.complete_task(tool_input.get("task_text", "")):
            return "Task checked off in Tasks/Master.md."
        return "No matching open task found."
    if name == "list_vault_files":
        files = vault.list_files(tool_input.get("subpath", ""))
        return "\n".join(files) if files else "No notes found (or vault unavailable)."
    if name == "append_to_note":
        return vault.append_under_section(
            tool_input.get("path", ""),
            tool_input.get("section", ""),
            tool_input.get("line", ""),
        )
    if name == "read_health_export":
        date_str = tool_input.get("date") or datetime.now().strftime("%Y-%m-%d")
        result = read_health_metrics(ctx["health_export_dir"], date_str)
        if "error" not in result:
            rings = rings_closed(result, ctx.get("ring_goals"))
            if rings:
                result["rings"] = rings
        return json.dumps(result, ensure_ascii=False)
    if name == "record_habits":
        return _record_habits(tool_input, vault)
    return f"Unknown tool: {name}"
