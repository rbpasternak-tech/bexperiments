#!/usr/bin/env python3
"""Newsletter Digest — main entry point.

Fetches tech and legal tech newsletters from Gmail, scrapes RSS feeds,
summarizes everything with Claude, sends a formatted digest email, extracts
structured trend data for the dashboard and publishes it to GitHub ``main``.

Usage:
    python main.py                  # Full run: email digest, trends, publish
    python main.py --dry-run        # Print digest; no email, no data, no push
    python main.py --skip-trends    # Email only; no dashboard data or push
    python main.py --trends-only    # Dashboard data + publish, no email
    python main.py --backfill 2026-04-15   # Trends for a past window

Each stage is isolated: a failure in the email, trend extraction or git
publish step is logged with a traceback and the remaining stages still run.
The exit code is non-zero if any stage failed, so launchd's "last exit
code" shows it.
"""

import argparse
import fcntl
import os
import sys
import tempfile
import traceback
from datetime import datetime, timedelta

from config_loader import load_config
from dashboard_publisher import publish_dashboard_data

TRENDS_OUTPUT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "trends-dashboard", "data")
)
LOCK_PATH = os.path.join(tempfile.gettempdir(), "newsletter-digest.lock")


def parse_args(argv=None):
    """Parse command-line arguments.

    Args:
        argv: Argument list (defaults to sys.argv[1:]).

    Returns:
        argparse.Namespace with the parsed options.
    """
    parser = argparse.ArgumentParser(description="Generate tech & legal tech newsletter digest")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the digest instead of emailing it; never writes dashboard data or pushes",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to config.yaml (defaults to config.yaml in project dir)",
    )
    parser.add_argument(
        "--skip-trends",
        action="store_true",
        help="Skip trend data extraction and the git publish that follows it",
    )
    parser.add_argument(
        "--trends-only",
        action="store_true",
        help="Only extract and publish trend data, skip the email digest",
    )
    parser.add_argument(
        "--backfill",
        metavar="YYYY-MM-DD",
        default=None,
        type=lambda s: datetime.strptime(s, "%Y-%m-%d"),
        help="Backfill trends for the window ending on this date (implies --trends-only)",
    )
    return parser.parse_args(argv)


def acquire_run_lock(path=LOCK_PATH):
    """Take an exclusive, non-blocking lock so two runs never overlap.

    Args:
        path: Lock file path.

    Returns:
        The open lock file (keep a reference for the life of the run), or
        None if another run already holds the lock.
    """
    lock_file = open(path, "w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock_file.close()
        return None
    lock_file.write(str(os.getpid()))
    lock_file.flush()
    return lock_file


def main(argv=None):
    """Run the pipeline and return a process exit code.

    Args:
        argv: Argument list (defaults to sys.argv[1:]).

    Returns:
        0 if every stage that ran succeeded, 1 otherwise.
    """
    args = parse_args(argv)
    if args.backfill:
        args.trends_only = True
    print(f"=== newsletter-digest run started {datetime.now():%Y-%m-%d %H:%M:%S} ===")

    lock = None
    if not args.dry_run:
        lock = acquire_run_lock()
        if lock is None:
            print(f"Another newsletter-digest run holds {LOCK_PATH}; exiting.")
            return 1

    publish = not args.dry_run and not args.skip_trends
    pipeline_ok = False
    publish_ok = True
    try:
        pipeline_ok = run_pipeline(args)
    finally:
        # Runs even if the pipeline crashed, so data left unpublished by an
        # earlier run (no network, credentials unavailable) is retried.
        if publish:
            print("Publishing dashboard data to GitHub (origin/main)...")
            try:
                publish_ok = publish_dashboard_data()
            except Exception:
                traceback.print_exc()
                publish_ok = False
        if lock is not None:
            lock.close()

    ok = pipeline_ok and publish_ok
    print(f"=== run finished {'OK' if ok else 'WITH ERRORS'} "
          f"{datetime.now():%Y-%m-%d %H:%M:%S} ===")
    return 0 if ok else 1


def run_pipeline(args):
    """Fetch, summarize, email and extract trends according to ``args``.

    Args:
        args: Parsed command-line options.

    Returns:
        True if every stage that ran succeeded.

    Raises:
        Exception: Config, Gmail fetch or RSS errors propagate, since
            nothing useful can run without the input content.
    """
    # Imported here so the dashboard publisher still runs (from main's
    # finally block) even if a third-party dependency fails to import.
    from gmail_client import fetch_emails
    from newsletter_detector import detect_newsletters
    from rss_fetcher import fetch_feeds

    print("Loading configuration...")
    config = load_config(args.config)
    lookback_days = config["gmail"]["lookback_days"]

    if args.backfill:
        date_end = args.backfill
        date_start = date_end - timedelta(days=lookback_days)
        print(f"Backfill mode: {date_start.date()} → {date_end.date()}")
        print(f"Fetching emails between {date_start.date()} and {date_end.date()}...")
    else:
        date_end = datetime.now()
        date_start = date_end - timedelta(days=lookback_days)
        print(f"Fetching emails from the last {lookback_days} days...")

    emails = fetch_emails(
        lookback_days=lookback_days,
        max_emails=config["gmail"]["max_emails"],
        after_date=date_start if args.backfill else None,
        before_date=date_end if args.backfill else None,
    )
    print(f"  Found {len(emails)} total emails")

    print("Detecting tech & legal tech newsletters...")
    newsletters = detect_newsletters(
        emails,
        sender_whitelist=config["newsletters"]["sender_whitelist"],
        keywords=config["newsletters"]["keywords"],
    )
    print(f"  Matched {len(newsletters)} newsletters")
    for nl in newsletters:
        print(f"    - {nl['sender']}: {nl['subject']}")

    print("Fetching RSS feeds...")
    rss_articles = fetch_feeds(
        feed_configs=config["rss_feeds"],
        lookback_days=lookback_days,
        # A backfill must use articles from the backfill window, not today's.
        end_date=date_end if args.backfill else None,
    )
    print(f"  Fetched {len(rss_articles)} articles from {len(config['rss_feeds'])} feeds")

    if not newsletters and not rss_articles:
        print("No content found for this period. Skipping digest.")
        return True

    ok = True
    if not args.trends_only:
        sent = send_digest(args, config, newsletters, rss_articles, date_start, date_end)
        if sent and not args.dry_run:
            # Recorded right away so a later trends/publish failure, which the
            # scheduler retries, never sends the same digest twice.
            from schedule_guard import mark_sent_from_env
            mark_sent_from_env()
        ok = sent and ok

    if args.skip_trends:
        pass
    elif args.dry_run:
        print(f"(Dry run) Would extract trend data into {TRENDS_OUTPUT_DIR} "
              "and publish it to GitHub origin/main. Nothing written.")
    else:
        ok = extract_dashboard_trends(config, newsletters, rss_articles,
                                      date_start, date_end) and ok
    return ok


def send_digest(args, config, newsletters, rss_articles, date_start, date_end):
    """Summarize the content and email (or, in dry-run, print) the digest.

    Returns:
        True on success, False if summarizing or sending failed.
    """
    from digest_formatter import format_digest_html
    from summarizer import summarize

    try:
        print(f"Summarizing {len(newsletters)} newsletters + {len(rss_articles)} "
              "articles with Claude...")
        digest_markdown = summarize(
            newsletters=newsletters,
            rss_articles=rss_articles,
            model=config["summarizer"]["model"],
            max_tokens=config["summarizer"]["max_tokens"],
        )

        date_range_start = date_start.strftime("%b %d, %Y")
        date_range_end = date_end.strftime("%b %d, %Y")

        if args.dry_run:
            print("\n" + "=" * 60)
            print(f"DIGEST: {date_range_start} — {date_range_end}")
            print("=" * 60 + "\n")
            print(digest_markdown)
            print("\n" + "=" * 60)
            print("(Dry run — email not sent)")
            return True

        from gmail_client import send_email

        print("Formatting HTML email...")
        html = format_digest_html(digest_markdown, date_range_start, date_range_end)
        subject = f"{config['digest']['subject_prefix']} — {date_range_end}"
        recipient = config["gmail"]["recipient_email"]
        print(f"Sending digest to {recipient}...")
        send_email(recipient, subject, html)
        print("Digest sent successfully!")
        return True
    except Exception:
        print("ERROR: digest email failed:")
        traceback.print_exc()
        return False


def extract_dashboard_trends(config, newsletters, rss_articles, date_start, date_end):
    """Extract structured trend data into trends-dashboard/data/.

    Returns:
        True on success, False if extraction failed.
    """
    from trend_extractor import extract_trends

    print("Extracting structured trend data for dashboard...")
    try:
        extract_trends(
            newsletters=newsletters,
            rss_articles=rss_articles,
            date_start=date_start,
            date_end=date_end,
            model=config["summarizer"]["model"],
            output_dir=TRENDS_OUTPUT_DIR,
        )
        return True
    except Exception:
        print("ERROR: trend extraction failed:")
        traceback.print_exc()
        return False


if __name__ == "__main__":
    sys.exit(main())
