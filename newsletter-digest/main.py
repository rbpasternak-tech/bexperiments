#!/usr/bin/env python3
"""Newsletter Digest — main entry point.

Fetches tech and legal tech newsletters from Gmail, scrapes RSS feeds,
summarizes everything with Claude, and sends a formatted digest email.

Usage:
    python main.py              # Full run: fetch, summarize, send email
    python main.py --dry-run    # Print digest to terminal instead of emailing
"""

import argparse
import sys
from datetime import datetime, timedelta

from config_loader import load_config
from gmail_client import fetch_emails, send_email
from newsletter_detector import detect_newsletters
from rss_fetcher import fetch_feeds
from summarizer import summarize
from digest_formatter import format_digest_html


def main():
    parser = argparse.ArgumentParser(description="Generate tech & legal tech newsletter digest")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print digest to terminal instead of sending email",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to config.yaml (defaults to config.yaml in project dir)",
    )
    args = parser.parse_args()

    # Load config
    print("Loading configuration...")
    config = load_config(args.config)

    lookback_days = config["gmail"]["lookback_days"]
    date_end = datetime.now()
    date_start = date_end - timedelta(days=lookback_days)

    # Step 1: Fetch emails from Gmail
    print(f"Fetching emails from the last {lookback_days} days...")
    emails = fetch_emails(
        lookback_days=lookback_days,
        max_emails=config["gmail"]["max_emails"],
    )
    print(f"  Found {len(emails)} total emails")

    # Step 2: Detect newsletters
    print("Detecting tech & legal tech newsletters...")
    newsletters = detect_newsletters(
        emails,
        sender_whitelist=config["newsletters"]["sender_whitelist"],
        keywords=config["newsletters"]["keywords"],
    )
    print(f"  Matched {len(newsletters)} newsletters")
    for nl in newsletters:
        print(f"    - {nl['sender']}: {nl['subject']}")

    # Step 3: Fetch RSS feeds
    print("Fetching RSS feeds...")
    rss_articles = fetch_feeds(
        feed_configs=config["rss_feeds"],
        lookback_days=lookback_days,
    )
    print(f"  Fetched {len(rss_articles)} articles from {len(config['rss_feeds'])} feeds")

    # Step 4: Summarize with Claude
    if not newsletters and not rss_articles:
        print("No content found for this period. Skipping digest.")
        return

    print(f"Summarizing {len(newsletters)} newsletters + {len(rss_articles)} articles with Claude...")
    digest_markdown = summarize(
        newsletters=newsletters,
        rss_articles=rss_articles,
        model=config["summarizer"]["model"],
        max_tokens=config["summarizer"]["max_tokens"],
    )

    # Step 5: Format and send/display
    date_range_start = date_start.strftime("%b %d, %Y")
    date_range_end = date_end.strftime("%b %d, %Y")

    if args.dry_run:
        print("\n" + "=" * 60)
        print(f"DIGEST: {date_range_start} — {date_range_end}")
        print("=" * 60 + "\n")
        print(digest_markdown)
        print("\n" + "=" * 60)
        print("(Dry run — email not sent)")
    else:
        print("Formatting HTML email...")
        html = format_digest_html(digest_markdown, date_range_start, date_range_end)

        subject = f"{config['digest']['subject_prefix']} — {date_range_end}"
        recipient = config["gmail"]["recipient_email"]

        print(f"Sending digest to {recipient}...")
        send_email(recipient, subject, html)
        print("Digest sent successfully!")


if __name__ == "__main__":
    main()
