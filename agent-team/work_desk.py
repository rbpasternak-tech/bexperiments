"""Work-desk facts for Jeeves' 07:00 morning triage (the daily message).

The morning triage gains a "Work desk" part built from outputs that other
jobs already produce, so nothing here sweeps Gmail, scrapes the web, or
duplicates a job:

- Inbox: today's 6:45 inbox sweep (vault_inbox_sweep) — its "Sweep flags
  (auto <today>)" section in the daily note and its "Gmail sweep (<today>"
  subsection in Reading/queue.md. Read only; the sweep owns both.
- Littler intel: the newest self-sent "Daily AI Competitive Intelligence"
  email (one targeted read-only Gmail search for that subject, not a sweep).
- Legal tech news: the newsletter digest's own JSON output in
  trends-dashboard/data, plus its launchd slots to notice missed runs.

Each source is classified NEW / NONE TODAY / STALE / UNAVAILABLE in code, so
the message never reposts an old issue as news. Read-only: this module never
writes to the vault, Gmail, or the state dir.
"""

import json
import plistlib
import re
from datetime import date, datetime, time, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

from cowork_watch import last_gmail_sweep

REPO_ROOT = Path(__file__).resolve().parent.parent
DIGEST_DATA_DIR = REPO_ROOT / "trends-dashboard" / "data"
DIGEST_PLIST = (
    Path.home() / "Library" / "LaunchAgents" / "com.bexperiments.newsletter-digest.plist"
)
LITTLER_QUERY = 'from:me subject:"Daily AI Competitive Intelligence" newer_than:4d'
# An issue counts as new if it arrived after yesterday's triage slot.
TRIAGE_SLOT = time(7, 0)
# A Littler issue whose body date trails its delivery date by more than this
# is old content re-sent (the task's known wrong-date bug).
MAX_LITTLER_LAG_DAYS = 1
# Grace after a digest slot before calling it missed (it can take ~2h).
DIGEST_GRACE = timedelta(hours=3)

_MONTH_DATE_RE = re.compile(
    r"Date:\W*((?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December) \d{1,2}, \d{4})"
)


def _local(dt):
    """Aware datetime -> naive local time (box/Mac clock zone)."""
    return dt.astimezone().replace(tzinfo=None) if dt.tzinfo else dt


def _clip(text, limit):
    """Trim text to `limit` chars on a line boundary where possible."""
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    return cut[: cut.rfind("\n")] if "\n" in cut else cut + "…"


def _section(text, heading_re):
    """Body of the first '## ' section whose heading matches, else None."""
    lines = text.splitlines()
    start = next((i for i, l in enumerate(lines) if re.match(heading_re, l)), None)
    if start is None:
        return None
    end = next(
        (i for i in range(start + 1, len(lines)) if re.match(r"^#{1,2}\s", lines[i])),
        len(lines),
    )
    return "\n".join(lines[start + 1:end]).strip()


def inbox_facts(vault, today):
    """Summarize today's 6:45 sweep from what it wrote; never re-run it."""
    day = today.isoformat()
    note = vault.read_note(f"Daily/{day}.md", max_chars=10**6)
    flags = _section(note, rf"^##\s+Sweep flags \(auto {day}")
    queue = vault.read_note("Reading/queue.md", max_chars=10**7)
    added = None
    qlines = queue.splitlines()
    for i, line in enumerate(qlines):
        if re.match(rf"^#{{2,4}}\s+Gmail sweep \({day}", line.strip()):
            added = 0
            for nxt in qlines[i + 1:]:
                if re.match(r"^#{1,4}\s", nxt):
                    break
                if re.match(r"^\s*- \[[ x]\]", nxt):
                    added += 1
            break
    if flags is None and added is None:
        last = last_gmail_sweep(vault)
        return (
            "Inbox: NONE TODAY — the 6:45 inbox sweep has not landed for "
            f"{day} (last sweep: {last.isoformat() if last else 'none found'}). "
            "Say so in one line; do not search Gmail yourself."
        )
    parts = [f"Inbox: NEW — today's sweep added {added if added is not None else 'an unknown number of'} "
             "item(s) to Reading/queue.md."]
    if flags:
        parts.append("Sweep flags (summarize; do not copy wholesale):\n" + _clip(flags, 2500))
    return "\n".join(parts)


def littler_facts(gmail, now):
    """Classify the newest Littler competitive-intel email."""
    since = datetime.combine(now.date() - timedelta(days=1), TRIAGE_SLOT)
    try:
        msgs = gmail.search(LITTLER_QUERY, 3)
    except Exception as exc:  # GmailUnavailable, network, quota
        return f"Littler intel: UNAVAILABLE — Gmail read failed ({type(exc).__name__}: {exc})."
    if not msgs:
        return "Littler intel: NONE TODAY — no issue in the last 4 days (the daily intel task may have stopped)."
    latest = msgs[0]
    try:
        delivered = _local(parsedate_to_datetime(latest["date"]))
    except (TypeError, ValueError):
        delivered = None
    when = delivered.strftime("%a %b %-d %-I:%M %p") if delivered else latest["date"]
    if delivered and delivered < since:
        return (
            f"Littler intel: NONE TODAY — no issue since yesterday's triage; "
            f"the last one arrived {when}."
        )
    try:
        body = gmail.read(latest["id"], max_chars=8000)
    except Exception as exc:
        return f"Littler intel: UNAVAILABLE — could not read the {when} issue ({type(exc).__name__})."
    match = _MONTH_DATE_RE.search(body.replace("*", ""))
    body_date = None
    if match:
        try:
            body_date = datetime.strptime(match.group(1), "%B %d, %Y").date()
        except ValueError:
            body_date = None
    if delivered and body_date and (delivered.date() - body_date).days > MAX_LITTLER_LAG_DAYS:
        return (
            f"Littler intel: STALE — the issue that arrived {when} is dated "
            f"{body_date:%b %-d} ({(delivered.date() - body_date).days} days old), "
            "the intel task's recurring wrong-date bug. Do not list its items."
        )
    new = _section(body.replace("**", ""), r"^#{2,4}\s*NEW SINCE LAST BRIEFING")
    if new is None:
        m = re.search(r"NEW SINCE LAST BRIEFING(.*?)(?:\n---|\n#{2,4}\s)", body, re.S)
        new = m.group(1).strip() if m else ""
    new = new.split("\n---")[0].strip()
    if not new or re.search(r"no (material )?new developments", new, re.I):
        return f"Littler intel: NONE TODAY — the {when} issue reports no new developments."
    dated = f" (dated {body_date:%b %-d})" if body_date else ""
    return (
        f"Littler intel: NEW — issue arrived {when}{dated}. New since last briefing "
        "(give at most three one-line highlights):\n" + _clip(new, 1800)
    )


def _digest_slots(now, days=8):
    """Past newsletter-digest launchd slots (from its plist) in the window."""
    try:
        with open(DIGEST_PLIST, "rb") as fh:
            entries = plistlib.load(fh).get("StartCalendarInterval") or []
    except (OSError, plistlib.InvalidFileException):
        return []
    if isinstance(entries, dict):
        entries = [entries]
    slots = []
    for back in range(days, -1, -1):
        day = now.date() - timedelta(days=back)
        for e in entries:
            wd = e.get("Weekday")
            if wd is not None and (int(wd) - 1) % 7 != day.weekday():
                continue  # launchd: 0/7 = Sunday; Python: Monday = 0
            slot = datetime.combine(day, time(int(e.get("Hour", 0)), int(e.get("Minute", 0))))
            if slot + DIGEST_GRACE <= now:
                slots.append(slot)
    return slots


def legal_tech_facts(now):
    """Classify the newest Tech & Legal Tech Digest run from its JSON output."""
    since = datetime.combine(now.date() - timedelta(days=1), TRIAGE_SLOT)
    try:
        index = json.loads((DIGEST_DATA_DIR / "index.json").read_text())
        runs = sorted(index["digests"], key=lambda d: d["run_date"])
        latest = runs[-1]
        digest = json.loads((DIGEST_DATA_DIR / latest["file"]).read_text())
    except (OSError, ValueError, KeyError, IndexError) as exc:
        return f"Legal tech news: UNAVAILABLE — no digest data ({type(exc).__name__})."
    run_dates = {r["run_date"][:10] for r in runs}
    try:
        ran_at = datetime.fromisoformat(digest.get("meta", {}).get("run_date", ""))
    except ValueError:
        ran_at = datetime.combine(date.fromisoformat(latest["run_date"][:10]), time(8, 0))
    ran_at = _local(ran_at)
    missed = [s.date() for s in _digest_slots(now) if s.date().isoformat() not in run_dates]
    late = ""
    if missed:
        late = " LATE/MISSED: no digest for " + ", ".join(f"{d:%a %-m/%-d}" for d in missed) + "."
    when = ran_at.strftime("%a %b %-d %-I:%M %p")
    if ran_at < since:
        return (
            f"Legal tech news: NONE TODAY — the last digest ran {when} "
            f"(covering {latest['date_range_start']} to {latest['date_range_end']}); "
            f"already reported, do not repeat it.{late}"
        )
    signals = [
        f"- {s.get('entity', '')}: {s.get('description', '')}"
        for s in (digest.get("legal_tech_signals") or [])[:4]
    ]
    narrative = _clip(digest.get("weekly_narrative") or "", 500)
    return (
        f"Legal tech news: NEW — digest ran {when} (covering "
        f"{latest['date_range_start']} to {latest['date_range_end']}; full issue "
        f"is in her email).{late} Give at most three one-line highlights.\n"
        f"Narrative: {narrative}\nLegal-tech signals:\n" + "\n".join(signals)
    )


def build_work_desk(vault, gmail, now=None):
    """The WORK DESK FACTS block appended to the morning-triage instruction."""
    now = now or datetime.now()
    sections = []
    for build in (
        lambda: inbox_facts(vault, now.date()),
        lambda: littler_facts(gmail, now),
        lambda: legal_tech_facts(now),
    ):
        try:
            sections.append(build())
        except Exception as exc:  # one bad source must not sink the triage
            sections.append(f"(work-desk source failed: {type(exc).__name__}: {exc})")
    return "WORK DESK FACTS (computed by the bot just now):\n\n" + "\n\n".join(sections)
