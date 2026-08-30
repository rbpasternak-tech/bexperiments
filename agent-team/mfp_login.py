"""Capture MyFitnessPal browser cookies once, for headless reuse by the bot.

Run this yourself, interactively, in the isolated MyFitnessPal venv, while
you are logged into MyFitnessPal (https://www.myfitnesspal.com) in a browser
on this Mac:

    ~/Library/Application\\ Support/agent-team/.mfp-venv/bin/python \\
        mfp_login.py

It reads your MyFitnessPal cookies from the browser and saves them to a jar
outside iCloud that mfp_fetch.py (and therefore the nightly bot) loads without
needing the browser. The cookies expire eventually; re-run this when the bot
reports MyFitnessPal auth has failed.

Nothing here is committed and no password is stored — only the session cookie
jar, in your local ~/Library.
"""
import pickle
import sys
from http.cookiejar import CookieJar
from pathlib import Path

from mfp_fetch import DEFAULT_COOKIE_FILE

# MyFitnessPal serves cookies from these hosts; grab whatever the browser has.
COOKIE_DOMAINS = ("www.myfitnesspal.com", "myfitnesspal.com")


def main():
    """Read MFP cookies from the local browser and pickle them to disk."""
    import browser_cookie3

    jar = CookieJar()
    total = 0
    for domain in COOKIE_DOMAINS:
        try:
            loaded = browser_cookie3.load(domain_name=domain)
        except Exception as exc:  # noqa: BLE001 - keep going across browsers
            print(f"  ({domain}: {type(exc).__name__}: {exc})")
            continue
        for cookie in loaded:
            jar.set_cookie(cookie)
            total += 1

    if total == 0:
        sys.exit(
            "No MyFitnessPal cookies found in any browser. Log into "
            "https://www.myfitnesspal.com in Chrome/Safari/Firefox on this "
            "Mac, then re-run."
        )

    path = Path(DEFAULT_COOKIE_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as handle:
        pickle.dump(jar, handle)
    print(f"Saved {total} MyFitnessPal cookie(s) to {path}")


if __name__ == "__main__":
    main()
