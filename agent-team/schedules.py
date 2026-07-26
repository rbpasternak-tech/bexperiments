"""Recurring scheduled duties (morning triage, nightly check-in, Sunday recap).

Config format (config.yaml `schedules`): "HH:MM" for daily, or a weekday
prefix for weekly, e.g. "sun 18:30". Fired state is tracked per-day in the
state dir so restarts don't re-fire and missed slots fire on next poll.
"""

from datetime import datetime

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


class Scheduler:
    """Decides which configured schedules are due on each poll cycle."""

    def __init__(self, state_store, schedules_cfg):
        """Parse schedule specs; invalid entries are skipped with a warning."""
        self.state = state_store
        self.entries = {}
        for key, spec in (schedules_cfg or {}).items():
            parsed = _parse_spec(str(spec))
            if parsed:
                self.entries[key] = parsed
            else:
                print(f"Warning: bad schedule spec for {key!r}: {spec!r}")

    def due_schedules(self, now=None):
        """Return schedule keys due now, marking them fired for today."""
        now = now or datetime.now()
        if not self._fired_path.exists():
            self._seed_first_run(now)
            return []
        fired = self.state._read_json(self._fired_path, {})
        today = now.strftime("%Y-%m-%d")
        due = []
        for key, (weekday, hour, minute) in self.entries.items():
            if weekday is not None and now.weekday() != weekday:
                continue
            if fired.get(key) == today:
                continue
            if (now.hour, now.minute) >= (hour, minute):
                due.append(key)
                fired[key] = today
        if due:
            self.state._write_json(self._fired_path, fired)
        return due

    @property
    def _fired_path(self):
        """Path of the fired-schedules tracking file."""
        return self.state.state_dir / "schedules-fired.json"

    def _seed_first_run(self, now):
        """On first launch, mark already-passed slots fired so they don't
        all deliver at once; future slots today still fire on time."""
        today = now.strftime("%Y-%m-%d")
        fired = {
            key: today
            for key, (weekday, hour, minute) in self.entries.items()
            if (weekday is None or now.weekday() == weekday)
            and (now.hour, now.minute) >= (hour, minute)
        }
        self.state._write_json(self._fired_path, fired)


def _parse_spec(spec):
    """Parse 'HH:MM' or 'ddd HH:MM' into (weekday|None, hour, minute)."""
    parts = spec.strip().lower().split()
    weekday = None
    if len(parts) == 2:
        if parts[0] not in WEEKDAYS:
            return None
        weekday = WEEKDAYS.index(parts[0])
        parts = parts[1:]
    if len(parts) != 1 or ":" not in parts[0]:
        return None
    try:
        hour, minute = (int(x) for x in parts[0].split(":"))
    except ValueError:
        return None
    if not (0 <= hour < 24 and 0 <= minute < 60):
        return None
    return (weekday, hour, minute)
