"""Second Brain jobs that used to be Cowork scheduled tasks.

The Cowork tasks (daily note, inbox sweep, weekly review, monthly archive)
run inside the Claude desktop app and skip their slot whenever the Mac is
asleep or the app is closed. They are ported here so they run inside the
bot, which launchd keeps alive and whose scheduler catches up missed slots
as soon as the Mac wakes. The job instructions are the Cowork task prompts,
adapted to this module's tools; each job may write only what its Cowork task
was allowed to write.

Every job runs unattended: Claude gets the job's instructions and a small
tool set, works until done, and its final summary goes to Telegram.
"""

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from cowork_watch import last_gmail_sweep
from gmail_reader import GmailReader, GmailUnavailable

MAX_ROUNDS = 40
MAX_TOKENS = 8000
_PROMPT_DIR = Path(__file__).resolve().parent / "vault_jobs"

# Loaded once at import: the repo sits in iCloud, and a prompt file evicted
# later could not be read by the launchd-run process.
JOBS = {
    "vault_inbox_sweep": ("Inbox sweep", (_PROMPT_DIR / "inbox_sweep.md").read_text()),
    "vault_weekly_review": ("Weekly review", (_PROMPT_DIR / "weekly_review.md").read_text()),
    "vault_monthly_archive": ("Monthly archive", (_PROMPT_DIR / "monthly_archive.md").read_text()),
}

# Default slots, merged under config.yaml `schedules` (config wins; set a key
# to "off" to disable). The sweep runs before the 07:00 morning triage so
# Jeeves reports what it captured.
DEFAULT_SCHEDULES = {
    "vault_daily_notes": "23:55",
    "vault_inbox_sweep": "06:45",
    "vault_weekly_review": "sun 18:45",
    "vault_monthly_archive": "day1 20:00",
}

TOOLS = [
    {
        "name": "read_note",
        "description": "Read a vault note by vault-relative path, e.g. 'Daily/2026-09-28.md'.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "list_files",
        "description": (
            "List .md notes under a vault folder (e.g. 'Projects', 'Ideas', "
            "'Daily') with days since each was last modified."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"folder": {"type": "string"}},
            "required": ["folder"],
        },
    },
    {
        "name": "last_gmail_sweep",
        "description": "Date of the newest 'Gmail sweep (YYYY-MM-DD…)' header in Reading/queue.md.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "gmail_search",
        "description": (
            "Search Gmail (read-only) with Gmail query syntax. Returns id, "
            "date, from, to, subject, snippet, unread, candidate urls (with "
            "in_queue flags) and a permalink for each message."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer", "description": "default 60, max 150"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "gmail_read",
        "description": "Read one Gmail message's text by id (read-only).",
        "input_schema": {
            "type": "object",
            "properties": {"message_id": {"type": "string"}},
            "required": ["message_id"],
        },
    },
    {
        "name": "add_queue_items",
        "description": (
            "Add reading items to Reading/queue.md under a new Inbox "
            "subsection (newest first). Items whose URL is already in the "
            "queue are skipped automatically. Call once per run."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "heading": {"type": "string", "description": "e.g. 'Gmail sweep (2026-09-28)'"},
                "items": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["heading", "items"],
        },
    },
    {
        "name": "append_section",
        "description": (
            "Append a new '## heading' section with a markdown body to the end "
            "of a note (a missing daily note is created from the template). "
            "Refuses if that heading already exists. Never rewrites content."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "heading": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["path", "heading", "body"],
        },
    },
]

# What each job may write, enforced in the tool handler (not just the prompt).
_ALLOWED_WRITES = {
    "vault_inbox_sweep": {"add_queue_items", "append_section:Sweep flags"},
    "vault_weekly_review": {"append_section:Weekly review"},
    "vault_monthly_archive": {"append_section:Monthly archive proposal"},
}


def run_job(job_key, claude, model, ctx, today=None, gmail=None):
    """Run one Second Brain job unattended; return its final summary text."""
    title, instructions = JOBS[job_key]
    vault = ctx["vault"]
    error = vault.availability_error()
    if error:
        raise RuntimeError(f"vault unavailable: {error}")
    today = today or date.today()
    vault.ensure_daily_notes(today)
    gmail = gmail or GmailReader(ctx.get("gmail_token_path"))
    job_ctx = {"vault": vault, "gmail": gmail, "job": job_key, "today": today}
    now = datetime.now()
    system = (
        f"You are running unattended inside Rebecca's Telegram bot as the "
        f"'{title}' job for her Obsidian Second Brain vault. Rebecca is not "
        f"present: never ask questions, decide and note assumptions.\n"
        f"TODAY is {today.isoformat()} ({today:%A}); YESTERDAY is "
        f"{(today - timedelta(days=1)).isoformat()}; local time {now:%H:%M}. "
        f"These dates are the only source of truth.\n"
        f"Use only the tools provided. You may write only what these "
        f"instructions say; everything else is read-only. Never move, "
        f"rename, or delete vault files, and never touch .obsidian/.\n\n"
        + instructions
    )
    messages = [{"role": "user", "content": f"Run the {title} now."}]
    response = None
    for round_no in range(1, MAX_ROUNDS + 1):
        response = claude.messages.create(
            model=model, max_tokens=MAX_TOKENS, system=system,
            tools=TOOLS, messages=messages,
        )
        if response.stop_reason != "tool_use":
            break
        messages.append({"role": "assistant", "content": response.content})
        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            try:
                result = _handle_tool(block.name, block.input, job_ctx)
            except Exception as exc:
                result = f"Error: {block.name} failed: {type(exc).__name__}: {exc}"
            print(f"[{job_key}] round {round_no}: {block.name} -> {str(result)[:160]}", flush=True)
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})
        messages.append({"role": "user", "content": results})
    text = "\n".join(b.text for b in (response.content if response else []) if b.type == "text").strip()
    if response is not None and response.stop_reason == "tool_use":
        text = (text + "\n" if text else "") + f"(stopped after {MAX_ROUNDS} tool rounds)"
    return text or "(finished without a summary)"


def run_daily_notes(ctx, today=None):
    """Deterministic nightly job: make sure notes exist through tomorrow."""
    today = today or date.today()
    vault = ctx["vault"]
    created = vault.ensure_daily_notes(today + timedelta(days=1), lookback_days=15)
    return created


def _handle_tool(name, args, job_ctx):
    """Execute one job tool call and return a string result."""
    vault, gmail, job = job_ctx["vault"], job_ctx["gmail"], job_ctx["job"]
    allowed = _ALLOWED_WRITES.get(job, set())
    if name == "read_note":
        return vault.read_note(args["path"], max_chars=60000)
    if name == "list_files":
        rows = vault.list_files_with_age(args.get("folder", ""))
        if not rows:
            return "No notes found there."
        return "\n".join(f"{path}  (modified {age}d ago)" for path, age in rows)
    if name == "last_gmail_sweep":
        found = last_gmail_sweep(vault)
        return found.isoformat() if found else "none found"
    if name in ("gmail_search", "gmail_read"):
        try:
            if name == "gmail_read":
                return gmail.read(args["message_id"])
            messages = gmail.search(args["query"], args.get("max_results", 60))
        except GmailUnavailable as exc:
            return f"Gmail unavailable: {exc}"
        in_queue = vault.queue_urls()
        for msg in messages:
            msg["urls"] = [{"url": u, "in_queue": u in in_queue} for u in msg["urls"]]
        return json.dumps(messages, ensure_ascii=False)[:120000] if messages else "[] (no messages)"
    if name == "add_queue_items":
        if "add_queue_items" not in allowed:
            return "Not allowed: this job may not write to the reading queue."
        return vault.add_queue_sweep(args["heading"], args.get("items", []))
    if name == "append_section":
        heading = args["heading"].strip().lstrip("#").strip()
        if not any(
            rule.startswith("append_section:") and heading.startswith(rule.split(":", 1)[1])
            for rule in allowed
        ):
            return f"Not allowed: this job may not add a section called '{heading}'."
        if not args["path"].startswith("Daily/"):
            return "Not allowed: sections may only be added to daily notes."
        return vault.append_section(args["path"], heading, args["body"])
    return f"Unknown tool: {name}"
