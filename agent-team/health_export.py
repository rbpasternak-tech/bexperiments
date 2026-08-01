"""Parses Health Auto Export JSON files (Apple Health -> iCloud folder).

The iPhone app exports files shaped like:
    {"data": {"metrics": [{"name": "step_count", "units": "count",
                           "data": [{"date": "2026-07-26 00:00:00 -0400",
                                     "qty": 12253.0}, ...]}, ...]}}
MyFitnessPal nutrition arrives via its Apple Health sync as dietary_energy.
"""

import json
import os
import re
from pathlib import Path

METRIC_MAP = {
    "step_count": "steps",
    "steps": "steps",
    "dietary_energy": "calories",
    "weight_body_mass": "weight",
    "weight_and_body_mass": "weight",
    "body_mass": "weight",
}


def _normalize(name):
    """Normalize a metric name: lowercase, non-alphanumerics to underscores."""
    return re.sub(r"[^a-z0-9]+", "_", str(name).lower()).strip("_")


def read_health_metrics(export_dir, date_str):
    """Return {"steps", "calories", "weight"} for a YYYY-MM-DD date.

    Scans JSON files in export_dir newest-first and uses the first file that
    contains data for the date. Steps/calories are summed across entries;
    weight takes the last reading. Missing values are None. On failure the
    dict carries an "error" key that says exactly what went wrong (folder
    unconfigured/missing, macOS permission denial, undownloaded iCloud
    placeholders, or simply no data for the date).
    """
    if not export_dir:
        return {"error": "No health_export_dir configured in config.yaml."}
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
        return {"error": f"Health export folder does not exist: {directory}"}
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
        }
    return {
        "error": (
            f"No health export data found for {date_str} in "
            f"{len(files)} file(s) (newest: {files[0].name})."
        )
    }


def _mtime(path):
    """Return a file's mtime, or 0 when it vanishes mid-scan (iCloud)."""
    try:
        return path.stat().st_mtime
    except OSError:
        return 0


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
