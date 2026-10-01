"""Automatic import of Apple Health numbers into the monthly habit grid.

Runs on its own background thread (every `health_import_every_minutes`,
default 60) and once more right before Bartleby's nightly check-in, so the
grid fills itself as soon as the phone's Health Auto Export JSON lands — no
Telegram conversation required.

Rules, per recent past day (today is never written; its totals are still
growing):

  * Provenance is kept per health cell in the ledger: "cells" holds the last
    value any bot wrote (this importer, or a persona via record_habits) and
    "sources" says who wrote it ("import", "bartleby", "jeeves", ... or
    "user"). A filled cell whose value differs from the last bot-written
    value was typed by hand: it is marked "user" and never overwritten.
  * Bot-written cells (import or persona) are upgraded when a finished
    (non-partial) export for that day arrives. A 'partial' read (written
    before the day ended) still fills blanks and may raise a bot-written
    count, but never lowers one.
  * The FINAL_AFTER_DAYS most recent days (the check-in's window) are
    re-read on every run and never frozen. Older days in the lookback are
    marked final once a finished export has been read (or every health cell
    is hand-typed), and are not read again.

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
# Health numbers a persona's record_habits write is tagged as bot-written
# for. Rings is left out: a rings answer via the check-in is usually the
# user correcting the export's call, and their word beats the export.
BOT_TAGGED_COLUMNS = ("Steps", "Calories", "Weight")
LOOKBACK_DAYS = 7
# Days 1..FINAL_AFTER_DAYS before today are never marked final, so late or
# re-run phone exports keep upgrading them (matches the 9pm check-in's
# three-day window).
FINAL_AFTER_DAYS = 3
LEDGER_KEEP_DAYS = 45
DEFAULT_EVERY_MINUTES = 60
LEDGER_FILE = "health-import.json"
# Hourly reads of a day with no data at all before giving up on it (two
# days' worth): covers a phone that was off or away, without re-reading a
# dead day for the whole lookback window.
MAX_MISSES = 48

# Serializes the background thread, the check-in's synchronous run and
# persona provenance notes so ledger read-modify-writes never interleave.
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


def note_bot_write(state, date_str, values, source):
    """Record that a persona (source, e.g. "bartleby") wrote health cells.

    Called after a successful record_habits write so the importer knows
    those Steps/Calories/Weight values are bot-written and may upgrade them
    from a finished export. Clears "final" so the day is looked at again
    while it is still inside the lookback window.
    """
    health = {c: v for c, v in values.items() if c in BOT_TAGGED_COLUMNS and v}
    if not health:
        return
    with _IMPORT_LOCK:
        ledger_path = state.state_dir / LEDGER_FILE
        ledger = state._read_json(ledger_path, {})
        entry = ledger.setdefault("days", {}).setdefault(
            date_str, {"cells": {}, "final": False}
        )
        entry.setdefault("cells", {}).update(health)
        entry.setdefault("sources", {}).update({c: source for c in health})
        entry["final"] = False
        state._write_json(ledger_path, ledger)


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
            outcome = _import_day(ctx, date_str, entry, offset)
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


def _import_day(ctx, date_str, entry, offset):
    """Import one day. Returns {written, partial, entry, error} (all optional).

    offset is how many days before today date_str is; only days past
    FINAL_AFTER_DAYS can be marked final.
    """
    if entry and entry.get("final"):
        return {}  # finished totals already in the grid
    if entry and not entry.get("cells") and entry.get("misses", 0) >= MAX_MISSES:
        return {}  # no data ever arrived for this day; stop asking
    vault = ctx["vault"]
    entry = entry or {}
    owned = dict(entry.get("cells", {}))      # last bot-written value per column
    sources = dict(entry.get("sources", {}))  # who wrote each health cell
    current = vault.habit_row_cells(date_str) or {}  # None: row/month not created yet
    may_finalize = offset > FINAL_AFTER_DAYS

    # A filled cell that no longer matches what a bot last wrote was typed
    # (or corrected) by hand: it belongs to the user from now on.
    for column in HEALTH_COLUMNS:
        cell = current.get(column, "")
        if cell and cell != owned.get(column):
            owned.pop(column, None)
            sources[column] = "user"

    def writable(column):
        """True when a cell is blank or still holds a bot-written value."""
        return not current.get(column, "") or column in owned

    def make_entry(final, finished=False):
        """Ledger entry carrying the (possibly updated) provenance."""
        new = {"cells": owned, "sources": sources, "final": final}
        if finished or entry.get("finished"):
            new["finished"] = True
        return new

    if not any(writable(c) for c in HEALTH_COLUMNS):
        # Every health cell was filled by hand; nothing to read.
        return {"entry": make_entry(final=may_finalize)}
    metrics = read_health_metrics(ctx.get("health_export_dir"), date_str)
    if "error" in metrics:
        return {"error": f"{date_str}: {metrics['error']}"}
    if metrics.get("steps") is None:
        return {"entry": make_entry(final=False)}
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
    # A finished read only freezes a day once it has left the check-in
    # window; inside it the day keeps being re-read every run.
    new_entry = make_entry(final=(not partial) and may_finalize, finished=not partial)
    # Cells already holding the export's value count as import-written.
    for column, cell in habit_cell_values(fields).items():
        if column in owned and current.get(column, "") == cell and not partial:
            sources[column] = sources.get(column) or "import"
    if not values:
        return {"entry": new_entry}  # nothing changed
    message = vault.upsert_habit_row(date_str, values)
    if not message.startswith("Updated"):
        return {"error": f"{date_str}: {message}"}
    owned.update(values)
    sources.update({column: "import" for column in values})
    return {"written": True, "partial": partial, "entry": new_entry}


def _backfill_calories_from_mfp(ctx, days, today, lookback_days):
    """Fill still-empty Calories cells from MyFitnessPal (best-effort).

    MyFitnessPal is the calorie source of truth; the Apple Health export often
    lags or drops calories. Only days a finished export has been read for
    whose Calories cell is blank are asked for, so hand-entered values are
    never touched. Does nothing unless mfp_source is configured, and never
    raises. Returns the list of "date (calories via MyFitnessPal)" strings
    written.
    """
    if not mfp_source.is_configured():
        return []
    vault = ctx["vault"]
    gaps = []
    for offset in range(1, lookback_days + 1):
        date_str = (today - timedelta(days=offset)).isoformat()
        entry = days.get(date_str) or {}
        cells = vault.habit_row_cells(date_str)
        if cells is None or not (entry.get("final") or entry.get("finished")):
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
            day = days.setdefault(date_str, {"cells": {}, "final": False})
            day.setdefault("cells", {}).update(values)
            day.setdefault("sources", {})["Calories"] = "mfp"
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
