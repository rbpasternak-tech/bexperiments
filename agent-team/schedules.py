"""Recurring scheduled duties (morning triage, nightly check-in, Sunday recap).

Config format (config.yaml `schedules`): "HH:MM" for daily, a weekday prefix
for weekly ("sun 18:30"), "dayN HH:MM" for monthly ("day1 20:00"), or "off".
Fired state is tracked in the state dir so restarts don't re-fire.

Missed slots fire on the next poll — this is what lets the bot survive the
Mac sleeping. A daily slot catches up only on the same day (a missed 07:00
triage is not delivered the next morning). A weekly or monthly slot catches
up for CATCH_UP_DAYS, so a Sunday review missed because the Mac slept all
evening still runs when it wakes on Monday.
"""

from datetime import datetime, timedelta

CATCH_UP_DAYS = 3

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


class Scheduler:
    """Decides which configured schedules are due on each poll cycle."""

    def __init__(self, state_store, schedules_cfg):
        """Parse schedule specs; invalid entries are skipped with a warning."""
        self.state = state_store
        self.entries = {}
        for key, spec in (schedules_cfg or {}).items():
            if str(spec).strip().lower() in ("off", "none", ""):
                continue
            parsed = _parse_spec(str(spec))
            if parsed:
                self.entries[key] = parsed
            else:
                print(f"Warning: bad schedule spec for {key!r}: {spec!r}")

    def due_schedules(self, now=None):
        """Return schedule keys due now, marking them fired."""
        now = now or datetime.now()
        if not self._fired_path.exists():
            self._seed_first_run(now)
            return []
        fired = self.state._read_json(self._fired_path, {})
        due = []
        for key, spec in self.entries.items():
            slot = _latest_slot(spec, now)
            if slot is None:
                continue
            slot_day = slot.strftime("%Y-%m-%d")
            if fired.get(key, "") >= slot_day:
                continue
            due.append(key)
            fired[key] = slot_day
        if due:
            self.state._write_json(self._fired_path, fired)
        return due

    @property
    def _fired_path(self):
        """Path of the fired-schedules tracking file."""
        return self.state.state_dir / "schedules-fired.json"

    def _seed_first_run(self, now):
        """On first launch, mark already-passed slots fired so they don't
        all deliver at once; future slots still fire on time."""
        fired = {}
        for key, spec in self.entries.items():
            slot = _latest_slot(spec, now)
            if slot is not None:
                fired[key] = slot.strftime("%Y-%m-%d")
        self.state._write_json(self._fired_path, fired)


def _latest_slot(spec, now):
    """Most recent slot at or before `now` that may still fire, or None.

    spec is (kind, value, hour, minute) with kind 'daily', 'weekly'
    (value = weekday 0-6) or 'monthly' (value = day of month).
    """
    kind, value, hour, minute = spec
    if kind == "daily":
        slot = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return slot if slot <= now else None
    for back in range(0, CATCH_UP_DAYS + 1):
        day = now - timedelta(days=back)
        if kind == "weekly" and day.weekday() != value:
            continue
        if kind == "monthly" and day.day != value:
            continue
        slot = day.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if slot <= now:
            return slot
    return None


def _parse_spec(spec):
    """Parse 'HH:MM', 'ddd HH:MM' or 'dayN HH:MM' into (kind, value, hour,
    minute); None for invalid specs. 'off' is handled by the caller."""
    parts = spec.strip().lower().split()
    kind, value = "daily", None
    if len(parts) == 2:
        prefix = parts[0]
        if prefix in WEEKDAYS:
            kind, value = "weekly", WEEKDAYS.index(prefix)
        elif prefix.startswith("day") and prefix[3:].isdigit() and 1 <= int(prefix[3:]) <= 28:
            kind, value = "monthly", int(prefix[3:])
        else:
            return None
        parts = parts[1:]
    if len(parts) != 1 or ":" not in parts[0]:
        return None
    try:
        hour, minute = (int(x) for x in parts[0].split(":"))
    except ValueError:
        return None
    if not (0 <= hour < 24 and 0 <= minute < 60):
        return None
    return (kind, value, hour, minute)
