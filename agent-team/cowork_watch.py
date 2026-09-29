"""Watchdog for the scheduled jobs that feed the Second Brain.

The nightly daily note, the morning inbox sweep, and the Sunday weekly review
used to be Cowork tasks that silently stopped when the Mac slept; they now run
inside the bot (vault_jobs.py). Each morning this checks their footprints in
the vault and says so in Telegram when one is missing, whatever wrote them.

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
            "Daily notes were missing — I created "
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
    lines = ["⚠️ Second Brain jobs missed runs:"]
    lines += [f"• {w}" for w in warnings]
    lines.append(
        "Missed slots run when the Mac wakes; details are in "
        "~/Library/Logs/agent-team/bot.log."
    )
    return "\n".join(lines)
