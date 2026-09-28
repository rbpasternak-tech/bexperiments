"""Automatic import of Apple Health numbers into the monthly habit grid.

Runs on its own background thread (every `health_import_every_minutes`,
default 60) and once more right before Bartleby's nightly check-in, so the
grid fills itself as soon as the phone's AutoSync push lands — no Telegram
conversation required.

Rules, per recent past day (today is never written; its totals are still
growing):

  * A cell is only written when it is empty, or still holds exactly the
    value this importer wrote last time. Anything typed or corrected by
    hand is left alone.
  * A 'partial' read (the phone had not pushed the finished day yet) is
    written anyway, so a day never stays blank just because the final push
    was late, and it is upgraded on a later run once the finished totals
    arrive. A final read marks the day done and it is not read again.

What was written is kept in a small ledger (health-import.json in the
bot's state dir) alongside the last run's status, which doctor.sh prints.
"""

import threading
import time
from datetime import date, datetime, timedelta

from agent_tools import habit_cell_values
import mfp_source
from health_export import read_health_metrics, rings_closed

HEALTH_COLUMNS = ("Steps", "Calories", "Weight", "Rings")
LOOKBACK_DAYS = 7
LEDGER_KEEP_DAYS = 45
DEFAULT_EVERY_MINUTES = 60
LEDGER_FILE = "health-import.json"
# Hourly reads of a day with no data at all before giving up on it (two
# days' worth): covers a phone that was off or away, without re-reading a
# dead day for the whole lookback window.
MAX_MISSES = 48

# Serializes the background thread and the check-in's synchronous run so
# two imports never interleave their ledger read-modify-write.
_IMPORT_LOCK = threading.Lock()


def import_recent_days(ctx, lookback_days=LOOKBACK_DAYS, today=None):
    """Write recent days' health numbers to the habit grid.

    ctx carries {state, vault, health_export_dir, ring_goals}. Returns a
    dict: {"recorded": [dates], "error": str or None, "summary": str}.
    "error" is set when the vault is unavailable or yesterday's numbers
    could not be read, so callers can alert; gaps on older days are only
    counted in the summary.
    """
    with _IMPORT_LOCK:
        return _import_locked(ctx, lookback_days, today or date.today())


def _import_locked(ctx, lookback_days, today):
    """Body of import_recent_days; caller holds _IMPORT_LOCK."""
    vault, state = ctx["vault"], ctx["state"]
    ledger_path = state.state_dir / LEDGER_FILE
    ledger = state._read_json(ledger_path, {})
    days = ledger.setdefault("days", {})
    recorded, notes, error = [], [], None

    vault_error = vault.availability_error()
    if vault_error:
        error = f"vault unavailable: {vault_error}"
    else:
        for offset in range(1, lookback_days + 1):
            date_str = (today - timedelta(days=offset)).isoformat()
            entry = days.get(date_str)
            outcome = _import_day(ctx, date_str, entry)
            if outcome.get("error"):
                notes.append(outcome["error"])
                # Alert-worthy only for yesterday: older gaps were already
                # reported on their own night and usually mean the phone
                # simply had no data for that day.
                if offset == 1:
                    error = outcome["error"]
                miss = dict(entry or {"cells": {}, "final": False})
                miss["misses"] = miss.get("misses", 0) + 1
                days[date_str] = miss
            if outcome.get("entry"):
                days[date_str] = outcome["entry"]
            if outcome.get("written"):
                recorded.append(date_str + (" (partial)" if outcome.get("partial") else ""))

        recorded.extend(_backfill_calories_from_mfp(ctx, days, today, lookback_days))

    cutoff = (today - timedelta(days=LEDGER_KEEP_DAYS)).isoformat()
    for old in [d for d in days if d < cutoff]:
        del days[old]

    if error:
        summary = "COULD NOT READ — " + error
        if recorded:
            summary += "; recorded " + ", ".join(recorded)
    elif recorded:
        summary = "recorded " + ", ".join(recorded)
    else:
        summary = "nothing new to record"
    if notes and not error:
        summary += f" ({len(notes)} older day(s) without data)"
    ledger["last_run"] = {
        "at": datetime.now().isoformat(timespec="seconds"),
        "summary": summary,
    }
    state._write_json(ledger_path, ledger)
    return {"recorded": recorded, "error": error, "summary": summary}


def _import_day(ctx, date_str, entry):
    """Import one day. Returns {written, partial, entry, error} (all optional)."""
    if entry and entry.get("final"):
        return {}  # finished totals already in the grid
    if entry and not entry.get("cells") and entry.get("misses", 0) >= MAX_MISSES:
        return {}  # no data ever arrived for this day; stop asking
    vault = ctx["vault"]
    owned = (entry or {}).get("cells", {})
    current = vault.habit_row_cells(date_str) or {}  # None: row/month not created yet

    def writable(column):
        """True when a cell is blank or still holds our own earlier value."""
        cell = current.get(column, "")
        return not cell or cell == owned.get(column)

    if not any(writable(c) for c in HEALTH_COLUMNS):
        return {}  # every health cell was filled by hand
    metrics = read_health_metrics(ctx.get("health_export_dir"), date_str)
    if "error" in metrics:
        return {"error": f"{date_str}: {metrics['error']}"}
    if metrics.get("steps") is None:
        return {}
    partial = bool(metrics.get("partial"))
    fields = {"steps": metrics["steps"]}
    for key in ("calories", "weight"):
        if metrics.get(key) is not None:
            fields[key] = metrics[key]
    rings = rings_closed(metrics, ctx.get("ring_goals"))
    if rings:
        fields["rings"] = rings
    values = {
        column: cell
        for column, cell in habit_cell_values(fields).items()
        if writable(column) and current.get(column, "") != cell
        and not (partial and _shrinks(current.get(column, ""), cell))
    }
    new_entry = {"cells": dict(owned), "final": not partial}
    if not values:
        return {"entry": new_entry}  # nothing changed; maybe now final
    message = vault.upsert_habit_row(date_str, values)
    if not message.startswith("Updated"):
        return {"error": f"{date_str}: {message}"}
    new_entry["cells"].update(values)
    return {"written": True, "partial": partial, "entry": new_entry}


def _backfill_calories_from_mfp(ctx, days, today, lookback_days):
    """Fill still-empty Calories cells from MyFitnessPal (best-effort).

    MyFitnessPal is the calorie source of truth; the Apple Health export often
    lags or drops calories. Only finished days (ledger says final) whose
    Calories cell is blank are asked for, so hand-entered values are never
    touched. Does nothing unless mfp_source is configured, and never raises.
    Returns the list of "date (calories via MyFitnessPal)" strings written.
    """
    if not mfp_source.is_configured():
        return []
    vault = ctx["vault"]
    gaps = []
    for offset in range(1, lookback_days + 1):
        date_str = (today - timedelta(days=offset)).isoformat()
        entry = days.get(date_str) or {}
        cells = vault.habit_row_cells(date_str)
        if cells is None or not entry.get("final"):
            continue
        if not cells.get("Calories"):
            gaps.append(date_str)
    written = []
    try:
        fetched = mfp_source.fetch_calories(gaps) if gaps else {}
    except Exception as exc:  # strictly best-effort
        print(f"[health_import] MyFitnessPal backfill failed: {exc}", flush=True)
        return []
    for date_str, calories in fetched.items():
        values = habit_cell_values({"calories": calories})
        message = vault.upsert_habit_row(date_str, values)
        if message.startswith("Updated"):
            days[date_str].setdefault("cells", {}).update(values)
            written.append(f"{date_str} (calories via MyFitnessPal)")
    return written


def _shrinks(old_cell, new_cell):
    """True when a count cell would go down (a staler partial snapshot).

    Running daily totals only grow, so a partial read lower than what is
    already in the grid is older data and must not replace it.
    """
    try:
        return float(new_cell.replace(",", "")) < float(old_cell.replace(",", ""))
    except ValueError:
        return False


def last_run_status(state):
    """Return the ledger's last_run dict ({at, summary}) or None."""
    ledger = state._read_json(state.state_dir / LEDGER_FILE, {})
    return ledger.get("last_run")


def start_background_import(ctx, every_minutes):
    """Start a daemon thread that imports now and then every N minutes.

    every_minutes <= 0 disables it (returns None). Errors are logged and
    never kill the thread; the bot's main loop is unaffected either way.
    """
    if not every_minutes or every_minutes <= 0:
        return None

    def loop():
        """Import forever, sleeping between runs."""
        while True:
            try:
                result = import_recent_days(ctx)
                print(f"[health_import] {result['summary']}", flush=True)
            except Exception as exc:  # keep the thread alive on any bug
                print(f"[health_import] failed: {type(exc).__name__}: {exc}",
                      flush=True)
            time.sleep(every_minutes * 60)

    thread = threading.Thread(target=loop, name="health-import", daemon=True)
    thread.start()
    return thread
