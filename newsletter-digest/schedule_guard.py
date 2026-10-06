#!/usr/bin/env python3
"""Decide whether a scheduled newsletter digest is due, so missed runs catch up.

launchd starts the runner every 30 minutes and again after the Mac wakes, not
only at the scheduled time. Each time, the runner asks this module whether the
most recent scheduled slot (Wednesday or Friday at 08:00 local time) has
already been sent. If the Mac was asleep, shut or offline at 08:00, the digest
therefore goes out shortly after it wakes instead of being skipped until the
next slot. A run that fails is retried on the next check.

The state file records the last slot a digest was sent for. main.py writes it
as soon as the email is sent (so a later failure in trend extraction or
publishing never causes a duplicate email), and the runner writes it after
any successful scheduled run.

Usage:
    python3 schedule_guard.py due STATE_FILE    # exit 0 if a digest is due, 1 if not
    python3 schedule_guard.py mark STATE_FILE   # record the current slot as sent
"""

import os
import sys
from datetime import datetime, time, timedelta

# datetime.weekday(): Monday is 0, so 2 is Wednesday and 4 is Friday.
SCHEDULE_WEEKDAYS = (2, 4)
SCHEDULE_TIME = time(8, 0)
STATE_ENV_VAR = "NEWSLETTER_DIGEST_STATE"


def last_slot(now=None):
    """Return the most recent scheduled slot at or before ``now``.

    Args:
        now: Local datetime to measure from (defaults to the current time).

    Returns:
        A naive local datetime on a scheduled weekday at SCHEDULE_TIME.
    """
    now = now or datetime.now()
    for days_back in range(8):
        day = (now - timedelta(days=days_back)).date()
        if day.weekday() in SCHEDULE_WEEKDAYS:
            slot = datetime.combine(day, SCHEDULE_TIME)
            if slot <= now:
                return slot
    raise ValueError("no scheduled weekday configured")


def read_marked(path):
    """Return the slot recorded in ``path``, or None if missing or unreadable."""
    try:
        with open(path) as state_file:
            return datetime.fromisoformat(state_file.read().strip())
    except (OSError, ValueError):
        return None


def is_due(path, now=None):
    """Return True if the latest slot has not been sent yet."""
    marked = read_marked(path)
    return marked is None or marked < last_slot(now)


def mark_sent(path, now=None):
    """Record the latest slot as sent, writing ``path`` atomically.

    Returns:
        The slot that was recorded.
    """
    slot = last_slot(now)
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w") as state_file:
        state_file.write(slot.isoformat() + "\n")
    os.replace(tmp_path, path)
    return slot


def mark_sent_from_env(now=None):
    """Record the slot in the state file named by STATE_ENV_VAR, if set.

    Never raises: failing to record the slot must not fail a run whose
    email already went out.
    """
    path = os.environ.get(STATE_ENV_VAR)
    if not path:
        return
    try:
        slot = mark_sent(path, now)
        print(f"  Recorded digest for the {slot:%a %Y-%m-%d %H:%M} slot.")
    except OSError as e:
        print(f"  Warning: could not record the sent slot in {path} ({e}).")


def main(argv=None):
    """Command-line entry point used by the launchd runner."""
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2 or argv[0] not in ("due", "mark"):
        print(__doc__.strip().split("Usage:")[1], file=sys.stderr)
        return 2
    command, path = argv
    if command == "mark":
        mark_sent(path)
        return 0
    slot = last_slot()
    if is_due(path):
        print(f"Digest due for the {slot:%a %Y-%m-%d %H:%M} slot.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
