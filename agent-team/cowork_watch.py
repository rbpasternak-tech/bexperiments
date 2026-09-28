"""Watchdog for the Cowork scheduled tasks that feed the Second Brain.

The Cowork tasks (nightly daily note, 8am inbox sweep, Sunday weekly review)
run inside the Claude desktop app and silently stop when the Mac is asleep
at their slot or the app is closed. Their failure output goes to a run log
nobody reads, so gaps went unnoticed for days. The bot runs under launchd and
catches up missed slots on wake, so it checks their footprints in the vault
each morning and says so in Telegram when one is missing.

Read-only: this module never writes to the vault.
"""

import re
from datetime import date, timedelta

GMAIL_SWEEP_RE = re.compile(r"^#{2,4}\s+Gmail sweep \((\d{4}-\d{2}-\d{2})")
WEEKLY_REVIEW_MARK = "Weekly review (auto-generated"


def last_gmail_sweep(vault):
    """Return the date of the newest '### Gmail sweep (YYYY-MM-DD…)' header in
    Reading/queue.md, or None when there is none or the file is unreadable."""
    text = vault.read_note("Reading/queue.md", max_chars=10**7)
    newest = None
    for line in text.splitlines():
        match = GMAIL_SWEEP_RE.match(line.strip())
        if match:
            found = date.fromisoformat(match.group(1))
            newest = found if newest is None or found > newest else newest
    return newest


def cowork_warnings(vault, today, backfilled):
    """Return human-readable warnings about Cowork tasks that did not run.

    `backfilled` is the list of daily-note dates the bot just had to create;
    any date before today means the nightly daily-note task missed that night.
    """
    warnings = []
    if vault.availability_error():
        return [f"Vault unavailable: {vault.availability_error()}"]

    missed_notes = [d for d in backfilled if d < today.isoformat()]
    if missed_notes:
        warnings.append(
            "Nightly daily-note task did not run — I created "
            + ", ".join(missed_notes) + " from the template."
        )

    yesterday = today - timedelta(days=1)
    sweep = last_gmail_sweep(vault)
    if sweep is None:
        warnings.append("No Gmail sweep found in Reading/queue.md.")
    elif sweep < yesterday:
        days = (today - sweep).days
        warnings.append(
            f"Inbox sweep has not run since {sweep.isoformat()} ({days} days)."
        )

    if today.weekday() == 0:  # Monday: did Sunday's weekly review land?
        sunday = yesterday.isoformat()
        note = vault.read_note(f"Daily/{sunday}.md")
        if WEEKLY_REVIEW_MARK not in note:
            warnings.append(f"Sunday weekly review did not run ({sunday}).")
    return warnings


def format_alert(warnings):
    """One Telegram message, or None when everything ran."""
    if not warnings:
        return None
    lines = ["⚠️ Cowork scheduled tasks missed runs:"]
    lines += [f"• {w}" for w in warnings]
    lines.append(
        "Likely cause: the Mac was asleep or the Claude app was closed at "
        "the scheduled time. Open Claude → Scheduled to re-run them."
    )
    return "\n".join(lines)
