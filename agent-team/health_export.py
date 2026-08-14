"""Parses Health Auto Export data (Apple Health -> iCloud folder).

Two sources are read, in order of trust for a given date:

  * AutoSync .hae files (LZFSE-compressed JSON, one file per metric per
    day under AutoSync/HealthMetrics/). The app pushes these
    automatically overnight, no need to open it — a finished day
    usually lands the following morning.
  * Daily JSON exports from the app's file automations, shaped like:
        {"data": {"metrics": [{"name": "step_count", "units": "count",
                               "data": [{"date": "2026-07-26 00:00:00 -0400",
                                         "qty": 12253.0}, ...]}, ...]}}
    These only appear when the app is opened on the phone. The configured
    folder is scanned first; if it yields nothing, auto-discovered
    candidate folders (the app's iCloud container and any iCloud Drive
    folder named like an export/automation destination) are scanned too.

MyFitnessPal nutrition arrives via its Apple Health sync as dietary_energy.
"""

import json
import os
import re
import subprocess
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

METRIC_MAP = {
    "step_count": "steps",
    "steps": "steps",
    "dietary_energy": "calories",
    "weight_body_mass": "weight",
    "weight_and_body_mass": "weight",
    "body_mass": "weight",
    # Apple Watch ring ingredients (enable Active Energy, Exercise Time,
    # and Stand Hours in the Health Auto Export automation's metrics).
    "active_energy": "active_energy",
    "active_energy_burned": "active_energy",
    "apple_exercise_time": "exercise_minutes",
    "exercise_time": "exercise_minutes",
    "exercise_minutes": "exercise_minutes",
    "apple_stand_hour": "stand_hours",
    "apple_stand_hours": "stand_hours",
    "stand_hours": "stand_hours",
}

# Metrics AutoSync records twice per sample (kJ and kcal duplicates).
ENERGY_KEYS = {"calories", "active_energy"}
KCAL_PER_KJ = 1 / 4.184

# AutoSync records each weigh-in three times, once per unit (kg/lb/st).
# The habit grid and the daily JSON exports both use pounds, so pounds is
# the canonical unit; the factors convert the other two back to it.
WEIGHT_UNIT_TO_LB = {"lb": 1.0, "kg": 2.2046226218, "st": 14.0}
COMPRESSION_TOOL = "/usr/bin/compression_tool"


def _normalize(name):
    """Normalize a metric name: lowercase, non-alphanumerics to underscores."""
    return re.sub(r"[^a-z0-9]+", "_", str(name).lower()).strip("_")


def rings_closed(metrics, goals):
    """Judge ring closure from exported metrics against configured goals.

    goals is config.yaml's ring_goals: {move_kcal, exercise_min,
    stand_hours}. Returns "yes" when all three ring metrics meet their
    goals, "no" when any falls short, and None when goals aren't
    configured or a needed metric/goal is missing (unknown, don't guess).
    """
    if not goals:
        return None
    needed = (
        ("active_energy", "move_kcal"),
        ("exercise_minutes", "exercise_min"),
        ("stand_hours", "stand_hours"),
    )
    verdict = "yes"
    for metric_key, goal_key in needed:
        value, goal = metrics.get(metric_key), goals.get(goal_key)
        if value is None or not goal:
            return None
        if value < goal:
            verdict = "no"
    return verdict


def read_health_metrics(export_dir, date_str):
    """Return the day's metrics ({"steps", "calories", "weight", plus
    "active_energy"/"exercise_minutes"/"stand_hours" when the automation
    exports them) for a YYYY-MM-DD date.

    Two data paths, tried in order of trust:

      1. AutoSync .hae files (the phone pushes a finished day overnight);
         a complete day here beats everything else.
      2. When AutoSync has nothing for the date, the JSON exports — the
         configured folder first (_read_from_configured), then
         auto-discovered candidate folders (_fallback_from_candidates), so
         an automation writing to its own folder (e.g. "New Automations")
         still gets found. A fallback hit carries "source_dir" and a
         "warning" asking to point health_export_dir at that folder.

    On total failure the dict carries an "error" key that says exactly
    what went wrong (folder unconfigured/missing, macOS permission denial,
    undownloaded iCloud placeholders, or simply no data for the date).
    """
    # iCloud can expose a new filename before its contents are readable on
    # this Mac.  A short retry prevents the nightly check-in from treating
    # that normal synchronization window as a missing export.
    result = _read_health_metrics_once(export_dir, date_str)
    if "error" not in result or not _may_be_syncing(result):
        return result
    time.sleep(5)
    retry = _read_health_metrics_once(export_dir, date_str)
    if "error" not in retry:
        retry["sync_retry"] = True
    return retry


def _read_health_metrics_once(export_dir, date_str):
    """Read one snapshot: AutoSync .hae first, then the JSON exports in the
    configured folder, then partial AutoSync, then auto-discovered folders.

    The public function wraps this with the iCloud sync-window retry.
    """
    directory = Path(export_dir).expanduser() if export_dir else None
    sync_dir = _autosync_dir(directory) if directory else None
    autosync = _autosync_metrics(sync_dir, date_str) if sync_dir else None

    # A complete AutoSync day (phone pushed the finished day) wins outright.
    if autosync and not autosync.get("partial"):
        return autosync

    # Otherwise the JSON exports in the configured folder.
    configured = _read_from_configured(export_dir, date_str)
    if "error" not in configured:
        return configured

    # A partial AutoSync day still beats no data at all.
    if autosync:
        return autosync

    # Nothing in the configured folder — try auto-discovered candidates.
    fallback = _fallback_from_candidates(date_str, directory)
    if fallback:
        return fallback

    # Everything missed. Enrich the "no data" error with AutoSync freshness
    # so the operator knows whether the phone simply stopped pushing.
    if sync_dir and configured.get("error", "").startswith(
        "No health export data found"
    ):
        latest = _latest_core_sync_date(sync_dir)
        if latest and latest < date_str:
            configured["error"] += (
                f" AutoSync's newest core-metric day is {latest} — the "
                "Health Auto Export app on the phone has not pushed "
                "steps/energy/rings since then, so nothing past that date "
                "can be filled. Open the app on the phone and confirm "
                "AutoSync is on and has run recently."
            )
    return configured


def _read_from_configured(export_dir, date_str):
    """Scan only the configured folder's JSON exports, returning metrics or
    a specific {"error": ...} explaining why nothing was read."""
    if not export_dir:
        return {
            "error": "No health_export_dir configured in config.yaml."
            + _candidates_hint()
        }
    directory = Path(export_dir).expanduser()
    try:
        os.stat(directory)
    except PermissionError:
        return {
            "error": (
                f"macOS denied access to {directory} — if the bot runs "
                "under launchd, grant Full Disk Access to its Python binary "
                "(System Settings > Privacy & Security), or run it from "
                "Terminal."
            )
        }
    except OSError:
        return {
            "error": f"Health export folder does not exist: {directory}"
            + _candidates_hint(directory)
        }
    if not directory.is_dir():
        return {"error": f"Health export path is not a folder: {directory}"}
    try:
        files = sorted(directory.rglob("*.json"), key=_mtime, reverse=True)
        placeholders = len(list(directory.rglob("*.icloud")))
    except OSError as exc:
        return {"error": f"Could not scan {directory}: {exc}"}
    for path in files:
        result = _metrics_from_file(path, date_str)
        if result:
            result["source_file"] = path.name
            return result
    if placeholders:
        return {
            "error": (
                f"No data for {date_str}; {placeholders} export file(s) in "
                f"{directory} are iCloud placeholders not downloaded to "
                "this Mac. Open the folder in Finder or run: "
                f"brctl download '{directory}'"
            )
        }
    if not files:
        return {
            "error": (
                f"No JSON files in {directory} — has the Health Auto "
                "Export automation run and synced via iCloud yet?"
            )
            + _candidates_hint(directory)
        }
    return {
        "error": (
            f"No health export data found for {date_str} in "
            f"{len(files)} file(s) (newest: {files[0].name})."
        )
    }


def _fallback_from_candidates(date_str, exclude):
    """Scan candidate export folders for the date; None when nothing hits."""
    for candidate in find_candidate_export_dirs():
        if exclude is not None and candidate == exclude:
            continue
        result = _scan_folder(candidate, date_str)
        if result:
            result["source_dir"] = str(candidate)
            result["warning"] = (
                f"This data was found in {candidate}, which is NOT the "
                "configured health_export_dir — the automation is writing "
                "to a different folder than config.yaml points to. Set "
                "health_export_dir to this folder and restart the bot. "
                "Tell the user."
            )
            return result
    return None


def _scan_folder(directory, date_str):
    """Return the date's metrics from the newest matching JSON file in
    directory (recursive), or None."""
    try:
        files = sorted(directory.rglob("*.json"), key=_mtime, reverse=True)
    except OSError:
        return None
    for path in files:
        result = _metrics_from_file(path, date_str)
        if result:
            result["source_file"] = path.name
            return result
    return None


def _may_be_syncing(result):
    """Whether an error can reasonably disappear after iCloud catches up."""
    error = result.get("error", "")
    return error.startswith("No health export data found") or "placeholder" in error


def _mtime(path):
    """Return a file's mtime, or 0 when it vanishes mid-scan (iCloud)."""
    try:
        return path.stat().st_mtime
    except OSError:
        return 0


def _autosync_dir(export_dir):
    """Locate the app's AutoSync/HealthMetrics folder near export_dir."""
    base = Path(export_dir).expanduser()
    for root in (base, base.parent):
        candidate = root / "AutoSync" / "HealthMetrics"
        if candidate.is_dir():
            return candidate
    return None


def _autosync_metrics(sync_dir, date_str):
    """Read one day's metrics from AutoSync .hae files, or None if empty.

    Flags the result "partial" when the newest contributing file was
    last written before the day ended, i.e. the phone had not yet
    pushed the finished day's totals.
    """
    day_file = date_str.replace("-", "") + ".hae"
    found, newest_sync = {}, 0.0
    try:
        folders = sorted(p for p in sync_dir.iterdir() if p.is_dir())
    except OSError:
        return None
    for folder in folders:
        key = METRIC_MAP.get(_normalize(folder.name))
        if not key or key in found:
            continue
        entries = _read_hae_entries(folder / day_file)
        value = _aggregate_entries(key, entries or [])
        if value is None:
            continue
        found[key] = value
        newest_sync = max(newest_sync, _mtime(folder / day_file))
    if not found:
        return None
    found["source_file"] = f"AutoSync/HealthMetrics/*/{day_file}"
    if newest_sync < _day_end_epoch(date_str):
        found["partial"] = True
        found["note"] = (
            "phone last synced before this day ended; totals may be "
            "incomplete"
        )
    return found


def _latest_core_sync_date(sync_dir):
    """Return the newest YYYY-MM-DD an AutoSync-mapped metric has a .hae for.

    Sparse nutrition/supplement metrics can keep syncing after the core
    ring/step/energy metrics have stopped, so this reports the freshest
    date among the metrics the automation actually records — the honest
    "last time your phone pushed the numbers we care about" signal.
    Returns None when the folder is unreadable or empty.
    """
    newest = None
    try:
        folders = [p for p in sync_dir.iterdir() if p.is_dir()]
    except OSError:
        return None
    for folder in folders:
        if METRIC_MAP.get(_normalize(folder.name)) is None:
            continue
        try:
            names = [p.stem for p in folder.glob("*.hae")]
        except OSError:
            continue
        for stem in names:
            match = re.fullmatch(r"(\d{4})(\d{2})(\d{2})", stem)
            if match:
                date = "-".join(match.groups())
                if newest is None or date > newest:
                    newest = date
    return newest


def _read_hae_entries(path):
    """Decompress one LZFSE .hae file and return its sample list, or None.

    Uses macOS's built-in /usr/bin/compression_tool, so no third-party
    LZFSE library is required; when the tool is absent or decoding fails,
    returns None so the caller falls back to the JSON export path rather
    than crashing.
    """
    if not path.is_file() or not os.path.exists(COMPRESSION_TOOL):
        return None
    with tempfile.NamedTemporaryFile(suffix=".json") as out:
        proc = subprocess.run(
            [COMPRESSION_TOOL, "-decode", "-a", "lzfse",
             "-i", str(path), "-o", out.name],
            capture_output=True,
        )
        if proc.returncode != 0:
            return None
        try:
            payload = json.loads(Path(out.name).read_text())
        except (OSError, json.JSONDecodeError):
            return None
    data = payload.get("data") if isinstance(payload, dict) else None
    return data if isinstance(data, list) else None


def _aggregate_entries(key, entries):
    """Collapse a day's AutoSync samples into one value, or None.

    Energy metrics arrive duplicated in kJ and kcal, so only the kcal
    samples are summed (falling back to converted kJ). Weight takes the
    last reading; every other metric sums its samples.
    """
    if key in ENERGY_KEYS:
        kcal = [e["qty"] for e in entries
                if e.get("qty") is not None and e.get("unit") == "kcal"]
        if kcal:
            return int(round(sum(kcal)))
        kilojoules = [e["qty"] for e in entries
                      if e.get("qty") is not None and e.get("unit") == "kJ"]
        return int(round(sum(kilojoules) * KCAL_PER_KJ)) if kilojoules else None
    quantities = [e.get("qty") for e in entries if e.get("qty") is not None]
    if not quantities:
        return None
    if key == "weight":
        # AutoSync duplicates each weigh-in in kg/lb/st, so a plain
        # "last sample" grabs whichever unit sorted last (stone). Pick a
        # single known unit and convert it to pounds; fall back to the raw
        # last sample only when entries carry no recognizable unit.
        for unit, factor in WEIGHT_UNIT_TO_LB.items():
            in_unit = [e["qty"] for e in entries
                       if e.get("qty") is not None and e.get("unit") == unit]
            if in_unit:
                return round(float(in_unit[-1]) * factor, 1)
        return round(float(quantities[-1]), 1)
    return int(round(sum(quantities)))


def _day_end_epoch(date_str):
    """Return the local Unix timestamp for midnight after the given day."""
    try:
        day = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return 0.0
    return (day + timedelta(days=1)).timestamp()


KNOWN_EXPORT_DIRS = (
    # The app's own iCloud container ("Health Auto Export" in Finder's
    # iCloud Drive sidebar lives here on disk).
    "~/Library/Mobile Documents/iCloud~com~HealthExport~HealthAutoExport/Documents",
)
CLOUD_DOCS = "~/Library/Mobile Documents/com~apple~CloudDocs"


CANDIDATE_NAME = re.compile(r"health|automation|export", re.IGNORECASE)


def find_candidate_export_dirs():
    """Return existing folders on this machine that look like Health Auto
    Export destinations: the app's iCloud container, plus any folder in
    iCloud Drive proper whose name mentions health, automation, or export
    (the app names automation folders things like 'New Automations')."""
    found = []
    for spec in KNOWN_EXPORT_DIRS:
        path = Path(spec).expanduser()
        if path.is_dir():
            found.append(path)
    cloud = Path(CLOUD_DOCS).expanduser()
    try:
        children = list(cloud.iterdir()) if cloud.is_dir() else []
    except OSError:
        children = []
    for child in children:
        if child.is_dir() and CANDIDATE_NAME.search(child.name):
            found.append(child)
    return found


def _candidates_hint(exclude=None):
    """Suffix suggesting likely export folders, or '' when none exist."""
    candidates = [
        str(p) for p in find_candidate_export_dirs()
        if exclude is None or p != Path(exclude)
    ]
    if not candidates:
        return ""
    return (
        " Possible export folders found on this Mac: "
        + "; ".join(candidates)
        + " — set health_export_dir in config.yaml to the right one."
    )


def _metrics_from_file(path, date_str):
    """Extract the date's metrics from one export file, or None if absent."""
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    metrics = data.get("metrics") if isinstance(data, dict) else None
    metrics = metrics or []
    found = {}
    for metric in metrics:
        key = METRIC_MAP.get(_normalize(metric.get("name")))
        if not key:
            continue
        entries = [
            e for e in metric.get("data", [])
            if str(e.get("date", "")).startswith(date_str)
        ]
        if not entries:
            continue
        quantities = [e.get("qty") for e in entries if e.get("qty") is not None]
        if not quantities:
            continue
        if key == "weight":
            found[key] = round(float(quantities[-1]), 1)
        else:
            found[key] = int(round(sum(quantities)))
    return found or None
