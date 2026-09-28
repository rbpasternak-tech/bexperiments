"""Bridge from the bot to the isolated MyFitnessPal fetcher.

The MyFitnessPal client cannot live in the bot's own venv (its
typing-extensions pin conflicts with anthropic/pydantic), so it runs in a
separate venv and this module shells out to it. Everything here is guarded:
any MyFitnessPal failure returns "no data" rather than propagating, so a dead
or expired MyFitnessPal integration never breaks the nightly health write.

MyFitnessPal is only consulted when its cookie jar exists (created by
mfp_login.py); otherwise fetch_calories() is a no-op.
"""
import json
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SUPPORT = Path.home() / "Library" / "Application Support" / "agent-team"
MFP_PYTHON = _SUPPORT / ".mfp-venv" / "bin" / "python"
FETCH_SCRIPT = _HERE / "mfp_fetch.py"
COOKIE_FILE = _SUPPORT / "mfp_cookies.pkl"


def is_configured():
    """True when the isolated venv and a saved cookie jar are both present."""
    return MFP_PYTHON.is_file() and COOKIE_FILE.is_file()


def fetch_calories(dates, timeout=120):
    """Return {date_str: calories} for the given dates via MyFitnessPal.

    Only dates MyFitnessPal has a calorie total for appear in the result.
    Returns an empty dict (and prints a diagnostic to stderr) on any failure
    — missing venv, expired cookies, network error — so callers can treat
    MyFitnessPal as strictly best-effort.
    """
    dates = [d for d in dates if d]
    if not dates or not is_configured():
        return {}
    try:
        proc = subprocess.run(
            [str(MFP_PYTHON), str(FETCH_SCRIPT), *dates],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        print(f"[mfp] fetch failed to run: {exc}", file=sys.stderr)
        return {}
    if proc.returncode != 0:
        print(f"[mfp] {proc.stderr.strip()}", file=sys.stderr)
        return {}
    try:
        raw = json.loads(proc.stdout)
    except json.JSONDecodeError:
        print(f"[mfp] unparseable output: {proc.stdout!r}", file=sys.stderr)
        return {}
    return {d: v for d, v in raw.items() if isinstance(v, int)}
