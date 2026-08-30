"""Fetch daily calorie totals from MyFitnessPal, for the agent-team bot.

Runs in the ISOLATED MyFitnessPal venv (~/Library/Application Support/
agent-team/.mfp-venv), never the bot's own venv: the myfitnesspal package
pins an old typing-extensions that conflicts with the anthropic/pydantic
stack the bot depends on, so the two must stay in separate environments. The
bot calls this script as a subprocess (see mfp_source.py) and reads the JSON
it prints on stdout.

Auth is a SAVED cookie jar (written once by mfp_login.py), not a live read of
the browser's cookie store — a launchd daemon cannot reach the browser's
cookies, so the nightly run must rely on a persisted jar instead.

Usage:
    python mfp_fetch.py 2026-08-26 2026-08-27 2026-08-28

Prints one JSON object mapping each requested date to its calorie total
(integer) or null when that day has no logged calories. Exits non-zero with a
message on stderr when authentication fails, so the caller can tell "no
calories logged that day" (null, exit 0) apart from "cookies expired" (error).
"""
import json
import os
import pickle
import sys
from pathlib import Path

DEFAULT_COOKIE_FILE = (
    Path.home()
    / "Library"
    / "Application Support"
    / "agent-team"
    / "mfp_cookies.pkl"
)


def _cookie_file():
    """Return the cookie-jar path, overridable via MFP_COOKIE_FILE."""
    override = os.environ.get("MFP_COOKIE_FILE")
    return Path(override) if override else DEFAULT_COOKIE_FILE


def _load_client():
    """Build a MyFitnessPal client from the saved cookie jar.

    Raises SystemExit with an actionable message when the jar is missing or
    authentication is rejected (typically expired cookies).
    """
    import myfitnesspal

    path = _cookie_file()
    if not path.is_file():
        sys.exit(
            f"No MyFitnessPal cookie jar at {path}. Run mfp_login.py once "
            "(in the .mfp-venv) while logged into MyFitnessPal in your "
            "browser to create it."
        )
    with open(path, "rb") as handle:
        cookiejar = pickle.load(handle)
    try:
        return myfitnesspal.Client(cookiejar=cookiejar)
    except Exception as exc:  # noqa: BLE001 - surface any auth failure verbatim
        sys.exit(
            f"MyFitnessPal auth failed ({type(exc).__name__}: {exc}). The "
            "saved cookies have most likely expired — re-run mfp_login.py."
        )


def main(argv):
    """Fetch calories for each YYYY-MM-DD in argv and print them as JSON."""
    if not argv:
        sys.exit("usage: mfp_fetch.py YYYY-MM-DD [YYYY-MM-DD ...]")
    client = _load_client()
    out = {}
    for date_str in argv:
        year, month, day = (int(part) for part in date_str.split("-"))
        entry = client.get_date(year, month, day)
        calories = entry.totals.get("calories")
        out[date_str] = int(calories) if calories is not None else None
    print(json.dumps(out))


if __name__ == "__main__":
    main(sys.argv[1:])
