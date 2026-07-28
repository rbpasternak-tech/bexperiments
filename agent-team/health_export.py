"""Parses Health Auto Export JSON files (Apple Health -> iCloud folder).

The iPhone app exports files shaped like:
    {"data": {"metrics": [{"name": "step_count", "units": "count",
                           "data": [{"date": "2026-07-26 00:00:00 -0400",
                                     "qty": 12253.0}, ...]}, ...]}}
MyFitnessPal nutrition arrives via its Apple Health sync as dietary_energy.
"""

import json
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
    weight takes the last reading. Missing values are None.
    """
    directory = Path(export_dir).expanduser() if export_dir else None
    if not directory or not directory.is_dir():
        return {"error": "Health export folder not configured or not found."}
    files = sorted(
        directory.rglob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    for path in files:
        result = _metrics_from_file(path, date_str)
        if result:
            result["source_file"] = path.name
            return result
    return {"error": f"No health export data found for {date_str}."}


def _metrics_from_file(path, date_str):
    """Extract the date's metrics from one export file, or None if absent."""
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    metrics = (payload.get("data") or {}).get("metrics") or []
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
